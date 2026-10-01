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

            # Čekání na dokončení úlohy v hlavním vlákně Blenderu
            success = completion_event.wait(timeout=15.0)
            if not success:
                resp = {
                    "status": "error",
                    "error": "Timeout: Blender hlavní vlákno nestihlo úlohu vykonat včas.",
                    "traceback": "TimeoutError: bpy.app.timers execution timed out after 15.0s",
                }
            else:
                resp = result_container.get("response", {"status": "success"})

            conn.sendall((json.dumps(resp) + "\n").encode("utf-8"))

        except Exception as exc:
            err_resp = {"status": "error", "error": str(exc), "traceback": traceback.format_exc()}
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


def collect_scene_metrics():
    """
    Sesbírá základní metriku o scéně:
    - celkový počet objektů
    - seznam vybraných objektů (jména, typy meshů, souřadnice lokace, rotace a měřítko)
    - přítomná světla a kamery
    - aktivní objekt, režim editoru a render engine
    """
    scene = bpy.context.scene
    all_objects = list(bpy.data.objects)
    selected = list(bpy.context.selected_objects) if hasattr(bpy.context, "selected_objects") else []

    active_obj = None
    if hasattr(bpy.context, "view_layer") and hasattr(bpy.context.view_layer, "objects"):
        active_obj = bpy.context.view_layer.objects.active
    if not active_obj and hasattr(bpy.context, "active_object"):
        active_obj = bpy.context.active_object

    def fmt_vec(v, decimals=3):
        return [round(float(x), decimals) for x in v]

    def fmt_rot(rot, decimals=3):
        return [round(float(x), decimals) for x in rot]

    selected_info = []
    for obj in selected:
        info = {
            "name": obj.name,
            "type": obj.type,
            "location": fmt_vec(obj.location),
            "rotation_euler": fmt_rot(obj.rotation_euler),
            "scale": fmt_vec(obj.scale),
            "is_active": (obj == active_obj),
        }
        if obj.type == 'MESH' and getattr(obj, "data", None):
            info["mesh_name"] = obj.data.name
            info["vertices"] = len(obj.data.vertices) if hasattr(obj.data, "vertices") else 0
            info["polygons"] = len(obj.data.polygons) if hasattr(obj.data, "polygons") else 0
            if hasattr(obj.data, "materials"):
                info["materials"] = [m.name for m in obj.data.materials if m]
        selected_info.append(info)

    lights_info = []
    for obj in all_objects:
        if obj.type == 'LIGHT' and getattr(obj, "data", None):
            lights_info.append({
                "name": obj.name,
                "light_type": getattr(obj.data, "type", "POINT"),
                "energy": round(float(getattr(obj.data, "energy", 0.0)), 2),
                "location": fmt_vec(obj.location),
            })

    cameras_info = []
    for obj in all_objects:
        if obj.type == 'CAMERA' and getattr(obj, "data", None):
            is_active = (scene.camera == obj) if hasattr(scene, "camera") else False
            cameras_info.append({
                "name": obj.name,
                "is_active_scene_camera": is_active,
                "location": fmt_vec(obj.location),
                "lens_mm": round(float(getattr(obj.data, "lens", 50.0)), 1),
            })

    active_obj_info = None
    if active_obj:
        active_obj_info = {
            "name": active_obj.name,
            "type": active_obj.type,
            "location": fmt_vec(active_obj.location),
            "rotation_euler": fmt_rot(active_obj.rotation_euler),
            "scale": fmt_vec(active_obj.scale),
        }
        if active_obj.type == 'MESH' and getattr(active_obj, "data", None):
            active_obj_info["vertices"] = len(active_obj.data.vertices) if hasattr(active_obj.data, "vertices") else 0
            active_obj_info["polygons"] = len(active_obj.data.polygons) if hasattr(active_obj.data, "polygons") else 0

    all_objs_summary = [
        {
            "name": obj.name,
            "type": obj.type,
            "visible": not getattr(obj, "hide_viewport", False),
        }
        for obj in all_objects
    ]

    metrics = {
        "scene_name": getattr(scene, "name", "Scene"),
        "mode": getattr(bpy.context, "mode", "OBJECT"),
        "total_objects": len(all_objects),
        "selected_count": len(selected),
        "active_object": active_obj_info,
        "selected_objects": selected_info,
        "lights": lights_info,
        "cameras": cameras_info,
        "all_objects_summary": all_objs_summary,
        "render_engine": getattr(scene.render, "engine", "BLENDER_EEVEE") if hasattr(scene, "render") else "BLENDER_EEVEE",
    }
    return metrics


