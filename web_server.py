#!/usr/bin/env python3
"""
AI Assistant Voice CS — Web Backend (FastAPI)
Nahrazuje staré Tkinter GUI moderním REST/SSE API pro lokální webovou aplikaci.
Plně zachovává logiku kognitivního jádra, nástrojů, Blender bridge, RAG a paměti.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import queue
import re
import shutil
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Optional

import anyio
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict

from blender_connector import (
    is_blender_available,
    request_auto_rig,
    request_mesh_audit,
    request_mesh_repair,
    request_procedural_shader,
    request_product_studio,
    request_scene_inspection,
)
from document_service import ConversationMemoryService, DocumentService
from history_repository import HistoryRepository
from llama_module import (
    ANALYTICAL_PRESETS,
    DEFAULT_ANALYTICAL_PRESET,
    DEFAULT_SYSTEM_PROMPT,
    PRESETS_CATALOG,
    classify_methodology,
    detect_analytical_mode,
    generate_response,
    initialize_llama,
    load_analytical_prompt,
)

logger = logging.getLogger("web_server")
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")

# ------------------------------------------------------------------------------
# Konfigurace a Inicializace komponent
# ------------------------------------------------------------------------------

def load_config(path: str = "config.json") -> dict:
    cfg_path = Path(path)
    if cfg_path.exists():
        with cfg_path.open("r", encoding="utf-8") as f:
            return json.load(f)
    return {}

config = load_config()

# Repositář historie a služeb
history_repository = HistoryRepository()
document_service = DocumentService(config=config)
memory_service = ConversationMemoryService(
    config=config,
    shared_model_provider=document_service.get_embedding_model if hasattr(document_service, "get_embedding_model") else None,
)
history_repository.set_memory_service(memory_service)

# Llama Model inicializace (lazy load / resilient fallback)
_llm_instance = None
_llm_lock = threading.Lock()
_whisper_instance = None
_whisper_lock = threading.Lock()

def get_llm():
    global _llm_instance
    with _llm_lock:
        if _llm_instance is None:
            try:
                logger.info("Inicializuji Llama model pro webový backend...")
                _llm_instance = initialize_llama(config)
                logger.info("Llama model úspěšně připraven.")
            except Exception as e:
                logger.warning("Llama model se nepodařilo inicializovat v procesu: %s (používám fallback)", e)
                _llm_instance = None
        return _llm_instance

def get_whisper():
    global _whisper_instance
    with _whisper_lock:
        if _whisper_instance is None:
            from stt_module import initialize_whisper

            _whisper_instance = initialize_whisper(config)
        return _whisper_instance

# ------------------------------------------------------------------------------
# Správa životního cyklu generování & stop eventů (izolace podle session_id)
# ------------------------------------------------------------------------------
active_stop_event = threading.Event()  # Zachováno pro zpětnou kompatibilitu
_session_stop_events: dict[str, threading.Event] = {}
_session_stop_lock = threading.Lock()

def get_session_stop_event(session_id: str) -> threading.Event:
    with _session_stop_lock:
        if session_id not in _session_stop_events:
            _session_stop_events[session_id] = threading.Event()
        else:
            _session_stop_events[session_id].clear()
        return _session_stop_events[session_id]

def stop_session(session_id: Optional[str] = None):
    with _session_stop_lock:
        if session_id and session_id in _session_stop_events:
            _session_stop_events[session_id].set()
            logger.info("Vyžádáno zastavení pro relaci %s", session_id)
        elif not session_id:
            for ev in _session_stop_events.values():
                ev.set()
            active_stop_event.set()
            logger.info("Vyžádáno zastavení všech aktivních relací.")

def cleanup_session_stop_event(session_id: str):
    with _session_stop_lock:
        _session_stop_events.pop(session_id, None)

# ------------------------------------------------------------------------------
# FastAPI Aplikace
# ------------------------------------------------------------------------------

app = FastAPI(
    title="Polygon Beater Voice CS — Local Web Engine",
    description="Autonomní webové rozhraní pro lokálního hlasového a 3D asistenta.",
    version="2.3.0",
)

ALLOWED_ORIGINS = [
    "http://127.0.0.1",
    "http://127.0.0.1:8000",
    "http://localhost",
    "http://localhost:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

SESSION_ID_REGEX = re.compile(r"^[a-zA-Z0-9_-]+$")


def is_safe_session_id(sid: str) -> bool:
    """Ověří, že session_id obsahuje pouze povolené znaky (alfanumerické a pomlčky/podtržítka)."""
    return bool(sid and SESSION_ID_REGEX.match(sid))

# ------------------------------------------------------------------------------
# Pydantic Schémata
# ------------------------------------------------------------------------------

class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    session_id: Optional[str] = None
    sessionId: Optional[str] = None
    prompt: Optional[str] = None
    message: Optional[str] = None
    language: Optional[str] = "en"
    analytical_preset: Optional[str] = None
    analyticalPreset: Optional[str] = None
    methodology: Optional[str] = None
    online_mode: Optional[bool] = None
    onlineMode: Optional[bool] = None
    tools_enabled: Optional[bool] = None
    toolsEnabled: Optional[bool] = None
    rag_enabled: Optional[bool] = None
    ragEnabled: Optional[bool] = None

class SessionRenameRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    title: Optional[str] = "Přejmenovaný chat"

class SettingsUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    n_ctx: Optional[int] = None
    analytical_preset: Optional[str] = None
    online_mode: Optional[bool] = None
    system_prompt: Optional[str] = None

# ------------------------------------------------------------------------------
# Endpoints: Systém & Stav
# ------------------------------------------------------------------------------

@app.get("/api/status")
def get_system_status():
    blender_cfg = config.get("blender", {})
    b_host = blender_cfg.get("host", "127.0.0.1")
    b_port = int(blender_cfg.get("port", 9876))
    blender_online = is_blender_available(b_host, b_port)

    doc_count = len(document_service.get_indexed_documents()) if document_service else 0
    chunk_count = document_service.total_chunks() if document_service else 0
    mem_stats = memory_service.get_memory_stats() if memory_service else {}

    return {
        "status": "online",
        "engine": "Polygon Beater Local Engine v2.3",
        "llm_loaded": _llm_instance is not None,
        "blender": {
            "connected": blender_online,
            "host": b_host,
            "port": b_port,
        },
        "rag": {
            "enabled": bool(config.get("rag", {}).get("enabled", True)),
            "total_documents": doc_count,
            "total_chunks": chunk_count,
            "memory_chunks": mem_stats.get("total_chunks", 0),
        },
        "analytical_presets": list(ANALYTICAL_PRESETS.keys()),
        "presets_catalog": PRESETS_CATALOG,
        "current_preset": config.get("llama", {}).get("analytical_preset", DEFAULT_ANALYTICAL_PRESET),
    }

# ------------------------------------------------------------------------------
# Endpoints: Konverzace & Relace (Sessions)
# ------------------------------------------------------------------------------

def _normalize_session_summary(s: dict) -> dict:
    sid = s.get("session_id") or s.get("id") or ""
    return {
        "id": sid,
        "session_id": sid,
        "title": s.get("title", "Nový chat"),
        "updated_at": s.get("updated_at", ""),
    }

@app.get("/api/sessions")
def list_sessions():
    sessions = history_repository.list_sessions()
    if not sessions:
        new_sess = history_repository.create_session("Nový chat")
        sessions = [new_sess]
    return {"sessions": [_normalize_session_summary(s) for s in sessions]}

@app.post("/api/sessions")
def create_session(title: str = "New chat"):
    clean_title = (title or "New chat").strip()
    sess = history_repository.create_session(clean_title)
    return _normalize_session_summary(sess)

@app.get("/api/sessions/{session_id}")
def get_session(session_id: str):
    if not is_safe_session_id(session_id):
        raise HTTPException(status_code=400, detail="Neplatné ID relace.")
    try:
        messages = history_repository.load_session(session_id)
        return {"session_id": session_id, "messages": messages}
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Relace nenalezena: {e}")

@app.patch("/api/sessions/{session_id}")
def rename_session(session_id: str, req: SessionRenameRequest):
    if not is_safe_session_id(session_id):
        raise HTTPException(status_code=400, detail="Neplatné ID relace.")
    try:
        with history_repository._lock:
            session = history_repository._read_session(session_id)
            session["title"] = history_repository._clean_title(req.title)
            session["updated_at"] = history_repository._now()
            history_repository._write_session(session_id, session)
        return {"status": "success", "session_id": session_id, "title": req.title}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/api/sessions/{session_id}")
def delete_session(session_id: str):
    if not is_safe_session_id(session_id):
        raise HTTPException(status_code=400, detail="Neplatné ID relace.")
    # Zastavit probíhající worker/stream pro danou relaci
    stop_session(session_id)
    cleanup_session_stop_event(session_id)
    # Kompletní odstranění složky relace a její historie z disku
    success = history_repository.delete_session(session_id)
    return {"status": "success", "session_id": session_id, "deleted": success}

@app.delete("/api/sessions/{session_id}/messages")
def clear_session_messages(session_id: str):
    if not is_safe_session_id(session_id):
        raise HTTPException(status_code=400, detail="Neplatné ID relace.")
    try:
        history_repository.clear(session_id)
        return {"status": "success", "session_id": session_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ------------------------------------------------------------------------------
# Endpoints: Chat & Streaming (SSE)
# ------------------------------------------------------------------------------

@app.post("/api/chat/stop")
async def stop_generation(request: Request):
    """
    Zastaví probíhající generování pro konkrétní relaci (nebo globálně, pokud není zadána).
    """
    sid = None
    try:
        body = await request.json()
        if isinstance(body, dict):
            sid = (body.get("session_id") or body.get("sessionId") or "").strip() or None
    except Exception:
        pass
    if not sid:
        sid = request.query_params.get("session_id") or None

    stop_session(sid)
    return {"status": "stopped", "session_id": sid}

@app.post("/api/chat")
async def chat_stream(req: ChatRequest, request: Request):
    """
    Streamovaný SSE endpoint pro interakci s asistentem.
    Podporuje Server-Sent Events (SSE) s okamžitým přenosem tokenů a statusů.
    Neblokuje FastAPI Event Loop a řádně uvolňuje prostředky při odpojení klienta.
    """
    # 1. Bezpečná resoluce a validace session_id
    session_id = (req.session_id or req.sessionId or "").strip()
    if session_id and not is_safe_session_id(session_id):
        logger.warning("Detekován neplatný formát session_id: %r", session_id)
        raise HTTPException(
            status_code=400,
            detail="Neplatné session_id. Povoleny jsou pouze alfanumerické znaky a pomlčky.",
        )

    if not session_id:
        existing = await anyio.to_thread.run_sync(history_repository.list_sessions)
        if existing and (existing[0].get("session_id") or existing[0].get("id")):
            session_id = existing[0].get("session_id") or existing[0].get("id")
        else:
            new_sess = await anyio.to_thread.run_sync(history_repository.create_session, "Nový chat")
            session_id = new_sess.get("session_id") or new_sess.get("id")
    else:
        # Ověříme, že relace existuje na disku, jinak ji vytvoříme
        def _ensure_session():
            session_file = history_repository.sessions_dir / f"{session_id}.json"
            if not session_file.exists():
                session_data = {
                    "session_id": session_id,
                    "title": "Nový chat",
                    "created_at": history_repository._now(),
                    "updated_at": history_repository._now(),
                    "messages": [],
                }
                history_repository._write_session(session_id, session_data)
        try:
            await anyio.to_thread.run_sync(_ensure_session)
        except Exception as exc:
            logger.warning("Inicializace souboru relace %s selhala: %s", session_id, exc)

    # 2. Bezpečná resoluce promptu
    user_prompt = (req.prompt or req.message or "").strip()
    if not user_prompt:
        raise HTTPException(status_code=400, detail="Prázdný dotaz.")

    # 3. Uložení zprávy uživatele do historie (neblokující I/O)
    await anyio.to_thread.run_sync(history_repository.append, session_id, "user", user_prompt)

    # 4. Resoluce příznaků (RAG, Web Tools, Metodika)
    rag_active = True
    if req.rag_enabled is not None:
        rag_active = bool(req.rag_enabled)
    elif req.ragEnabled is not None:
        rag_active = bool(req.ragEnabled)

    online_active = True
    if req.online_mode is not None:
        online_active = bool(req.online_mode)
    elif req.onlineMode is not None:
        online_active = bool(req.onlineMode)
    elif req.tools_enabled is not None:
        online_active = bool(req.tools_enabled)
    elif req.toolsEnabled is not None:
        online_active = bool(req.toolsEnabled)

    preset = req.analytical_preset or req.analyticalPreset or req.methodology

    # 5. Příprava RAG kontextu, pokud je zapnut (neblokující vektorové vyhledávání)
    retrieved_chunks = []
    rag_context = ""
    if rag_active and document_service and document_service.total_chunks() > 0:
        try:
            retrieved_chunks = await anyio.to_thread.run_sync(
                document_service.search, user_prompt, document_service.top_k
            )
            if retrieved_chunks:
                rag_context = await anyio.to_thread.run_sync(
                    document_service.format_chunks_for_prompt, retrieved_chunks
                )
        except Exception as exc:
            logger.error("Chyba při RAG vyhledávání: %s", exc)

    full_prompt = user_prompt
    if rag_context:
        full_prompt = (
            "RELEVANTNÍ DOKUMENTOVÝ KONTEXT (LOKÁLNÍ RAG ZAČÁTEK):\n"
            f"{rag_context}\n"
            "LOKÁLNÍ RAG KONEC\n\n"
            f"DOTAZ UŽIVATELE:\n{user_prompt}"
        )

    # 6. Příprava historie (posledních 6 zpráv, neblokující I/O)
    raw_history = await anyio.to_thread.run_sync(history_repository.load_session, session_id) or []
    chat_history = raw_history[:-1][-6:] if len(raw_history) > 1 else []

    # 7. Dočasné nastavení konfigurace pro request
    req_config = json.loads(json.dumps(config))
    req_config.setdefault("llama", {})
    req_lang = (req.language or "en").lower().strip()
    req_config["language"] = req_lang
    req_config["llama"]["language"] = req_lang
    req_config["llama"]["online_mode"] = online_active
    if preset:
        req_config["llama"]["analytical_preset"] = preset

    # Izolovaný stop event pro konkrétní relaci
    session_stop = get_session_stop_event(session_id)

    # Fronta pro přenos událostí z worker vlákna do SSE streamu
    event_queue: queue.Queue[dict[str, Any]] = queue.Queue()
    collected_tokens: list[str] = []
    collected_sentences: list[str] = []

    def worker():
        try:
            llm = get_llm()
            event_queue.put({"type": "session_id", "content": session_id})
            preset_now = req_config.get("llama", {}).get("analytical_preset", "")

            if preset_now in ("⚡ Auto (Doporučit)", "⚡ Auto-Select Methodology", "auto"):
                auto_status = "● 🧠 Determining optimal analytical methodology…" if req_lang == "en" else "● 🧠 Určuji optimální analytickou metodiku…"
                event_queue.put({"type": "status", "content": auto_status})
                detected = classify_methodology(llm, user_prompt, language=req_lang)
                req_config["llama"]["analytical_preset"] = detected
                event_queue.put({"type": "methodology", "content": detected})

            def _on_token(token: str):
                collected_tokens.append(token)
                event_queue.put({"type": "token", "content": token, "chunk": token})

            def _on_status(status: str):
                event_queue.put({"type": "status", "content": status})

            def _on_tool(event_type: str, data: dict[str, Any]):
                payload = {"type": event_type}
                payload.update(data)
                event_queue.put(payload)
                # Odeslání specializovaných SSE eventů pro UI panely (Research / RAG)
                if event_type == "tool_end":
                    tool_name = data.get("tool")
                    tool_res = data.get("result", {})
                    if tool_name == "search_web":
                        sources_list = []
                        if isinstance(tool_res, dict):
                            sources_list = tool_res.get("sources") or tool_res.get("results") or []
                        elif isinstance(data.get("sources"), list):
                            sources_list = data["sources"]
                        elif isinstance(data.get("results"), list):
                            sources_list = data["results"]

                        if not isinstance(sources_list, list):
                            sources_list = []

                        if not sources_list and isinstance(tool_res, dict) and "result" in tool_res:
                            import re
                            res_text = str(tool_res.get("result", ""))
                            for m in re.finditer(r"\[([^\]]+)\]\((https?://[^\)]+)\)", res_text):
                                sources_list.append({"title": m.group(1), "url": m.group(2), "snippet": ""})

                        event_queue.put({
                            "type": "web_search",
                            "query": data.get("arguments", {}).get("query", user_prompt),
                            "results": sources_list,
                            "sources": sources_list,
                        })
                    elif tool_name in ("query_local_rag", "query_memory_rag"):
                        res_val = tool_res.get("result", "") if isinstance(tool_res, dict) else str(tool_res)
                        event_queue.put({
                            "type": "rag_context",
                            "content": res_val,
                        })

            for chunk in generate_response(
                llm,
                full_prompt,
                req_config,
                chat_history=chat_history,
                callback_on_token=_on_token,
                status_callback=_on_status,
                stop_event=session_stop,
                document_service=document_service,
                memory_service=memory_service,
                active_session_id=session_id,
                tool_callback=_on_tool,
            ):
                collected_sentences.append(chunk)

            full_reply = "".join(collected_tokens).strip() or " ".join(collected_sentences).strip()
            if full_reply:
                history_repository.append(session_id, "assistant", full_reply)

            event_queue.put({"type": "done", "content": full_reply})
        except Exception as e:
            logger.exception("Chyba při generování odpovědi: %s", e)
            err_msg = f"Došlo k chybě: {e}"
            event_queue.put({"type": "error", "content": err_msg})
        finally:
            event_queue.put({"type": "finish"})

    # Spuštění generování na pozadí
    thread = threading.Thread(target=worker, daemon=True)
    thread.start()

    async def event_generator():
        done_sent = False
        full_reply_text = ""
        last_event_time = time.monotonic()
        heartbeat_interval = 15.0  # Periodický ping každých 15 sekund, dokud model nebo nástroj počítá
        try:
            while True:
                # Detekce odpojení klienta (zavření okna prohlížeče / přerušení spojení)
                if await request.is_disconnected():
                    logger.info("Klient se odpojil, ukončuji SSE stream pro relaci: %s", session_id)
                    session_stop.set()
                    break

                try:
                    item = event_queue.get_nowait()
                except queue.Empty:
                    if not thread.is_alive() and event_queue.empty():
                        break
                    # Odeslat heartbeat ping při nečinnosti fronty každých 15 sekund
                    now = time.monotonic()
                    if now - last_event_time >= heartbeat_interval:
                        last_event_time = now
                        yield f"data: {json.dumps({'type': 'ping'}, ensure_ascii=False)}\n\n"
                    await asyncio.sleep(0.02)
                    continue

                last_event_time = time.monotonic()
                msg_type = item.get("type")
                if msg_type == "finish":
                    break

                if msg_type == "done":
                    done_sent = True
                    full_reply_text = item.get("content", "")

                yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"

            # Garantovaný koncový signál a [DONE] pro každý SSE stream
            if not await request.is_disconnected():
                if not done_sent:
                    yield f"data: {json.dumps({'type': 'done', 'content': full_reply_text}, ensure_ascii=False)}\n\n"
                    done_sent = True
                yield "data: [DONE]\n\n"
        except Exception as exc:
            logger.warning("Výjimka v SSE event_generator pro relaci %s: %s", session_id, exc)
            if not done_sent and not await request.is_disconnected():
                try:
                    yield f"data: {json.dumps({'type': 'done', 'content': full_reply_text}, ensure_ascii=False)}\n\n"
                    yield "data: [DONE]\n\n"
                except Exception:
                    pass
        finally:
            if thread.is_alive():
                session_stop.set()
            cleanup_session_stop_event(session_id)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

# ------------------------------------------------------------------------------
# Endpoints: 3D Blender Bridge & Telemetrie
# ------------------------------------------------------------------------------

@app.get("/api/blender/status")
def blender_status():
    b_cfg = config.get("blender", {})
    host = b_cfg.get("host", "127.0.0.1")
    port = int(b_cfg.get("port", 9876))
    online = is_blender_available(host, port)
    return {"connected": online, "host": host, "port": port}

@app.post("/api/blender/inspect")
def blender_inspect():
    b_cfg = config.get("blender", {})
    host = b_cfg.get("host", "127.0.0.1")
    port = int(b_cfg.get("port", 9876))
    output_path = "/tmp/ai_assistant_viewport.png"
    res = request_scene_inspection(host=host, port=port, output_path=output_path)
    return res

@app.post("/api/blender/auto-rig")
def blender_auto_rig(rig_type: str = "basic"):
    b_cfg = config.get("blender", {})
    host = b_cfg.get("host", "127.0.0.1")
    port = int(b_cfg.get("port", 9876))
    res = request_auto_rig(host=host, port=port, rig_type=rig_type)
    return res

@app.post("/api/blender/mesh-doctor")
def blender_mesh_doctor(action: str = "audit", merge_distance: float = 0.0001):
    b_cfg = config.get("blender", {})
    host = b_cfg.get("host", "127.0.0.1")
    port = int(b_cfg.get("port", 9876))
    if action == "repair":
        return request_mesh_repair(host=host, port=port, merge_distance=merge_distance)
    return request_mesh_audit(host=host, port=port)

@app.post("/api/blender/product-studio")
def blender_product_studio(style: str = "standard"):
    b_cfg = config.get("blender", {})
    host = b_cfg.get("host", "127.0.0.1")
    port = int(b_cfg.get("port", 9876))
    return request_product_studio(host=host, port=port, style=style)

@app.post("/api/blender/procedural-shader")
def blender_procedural_shader(shader_type: str = "brushed_metal", material_name: Optional[str] = None):
    b_cfg = config.get("blender", {})
    host = b_cfg.get("host", "127.0.0.1")
    port = int(b_cfg.get("port", 9876))
    return request_procedural_shader(material_name=material_name, shader_type=shader_type, host=host, port=port)

@app.get("/api/blender/viewport-image")
def get_viewport_image():
    """Vrátí aktuální pořízený snímek viewportu z Blenderu."""
    candidates = [
        Path("/tmp/ai_assistant_viewport.png"),
        Path("/tmp/blender_viewport.png"),
    ]
    for c in candidates:
        if c.exists() and c.is_file():
            return FileResponse(
                str(c),
                media_type="image/png",
                headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
            )

    # Pokud snímek ještě neexistuje, vrátit placeholder SVG
    svg_placeholder = """<svg xmlns="http://www.w3.org/2000/svg" width="400" height="250" viewBox="0 0 400 250">
      <rect width="100%" height="100%" fill="#161922"/>
      <path d="M160 85 L240 85 L200 155 Z" fill="none" stroke="#38bdf8" stroke-width="2" stroke-dasharray="4,4"/>
      <circle cx="200" cy="120" r="40" fill="none" stroke="#818cf8" stroke-width="2"/>
      <text x="50%" y="185" font-family="system-ui, sans-serif" font-size="13" fill="#64748b" text-anchor="middle">
        3D Viewport čeká na první inspekci
      </text>
    </svg>"""
    return Response(content=svg_placeholder, media_type="image/svg+xml")

# ------------------------------------------------------------------------------
# Endpoints: RAG & Sémantická Paměť
# ------------------------------------------------------------------------------

@app.get("/api/rag/documents")
def get_rag_documents():
    docs = document_service.get_indexed_documents() if document_service else []
    total_ch = document_service.total_chunks() if document_service else 0
    return {"documents": docs, "total_chunks": total_ch}

@app.post("/api/rag/upload")
async def upload_rag_document(file: UploadFile = File(...)):
    """
    Nahraje a zindexuje dokument do RAG databáze.
    Neblokuje FastAPI Event Loop a spolehlivě odstraňuje dočasné soubory po indexaci.
    """
    raw_filename = file.filename or "upload.txt"
    # Původní název uchováme pouze jako bezpečná metadata
    safe_metadata_filename = Path(raw_filename).name.strip() or "upload.txt"
    suffix = Path(safe_metadata_filename).suffix.lower()

    # Vygenerujeme bezpečný náhodný název na disku (uuid) pro zamezení path traversal
    random_disk_filename = f"{uuid.uuid4().hex}{suffix}"

    temp_dir = (Path(tempfile.gettempdir()) / "rag_uploads").resolve()
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_path = (temp_dir / random_disk_filename).resolve()

    # Striktní ověření, že cesta neleží mimo vyhrazený dočasný adresář
    if not temp_path.is_relative_to(temp_dir):
        raise HTTPException(status_code=400, detail="Neplatný název souboru.")

    try:
        def _save_file():
            with temp_path.open("wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

        await anyio.to_thread.run_sync(_save_file)

        if not document_service:
            raise HTTPException(status_code=400, detail="RAG služba není dostupná.")

        chunk_count = await anyio.to_thread.run_sync(document_service.index_file, temp_path)
        return {
            "status": "success",
            "filename": safe_metadata_filename,
            "chunks_indexed": chunk_count,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Chyba při indexaci dokumentu: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        try:
            if temp_path.exists():
                temp_path.unlink()
                logger.info("Dočasný soubor po RAG uploadu byl bezpečně odstraněn: %s", temp_path)
        except Exception as cleanup_err:
            logger.warning("Nepodařilo se odstranit dočasný soubor %s: %s", temp_path, cleanup_err)

@app.post("/api/stt/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    """Přepíše krátkou nahrávku lokálním modelem Whisper."""
    max_audio_bytes = 15 * 1024 * 1024
    media_type = (file.content_type or "").split(";", 1)[0].strip().lower()
    audio_suffixes = {
        "audio/webm": ".webm",
        "audio/ogg": ".ogg",
        "audio/mp4": ".mp4",
        "audio/wav": ".wav",
        "audio/x-wav": ".wav",
        "audio/mpeg": ".mp3",
        "audio/mp3": ".mp3",
        "audio/flac": ".flac",
    }
    suffix = audio_suffixes.get(media_type)
    if not suffix:
        raise HTTPException(status_code=415, detail="Nepodporovaný formát zvukové nahrávky.")

    contents = await file.read(max_audio_bytes + 1)
    if not contents:
        raise HTTPException(status_code=400, detail="Zvuková nahrávka je prázdná.")
    if len(contents) > max_audio_bytes:
        raise HTTPException(status_code=413, detail="Zvuková nahrávka překračuje limit 15 MB.")

    temp_dir = (Path(tempfile.gettempdir()) / "stt_uploads").resolve()
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_path = temp_dir / f"{uuid.uuid4().hex}{suffix}"
    try:
        await anyio.to_thread.run_sync(temp_path.write_bytes, contents)

        def _transcribe() -> str:
            model = get_whisper()
            whisper_cfg = config.get("whisper", {})
            segments, _ = model.transcribe(
                str(temp_path),
                language=whisper_cfg.get("language", "cs"),
                beam_size=int(whisper_cfg.get("beam_size", 1)),
                temperature=float(whisper_cfg.get("temperature", 0.0)),
                condition_on_previous_text=False,
                vad_filter=True,
            )
            valid_segments = []
            for segment in segments:
                if segment.no_speech_prob is not None and segment.no_speech_prob > 0.6:
                    continue
                if segment.compression_ratio is not None and segment.compression_ratio > 2.4:
                    continue
                text = segment.text.strip()
                if text:
                    valid_segments.append(text)
            return " ".join(valid_segments).strip()

        text = await anyio.to_thread.run_sync(_transcribe)
        return {"text": text}
    except Exception as exc:
        logger.exception("Lokální přepis nahrávky selhal: %s", exc)
        raise HTTPException(status_code=500, detail=f"Lokální přepis selhal: {exc}") from exc
    finally:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError as cleanup_err:
            logger.warning("Nepodařilo se odstranit dočasnou nahrávku %s: %s", temp_path, cleanup_err)

@app.delete("/api/rag/documents/{doc_name}")
def delete_rag_document(doc_name: str):
    if not document_service:
        raise HTTPException(status_code=400, detail="RAG služba není dostupná.")
    success = document_service.delete_document(doc_name)
    return {"status": "success" if success else "not_found", "document": doc_name}

@app.post("/api/rag/memory/reindex")
def reindex_all_memory():
    res = history_repository.reindex_all_to_memory()
    return {"status": "success", "result": res}

# ------------------------------------------------------------------------------
# Endpoints: Konfigurace & Nastavení
# ------------------------------------------------------------------------------

@app.get("/api/config")
def get_config():
    return {
        "config": config,
        "analytical_presets": list(ANALYTICAL_PRESETS.keys()),
        "default_preset": DEFAULT_ANALYTICAL_PRESET,
        "default_system_prompt": DEFAULT_SYSTEM_PROMPT,
    }

@app.post("/api/config")
def update_config(req: SettingsUpdateRequest):
    llama_cfg = config.setdefault("llama", {})
    if req.temperature is not None:
        llama_cfg["temperature"] = req.temperature
    if req.max_tokens is not None:
        llama_cfg["max_tokens"] = req.max_tokens
    if req.n_ctx is not None:
        llama_cfg["n_ctx"] = req.n_ctx
    if req.analytical_preset is not None:
        llama_cfg["analytical_preset"] = req.analytical_preset
    if req.online_mode is not None:
        llama_cfg["online_mode"] = req.online_mode
    if req.system_prompt is not None:
        llama_cfg["system_prompt"] = req.system_prompt

    # Uložení do config.json
    try:
        with open("config.json", "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
    except Exception as exc:
        logger.warning("Nepodařilo se uložit config.json: %s", exc)

    return {"status": "success", "config": config}

@app.post("/api/app/shutdown")
def shutdown_app():
    """Ukončí běžící desktopový server a aplikaci na vyžádání z UI."""
    logger.info("Přijat požadavek na ukončení aplikace skrze API (/api/app/shutdown)")
    def _delayed_exit():
        time.sleep(0.2)
        try:
            os.kill(os.getpid(), signal.SIGTERM)
        except Exception:
            pass
    threading.Thread(target=_delayed_exit, daemon=True).start()
    return {"status": "shutting_down"}

# ------------------------------------------------------------------------------
# Statické soubory frontendu
# ------------------------------------------------------------------------------

web_ui_dir = Path(__file__).parent / "web_ui"
if web_ui_dir.exists():
    app.mount("/", StaticFiles(directory=str(web_ui_dir), html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("web_server:app", host="127.0.0.1", port=8000, reload=False)
