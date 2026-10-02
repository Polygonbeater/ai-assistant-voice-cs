#!/usr/bin/env python3
"""
AI Assistant Voice CS — Antigravity Web Interface Launcher
Spouští lokální FastAPI backend a otevírá webové rozhraní Antigravity v prohlížeči.
"""

from __future__ import annotations

import argparse
import sys
import threading
import time
import webbrowser
from pathlib import Path

BANNER = r"""
    ___    _   ___________ ________  ___ _    ________________  __
   /   |  / | / /_  __/  _/ ____/ __ \/   | |  / /  _/_  __/\ \/ /
  / /| | /  |/ / / /  / / // /_  / /_/ / /| | | / // /  / /    \  / 
 / ___ |/ /|  / / / _/ / // __/ / _, _/ ___ | |/ // /  / /     / /  
/_/  |_/_/ |_/ /_/ /___//_/    /_/ |_/_/  |_|___/___/ /_/     /_/   
                  Local Voice & 3D Assistant v2.3
"""

def open_browser_delayed(url: str, delay: float = 1.0) -> None:
    """Otevře URL v prohlížeči po zadané prodlevě, aby server stihl nastartovat."""
    def _target():
        time.sleep(delay)
        print(f"\n[Antigravity] Otevírám rozhraní v prohlížeči: {url}")
        try:
            webbrowser.open_new_tab(url)
        except Exception as exc:
            print(f"[Antigravity] Automatické otevření prohlížeče selhalo ({exc}). Otevřete ručně: {url}")

    thread = threading.Thread(target=_target, daemon=True)
    thread.start()

def main():
    parser = argparse.ArgumentParser(description="Antigravity Voice CS — Web Interface Launcher")
    parser.add_argument("--host", default="127.0.0.1", help="Host rozhraní (výchozí: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port rozhraní (výchozí: 8000)")
    parser.add_argument("--no-browser", action="store_true", help="Neotevírat automaticky webový prohlížeč")
    parser.add_argument("--reload", action="store_true", help="Povolit autoreload pro vývoj")
    args = parser.parse_args()

    print(BANNER)
    print(f"[*] Inicializuji lokální Antigravity engine na http://{args.host}:{args.port}")
    print("[*] 100% Soukromé & Lokální prostředí (LLM, Blender Bridge, RAG Paměť, STT/TTS)")
    print("[*] Stiskněte Ctrl+C pro ukončení serveru.\n")

    if not args.no_browser:
        open_browser_delayed(f"http://{args.host}:{args.port}")

    import uvicorn
    uvicorn.run(
        "web_server:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )

if __name__ == "__main__":
    main()
