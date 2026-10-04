#!/usr/bin/env python3
"""
AI Assistant Voice CS — Web Backend (FastAPI)
Nahrazuje staré Tkinter GUI moderním REST/SSE API pro lokální webovou aplikaci.
Plně zachovává logiku kognitivního jádra, nástrojů, Blender bridge, RAG a paměti.
"""

from __future__ import annotations

import asyncio
import ipaddress
import json
import logging
import os
import queue
import re
import shutil
import signal
import subprocess
import tempfile
import threading
import time
import uuid
import webbrowser
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

import aiohttp
import anyio
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from blender_connector import (
    is_blender_available,
    request_auto_rig,
    request_mesh_audit,
    request_mesh_repair,
    request_procedural_shader,
    request_product_studio,
    request_scene_inspection,
    request_uv_audit,
    send_code_to_blender,
)
from document_service import ConversationMemoryService, DocumentService
from history_repository import HistoryRepository
from project_repository import ProjectPathError, ProjectRepository, clean_project_name, ensure_project_dir, resolve_project_path
from llama_module import (
    ANALYTICAL_PRESETS,
    DEFAULT_ANALYTICAL_PRESET,
    DEFAULT_SYSTEM_PROMPT,
    DEFAULT_WORKSPACE_DIR,
    PRESETS_CATALOG,
    OpenAICompatibleClient,
    apply_workspace_write_proposal,
    classify_methodology,
    detect_analytical_mode,
    detect_workspace_request,
    generate_response,
    get_workspace_dir,
    is_default_workspace,
    initialize_llama,
    load_analytical_prompt,
    reset_workspace_dir,
    scan_local_models,
    set_workspace_dir,
    test_provider_connection,
    unload_llama_model,
    WORKSPACE_AGENT_TOOL_NAMES,
)
from web_search import PublicOnlyResolver, _safe_get, is_safe_web_url

logger = logging.getLogger("web_server")
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")
_pending_workspace_diffs: dict[str, dict[str, Any]] = {}
_pending_workspace_diffs_lock = threading.Lock()
_MAX_PENDING_WORKSPACE_DIFFS = 100

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

def require_loopback_client(request: Request) -> None:
    client_host = request.client.host if request.client else ""
    if client_host in ("testclient", "localhost", "127.0.0.1", "::1"):
        return
    try:
        is_loopback = ipaddress.ip_address(client_host).is_loopback
    except ValueError:
        is_loopback = False
    if not is_loopback:
        raise HTTPException(status_code=403, detail="Tato operace je povolena pouze z lokálního zařízení.")

