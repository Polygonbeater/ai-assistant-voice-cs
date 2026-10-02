#!/usr/bin/env python3
"""
AI Assistant Voice CS — Polygon Beater Web Interface Launcher
Spouští lokální FastAPI backend a otevírá webové rozhraní Polygon Beater v prohlížeči.
"""

from __future__ import annotations

import argparse
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

BANNER = r"""
  ____   ____  _  __   ______  ___  _   _   ____  _____    _  _____ _____ ____  
 |  _ \ / __ \| | \ \ / / ___|/ _ \| \ | | | __ )| ____|  / \|_   _| ____|  _ \ 
 | |_) | |  | | |  \ V / |  _| | | |  \| | |  _ \|  _|   / _ \ | | |  _| | |_) |
 |  __/| |__| | |___| || |_| | |_| | |\  | | |_) | |___ / ___ \| | | |___|  _ < 
 |_|    \____/|_____|_| \____|\___/|_| \_| |____/|_____/_/   \_\_| |_____|_| \_\
                     Local Voice & 3D Assistant v2.3
"""

def wait_and_open_browser(url: str, check_url: str | None = None, poll_interval: float = 1.0, max_attempts: int = 60) -> None:
    """
    Aktivně dotazuje backend (urllib.request) a otevře prohlížeč až v momentě,
    kdy server vrátí úspěšnou HTTP 200 odpověď (inicializace modelů hotova).
    """
    if check_url is None:
        check_url = f"{url.rstrip('/')}/api/status"

    def _target():
        print(f"[*] Sleduji inicializaci serveru ({check_url})...")
        attempts = 0
        while attempts < max_attempts:
            time.sleep(poll_interval)
            attempts += 1
            try:
                req = urllib.request.Request(check_url, headers={"User-Agent": "PolygonBeaterLauncher/2.3"})
                with urllib.request.urlopen(req, timeout=2.0) as resp:
                    if resp.status == 200:
                        print(f"\n[Polygon Beater] Backend je plně připraven (HTTP 200). Otevírám rozhraní v prohlížeči: {url}")
                        webbrowser.open_new_tab(url)
                        return
            except (urllib.error.URLError, urllib.error.HTTPError, OSError):
                # Server ještě nenastartoval nebo inicializuje modely, zkusíme za 1s
                continue
            except Exception as exc:
                print(f"[Polygon Beater] Chyba při testování dostupnosti ({exc})")
                continue

        # Fallback po vypršení maximálního počtu pokusů
        print(f"\n[Polygon Beater] Timeout dotazování serveru. Otevírám prohlížeč: {url}")
        try:
            webbrowser.open_new_tab(url)
        except Exception as exc:
            print(f"[Polygon Beater] Otevření prohlížeče selhalo: {exc}")

    thread = threading.Thread(target=_target, daemon=True)
    thread.start()

def main():
    parser = argparse.ArgumentParser(description="Polygon Beater Voice CS — Web Interface Launcher")
    # Bezpečnostní opatření (Fáze 6): Výchozí hodnota je natvrdo 127.0.0.1 (loopback).
    # Při spuštění na veřejném rozhraní se zobrazí bezpečnostní varování.
    parser.add_argument("--host", default="127.0.0.1", help="Host rozhraní (výchozí: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port rozhraní (výchozí: 8000)")
    parser.add_argument("--no-browser", action="store_true", help="Neotevírat automaticky webový prohlížeč")
    parser.add_argument("--reload", action="store_true", help="Povolit autoreload pro vývoj")
    args = parser.parse_args()

    print(BANNER)
    print(f"[*] Inicializuji lokální Polygon Beater engine na http://{args.host}:{args.port}")
    print("[*] 100% Soukromé & Lokální prostředí (LLM, Blender Bridge, RAG Paměť, STT/TTS)")
    print("[*] Stiskněte Ctrl+C pro ukončení serveru.\n")

    # Bezpečnostní varování při startu na veřejném rozhraní
    _PUBLIC_HOSTS = {"0.0.0.0", "::"}
    if args.host in _PUBLIC_HOSTS:
        print("=" * 70)
        print("⚠️  BEZPEČNOSTNÍ VAROVÁNÍ: Server je spuštěn na veřejném rozhraní!")
        print(f"   Host: {args.host}:{args.port}")
        print("   Polygon Beater zpřístupní rozhraní VŠEM zařízením v lokální síti.")
        print("   Pro bezpečný provoz spusťte s --host 127.0.0.1 (výchozí hodnota).")
        print("=" * 70 + "\n")

    if not args.no_browser:
        browser_host = "127.0.0.1" if args.host in _PUBLIC_HOSTS else args.host
        browser_url = f"http://{browser_host}:{args.port}"
        status_url = f"http://{browser_host}:{args.port}/api/status"
        wait_and_open_browser(browser_url, check_url=status_url, poll_interval=1.0)

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
