"""
=============================================================================
             POLYGON BEATER AI ASSISTANT - BLENDER RECEIVER
=============================================================================
Tento skript spusťte uvnitř Blenderu (v záložce Text Editor -> klikněte na 'Run Script' nebo stiskněte Alt+P).

Jak to funguje:
1. Spustí na pozadí neblokující TCP server na adrese 127.0.0.1:9876.
2. Přijímá příkazy vygenerované AI asistentem (modul bpy).
3. Pomocí oficiálního Blender Timer API (bpy.app.timers) kód bezpečně spustí
   v HLAVNÍM VLÁKNĚ Blenderu, takže nehrozí pád aplikace ani kolize s GPU.
4. Okamžitě překreslí 3D pohled a odešle asistentovi potvrzení o výsledku.
=============================================================================
"""

import contextlib
import io
import json
import logging
import queue
import socket
import sys
import threading
import traceback

import bpy

HOST = "127.0.0.1"
PORT = 9876

# Globální instance pro správu běhu serveru
_RECEIVER_INSTANCE = None


class BlenderSocketServer:
    def __init__(self, host=HOST, port=PORT):
        self.host = host
        self.port = port
        self.server_sock = None
        self.is_running = False
        self.request_queue = queue.Queue()
        self.listen_thread = None

    def start(self):
        if self.is_running:
            print("[AI-Blender] Server již běží.")
            return

        try:
            self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_sock.bind((self.host, self.port))
            self.server_sock.listen(5)
            self.server_sock.settimeout(0.5)
            self.is_running = True

            # Registrace časovače v hlavním vlákně Blenderu
            if not bpy.app.timers.is_registered(process_blender_queue_timer):
                bpy.app.timers.register(process_blender_queue_timer, persistent=True)

            self.listen_thread = threading.Thread(target=self._accept_loop, daemon=True)
            self.listen_thread.start()

            print(f"==================================================")
            print(f"🤖 [AI-Blender] Server úspěšně spuštěn na {self.host}:{self.port}")
            print(f"Připraven přijímat hlasové i textové příkazy od asistenta.")
            print(f"==================================================")
        except Exception as e:
            print(f"❌ [AI-Blender] Nelze spustit server na {self.host}:{self.port}: {e}")
            self.stop()

    def _accept_loop(self):
        while self.is_running and self.server_sock:
            try:
                conn, addr = self.server_sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            except Exception as e:
                print(f"[AI-Blender] Chyba při accept: {e}")
                break

            # Zpracování klienta v samostatném worker vlákně
            threading.Thread(target=self._handle_client, args=(conn, addr), daemon=True).start()

    def _handle_client(self, conn, addr):
        try:
            conn.settimeout(15.0)
            data_buffer = b""
            while not data_buffer.endswith(b"\n"):
                chunk = conn.recv(4096)
                if not chunk:
                    break
                data_buffer += chunk

            if not data_buffer:
                conn.close()
                return

            message = json.loads(data_buffer.decode("utf-8"))
            action = message.get("action", "execute")

            # Ping test
            if action == "ping":
                resp = {
                    "status": "pong",
                    "blender_version": ".".join(map(str, bpy.app.version)),
                    "file": bpy.data.filepath or "Untitled",
                }
                conn.sendall((json.dumps(resp) + "\n").encode("utf-8"))
                conn.close()
                return

            # Spuštění kódu v hlavním vlákně Blenderu přes frontu
            completion_event = threading.Event()
            result_container = {}

            self.request_queue.put((message, completion_event, result_container))

            # Čekání na dokončení kódu v hlavním vlákně Blenderu
            success = completion_event.wait(timeout=10.0)
            if not success:
                resp = {
                    "status": "error",
                    "error": "Timeout: Blender hlavní vlákno nestihlo úlohu vykonat včas.",
                }
            else:
                resp = result_container.get("response", {"status": "success"})

            conn.sendall((json.dumps(resp) + "\n").encode("utf-8"))

        except Exception as exc:
            err_resp = {"status": "error", "error": str(exc), "trace": traceback.format_exc()}
            try:
                conn.sendall((json.dumps(err_resp) + "\n").encode("utf-8"))
            except Exception:
                pass
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def stop(self):
        print("[AI-Blender] Zastavuji server...")
        self.is_running = False
        if bpy.app.timers.is_registered(process_blender_queue_timer):
            bpy.app.timers.unregister(process_blender_queue_timer)
        if self.server_sock:
            try:
                self.server_sock.close()
            except Exception:
                pass
            self.server_sock = None
        print("[AI-Blender] Server byl ukončen.")


def process_blender_queue_timer():
    """
    Tato funkce je volána pravidelně z HLAVNÍHO VLÁKNA Blenderu pomocí bpy.app.timers.
    Bezpečně spouští příchozí Python kód přímo v kontextu Blender scény.
    """
    global _RECEIVER_INSTANCE
    if not _RECEIVER_INSTANCE or not _RECEIVER_INSTANCE.is_running:
        return None  # Ukončí časovač

    while not _RECEIVER_INSTANCE.request_queue.empty():
        try:
            item = _RECEIVER_INSTANCE.request_queue.get_nowait()
        except queue.Empty:
            break

        message, completion_event, result_container = item
        code = message.get("code", "")
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()

        print(f"\n[AI-Blender] >>> Vykonávám příkaz asistenta:")
        print("--------------------------------------------------")
        print(code)
        print("--------------------------------------------------")

        exec_context = {
            "bpy": bpy,
            "__name__": "__main__",
        }

        try:
            with contextlib.redirect_stdout(stdout_capture), contextlib.redirect_stderr(stderr_capture):
                exec(code, exec_context)

            # Vynutit překreslení všech 3D pohledů, aby uživatel ihned viděl výsledek
            for window in bpy.context.window_manager.windows:
                for area in window.screen.areas:
                    if area.type == 'VIEW_3D':
                        area.tag_redraw()

            out_text = stdout_capture.getvalue().strip()
            result_container["response"] = {
                "status": "success",
                "output": out_text or "Kód byl úspěšně vykonán.",
            }
            print(f"✅ [AI-Blender] Kód úspěšně proběhl.")
            if out_text:
                print(f"Výstup:\n{out_text}")

        except Exception as e:
            err_trace = traceback.format_exc()
            result_container["response"] = {
                "status": "error",
                "error": str(e),
                "trace": err_trace,
                "output": stdout_capture.getvalue().strip(),
            }
            print(f"❌ [AI-Blender] Chyba při spuštění kódu: {e}")
            print(err_trace)
        finally:
            completion_event.set()
            _RECEIVER_INSTANCE.request_queue.task_done()

    # Spouštět každých 50 ms pro minimální latenci
    return 0.05


def start_server():
    global _RECEIVER_INSTANCE
    # Pokud již běží starý server, bezpečně ho zastavíme
    if _RECEIVER_INSTANCE:
        _RECEIVER_INSTANCE.stop()
    _RECEIVER_INSTANCE = BlenderSocketServer()
    _RECEIVER_INSTANCE.start()


def stop_server():
    global _RECEIVER_INSTANCE
    if _RECEIVER_INSTANCE:
        _RECEIVER_INSTANCE.stop()
        _RECEIVER_INSTANCE = None


# Automatické spuštění serveru při spuštění skriptu v Blenderu
if __name__ == "__main__" or __name__ == "<run_path>":
    start_server()
