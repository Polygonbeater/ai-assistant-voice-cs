from __future__ import annotations

import json
import logging
import os
import re
import shutil
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import TypedDict

logger = logging.getLogger(__name__)


class ChatMessage(TypedDict):
    role: str
    content: str
    timestamp: str


class SessionSummary(TypedDict):
    session_id: str
    title: str
    updated_at: str


class HistoryRepository:
    """Thread-safe local repository for independent chat sessions."""

    def __init__(self, path: str | Path = "chat_history.txt", memory_service=None):
        legacy_path = Path(path)
        self.sessions_dir = legacy_path.parent / "sessions"
        self.legacy_path = legacy_path
        self.memory_service = memory_service
        self._lock = threading.RLock()
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.sessions_dir, 0o700)
        except OSError:
            pass

    def set_memory_service(self, memory_service) -> None:
        """Nastaví instanci sémantické paměti pro automatickou indexaci."""
        with self._lock:
            self.memory_service = memory_service

    def _safe_index_session(self, session_id: str, title: str, messages: list[dict], updated_at: str) -> None:
        """Asynchronně a bezpečně zindexuje relaci do sémantické paměti s ověřením existence a konzistence."""
        try:
            path = self.sessions_dir / f"{session_id}.json"
            with self._lock:
                # 1. Kontrola, zda soubor relace stále existuje
                if not path.is_file():
                    logger.info("Relace %s byla mezitím smazána, přeskakuji indexaci.", session_id)
                    return

                try:
                    current = self._read_session(session_id)
                    if current.get("updated_at") != updated_at or not current.get("messages"):
                        logger.info("Relace %s byla mezitím modifikována nebo vyprázdněna, přeskakuji indexaci.", session_id)
                        return
                except Exception:
                    return

                # 2. Těsně před finálním zápisem do vektorového indexu/paměti ověříme existenci souboru
                if not path.is_file():
                    logger.info("Soubor relace %s na disku již neexistuje (uživatelem smazán), indexaci tiše ukončuji.", session_id)
                    return

                if self.memory_service and messages:
                    self.memory_service.index_session(session_id, title, messages, updated_at=updated_at)
        except Exception as exc:
            logger.exception("Chyba při automatické indexaci relace %s do sémantické paměti: %s", session_id, exc)

    def get_session_dir(self, session_id: str) -> Path:
        """Vrátí dedikovanou složku relace na disku a zajistí její existenci."""
        if not session_id or Path(session_id).name != session_id or not re.match(r"^[a-zA-Z0-9_-]+$", session_id):
            raise ValueError("Neplatné ID relace.")
        session_folder = self.sessions_dir / session_id
        session_folder.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(session_folder, 0o700)
        except OSError:
            pass
        return session_folder

    def create_session(
        self,
        title: str = "Nový chat",
        workspace_path: str | None = None,
        project_name: str | None = None,
    ) -> SessionSummary:
        with self._lock:
            session_id = f"{datetime.now(timezone.utc):%Y%m%dT%H%M%S}_{uuid.uuid4().hex[:8]}"
            session = {
                "session_id": session_id,
                "title": self._clean_title(title),
                "created_at": self._now(),
                "updated_at": self._now(),
                "messages": [],
            }
            if workspace_path:
                session["workspace_path"] = workspace_path
                session["project_name"] = project_name or Path(workspace_path).name or workspace_path
            self._write_session(session_id, session)
            self.get_session_dir(session_id)
            return self._summary(session)

    def get_session_project(self, session_id: str) -> dict[str, str | None]:
        """Vrátí vazbu relace na projekt (workspace_path, project_name)."""
        with self._lock:
            session = self._read_session(session_id)
            return {
                "workspace_path": session.get("workspace_path"),
                "project_name": session.get("project_name"),
            }

    def set_session_project(self, session_id: str, workspace_path: str, project_name: str | None = None) -> None:
        """Přiřadí relaci k projektovému adresáři."""
        with self._lock:
            session = self._read_session(session_id)
            session["workspace_path"] = workspace_path
            session["project_name"] = project_name or Path(workspace_path).name or workspace_path
            self._write_session(session_id, session)

    def list_sessions(self) -> list[SessionSummary]:
        with self._lock:
            summaries = []
            for path in self.sessions_dir.glob("*.json"):
                try:
                    session = self._read_session(path.stem)
                    summaries.append(self._summary(session))
                except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
                    continue
            return sorted(summaries, key=lambda item: item["updated_at"], reverse=True)

    def load_session(self, session_id: str) -> list[ChatMessage]:
        with self._lock:
            session = self._read_session(session_id)
            return list(session["messages"])

    def append(self, session_id: str, role: str, content: str) -> None:
        if role not in {"user", "assistant"}:
            raise ValueError("Role musí být 'user' nebo 'assistant'.")
        if not content.strip():
            return
        with self._lock:
            session = self._read_session(session_id)
            message: ChatMessage = {
                "role": role,
                "content": content,
                "timestamp": self._now(),
            }
            session["messages"].append(message)
            if role == "user" and session["title"] in ("Nový chat", "New chat"):
                session["title"] = self._clean_title(content)
            session["updated_at"] = message["timestamp"]
            self._write_session(session_id, session)

            # Automatická sémantická indexace po dokončení odpovědi asistenta (neblokující na pozadí)
            if self.memory_service and role == "assistant":
                threading.Thread(
                    target=self._safe_index_session,
                    args=(session_id, session["title"], list(session["messages"]), session["updated_at"]),
                    daemon=True,
                ).start()

    def clear(self, session_id: str) -> None:
        with self._lock:
            session = self._read_session(session_id)
            session["messages"] = []
            session["title"] = "Nový chat"
            session["updated_at"] = self._now()
            self._write_session(session_id, session)
            if self.memory_service:
                try:
                    self.memory_service.delete_session(session_id)
                except Exception:
                    pass

    def delete_session(self, session_id: str) -> bool:
        """Kompletní smazání relace z disku (Hard Delete) včetně její celé složky a historie."""
        if not session_id or Path(session_id).name != session_id or not re.match(r"^[a-zA-Z0-9_-]+$", session_id):
            return False
        with self._lock:
            deleted = False
            path = self.sessions_dir / f"{session_id}.json"
            session_folder = self.sessions_dir / session_id

            # 1. Kompletní smazání celé složky relace z disku
            if session_folder.exists():
                try:
                    if session_folder.is_dir():
                        shutil.rmtree(session_folder)
                    else:
                        session_folder.unlink()
                    deleted = True
                    logger.info("Složka relace %s byla kompletně smazána z disku.", session_id)
                except OSError as err:
                    logger.warning("Chyba při mazání složky relace %s: %s", session_id, err)

            # 2. Smazání souboru relace (.json)
            if path.is_file():
                try:
                    path.unlink()
                    deleted = True
                except OSError:
                    pass

            # 3. Smazání případného dočasného souboru (.tmp)
            tmp = path.with_suffix(".tmp")
            if tmp.is_file():
                try:
                    tmp.unlink()
                except OSError:
                    pass

            # 4. Odstranění ze sémantické paměti
            if self.memory_service:
                try:
                    self.memory_service.delete_session(session_id)
                except Exception:
                    pass

            return deleted

    def reindex_all_to_memory(self) -> dict[str, int]:
        """Projde všechny existující relace a zindexuje je do sémantické paměti."""
        if not self.memory_service:
            return {}
        return self.memory_service.reindex_all_sessions(self.sessions_dir)

    def delete_empty_sessions(self) -> int:
        removed = 0
        with self._lock:
            for path in self.sessions_dir.glob("*.json"):
                try:
                    session = self._read_session(path.stem)
                    if not session.get("messages"):
                        if self.delete_session(path.stem):
                            removed += 1
                except Exception:
                    continue
        return removed

    def _read_session(self, session_id: str) -> dict:
        if not session_id or Path(session_id).name != session_id or not re.match(r"^[a-zA-Z0-9_-]+$", session_id):
            raise ValueError("Neplatné ID relace.")
        path = self.sessions_dir / f"{session_id}.json"
        if not path.exists():
            raise FileNotFoundError(f"Relace neexistuje: {session_id}")
        with path.open("r", encoding="utf-8") as session_file:
            session = json.load(session_file)
        if not isinstance(session.get("messages"), list):
            raise ValueError("Relace obsahuje neplatné zprávy.")
        return session

    def _write_session(self, session_id: str, session: dict) -> None:
        if not session_id or Path(session_id).name != session_id or not re.match(r"^[a-zA-Z0-9_-]+$", session_id):
            raise ValueError("Neplatné ID relace.")
        target = self.sessions_dir / f"{session_id}.json"
        temporary = target.with_suffix(".tmp")
        with temporary.open("w", encoding="utf-8") as session_file:
            json.dump(session, session_file, ensure_ascii=False, indent=2)
        try:
            os.chmod(temporary, 0o600)
        except OSError:
            pass
        temporary.replace(target)
        try:
            os.chmod(target, 0o600)
        except OSError:
            pass

    @staticmethod
    def _summary(session: dict) -> SessionSummary:
        return {
            "session_id": session["session_id"],
            "title": session["title"],
            "updated_at": session["updated_at"],
            "workspace_path": session.get("workspace_path"),
            "project_name": session.get("project_name"),
        }

    @staticmethod
    def _clean_title(content: str) -> str:
        title = " ".join(content.split())
        return title[:48] + ("…" if len(title) > 48 else "")

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