def save_config_file(path: str = "config.json") -> bool:
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
        mode = 0o600
        fd = os.open(path, flags, mode)
        with open(fd, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        try:
            os.chmod(path, 0o600)
        except Exception:
            pass
        return True
    except Exception as exc:
        logger.warning("Nepodařilo se uložit config.json: %s", exc)
        return False


def mask_api_key(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 8:
        return "••••••••"
    return f"{key[:3]}••••••••{key[-4:]}"

def get_active_provider_info() -> dict[str, Any]:
    provider_cfg = config.get("llm_provider", {})
    active = provider_cfg.get("active_provider", "local")
    if active == "groq":
        g = provider_cfg.get("groq", {})
        m = g.get("model") or "openai/gpt-oss-120b"
        return {"provider": "groq", "model": m, "display_name": f"Groq: {m}", "is_cloud": True}
    elif active == "gemini":
        gm = provider_cfg.get("gemini", {})
        m = gm.get("model") or "gemini-flash-latest"
        return {"provider": "gemini", "model": m, "display_name": f"Gemini: {m}", "is_cloud": True}
    elif active == "custom":
        c = provider_cfg.get("custom", {})
        pname = c.get("provider_name") or "API"
        m = c.get("model") or "gpt-4o"
        return {"provider": "custom", "model": m, "display_name": f"{pname}: {m}", "is_cloud": True}
    else:
        m = config.get("llama", {}).get("model", "Qwen2.5-7B-Instruct-Q4_K_M.gguf")
        fname = Path(m).name
        clean_m = fname[:-5] if fname.lower().endswith(".gguf") else fname
        short_name = clean_m.split("-")[0] if "-" in clean_m else clean_m
        return {"provider": "local", "model": fname, "display_name": f"{short_name} (Local)", "is_cloud": False}

# Repositář historie a služeb
history_repository = HistoryRepository()
project_repository = ProjectRepository(history_repository.sessions_dir.parent / "projects.json")
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
    provider_cfg = config.get("llm_provider", {})
    active_provider = provider_cfg.get("active_provider", "local")

    if active_provider != "local":
        p_data = provider_cfg.get(active_provider, {})
        base_url = p_data.get("base_url", "")
        api_key = p_data.get("api_key", "")
        model = p_data.get("model", "")

        if active_provider == "groq":
            base_url = base_url or "https://api.groq.com/openai/v1"
            model = model or "openai/gpt-oss-120b"
        elif active_provider == "gemini":
            base_url = base_url or "https://generativelanguage.googleapis.com/v1beta/openai/"
            model = model or "gemini-flash-latest"
        elif active_provider == "custom":
            base_url = base_url or "https://api.openai.com/v1"
            model = model or "gpt-4o"

        return OpenAICompatibleClient(
            base_url=base_url,
            api_key=api_key,
            model=model,
            timeout=float(config.get("llama", {}).get("timeout", 90.0)),
        )

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

def reload_local_llm(new_model_path: Optional[str] = None):
    global _llm_instance
    with _llm_lock:
        target_path = new_model_path.strip() if new_model_path else config.get("llama", {}).get("model")
        if not target_path or not Path(target_path).exists():
            raise FileNotFoundError(f"Modelový soubor nebyl nalezen na cestě: {target_path}")

        # Vytvoříme testovací konfiguraci a zavedeme nový model před uvolněním starého
        test_config = json.loads(json.dumps(config))
        test_config.setdefault("llama", {})["model"] = target_path

        logger.info("Zavádím nový model do paměti: %s", target_path)
        new_instance = initialize_llama(test_config)
        if new_instance is None:
            raise RuntimeError(f"Inicializace modelu '{target_path}' selhala.")

        # Nový model byl úspěšně vytvořen, bezpečně uvolníme starý
        if _llm_instance is not None:
            logger.info("Uvolňuji stávající model z paměti RAM/VRAM...")
            try:
                unload_llama_model(_llm_instance)
            except Exception as e:
                logger.warning("Upozornění při uvolňování starého modelu: %s", e)

        _llm_instance = new_instance
        if new_model_path:
            config.setdefault("llama", {})["model"] = target_path
        save_config_file()

        logger.info("Nový lokální model úspěšně zaveden.")
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


@app.middleware("http")
async def security_shield_middleware(request: Request, call_next):
    """
    Bezpečnostní middleware štít:
    1. Network Loopback Shield: Všechny /api/ endpointy jsou přístupné výhradně z lokálního zařízení (loopback).
    2. Anti-CSRF Guard: Všechny mutační metody (POST, PUT, PATCH, DELETE) vyžadují hlavičku X-Polygon-Client: true.
    """
    if request.method == "OPTIONS":
        return await call_next(request)

    # 1. DNS Rebinding Shield: Ověření Host hlavičky (přístup pouze přes loopback)
    raw_host = request.headers.get("host") or ""
    host_name = raw_host.strip().lower()
    if host_name:
        if host_name.startswith("[") and "]" in host_name:
            host_name = host_name[:host_name.index("]") + 1]
        elif ":" in host_name:
            host_name = host_name.split(":", 1)[0]
        if host_name not in ("127.0.0.1", "localhost", "::1", "[::1]", "testserver"):
            return JSONResponse(
                status_code=403,
                content={"detail": "Neplatná Host hlavička: přístup povolen pouze přes loopback."},
            )

    # 2. Loopback ochrana pro všechny /api/ endpointy
    if request.url.path.startswith("/api/"):
        client_host = request.client.host if request.client else ""
        if client_host not in ("testclient", "localhost", "127.0.0.1", "::1"):
            try:
                if not ipaddress.ip_address(client_host).is_loopback:
                    return JSONResponse(
                        status_code=403,
                        content={"detail": "Tato operace je povolena pouze z lokálního zařízení."},
                    )
            except ValueError:
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Tato operace je povolena pouze z lokálního zařízení."},
                )

    # 2. Anti-CSRF ochrana pro mutační HTTP požadavky
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        csrf_header = (request.headers.get("x-polygon-client") or "").strip().lower()
        if csrf_header != "true":
            return JSONResponse(
                status_code=403,
                content={"detail": "Chybí nebo je neplatná bezpečnostní hlavička X-Polygon-Client: true."},
            )

    return await call_next(request)


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
    active_tools: Optional[list[str]] = None
    activeTools: Optional[list[str]] = None
    mode_3d: Optional[bool] = None
    mode3d: Optional[bool] = None
    images: Optional[list[str]] = None

class ExternalUrlRequest(BaseModel):
    url: str = Field(min_length=1, max_length=32768)

class WorkspacePathRequest(BaseModel):
    path: str = Field(min_length=1, max_length=32768)

class WorkspaceDiffRequest(BaseModel):
    proposal_id: str = Field(min_length=1, max_length=128)

class SessionRenameRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    title: Optional[str] = "Přejmenovaný chat"

class SwitchLocalModelRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    model_path: str

class TestConnectionRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    provider: Optional[str] = None
    provider_type: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    model: Optional[str] = None

class SettingsUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    n_ctx: Optional[int] = None
    analytical_preset: Optional[str] = None
    online_mode: Optional[bool] = None
    system_prompt: Optional[str] = None
    local_model: Optional[str] = None
    active_provider: Optional[str] = None
    llm_provider: Optional[dict[str, Any]] = None
    blender: Optional[dict[str, Any]] = None

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
    active_brain = get_active_provider_info()

    return {
        "status": "online",
        "engine": "Polygon Beater Local Engine v2.3",
        "llm_loaded": _llm_instance is not None or active_brain.get("is_cloud", False),
        "llm": active_brain,
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

def _is_valid_external_url_syntax(url: str) -> bool:
    if not url or url != url.strip() or any(ord(char) < 32 or char.isspace() for char in url):
        return False
    try:
        parsed = urlparse(url)
        return (
            parsed.scheme.lower() in {"http", "https"}
            and bool(parsed.hostname)
            and bool(parsed.netloc)
            and parsed.username is None
            and parsed.password is None
            and (parsed.port is None or 1 <= parsed.port <= 65535)
        )
    except ValueError:
        return False


@app.post("/api/open-external-url")
async def open_external_url(req: ExternalUrlRequest, request: Request):
    require_loopback_client(request)
    if not _is_valid_external_url_syntax(req.url) or not is_safe_web_url(req.url):
        return JSONResponse(
            status_code=400,
            content={"status": "error", "message": "Odkaz je neplatný nebo není bezpečný."},
        )

    timeout = aiohttp.ClientTimeout(total=2.5, connect=2.5)
    connector = aiohttp.TCPConnector(resolver=PublicOnlyResolver(), limit=1)
    try:
        async with aiohttp.ClientSession(connector=connector) as session:
            response = await _safe_get(session, req.url, timeout=timeout)
            if response is None:
                return JSONResponse(
                    status_code=502,
                    content={"status": "error", "message": "Odkaz není dostupný nebo neexistuje."},
                )
            status_code = response.status
            response.release()
    except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as exc:
        logger.info("Ověření externího odkazu selhalo: %s", exc)
        return JSONResponse(
            status_code=502,
            content={"status": "error", "message": "Odkaz není dostupný nebo neexistuje."},
        )

    if not 200 <= status_code < 400:
        return JSONResponse(
            status_code=502,
            content={"status": "error", "message": "Odkaz není dostupný nebo neexistuje."},
        )

    try:
        opened = await asyncio.to_thread(webbrowser.open_new_tab, req.url)
    except (webbrowser.Error, OSError) as exc:
        logger.warning("Nepodařilo se otevřít externí odkaz v prohlížeči: %s", exc)
        opened = False
    if not opened:
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": "Odkaz se nepodařilo otevřít v prohlížeči."},
        )
    return {"status": "ok"}


def _default_project_path() -> str:
    return os.path.realpath(DEFAULT_WORKSPACE_DIR)


def _session_project_path(s: dict) -> str:
    """Legacy relace bez vazby patří do výchozího projektu (repozitář asistenta)."""
    return s.get("workspace_path") or _default_project_path()


def _active_project() -> dict[str, str]:
    path = os.path.realpath(get_workspace_dir())
    record = project_repository.get(path)
    return {"path": path, "name": (record or {}).get("name") or clean_project_name(None, path)}


def _normalize_session_summary(s: dict) -> dict:
    sid = s.get("session_id") or s.get("id") or ""
    project_path = _session_project_path(s)
    return {
        "id": sid,
        "session_id": sid,
        "title": s.get("title", "Nový chat"),
        "updated_at": s.get("updated_at", ""),
        "workspace_path": project_path,
        "project_name": s.get("project_name") or clean_project_name(None, project_path),
    }


def _create_session_in_active_project(title: str) -> dict:
    project = _active_project()
    return history_repository.create_session(title, workspace_path=project["path"], project_name=project["name"])


@app.get("/api/sessions")
def list_sessions(request: Request):
    require_loopback_client(request)
    sessions = history_repository.list_sessions()
    if not sessions:
        new_sess = _create_session_in_active_project("Nový chat")
        sessions = [new_sess]
    return {"sessions": [_normalize_session_summary(s) for s in sessions]}

@app.post("/api/sessions")
def create_session(request: Request, title: str = "New chat"):
    require_loopback_client(request)
    clean_title = (title or "New chat").strip()
    sess = _create_session_in_active_project(clean_title)
    return _normalize_session_summary(sess)


# ------------------------------------------------------------------------------
# Endpoints: Projekty (Projects)
# ------------------------------------------------------------------------------

class ProjectCreateRequest(BaseModel):
    path: str = Field(min_length=1, max_length=4096)
    name: Optional[str] = Field(default=None, max_length=200)
    create_if_missing: bool = True


class ProjectSwitchRequest(BaseModel):
    path: str = Field(min_length=1, max_length=4096)
    session_id: Optional[str] = Field(default=None, max_length=128)


def _activate_project(path: str, name: Optional[str] = None) -> dict[str, Any]:
    """Aktivuje workspace projektu a zaeviduje ho mezi nedávné projekty."""
    try:
        active_path = set_workspace_dir(path)
    except (PermissionError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    record = project_repository.touch(active_path, name)
    logger.info("[Projects] Aktivní projekt: %s (%s)", record["name"], active_path)
    return {"name": record["name"], "path": active_path}


@app.get("/api/projects")
def list_projects(request: Request):
    require_loopback_client(request)
    stats: dict[str, dict[str, Any]] = {}
    for s in history_repository.list_sessions():
        path = _session_project_path(s)
        entry = stats.setdefault(path, {"conversation_count": 0, "last_activity": "", "name": s.get("project_name")})
        entry["conversation_count"] += 1
        entry["last_activity"] = max(entry["last_activity"], s.get("updated_at") or "")

    projects: dict[str, dict[str, Any]] = {}
    for record in project_repository.list_projects():
        projects[record["path"]] = {
            "name": record.get("name") or clean_project_name(None, record["path"]),
            "path": record["path"],
            "last_activity": record.get("last_opened", ""),
        }
    for path, entry in stats.items():
        proj = projects.setdefault(path, {
            "name": entry["name"] or clean_project_name(None, path),
            "path": path,
            "last_activity": "",
        })
        proj["last_activity"] = max(proj["last_activity"], entry["last_activity"])

    active = _active_project()
    projects.setdefault(active["path"], {"name": active["name"], "path": active["path"], "last_activity": ""})
    result = []
    for path, proj in projects.items():
        proj["conversation_count"] = stats.get(path, {}).get("conversation_count", 0)
        proj["exists"] = os.path.isdir(path)
        proj["is_active"] = path == active["path"]
        result.append(proj)
    # Aktivní první, pak podle poslední aktivity sestupně
    active_items = [p for p in result if p["is_active"]]
    others = sorted((p for p in result if not p["is_active"]), key=lambda p: p["last_activity"], reverse=True)
    return {"status": "ok", "active": active, "projects": active_items + others}


@app.post("/api/projects")
def create_or_open_project(req: ProjectCreateRequest, request: Request):
    require_loopback_client(request)
    try:
        path = ensure_project_dir(req.path, create_if_missing=req.create_if_missing)
    except ProjectPathError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=400, detail=f"Adresář projektu nelze vytvořit: {exc}") from exc

    project = _activate_project(path, req.name)
    session = history_repository.create_session("Nový chat", workspace_path=project["path"], project_name=project["name"])
    return {
        "status": "success",
        "project": project,
        "session_id": session["session_id"],
        "session": _normalize_session_summary(session),
    }


@app.post("/api/projects/switch")
def switch_project(req: ProjectSwitchRequest, request: Request):
    require_loopback_client(request)
    try:
        path = resolve_project_path(req.path)
    except ProjectPathError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not os.path.isdir(path):
        raise HTTPException(status_code=404, detail="Adresář projektu již neexistuje.")

    project = _activate_project(path)
    sessions = [
        _normalize_session_summary(s)
        for s in history_repository.list_sessions()
        if os.path.realpath(_session_project_path(s)) == project["path"]
    ]
    session_id = None
    if req.session_id and is_safe_session_id(req.session_id):
        if any(s["session_id"] == req.session_id for s in sessions):
            session_id = req.session_id
    if session_id is None:
        if sessions:
            session_id = sessions[0]["session_id"]
        else:
            new_sess = history_repository.create_session("Nový chat", workspace_path=project["path"], project_name=project["name"])
            sessions = [_normalize_session_summary(new_sess)]
            session_id = new_sess["session_id"]
    return {"status": "success", "project": project, "session_id": session_id, "sessions": sessions}


# ------------------------------------------------------------------------------
# Endpoints: Výběr složky (nativní dialog pro Create / Open Project)
# ------------------------------------------------------------------------------

_FOLDER_DIALOG_TITLE = "Vyberte složku projektu"
_FOLDER_DIALOG_TIMEOUT = 60  # sekund – dialog nesmí navěky blokovat API endpoint
# Systémové stromy, do kterých nikdy nesmí mířit rychlá volba složky
_QUICK_DIR_BLOCKED_TREES = ("/etc", "/sys", "/proc", "/usr", "/bin", "/sbin", "/boot", "/dev", "/lib", "/run", "/var")
# Výchozí složky, ve kterých uživatel obvykle drží své projekty
_QUICK_DIR_PROJECTS_NAMES = ("Projects", "projects", "Projekty", "projekty")


def _zenity_folder_dialog(timeout: int = _FOLDER_DIALOG_TIMEOUT) -> tuple[str, Optional[str]]:
    """Otevře nativní dialog pro výběr složky přes zenity (Ubuntu/Linux).

    Vrací dvojici (status, cesta), kde status je "success" | "cancelled" | "unavailable".
    """
    try:
        result = subprocess.run(
            ["zenity", "--file-selection", "--directory", f"--title={_FOLDER_DIALOG_TITLE}"],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        # Uživatel dialog zapomněl otevřený – bereme to jako zrušení
        return "cancelled", None
    except (FileNotFoundError, OSError):
        # zenity není nainstalováno → zkusíme zálohu
        return "unavailable", None

    path = (result.stdout or "").strip()
    if result.returncode == 0 and path:
        return "success", path
    # zenity vrací nulový/kód 1 podle toho, zda uživatel zrušil dialog
    return "cancelled", None


def _tkinter_folder_dialog() -> tuple[str, Optional[str]]:
    """Záložní dialog pro výběr složky přes tkinter (bez závislosti na zenity)."""
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception:
        return "unavailable", None

    root = None
    try:
        root = tk.Tk()
        root.withdraw()
        try:
            root.attributes("-topmost", True)
        except Exception:
            pass
        selected = filedialog.askdirectory(title=_FOLDER_DIALOG_TITLE, mustexist=True)
    except Exception:
        # Headless prostředí bez DISPLAY atd.
        return "unavailable", None
    finally:
        if root is not None:
            try:
                root.destroy()
            except Exception:
                pass

    if selected:
        return "success", str(selected)
    return "cancelled", None


def _pick_folder_interactively() -> tuple[str, Optional[str]]:
    """Otevře zenity dialog, není-li k dispozici, použije tkinter. Vrací (status, cesta)."""
    status, path = _zenity_folder_dialog()
    if status == "unavailable":
        status, path = _tkinter_folder_dialog()
    if status == "success" and path:
        return "success", os.path.realpath(str(path).strip())
    return status, None


@app.post("/api/projects/browse-folder")
def browse_project_folder(request: Request):
    """Otevře nativní dialog pro výběr složky projektu na hostitelském systému."""
    require_loopback_client(request)
    status, path = _pick_folder_interactively()
    if status == "success" and path:
        return {"status": "success", "path": path}
    if status == "cancelled":
        return {"status": "cancelled", "path": None}
    raise HTTPException(
        status_code=503,
        detail="Dialog pro výběr složky není v tomto prostředí k dispozici (chybí zenity i tkinter).",
    )


def _is_safe_quick_dir(path: str) -> bool:
    """Rychlá složka musí existovat a nesmí mířit do systémového stromu."""
    if not path or not os.path.isdir(path):
        return False
    resolved = os.path.realpath(path)
    for tree in _QUICK_DIR_BLOCKED_TREES:
        canonical = os.path.realpath(tree)
        if resolved == canonical or resolved.startswith(canonical + os.sep):
            return False
    return True


@app.get("/api/fs/quick-dirs")
def quick_dirs(request: Request):
    """Vrátí bezpečné výchozí složky pro rychlý výběr v dialogu projektu."""
    require_loopback_client(request)
    home = os.path.realpath(os.path.expanduser("~"))
    candidates: list[tuple[str, str]] = [("home", home)]
    try:
        candidates.append(("workspace", os.path.realpath(get_workspace_dir())))
    except Exception:
        pass
    candidates.extend(("projects", os.path.join(home, name)) for name in _QUICK_DIR_PROJECTS_NAMES)

    seen: set[str] = set()
    dirs: list[dict[str, Any]] = []
    for key, path in candidates:
        if not _is_safe_quick_dir(path):
            continue
        if path in seen:
            continue
        seen.add(path)
        dirs.append({"key": key, "path": path, "label": "~" if key == "home" else path})
    return {"status": "ok", "dirs": dirs}


@app.get("/api/sessions/{session_id}")
def get_session(session_id: str, request: Request):
    require_loopback_client(request)
    if not is_safe_session_id(session_id):
        raise HTTPException(status_code=400, detail="Neplatné ID relace.")
    try:
        messages = history_repository.load_session(session_id)
        proj = history_repository.get_session_project(session_id)
        w_path = proj.get("workspace_path") or _default_project_path()
        w_name = proj.get("project_name") or clean_project_name(None, w_path)
        if os.path.isdir(w_path):
            try:
                set_workspace_dir(w_path)
            except Exception:
                pass
        return {
            "session_id": session_id,
            "messages": messages,
            "workspace_path": w_path,
            "project_name": w_name,
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Relace nenalezena: {e}")

@app.patch("/api/sessions/{session_id}")
def rename_session(session_id: str, req: SessionRenameRequest, request: Request):
    require_loopback_client(request)
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
def delete_session(session_id: str, request: Request):
    require_loopback_client(request)
    if not is_safe_session_id(session_id):
        raise HTTPException(status_code=400, detail="Neplatné ID relace.")
    # Zastavit probíhající worker/stream pro danou relaci
    stop_session(session_id)
    cleanup_session_stop_event(session_id)
    # Kompletní odstranění složky relace a její historie z disku
    success = history_repository.delete_session(session_id)
    return {"status": "success", "session_id": session_id, "deleted": success}

@app.delete("/api/sessions/{session_id}/messages")
def clear_session_messages(session_id: str, request: Request):
    require_loopback_client(request)
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
            new_sess = await anyio.to_thread.run_sync(_create_session_in_active_project, "Nový chat")
            session_id = new_sess.get("session_id") or new_sess.get("id")
    else:
        # Ověříme, že relace existuje na disku, jinak ji vytvoříme
        def _ensure_session():
            session_file = history_repository.sessions_dir / f"{session_id}.json"
            if not session_file.exists():
                active = _active_project()
                session_data = {
                    "session_id": session_id,
                    "title": "Nový chat",
                    "created_at": history_repository._now(),
                    "updated_at": history_repository._now(),
                    "messages": [],
                    "workspace_path": active["path"],
                    "project_name": active["name"],
                }
                history_repository._write_session(session_id, session_data)
        try:
            await anyio.to_thread.run_sync(_ensure_session)
        except Exception as exc:
            logger.warning("Inicializace souboru relace %s selhala: %s", session_id, exc)

    # Synchronizace aktivního workspace podle projektu relace
    try:
        sess_proj = await anyio.to_thread.run_sync(history_repository.get_session_project, session_id)
        sp_path = sess_proj.get("workspace_path")
        if sp_path and os.path.isdir(sp_path):
            set_workspace_dir(sp_path)
    except Exception:
        pass

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
    req_config["llama"]["rag_enabled"] = rag_active

    b_cfg = config.get("blender", {})
    b_online = is_blender_available(b_cfg.get("host", "127.0.0.1"), int(b_cfg.get("port", 9876)))
    req_config["llama"]["blender_online"] = b_online
    req_config["llama"]["mode_3d"] = bool(req.mode_3d if req.mode_3d is not None else req.mode3d)
    if req.active_tools is not None:
        req_config["llama"]["active_tools"] = req.active_tools
    elif req.activeTools is not None:
        req_config["llama"]["active_tools"] = req.activeTools

    if preset:
        req_config["llama"]["analytical_preset"] = preset

    # Izolovaný stop event pro konkrétní relaci
    session_stop = get_session_stop_event(session_id)

    # Fronta pro přenos událostí z worker vlákna do SSE streamu
    event_queue: queue.Queue[dict[str, Any]] = queue.Queue()
    collected_answer_tokens: list[str] = []
    collected_sentences: list[str] = []

    def worker():
        try:
            llm = get_llm()
            event_queue.put({"type": "session_id", "content": session_id})
            preset_now = req_config.get("llama", {}).get("analytical_preset", "")

            preset_key = str(preset_now).strip().casefold()
            if preset_key == "auto" or preset_key.endswith(("auto (doporučit)", "auto-select methodology")):
                auto_status = "● [AGENT] Determining optimal analytical methodology…" if req_lang == "en" else "● [AGENT] Určuji optimální analytickou metodiku…"
                event_queue.put({"type": "status", "content": auto_status})
                detected = classify_methodology(llm, user_prompt, language=req_lang)
                req_config["llama"]["analytical_preset"] = detected
                event_queue.put({"type": "methodology", "content": detected})

                # AGENTNÍ WORKSPACE REŽIM: dotazy cílící na soubory/kód/projekt
                # nikdy nespadnou do standardního chatu. Vynutíme function calling
                # (ReAct smyčku) a plnou sadu 8 workspace nástrojů (3 web + 5 system).
                if detect_workspace_request(user_prompt):
                    req_config["llama"]["function_calling"] = True
                    req_config["llama"]["online_mode"] = True
                    req_config["llama"]["rag_enabled"] = True
                    active_tools = req_config["llama"].get("active_tools")
                    if active_tools is not None:
                        req_config["llama"]["active_tools"] = sorted(
                            set(active_tools) | set(WORKSPACE_AGENT_TOOL_NAMES)
                        )
                    ws_status = (
                        "● [AGENT] Workspace request: ReAct loop enabled (8 tools)…"
                        if req_lang == "en"
                        else "● [AGENT] Workspace dotaz: aktivuji ReAct smyčku (8 nástrojů)…"
                    )
                    event_queue.put({"type": "status", "content": ws_status})

            def _on_token(token: str):
                event_queue.put({"type": "token", "content": token, "chunk": token})

            def _on_answer_token(token: str):
                collected_answer_tokens.append(token)

            def _on_status(status: str):
                event_queue.put({"type": "status", "content": status})

            def _on_tool(event_type: str, data: dict[str, Any]):
                payload = {"type": event_type}
                payload.update(data)
                proposal_event = None
                if event_type == "tool_end" and data.get("tool") == "write_file":
                    tool_result = data.get("result")
                    proposal = tool_result.get("proposal") if isinstance(tool_result, dict) else None
                    if isinstance(proposal, dict):
                        proposal_id = uuid.uuid4().hex
                        with _pending_workspace_diffs_lock:
                            if len(_pending_workspace_diffs) >= _MAX_PENDING_WORKSPACE_DIFFS:
                                oldest_proposal = next(iter(_pending_workspace_diffs))
                                _pending_workspace_diffs.pop(oldest_proposal)
                            _pending_workspace_diffs[proposal_id] = proposal
                        payload["result"] = {
                            key: value for key, value in tool_result.items() if key != "proposal"
                        }
                        proposal_event = {
                            "type": "code_diff_proposal",
                            "proposal_id": proposal_id,
                            "file_path": proposal["file_path"],
                            "original_content": proposal["original_content"],
                            "new_content": proposal["new_content"],
                            "original_exists": proposal["original_exists"],
                            "unified_diff": proposal["unified_diff"],
                            "is_truncated": bool(proposal.get("is_truncated", False)),
                        }
                if data.get("tool") == "write_file" and isinstance(data.get("arguments"), dict):
                    payload["arguments"] = {
                        key: value for key, value in data["arguments"].items() if key != "content"
                    }
                fs_tools = {
                    "list_directory": ("list", "rel_path", "directory"),
                    "read_file": ("read", "file_path", "file"),
                    "write_file": ("write", "file_path", "file"),
                    "search_in_files": ("search", "file_pattern", "files"),
                }
                fs_tool = fs_tools.get(str(data.get("tool", "")))
                if fs_tool:
                    operation, path_key, path_label = fs_tool
                    tool_arguments = data.get("arguments")
                    if not isinstance(tool_arguments, dict):
                        tool_arguments = {}
                    path_value = str(tool_arguments.get(path_key) or ("." if operation == "list" else ""))
                    operation_text = {
                        "list": {
                            "start": ("Prohlížím adresář", "Listing directory"),
                            "end": ("Výpis adresáře dokončen", "Directory listing complete"),
                        },
                        "read": {
                            "start": ("Čtu soubor", "Reading file"),
                            "end": ("Přečteno", "Read"),
                        },
                        "write": {
                            "start": ("Ukládám změny", "Saving changes"),
                            "end": ("Uloženo", "Saved"),
                        },
                        "search": {
                            "start": ("Hledám v souborech", "Searching files"),
                            "end": ("Vyhledávání dokončeno", "Search complete"),
                        },
                    }[operation]
                    phase = "end" if event_type == "tool_end" else "start"
                    verb = operation_text[phase][0] if req_lang != "en" else operation_text[phase][1]
                    payload["fs_operation"] = {
                        "operation": operation,
                        "message": f"[FS] {verb}: {path_value or path_label}",
                    }
                event_queue.put(payload)
                if proposal_event:
                    event_queue.put(proposal_event)
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
                callback_on_answer_token=_on_answer_token,
                status_callback=_on_status,
                stop_event=session_stop,
                document_service=document_service,
                memory_service=memory_service,
                active_session_id=session_id,
                tool_callback=_on_tool,
                images=req.images,
            ):
                collected_sentences.append(chunk)

            yielded_reply = "".join(collected_sentences).strip()
            streamed_answer = "".join(collected_answer_tokens).strip()
            if yielded_reply and not streamed_answer:
                for chunk in collected_sentences:
                    event_queue.put({"type": "token", "content": chunk, "chunk": chunk})

            full_reply = streamed_answer or yielded_reply
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
        media_type="text/event-stream; charset=utf-8",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

# ------------------------------------------------------------------------------
# Endpoints: Registered Tools Inspector & Integrations
# ------------------------------------------------------------------------------

@app.get("/api/tools")
def get_tools_list():
    """Vrací seznam všech registrovaných nástrojů rozdělených do kategorií pro UI inspektor."""
    try:
        from llama_module import TOOL_SCHEMAS, TOOL_CATEGORIES, BLENDER_TOOL_NAMES
        blender_cfg = config.get("blender", {})
        b_host = blender_cfg.get("host", "127.0.0.1")
        b_port = int(blender_cfg.get("port", 9876))
        b_online = is_blender_available(b_host, b_port)

        tools = []
        for s in TOOL_SCHEMAS:
            fn = s.get("function", {})
            name = fn.get("name", "")
            cat = TOOL_CATEGORIES.get(name, "system")
            tools.append({
                "name": name,
                "category": cat,
                "description": fn.get("description", ""),
                "parameters": fn.get("parameters", {}),
                "requires_blender": (name in BLENDER_TOOL_NAMES),
            })
        return {
            "status": "ok",
            "blender_online": b_online,
            "total": len(tools),
            "tools": tools,
        }
    except Exception as exc:
        logger.error("Chyba při načítání seznamu nástrojů: %s", exc)
        return {"status": "error", "message": str(exc), "tools": []}


# ------------------------------------------------------------------------------
# Endpoints: 3D Blender Bridge & Telemetrie
# ------------------------------------------------------------------------------

@app.get("/api/blender/status")
def blender_status(request: Request):
    require_loopback_client(request)
    b_cfg = config.get("blender", {})
    host = b_cfg.get("host", "127.0.0.1")
    port = int(b_cfg.get("port", 9876))
    online = is_blender_available(host, port)
    return {"connected": online, "host": host, "port": port}

@app.post("/api/blender/inspect")
def blender_inspect(request: Request):
    require_loopback_client(request)
    b_cfg = config.get("blender", {})
    host = b_cfg.get("host", "127.0.0.1")
    port = int(b_cfg.get("port", 9876))
    output_path = "/tmp/ai_assistant_viewport.png"
    res = request_scene_inspection(host=host, port=port, output_path=output_path)
    return res

@app.post("/api/blender/auto-rig")
def blender_auto_rig(request: Request, rig_type: str = "basic"):
    require_loopback_client(request)
    b_cfg = config.get("blender", {})
    host = b_cfg.get("host", "127.0.0.1")
    port = int(b_cfg.get("port", 9876))
    res = request_auto_rig(host=host, port=port, rig_type=rig_type)
    return res

@app.post("/api/blender/mesh-doctor")
def blender_mesh_doctor(request: Request, action: str = "audit", merge_distance: float = 0.0001):
    require_loopback_client(request)
    b_cfg = config.get("blender", {})
    host = b_cfg.get("host", "127.0.0.1")
    port = int(b_cfg.get("port", 9876))
    if action == "repair":
        return request_mesh_repair(host=host, port=port, merge_distance=merge_distance)
    return request_mesh_audit(host=host, port=port)

@app.post("/api/blender/product-studio")
def blender_product_studio(request: Request, style: str = "standard"):
    require_loopback_client(request)
    b_cfg = config.get("blender", {})
    host = b_cfg.get("host", "127.0.0.1")
    port = int(b_cfg.get("port", 9876))
    return request_product_studio(host=host, port=port, style=style)

@app.post("/api/blender/procedural-shader")
def blender_procedural_shader(request: Request, shader_type: str = "brushed_metal", material_name: Optional[str] = None):
    require_loopback_client(request)
    b_cfg = config.get("blender", {})
    host = b_cfg.get("host", "127.0.0.1")
    port = int(b_cfg.get("port", 9876))
    return request_procedural_shader(material_name=material_name, shader_type=shader_type, host=host, port=port)

@app.post("/api/blender/uv-audit")
def blender_uv_audit(request: Request, texture_res: int = 2048):
    require_loopback_client(request)
    b_cfg = config.get("blender", {})
    host = b_cfg.get("host", "127.0.0.1")
    port = int(b_cfg.get("port", 9876))
    return request_uv_audit(host=host, port=port, texture_res=texture_res)

class BlenderExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    code: str

@app.post("/api/blender/execute")
def blender_execute_code(req: BlenderExecuteRequest, request: Request):
    """Spustí libovolný Python (bpy) skript přímo v běžící instanci Blenderu."""
    require_loopback_client(request)
    b_cfg = config.get("blender", {})
    host = b_cfg.get("host", "127.0.0.1")
    port = int(b_cfg.get("port", 9876))
    return send_code_to_blender(code=req.code, host=host, port=port)

@app.get("/api/blender/viewport-image")
def get_viewport_image(request: Request):
    """Vrátí aktuální pořízený snímek viewportu z Blenderu."""
    require_loopback_client(request)
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
    Neblokuje FastAPI Event Loop, omezuje maximální velikost souboru a odstraňuje dočasné soubory po indexaci.
    """
    max_rag_bytes = 25 * 1024 * 1024  # 25 MB limit
    contents = await file.read(max_rag_bytes + 1)
    if not contents:
        raise HTTPException(status_code=400, detail="Nahraný dokument je prázdný.")
    if len(contents) > max_rag_bytes:
        raise HTTPException(status_code=413, detail="Dokument překračuje maximální povolenou velikost 25 MB.")

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
        await anyio.to_thread.run_sync(temp_path.write_bytes, contents)

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
def delete_rag_document(doc_name: str, request: Request):
    require_loopback_client(request)
    if not document_service:
        raise HTTPException(status_code=400, detail="RAG služba není dostupná.")
    success = document_service.delete_document(doc_name)
    return {"status": "success" if success else "not_found", "document": doc_name}

@app.post("/api/rag/memory/reindex")
def reindex_all_memory(request: Request):
    require_loopback_client(request)
    res = history_repository.reindex_all_to_memory()
    return {"status": "success", "result": res}

# ------------------------------------------------------------------------------
# Endpoints: Lokální modely & Externí poskytovatelé (AI Brain)
# ------------------------------------------------------------------------------

@app.get("/api/llm/local-models")
def get_local_models(request: Request):
    require_loopback_client(request)
    """Vrací seznam všech nalezených lokálních .gguf modelů s metadaty."""
    models_dir = config.get("llama", {}).get("models_dir", "models")
    active_model = config.get("llama", {}).get("model", "")
    found = scan_local_models(models_dir=models_dir, active_model_path=active_model)
    return {
        "status": "ok",
        "models_dir": models_dir,
        "active_model": active_model,
        "count": len(found),
        "models": found,
    }

@app.post("/api/llm/switch-model")
def switch_local_model(req: SwitchLocalModelRequest, request: Request):
    require_loopback_client(request)
    """Bezpečně uvolní stávající model z RAM/VRAM a zavede nově vybraný .gguf soubor."""
    path_str = req.model_path.strip()
    if not path_str:
        raise HTTPException(status_code=400, detail="Cesta k modelu nesmí být prázdná.")

    p = Path(path_str)
    if not p.is_file():
        alt = Path("models") / path_str
        if alt.is_file():
            path_str = str(alt)
        else:
            raise HTTPException(status_code=404, detail=f"Soubor modelu '{path_str}' nebyl nalezen.")

    backup_config = json.loads(json.dumps(config))
    try:
        reload_local_llm(new_model_path=path_str)
        config.setdefault("llm_provider", {})["active_provider"] = "local"
        save_config_file()
        return {
            "status": "ok",
            "message": f"Model '{path_str}' byl úspěšně zaveden do paměti.",
            "active_model": path_str,
            "active_brain": get_active_provider_info(),
        }
    except Exception as exc:
        config.clear()
        config.update(backup_config)
        logger.exception("Chyba při přepínání modelu (proveden rollback): %s", exc)
        raise HTTPException(status_code=500, detail=f"Chyba při zavádění modelu: {exc}")

@app.post("/api/llm/test-connection")
def test_connection_endpoint(req: TestConnectionRequest, request: Request):
    """Otestuje spojení s vybraným API poskytovatelem (Ping API)."""
    require_loopback_client(request)

    if req.provider and req.provider_type and req.provider.lower().strip() != req.provider_type.lower().strip():
        raise HTTPException(status_code=400, detail="Typ poskytovatele není jednoznačný.")

    provider = (req.provider_type or req.provider or "groq").lower().strip()
    if provider not in {"groq", "gemini", "custom"}:
        raise HTTPException(status_code=400, detail="Neznámý poskytovatel.")

    provider_cfg = config.get("llm_provider", {}).get(provider, {})
    requested_api_key = (req.api_key or "").strip()
    uses_saved_api_key = not requested_api_key or "••••" in requested_api_key or "*" in requested_api_key

    base_url = (
        (provider_cfg.get("base_url", "") if uses_saved_api_key else (req.base_url or "").strip())
        or provider_cfg.get("base_url", "")
    )
    if not base_url:
        if provider == "groq":
            base_url = "https://api.groq.com/openai/v1"
        elif provider == "gemini":
            base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
        else:
            base_url = "https://api.openai.com/v1"

    api_key = provider_cfg.get("api_key", "") if uses_saved_api_key else requested_api_key

    model = (req.model or "").strip() or provider_cfg.get("model", "")
    if not model:
        if provider == "groq":
            model = "openai/gpt-oss-120b"
        elif provider == "gemini":
            model = "gemini-flash-latest"
        else:
            model = "gpt-4o"

    if provider == "gemini":
        base_url = base_url.replace("v1main", "v1beta")

    res = test_provider_connection(
        provider_type=provider,
        base_url=base_url,
        api_key=api_key,
        model=model,
    )
    return res

# ------------------------------------------------------------------------------
# Endpoints: Konfigurace & Nastavení
# ------------------------------------------------------------------------------

@app.get("/api/workspace")
def get_workspace(request: Request):
    require_loopback_client(request)
    path = get_workspace_dir()
    return {
        "status": "ok",
        "path": path,
        "is_default": is_default_workspace(),
        "permissions": {
            "readable": os.access(path, os.R_OK | os.X_OK),
            "writable": os.access(path, os.W_OK | os.X_OK),
        },
    }


@app.post("/api/workspace")
def update_workspace(req: WorkspacePathRequest, request: Request):
    require_loopback_client(request)
    try:
        path = set_workspace_dir(req.path)
    except (PermissionError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    logger.info("[FS] Pracovní adresář změněn na: %s", path)
    return {
        "status": "ok",
        "path": path,
        "is_default": is_default_workspace(),
        "permissions": {"readable": True, "writable": True},
    }


@app.post("/api/workspace/reset")
def reset_workspace(request: Request):
    require_loopback_client(request)
    path = reset_workspace_dir()
    logger.info("[FS] Pracovní adresář změněn na: %s", path)
    return {
        "status": "ok",
        "path": path,
        "is_default": True,
        "permissions": {
            "readable": os.access(path, os.R_OK | os.X_OK),
            "writable": os.access(path, os.W_OK | os.X_OK),
        },
    }


@app.post("/api/workspace/apply-diff")
def apply_workspace_diff(req: WorkspaceDiffRequest, request: Request):
    require_loopback_client(request)
    with _pending_workspace_diffs_lock:
        proposal = _pending_workspace_diffs.get(req.proposal_id)
        if proposal is None:
            raise HTTPException(status_code=404, detail="Návrh změny neexistuje nebo již byl použit.")
        try:
            result = apply_workspace_write_proposal(proposal)
        except (PermissionError, ValueError, OSError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        del _pending_workspace_diffs[req.proposal_id]
    logger.info("[FS] Schválená změna uložena: %s", proposal["file_path"])
    return {"status": "ok", "file_path": proposal["file_path"], "result": result["result"]}


@app.post("/api/workspace/discard-diff")
def discard_workspace_diff(req: WorkspaceDiffRequest, request: Request):
    require_loopback_client(request)
    with _pending_workspace_diffs_lock:
        if _pending_workspace_diffs.pop(req.proposal_id, None) is None:
            raise HTTPException(status_code=404, detail="Návrh změny neexistuje nebo již byl použit.")
    logger.info("[FS] Návrh změny zahozen: %s", req.proposal_id)
    return {"status": "ok"}


@app.get("/api/config")
def get_config():
    safe_cfg = json.loads(json.dumps(config))
    llm_prov = safe_cfg.setdefault("llm_provider", {
        "active_provider": "local",
        "groq": {"api_key": "", "model": "openai/gpt-oss-120b", "base_url": "https://api.groq.com/openai/v1"},
        "gemini": {"api_key": "", "model": "gemini-flash-latest", "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/"},
        "custom": {"provider_name": "OpenAI", "base_url": "https://api.openai.com/v1", "api_key": "", "model": "gpt-4o", "temperature": 0.7}
    })
    for p_name in ("groq", "gemini", "custom"):
        sub = llm_prov.get(p_name, {})
        raw_key = config.get("llm_provider", {}).get(p_name, {}).get("api_key", "")
        sub["has_api_key"] = bool(raw_key)
        sub["api_key"] = mask_api_key(raw_key)

    # Bezpečnostní maskování citlivého Blender auth_tokenu
    blender_sec = safe_cfg.get("blender")
    if isinstance(blender_sec, dict):
        raw_token = config.get("blender", {}).get("auth_token", "")
        blender_sec["has_auth_token"] = bool(raw_token)
        blender_sec["auth_token"] = mask_api_key(raw_token)

    return {
        "config": safe_cfg,
        "analytical_presets": list(ANALYTICAL_PRESETS.keys()),
        "default_preset": DEFAULT_ANALYTICAL_PRESET,
        "default_system_prompt": DEFAULT_SYSTEM_PROMPT,
        "active_brain": get_active_provider_info(),
    }

@app.post("/api/config")
def update_config(req: SettingsUpdateRequest, request: Request):
    require_loopback_client(request)

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

    llm_prov = config.setdefault("llm_provider", {})
    if req.active_provider:
        llm_prov["active_provider"] = req.active_provider
    elif req.llm_provider and "active_provider" in req.llm_provider:
        llm_prov["active_provider"] = req.llm_provider["active_provider"]

    if req.llm_provider:
        for p_name in ("groq", "gemini", "custom"):
            if p_name in req.llm_provider and isinstance(req.llm_provider[p_name], dict):
                incoming = req.llm_provider[p_name]
                current = llm_prov.setdefault(p_name, {})
                for k, v in incoming.items():
                    if k == "api_key":
                        # Aktualizujeme klíč pouze pokud není prázdný a není zamaskovaný
                        if v and "••••" not in v and "..." not in v and "*" not in v:
                            current["api_key"] = v.strip()
                    elif k != "has_api_key":
                        current[k] = v

    if req.blender and isinstance(req.blender, dict):
        blender_cfg = config.setdefault("blender", {})
        for k, v in req.blender.items():
            if k == "auth_token":
                if v and "••••" not in v and "..." not in v and "*" not in v:
                    blender_cfg["auth_token"] = v.strip()
            elif k != "has_auth_token":
                blender_cfg[k] = v

    backup_config = json.loads(json.dumps(config))
    try:
        # Přepnutí lokálního modelu, pokud bylo zvoleno a liší se od aktuálního
        if req.local_model and req.local_model.strip() and req.local_model.strip() != llama_cfg.get("model"):
            new_m = req.local_model.strip()
            reload_local_llm(new_model_path=new_m)
        else:
            saved = save_config_file()
            if not saved:
                raise RuntimeError("Nepodařilo se uložit konfiguraci do souboru config.json.")
    except Exception as e:
        config.clear()
        config.update(backup_config)
        logger.warning("Rollback konfigurace kvůli chybě: %s", e)
        if isinstance(e, HTTPException):
            raise e
        status = 400 if isinstance(e, (ValueError, FileNotFoundError)) else 500
        raise HTTPException(status_code=status, detail=f"Chyba při aktualizaci konfigurace: {e}")

    return {
        "status": "success",
        "config": get_config()["config"],
        "active_brain": get_active_provider_info(),
    }



@app.post("/api/app/shutdown")
def shutdown_app(request: Request):
    """Ukončí běžící desktopový server a aplikaci na vyžádání z UI."""
    require_loopback_client(request)
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
