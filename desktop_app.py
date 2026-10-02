#!/usr/bin/env python3
"""
desktop_app.py — Nativní desktopový wrapper a správce sjednoceného životního cyklu.
Polygon Beater Voice CS.

Zajišťuje:
1. Běh lokálního FastAPI/Uvicorn serveru v koordinovaném vlákně.
2. Aktivní sledování připravenosti serveru (health check polling na /api/status).
3. Spuštění čistého samostatného desktopového okna bez adresního řádku a záložek
   pomocí pywebview nebo systémového Chromium prohlížeče v aplikačním režimu (--app).
4. Sjednocený životní cyklus: Okamžité a čisté ukončení celého backendu a uvolnění
   všech procesů při zavření okna nebo stisku Ctrl+C (žádné zombie procesy).
"""

from __future__ import annotations

import argparse
import atexit
import logging
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

logger = logging.getLogger("polygon_beater.desktop")

BANNER = r"""
  ____   ____  _  __   ______  ___  _   _   ____  _____    _  _____ _____ ____  
 |  _ \ / __ \| | \ \ / / ___|/ _ \| \ | | | __ )| ____|  / \|_   _| ____|  _ \ 
 | |_) | |  | | |  \ V / |  _| | | |  \| | |  _ \|  _|   / _ \ | | |  _| | |_) |
 |  __/| |__| | |___| || |_| | |_| | |\  | | |_) | |___ / ___ \| | | |___|  _ < 
 |_|    \____/|_____|_| \____|\___/|_| \_| |____/|_____/_/   \_\_| |_____|_| \_\
                     Standalone Desktop Application v2.3
"""

# Seznam kandidátů na Chromium prohlížeče podporující --app=...
APP_BROWSERS = [
    "brave-browser",
    "brave",
    "google-chrome",
    "google-chrome-stable",
    "chromium",
    "chromium-browser",
    "microsoft-edge",
    "microsoft-edge-stable",
]


def find_system_app_browser() -> Optional[str]:
    """Vyhledá v systému první dostupný prohlížeč podporující aplikační režim (--app)."""
    for browser in APP_BROWSERS:
        path = shutil.which(browser)
        if path:
            return path
    return None


def get_desktop_profile_dir() -> Path:
    """Vrací cestu k izolovanému uživatelskému profilu pro desktopové okno."""
    config_home = os.environ.get("XDG_CONFIG_HOME")
    if config_home:
        base = Path(config_home)
    else:
        base = Path.home() / ".config"
    profile_dir = base / "polygon_beater_desktop"
    profile_dir.mkdir(parents=True, exist_ok=True)
    return profile_dir


def wait_for_server(
    check_url: str,
    timeout: float = 35.0,
    poll_interval: float = 0.25,
) -> bool:
    """
    Aktivně dotazuje backend, dokud nevrátí HTTP 200, což značí plnou připravenost serveru.
    """
    start_time = time.monotonic()
    req = urllib.request.Request(
        check_url,
        headers={"User-Agent": "PolygonBeaterDesktopLauncher/2.3"},
    )
    while time.monotonic() - start_time < timeout:
        try:
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                if resp.status == 200:
                    return True
        except (urllib.error.URLError, urllib.error.HTTPError, OSError):
            pass
        time.sleep(poll_interval)
    return False


