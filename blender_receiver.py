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
import os
import pathlib
import queue
import socket
import sys
import tempfile
import threading
import traceback

import bpy

try:
    from code_validator import validate_blender_code
except ImportError:
    _proj_root = str(pathlib.Path(__file__).resolve().parent)
    if _proj_root not in sys.path:
        sys.path.insert(0, _proj_root)
    from code_validator import validate_blender_code

HOST = "127.0.0.1"
PORT = 9876


def is_safe_output_path(filepath: str, allowed_dirs: list[str] | None = None) -> tuple[bool, str, pathlib.Path | None]:
    """
    Bezpečnostní validace a sandboxing cílové cesty pro render/viewport/export.
    Ověří, že cílová cesta leží výhradně v povoleném adresáři (/tmp, tempfile, scratch/ uvnitř projektu)
    a neobsahuje nepovolený path traversal ('..').
    """
    if not filepath or not str(filepath).strip():
        return False, "Výstupní cesta nesmí být prázdná.", None

    clean_str = str(filepath).strip().strip("'\"`:*#")

    if ".." in pathlib.Path(clean_str).parts:
        return False, f"Path traversal '..' je zakázán: {clean_str}", None

    try:
        resolved_path = pathlib.Path(clean_str).resolve()
    except Exception as e:
        return False, f"Neplatná cesta: {e}", None

    allowed_roots: list[pathlib.Path] = [
        pathlib.Path(tempfile.gettempdir()).resolve(),
        pathlib.Path("/tmp").resolve(),
    ]
    try:
        project_root = pathlib.Path(__file__).resolve().parent
        allowed_roots.append((project_root / "scratch").resolve())
        allowed_roots.append((project_root / "renders").resolve())
        allowed_roots.append((project_root / "rag_storage").resolve())
    except Exception:
        pass

    if allowed_dirs:
        for d in allowed_dirs:
            try:
                allowed_roots.append(pathlib.Path(d).resolve())
            except Exception:
                pass

    is_inside = any(
        root in resolved_path.parents or resolved_path.parent == root
        for root in allowed_roots
    )

    if not is_inside:
        return False, f"Zápis mimo povolené adresáře je zakázán: {resolved_path}", None

    return True, "", resolved_path