def capture_viewport_render(output_path="/tmp/blender_viewport.png"):
    """
    Uloží aktuální 3D viewport render do souboru pomocí:
    bpy.ops.render.opengl(write_still=True, view_context=True)
    """
    import os
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    scene = bpy.context.scene
    orig_filepath = scene.render.filepath
    orig_format = scene.render.image_settings.file_format

    try:
        scene.render.filepath = output_path
        scene.render.image_settings.file_format = 'PNG'

        target_win = None
        target_area = None
        target_region = None

        if hasattr(bpy.context, "window_manager") and bpy.context.window_manager:
            for win in bpy.context.window_manager.windows:
                if not win.screen:
                    continue
                for area in win.screen.areas:
                    if area.type == 'VIEW_3D':
                        target_win = win
                        target_area = area
                        for region in area.regions:
                            if region.type == 'WINDOW':
                                target_region = region
                                break
                        if target_region:
                            break
                if target_area:
                    break

        rendered = False
        if target_area and target_win:
            override_ctx = {
                "window": target_win,
                "screen": target_win.screen,
                "area": target_area,
                "region": target_region or target_area.regions[0],
                "scene": scene,
            }
            if hasattr(bpy.context, "temp_override"):
                try:
                    with bpy.context.temp_override(**override_ctx):
                        bpy.ops.render.opengl(write_still=True, view_context=True)
                        rendered = True
                except Exception as ex1:
                    print(f"[AI-Blender] temp_override opengl selhalo: {ex1}")

            if not rendered:
                try:
                    bpy.ops.render.opengl(override_ctx, write_still=True, view_context=True)
                    rendered = True
                except Exception as ex2:
                    print(f"[AI-Blender] context override dict opengl selhalo: {ex2}")

        if not rendered:
            try:
                bpy.ops.render.opengl(write_still=True, view_context=False)
                rendered = True
            except Exception:
                bpy.ops.render.render(write_still=True)
                rendered = True

        actual_path = output_path
        if not os.path.exists(actual_path):
            if os.path.exists(output_path + ".png"):
                actual_path = output_path + ".png"
            elif os.path.exists(output_path + "0001.png"):
                actual_path = output_path + "0001.png"

        return actual_path
    finally:
        scene.render.filepath = orig_filepath
        scene.render.image_settings.file_format = orig_format


def process_blender_queue_timer():
    """
    Tato funkce je volána pravidelně z HLAVNÍHO VLÁKNA Blenderu pomocí bpy.app.timers.
    Bezpečně spouští příchozí Python kód přímo v kontextu Blender scény nebo provádí inspekci.
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
        action = message.get("action", "execute")

        # 1. Inspekce 3D scény a pořízení snímku viewportu
        if action in ("inspect_scene", "viewport_snapshot"):
            output_path = message.get("output_path", "/tmp/blender_viewport.png")
            print("\n[AI-Blender] >>> Zahajuji inspekci 3D scény a viewportu...")
            try:
                metrics = collect_scene_metrics()
                img_path = capture_viewport_render(output_path)
                result_container["response"] = {
                    "status": "success",
                    "action": action,
                    "scene_metrics": metrics,
                    "screenshot_path": img_path,
                }
                print(f"✅ [AI-Blender] Inspekce scény dokončena (objektů: {metrics['total_objects']}, snapshot: {img_path})")
            except Exception as e:
                err_trace = traceback.format_exc()
                result_container["response"] = {
                    "status": "error",
                    "error": str(e),
                    "traceback": err_trace,
                }
                print(f"❌ [AI-Blender] Chyba při inspekci scény: {e}")
                print(err_trace)
            finally:
                completion_event.set()
                _RECEIVER_INSTANCE.request_queue.task_done()
            continue

        # 2. Vykonání Python kódu (action == 'execute')
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
                "traceback": err_trace,
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