class DesktopAppRunner:
    """
    Správce sjednoceného životního cyklu pro FastAPI backend a desktopové UI okno.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8000,
        reload: bool = False,
        window_title: str = "Polygon Beater — AI Assistant Voice CS",
        width: int = 1440,
        height: int = 900,
        use_pywebview: bool = True,
        open_as_tab: bool = False,
        quiet: bool = False,
    ):
        self.host = host
        self.port = port
        self.reload = reload
        self.window_title = window_title
        self.width = width
        self.height = height
        self.use_pywebview = use_pywebview
        self.open_as_tab = open_as_tab
        self.quiet = quiet

        self.server: Optional[object] = None
        self.server_thread: Optional[threading.Thread] = None
        self.browser_proc: Optional[subprocess.Popen] = None
        self._is_shutting_down = False
        self._lock = threading.Lock()
        self._shutdown_event = threading.Event()

    def _run_server_thread(self):
        """Spustí Uvicorn server v samostatném vlákně."""
        import uvicorn
        log_level = "error" if self.quiet else ("warning" if not self.reload else "info")
        config = uvicorn.Config(
            "web_server:app",
            host=self.host,
            port=self.port,
            reload=self.reload,
            log_level=log_level,
        )
        self.server = uvicorn.Server(config)
        self.server.run()

    def _launch_browser_window(self, url: str) -> Optional[subprocess.Popen]:
        """Spustí systémový prohlížeč v dedikovaném aplikačním režimu (--app)."""
        if self.open_as_tab:
            import webbrowser
            if not self.quiet:
                logger.info("Otevírám standardní záložku v prohlížeči: %s", url)
            webbrowser.open_new_tab(url)
            return None

        browser_bin = find_system_app_browser()
        if not browser_bin:
            logger.warning("V systému nebyl nalezen žádný prohlížeč s podporou --app. Používám systémový výchozí.")
            import webbrowser
            webbrowser.open_new_tab(url)
            return None

        profile_dir = get_desktop_profile_dir()
        cmd = [
            browser_bin,
            f"--app={url}",
            f"--user-data-dir={profile_dir}",
            f"--window-size={self.width},{self.height}",
            "--window-position=center",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-background-mode",
            "--disable-session-crashed-bubble",
            "--hide-crash-restore-bubble",
            "--password-store=basic",
            "--disable-features=Translate,OptimizationHints,MediaRouter",
            "--disable-sync",
            "--disable-background-networking",
            "--disable-component-update",
            "--app-id=polygon_beater_desktop",
            "--class=PolygonBeater",
        ]
        if not self.quiet:
            logger.info("Spouštím samostatné desktopové okno: %s", browser_bin)
        try:
            # Přesměrování stdout/stderr na DEVNULL zamezí šumu z grafických ovladačů do terminálu
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return proc
        except Exception as exc:
            logger.error("Chyba při spuštění okna prohlížeče: %s", exc)
            import webbrowser
            webbrowser.open_new_tab(url)
            return None

    def shutdown(self, reason: str = ""):
        """Čistě ukončí desktopové okno i FastAPI backend bez zanechání zombie procesů."""
        with self._lock:
            if self._is_shutting_down:
                return
            self._is_shutting_down = True

        if not self.quiet:
            if reason:
                print(f"\n[*] {reason}")
            print("[*] Provádím čisté ukončení Polygon Beater (backend i okno)...")

        # 1. Ukončit proces okna prohlížeče, pokud ještě běží
        if self.browser_proc and self.browser_proc.poll() is None:
            try:
                self.browser_proc.terminate()
                self.browser_proc.wait(timeout=2.0)
            except Exception:
                try:
                    self.browser_proc.kill()
                except Exception:
                    pass

        # 2. Ukončit Uvicorn server nastavením příznaku should_exit
        if self.server:
            try:
                self.server.should_exit = True
            except Exception:
                pass

        if self.server_thread and self.server_thread.is_alive():
            self.server_thread.join(timeout=3.0)

        self._shutdown_event.set()
        if not self.quiet:
            print("[✓] Polygon Beater byl čistě ukončen. Všechny procesy uvolněny.")

    def run(self):
        """Hlavní řídicí smyčka spuštění a sledování životního cyklu."""
        # Registrace atexit handleru
        atexit.register(self.shutdown)

        # Registrace signal handlerů (Ctrl+C, SIGTERM)
        def _signal_handler(signum, frame):
            sig_name = "SIGINT (Ctrl+C)" if signum == signal.SIGINT else f"Signál {signum}"
            self.shutdown(f"Zachycen {sig_name}")
            sys.exit(0)

        try:
            signal.signal(signal.SIGINT, _signal_handler)
            signal.signal(signal.SIGTERM, _signal_handler)
        except (ValueError, AttributeError):
            pass

        if not self.quiet:
            print(BANNER)
            print(f"[*] Spouštím Polygon Beater engine na http://{self.host}:{self.port}")
            print("[*] 100% Soukromé & Lokální prostředí (LLM, Blender Bridge, RAG Paměť, STT/TTS)")

        _PUBLIC_HOSTS = {"0.0.0.0", "::"}
        if self.host in _PUBLIC_HOSTS:
            print("=" * 70)
            print("⚠️  BEZPEČNOSTNÍ VAROVÁNÍ: Server je spuštěn na veřejném rozhraní!")
            print(f"   Host: {self.host}:{self.port}")
            print("   Polygon Beater zpřístupní rozhraní VŠEM zařízením v lokální síti.")
            print("=" * 70 + "\n")

        browser_host = "127.0.0.1" if self.host in _PUBLIC_HOSTS else self.host
        url = f"http://{browser_host}:{self.port}"
        status_url = f"{url}/api/status"

        # Start FastAPI/Uvicorn serveru v samostatném koordinovaném vlákně
        self.server_thread = threading.Thread(target=self._run_server_thread, daemon=True)
        self.server_thread.start()

        # Automatický start: Aktivní čekání na plnou inicializaci serveru
        if not self.quiet:
            print(f"[*] Čekám na dokončení inicializace backendu ({status_url})...")
        ready = wait_for_server(status_url, timeout=35.0, poll_interval=0.25)
        if not ready:
            print(f"[!] Backend na {status_url} neodpověděl v časovém limitu. Ukončuji.")
            self.shutdown("Server timeout při startu")
            sys.exit(1)

        if not self.quiet:
            print("[✓] Backend je plně připraven (HTTP 200).")

        # 1. Zkouška pywebview (pokud je povoleno a dostupné v prostředí)
        pywebview_launched = False
        if self.use_pywebview and not self.open_as_tab:
            try:
                import webview
                print("[*] Spouštím nativní desktopové okno přes pywebview...")

                def _on_closed():
                    self.shutdown("Desktopové okno bylo zavřeno uživatelem.")

                window = webview.create_window(
                    title=self.window_title,
                    url=url,
                    width=self.width,
                    height=self.height,
                    min_size=(960, 600),
                )
                window.events.closed += _on_closed
                webview.start()
                pywebview_launched = True
            except (ImportError, Exception) as exc:
                logger.debug("pywebview není dostupné (%s), použiji aplikační režim systémového prohlížeče.", exc)
                pywebview_launched = False

        # 2. Systémový prohlížeč v režimu samostatné aplikace (--app=...)
        if not pywebview_launched:
            self.browser_proc = self._launch_browser_window(url)
            if self.browser_proc:
                print(f"[✓] Samostatné desktopové okno běží (PID {self.browser_proc.pid}).")
                print("[*] Sjednocený životní cyklus aktivní: Zavřením okna se aplikace čistě ukončí.\n")

                # Sledování životního cyklu okna
                while not self._is_shutting_down:
                    # Kontrola 1: Zavřel uživatel okno aplikace?
                    ret = self.browser_proc.poll()
                    if ret is not None:
                        self.shutdown("Desktopové okno bylo zavřeno uživatelem.")
                        break

                    # Kontrola 2: Běží server stále v pořádku?
                    if self.server_thread and not self.server_thread.is_alive():
                        self.shutdown("Backend server byl neočekávaně ukončen.")
                        break

                    time.sleep(0.3)
            else:
                # Záložní režim při otevření běžné záložky
                print("[!] Rozhraní otevřeno v běžném prohlížeči. Pro ukončení stiskněte Ctrl+C v terminálu.")
                while not self._is_shutting_down:
                    if self.server_thread and not self.server_thread.is_alive():
                        break
                    time.sleep(0.5)

        self.shutdown()


def main():
    parser = argparse.ArgumentParser(description="Polygon Beater Voice CS — Desktop Application Launcher")
    parser.add_argument("--host", default="127.0.0.1", help="Host rozhraní (výchozí: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port rozhraní (výchozí: 8000)")
    parser.add_argument("--browser-tab", action="store_true", help="Otevřít běžnou záložku namísto samostatného okna")
    parser.add_argument("--no-window", "--server-only", dest="server_only", action="store_true", help="Spustit pouze server bez desktopového okna")
    parser.add_argument("--quiet", "-q", action="store_true", help="Tichý start pro čisté desktopové prostředí")
    parser.add_argument("--reload", action="store_true", help="Povolit autoreload pro vývoj")
    args = parser.parse_args()

    if args.server_only:
        import uvicorn
        if not args.quiet:
            print(BANNER)
            print(f"[*] Spouštím Polygon Beater v režimu pouze server na http://{args.host}:{args.port}")
        uvicorn.run("web_server:app", host=args.host, port=args.port, reload=args.reload)
        return

    runner = DesktopAppRunner(
        host=args.host,
        port=args.port,
        reload=args.reload,
        open_as_tab=args.browser_tab,
        quiet=args.quiet,
    )
    runner.run()


if __name__ == "__main__":
    main()
