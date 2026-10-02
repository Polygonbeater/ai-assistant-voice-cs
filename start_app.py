#!/usr/bin/env python3
"""
start_app.py — Hlavní uživatelský spouštěč aplikace Polygon Beater (Click-and-Run).
Polygon Beater Voice CS — 100% Soukromý lokální AI asistent.

Zajišťuje:
1. Automatickou detekci a transparentní přepnutí do virtuálního prostředí (venv),
   pokud je skript spuštěn přes systémový Python nebo poklepáním myší.
2. Tichý start FastAPI/Uvicorn serveru na pozadí bez zbytečného šumu v terminálu.
3. Spuštění nativního samostatného desktopového okna v aplikačním režimu
   s plně perzistentním uživatelským profilem (trvalý localStorage, nastavení, presety).
4. Sjednocený životní cyklus — při zavření okna (křížkem) dojde k čistému a bezpečnému
   ukončení celého stacku bez zanechání visících procesů.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Cesta k repozitáři
REPO_DIR = Path(__file__).resolve().parent

# 1. Automatické přepnutí do lokálního venv, pokud je spuštěno systémovým Pythonem
def _ensure_venv():
    venv_python = REPO_DIR / "venv" / "bin" / "python"
    if not venv_python.is_file():
        alt_venv = REPO_DIR / ".venv" / "bin" / "python"
        if alt_venv.is_file():
            venv_python = alt_venv

    if venv_python.is_file():
        current_py = Path(sys.executable).resolve()
        target_py = venv_python.resolve()
        if current_py != target_py:
            # Re-exec venv Pythonem se zachováním všech argumentů
            os.execv(str(target_py), [str(target_py), str(Path(__file__).resolve())] + sys.argv[1:])

_ensure_venv()

# Přidání kořenového adresáře do sys.path
if str(REPO_DIR) not in sys.path:
    sys.path.insert(0, str(REPO_DIR))

from desktop_app import DesktopAppRunner, BANNER, find_system_app_browser


def main():
    parser = argparse.ArgumentParser(
        description="Polygon Beater — Click-and-Run Desktop Launcher",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host rozhraní")
    parser.add_argument("--port", type=int, default=8000, help="Port rozhraní")
    parser.add_argument("--verbose", "-v", action="store_true", help="Zobrazit podrobné výpisy serveru")
    parser.add_argument("--browser-tab", action="store_true", help="Otevřít běžnou záložku namísto samostatného okna")
    parser.add_argument("--server-only", "--no-window", dest="server_only", action="store_true", help="Spustit pouze backend bez okna")
    parser.add_argument("--reload", action="store_true", help="Povolit autoreload pro vývoj")

    args = parser.parse_args()

    if args.server_only:
        import uvicorn
        if args.verbose:
            print(BANNER)
            print(f"[*] Spouštím Polygon Beater v režimu pouze server na http://{args.host}:{args.port}")
        uvicorn.run(
            "web_server:app",
            host=args.host,
            port=args.port,
            reload=args.reload,
            log_level="info" if args.verbose else "warning",
        )
        return

    # Pro koncového uživatele je výchozí režim tichý a elegantní (quiet), pokud nezadá --verbose
    is_quiet = not args.verbose

    if not is_quiet:
        print(BANNER)

    runner = DesktopAppRunner(
        host=args.host,
        port=args.port,
        reload=args.reload,
        open_as_tab=args.browser_tab,
        quiet=is_quiet,
    )
    runner.run()


if __name__ == "__main__":
    main()