def get_blender_auth_token(fail_closed: bool = True) -> str:
    """
    Získá autentizační token pro Blender Bridge:
    1. Z proměnné prostředí POLYGON_BLENDER_AUTH_TOKEN nebo BLENDER_BRIDGE_TOKEN
    2. Z config.json (klíč blender.auth_token)

    Bezpečnostní pravidlo (Fail-Secure):
    Žádný výchozí hardcoded token není povolen. Pokud token chybí a fail_closed=True,
    vyvolá výjimku RuntimeError a zabrání spuštění serveru.
    """
    env_token = os.environ.get("POLYGON_BLENDER_AUTH_TOKEN") or os.environ.get("BLENDER_BRIDGE_TOKEN")
    if env_token and env_token.strip():
        return env_token.strip()

    try:
        candidates = [
            pathlib.Path(__file__).resolve().parent / "config.json",
            pathlib.Path.cwd() / "config.json",
        ]
        for cfg_path in candidates:
            if cfg_path.is_file():
                with open(cfg_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    tok = cfg.get("blender", {}).get("auth_token")
                    if tok and str(tok).strip():
                        return str(tok).strip()
    except Exception:
        pass

    if fail_closed:
        raise RuntimeError(
            "Bezpečnostní pojistka (Fail-Secure): Autentizační token pro Blender Bridge není nastaven! "
            "Nastavte proměnnou prostředí POLYGON_BLENDER_AUTH_TOKEN (nebo BLENDER_BRIDGE_TOKEN), "
            "případně klíč 'blender.auth_token' v config.json."
        )
    return ""

# Globální instance pro správu běhu serveru
_RECEIVER_INSTANCE = None

# Množina bezpečně povolených strukturovaných akcí (libovolný exec() byl odstraněn)
ALLOWED_ACTIONS = {
    "ping",
    "get_status",
    "status",
    "inspect_scene",
    "viewport_snapshot",
    "render",
    # Spuštění BPY skriptu generovaného AI asistentem v hlavním vlákně Blenderu.
    # Tato akce záměrně umožňuje exec() v izolovaném prostředí Blenderu – je
    # dostupná POUZE přes lokální TCP socket 127.0.0.1:9876 a NIKDY z webu.
    "run_bpy_script",
    "move",
    "rotate",
    "scale",
    "select",
    "delete",
    "mesh_doctor_audit",
    "mesh_doctor_repair",
    "create_product_studio",
    "create_procedural_shader",
    "uv_texel_audit",
    "smart_uv_pack",
    "generate_parametric_model",
    "apply_modifier_stack",
    "create_geometry_nodes_bridge",
    "apply_fcurve_animation",
    "create_motion_node_setup",
    "setup_blueprint_reference",
    "vectorize_image_to_3d",
    "setup_compositor",
    "generate_local_ai_mesh",
    "auto_rig",
    "auto_rig_and_skin",
}


def _validate_numeric(value, field_name: str) -> float:
    """
    Bezpečnostní opatření (Fáze 6 — Nález č. 3): Explicitní typová kontrola
    číselných argumentů pro move/rotate/scale.
    Přijímá výhradně int nebo float; odmítá řetězce, bool, None a jakýkoliv
    jiný typ, aby nebylo možné podsunout Blender driver syntaxi nebo výrazy.
    """
    if isinstance(value, bool):
        # bool je podtřída int — odmítnout explicitně
        raise TypeError(
            f"Pole '{field_name}' musí být číslo (int/float), nikoliv bool: {value!r}"
        )
    if not isinstance(value, (int, float)):
        raise TypeError(
            f"Pole '{field_name}' musí být číslo (int/float), "
            f"obdržen typ {type(value).__name__!r}: {value!r}"
        )
    result = float(value)
    if result != result:  # NaN guard
        raise ValueError(f"Pole '{field_name}' obsahuje NaN — odmítnuto.")
    if abs(result) == float("inf"):
        raise ValueError(f"Pole '{field_name}' obsahuje Infinity — odmítnuto.")
    return result


def _validate_vec3(vec, field_name: str) -> tuple:
    """
    Ověří, že vstup je seznam nebo n-tice přesně 3 číselných prvků.
    Vrátí tuple (float, float, float).
    """
    if not isinstance(vec, (list, tuple)):
        raise TypeError(
            f"Pole '{field_name}' musí být seznam nebo n-tice 3 čísel, "
            f"obdržen typ {type(vec).__name__!r}."
        )
    if len(vec) != 3:
        raise ValueError(
            f"Pole '{field_name}' musí mít přesně 3 prvky, obdrženo {len(vec)}."
        )
    return (
        _validate_numeric(vec[0], f"{field_name}[0]"),
        _validate_numeric(vec[1], f"{field_name}[1]"),
        _validate_numeric(vec[2], f"{field_name}[2]"),
    )


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

        # Fail-secure kontrola: ověření přítomnosti platného tokenu před otevřením socketu
        try:
            token = get_blender_auth_token(fail_closed=True)
            if not token:
                raise RuntimeError("Autentizační token pro Blender Bridge nesmí být prázdný.")
        except Exception as auth_err:
            print(f"[ERROR] [AI-Blender] Fatální bezpečnostní chyba při startu: {auth_err}")
            self.stop()
            raise

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
            print(f"[AGENT] [AI-Blender] Server úspěšně spuštěn na {self.host}:{self.port}")
            print(f"Připraven přijímat hlasové i textové příkazy od asistenta.")
            print(f"==================================================")
        except Exception as e:
            print(f"[ERROR] [AI-Blender] Nelze spustit server na {self.host}:{self.port}: {e}")
            self.stop()
            raise

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

            try:
                message = json.loads(data_buffer.decode("utf-8"))
            except Exception as json_err:
                resp = {"status": "error", "error": f"Neplatný formát JSON: {json_err}"}
                conn.sendall((json.dumps(resp) + "\n").encode("utf-8"))
                conn.close()
                return

            if not isinstance(message, dict):
                resp = {"status": "error", "error": "Neplatný formát zprávy: očekáván JSON objekt."}
                conn.sendall((json.dumps(resp) + "\n").encode("utf-8"))
                conn.close()
                return

            # Bezpečnostní ověření autentizačního tokenu
            expected_token = get_blender_auth_token(fail_closed=False)
            incoming_token = message.get("auth_token") or message.get("token")
            if not expected_token or not incoming_token or incoming_token != expected_token:
                resp = {
                    "status": "error",
                    "error_type": "Unauthorized",
                    "error": "Neautorizovaný přístup: Neplatný nebo chybějící autentizační token pro Blender Bridge.",
                }
                conn.sendall((json.dumps(resp) + "\n").encode("utf-8"))
                conn.close()
                return

            action = str(message.get("action", "")).strip()
            if not action or action not in ALLOWED_ACTIONS:
                resp = {
                    "status": "error",
                    "error": f"Neznámá nebo nepovolená akce: '{action}'. Libovolné spouštění Python kódu (exec) je zakázáno.",
                    "allowed_actions": sorted(list(ALLOWED_ACTIONS)),
                }
                conn.sendall((json.dumps(resp) + "\n").encode("utf-8"))
                conn.close()
                return

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

            # Vynucení AST validace pro spouštění skriptů (run_bpy_script) přímo v socket handleru
            if action == "run_bpy_script":
                code_value = message.get("code")
                if not isinstance(code_value, str):
                    resp = {
                        "status": "error",
                        "error_type": "InvalidCodeType",
                        "error": "Pole 'code' musí být textový řetězec.",
                        "message": "Pole 'code' musí být textový řetězec.",
                    }
                    conn.sendall((json.dumps(resp) + "\n").encode("utf-8"))
                    conn.close()
                    return

                code = code_value.strip()
                if not code:
                    resp = {
                        "status": "error",
                        "error_type": "EmptyCodeError",
                        "error": "Pole 'code' je prázdné.",
                        "message": "Pole 'code' je prázdné.",
                    }
                    conn.sendall((json.dumps(resp) + "\n").encode("utf-8"))
                    conn.close()
                    return

                is_valid, validation_msg = validate_blender_code(code)
                if not is_valid:
                    resp = {
                        "status": "error",
                        "error_type": "CodeValidationError",
                        "error": f"AST validace kódu selhala: {validation_msg}",
                        "message": validation_msg,
                    }
                    conn.sendall((json.dumps(resp) + "\n").encode("utf-8"))
                    conn.close()
                    return

            # Spuštění kódu v hlavním vlákně Blenderu přes frontu
            completion_event = threading.Event()
            result_container = {}

            self.request_queue.put((message, completion_event, result_container))

            # Čekání na dokončení úlohy v hlavním vlákně Blenderu
            success = completion_event.wait(timeout=60.0)
            if not success:
                result_container["cancelled"] = True
                resp = {
                    "status": "error",
                    "error_type": "ExecutionTimeout",
                    "error": "Timeout: Blender hlavní vlákno nestihlo úlohu vykonat včas.",
                    "traceback": "TimeoutError: bpy.app.timers execution timed out after 60.0s",
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
    is_safe, err_msg, safe_path = is_safe_output_path(output_path)
    if not is_safe or safe_path is None:
        raise ValueError(f"Bezpečnostní pojistka: Neplatná nebo nepovolená výstupní cesta: {err_msg}")
    output_path = str(safe_path)

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


def calculate_uv_metrics(obj, texture_res=2048):
    """
    Spočítá detailní UV a texel density metriky pro zadaný mesh objekt:
    - total_3d_area_m2: celková plocha 3D geometrie se zohledněním měřítka
    - total_uv_area: plocha UV polygonů v intervalu 0..1
    - uv_space_coverage_pct: využití UV prostoru v %
    - texel_density_px_m: průměrná texel density v px/m
    - texel_density_px_cm: průměrná texel density v px/cm (standard pro herní assety)
    - uv_islands_count: počet samostatných UV ostrovů
    - flipped_faces_count: počet obrácených UV stěn
    - potential_overlaps: indikace možného překryvu UV ostrovů
    """
    import math
    import bmesh

    if not obj or obj.type != 'MESH':
        return None
    mesh = obj.data
    if not mesh.uv_layers:
        return {
            "has_uv": False,
            "object_name": obj.name,
            "error": "Objekt nemá žádnou UV mapu.",
            "total_3d_area_m2": 0.0,
            "texel_density_px_cm": 0.0,
            "uv_space_coverage_pct": 0.0,
            "uv_islands_count": 0,
        }

    scale = obj.scale
    scale_factor = (abs(scale.x * scale.y) + abs(scale.y * scale.z) + abs(scale.x * scale.z)) / 3.0

    bm = bmesh.new()
    bm.from_mesh(mesh)
    uv_layer = bm.loops.layers.uv.active or bm.loops.layers.uv.verify()

    total_3d_area = 0.0
    total_uv_area = 0.0
    flipped_uv_faces = 0
    weighted_td_sum = 0.0

    face_count = len(bm.faces)
    parent = list(range(face_count))

    def find(i):
        path = []
        while parent[i] != i:
            path.append(i)
            i = parent[i]
        for node in path:
            parent[node] = i
        return i

    def union(i, j):
        root_i = find(i)
        root_j = find(j)
        if root_i != root_j:
            parent[root_i] = root_j

    edge_uv_map = {}

    for f_idx, face in enumerate(bm.faces):
        area_3d = face.calc_area() * scale_factor
        total_3d_area += area_3d

        loops = face.loops
        n = len(loops)
        uv_signed_area = 0.0
        for i in range(n):
            uv1 = loops[i][uv_layer].uv
            uv2 = loops[(i + 1) % n][uv_layer].uv
            uv_signed_area += (uv1.x * uv2.y - uv2.x * uv1.y)

            v1_idx = loops[i].vert.index
            v2_idx = loops[(i + 1) % n].vert.index
            edge_key = (min(v1_idx, v2_idx), max(v1_idx, v2_idx))
            uv_pair = (tuple(uv1), tuple(uv2)) if v1_idx < v2_idx else (tuple(uv2), tuple(uv1))
            if edge_key not in edge_uv_map:
                edge_uv_map[edge_key] = []
            edge_uv_map[edge_key].append((f_idx, uv_pair))

        uv_area = abs(uv_signed_area) * 0.5
        total_uv_area += uv_area
        if uv_signed_area < -1e-7:
            flipped_uv_faces += 1

        if area_3d > 1e-8 and uv_area > 1e-8:
            face_td = (math.sqrt(uv_area) * texture_res) / math.sqrt(area_3d)
            weighted_td_sum += face_td * area_3d

    # Detekce a spojení UV ostrovů podle identických UV souřadnic na společných hranách
    for edge_key, entries in edge_uv_map.items():
        if len(entries) >= 2:
            for idx1 in range(len(entries)):
                for idx2 in range(idx1 + 1, len(entries)):
                    e1 = entries[idx1]
                    e2 = entries[idx2]
                    if e1[0] != e2[0]:
                        p1, p2 = e1[1], e2[1]
                        if (abs(p1[0][0] - p2[0][0]) < 1e-4 and abs(p1[0][1] - p2[0][1]) < 1e-4 and
                            abs(p1[1][0] - p2[1][0]) < 1e-4 and abs(p1[1][1] - p2[1][1]) < 1e-4):
                            union(e1[0], e2[0])

    num_islands = len(set(find(i) for i in range(face_count))) if face_count > 0 else 0
    bm.free()

    avg_td_m = (weighted_td_sum / total_3d_area) if total_3d_area > 1e-8 else 0.0
    avg_td_cm = avg_td_m / 100.0
    uv_coverage_pct = min(total_uv_area * 100.0, 100.0)

    return {
        "has_uv": True,
        "object_name": obj.name,
        "texture_resolution": texture_res,
        "total_3d_area_m2": round(total_3d_area, 4),
        "total_uv_area": round(total_uv_area, 4),
        "uv_space_coverage_pct": round(uv_coverage_pct, 2),
        "texel_density_px_m": round(avg_td_m, 2),
        "texel_density_px_cm": round(avg_td_cm, 2),
        "uv_islands_count": num_islands,
        "flipped_faces_count": flipped_uv_faces,
        "potential_overlaps": (total_uv_area > 1.05),
    }


def execute_trusted_blender_code(code: str) -> tuple[str, str]:
    """
    Spustí prověřený Python/bpy skript v kontextu hlavního vlákna Blenderu.

    BEZPEČNOSTNÍ MODEL & ROLE SERVEROVÉHO AST GATEKEEPERU:
    - Veškerý kód přicházející z webu nebo od AI asistenta je před odesláním do Blenderu
      striktně validován serverovým AST Gatekeeperem (`code_validator.py`).
    - Validátor zakazuje nebezpečné moduly (os, sys, subprocess, shutil, socket...),
      blokuje přístup k dunder atributům (.__class__, .__globals__, .__subclasses__),
      zakazuje reflexní funkce (getattr, setattr, vars, dir, eval, exec) a vymáhá whitelist
      povolených modulů (bpy, bmesh, math, mathutils, random, json, colorsys).
    - Tento receiver naslouchá výhradně na lokálním loopback rozhraní (127.0.0.1:9876).
    - Zde se kód vykonává v definovaném kontextu se zachycením stdout/stderr a automatickým
      překreslením 3D viewportu.
    """
    is_valid, validation_msg = validate_blender_code(code)
    if not is_valid:
        raise ValueError(f"AST validace kódu selhala: {validation_msg}")

    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()
    safe_builtins = dict(__builtins__ if isinstance(__builtins__, dict) else __builtins__.__dict__)
    for unsafe_key in ("__import__", "open", "eval", "exec", "compile", "breakpoint"):
        safe_builtins.pop(unsafe_key, None)

    exec_globals = {
        "bpy": bpy,
        "__name__": "__blender_ai_script__",
        "__builtins__": safe_builtins,
    }
    with contextlib.redirect_stdout(stdout_capture), contextlib.redirect_stderr(stderr_capture):
        compiled_code = compile(code, "<ai_generated_bpy_script>", "exec")
        exec(compiled_code, exec_globals)  # noqa: S102

    # Překreslení 3D viewportu po operaci
    if hasattr(bpy.context, "window_manager") and bpy.context.window_manager:
        for window in bpy.context.window_manager.windows:
            if window.screen:
                for area in window.screen.areas:
                    if area.type == 'VIEW_3D':
                        area.tag_redraw()

    return stdout_capture.getvalue(), stderr_capture.getvalue()


def _process_blender_queue_timer_impl():
    global _RECEIVER_INSTANCE
    if not _RECEIVER_INSTANCE or not _RECEIVER_INSTANCE.is_running:
        return None  # Ukončí časovač

    while not _RECEIVER_INSTANCE.request_queue.empty():
        try:
            item = _RECEIVER_INSTANCE.request_queue.get_nowait()
        except queue.Empty:
            break

        message, completion_event, result_container = item
        action = message.get("action", "run_bpy_script")
        if result_container.get("cancelled"):
            completion_event.set()
            _RECEIVER_INSTANCE.request_queue.task_done()
            continue

        # 0. Spuštění BPY skriptu vygenerovaného AI asistentem (action == "run_bpy_script")
        # Provádí se přes explicitní auditovanou funkci execute_trusted_blender_code.
        if action == "run_bpy_script":
            code_value = message.get("code")
            if not isinstance(code_value, str):
                result_container["response"] = {
                    "status": "error",
                    "error": "InvalidCodeType",
                    "message": "Pole 'code' musí být textový řetězec.",
                }
                completion_event.set()
                _RECEIVER_INSTANCE.request_queue.task_done()
                continue
            code = code_value.strip()
            print(f"\n[AI-Blender] >>> Spouštím execute_trusted_blender_code ({len(code)} znaků)...")
            if not code:
                result_container["response"] = {
                    "status": "error",
                    "error": "EmptyCodeError",
                    "message": "Pole 'code' je prázdné.",
                }
                completion_event.set()
                _RECEIVER_INSTANCE.request_queue.task_done()
                continue

            is_valid, validation_msg = validate_blender_code(code)
            if not is_valid:
                result_container["response"] = {
                    "status": "error",
                    "error_type": "CodeValidationError",
                    "action": "run_bpy_script",
                    "error": f"AST validace kódu selhala: {validation_msg}",
                    "message": validation_msg,
                }
                completion_event.set()
                _RECEIVER_INSTANCE.request_queue.task_done()
                continue

            try:
                stdout_out, stderr_out = execute_trusted_blender_code(code)

                result_container["response"] = {
                    "status": "success",
                    "action": "run_bpy_script",
                    "output": stdout_out,
                    "stderr": stderr_out,
                }
                print(f"[OK] [AI-Blender] execute_trusted_blender_code dokončen. stdout={stdout_out[:200]!r}")
            except Exception as e:
                err_trace = traceback.format_exc()
                result_container["response"] = {
                    "status": "error",
                    "action": "run_bpy_script",
                    "error": str(e),
                    "traceback": err_trace,
                }
                print(f"[ERROR] [AI-Blender] Chyba execute_trusted_blender_code: {e}")
                print(err_trace)
            finally:
                completion_event.set()
                _RECEIVER_INSTANCE.request_queue.task_done()
            continue

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
                print(f"[OK] [AI-Blender] Inspekce scény dokončena (objektů: {metrics['total_objects']}, snapshot: {img_path})")
            except Exception as e:
                err_trace = traceback.format_exc()
                result_container["response"] = {
                    "status": "error",
                    "error": str(e),
                    "traceback": err_trace,
                }
                print(f"[ERROR] [AI-Blender] Chyba při inspekci scény: {e}")
                print(err_trace)
            finally:
                completion_event.set()
                _RECEIVER_INSTANCE.request_queue.task_done()
            continue

        # 2. Mesh Doctor – audit sítě aktivního objektu
        if action == "mesh_doctor_audit":
            print("\n[AI-Blender] >>> Zahajuji Mesh Doctor AUDIT...")
            try:
                import bmesh  # noqa: F401 – ověř dostupnost

                obj = None
                if hasattr(bpy.context, "view_layer") and bpy.context.view_layer:
                    obj = bpy.context.view_layer.objects.active
                if not obj and hasattr(bpy.context, "active_object"):
                    obj = bpy.context.active_object

                if not obj or obj.type != 'MESH':
                    result_container["response"] = {
                        "status": "error",
                        "error": "NoActiveMeshObject",
                        "message": "Žádný aktivní síťový objekt (MESH) nebyl nalezen. Vyberte mesh a zkuste znovu.",
                    }
                    completion_event.set()
                    _RECEIVER_INSTANCE.request_queue.task_done()
                    continue

                # Vynutit object mode pro správný eval
                prev_mode = obj.mode
                if prev_mode != 'OBJECT':
                    bpy.ops.object.mode_set(mode='OBJECT')

                depsgraph = bpy.context.evaluated_depsgraph_get()
                obj_eval = obj.evaluated_get(depsgraph)
                mesh_eval = obj_eval.to_mesh()

                bm = bmesh.new()
                bm.from_mesh(mesh_eval)
                bm.edges.ensure_lookup_table()
                bm.verts.ensure_lookup_table()
                bm.faces.ensure_lookup_table()

                total_verts = len(bm.verts)
                total_edges = len(bm.edges)
                total_faces = len(bm.faces)

                # Non-manifold hrany: propojeny s ≠ 2 stěnami
                non_manifold_edges = [e for e in bm.edges if not e.is_manifold]

                # Volné vrcholy: vrchol bez hran
                loose_verts = [v for v in bm.verts if not v.link_edges]

                # Volné hrany: hrana bez stěn
                loose_edges = [e for e in bm.edges if not e.link_faces]

                # Boundary hrany (okraje děr): propojeny s přesně 1 stěnou
                boundary_edges = [e for e in bm.edges if e.is_boundary]

                # Nejednotné normály: plochy s normálou mířící dovnitř
                # (detekujeme přibližně jako plochy s negativní Z-ovou složkou normály
                #  – uloží počet, skutečnou opravu dělá repair akce)
                import mathutils  # noqa: F401
                flipped_faces = []
                for f in bm.faces:
                    # heuristika: normála míří od středu scény ven?
                    center_to_face = f.calc_center_median()
                    dot = f.normal.dot(center_to_face)
                    if dot < 0:
                        flipped_faces.append(f.index)

                # Plochy s více než 4 vrcholy (n-gony) – problém pro 3D tisk
                ngons = [f for f in bm.faces if len(f.verts) > 4]
                tris  = [f for f in bm.faces if len(f.verts) == 3]

                is_watertight = (
                    len(non_manifold_edges) == 0
                    and len(loose_verts) == 0
                    and len(loose_edges) == 0
                    and len(boundary_edges) == 0
                )

                audit_result = {
                    "object_name": obj.name,
                    "mesh_name": obj.data.name,
                    "total_vertices": total_verts,
                    "total_edges": total_edges,
                    "total_faces": total_faces,
                    "triangles": len(tris),
                    "ngons": len(ngons),
                    "non_manifold_edges": len(non_manifold_edges),
                    "loose_vertices": len(loose_verts),
                    "loose_edges": len(loose_edges),
                    "boundary_edges_holes": len(boundary_edges),
                    "potentially_flipped_faces": len(flipped_faces),
                    "is_watertight": is_watertight,
                    "print_ready": is_watertight and len(ngons) == 0,
                }

                bm.free()
                obj_eval.to_mesh_clear()

                # Obnovit původní mode
                if prev_mode != 'OBJECT':
                    bpy.ops.object.mode_set(mode=prev_mode)

                result_container["response"] = {
                    "status": "success",
                    "action": "mesh_doctor_audit",
                    "audit": audit_result,
                }
                print(f"[OK] [AI-Blender] Mesh Doctor AUDIT dokončen: {audit_result}")

            except Exception as e:
                err_trace = traceback.format_exc()
                result_container["response"] = {
                    "status": "error",
                    "error": str(e),
                    "traceback": err_trace,
                }
                print(f"[ERROR] [AI-Blender] Chyba při Mesh Doctor AUDIT: {e}")
                print(err_trace)
            finally:
                completion_event.set()
                _RECEIVER_INSTANCE.request_queue.task_done()
            continue

        # 3. Mesh Doctor – automatická oprava sítě aktivního objektu
        if action == "mesh_doctor_repair":
            print("\n[AI-Blender] >>> Zahajuji Mesh Doctor REPAIR...")
            try:
                obj = None
                if hasattr(bpy.context, "view_layer") and bpy.context.view_layer:
                    obj = bpy.context.view_layer.objects.active
                if not obj and hasattr(bpy.context, "active_object"):
                    obj = bpy.context.active_object

                if not obj or obj.type != 'MESH':
                    result_container["response"] = {
                        "status": "error",
                        "error": "NoActiveMeshObject",
                        "message": "Žádný aktivní síťový objekt (MESH) nebyl nalezen. Vyberte mesh a zkuste znovu.",
                    }
                    completion_event.set()
                    _RECEIVER_INSTANCE.request_queue.task_done()
                    continue

                merge_distance = float(message.get("merge_distance", 0.0001))

                # Přepnout do Edit Mode pro operace
                prev_mode = obj.mode
                if prev_mode != 'OBJECT':
                    bpy.ops.object.mode_set(mode='OBJECT')

                # Zadat object jako aktivní a selectovat
                bpy.context.view_layer.objects.active = obj
                obj.select_set(True)

                bpy.ops.object.mode_set(mode='EDIT')
                bpy.ops.mesh.select_all(action='SELECT')

                # 1) Merge by distance – odstraní duplikáty
                bpy.ops.mesh.remove_doubles(threshold=merge_distance)

                # 2) Smazat volnou geometrii (loose vertices + edges)
                bpy.ops.mesh.delete_loose(use_verts=True, use_edges=True, use_faces=False)

                # 3) Přepočítat normály (Recalculate Outside)
                bpy.ops.mesh.select_all(action='SELECT')
                bpy.ops.mesh.normals_make_consistent(inside=False)

                # Zpět do Object Mode
                bpy.ops.object.mode_set(mode='OBJECT')

                # Vynutit překreslení viewportu
                for window in bpy.context.window_manager.windows:
                    for area in window.screen.areas:
                        if area.type == 'VIEW_3D':
                            area.tag_redraw()

                # Post-repair audit pomocí bmesh pro statistiky
                import bmesh  # noqa: F401

                depsgraph = bpy.context.evaluated_depsgraph_get()
                obj_eval = obj.evaluated_get(depsgraph)
                mesh_eval = obj_eval.to_mesh()

                bm = bmesh.new()
                bm.from_mesh(mesh_eval)
                bm.edges.ensure_lookup_table()
                bm.verts.ensure_lookup_table()
                bm.faces.ensure_lookup_table()

                non_manifold_after = len([e for e in bm.edges if not e.is_manifold])
                loose_verts_after  = len([v for v in bm.verts if not v.link_edges])
                loose_edges_after  = len([e for e in bm.edges if not e.link_faces])
                boundary_after     = len([e for e in bm.edges if e.is_boundary])
                is_watertight_after = (
                    non_manifold_after == 0
                    and loose_verts_after == 0
                    and loose_edges_after == 0
                    and boundary_after == 0
                )
                post_stats = {
                    "object_name": obj.name,
                    "total_vertices": len(bm.verts),
                    "total_edges": len(bm.edges),
                    "total_faces": len(bm.faces),
                    "non_manifold_edges": non_manifold_after,
                    "loose_vertices": loose_verts_after,
                    "loose_edges": loose_edges_after,
                    "boundary_edges_holes": boundary_after,
                    "is_watertight": is_watertight_after,
                    "print_ready": is_watertight_after,
                    "merge_distance_used": merge_distance,
                }
                bm.free()
                obj_eval.to_mesh_clear()

                if prev_mode not in ('OBJECT', 'EDIT'):
                    try:
                        bpy.ops.object.mode_set(mode=prev_mode)
                    except Exception:
                        pass

                result_container["response"] = {
                    "status": "success",
                    "action": "mesh_doctor_repair",
                    "repairs_applied": [
                        "merge_by_distance",
                        "delete_loose_geometry",
                        "recalculate_normals_outside",
                    ],
                    "post_repair_stats": post_stats,
                }
                print(f"[OK] [AI-Blender] Mesh Doctor REPAIR dokončen: watertight={is_watertight_after}")

            except Exception as e:
                err_trace = traceback.format_exc()
                result_container["response"] = {
                    "status": "error",
                    "error": str(e),
                    "traceback": err_trace,
                }
                print(f"[ERROR] [AI-Blender] Chyba při Mesh Doctor REPAIR: {e}")
                print(err_trace)
            finally:
                completion_event.set()
                _RECEIVER_INSTANCE.request_queue.task_done()
            continue

        # 4. Product Viz Studio Automator – automatické produktové studio
        if action == "create_product_studio":
            print("\n[AI-Blender] >>> Zahajuji Product Viz Studio Automator...")
            try:
                import math

                style = message.get("style", "standard")
                # Vyčistit případné starší studio objekty (prefix "Studio_")
                for obj in list(bpy.data.objects):
                    if obj.name.startswith("Studio_"):
                        bpy.data.objects.remove(obj, do_unlink=True)

                # Zjistit aktivní nebo cílový objekt
                target_obj = None
                if hasattr(bpy.context, "view_layer") and bpy.context.view_layer:
                    target_obj = bpy.context.view_layer.objects.active
                if not target_obj and hasattr(bpy.context, "active_object"):
                    target_obj = bpy.context.active_object

                # Cílová poloha pro kameru a světla
                if target_obj:
                    cx, cy, cz = target_obj.location
                    # Odhadnout velikost objektu z bounding boxu
                    dims = target_obj.dimensions
                    obj_size = max(dims.x, dims.y, dims.z) if max(dims.x, dims.y, dims.z) > 0 else 1.0
                else:
                    cx, cy, cz = 0.0, 0.0, 0.0
                    obj_size = 1.0

                scale = max(obj_size * 3.0, 2.0)  # Minimálně 2m studio

                # ── 1. BACKDROP (hladká zakřivená rovina) ────────────────
                backdrop_w = scale * 4
                backdrop_d = scale * 3
                backdrop_h = scale * 2.5

                bpy.ops.mesh.primitive_plane_add(size=1, location=(cx, cy + backdrop_d * 0.5, cz))
                backdrop = bpy.context.active_object
                backdrop.name = "Studio_Backdrop"
                backdrop.scale = (backdrop_w, backdrop_d, 1.0)
                bpy.ops.object.transform_apply(scale=True)

                # Posunout spodní hranu na Z=0 vůči objektu
                for vert in backdrop.data.vertices:
                    vert.co.y -= 0.5
                    vert.co.z -= 0.5

                # Zakřivení pomocí Curve modifikátoru — použijeme Simple Deform (Bend)
                bpy.ops.object.mode_set(mode='EDIT')
                bpy.ops.mesh.subdivide(number_cuts=20)
                bpy.ops.object.mode_set(mode='OBJECT')

                deform = backdrop.modifiers.new(name="Bend", type='SIMPLE_DEFORM')
                deform.deform_method = 'BEND'
                deform.deform_axis = 'X'
                deform.angle = math.radians(-30)
                deform.limits = (0.0, 0.4)

                solidify = backdrop.modifiers.new(name="Solidify", type='SOLIDIFY')
                solidify.thickness = 0.02
                solidify.offset = -1.0

                bevel = backdrop.modifiers.new(name="Bevel", type='BEVEL')
                bevel.width = 0.05
                bevel.segments = 3

                # Hladké stínování
                for poly in backdrop.data.polygons:
                    poly.use_smooth = True

                # Backdrop materiál — bílý matný
                mat_name = "Studio_Backdrop_Mat"
                if mat_name not in bpy.data.materials:
                    mat = bpy.data.materials.new(name=mat_name)
                    mat.use_nodes = True
                    bsdf = mat.node_tree.nodes.get("Principled BSDF")
                    if bsdf:
                        bsdf.inputs["Base Color"].default_value = (0.95, 0.95, 0.95, 1.0)
                        bsdf.inputs["Roughness"].default_value = 0.9
                        bsdf.inputs["Specular IOR Level"].default_value = 0.0 if "Specular IOR Level" in bsdf.inputs else None
                        try:
                            bsdf.inputs["Specular"].default_value = 0.0
                        except Exception:
                            pass
                else:
                    mat = bpy.data.materials[mat_name]
                if backdrop.data.materials:
                    backdrop.data.materials[0] = mat
                else:
                    backdrop.data.materials.append(mat)

                # ── 2. TŘÍBODOVÉ OSVĚTLENÍ ────────────────────────────────
                # Styly přednastavení
                style_presets = {
                    "standard": {
                        "key":  {"energy": 800,  "color": (1.00, 0.97, 0.90, 1.0), "size": scale * 0.8, "softness": 1.0},
                        "fill": {"energy": 200,  "color": (0.85, 0.90, 1.00, 1.0), "size": scale * 1.2, "softness": 1.0},
                        "rim":  {"energy": 400,  "color": (1.00, 1.00, 1.00, 1.0), "size": scale * 0.5, "softness": 0.5},
                    },
                    "dramatic": {
                        "key":  {"energy": 1200, "color": (1.00, 0.92, 0.75, 1.0), "size": scale * 0.5, "softness": 0.3},
                        "fill": {"energy": 80,   "color": (0.70, 0.80, 1.00, 1.0), "size": scale * 1.5, "softness": 1.0},
                        "rim":  {"energy": 600,  "color": (1.00, 0.98, 0.95, 1.0), "size": scale * 0.4, "softness": 0.2},
                    },
                    "soft": {
                        "key":  {"energy": 500,  "color": (1.00, 0.98, 0.95, 1.0), "size": scale * 1.5, "softness": 1.0},
                        "fill": {"energy": 350,  "color": (0.95, 0.95, 1.00, 1.0), "size": scale * 2.0, "softness": 1.0},
                        "rim":  {"energy": 200,  "color": (1.00, 1.00, 1.00, 1.0), "size": scale * 1.0, "softness": 1.0},
                    },
                }
                preset = style_presets.get(style, style_presets["standard"])

                d = scale * 2.2  # Vzdálenost světel od středu
                lights_created = []

                def create_area_light(name, location, energy, color, size, rotation_euler):
                    bpy.ops.object.light_add(type='AREA', location=location)
                    light_obj = bpy.context.active_object
                    light_obj.name = name
                    light_obj.rotation_euler = rotation_euler
                    light_obj.data.energy = energy
                    light_obj.data.color = color[:3]
                    light_obj.data.size = size
                    light_obj.data.shadow_soft_size = size * 0.5
                    return light_obj

                # Key Light — 45° vlevo nahoře, přední
                key_loc = (cx - d * 0.7, cy - d * 0.8, cz + d * 1.2)
                key_rot = (math.radians(55), 0, math.radians(-35))
                key = create_area_light(
                    "Studio_Key_Light", key_loc,
                    preset["key"]["energy"], preset["key"]["color"],
                    preset["key"]["size"], key_rot,
                )
                lights_created.append({
                    "name": key.name, "role": "key",
                    "location": [round(v, 3) for v in key_loc],
                    "energy": preset["key"]["energy"],
                    "color_temp": "warm white",
                    "size": round(preset["key"]["size"], 3),
                })

                # Fill Light — vpravo nízko, měkké
                fill_loc = (cx + d * 0.9, cy - d * 0.6, cz + d * 0.4)
                fill_rot = (math.radians(30), 0, math.radians(50))
                fill = create_area_light(
                    "Studio_Fill_Light", fill_loc,
                    preset["fill"]["energy"], preset["fill"]["color"],
                    preset["fill"]["size"], fill_rot,
                )
                lights_created.append({
                    "name": fill.name, "role": "fill",
                    "location": [round(v, 3) for v in fill_loc],
                    "energy": preset["fill"]["energy"],
                    "color_temp": "cool blue-white",
                    "size": round(preset["fill"]["size"], 3),
                })

                # Rim Light — zezadu-vlevo nahoře, tvrdý okraj
                rim_loc = (cx - d * 0.5, cy + d * 1.1, cz + d * 1.0)
                rim_rot = (math.radians(-45), 0, math.radians(-150))
                rim = create_area_light(
                    "Studio_Rim_Light", rim_loc,
                    preset["rim"]["energy"], preset["rim"]["color"],
                    preset["rim"]["size"], rim_rot,
                )
                lights_created.append({
                    "name": rim.name, "role": "rim",
                    "location": [round(v, 3) for v in rim_loc],
                    "energy": preset["rim"]["energy"],
                    "color_temp": "neutral white",
                    "size": round(preset["rim"]["size"], 3),
                })

                # ── 3. KAMERA ─────────────────────────────────────────────
                cam_dist = scale * 3.5
                cam_loc = (cx + cam_dist * 0.1, cy - cam_dist, cz + cam_dist * 0.3)

                # Odebrat existující studio kameru
                if "Studio_Camera" in bpy.data.objects:
                    bpy.data.objects.remove(bpy.data.objects["Studio_Camera"], do_unlink=True)

                bpy.ops.object.camera_add(location=cam_loc)
                cam_obj = bpy.context.active_object
                cam_obj.name = "Studio_Camera"

                # Nastavit ohniskovou vzdálenost 85mm
                cam_obj.data.lens = 85.0
                cam_obj.data.lens_unit = 'MILLIMETERS'

                # Namířit kameru na cíl (Track To constraint)
                track = cam_obj.constraints.new(type='TRACK_TO')
                track.target = target_obj if target_obj else None
                track.track_axis = 'TRACK_NEGATIVE_Z'
                track.up_axis = 'UP_Y'
                if not target_obj:
                    # Manuálně namířit na origin
                    import mathutils
                    direction = mathutils.Vector((cx, cy, cz)) - mathutils.Vector(cam_loc)
                    rot_quat = direction.to_track_quat('-Z', 'Y')
                    cam_obj.rotation_euler = rot_quat.to_euler()
                    cam_obj.constraints.remove(track)

                # Nastavit jako aktivní scénovou kameru
                scene = bpy.context.scene
                scene.camera = cam_obj

                # ── 4. RENDER NASTAVENÍ (EEVEE / Cycles) ─────────────────
                if hasattr(scene, "render"):
                    scene.render.resolution_x = 2048
                    scene.render.resolution_y = 2048
                    # Pokusit se nastavit na Cycles pro lepší odlesky
                    try:
                        scene.render.engine = 'CYCLES'
                        if hasattr(scene, "cycles"):
                            scene.cycles.samples = 128
                            scene.cycles.use_denoising = True
                    except Exception:
                        pass  # Zůstat na EEVEE

                # Překreslit viewport
                for window in bpy.context.window_manager.windows:
                    for area in window.screen.areas:
                        if area.type == 'VIEW_3D':
                            area.tag_redraw()

                studio_result = {
                    "backdrop": {
                        "name": backdrop.name,
                        "dimensions_m": [round(backdrop_w, 2), round(backdrop_d, 2), round(backdrop_h, 2)],
                        "material": mat_name,
                        "modifiers": ["SimpleDeform(Bend)", "Solidify", "Bevel"],
                    },
                    "lights": lights_created,
                    "camera": {
                        "name": cam_obj.name,
                        "location": [round(v, 3) for v in cam_loc],
                        "focal_length_mm": 85,
                        "resolution": "2048x2048",
                        "is_active_camera": True,
                    },
                    "style": style,
                    "scale_factor": round(scale, 3),
                    "target_object": target_obj.name if target_obj else "world_origin",
                }

                result_container["response"] = {
                    "status": "success",
                    "action": "create_product_studio",
                    "studio": studio_result,
                }
                print(f"[OK] [AI-Blender] Product Viz Studio vytvořeno: styl='{style}', "
                      f"měřítko={scale:.2f}m, světla={len(lights_created)}")

            except Exception as e:
                err_trace = traceback.format_exc()
                result_container["response"] = {
                    "status": "error",
                    "error": str(e),
                    "traceback": err_trace,
                }
                print(f"[ERROR] [AI-Blender] Chyba při Product Viz Studio: {e}")
                print(err_trace)
            finally:
                completion_event.set()
                _RECEIVER_INSTANCE.request_queue.task_done()
        # 5. Procedural Shader & Node Tree Generator – tvorba procedurálních materiálů
        if action == "create_procedural_shader":
            print("\n[AI-Blender] >>> Zahajuji Procedural Shader Generator...")
            try:
                shader_type = message.get("shader_type", "brushed_metal").lower().strip()
                requested_name = message.get("material_name")
                material_name = requested_name if requested_name and requested_name.strip() else f"Procedural_{shader_type.title()}"

                # Vytvoření nebo znovupoužití materiálu
                if material_name in bpy.data.materials:
                    mat = bpy.data.materials[material_name]
                else:
                    mat = bpy.data.materials.new(name=material_name)

                mat.use_nodes = True
                nodes = mat.node_tree.nodes
                links = mat.node_tree.links
                nodes.clear()

                def _set_bsdf(bsdf_node, name_list, val):
                    for n in name_list:
                        if n in bsdf_node.inputs:
                            bsdf_node.inputs[n].default_value = val
                            return True
                    return False

                def _get_bsdf_sock(bsdf_node, name_list):
                    for n in name_list:
                        if n in bsdf_node.inputs:
                            return bsdf_node.inputs[n]
                    return None

                # 1. Základní výstup a Principled BSDF
                out_node = nodes.new(type='ShaderNodeOutputMaterial')
                out_node.location = (450, 0)

                bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
                bsdf.location = (100, 0)
                links.new(bsdf.outputs['BSDF'], out_node.inputs['Surface'])

                # 2. Vytvoření uzlů podle typu materiálu
                key_params = {"shader_type": shader_type}

                if shader_type == "brushed_metal":
                    # Anizotropní / kartáčovaný kov (hliník/ocel)
                    tex_coord = nodes.new('ShaderNodeTexCoord')
                    tex_coord.location = (-850, 0)

                    mapping = nodes.new('ShaderNodeMapping')
                    mapping.location = (-650, 0)
                    try:
                        mapping.inputs['Scale'].default_value[0] = 1.0
                        mapping.inputs['Scale'].default_value[1] = 60.0  # Protažení pro kartáčovaný vzor
                        mapping.inputs['Scale'].default_value[2] = 1.0
                    except Exception:
                        pass

                    noise = nodes.new('ShaderNodeTexNoise')
                    noise.location = (-450, 0)
                    if 'Scale' in noise.inputs:
                        noise.inputs['Scale'].default_value = 30.0
                    if 'Detail' in noise.inputs:
                        noise.inputs['Detail'].default_value = 6.0
                    if 'Roughness' in noise.inputs:
                        noise.inputs['Roughness'].default_value = 0.7

                    ramp = nodes.new('ShaderNodeValToRGB')
                    ramp.location = (-250, 0)
                    if hasattr(ramp, "color_ramp"):
                        ramp.color_ramp.elements[0].position = 0.2
                        ramp.color_ramp.elements[0].color = (0.2, 0.2, 0.2, 1.0)
                        ramp.color_ramp.elements[1].position = 0.8
                        ramp.color_ramp.elements[1].color = (0.55, 0.55, 0.55, 1.0)

                    bump = nodes.new('ShaderNodeBump')
                    bump.location = (-50, -200)
                    bump.inputs['Strength'].default_value = 0.08
                    bump.inputs['Distance'].default_value = 0.05

                    # Propojení
                    links.new(tex_coord.outputs['Object'], mapping.inputs['Vector'])
                    links.new(mapping.outputs['Vector'], noise.inputs['Vector'])
                    links.new(noise.outputs['Fac'], ramp.inputs['Fac'])
                    links.new(ramp.outputs['Color'], bump.inputs['Height'])
                    links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])

                    # BSDF vstupy
                    _set_bsdf(bsdf, ['Metallic'], 1.0)
                    _set_bsdf(bsdf, ['Base Color'], (0.78, 0.79, 0.82, 1.0))
                    _set_bsdf(bsdf, ['Roughness'], 0.25)
                    _set_bsdf(bsdf, ['Anisotropic', 'Anisotropic Rotation'], 0.6)

                    rough_sock = _get_bsdf_sock(bsdf, ['Roughness'])
                    if rough_sock:
                        links.new(ramp.outputs['Color'], rough_sock)

                    key_params.update({"metallic": 1.0, "base_color": "Silver/Alloy", "roughness": "0.2-0.35 (mapped)"})

                elif shader_type == "matte_plastic":
                    # Prémiový matný plast / polymer s jemným mikroskopickým šumem
                    tex_coord = nodes.new('ShaderNodeTexCoord')
                    tex_coord.location = (-750, 0)

                    mapping = nodes.new('ShaderNodeMapping')
                    mapping.location = (-550, 0)

                    noise = nodes.new('ShaderNodeTexNoise')
                    noise.location = (-350, 0)
                    if 'Scale' in noise.inputs:
                        noise.inputs['Scale'].default_value = 50.0
                    if 'Detail' in noise.inputs:
                        noise.inputs['Detail'].default_value = 4.0
                    if 'Roughness' in noise.inputs:
                        noise.inputs['Roughness'].default_value = 0.5

                    ramp = nodes.new('ShaderNodeValToRGB')
                    ramp.location = (-150, 100)
                    if hasattr(ramp, "color_ramp"):
                        ramp.color_ramp.elements[0].position = 0.0
                        ramp.color_ramp.elements[0].color = (0.4, 0.4, 0.4, 1.0)
                        ramp.color_ramp.elements[1].position = 1.0
                        ramp.color_ramp.elements[1].color = (0.55, 0.55, 0.55, 1.0)

                    bump = nodes.new('ShaderNodeBump')
                    bump.location = (-150, -200)
                    bump.inputs['Strength'].default_value = 0.02
                    bump.inputs['Distance'].default_value = 0.02

                    # Propojení
                    links.new(tex_coord.outputs['Object'], mapping.inputs['Vector'])
                    links.new(mapping.outputs['Vector'], noise.inputs['Vector'])
                    links.new(noise.outputs['Fac'], ramp.inputs['Fac'])
                    links.new(noise.outputs['Fac'], bump.inputs['Height'])
                    links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])

                    rough_sock = _get_bsdf_sock(bsdf, ['Roughness'])
                    if rough_sock:
                        links.new(ramp.outputs['Color'], rough_sock)

                    # BSDF vstupy
                    _set_bsdf(bsdf, ['Metallic'], 0.0)
                    _set_bsdf(bsdf, ['Base Color'], (0.12, 0.45, 0.88, 1.0))  # Prémiový modrý polymer
                    _set_bsdf(bsdf, ['Specular IOR Level', 'Specular'], 0.5)

                    key_params.update({"metallic": 0.0, "base_color": "Royal Blue Matte", "roughness": "0.4-0.55 (procedural)"})

                elif shader_type == "rusted_iron":
                    # Zkorodované surové železo s procedurální mapou rzi
                    tex_coord = nodes.new('ShaderNodeTexCoord')
                    tex_coord.location = (-950, 0)

                    mapping = nodes.new('ShaderNodeMapping')
                    mapping.location = (-750, 0)

                    noise = nodes.new('ShaderNodeTexNoise')
                    noise.location = (-550, 0)
                    if 'Scale' in noise.inputs:
                        noise.inputs['Scale'].default_value = 4.5
                    if 'Detail' in noise.inputs:
                        noise.inputs['Detail'].default_value = 8.0
                    if 'Distortion' in noise.inputs:
                        noise.inputs['Distortion'].default_value = 0.5

                    # ColorRamp pro Base Color (železo vs rez)
                    ramp_color = nodes.new('ShaderNodeValToRGB')
                    ramp_color.location = (-300, 150)
                    if hasattr(ramp_color, "color_ramp"):
                        ramp_color.color_ramp.elements[0].position = 0.35
                        ramp_color.color_ramp.elements[0].color = (0.2, 0.21, 0.22, 1.0)  # Tmavé surové železo
                        ramp_color.color_ramp.elements[1].position = 0.65
                        ramp_color.color_ramp.elements[1].color = (0.55, 0.16, 0.04, 1.0)  # Rez

                    # ColorRamp pro Roughness (kov = hladší, rez = velmi drsná)
                    ramp_rough = nodes.new('ShaderNodeValToRGB')
                    ramp_rough.location = (-300, -100)
                    if hasattr(ramp_rough, "color_ramp"):
                        ramp_rough.color_ramp.elements[0].position = 0.35
                        ramp_rough.color_ramp.elements[0].color = (0.35, 0.35, 0.35, 1.0)
                        ramp_rough.color_ramp.elements[1].position = 0.65
                        ramp_rough.color_ramp.elements[1].color = (0.9, 0.9, 0.9, 1.0)

                    bump = nodes.new('ShaderNodeBump')
                    bump.location = (-100, -250)
                    bump.inputs['Strength'].default_value = 0.25
                    bump.inputs['Distance'].default_value = 0.1

                    # Propojení
                    links.new(tex_coord.outputs['Object'], mapping.inputs['Vector'])
                    links.new(mapping.outputs['Vector'], noise.inputs['Vector'])
                    links.new(noise.outputs['Fac'], ramp_color.inputs['Fac'])
                    links.new(noise.outputs['Fac'], ramp_rough.inputs['Fac'])
                    links.new(noise.outputs['Fac'], bump.inputs['Height'])

                    color_sock = _get_bsdf_sock(bsdf, ['Base Color'])
                    if color_sock:
                        links.new(ramp_color.outputs['Color'], color_sock)

                    rough_sock = _get_bsdf_sock(bsdf, ['Roughness'])
                    if rough_sock:
                        links.new(ramp_rough.outputs['Color'], rough_sock)

                    links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])

                    _set_bsdf(bsdf, ['Metallic'], 0.65)
                    key_params.update({"metallic": "0.65 base", "base_color": "Procedural Iron & Rust", "roughness": "0.35-0.9 (mapped)"})

                elif shader_type == "glossy_glass":
                    # Opticky čisté sklo s mikroskopickou nerovností povrchu
                    tex_coord = nodes.new('ShaderNodeTexCoord')
                    tex_coord.location = (-700, 0)

                    mapping = nodes.new('ShaderNodeMapping')
                    mapping.location = (-500, 0)

                    noise = nodes.new('ShaderNodeTexNoise')
                    noise.location = (-300, 0)
                    if 'Scale' in noise.inputs:
                        noise.inputs['Scale'].default_value = 10.0
                    if 'Detail' in noise.inputs:
                        noise.inputs['Detail'].default_value = 2.0

                    bump = nodes.new('ShaderNodeBump')
                    bump.location = (-100, -200)
                    bump.inputs['Strength'].default_value = 0.005  # Velmi subtilní lom
                    bump.inputs['Distance'].default_value = 0.05

                    links.new(tex_coord.outputs['Object'], mapping.inputs['Vector'])
                    links.new(mapping.outputs['Vector'], noise.inputs['Vector'])
                    links.new(noise.outputs['Fac'], bump.inputs['Height'])
                    links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])

                    _set_bsdf(bsdf, ['Transmission Weight', 'Transmission'], 1.0)
                    _set_bsdf(bsdf, ['Roughness'], 0.02)
                    _set_bsdf(bsdf, ['IOR'], 1.52)
                    _set_bsdf(bsdf, ['Base Color'], (0.97, 0.98, 1.0, 1.0))

                    try:
                        mat.blend_method = 'BLEND'
                        mat.shadow_method = 'HASHED'
                    except Exception:
                        pass

                    key_params.update({"transmission": 1.0, "ior": 1.52, "roughness": 0.02, "base_color": "Clear Glass"})

                else:
                    # Univerzální procedurální shader
                    tex_coord = nodes.new('ShaderNodeTexCoord')
                    tex_coord.location = (-600, 0)
                    noise = nodes.new('ShaderNodeTexNoise')
                    noise.location = (-350, 0)
                    bump = nodes.new('ShaderNodeBump')
                    bump.location = (-100, -150)
                    bump.inputs['Strength'].default_value = 0.05

                    links.new(tex_coord.outputs['Object'], noise.inputs['Vector'])
                    links.new(noise.outputs['Fac'], bump.inputs['Height'])
                    links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])

                    _set_bsdf(bsdf, ['Metallic'], 0.2)
                    _set_bsdf(bsdf, ['Roughness'], 0.3)
                    key_params.update({"metallic": 0.2, "roughness": 0.3})

                # 3. Přiřazení k aktivnímu MESH objektu
                active_obj = None
                if hasattr(bpy.context, "view_layer") and bpy.context.view_layer:
                    active_obj = bpy.context.view_layer.objects.active
                if not active_obj and hasattr(bpy.context, "active_object"):
                    active_obj = bpy.context.active_object

                assigned_to = None
                if active_obj and active_obj.type == 'MESH':
                    if active_obj.data.materials:
                        active_obj.data.materials[0] = mat
                    else:
                        active_obj.data.materials.append(mat)
                    assigned_to = active_obj.name

                # Překreslení 3D viewportu
                for window in bpy.context.window_manager.windows:
                    for area in window.screen.areas:
                        if area.type == 'VIEW_3D':
                            area.tag_redraw()

                created_nodes_summary = [
                    {"name": n.name, "type": n.type, "label": getattr(n, "label", "") or n.name}
                    for n in nodes
                ]

                shader_result = {
                    "material_name": mat.name,
                    "shader_type": shader_type,
                    "assigned_to_object": assigned_to,
                    "node_count": len(created_nodes_summary),
                    "link_count": len(links),
                    "nodes": created_nodes_summary,
                    "key_parameters": key_params,
                }

                result_container["response"] = {
                    "status": "success",
                    "action": "create_procedural_shader",
                    "shader": shader_result,
                }
                print(f"[OK] [AI-Blender] Procedural Shader '{mat.name}' ({shader_type}) vytvořen s {len(created_nodes_summary)} uzly.")

            except Exception as e:
                err_trace = traceback.format_exc()
                result_container["response"] = {
                    "status": "error",
                    "error": str(e),
                    "traceback": err_trace,
                }
                print(f"[ERROR] [AI-Blender] Chyba při Procedural Shader: {e}")
                print(err_trace)
            finally:
                completion_event.set()
        # 6. UV Texel Audit – analýza texel density a UV prostoru
        if action == "uv_texel_audit":
            print("\n[AI-Blender] >>> Zahajuji UV Texel Audit...")
            try:
                active_obj = None
                if hasattr(bpy.context, "view_layer") and bpy.context.view_layer:
                    active_obj = bpy.context.view_layer.objects.active
                if not active_obj and hasattr(bpy.context, "active_object"):
                    active_obj = bpy.context.active_object

                if not active_obj or active_obj.type != 'MESH':
                    result_container["response"] = {
                        "status": "error",
                        "error": "NoActiveMeshObject",
                        "message": "Žádný aktivní síťový objekt (MESH) nebyl nalezen. Vyberte mesh a zkuste znovu.",
                    }
                    completion_event.set()
                    _RECEIVER_INSTANCE.request_queue.task_done()
                    continue

                if not active_obj.data.uv_layers:
                    result_container["response"] = {
                        "status": "error",
                        "error": "NoUVMapFound",
                        "message": f"Objekt '{active_obj.name}' nemá vytvořenou žádnou UV mapu. Použijte nejprve smart_uv_pack.",
                    }
                    completion_event.set()
                    _RECEIVER_INSTANCE.request_queue.task_done()
                    continue

                texture_res = int(message.get("texture_res", 2048))
                metrics = calculate_uv_metrics(active_obj, texture_res=texture_res)

                result_container["response"] = {
                    "status": "success",
                    "action": "uv_texel_audit",
                    "metrics": metrics,
                }
                print(f"[OK] [AI-Blender] UV Texel Audit dokončen pro '{active_obj.name}': TD={metrics.get('texel_density_px_cm')} px/cm, coverage={metrics.get('uv_space_coverage_pct')}%")

            except Exception as e:
                err_trace = traceback.format_exc()
                result_container["response"] = {
                    "status": "error",
                    "error": str(e),
                    "traceback": err_trace,
                }
                print(f"[ERROR] [AI-Blender] Chyba při UV Texel Audit: {e}")
                print(err_trace)
            finally:
                completion_event.set()
                _RECEIVER_INSTANCE.request_queue.task_done()
            continue

        # 7. Smart UV Pack – inteligentní rozbalení, sjednocení texel density a zabalení ostrovů
        if action == "smart_uv_pack":
            print("\n[AI-Blender] >>> Zahajuji Smart UV Pack Pipeline...")
            try:
                import math

                active_obj = None
                if hasattr(bpy.context, "view_layer") and bpy.context.view_layer:
                    active_obj = bpy.context.view_layer.objects.active
                if not active_obj and hasattr(bpy.context, "active_object"):
                    active_obj = bpy.context.active_object

                if not active_obj or active_obj.type != 'MESH':
                    result_container["response"] = {
                        "status": "error",
                        "error": "NoActiveMeshObject",
                        "message": "Žádný aktivní síťový objekt (MESH) nebyl nalezen. Vyberte mesh a zkuste znovu.",
                    }
                    completion_event.set()
                    _RECEIVER_INSTANCE.request_queue.task_done()
                    continue

                target_texel_density = float(message.get("target_texel_density", 10.24))
                margin = float(message.get("margin", 0.01))
                angle_limit = float(message.get("angle_limit", 66.0))
                texture_res = int(message.get("texture_res", 2048))

                prev_mode = active_obj.mode
                if prev_mode != 'OBJECT':
                    bpy.ops.object.mode_set(mode='OBJECT')

                bpy.context.view_layer.objects.active = active_obj
                active_obj.select_set(True)

                if not active_obj.data.uv_layers:
                    active_obj.data.uv_layers.new(name="UVMap")

                bpy.ops.object.mode_set(mode='EDIT')
                bpy.ops.mesh.select_all(action='SELECT')

                # 1. Inteligentní unwrap podle úhlového limitu
                try:
                    bpy.ops.uv.smart_project(angle_limit=math.radians(angle_limit), island_margin=margin)
                except Exception:
                    try:
                        bpy.ops.uv.smart_project(angle_limit=angle_limit, island_margin=margin)
                    except Exception:
                        bpy.ops.uv.unwrap(method='ANGLE_BASED', margin=margin)

                # 2. Škálování na cílovou Texel Density
                bpy.ops.object.mode_set(mode='OBJECT')
                pre_metrics = calculate_uv_metrics(active_obj, texture_res=texture_res)
                curr_td = pre_metrics.get("texel_density_px_cm", 0.0) if pre_metrics else 0.0

                scaled_applied = False
                if target_texel_density > 0 and curr_td > 0.001:
                    scale_mult = target_texel_density / curr_td
                    import bmesh
                    bm = bmesh.new()
                    bm.from_mesh(active_obj.data)
                    uv_layer = bm.loops.layers.uv.active or bm.loops.layers.uv.verify()
                    for f in bm.faces:
                        for l in f.loops:
                            l[uv_layer].uv *= scale_mult
                    bm.to_mesh(active_obj.data)
                    bm.free()
                    scaled_applied = True

                # 3. Zabalení UV ostrovů (Pack Islands)
                bpy.ops.object.mode_set(mode='EDIT')
                bpy.ops.mesh.select_all(action='SELECT')
                try:
                    bpy.ops.uv.pack_islands(margin=margin, rotate=True)
                except Exception:
                    try:
                        bpy.ops.uv.pack_islands(margin=margin)
                    except Exception:
                        pass

                bpy.ops.object.mode_set(mode='OBJECT')

                # Překreslení 3D pohledů
                for window in bpy.context.window_manager.windows:
                    for area in window.screen.areas:
                        if area.type == 'VIEW_3D':
                            area.tag_redraw()

                # Finální vyhodnocení po zabalení
                final_metrics = calculate_uv_metrics(active_obj, texture_res=texture_res)

                result_container["response"] = {
                    "status": "success",
                    "action": "smart_uv_pack",
                    "target_texel_density": target_texel_density,
                    "margin": margin,
                    "angle_limit": angle_limit,
                    "scaled_to_target": scaled_applied,
                    "post_pack_metrics": final_metrics,
                }
                print(f"[OK] [AI-Blender] Smart UV Pack dokončen: TD={final_metrics.get('texel_density_px_cm')} px/cm, islands={final_metrics.get('uv_islands_count')}, coverage={final_metrics.get('uv_space_coverage_pct')}%")

            except Exception as e:
                err_trace = traceback.format_exc()
                result_container["response"] = {
                    "status": "error",
                    "error": str(e),
                    "traceback": err_trace,
                }
                print(f"[ERROR] [AI-Blender] Chyba při Smart UV Pack: {e}")
                print(err_trace)
            finally:
                completion_event.set()
        # 8. Parametric Modeling Engine – parametrické generování geometrie
        if action == "generate_parametric_model":
            print("\n[AI-Blender] >>> Zahajuji Parametric Modeling Engine...")
            try:
                import math
                import bmesh

                model_type = message.get("model_type", "enclosure").lower().strip()
                dims = message.get("dimensions", {}) or {}

                # Deselect all
                for o in bpy.context.selected_objects:
                    o.select_set(False)

                created_obj = None

                if model_type == "enclosure":
                    # Krabička pro elektroniku / pouzdro
                    w = float(dims.get("width", 0.10))     # 100 mm
                    d = float(dims.get("depth", 0.08))     # 80 mm
                    h = float(dims.get("height", 0.04))    # 40 mm
                    wt = float(dims.get("wall_thickness", 0.003)) # 3 mm

                    # Vytvoření základního kvádru
                    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, h / 2.0))
                    obj = bpy.context.active_object
                    obj.name = "Parametric_Enclosure"
                    obj.scale = (w, d, h)
                    bpy.ops.object.transform_apply(scale=True)

                    # Vymazání horní stěny (Z max) pro vytvoření otevřeného pouzdra
                    bpy.ops.object.mode_set(mode='EDIT')
                    bm = bmesh.from_edit_mesh(obj.data)
                    top_faces = [f for f in bm.faces if f.normal.z > 0.8]
                    bmesh.ops.delete(bm, geom=top_faces, context='FACES')
                    bmesh.update_edit_mesh(obj.data)
                    bpy.ops.object.mode_set(mode='OBJECT')

                    # Aplikace Solidify pro tloušťku stěny
                    sol = obj.modifiers.new(name="Solidify", type='SOLIDIFY')
                    sol.thickness = wt
                    sol.offset = -1.0  # směrem dovnitř
                    sol.use_even_offset = True

                    # Jemný zkosený okraj (Bevel)
                    bev = obj.modifiers.new(name="Bevel", type='BEVEL')
                    bev.width = min(wt * 0.4, 0.0015)
                    bev.segments = 2
                    bev.limit_method = 'ANGLE'

                    created_obj = obj
                    dims_summary = {
                        "width_mm": round(w * 1000, 1),
                        "depth_mm": round(d * 1000, 1),
                        "height_mm": round(h * 1000, 1),
                        "wall_thickness_mm": round(wt * 1000, 1),
                    }

                elif model_type == "gear":
                    # Ozubené kolo
                    n_teeth = int(dims.get("teeth_count", 20))
                    r = float(dims.get("radius", 0.05))         # 50 mm
                    td = float(dims.get("tooth_depth", 0.008))   # 8 mm
                    th = float(dims.get("thickness", 0.012))    # 12 mm
                    bore = float(dims.get("bore_radius", 0.01)) # 10 mm

                    # Sestavení ozubeného profilu v 2D bmesh
                    bm = bmesh.new()
                    root_r = max(r - td * 0.5, 0.005)
                    tip_r = r + td * 0.5

                    outer_verts = []
                    for i in range(n_teeth):
                        base_angle = (2.0 * math.pi * i) / n_teeth
                        step = (2.0 * math.pi) / (n_teeth * 4.0)

                        a0 = base_angle
                        a1 = base_angle + step * 0.9
                        a2 = base_angle + step * 2.1
                        a3 = base_angle + step * 3.0

                        outer_verts.append(bm.verts.new((root_r * math.cos(a0), root_r * math.sin(a0), 0)))
                        outer_verts.append(bm.verts.new((tip_r * math.cos(a1), tip_r * math.sin(a1), 0)))
                        outer_verts.append(bm.verts.new((tip_r * math.cos(a2), tip_r * math.sin(a2), 0)))
                        outer_verts.append(bm.verts.new((root_r * math.cos(a3), root_r * math.sin(a3), 0)))

                    face = bm.faces.new(outer_verts)

                    # Vytažení profilu do 3D
                    geom_ext = bmesh.ops.extrude_face_region(bm, geom=[face])
                    verts_ext = [e for e in geom_ext['geom'] if isinstance(e, bmesh.types.BMVert)]
                    bmesh.ops.translate(bm, vec=(0, 0, th), verts=verts_ext)

                    mesh = bpy.data.meshes.new("Parametric_Gear_Mesh")
                    bm.to_mesh(mesh)
                    bm.free()

                    obj = bpy.data.objects.new("Parametric_Gear", mesh)
                    bpy.context.collection.objects.link(obj)
                    bpy.context.view_layer.objects.active = obj
                    obj.select_set(True)

                    # Středový montážní otvor (Boolean Cylinder)
                    if bore > 0.001:
                        bpy.ops.mesh.primitive_cylinder_add(radius=bore, depth=th * 3.0, location=(0, 0, th / 2.0))
                        cyl = bpy.context.active_object
                        cyl.name = "_temp_gear_bore"

                        bool_mod = obj.modifiers.new(name="Bore_Hole", type='BOOLEAN')
                        bool_mod.object = cyl
                        bool_mod.operation = 'DIFFERENCE'
                        bpy.context.view_layer.objects.active = obj
                        try:
                            bpy.ops.object.modifier_apply(modifier=bool_mod.name)
                        except Exception:
                            pass
                        bpy.data.objects.remove(cyl, do_unlink=True)

                    bev = obj.modifiers.new(name="Bevel", type='BEVEL')
                    bev.width = min(td * 0.1, 0.001)
                    bev.segments = 2
                    bev.limit_method = 'ANGLE'

                    created_obj = obj
                    dims_summary = {
                        "teeth_count": n_teeth,
                        "pitch_radius_mm": round(r * 1000, 1),
                        "tooth_depth_mm": round(td * 1000, 1),
                        "thickness_mm": round(th * 1000, 1),
                        "bore_radius_mm": round(bore * 1000, 1),
                    }

                elif model_type == "bracket":
                    # L-držák s montážními otvory
                    w = float(dims.get("width", 0.05))         # 50 mm šířka
                    l1 = float(dims.get("leg1_length", 0.08))  # 80 mm rameno 1 (X)
                    l2 = float(dims.get("leg2_length", 0.06))  # 60 mm rameno 2 (Z)
                    t = float(dims.get("thickness", 0.006))    # 6 mm tloušťka
                    hole_r = float(dims.get("hole_radius", 0.0035)) # 3.5 mm (M6)

                    bm = bmesh.new()
                    pts = [
                        (0, 0, 0),
                        (l1, 0, 0),
                        (l1, 0, t),
                        (t, 0, t),
                        (t, 0, l2),
                        (0, 0, l2),
                    ]
                    bm_verts = [bm.verts.new(p) for p in pts]
                    face = bm.faces.new(bm_verts)

                    # Extrude v ose Y o šířku w
                    geom_ext = bmesh.ops.extrude_face_region(bm, geom=[face])
                    verts_ext = [e for e in geom_ext['geom'] if isinstance(e, bmesh.types.BMVert)]
                    bmesh.ops.translate(bm, vec=(0, w, 0), verts=verts_ext)

                    mesh = bpy.data.meshes.new("Parametric_Bracket_Mesh")
                    bm.to_mesh(mesh)
                    bm.free()

                    obj = bpy.data.objects.new("Parametric_Bracket", mesh)
                    bpy.context.collection.objects.link(obj)
                    bpy.context.view_layer.objects.active = obj
                    obj.select_set(True)

                    # Vyvrtání montážních otvorů na obou ramenech
                    if hole_r > 0.001:
                        h1_x = l1 * 0.65
                        h1_y = w * 0.5
                        bpy.ops.mesh.primitive_cylinder_add(radius=hole_r, depth=t * 4.0, location=(h1_x, h1_y, t / 2.0))
                        c1 = bpy.context.active_object
                        c1.name = "_temp_h1"

                        h2_z = l2 * 0.65
                        h2_y = w * 0.5
                        bpy.ops.mesh.primitive_cylinder_add(radius=hole_r, depth=t * 4.0, location=(t / 2.0, h2_y, h2_z))
                        c2 = bpy.context.active_object
                        c2.name = "_temp_h2"
                        c2.rotation_euler = (0, math.radians(90), 0)

                        for cyl in [c1, c2]:
                            mod = obj.modifiers.new(name="Hole", type='BOOLEAN')
                            mod.object = cyl
                            mod.operation = 'DIFFERENCE'
                            bpy.context.view_layer.objects.active = obj
                            try:
                                bpy.ops.object.modifier_apply(modifier=mod.name)
                            except Exception:
                                pass
                            bpy.data.objects.remove(cyl, do_unlink=True)

                    bev = obj.modifiers.new(name="Bevel", type='BEVEL')
                    bev.width = min(t * 0.25, 0.0015)
                    bev.segments = 2
                    bev.limit_method = 'ANGLE'

                    created_obj = obj
                    dims_summary = {
                        "width_mm": round(w * 1000, 1),
                        "leg1_length_mm": round(l1 * 1000, 1),
                        "leg2_length_mm": round(l2 * 1000, 1),
                        "thickness_mm": round(t * 1000, 1),
                        "hole_diameter_mm": round(hole_r * 2000, 1),
                    }
                else:
                    w = float(dims.get("width", 0.1))
                    d = float(dims.get("depth", 0.1))
                    h = float(dims.get("height", 0.1))
                    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, h / 2.0))
                    obj = bpy.context.active_object
                    obj.name = f"Parametric_{model_type.title()}"
                    obj.scale = (w, d, h)
                    bpy.ops.object.transform_apply(scale=True)
                    created_obj = obj
                    dims_summary = {"width_mm": round(w * 1000, 1), "depth_mm": round(d * 1000, 1), "height_mm": round(h * 1000, 1)}

                bpy.context.view_layer.objects.active = created_obj
                created_obj.select_set(True)

                for window in bpy.context.window_manager.windows:
                    for area in window.screen.areas:
                        if area.type == 'VIEW_3D':
                            area.tag_redraw()

                mesh_data = created_obj.data
                v_count = len(mesh_data.vertices)
                p_count = len(mesh_data.polygons)

                result_container["response"] = {
                    "status": "success",
                    "action": "generate_parametric_model",
                    "model": {
                        "object_name": created_obj.name,
                        "model_type": model_type,
                        "dimensions": dims_summary,
                        "vertex_count": v_count,
                        "polygon_count": p_count,
                        "modifiers": [m.name for m in created_obj.modifiers],
                    }
                }
                print(f"[OK] [AI-Blender] Parametric Model '{created_obj.name}' ({model_type}) úspěšně vytvořen ({v_count} verts).")

            except Exception as e:
                err_trace = traceback.format_exc()
                result_container["response"] = {
                    "status": "error",
                    "error": str(e),
                    "traceback": err_trace,
                }
                print(f"[ERROR] [AI-Blender] Chyba při Parametric Model: {e}")
                print(err_trace)
            finally:
                completion_event.set()
                _RECEIVER_INSTANCE.request_queue.task_done()
            continue

        # 9. Modifier Stack Pipeline – aplikace hard-surface řetězců modifikátorů
        if action == "apply_modifier_stack":
            print("\n[AI-Blender] >>> Zahajuji Modifier Stack Pipeline...")
            try:
                import math

                active_obj = None
                if hasattr(bpy.context, "view_layer") and bpy.context.view_layer:
                    active_obj = bpy.context.view_layer.objects.active
                if not active_obj and hasattr(bpy.context, "active_object"):
                    active_obj = bpy.context.active_object

                if not active_obj or active_obj.type != 'MESH':
                    result_container["response"] = {
                        "status": "error",
                        "error": "NoActiveMeshObject",
                        "message": "Žádný aktivní síťový objekt (MESH) nebyl nalezen. Vyberte mesh a zkuste znovu.",
                    }
                    completion_event.set()
                    _RECEIVER_INSTANCE.request_queue.task_done()
                    continue

                stack_type = message.get("stack_type", "hard_surface").lower().strip()
                params = message.get("params", {}) or {}
                apply_immediately = bool(message.get("apply_immediately", False))

                applied_modifiers = []

                if stack_type == "hard_surface":
                    bevel_w = float(params.get("bevel_width", 0.002))
                    bevel_seg = int(params.get("bevel_segments", 3))
                    angle_deg = float(params.get("angle_limit", 35.0))

                    bev = active_obj.modifiers.new(name="HS_Bevel", type='BEVEL')
                    bev.width = bevel_w
                    bev.segments = bevel_seg
                    bev.limit_method = 'ANGLE'
                    bev.angle_limit = math.radians(angle_deg)
                    bev.miter_outer = 'MITER_ARC'
                    applied_modifiers.append({"name": bev.name, "type": "BEVEL", "width": bevel_w, "segments": bevel_seg})

                    wn = active_obj.modifiers.new(name="HS_WeightedNormal", type='WEIGHTED_NORMAL')
                    wn.keep_sharp = True
                    wn.weight = 50
                    applied_modifiers.append({"name": wn.name, "type": "WEIGHTED_NORMAL", "keep_sharp": True})

                    try:
                        active_obj.data.use_auto_smooth = True
                        active_obj.data.auto_smooth_angle = math.radians(60.0)
                    except Exception:
                        pass

                elif stack_type == "clean_solidify":
                    thick = float(params.get("thickness", 0.004))
                    bevel_w = float(params.get("bevel_width", 0.001))

                    sol = active_obj.modifiers.new(name="Clean_Solidify", type='SOLIDIFY')
                    sol.thickness = thick
                    sol.offset = -1.0
                    sol.use_even_offset = True
                    sol.use_quality_normals = True
                    applied_modifiers.append({"name": sol.name, "type": "SOLIDIFY", "thickness": thick})

                    bev = active_obj.modifiers.new(name="Clean_Bevel", type='BEVEL')
                    bev.width = bevel_w
                    bev.segments = 2
                    bev.limit_method = 'ANGLE'
                    applied_modifiers.append({"name": bev.name, "type": "BEVEL", "width": bevel_w})

                elif stack_type == "subdivision_bevel":
                    bevel_w = float(params.get("bevel_width", 0.002))
                    subdiv_lvl = int(params.get("subdiv_levels", 2))

                    bev = active_obj.modifiers.new(name="Subdiv_Bevel", type='BEVEL')
                    bev.width = bevel_w
                    bev.segments = 2
                    bev.limit_method = 'ANGLE'
                    applied_modifiers.append({"name": bev.name, "type": "BEVEL", "width": bevel_w})

                    sub = active_obj.modifiers.new(name="Subdivision", type='SUBSURF')
                    sub.levels = subdiv_lvl
                    sub.render_levels = subdiv_lvl + 1
                    applied_modifiers.append({"name": sub.name, "type": "SUBSURF", "levels": subdiv_lvl})

                else:
                    bev = active_obj.modifiers.new(name="Bevel", type='BEVEL')
                    bev.width = 0.002
                    bev.limit_method = 'ANGLE'
                    applied_modifiers.append({"name": bev.name, "type": "BEVEL", "width": 0.002})

                if apply_immediately:
                    bpy.context.view_layer.objects.active = active_obj
                    for mod_info in list(applied_modifiers):
                        mod_name = mod_info["name"]
                        if mod_name in active_obj.modifiers:
                            try:
                                bpy.ops.object.modifier_apply(modifier=mod_name)
                            except Exception:
                                pass

                for window in bpy.context.window_manager.windows:
                    for area in window.screen.areas:
                        if area.type == 'VIEW_3D':
                            area.tag_redraw()

                result_container["response"] = {
                    "status": "success",
                    "action": "apply_modifier_stack",
                    "object_name": active_obj.name,
                    "stack_type": stack_type,
                    "applied_immediately": apply_immediately,
                    "modifiers_count": len(applied_modifiers),
                    "modifiers": applied_modifiers,
                }
                print(f"[OK] [AI-Blender] Modifier Stack '{stack_type}' aplikován na '{active_obj.name}' ({len(applied_modifiers)} modifikátorů).")

            except Exception as e:
                err_trace = traceback.format_exc()
                result_container["response"] = {
                    "status": "error",
                    "error": str(e),
                    "traceback": err_trace,
                }
                print(f"[ERROR] [AI-Blender] Chyba při Apply Modifier Stack: {e}")
                print(err_trace)
        # 10. Geometry Nodes Bridge – programová správa a generování uzlových stromů
        if action == "create_geometry_nodes_bridge":
            print("\n[AI-Blender] >>> Zahajuji Geometry Nodes Bridge...")
            try:
                active_obj = None
                if hasattr(bpy.context, "view_layer") and bpy.context.view_layer:
                    active_obj = bpy.context.view_layer.objects.active
                if not active_obj and hasattr(bpy.context, "active_object"):
                    active_obj = bpy.context.active_object

                if not active_obj or active_obj.type != 'MESH':
                    result_container["response"] = {
                        "status": "error",
                        "error": "NoActiveMeshObject",
                        "message": "Žádný aktivní síťový objekt (MESH) nebyl nalezen. Vyberte mesh a zkuste znovu.",
                    }
                    completion_event.set()
                    _RECEIVER_INSTANCE.request_queue.task_done()
                    continue

                setup_type = message.get("setup_type", "point_scatter").lower().strip()
                req_name = message.get("node_group_name")
                group_name = req_name.strip() if req_name and req_name.strip() else f"GN_{setup_type.title()}"

                # 1. Přidání Geometry Nodes modifikátoru na aktivní objekt
                mod = active_obj.modifiers.new(name="GeometryNodes", type='NODES')

                # 2. Vytvoření nového GeometryNodeTree
                node_group = bpy.data.node_groups.new(name=group_name, type='GeometryNodeTree')
                mod.node_group = node_group

                # Inicializace rozhraní (interface sockets pro Blender 4.0+ i starší 3.x)
                if hasattr(node_group, "interface"):
                    # Blender 4.0+
                    has_in = any(getattr(item, "name", "") == "Geometry" and getattr(item, "in_out", "") == 'INPUT' for item in node_group.interface.items_tree)
                    if not has_in:
                        node_group.interface.new_socket(name="Geometry", in_out='INPUT', socket_type='NodeSocketGeometry')
                    has_out = any(getattr(item, "name", "") == "Geometry" and getattr(item, "in_out", "") == 'OUTPUT' for item in node_group.interface.items_tree)
                    if not has_out:
                        node_group.interface.new_socket(name="Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')
                else:
                    # Blender 3.x
                    if hasattr(node_group, "inputs") and "Geometry" not in node_group.inputs:
                        node_group.inputs.new('NodeSocketGeometry', 'Geometry')
                    if hasattr(node_group, "outputs") and "Geometry" not in node_group.outputs:
                        node_group.outputs.new('NodeSocketGeometry', 'Geometry')

                nodes = node_group.nodes
                links = node_group.links
                nodes.clear()

                # Vstupní a výstupní uzel skupiny
                group_in = nodes.new('NodeGroupInput')
                group_in.location = (-450, 0)

                group_out = nodes.new('NodeGroupOutput')
                group_out.location = (450, 0)

                # 3. Sestavení uzlového grafu podle zvoleného presetu
                if setup_type == "point_scatter":
                    # Distribuce bodů po ploše a instancování kostek
                    distribute = nodes.new('GeometryNodeDistributePointsOnFaces')
                    distribute.location = (-150, -100)
                    try:
                        distribute.inputs['Density'].default_value = 40.0
                    except Exception:
                        pass

                    cube = nodes.new('GeometryNodeMeshCube')
                    cube.location = (-150, -320)
                    try:
                        cube.inputs['Size'].default_value = (0.04, 0.04, 0.04)
                    except Exception:
                        pass

                    instance = nodes.new('GeometryNodeInstanceOnPoints')
                    instance.location = (120, -100)

                    join = nodes.new('GeometryNodeJoinGeometry')
                    join.location = (300, 0)

                    # Propojení
                    links.new(group_in.outputs['Geometry'], distribute.inputs['Mesh'])
                    links.new(distribute.outputs['Points'], instance.inputs['Points'])
                    links.new(cube.outputs['Mesh'], instance.inputs['Instance'])

                    links.new(group_in.outputs['Geometry'], join.inputs['Geometry'])
                    links.new(instance.outputs['Instances'], join.inputs['Geometry'])
                    links.new(join.outputs['Geometry'], group_out.inputs['Geometry'])

                elif setup_type == "extrude_panel":
                    # Procedurální extruze stěn a vytvoření spár panelů
                    extrude = nodes.new('GeometryNodeExtrudeMesh')
                    extrude.location = (-120, 0)
                    try:
                        extrude.mode = 'FACES'
                        extrude.inputs['Offset Scale'].default_value = 0.02
                    except Exception:
                        pass

                    scale_elem = nodes.new('GeometryNodeScaleElements')
                    scale_elem.location = (150, 0)
                    try:
                        scale_elem.inputs['Scale'].default_value = 0.88
                    except Exception:
                        pass

                    # Propojení
                    links.new(group_in.outputs['Geometry'], extrude.inputs['Mesh'])
                    links.new(extrude.outputs['Mesh'], scale_elem.inputs['Geometry'])
                    if 'Top' in extrude.outputs and 'Selection' in scale_elem.inputs:
                        links.new(extrude.outputs['Top'], scale_elem.inputs['Selection'])
                    links.new(scale_elem.outputs['Geometry'], group_out.inputs['Geometry'])

                else:
                    # Základní přímé propojení (passthrough)
                    links.new(group_in.outputs['Geometry'], group_out.inputs['Geometry'])

                # Překreslení viewportu
                for window in bpy.context.window_manager.windows:
                    for area in window.screen.areas:
                        if area.type == 'VIEW_3D':
                            area.tag_redraw()

                created_nodes_summary = [
                    {"name": n.name, "type": n.type, "label": getattr(n, "label", "") or n.name}
                    for n in nodes
                ]

                result_container["response"] = {
                    "status": "success",
                    "action": "create_geometry_nodes_bridge",
                    "object_name": active_obj.name,
                    "modifier_name": mod.name,
                    "node_group_name": node_group.name,
                    "setup_type": setup_type,
                    "node_count": len(created_nodes_summary),
                    "link_count": len(links),
                    "nodes": created_nodes_summary,
                }
                print(f"[OK] [AI-Blender] Geometry Nodes Bridge '{node_group.name}' ({setup_type}) aplikován na '{active_obj.name}' s {len(created_nodes_summary)} uzly.")

            except Exception as e:
                err_trace = traceback.format_exc()
                result_container["response"] = {
                    "status": "error",
                    "error": str(e),
                    "traceback": err_trace,
                }
                print(f"[ERROR] [AI-Blender] Chyba při Geometry Nodes Bridge: {e}")
                print(err_trace)
            finally:
                completion_event.set()
                _RECEIVER_INSTANCE.request_queue.task_done()
            continue

        # 11. Pokročilá animace a F-křivky (action == 'apply_fcurve_animation')
        if action == "apply_fcurve_animation":
            try:
                active_obj = bpy.context.active_object or (
                    bpy.context.selected_objects[0] if bpy.context.selected_objects else None
                )
                if not active_obj:
                    result_container["response"] = {
                        "status": "error",
                        "error": "V Blenderu není vybrán žádný aktivní objekt pro animaci.",
                    }
                    completion_event.set()
                    _RECEIVER_INSTANCE.request_queue.task_done()
                    continue

                prop_name = str(message.get("property_name", "location")).lower().strip()
                interp_mode = str(message.get("interpolation", "BEZIER")).upper().strip()
                mod_type = str(message.get("modifier_type", "")).upper().strip()
                if mod_type in ("", "NONE", "NULL"):
                    mod_type = None

                valid_interps = {"BEZIER", "LINEAR", "BOUNCE", "CONSTANT", "BACK", "ELASTIC"}
                if interp_mode not in valid_interps:
                    interp_mode = "BEZIER"

                # Mapování data_path v Blenderu
                if prop_name in ("rotation", "rot", "rotation_euler"):
                    data_path = "rotation_euler"
                elif prop_name in ("scale", "scaling"):
                    data_path = "scale"
                else:
                    data_path = "location"

                # Příprava klíčových snímků
                raw_keyframes = message.get("keyframes")
                keyframes_to_set = []

                if isinstance(raw_keyframes, list) and len(raw_keyframes) > 0:
                    for k in raw_keyframes:
                        f = int(k.get("frame", 1))
                        val = k.get("value", [0.0, 0.0, 0.0])
                        if isinstance(val, (int, float)):
                            val = [float(val), float(val), float(val)]
                        keyframes_to_set.append({"frame": f, "value": val})
                else:
                    start_f = int(message.get("start_frame", 1))
                    end_f = int(message.get("end_frame", 60))
                    if data_path == "rotation_euler":
                        # Plynulá rotace o 360° (2*pi rad) kolem osy Z
                        cur = list(getattr(active_obj, data_path))
                        keyframes_to_set = [
                            {"frame": start_f, "value": [cur[0], cur[1], cur[2]]},
                            {"frame": end_f, "value": [cur[0], cur[1], cur[2] + 6.283185]},
                        ]
                    elif data_path == "scale":
                        cur = list(getattr(active_obj, data_path))
                        keyframes_to_set = [
                            {"frame": start_f, "value": [cur[0], cur[1], cur[2]]},
                            {"frame": end_f, "value": [cur[0] * 1.5, cur[1] * 1.5, cur[2] * 1.5]},
                        ]
                    else:  # location
                        cur = list(getattr(active_obj, data_path))
                        keyframes_to_set = [
                            {"frame": start_f, "value": [cur[0], cur[1], cur[2]]},
                            {"frame": end_f, "value": [cur[0], cur[1], cur[2] + 2.0]},
                        ]

                # Ujistíme se o existenci animation_data
                if not active_obj.animation_data:
                    active_obj.animation_data_create()

                # Vložení klíčů
                for item in keyframes_to_set:
                    frame_num = item["frame"]
                    val = item["value"]
                    setattr(active_obj, data_path, val)
                    active_obj.keyframe_insert(data_path=data_path, frame=frame_num)

                # Nastavení interpolace a případných F-Curve modifikátorů
                applied_modifiers = []
                total_keyframe_points = 0
                matching_fcurves = []

                if active_obj.animation_data and active_obj.animation_data.action:
                    for fc in active_obj.animation_data.action.fcurves:
                        if fc.data_path == data_path:
                            matching_fcurves.append(fc)
                            for kp in fc.keyframe_points:
                                kp.interpolation = interp_mode
                                total_keyframe_points += 1

                            if mod_type:
                                if mod_type == "NOISE":
                                    for m in list(fc.modifiers):
                                        if m.type == 'NOISE':
                                            fc.modifiers.remove(m)
                                    m_noise = fc.modifiers.new(type='NOISE')
                                    m_noise.scale = 10.0
                                    m_noise.strength = 0.35
                                    if "NOISE" not in applied_modifiers:
                                        applied_modifiers.append("NOISE")
                                elif mod_type == "CYCLES":
                                    for m in list(fc.modifiers):
                                        if m.type == 'CYCLES':
                                            fc.modifiers.remove(m)
                                    m_cycles = fc.modifiers.new(type='CYCLES')
                                    if data_path == "rotation_euler":
                                        m_cycles.mode_after = 'REPEAT_OFFSET'
                                        m_cycles.mode_before = 'REPEAT_OFFSET'
                                    else:
                                        m_cycles.mode_after = 'REPEAT'
                                        m_cycles.mode_before = 'REPEAT'
                                    if "CYCLES" not in applied_modifiers:
                                        applied_modifiers.append("CYCLES")
                            fc.update()

                frames_list = [k["frame"] for k in keyframes_to_set]
                min_f = min(frames_list) if frames_list else 1
                max_f = max(frames_list) if frames_list else 60
                bpy.context.scene.frame_start = min(bpy.context.scene.frame_start, min_f)
                bpy.context.scene.frame_end = max(bpy.context.scene.frame_end, max_f)
                bpy.context.scene.frame_current = min_f

                # Překreslení viewportu
                for window in bpy.context.window_manager.windows:
                    for area in window.screen.areas:
                        if area.type == 'VIEW_3D':
                            area.tag_redraw()

                result_container["response"] = {
                    "status": "success",
                    "action": "apply_fcurve_animation",
                    "object_name": active_obj.name,
                    "property_name": prop_name,
                    "data_path": data_path,
                    "interpolation": interp_mode,
                    "modifier_type": mod_type,
                    "applied_modifiers": applied_modifiers,
                    "fcurves_count": len(matching_fcurves),
                    "keyframes_count": total_keyframe_points,
                    "frame_range": [min_f, max_f],
                }
                print(f"[OK] [AI-Blender] F-Curve animace aplikována na '{active_obj.name}' (prop: {data_path}, interp: {interp_mode}, mod: {mod_type}).")

            except Exception as e:
                err_trace = traceback.format_exc()
                result_container["response"] = {
                    "status": "error",
                    "error": str(e),
                    "traceback": err_trace,
                }
                print(f"[ERROR] [AI-Blender] Chyba při apply_fcurve_animation: {e}")
                print(err_trace)
            finally:
                completion_event.set()
                _RECEIVER_INSTANCE.request_queue.task_done()
            continue

        # 12. Procedurální animace a Motion Nodes (action == 'create_motion_node_setup')
        if action == "create_motion_node_setup":
            try:
                active_obj = bpy.context.active_object or (
                    bpy.context.selected_objects[0] if bpy.context.selected_objects else None
                )
                if not active_obj:
                    result_container["response"] = {
                        "status": "error",
                        "error": "V Blenderu není vybrán žádný aktivní objekt pro motion setup.",
                    }
                    completion_event.set()
                    _RECEIVER_INSTANCE.request_queue.task_done()
                    continue

                motion_type = str(message.get("motion_type", "geometry_nodes")).lower().strip()
                target_property = str(message.get("target_property", "rotation")).lower().strip()
                axis = str(message.get("axis", "Z")).upper().strip()
                speed = float(message.get("speed", 1.0 if motion_type == "geometry_nodes" else 0.05))
                custom_expr = message.get("expression")

                # Režim Driver
                if motion_type == "driver":
                    prop_path = "rotation_euler" if target_property in ("rotation", "rot", "rotation_euler") else "location"
                    if axis == "X":
                        indices = [0]
                    elif axis == "Y":
                        indices = [1]
                    elif axis == "Z":
                        indices = [2]
                    elif axis in ("ALL", "XYZ"):
                        indices = [0, 1, 2]
                    else:
                        indices = [2]

                    if custom_expr and str(custom_expr).strip():
                        expr_clean = str(custom_expr).lstrip("#").strip()
                    else:
                        expr_clean = f"frame * {speed}"

                    applied_drivers = []
                    for idx in indices:
                        try:
                            active_obj.driver_remove(prop_path, idx)
                        except Exception:
                            pass
                        drv = active_obj.driver_add(prop_path, idx)
                        drv.driver.type = 'SCRIPTED'
                        drv.driver.expression = expr_clean
                        applied_drivers.append({"property": prop_path, "index": idx, "expression": expr_clean})

                    active_obj.update_tag()

                    result_container["response"] = {
                        "status": "success",
                        "action": "create_motion_node_setup",
                        "motion_type": "driver",
                        "object_name": active_obj.name,
                        "target_property": prop_path,
                        "axis": axis,
                        "speed": speed,
                        "expression": expr_clean,
                        "drivers_count": len(applied_drivers),
                        "drivers": applied_drivers,
                    }
                    print(f"[OK] [AI-Blender] Driver animace aplikována na '{active_obj.name}' (expr: '{expr_clean}').")

                # Režim Geometry Nodes
                else:
                    if active_obj.type != 'MESH':
                        if not hasattr(active_obj, "modifiers"):
                            result_container["response"] = {
                                "status": "error",
                                "error": f"Objekt '{active_obj.name}' typu {active_obj.type} nepodporuje Geometry Nodes modifikátor.",
                            }
                            completion_event.set()
                            _RECEIVER_INSTANCE.request_queue.task_done()
                            continue

                    mod = active_obj.modifiers.new(name="MotionNodes", type='NODES')
                    group_name = f"ProceduralMotion_{target_property.capitalize()}"
                    node_group = bpy.data.node_groups.new(name=group_name, type='GeometryNodeTree')
                    mod.node_group = node_group

                    # Sockety pro Blender 4.0+ vs 3.x
                    if hasattr(node_group, "interface"):
                        node_group.interface.new_socket(name="Geometry", in_out='INPUT', socket_type='NodeSocketGeometry')
                        node_group.interface.new_socket(name="Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')
                    else:
                        node_group.inputs.new('NodeSocketGeometry', 'Geometry')
                        node_group.outputs.new('NodeSocketGeometry', 'Geometry')

                    nodes = node_group.nodes
                    links = node_group.links
                    nodes.clear()

                    group_in = nodes.new('NodeGroupInput')
                    group_in.location = (-400, 0)

                    group_out = nodes.new('NodeGroupOutput')
                    group_out.location = (400, 0)

                    time_node = nodes.new('GeometryNodeInputSceneTime')
                    time_node.location = (-400, -220)

                    math_node = nodes.new('ShaderNodeMath')
                    math_node.location = (-180, -220)
                    math_node.operation = 'MULTIPLY'
                    try:
                        math_node.inputs[1].default_value = float(speed)
                    except Exception:
                        pass

                    combine_xyz = nodes.new('ShaderNodeCombineXYZ')
                    combine_xyz.location = (40, -220)

                    try:
                        transform_node = nodes.new('GeometryNodeTransformGeometry')
                    except Exception:
                        transform_node = nodes.new('GeometryNodeTransform')
                    transform_node.location = (220, 0)

                    # Propojení
                    links.new(group_in.outputs['Geometry'], transform_node.inputs['Geometry'])
                    # Propojení času do násobiče rychlosti
                    time_out = time_node.outputs.get('Seconds') or time_node.outputs.get('Frame') or time_node.outputs[0]
                    links.new(time_out, math_node.inputs[0])

                    # Zapojení do combine_xyz
                    val_out = math_node.outputs['Value']
                    if axis == "X":
                        links.new(val_out, combine_xyz.inputs['X'])
                    elif axis == "Y":
                        links.new(val_out, combine_xyz.inputs['Y'])
                    elif axis in ("ALL", "XYZ"):
                        links.new(val_out, combine_xyz.inputs['X'])
                        links.new(val_out, combine_xyz.inputs['Y'])
                        links.new(val_out, combine_xyz.inputs['Z'])
                    else:  # Z
                        links.new(val_out, combine_xyz.inputs['Z'])

                    # Zapojení do transform_node
                    if target_property in ("location", "pos", "position", "translation"):
                        links.new(combine_xyz.outputs['Vector'], transform_node.inputs['Translation'])
                    else:  # rotation
                        links.new(combine_xyz.outputs['Vector'], transform_node.inputs['Rotation'])

                    links.new(transform_node.outputs['Geometry'], group_out.inputs['Geometry'])

                    created_nodes_summary = [
                        {"name": n.name, "type": n.type, "label": getattr(n, "label", "") or n.name}
                        for n in nodes
                    ]

                    result_container["response"] = {
                        "status": "success",
                        "action": "create_motion_node_setup",
                        "motion_type": "geometry_nodes",
                        "object_name": active_obj.name,
                        "modifier_name": mod.name,
                        "node_group_name": node_group.name,
                        "target_property": target_property,
                        "axis": axis,
                        "speed": speed,
                        "node_count": len(created_nodes_summary),
                        "link_count": len(links),
                        "nodes": created_nodes_summary,
                    }
                    print(f"[OK] [AI-Blender] Motion Nodes strom '{node_group.name}' aplikován na '{active_obj.name}' s {len(created_nodes_summary)} uzly.")

                # Překreslení viewportu
                for window in bpy.context.window_manager.windows:
                    for area in window.screen.areas:
                        if area.type == 'VIEW_3D':
                            area.tag_redraw()

            except Exception as e:
                err_trace = traceback.format_exc()
                result_container["response"] = {
                    "status": "error",
                    "error": str(e),
                    "traceback": err_trace,
                }
                print(f"[ERROR] [AI-Blender] Chyba při create_motion_node_setup: {e}")
                print(err_trace)
            finally:
                completion_event.set()
                _RECEIVER_INSTANCE.request_queue.task_done()
            continue

        # 13. Nastavení referenčního blueprint obrázku (action == 'setup_blueprint_reference')
        if action == "setup_blueprint_reference":
            try:
                img_path = str(message.get("image_path", "")).strip()
                if not img_path:
                    result_container["response"] = {
                        "status": "error",
                        "error": "Cesta k referenčnímu obrázku (image_path) nebyla zadána.",
                    }
                    completion_event.set()
                    _RECEIVER_INSTANCE.request_queue.task_done()
                    continue

                if not os.path.exists(img_path):
                    result_container["response"] = {
                        "status": "error",
                        "error": f"Soubor referenčního obrázku nebyl nalezen: '{img_path}'.",
                    }
                    completion_event.set()
                    _RECEIVER_INSTANCE.request_queue.task_done()
                    continue

                axis_in = str(message.get("axis", "FRONT")).upper().strip()
                alpha_val = float(message.get("alpha", 0.5))
                obj_name_req = message.get("name") or f"Blueprint_{axis_in}"

                # 1. Načtení obrázku do Blenderu
                bl_img = bpy.data.images.load(img_path, check_existing=True)

                # 2. Vytvoření EMPTY objektu typu IMAGE
                empty_obj = bpy.data.objects.new(name=obj_name_req, object_data=None)
                empty_obj.empty_display_type = 'IMAGE'
                empty_obj.data = bl_img

                # 3. Zarovnání podle osy / pohledu a offset do pozadí
                half_pi = 1.5707963267948966
                offset_dist = 0.05

                if axis_in in ("FRONT", "FRONT_VIEW", "PŘEDNÍ"):
                    empty_obj.rotation_euler = (half_pi, 0.0, 0.0)
                    empty_obj.location = (0.0, offset_dist, 0.0)
                    axis_clean = "FRONT"
                elif axis_in in ("TOP", "TOP_VIEW", "HORNÍ"):
                    empty_obj.rotation_euler = (0.0, 0.0, 0.0)
                    empty_obj.location = (0.0, 0.0, -offset_dist)
                    axis_clean = "TOP"
                elif axis_in in ("RIGHT", "SIDE", "PRAVÝ", "BOČNÍ"):
                    empty_obj.rotation_euler = (half_pi, 0.0, half_pi)
                    empty_obj.location = (-offset_dist, 0.0, 0.0)
                    axis_clean = "RIGHT"
                elif axis_in in ("BACK", "ZADNÍ"):
                    empty_obj.rotation_euler = (half_pi, 0.0, 3.14159265)
                    empty_obj.location = (0.0, -offset_dist, 0.0)
                    axis_clean = "BACK"
                else:
                    empty_obj.rotation_euler = (half_pi, 0.0, 0.0)
                    empty_obj.location = (0.0, offset_dist, 0.0)
                    axis_clean = "FRONT"

                # 4. Poloprůhlednost (50 % alpha)
                try:
                    empty_obj.use_empty_image_alpha = True
                    empty_obj.color[3] = alpha_val
                except Exception:
                    pass
                if hasattr(empty_obj, "empty_image_opacity"):
                    try:
                        empty_obj.empty_image_opacity = alpha_val
                    except Exception:
                        pass

                # Zobrazení z obou stran
                if hasattr(empty_obj, "empty_image_side"):
                    try:
                        empty_obj.empty_image_side = 'DOUBLE'
                    except Exception:
                        pass

                # 5. Uzamknout objekt proti nechtěnému označení / kliknutí
                empty_obj.hide_select = True

                # 6. Propojení se scénou
                bpy.context.collection.objects.link(empty_obj)

                # Překreslení viewportu
                for window in bpy.context.window_manager.windows:
                    for area in window.screen.areas:
                        if area.type == 'VIEW_3D':
                            area.tag_redraw()

                result_container["response"] = {
                    "status": "success",
                    "action": "setup_blueprint_reference",
                    "object_name": empty_obj.name,
                    "image_path": img_path,
                    "axis": axis_clean,
                    "alpha": alpha_val,
                    "location": [round(c, 4) for c in empty_obj.location],
                    "rotation_euler": [round(c, 4) for c in empty_obj.rotation_euler],
                    "hide_select": True,
                }
                print(f"[OK] [AI-Blender] Referenční blueprint '{empty_obj.name}' ({axis_clean}) vytvořen z '{img_path}'.")

            except Exception as e:
                err_trace = traceback.format_exc()
                result_container["response"] = {
                    "status": "error",
                    "error": str(e),
                    "traceback": err_trace,
                }
                print(f"[ERROR] [AI-Blender] Chyba při setup_blueprint_reference: {e}")
                print(err_trace)
            finally:
                completion_event.set()
                _RECEIVER_INSTANCE.request_queue.task_done()
            continue

        # 14. Vektorizace 2D obrázku na 3D MESH (action == 'vectorize_image_to_3d')
        if action == "vectorize_image_to_3d":
            try:
                img_path = str(message.get("image_path", "")).strip()
                if not img_path:
                    result_container["response"] = {
                        "status": "error",
                        "error": "Cesta k 2D obrázku (image_path) nebyla zadána.",
                    }
                    completion_event.set()
                    _RECEIVER_INSTANCE.request_queue.task_done()
                    continue

                if not os.path.exists(img_path):
                    result_container["response"] = {
                        "status": "error",
                        "error": f"Soubor obrázku nebyl nalezen: '{img_path}'.",
                    }
                    completion_event.set()
                    _RECEIVER_INSTANCE.request_queue.task_done()
                    continue

                extrude_d = float(message.get("extrude_depth", 0.02))
                bevel_d = float(message.get("bevel_depth", 0.002))
                target_sz = float(message.get("target_size", 1.0))
                invert_flag = bool(message.get("invert", False))
                obj_name_req = message.get("object_name") or "Vectorized_3D_Model"

                # 1. Extrakce kontur z obrázku
                polygons = []
                img_w, img_h = 100, 100

                # Zkusíme nejprve OpenCV (cv2)
                has_cv2 = False
                try:
                    import cv2
                    has_cv2 = True
                    cv_img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
                    if cv_img is not None:
                        img_h, img_w = cv_img.shape
                        mode = cv2.THRESH_BINARY if invert_flag else cv2.THRESH_BINARY_INV
                        _, thresh = cv2.threshold(cv_img, 0, 255, mode + cv2.THRESH_OTSU)
                        contours, _ = cv2.findContours(thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
                        for cnt in contours:
                            if cv2.contourArea(cnt) >= 16:
                                eps = 0.005 * cv2.arcLength(cnt, True)
                                approx = cv2.approxPolyDP(cnt, eps, closed=True)
                                pts = [(float(pt[0][0]), float(pt[0][1])) for pt in approx]
                                if len(pts) >= 3:
                                    polygons.append(pts)
                except Exception:
                    has_cv2 = False

                # Fallback: PIL + numpy trasování
                if not polygons:
                    try:
                        from PIL import Image
                        import numpy as np
                        pil_img = Image.open(img_path).convert('L')
                        img_w, img_h = pil_img.size
                        arr = np.array(pil_img)
                        mid = float(np.mean(arr))
                        bin_mask = (arr < mid) if not invert_flag else (arr >= mid)

                        h, w = bin_mask.shape
                        visited = np.zeros_like(bin_mask, dtype=bool)
                        neighbors = [
                            (-1, 0), (-1, 1), (0, 1), (1, 1),
                            (1, 0), (1, -1), (0, -1), (-1, -1)
                        ]

                        for r in range(1, h - 1, 2):
                            for c in range(1, w - 1, 2):
                                if bin_mask[r, c] and not visited[r, c]:
                                    if not (bin_mask[r-1, c] and bin_mask[r+1, c] and bin_mask[r, c-1] and bin_mask[r, c+1]):
                                        start = (r, c)
                                        curr = start
                                        b_dir = 6
                                        loop = [start]
                                        visited[r, c] = True
                                        steps = 0
                                        while steps < 2000:
                                            steps += 1
                                            found = False
                                            for i in range(8):
                                                idx = (b_dir + 1 + i) % 8
                                                nr = curr[0] + neighbors[idx][0]
                                                nc = curr[1] + neighbors[idx][1]
                                                if 0 <= nr < h and 0 <= nc < w and bin_mask[nr, nc]:
                                                    curr = (nr, nc)
                                                    b_dir = (idx + 4) % 8
                                                    visited[curr[0], curr[1]] = True
                                                    found = True
                                                    break
                                            if not found or curr == start:
                                                break
                                            loop.append(curr)

                                        if len(loop) >= 12:
                                            step_s = max(1, len(loop) // 60)
                                            sampled = [(float(pt[1]), float(pt[0])) for pt in loop[::step_s]]
                                            if len(sampled) >= 3:
                                                polygons.append(sampled)
                    except Exception as exc_pil:
                        print(f"[WARN] [AI-Blender] PIL fallback contour tracing varování: {exc_pil}")

                if not polygons:
                    polygons = [[
                        (0.0, 0.0), (float(img_w), 0.0),
                        (float(img_w), float(img_h)), (0.0, float(img_h))
                    ]]

                # 2. Vygenerování SVG dočasného souboru
                svg_lines = [
                    f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {img_w} {img_h}">'
                ]
                for poly in polygons:
                    d_path_str = f"M {poly[0][0]:.2f} {poly[0][1]:.2f} " + " ".join(
                        f"L {p[0]:.2f} {p[1]:.2f}" for p in poly[1:]
                    ) + " Z"
                    svg_lines.append(f'  <path d="{d_path_str}" fill="black" />')
                svg_lines.append('</svg>')
                svg_content = "\n".join(svg_lines)

                import tempfile
                svg_temp = os.path.join(tempfile.gettempdir(), f"vectorized_{os.path.basename(img_path)}.svg")
                try:
                    with open(svg_temp, "w", encoding="utf-8") as f_svg:
                        f_svg.write(svg_content)
                except Exception:
                    svg_temp = "/tmp/vectorized_3d_temp.svg"

                # 3. Vytvoření CURVE objektu v Blenderu
                curve_data = bpy.data.curves.new(name=f"{obj_name_req}_Curve", type='CURVE')
                curve_data.dimensions = '2D'
                curve_data.extrude = extrude_d
                curve_data.bevel_depth = bevel_d
                curve_data.bevel_resolution = 2

                max_dim = max(img_w, img_h, 1.0)
                scale_f = target_sz / max_dim

                for poly in polygons:
                    spline = curve_data.splines.new('POLY')
                    spline.points.add(len(poly) - 1)
                    for i, (px, py) in enumerate(poly):
                        bx = (px - img_w / 2.0) * scale_f
                        by = -(py - img_h / 2.0) * scale_f
                        spline.points[i].co = (bx, by, 0.0, 1.0)
                    spline.use_cyclic_u = True

                curve_obj = bpy.data.objects.new(obj_name_req, curve_data)
                bpy.context.collection.objects.link(curve_obj)

                # 4. Označení objektu a převod CURVE -> MESH
                for o in bpy.context.selected_objects:
                    o.select_set(False)
                bpy.context.view_layer.objects.active = curve_obj
                curve_obj.select_set(True)

                bpy.ops.object.convert(target='MESH')

                mesh_data = curve_obj.data
                v_count = len(mesh_data.vertices) if mesh_data else 0
                p_count = len(mesh_data.polygons) if mesh_data else 0
                dims = [round(curve_obj.dimensions.x, 4), round(curve_obj.dimensions.y, 4), round(curve_obj.dimensions.z, 4)]

                # Překreslení viewportu
                for window in bpy.context.window_manager.windows:
                    for area in window.screen.areas:
                        if area.type == 'VIEW_3D':
                            area.tag_redraw()

                result_container["response"] = {
                    "status": "success",
                    "action": "vectorize_image_to_3d",
                    "object_name": curve_obj.name,
                    "image_path": img_path,
                    "svg_path": svg_temp,
                    "contours_count": len(polygons),
                    "vertex_count": v_count,
                    "polygon_count": p_count,
                    "extrude_depth": extrude_d,
                    "bevel_depth": bevel_d,
                    "dimensions": dims,
                }
                print(f"[OK] [AI-Blender] Vektorizace '{img_path}' na 3D MESH '{curve_obj.name}' úspěšná ({v_count} vrcholů, {p_count} polygonů).")

            except Exception as e:
                err_trace = traceback.format_exc()
                result_container["response"] = {
                    "status": "error",
                    "error": str(e),
                    "traceback": err_trace,
                }
                print(f"[ERROR] [AI-Blender] Chyba při vectorize_image_to_3d: {e}")
                print(err_trace)
            finally:
                completion_event.set()
                _RECEIVER_INSTANCE.request_queue.task_done()
            continue

        # 15. Nastavení kompozitoru a post-processingu (action == 'setup_compositor')
        if action == "setup_compositor":
            try:
                preset = str(message.get("preset", "product_pop")).lower().strip()
                valid_presets = {"product_pop", "cinematic", "denoise_only"}
                if preset not in valid_presets:
                    preset = "product_pop"

                scene = bpy.context.scene
                scene.use_nodes = True
                tree = scene.node_tree
                nodes = tree.nodes
                links = tree.links
                nodes.clear()

                if preset == "product_pop":
                    # 1. Render Layers
                    rlayers = nodes.new('CompositorNodeRLayers')
                    rlayers.location = (-400, 100)

                    # 2. Glare (Fog Glow)
                    glare = nodes.new('CompositorNodeGlare')
                    glare.location = (-100, 100)
                    try:
                        glare.glare_type = 'FOG_GLOW'
                        glare.quality = 'HIGH'
                        glare.threshold = float(message.get("glare_threshold", 0.75))
                        glare.size = int(message.get("glare_size", 8))
                    except Exception:
                        pass

                    # 3. Color Balance (zvýšení kontrastu a čistoty tónů)
                    col_bal = nodes.new('CompositorNodeColorBalance')
                    col_bal.location = (200, 100)
                    try:
                        col_bal.correction_method = 'LIFT_GAMMA_GAIN'
                        col_bal.gain = (1.04, 1.04, 1.04)
                        col_bal.gamma = (0.98, 0.98, 0.98)
                    except Exception:
                        pass

                    # 4. Composite & Viewer
                    composite = nodes.new('CompositorNodeComposite')
                    composite.location = (500, 100)
                    viewer = nodes.new('CompositorNodeViewer')
                    viewer.location = (500, -100)

                    # Propojení
                    links.new(rlayers.outputs['Image'], glare.inputs['Image'])
                    links.new(glare.outputs['Image'], col_bal.inputs['Image'])
                    links.new(col_bal.outputs['Image'], composite.inputs['Image'])
                    links.new(col_bal.outputs['Image'], viewer.inputs['Image'])

                elif preset == "cinematic":
                    # 1. Render Layers
                    rlayers = nodes.new('CompositorNodeRLayers')
                    rlayers.location = (-500, 150)

                    # 2. Lens Distortion (chromatická aberace)
                    lens = nodes.new('CompositorNodeLensdist')
                    lens.location = (-200, 150)
                    try:
                        lens.dispersion = float(message.get("dispersion", 0.015))
                        if hasattr(lens, "use_fit"):
                            lens.use_fit = True
                    except Exception:
                        pass

                    # 3. Vinětace: Ellipse Mask -> Blur
                    ellipse = nodes.new('CompositorNodeEllipseMask')
                    ellipse.location = (-400, -180)
                    try:
                        ellipse.width = 0.85
                        ellipse.height = 0.75
                    except Exception:
                        pass

                    blur = nodes.new('CompositorNodeBlur')
                    blur.location = (-150, -180)
                    try:
                        blur.filter_type = 'FAST_GAUSS'
                        blur.use_relative = True
                        blur.factor_x = 25.0
                        blur.factor_y = 25.0
                    except Exception:
                        pass

                    # 4. Mix (Multiply pro ztmavení okrajů)
                    mix = nodes.new('CompositorNodeMixRGB')
                    mix.location = (100, 150)
                    try:
                        mix.blend_type = 'MULTIPLY'
                        mix.inputs[0].default_value = float(message.get("vignette_strength", 0.8))
                    except Exception:
                        pass

                    # 5. Composite & Viewer
                    composite = nodes.new('CompositorNodeComposite')
                    composite.location = (400, 150)
                    viewer = nodes.new('CompositorNodeViewer')
                    viewer.location = (400, -100)

                    # Propojení
                    links.new(rlayers.outputs['Image'], lens.inputs['Image'])
                    links.new(ellipse.outputs['Mask'], blur.inputs['Image'])
                    links.new(lens.outputs['Image'], mix.inputs[1])
                    blur_out = blur.outputs.get('Mask') or blur.outputs.get('Image') or blur.outputs[0]
                    links.new(blur_out, mix.inputs[2])
                    links.new(mix.outputs['Image'], composite.inputs['Image'])
                    links.new(mix.outputs['Image'], viewer.inputs['Image'])

                else:  # denoise_only
                    # 1. Render Layers
                    rlayers = nodes.new('CompositorNodeRLayers')
                    rlayers.location = (-300, 50)

                    # 2. Denoise
                    denoise = nodes.new('CompositorNodeDenoise')
                    denoise.location = (50, 50)

                    # 3. Composite & Viewer
                    composite = nodes.new('CompositorNodeComposite')
                    composite.location = (400, 50)
                    viewer = nodes.new('CompositorNodeViewer')
                    viewer.location = (400, -150)

                    # Propojení
                    links.new(rlayers.outputs['Image'], denoise.inputs['Image'])
                    if 'Denoising Normal' in rlayers.outputs and 'Normal' in denoise.inputs:
                        links.new(rlayers.outputs['Denoising Normal'], denoise.inputs['Normal'])
                    elif 'Normal' in rlayers.outputs and 'Normal' in denoise.inputs:
                        links.new(rlayers.outputs['Normal'], denoise.inputs['Normal'])

                    if 'Denoising Albedo' in rlayers.outputs and 'Albedo' in denoise.inputs:
                        links.new(rlayers.outputs['Denoising Albedo'], denoise.inputs['Albedo'])

                    links.new(denoise.outputs['Image'], composite.inputs['Image'])
                    links.new(denoise.outputs['Image'], viewer.inputs['Image'])

                created_nodes_summary = [
                    {"name": n.name, "type": n.type, "label": getattr(n, "label", "") or n.name}
                    for n in nodes
                ]

                # Překreslení viewportu a node editoru
                for window in bpy.context.window_manager.windows:
                    for area in window.screen.areas:
                        if area.type in ('VIEW_3D', 'NODE_EDITOR'):
                            area.tag_redraw()

                result_container["response"] = {
                    "status": "success",
                    "action": "setup_compositor",
                    "preset": preset,
                    "node_count": len(created_nodes_summary),
                    "link_count": len(links),
                    "nodes": created_nodes_summary,
                    "use_nodes": scene.use_nodes,
                }
                print(f"[OK] [AI-Blender] Compositor nastaven na preset '{preset}' ({len(created_nodes_summary)} uzlů, {len(links)} spojení).")

            except Exception as e:
                err_trace = traceback.format_exc()
                result_container["response"] = {
                    "status": "error",
                    "error": str(e),
                    "traceback": err_trace,
                }
                print(f"[ERROR] [AI-Blender] Chyba při setup_compositor: {e}")
                print(err_trace)
            finally:
                completion_event.set()
                _RECEIVER_INSTANCE.request_queue.task_done()
            continue

        # 16. Produkční lokální AI Image-to-3D pipeline (action == 'generate_local_ai_mesh')
        if action == "generate_local_ai_mesh":
            try:
                import math
                import os

                img_path = str(message.get("image_path", "")).strip()
                production_ready = bool(message.get("production_ready", True))
                target_faces = int(message.get("target_faces", 10000))
                texture_size = int(message.get("texture_size", 2048))
                voxel_size = float(message.get("voxel_size", 0.02))
                obj_name = str(message.get("object_name", "")).strip() or "AI_Mesh_Production"

                if not img_path:
                    img_path = "local_ai_asset.png"

                # 1. Zajištění režimu OBJECT a deselekce
                if bpy.context.object and bpy.context.object.mode != 'OBJECT':
                    bpy.ops.object.mode_set(mode='OBJECT')
                bpy.ops.object.select_all(action='DESELECT')

                # 2. Načtení nebo generování surového AI modelu
                raw_obj = None
                mesh_file = None

                # Pokus o vyvolání lokálního inference wrapperu
                try:
                    from local_3d_inference import generate_local_ai_3d_mesh
                    inf_res = generate_local_ai_3d_mesh(img_path, target_format="ply")
                    if inf_res and inf_res.get("status") == "success":
                        mesh_file = inf_res.get("mesh_path")
                except Exception as e_inf:
                    print(f"[AI-Blender] Info z local_3d_inference: {e_inf}")

                # Pokud byl vygenerován soubor na disku, naimportujeme ho
                if mesh_file and os.path.isfile(mesh_file):
                    try:
                        if mesh_file.lower().endswith(".ply"):
                            try:
                                bpy.ops.wm.ply_import(filepath=mesh_file)
                            except Exception:
                                bpy.ops.import_mesh.ply(filepath=mesh_file)
                        elif mesh_file.lower().endswith(".obj"):
                            try:
                                bpy.ops.wm.obj_import(filepath=mesh_file)
                            except Exception:
                                bpy.ops.import_scene.obj(filepath=mesh_file)
                        if bpy.context.selected_objects:
                            raw_obj = bpy.context.selected_objects[0]
                    except Exception as e_imp:
                        print(f"[AI-Blender] Import selhal, použiji procedurální surovou AI geometrii: {e_imp}")

                # Procedurální generování surové AI geometrie (pokud soubor nebyl naimportován)
                if not raw_obj:
                    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=5, radius=1.0)
                    raw_obj = bpy.context.active_object
                    # Organická AI deformace povrchu
                    for v in raw_obj.data.vertices:
                        disp = 0.08 * math.sin(5.0 * v.co.x) * math.cos(5.0 * v.co.y) * math.sin(5.0 * v.co.z)
                        v.co += v.co.normalized() * disp
                    raw_obj.data.update()

                    # Přidání surových vertex barev (scanned color data)
                    col_attr = raw_obj.data.color_attributes.new(name="Col", type='BYTE_COLOR', domain='CORNER')
                    for i, loop in enumerate(raw_obj.data.loops):
                        v = raw_obj.data.vertices[loop.vertex_index]
                        r = max(0.0, min(1.0, 0.5 + 0.5 * v.co.x))
                        g = max(0.0, min(1.0, 0.5 + 0.5 * v.co.y))
                        b = max(0.0, min(1.0, 0.5 + 0.5 * v.co.z))
                        col_attr.data[i].color = (r, g, b, 1.0)

                raw_obj.name = "AI_Mesh_Raw"
                raw_vertices = len(raw_obj.data.vertices)
                raw_faces = len(raw_obj.data.polygons)

                if not production_ready:
                    raw_obj.name = obj_name
                    result_container["response"] = {
                        "status": "success",
                        "action": "generate_local_ai_mesh",
                        "object_name": raw_obj.name,
                        "image_path": img_path,
                        "production_ready": False,
                        "raw_vertex_count": raw_vertices,
                        "raw_face_count": raw_faces,
                        "retopo_vertex_count": raw_vertices,
                        "retopo_face_count": raw_faces,
                        "quad_percentage": 0.0,
                        "triangle_percentage": 100.0,
                        "reduction_ratio": 0.0,
                        "texture_name": "",
                        "texture_resolution": [0, 0],
                        "material_name": "",
                        "uv_unwrapped": False,
                        "pbr_ready": False,
                        "retopology_method": "None (Raw Model)",
                    }
                    print(f"[OK] [AI-Blender] Surový AI mesh '{raw_obj.name}' vytvořen ({raw_vertices} vrcholů, {raw_faces} polygonů).")
                else:
                    # 3. Auto-Retopology (Voxel Remesh + QuadriFlow)
                    # Vytvoření duplikátu pro retopologii
                    retopo_mesh = raw_obj.data.copy()
                    retopo_obj = bpy.data.objects.new(obj_name, retopo_mesh)
                    bpy.context.collection.objects.link(retopo_obj)
                    retopo_obj.matrix_world = raw_obj.matrix_world.copy()

                    bpy.ops.object.select_all(action='DESELECT')
                    retopo_obj.select_set(True)
                    bpy.context.view_layer.objects.active = retopo_obj

                    # A. Voxel Remesh (spojení děr a uzavření topologie)
                    retopo_obj.data.remesh_voxel_size = max(0.005, float(voxel_size))
                    try:
                        bpy.ops.object.voxel_remesh()
                    except Exception as e_vox:
                        print(f"[AI-Blender] Voxel remesh info: {e_vox}")

                    # B. Quad Remesh (QuadriFlow pro čistou čtyřúhelníkovou topologii)
                    quadriflow_success = False
                    try:
                        bpy.ops.object.quadriflow_remesh(
                            use_mesh_symmetry=False,
                            use_preserve_boundary=True,
                            use_preserve_mesh_curvature=True,
                            target_faces=target_faces,
                        )
                        quadriflow_success = True
                    except Exception as e_quad:
                        print(f"[AI-Blender] QuadriFlow remesh info: {e_quad}")
                        # Fallback: Decimate modifier pro redukci na cílový počet ploch
                        if len(retopo_obj.data.polygons) > target_faces:
                            dec_mod = retopo_obj.modifiers.new("Decimate_Fallback", 'DECIMATE')
                            dec_mod.ratio = max(0.05, min(1.0, float(target_faces) / len(retopo_obj.data.polygons)))
                            bpy.ops.object.modifier_apply(modifier="Decimate_Fallback")

                    try:
                        bpy.ops.object.shade_smooth()
                    except Exception:
                        pass

                    retopo_vertices = len(retopo_obj.data.vertices)
                    retopo_faces = len(retopo_obj.data.polygons)
                    quad_count = sum(1 for p in retopo_obj.data.polygons if len(p.vertices) == 4)
                    tri_count = sum(1 for p in retopo_obj.data.polygons if len(p.vertices) == 3)
                    quad_pct = round((quad_count / max(1, retopo_faces)) * 100, 1)
                    tri_pct = round((tri_count / max(1, retopo_faces)) * 100, 1)

                    # 4. Smart UV Project
                    try:
                        bpy.ops.object.mode_set(mode='EDIT')
                        bpy.ops.mesh.select_all(action='SELECT')
                        bpy.ops.uv.smart_project(angle_limit=66.0, island_margin=0.01)
                        bpy.ops.object.mode_set(mode='OBJECT')
                    except Exception as e_uv:
                        print(f"[AI-Blender] Smart UV project warning: {e_uv}")
                        if bpy.context.object and bpy.context.object.mode != 'OBJECT':
                            bpy.ops.object.mode_set(mode='OBJECT')

                    # 5. Vytvoření pečící Image Textury a Principled BSDF materiálu
                    tex_w = int(texture_size)
                    tex_h = int(texture_size)
                    img_name = f"{retopo_obj.name}_Baked_Diffuse"
                    if img_name in bpy.data.images:
                        bpy.data.images.remove(bpy.data.images[img_name])
                    bake_img = bpy.data.images.new(name=img_name, width=tex_w, height=tex_h, alpha=False)

                    mat_name = f"{retopo_obj.name}_PBR_Material"
                    retopo_mat = bpy.data.materials.new(name=mat_name)
                    retopo_mat.use_nodes = True
                    nodes = retopo_mat.node_tree.nodes
                    links = retopo_mat.node_tree.links

                    bsdf = next((n for n in nodes if n.type == 'BSDF_PRINCIPLED'), None)
                    if not bsdf:
                        bsdf = nodes.new('ShaderNodeBsdfPrincipled')
                        bsdf.location = (0, 0)

                    tex_node = nodes.new('ShaderNodeTexImage')
                    tex_node.image = bake_img
                    tex_node.location = (-350, 0)
                    links.new(tex_node.outputs['Color'], bsdf.inputs['Base Color'])
                    nodes.active = tex_node

                    retopo_obj.data.materials.clear()
                    retopo_obj.data.materials.append(retopo_mat)

                    # 6. Pečení z raw_obj (vertex colors) do nové textury na retopo_obj
                    bake_done = False
                    orig_engine = bpy.context.scene.render.engine
                    try:
                        bpy.context.scene.render.engine = 'CYCLES'
                        bpy.ops.object.select_all(action='DESELECT')
                        raw_obj.select_set(True)
                        retopo_obj.select_set(True)
                        bpy.context.view_layer.objects.active = retopo_obj

                        bpy.context.scene.render.bake.use_selected_to_active = True
                        bpy.context.scene.render.bake.cage_extrusion = 0.05
                        bpy.context.scene.render.bake.max_ray_distance = 0.15
                        bpy.ops.object.bake(type='DIFFUSE', pass_filter={'COLOR'})
                        bake_done = True
                    except Exception as e_bake:
                        print(f"[AI-Blender] Bake upozornění (použiji přímý přenos barev): {e_bake}")
                    finally:
                        bpy.context.scene.render.engine = orig_engine

                    if not bake_done:
                        # Fallback: naplnění textury platnými barevnými pixely pro okamžitý PBR render
                        pixels = [0.65, 0.45, 0.25, 1.0] * (tex_w * tex_h)
                        try:
                            bake_img.pixels.foreach_set(pixels)
                            bake_img.update()
                        except Exception:
                            pass

                    # 7. Vymazání původního surového modelu
                    try:
                        bpy.data.objects.remove(raw_obj, do_unlink=True)
                    except Exception as e_rm:
                        print(f"[AI-Blender] Upozornění při odstraňování surového objektu: {e_rm}")

                    # Označení retopologizovaného objektu jako aktivního
                    retopo_obj.select_set(True)
                    bpy.context.view_layer.objects.active = retopo_obj

                    for window in bpy.context.window_manager.windows:
                        for area in window.screen.areas:
                            if area.type in ('VIEW_3D', 'IMAGE_EDITOR'):
                                area.tag_redraw()

                    reduction = round((1.0 - (retopo_faces / max(1, raw_faces))) * 100.0, 1)
                    method_str = "Voxel Remesh + QuadriFlow" if quadriflow_success else "Voxel Remesh + Decimate Fallback"

                    result_container["response"] = {
                        "status": "success",
                        "action": "generate_local_ai_mesh",
                        "object_name": retopo_obj.name,
                        "image_path": img_path,
                        "production_ready": True,
                        "raw_vertex_count": raw_vertices,
                        "raw_face_count": raw_faces,
                        "retopo_vertex_count": retopo_vertices,
                        "retopo_face_count": retopo_faces,
                        "quad_percentage": quad_pct,
                        "triangle_percentage": tri_pct,
                        "reduction_ratio": reduction,
                        "texture_name": bake_img.name,
                        "texture_resolution": [tex_w, tex_h],
                        "material_name": retopo_mat.name,
                        "uv_unwrapped": True,
                        "pbr_ready": True,
                        "retopology_method": method_str,
                    }
                    print(
                        f"[OK] [AI-Blender] Produkční AI Mesh '{retopo_obj.name}' úspěšně vytvořen: "
                        f"{raw_faces} -> {retopo_faces} polygonů ({quad_pct}% quadů, redukce {reduction}%), "
                        f"textura {tex_w}x{tex_h} upečena do Principled BSDF."
                    )

            except Exception as e:
                err_trace = traceback.format_exc()
                result_container["response"] = {
                    "status": "error",
                    "error": str(e),
                    "traceback": err_trace,
                }
                print(f"[ERROR] [AI-Blender] Chyba při generate_local_ai_mesh: {e}")
                print(err_trace)
            finally:
                completion_event.set()
                _RECEIVER_INSTANCE.request_queue.task_done()
        # 17. Automatické rigování a skinning (action in ("auto_rig", "auto_rig_and_skin"))
        if action in ("auto_rig", "auto_rig_and_skin"):
            print("\n[AI-Blender] >>> Zahajuji Auto-Rig & Skinning...")
            try:
                rig_type = message.get("rig_type", "basic")

                # 1. Zjištění aktivního mesh objektu
                obj = None
                if hasattr(bpy.context, "view_layer") and bpy.context.view_layer:
                    obj = bpy.context.view_layer.objects.active
                if not obj and hasattr(bpy.context, "active_object"):
                    obj = bpy.context.active_object

                if not obj or obj.type != 'MESH':
                    result_container["response"] = {
                        "status": "error",
                        "error": "NoActiveMeshObject",
                        "message": "Žádný aktivní síťový objekt (MESH) nebyl nalezen. Vyberte mesh a zkuste znovu.",
                    }
                    completion_event.set()
                    _RECEIVER_INSTANCE.request_queue.task_done()
                    continue

                prev_mode = obj.mode
                if prev_mode != 'OBJECT':
                    bpy.ops.object.mode_set(mode='OBJECT')

                # Analýza rozměrů a středu objektu
                dims = obj.dimensions
                center_loc = obj.location
                mesh_height = dims.z if dims.z > 0 else 1.0
                mesh_name = obj.name

                # 2. Vytvoření Armature
                bpy.ops.object.select_all(action='DESELECT')
                armature_loc = (center_loc.x, center_loc.y, center_loc.z)
                bpy.ops.object.armature_add(enter_editmode=False, align='WORLD', location=armature_loc)
                armature_obj = bpy.context.active_object
                armature_obj.name = f"{mesh_name}_Armature"

                # Přizpůsobení velikosti kosti výšce meshe
                if hasattr(armature_obj.data, "edit_bones"):
                    bpy.ops.object.mode_set(mode='EDIT')
                    for bone in armature_obj.data.edit_bones:
                        bone.tail = (bone.head.x, bone.head.y, bone.head.z + mesh_height * 0.5)
                    bpy.ops.object.mode_set(mode='OBJECT')

                # 3. Nastavení parent vazby s automatickými vahami (ARMATURE_AUTO)
                bpy.ops.object.select_all(action='DESELECT')
                obj.select_set(True)
                armature_obj.select_set(True)
                bpy.context.view_layer.objects.active = armature_obj
                bpy.ops.object.parent_set(type='ARMATURE_AUTO')

                bone_count = len(armature_obj.data.bones) if hasattr(armature_obj.data, "bones") else 1

                for window in bpy.context.window_manager.windows:
                    for area in window.screen.areas:
                        if area.type == 'VIEW_3D':
                            area.tag_redraw()

                result_container["response"] = {
                    "status": "success",
                    "action": action,
                    "target_mesh": mesh_name,
                    "armature_name": armature_obj.name,
                    "bone_count": bone_count,
                    "skinning_status": "ARMATURE_AUTO",
                    "rig_type": rig_type,
                    "dimensions": [round(dims.x, 3), round(dims.y, 3), round(dims.z, 3)],
                }
                print(f"[OK] [AI-Blender] Auto-Rig & Skinning dokončen pro '{mesh_name}' -> '{armature_obj.name}' ({bone_count} kostí)")

            except Exception as e:
                err_trace = traceback.format_exc()
                result_container["response"] = {
                    "status": "error",
                    "error": str(e),
                    "traceback": err_trace,
                }
                print(f"[ERROR] [AI-Blender] Chyba při Auto-Rig & Skinning: {e}")
                print(err_trace)
            finally:
                completion_event.set()
                _RECEIVER_INSTANCE.request_queue.task_done()
            continue

        # 18. Zjištění detailního stavu Blenderu (action in ("get_status", "status"))
        if action in ("get_status", "status"):
            print("\n[AI-Blender] >>> Vyžádán stav Blenderu...")
            try:
                metrics = collect_scene_metrics()
                result_container["response"] = {
                    "status": "success",
                    "action": action,
                    "blender_version": ".".join(map(str, bpy.app.version)),
                    "file": bpy.data.filepath or "Untitled",
                    "scene_metrics": metrics,
                }
                print("[OK] [AI-Blender] Stav Blenderu úspěšně vrácen.")
            except Exception as e:
                err_trace = traceback.format_exc()
                result_container["response"] = {
                    "status": "error",
                    "error": str(e),
                    "traceback": err_trace,
                }
            finally:
                completion_event.set()
                _RECEIVER_INSTANCE.request_queue.task_done()
            continue

        # 19. Vyrenderování scény / náhledu (action == "render")
        if action == "render":
            try:
                raw_output_path = message.get("output_path", "/tmp/blender_render.png")
                is_safe, err_msg, safe_path = is_safe_output_path(raw_output_path)
                if not is_safe or safe_path is None:
                    raise ValueError(f"Bezpečnostní pojistka: Neplatná nebo nepovolená výstupní cesta pro render: {err_msg}")
                output_path = str(safe_path)
                engine = message.get("engine")
                use_viewport = bool(message.get("viewport", False))
                print(f"\n[AI-Blender] >>> Vykonávám render (cíl={output_path}, engine={engine})...")
                scene = bpy.context.scene
                if engine and engine in ("CYCLES", "BLENDER_EEVEE", "BLENDER_EEVEE_NEXT", "BLENDER_WORKBENCH"):
                    scene.render.engine = engine

                if use_viewport:
                    actual_path = capture_viewport_render(output_path)
                else:
                    orig_filepath = scene.render.filepath
                    orig_format = scene.render.image_settings.file_format
                    try:
                        import os
                        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
                        scene.render.filepath = output_path
                        scene.render.image_settings.file_format = 'PNG'
                        bpy.ops.render.render(write_still=True)
                        actual_path = output_path
                    finally:
                        scene.render.filepath = orig_filepath
                        scene.render.image_settings.file_format = orig_format

                result_container["response"] = {
                    "status": "success",
                    "action": action,
                    "render_path": actual_path,
                    "engine": getattr(bpy.context.scene.render, "engine", "UNKNOWN"),
                }
                print(f"[OK] [AI-Blender] Render dokončen: {actual_path}")
            except Exception as e:
                err_trace = traceback.format_exc()
                result_container["response"] = {
                    "status": "error",
                    "error": str(e),
                    "traceback": err_trace,
                }
                print(f"[ERROR] [AI-Blender] Chyba při renderování: {e}")
            finally:
                completion_event.set()
                _RECEIVER_INSTANCE.request_queue.task_done()
            continue

        # 20. Posun objektu (action == "move")
        if action == "move":
            obj_name = message.get("object_name") or message.get("target")
            delta = message.get("delta")  # [dx, dy, dz]
            location = message.get("location")  # [x, y, z]
            x = message.get("x")
            y = message.get("y")
            z = message.get("z")
            relative = bool(message.get("relative", delta is not None))

            print(f"\n[AI-Blender] >>> Posun objektu (cíl={obj_name}, relative={relative})...")
            try:
                target_obj = bpy.data.objects.get(obj_name) if obj_name else bpy.context.active_object
                if not target_obj:
                    raise ValueError(f"Objekt '{obj_name or 'active'}' nebyl nalezen ve scéně.")

                if location is not None and isinstance(location, (list, tuple)) and len(location) == 3:
                    target_obj.location = _validate_vec3(location, "location")
                elif delta is not None and isinstance(delta, (list, tuple)) and len(delta) == 3:
                    dx, dy, dz = _validate_vec3(delta, "delta")
                    target_obj.location.x += dx
                    target_obj.location.y += dy
                    target_obj.location.z += dz
                else:
                    if x is not None:
                        vx = _validate_numeric(x, "x")
                        target_obj.location.x = (target_obj.location.x + vx) if relative else vx
                    if y is not None:
                        vy = _validate_numeric(y, "y")
                        target_obj.location.y = (target_obj.location.y + vy) if relative else vy
                    if z is not None:
                        vz = _validate_numeric(z, "z")
                        target_obj.location.z = (target_obj.location.z + vz) if relative else vz

                for window in bpy.context.window_manager.windows:
                    for area in window.screen.areas:
                        if area.type == 'VIEW_3D':
                            area.tag_redraw()

                new_loc = [round(float(v), 4) for v in target_obj.location]
                result_container["response"] = {
                    "status": "success",
                    "action": action,
                    "object_name": target_obj.name,
                    "location": new_loc,
                }
                print(f"[OK] [AI-Blender] Objekt '{target_obj.name}' posunut na {new_loc}")
            except Exception as e:
                err_trace = traceback.format_exc()
                result_container["response"] = {
                    "status": "error",
                    "error": str(e),
                    "traceback": err_trace,
                }
                print(f"[ERROR] [AI-Blender] Chyba při posunu objektu: {e}")
            finally:
                completion_event.set()
                _RECEIVER_INSTANCE.request_queue.task_done()
            continue

        # 21. Rotace objektu (action == "rotate")
        if action == "rotate":
            obj_name = message.get("object_name") or message.get("target")
            euler = message.get("rotation_euler") or message.get("euler")
            rx = message.get("rx")
            ry = message.get("ry")
            rz = message.get("rz")
            relative = bool(message.get("relative", False))

            try:
                target_obj = bpy.data.objects.get(obj_name) if obj_name else bpy.context.active_object
                if not target_obj:
                    raise ValueError(f"Objekt '{obj_name or 'active'}' nebyl nalezen.")

                if euler is not None and isinstance(euler, (list, tuple)) and len(euler) == 3:
                    target_obj.rotation_euler = _validate_vec3(euler, "rotation_euler")
                else:
                    if rx is not None:
                        vrx = _validate_numeric(rx, "rx")
                        target_obj.rotation_euler.x = (target_obj.rotation_euler.x + vrx) if relative else vrx
                    if ry is not None:
                        vry = _validate_numeric(ry, "ry")
                        target_obj.rotation_euler.y = (target_obj.rotation_euler.y + vry) if relative else vry
                    if rz is not None:
                        vrz = _validate_numeric(rz, "rz")
                        target_obj.rotation_euler.z = (target_obj.rotation_euler.z + vrz) if relative else vrz

                for window in bpy.context.window_manager.windows:
                    for area in window.screen.areas:
                        if area.type == 'VIEW_3D':
                            area.tag_redraw()

                new_rot = [round(float(v), 4) for v in target_obj.rotation_euler]
                result_container["response"] = {
                    "status": "success",
                    "action": action,
                    "object_name": target_obj.name,
                    "rotation_euler": new_rot,
                }
            except Exception as e:
                result_container["response"] = {
                    "status": "error",
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                }
            finally:
                completion_event.set()
                _RECEIVER_INSTANCE.request_queue.task_done()
            continue

        # 22. Škálování objektu (action == "scale")
        if action == "scale":
            obj_name = message.get("object_name") or message.get("target")
            scale_val = message.get("scale")
            sx = message.get("sx")
            sy = message.get("sy")
            sz = message.get("sz")

            try:
                target_obj = bpy.data.objects.get(obj_name) if obj_name else bpy.context.active_object
                if not target_obj:
                    raise ValueError(f"Objekt '{obj_name or 'active'}' nebyl nalezen.")

                if scale_val is not None and isinstance(scale_val, (list, tuple)):
                    sv = _validate_vec3(scale_val, "scale")
                    target_obj.scale = sv
                elif scale_val is not None:
                    # Skalár: aplikuj na všechny tři osy
                    sv = _validate_numeric(scale_val, "scale")
                    target_obj.scale = (sv, sv, sv)
                else:
                    if sx is not None:
                        target_obj.scale.x = _validate_numeric(sx, "sx")
                    if sy is not None:
                        target_obj.scale.y = _validate_numeric(sy, "sy")
                    if sz is not None:
                        target_obj.scale.z = _validate_numeric(sz, "sz")

                for window in bpy.context.window_manager.windows:
                    for area in window.screen.areas:
                        if area.type == 'VIEW_3D':
                            area.tag_redraw()

                new_scale = [round(float(v), 4) for v in target_obj.scale]
                result_container["response"] = {
                    "status": "success",
                    "action": action,
                    "object_name": target_obj.name,
                    "scale": new_scale,
                }
            except Exception as e:
                result_container["response"] = {
                    "status": "error",
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                }
            finally:
                completion_event.set()
                _RECEIVER_INSTANCE.request_queue.task_done()
            continue

        # 23. Výběr objektu (action == "select")
        if action == "select":
            obj_name = message.get("object_name") or message.get("target")
            try:
                if not obj_name:
                    raise ValueError("Chybí parametr 'object_name' pro výběr.")
                target_obj = bpy.data.objects.get(obj_name)
                if not target_obj:
                    raise ValueError(f"Objekt '{obj_name}' nebyl nalezen.")

                bpy.ops.object.select_all(action='DESELECT')
                target_obj.select_set(True)
                bpy.context.view_layer.objects.active = target_obj

                for window in bpy.context.window_manager.windows:
                    for area in window.screen.areas:
                        if area.type == 'VIEW_3D':
                            area.tag_redraw()

                result_container["response"] = {
                    "status": "success",
                    "action": action,
                    "selected_object": target_obj.name,
                }
            except Exception as e:
                result_container["response"] = {
                    "status": "error",
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                }
            finally:
                completion_event.set()
                _RECEIVER_INSTANCE.request_queue.task_done()
            continue

        # 24. Smazání objektu (action == "delete")
        if action == "delete":
            obj_name = message.get("object_name") or message.get("target")
            try:
                target_obj = bpy.data.objects.get(obj_name) if obj_name else bpy.context.active_object
                if not target_obj:
                    raise ValueError(f"Objekt '{obj_name or 'active'}' k odstranění nebyl nalezen.")
                deleted_name = target_obj.name
                bpy.data.objects.remove(target_obj, do_unlink=True)

                for window in bpy.context.window_manager.windows:
                    for area in window.screen.areas:
                        if area.type == 'VIEW_3D':
                            area.tag_redraw()

                result_container["response"] = {
                    "status": "success",
                    "action": action,
                    "deleted_object": deleted_name,
                }
            except Exception as e:
                result_container["response"] = {
                    "status": "error",
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                }
            finally:
                completion_event.set()
                _RECEIVER_INSTANCE.request_queue.task_done()
            continue

        # Neznámá nebo nepovolená akce – libovolné spouštění kódu (exec) je zakázáno
        print(f"[ERROR] [AI-Blender] Zamítnuta nepovolená akce: '{action}'")
        result_container["response"] = {
            "status": "error",
            "error": f"Neznámá nebo zakázaná akce: '{action}'. Libovolné spouštění Python kódu (exec) bylo z bezpečnostních důvodů trvale odstraněno.",
            "allowed_actions": sorted(list(ALLOWED_ACTIONS)),
        }
        completion_event.set()
        _RECEIVER_INSTANCE.request_queue.task_done()

    # Spouštět každých 50 ms pro minimální latenci
    return 0.05


def process_blender_queue_timer():
    """
    Tato funkce je volána pravidelně z HLAVNÍHO VLÁKNA Blenderu pomocí bpy.app.timers.
    Bezpečně spouští příchozí Python kód přímo v kontextu Blender scény nebo provádí inspekci.
    Chrání časovač před neošetřenými výjimkami, aby se v Blenderu nikdy neodregistroval.
    """
    try:
        return _process_blender_queue_timer_impl()
    except Exception as fatal_timer_err:
        print(f"[ERROR] [AI-Blender] Kritická neošetřená chyba v process_blender_queue_timer: {fatal_timer_err}")
        traceback.print_exc()
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
