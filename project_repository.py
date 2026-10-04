"""Správa projektů (Projects): validace cest, vytváření složek a evidence nedávných projektů."""
from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Systémové kořeny, do kterých (ani pod které) nesmí projekt nikdy ukazovat
_BLOCKED_PROJECT_TREES = (
    "/etc", "/sys", "/proc", "/root", "/bin", "/sbin", "/usr", "/boot",
    "/dev", "/lib", "/lib32", "/lib64", "/var", "/run", "/snap", "/srv",
)
# Příliš široké adresáře, které nesmí být projektem samy o sobě (podadresáře jsou OK)
_BLOCKED_EXACT_PATHS = ("/", "/home", "/tmp", "/mnt", "/media", "/opt")
_BLOCKED_PATH_PARTS = {".git", ".ssh", ".gnupg", ".env", "__pycache__", ".venv", "venv"}
_MAX_PROJECT_NAME = 80
_MAX_RECENT_PROJECTS = 50


class ProjectPathError(ValueError):
    """Neplatná nebo zakázaná cesta projektu."""


def _is_within(path: str, root: str) -> bool:
    try:
        return os.path.commonpath((root, path)) == root
    except ValueError:
        return False


def resolve_project_path(raw_path: str) -> str:
    """
    Převede uživatelskou cestu na kanonickou absolutní cestu a ověří bezpečnost.
    Relativní cesty a `~` se vztahují k domovské složce. Adresář nemusí existovat.
    """
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise ProjectPathError("Cesta k projektu nesmí být prázdná.")
    if "\x00" in raw_path:
        raise ProjectPathError("Cesta obsahuje neplatné znaky.")

    home = os.path.realpath(os.path.expanduser("~"))
    expanded = os.path.expanduser(raw_path.strip())
    if not os.path.isabs(expanded):
        expanded = os.path.join(home, expanded)
    resolved = os.path.realpath(expanded)

    if resolved in {os.path.realpath(p) for p in _BLOCKED_EXACT_PATHS} or resolved == home:
        raise ProjectPathError(f"Adresář {resolved} je příliš obecný – zvolte konkrétní podsložku projektu.")
    for tree in _BLOCKED_PROJECT_TREES:
        canonical_tree = os.path.realpath(tree)
        if _is_within(resolved, canonical_tree) or _is_within(resolved, tree):
            raise ProjectPathError(f"Systémový adresář nelze použít jako projekt: {tree}")
    if any(part in _BLOCKED_PATH_PARTS for part in Path(resolved).parts):
        raise ProjectPathError("Cesta projektu nesmí vést do skrytých/citlivých složek (.git, .ssh, venv…).")
    return resolved


def ensure_project_dir(raw_path: str, create_if_missing: bool = True) -> str:
    """Ověří cestu a podle potřeby bezpečně vytvoří (prázdný) adresář projektu."""
    resolved = resolve_project_path(raw_path)
    if os.path.exists(resolved):
        if not os.path.isdir(resolved):
            raise ProjectPathError("Zadaná cesta existuje, ale není to adresář.")
        return resolved
    if not create_if_missing:
        raise ProjectPathError("Adresář projektu neexistuje (povolte jeho vytvoření).")
    os.makedirs(resolved, mode=0o755, exist_ok=True)
    # Ochrana proti symlink race: po vytvoření ověříme kanonickou cestu znovu
    return resolve_project_path(os.path.realpath(resolved))


def clean_project_name(name: str | None, path: str) -> str:
    candidate = " ".join((name or "").split()) or Path(path).name or path
    return candidate[:_MAX_PROJECT_NAME]


class ProjectRepository:
    """Thread-safe evidence známých projektů v JSON souboru."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._lock = threading.RLock()

    def _load(self) -> list[dict[str, Any]]:
        try:
            with self.path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            projects = data.get("projects", []) if isinstance(data, dict) else []
            return [p for p in projects if isinstance(p, dict) and isinstance(p.get("path"), str)]
        except (OSError, json.JSONDecodeError):
            return []

    def _save(self, projects: list[dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump({"projects": projects}, fh, ensure_ascii=False, indent=2)
        try:
            os.chmod(tmp, 0o600)
        except OSError:
            pass
        tmp.replace(self.path)

    def list_projects(self) -> list[dict[str, Any]]:
        with self._lock:
            return sorted(self._load(), key=lambda p: p.get("last_opened", ""), reverse=True)

    def get(self, path: str) -> dict[str, Any] | None:
        with self._lock:
            return next((p for p in self._load() if p["path"] == path), None)

    def touch(self, path: str, name: str | None = None) -> dict[str, Any]:
        """Zaeviduje projekt (nebo aktualizuje datum otevření) a vrátí jeho záznam."""
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            projects = self._load()
            record = next((p for p in projects if p["path"] == path), None)
            if record is None:
                record = {"path": path, "name": clean_project_name(name, path), "created_at": now}
                projects.append(record)
            elif name:
                record["name"] = clean_project_name(name, path)
            record["last_opened"] = now
            projects.sort(key=lambda p: p.get("last_opened", ""), reverse=True)
            self._save(projects[:_MAX_RECENT_PROJECTS])
            return dict(record)
