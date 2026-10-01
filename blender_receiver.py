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
                print(f"✅ [AI-Blender] Mesh Doctor AUDIT dokončen: {audit_result}")

            except Exception as e:
                err_trace = traceback.format_exc()
                result_container["response"] = {
                    "status": "error",
                    "error": str(e),
                    "traceback": err_trace,
                }
                print(f"❌ [AI-Blender] Chyba při Mesh Doctor AUDIT: {e}")
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
                print(f"✅ [AI-Blender] Mesh Doctor REPAIR dokončen: watertight={is_watertight_after}")

            except Exception as e:
                err_trace = traceback.format_exc()
                result_container["response"] = {
                    "status": "error",
                    "error": str(e),
                    "traceback": err_trace,
                }
                print(f"❌ [AI-Blender] Chyba při Mesh Doctor REPAIR: {e}")
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
                print(f"✅ [AI-Blender] Product Viz Studio vytvořeno: styl='{style}', "
                      f"měřítko={scale:.2f}m, světla={len(lights_created)}")

            except Exception as e:
                err_trace = traceback.format_exc()
                result_container["response"] = {
                    "status": "error",
                    "error": str(e),
                    "traceback": err_trace,
                }
                print(f"❌ [AI-Blender] Chyba při Product Viz Studio: {e}")
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
                print(f"✅ [AI-Blender] Procedural Shader '{mat.name}' ({shader_type}) vytvořen s {len(created_nodes_summary)} uzly.")

            except Exception as e:
                err_trace = traceback.format_exc()
                result_container["response"] = {
                    "status": "error",
                    "error": str(e),
                    "traceback": err_trace,
                }
                print(f"❌ [AI-Blender] Chyba při Procedural Shader: {e}")
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
                print(f"✅ [AI-Blender] UV Texel Audit dokončen pro '{active_obj.name}': TD={metrics.get('texel_density_px_cm')} px/cm, coverage={metrics.get('uv_space_coverage_pct')}%")

            except Exception as e:
                err_trace = traceback.format_exc()
                result_container["response"] = {
                    "status": "error",
                    "error": str(e),
                    "traceback": err_trace,
                }
                print(f"❌ [AI-Blender] Chyba při UV Texel Audit: {e}")
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
                print(f"✅ [AI-Blender] Smart UV Pack dokončen: TD={final_metrics.get('texel_density_px_cm')} px/cm, islands={final_metrics.get('uv_islands_count')}, coverage={final_metrics.get('uv_space_coverage_pct')}%")

            except Exception as e:
                err_trace = traceback.format_exc()
                result_container["response"] = {
                    "status": "error",
                    "error": str(e),
                    "traceback": err_trace,
                }
                print(f"❌ [AI-Blender] Chyba při Smart UV Pack: {e}")
                print(err_trace)
            finally:
                completion_event.set()
                _RECEIVER_INSTANCE.request_queue.task_done()
            continue

        # 8. Vykonání Python kódu (action == 'execute')

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
