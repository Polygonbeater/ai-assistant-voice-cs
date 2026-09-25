from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import TypedDict


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

    def __init__(self, path: str | Path = "chat_history.txt"):
        legacy_path = Path(path)
        self.sessions_dir = legacy_path.parent / "sessions"
        self.legacy_path = legacy_path
        self._lock = threading.RLock()
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    def create_session(self, title: str = "Nový chat") -> SessionSummary:
        with self._lock:
            session_id = f"{datetime.now(timezone.utc):%Y%m%dT%H%M%S}_{uuid.uuid4().hex[:8]}"
            session = {
                "session_id": session_id,
                "title": self._clean_title(title),
                "created_at": self._now(),
                "updated_at": self._now(),
                "messages": [],
            }
            self._write_session(session_id, session)
            return self._summary(session)

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
            if role == "user" and session["title"] == "Nový chat":
                session["title"] = self._clean_title(content)
            session["updated_at"] = message["timestamp"]
            self._write_session(session_id, session)

    def clear(self, session_id: str) -> None:
        with self._lock:
            session = self._read_session(session_id)
            session["messages"] = []
            session["title"] = "Nový chat"
            session["updated_at"] = self._now()
            self._write_session(session_id, session)

    def _read_session(self, session_id: str) -> dict:
        if not session_id or Path(session_id).name != session_id:
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
        target = self.sessions_dir / f"{session_id}.json"
        temporary = target.with_suffix(".tmp")
        with temporary.open("w", encoding="utf-8") as session_file:
            json.dump(session, session_file, ensure_ascii=False, indent=2)
        temporary.replace(target)

    @staticmethod
    def _summary(session: dict) -> SessionSummary:
        return {
            "session_id": session["session_id"],
            "title": session["title"],
            "updated_at": session["updated_at"],
        }

    @staticmethod
    def _clean_title(content: str) -> str:
        title = " ".join(content.split())
        return title[:48] + ("…" if len(title) > 48 else "")

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
