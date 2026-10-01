"""
Modul pro síťovou komunikaci s 3D modelovacím softwarem Blender přes lokální TCP socket.
Umožňuje asistentovi odesílat vygenerovaný Python (bpy) kód přímo do běžící instance Blenderu.
"""

import json
import logging
import socket
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_BLENDER_HOST = "127.0.0.1"
DEFAULT_BLENDER_PORT = 9876
DEFAULT_TIMEOUT = 5.0


def is_blender_available(host: str = DEFAULT_BLENDER_HOST, port: int = DEFAULT_BLENDER_PORT) -> bool:
    """
    Rychle ověří, zda na zadané adrese a portu naslouchá přijímací skript v Blenderu.
    """
    try:
        with socket.create_connection((host, port), timeout=0.6):
            return True
    except (OSError, socket.error):
        return False


def ping_blender(host: str = DEFAULT_BLENDER_HOST, port: int = DEFAULT_BLENDER_PORT) -> dict[str, Any]:
    """
    Odešle ping požadavek a vrátí informace o instanci Blenderu (verze atd.).
    """
    try:
        with socket.create_connection((host, port), timeout=2.0) as sock:
            payload = json.dumps({"action": "ping"}) + "\n"
            sock.sendall(payload.encode("utf-8"))

            data = b""
            while not data.endswith(b"\n"):
                chunk = sock.recv(1024)
                if not chunk:
                    break
                data += chunk

            if data:
                return json.loads(data.decode("utf-8"))
            return {"status": "error", "message": "Prázdná odpověď od Blenderu."}
    except Exception as e:
        return {"status": "error", "message": f"Blender neodpovídá: {e}"}


import traceback


class BlenderExecutionError(Exception):
    """Výjimka vyvolaná při chybě spuštění kódu nebo selhání komunikace s Blenderem."""

    def __init__(
        self,
        message: str,
        error: str = "",
        traceback_str: str = "",
        response: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.error = error or message
        self.traceback = traceback_str
        self.response = response or {}


def send_code_to_blender(
    code: str,
    host: str = DEFAULT_BLENDER_HOST,
    port: int = DEFAULT_BLENDER_PORT,
    timeout: float = DEFAULT_TIMEOUT,
    raise_on_error: bool = False,
) -> dict[str, Any]:
    """
    Odešle Python kód do Blenderu k bezpečnému spuštění v hlavním vlákně Blenderu.
    Čte strukturovanou JSON odpověď od Blenderu.
    
    Vrací slovník s výsledkem:
    - {"status": "success", "output": "..."} při úspěchu
    - {"status": "error", "error": "...", "traceback": "...", "detail": "..."} při chybě

    Pokud je nastaveno raise_on_error=True a přijde chyba, vyvolá výjimku BlenderExecutionError.
    """
    if not code or not code.strip():
        err_dict = {
            "status": "error",
            "error": "EmptyCodeError",
            "traceback": "",
            "message": "Kód k odeslání je prázdný.",
            "detail": "Kód k odeslání je prázdný.",
        }
        if raise_on_error:
            raise BlenderExecutionError("Kód k odeslání je prázdný.", response=err_dict)
        return err_dict

    sock = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, port))

        request_payload = {
            "action": "execute",
            "code": code.strip(),
        }
        raw_msg = json.dumps(request_payload) + "\n"
        sock.sendall(raw_msg.encode("utf-8"))

        response_bytes = b""
        while not response_bytes.endswith(b"\n"):
            chunk = sock.recv(4096)
            if not chunk:
                break
            response_bytes += chunk

        if not response_bytes:
            msg = "Blender spojení uzavřel bez odpovědi."
            err_dict = {
                "status": "error",
                "error": "ConnectionClosedWithoutResponse",
                "traceback": "",
                "message": msg,
                "detail": msg,
            }
            if raise_on_error:
                raise BlenderExecutionError(msg, response=err_dict)
            return err_dict

        response: dict[str, Any] = json.loads(response_bytes.decode("utf-8"))
        status = response.get("status", "unknown")
        logger.info("Přijata odpověď od Blenderu: status=%s", status)

        if status == "error":
            err_msg = response.get("error", "Neznámá chyba v Blenderu")
            tb = response.get("traceback") or response.get("trace", "")
            detailed_err = f"{err_msg}\n{tb}".strip() if tb else err_msg
            response["detail"] = detailed_err
            if "message" not in response:
                response["message"] = err_msg
            logger.error("Chyba při vykonávání v Blenderu: %s\n%s", err_msg, tb)
            if raise_on_error:
                raise BlenderExecutionError(
                    detailed_err,
                    error=err_msg,
                    traceback_str=tb,
                    response=response,
                )

        return response

    except (ConnectionRefusedError, ConnectionResetError):
        logger.warning("Připojení k Blenderu na %s:%d bylo odmítnuto.", host, port)
        msg = (
            f"Nelze se spojit s Blenderem na {host}:{port}. "
            "Ujistěte se, že Blender běží a v Text Editoru má spuštěný skript 'blender_receiver.py'."
        )
        res = {
            "status": "error",
            "error_type": "ConnectionRefused",
            "error": "ConnectionRefused: Nelze se připojit k Blenderu",
            "traceback": "",
            "message": msg,
            "detail": msg,
        }
        if raise_on_error:
            raise BlenderExecutionError(msg, error="ConnectionRefused", response=res)
        return res
    except socket.timeout:
        logger.error("Vypršel časový limit při čekání na odpověď od Blenderu.")
        msg = f"Vypršel časový limit ({timeout} s) při vykonávání kódu v Blenderu."
        res = {
            "status": "error",
            "error_type": "Timeout",
            "error": "TimeoutError: Vypršel časový limit operace",
            "traceback": "",
            "message": msg,
            "detail": msg,
        }
        if raise_on_error:
            raise BlenderExecutionError(msg, error="Timeout", response=res)
        return res
    except BlenderExecutionError:
        raise
    except Exception as exc:
        logger.exception("Chyba při komunikaci s Blenderem: %s", exc)
        tb = traceback.format_exc()
        msg = f"Chyba při komunikaci s Blenderem: {exc}"
        res = {
            "status": "error",
            "error_type": "CommunicationError",
            "error": str(exc),
            "traceback": tb,
            "message": msg,
            "detail": f"{msg}\n{tb}".strip(),
        }
        if raise_on_error:
            raise BlenderExecutionError(msg, error=str(exc), traceback_str=tb, response=res)
        return res
    finally:
        if sock is not None:
            try:
                sock.close()
            except Exception:
                pass


def request_scene_inspection(
    host: str = DEFAULT_BLENDER_HOST,
    port: int = DEFAULT_BLENDER_PORT,
    output_path: str = "/tmp/blender_viewport.png",
    timeout: float = 12.0,
    raise_on_error: bool = False,
) -> dict[str, Any]:
    """
    Odešle do Blenderu požadavek na inspekci scény a pořízení snímku viewportu (action: inspect_scene).
    
    Vrací strukturovaný slovník s telemetrií a cestou ke snímku:
    - {"status": "success", "scene_metrics": {...}, "screenshot_path": "/tmp/blender_viewport.png"}
    - {"status": "error", "error": "...", "traceback": "...", "detail": "..."} při chybě

    Pokud je nastaveno raise_on_error=True a přijde chyba, vyvolá výjimku BlenderExecutionError.
    """
    sock = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, port))

        request_payload = {
            "action": "inspect_scene",
            "output_path": output_path,
        }
        raw_msg = json.dumps(request_payload) + "\n"
        sock.sendall(raw_msg.encode("utf-8"))

        response_bytes = b""
        while not response_bytes.endswith(b"\n"):
            chunk = sock.recv(4096)
            if not chunk:
                break
            response_bytes += chunk

        if not response_bytes:
            msg = "Blender spojení uzavřel bez odpovědi na inspekci scény."
            err_dict = {
                "status": "error",
                "error": "ConnectionClosedWithoutResponse",
                "traceback": "",
                "message": msg,
                "detail": msg,
            }
            if raise_on_error:
                raise BlenderExecutionError(msg, response=err_dict)
            return err_dict

        response: dict[str, Any] = json.loads(response_bytes.decode("utf-8"))
        status = response.get("status", "unknown")
        logger.info("Přijata odpověď inspekce od Blenderu: status=%s", status)

        if status == "error":
            err_msg = response.get("error", "Chyba při inspekci scény v Blenderu")
            tb = response.get("traceback") or response.get("trace", "")
            detailed_err = f"{err_msg}\n{tb}".strip() if tb else err_msg
            response["detail"] = detailed_err
            if "message" not in response:
                response["message"] = err_msg
            logger.error("Chyba při inspekci scény v Blenderu: %s\n%s", err_msg, tb)
            if raise_on_error:
                raise BlenderExecutionError(
                    detailed_err,
                    error=err_msg,
                    traceback_str=tb,
                    response=response,
                )

        return response

    except (ConnectionRefusedError, ConnectionResetError):
        logger.warning("Připojení k Blenderu na %s:%d bylo odmítnuto.", host, port)
        msg = (
            f"Nelze se spojit s Blenderem na {host}:{port}. "
            "Ujistěte se, že Blender běží a v Text Editoru má spuštěný skript 'blender_receiver.py'."
        )
        res = {
            "status": "error",
            "error_type": "ConnectionRefused",
            "error": "ConnectionRefused: Nelze se připojit k Blenderu",
            "traceback": "",
            "message": msg,
            "detail": msg,
        }
        if raise_on_error:
            raise BlenderExecutionError(msg, error="ConnectionRefused", response=res)
        return res
    except socket.timeout:
        logger.error("Vypršel časový limit při čekání na inspekci scény z Blenderu.")
        msg = f"Vypršel časový limit ({timeout} s) při inspekci scény v Blenderu."
        res = {
            "status": "error",
            "error_type": "Timeout",
            "error": "TimeoutError: Vypršel časový limit operace",
            "traceback": "",
            "message": msg,
            "detail": msg,
        }
        if raise_on_error:
            raise BlenderExecutionError(msg, error="Timeout", response=res)
        return res
    except BlenderExecutionError:
        raise
    except Exception as exc:
        logger.exception("Chyba při komunikaci s Blenderem během inspekce: %s", exc)
        tb = traceback.format_exc()
        msg = f"Chyba při komunikaci s Blenderem: {exc}"
        res = {
            "status": "error",
            "error_type": "CommunicationError",
            "error": str(exc),
            "traceback": tb,
            "message": msg,
            "detail": f"{msg}\n{tb}".strip(),
        }
        if raise_on_error:
            raise BlenderExecutionError(msg, error=str(exc), traceback_str=tb, response=res)
        return res
    finally:
        if sock is not None:
            try:
                sock.close()
            except Exception:
                pass


def _send_blender_request(
    payload: dict[str, Any],
    host: str = DEFAULT_BLENDER_HOST,
    port: int = DEFAULT_BLENDER_PORT,
    timeout: float = 20.0,
    raise_on_error: bool = False,
) -> dict[str, Any]:
    """
    Interní helper: odešle libovolný JSON payload do Blenderu a vrátí JSON odpověď.
    Sdílená logika pro všechny speciální akce (audit, repair, …).
    """
    sock = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, port))

        raw_msg = json.dumps(payload) + "\n"
        sock.sendall(raw_msg.encode("utf-8"))

        response_bytes = b""
        while not response_bytes.endswith(b"\n"):
            chunk = sock.recv(4096)
            if not chunk:
                break
            response_bytes += chunk

        if not response_bytes:
            msg = "Blender spojení uzavřel bez odpovědi."
            err = {
                "status": "error",
                "error": "ConnectionClosedWithoutResponse",
                "traceback": "",
                "message": msg,
                "detail": msg,
            }
            if raise_on_error:
                raise BlenderExecutionError(msg, response=err)
            return err

        response: dict[str, Any] = json.loads(response_bytes.decode("utf-8"))
        status = response.get("status", "unknown")
        logger.info(
            "Přijata odpověď od Blenderu (action=%s): status=%s",
            payload.get("action"),
            status,
        )

        if status == "error":
            err_msg = response.get("error", "Neznámá chyba v Blenderu")
            tb = response.get("traceback") or response.get("trace", "")
            detailed_err = f"{err_msg}\n{tb}".strip() if tb else err_msg
            response.setdefault("detail", detailed_err)
            response.setdefault("message", err_msg)
            logger.error(
                "Chyba Blender akce '%s': %s\n%s", payload.get("action"), err_msg, tb
            )
            if raise_on_error:
                raise BlenderExecutionError(
                    detailed_err, error=err_msg, traceback_str=tb, response=response
                )

        return response

    except (ConnectionRefusedError, ConnectionResetError):
        logger.warning("Připojení k Blenderu na %s:%d bylo odmítnuto.", host, port)
        msg = (
            f"Nelze se spojit s Blenderem na {host}:{port}. "
            "Ujistěte se, že Blender běží a v Text Editoru má spuštěný skript 'blender_receiver.py'."
        )
        res = {
            "status": "error",
            "error_type": "ConnectionRefused",
            "error": "ConnectionRefused: Nelze se připojit k Blenderu",
            "traceback": "",
            "message": msg,
            "detail": msg,
        }
        if raise_on_error:
            raise BlenderExecutionError(msg, error="ConnectionRefused", response=res)
        return res
    except socket.timeout:
        logger.error(
            "Vypršel časový limit při akci '%s' v Blenderu.", payload.get("action")
        )
        msg = f"Vypršel časový limit ({timeout} s) při komunikaci s Blenderem."
        res = {
            "status": "error",
            "error_type": "Timeout",
            "error": "TimeoutError: Vypršel časový limit operace",
            "traceback": "",
            "message": msg,
            "detail": msg,
        }
        if raise_on_error:
            raise BlenderExecutionError(msg, error="Timeout", response=res)
        return res
    except BlenderExecutionError:
        raise
    except Exception as exc:
        logger.exception("Chyba při komunikaci s Blenderem: %s", exc)
        import traceback as _tb

        tb = _tb.format_exc()
        msg = f"Chyba při komunikaci s Blenderem: {exc}"
        res = {
            "status": "error",
            "error_type": "CommunicationError",
            "error": str(exc),
            "traceback": tb,
            "message": msg,
            "detail": f"{msg}\n{tb}".strip(),
        }
        if raise_on_error:
            raise BlenderExecutionError(
                msg, error=str(exc), traceback_str=tb, response=res
            )
        return res
    finally:
        if sock is not None:
            try:
                sock.close()
            except Exception:
                pass


def request_mesh_audit(
    host: str = DEFAULT_BLENDER_HOST,
    port: int = DEFAULT_BLENDER_PORT,
    timeout: float = 20.0,
    raise_on_error: bool = False,
) -> dict[str, Any]:
    """
    Odešle do Blenderu požadavek na audit topologie aktivního síťového objektu
    (action: mesh_doctor_audit).

    Vrací strukturovaný slovník s metrikami sítě:
    {
        "status": "success",
        "action": "mesh_doctor_audit",
        "audit": {
            "object_name": str,
            "mesh_name": str,
            "total_vertices": int,
            "total_edges": int,
            "total_faces": int,
            "triangles": int,
            "ngons": int,
            "non_manifold_edges": int,
            "loose_vertices": int,
            "loose_edges": int,
            "boundary_edges_holes": int,
            "potentially_flipped_faces": int,
            "is_watertight": bool,
            "print_ready": bool,
        }
    }
    """
    payload = {"action": "mesh_doctor_audit"}
    return _send_blender_request(
        payload, host=host, port=port, timeout=timeout, raise_on_error=raise_on_error
    )


def request_mesh_repair(
    host: str = DEFAULT_BLENDER_HOST,
    port: int = DEFAULT_BLENDER_PORT,
    merge_distance: float = 0.0001,
    timeout: float = 25.0,
    raise_on_error: bool = False,
) -> dict[str, Any]:
    """
    Odešle do Blenderu požadavek na automatickou opravu aktivního síťového objektu
    (action: mesh_doctor_repair).

    Opravy zahrnují:
    1. Merge by distance (sloučení duplicitních vrcholů)
    2. Delete loose geometry (smazání volných vrcholů a hran)
    3. Recalculate Normals Outside (přepočet normál směrem ven)

    Vrací stav úspěšnosti a statistiky sítě po opravě:
    {
        "status": "success",
        "action": "mesh_doctor_repair",
        "repairs_applied": [...],
        "post_repair_stats": { ... }
    }

    Args:
        merge_distance: Práh pro sloučení vrcholů v metrech.
                        Výchozí: 0.0001 m (= 0.1 mm) – vhodné pro 3D tisk.
    """
    payload = {"action": "mesh_doctor_repair", "merge_distance": merge_distance}
    return _send_blender_request(
        payload, host=host, port=port, timeout=timeout, raise_on_error=raise_on_error
    )



def request_product_studio(
    host: str = DEFAULT_BLENDER_HOST,
    port: int = DEFAULT_BLENDER_PORT,
    style: str = "standard",
    timeout: float = 30.0,
    raise_on_error: bool = False,
) -> dict[str, Any]:
    """
    Odešle do Blenderu požadavek na vytvoření kompletního produktového prezentačního studia
    (action: create_product_studio).

    Studio zahrnuje:
    - Zakřivené hladké pozadí (backdrop) s SimpleDeform(Bend) + Solidify + Bevel modifikátory
    - Tříbodové AREA osvětlení (Key / Fill / Rim light) s nastavenou barvou a měkkostí
    - Kameru s ohniskovou vzdáleností 85mm namířenou na aktivní objekt
    - Render nastavení 2048×2048 px (Cycles pokud dostupný)

    Args:
        style: Osvětlovací styl prezentace:
               - "standard"  -- Neutrální bílé studio, vyvážené světlo (výchozí)
               - "dramatic"  -- Vysoký kontrast, teplý key light, slabý fill
               - "soft"      -- Jemné přesvětlení, velké difuzní plochy

    Vrací strukturovaný slovník se seznamem vytvořených objektů (backdrop, světla, kamera).
    """
    if style not in ("standard", "dramatic", "soft"):
        style = "standard"
    payload = {"action": "create_product_studio", "style": style}
    return _send_blender_request(
        payload, host=host, port=port, timeout=timeout, raise_on_error=raise_on_error
    )


def request_procedural_shader(
    material_name: str | None = None,
    shader_type: str = "brushed_metal",
    host: str = DEFAULT_BLENDER_HOST,
    port: int = DEFAULT_BLENDER_PORT,
    timeout: float = 25.0,
    raise_on_error: bool = False,
) -> dict[str, Any]:
    """
    Odešle do Blenderu požadavek na programové vygenerování procedurálního materiálu
    (action: create_procedural_shader).

    Vytvoří kompletní node tree s Principled BSDF, procedurálními texturami (Noise, Bump, ColorRamp, Mapping)
    a přiřadí materiál k aktivnímu MESH objektu.

    Args:
        material_name: Vlastní název materiálu (volitelný, např. 'Titanium_Brushed').
        shader_type: Typ procedurálního materiálu:
                     - "brushed_metal"  -- Kartáčovaný kov (anizotropní šum, metallic=1.0)
                     - "matte_plastic"  -- Matný prémiový polymer (mikrotextura bump, roughness=0.45)
                     - "rusted_iron"    -- Zkorodované železo (kombinace kovu a texturované rzi)
                     - "glossy_glass"   -- Optické čiré sklo (transmission=1.0, ior=1.52)

    Vrací strukturovaný slovník:
    {
        "status": "success",
        "action": "create_procedural_shader",
        "shader": {
            "material_name": str,
            "shader_type": str,
            "assigned_to_object": str | None,
            "node_count": int,
            "link_count": int,
            "nodes": list[dict],
            "key_parameters": dict,
        }
    }
    """
    valid_types = ("brushed_metal", "matte_plastic", "rusted_iron", "glossy_glass")
    clean_type = shader_type.lower().strip() if shader_type else "brushed_metal"
    if clean_type not in valid_types:
        clean_type = "brushed_metal"

    payload: dict[str, Any] = {
        "action": "create_procedural_shader",
        "shader_type": clean_type,
    }
    if material_name and material_name.strip():
        payload["material_name"] = material_name.strip()

    return _send_blender_request(
        payload, host=host, port=port, timeout=timeout, raise_on_error=raise_on_error
    )


def request_uv_audit(
    host: str = DEFAULT_BLENDER_HOST,
    port: int = DEFAULT_BLENDER_PORT,
    texture_res: int = 2048,
    timeout: float = 20.0,
    raise_on_error: bool = False,
) -> dict[str, Any]:
    """
    Odešle do Blenderu požadavek na audit UV mapy a texel density aktivního objektu
    (action: uv_texel_audit).

    Vrací strukturovaný slovník:
    {
        "status": "success",
        "action": "uv_texel_audit",
        "metrics": {
            "has_uv": bool,
            "object_name": str,
            "texture_resolution": int,
            "total_3d_area_m2": float,
            "total_uv_area": float,
            "uv_space_coverage_pct": float,
            "texel_density_px_m": float,
            "texel_density_px_cm": float,
            "uv_islands_count": int,
            "flipped_faces_count": int,
            "potential_overlaps": bool,
        }
    }
    """
    payload = {
        "action": "uv_texel_audit",
        "texture_res": texture_res,
    }
    return _send_blender_request(
        payload, host=host, port=port, timeout=timeout, raise_on_error=raise_on_error
    )


def request_uv_pack(
    target_texel_density: float = 10.24,
    margin: float = 0.01,
    angle_limit: float = 66.0,
    texture_res: int = 2048,
    host: str = DEFAULT_BLENDER_HOST,
    port: int = DEFAULT_BLENDER_PORT,
    timeout: float = 30.0,
    raise_on_error: bool = False,
) -> dict[str, Any]:
    """
    Odešle do Blenderu požadavek na automatické rozbalení (Smart UV), sjednocení texel density
    na cílovou hodnotu a zabalení UV ostrovů (action: smart_uv_pack).

    Args:
        target_texel_density: Cílová texel density v px/cm (výchozí: 10.24 px/cm = standard pro 2K mapu na 2m model).
        margin: Odsazení mezi UV ostrovy v relativních jednotkách (výchozí: 0.01 = 1% UV padding).
        angle_limit: Úhlový limit pro rozdělení švů ve stupních (výchozí: 66.0°).
        texture_res: Referenční rozlišení textury v px (výchozí: 2048).

    Vrací strukturovaný slovník:
    {
        "status": "success",
        "action": "smart_uv_pack",
        "target_texel_density": float,
        "margin": float,
        "angle_limit": float,
        "scaled_to_target": bool,
        "post_pack_metrics": dict,
    }
    """
    payload = {
        "action": "smart_uv_pack",
        "target_texel_density": float(target_texel_density),
        "margin": float(margin),
        "angle_limit": float(angle_limit),
        "texture_res": int(texture_res),
    }
    return _send_blender_request(
        payload, host=host, port=port, timeout=timeout, raise_on_error=raise_on_error
    )


def request_parametric_model(
    model_type: str = "enclosure",
    dimensions: dict[str, Any] | None = None,
    host: str = DEFAULT_BLENDER_HOST,
    port: int = DEFAULT_BLENDER_PORT,
    timeout: float = 25.0,
    raise_on_error: bool = False,
) -> dict[str, Any]:
    """
    Odešle do Blenderu požadavek na vytvoření parametrického modelu (action: generate_parametric_model).

    Args:
        model_type: Typ parametrického tvaru ("enclosure", "gear", "bracket").
        dimensions: Volitelný slovník rozměrů (v metrech nebo počtech prvků):
                    - enclosure: width, depth, height, wall_thickness
                    - gear: teeth_count, radius, tooth_depth, thickness, bore_radius
                    - bracket: width, leg1_length, leg2_length, thickness, hole_radius

    Vrací strukturovaný slovník:
    {
        "status": "success",
        "action": "generate_parametric_model",
        "model": {
            "object_name": str,
            "model_type": str,
            "dimensions": dict,
            "vertex_count": int,
            "polygon_count": int,
            "modifiers": list[str],
        }
    }
    """
    clean_type = (model_type or "enclosure").lower().strip()
    payload = {
        "action": "generate_parametric_model",
        "model_type": clean_type,
        "dimensions": dimensions or {},
    }
    return _send_blender_request(
        payload, host=host, port=port, timeout=timeout, raise_on_error=raise_on_error
    )


def request_modifier_stack(
    stack_type: str = "hard_surface",
    params: dict[str, Any] | None = None,
    apply_immediately: bool = False,
    host: str = DEFAULT_BLENDER_HOST,
    port: int = DEFAULT_BLENDER_PORT,
    timeout: float = 25.0,
    raise_on_error: bool = False,
) -> dict[str, Any]:
    """
    Odešle do Blenderu požadavek na aplikaci profesionálního řetězce modifikátorů
    na aktivní objekt (action: apply_modifier_stack).

    Args:
        stack_type: Typ řetězce modifikátorů:
                    - "hard_surface": Bevel (úhlové omezení) + Weighted Normal pro dokonalý shading
                    - "clean_solidify": Solidify s rovnoměrnou tloušťkou + sražení hran
                    - "subdivision_bevel": Bevel + Subsurf pro hi-poly modelování
        params: Volitelné parametry modifikátorů (např. bevel_width, bevel_segments, thickness).
        apply_immediately: Zda modifikátory okamžitě zapsat (apply) do geometrie (výchozí: False).

    Vrací strukturovaný slovník:
    {
        "status": "success",
        "action": "apply_modifier_stack",
        "object_name": str,
        "stack_type": str,
        "applied_immediately": bool,
        "modifiers_count": int,
        "modifiers": list[dict],
    }
    """
    clean_type = (stack_type or "hard_surface").lower().strip()
    payload = {
        "action": "apply_modifier_stack",
        "stack_type": clean_type,
        "params": params or {},
        "apply_immediately": apply_immediately,
    }
    return _send_blender_request(
        payload, host=host, port=port, timeout=timeout, raise_on_error=raise_on_error
    )


def request_geometry_nodes_bridge(
    setup_type: str = "point_scatter",
    node_group_name: str | None = None,
    host: str = DEFAULT_BLENDER_HOST,
    port: int = DEFAULT_BLENDER_PORT,
    timeout: float = 25.0,
    raise_on_error: bool = False,
) -> dict[str, Any]:
    """
    Odešle do Blenderu požadavek na vytvoření a aplikaci procedurálního Geometry Nodes systému
    na aktivní objekt (action: create_geometry_nodes_bridge).

    Args:
        setup_type: Typ přednastaveného Geometry Nodes stromu:
                    - "point_scatter": Distribuce bodů po povrchu a instancování geometrie
                    - "extrude_panel": Procedurální extrudování a panelizace stěn se spárami
        node_group_name: Volitelný vlastní název nové skupiny uzlů (např. "GN_Panels").

    Vrací strukturovaný slovník:
    {
        "status": "success",
        "action": "create_geometry_nodes_bridge",
        "object_name": str,
        "modifier_name": str,
        "node_group_name": str,
        "setup_type": str,
        "node_count": int,
        "link_count": int,
        "nodes": list[dict],
    }
    """
    clean_type = (setup_type or "point_scatter").lower().strip()
    payload: dict[str, Any] = {
        "action": "create_geometry_nodes_bridge",
        "setup_type": clean_type,
    }
    if node_group_name and node_group_name.strip():
        payload["node_group_name"] = node_group_name.strip()

    return _send_blender_request(
        payload, host=host, port=port, timeout=timeout, raise_on_error=raise_on_error
    )


def request_fcurve_animation(
    property_name: str = "location",
    interpolation: str = "BEZIER",
    modifier_type: str | None = None,
    keyframes: list[dict[str, Any]] | None = None,
    start_frame: int = 1,
    end_frame: int = 60,
    host: str = DEFAULT_BLENDER_HOST,
    port: int = DEFAULT_BLENDER_PORT,
    timeout: float = 25.0,
    raise_on_error: bool = False,
) -> dict[str, Any]:
    """
    Odešle do Blenderu požadavek na vytvoření F-Curve animace aktivního objektu
    (action: apply_fcurve_animation).

    Args:
        property_name: Vlastnost pro animaci ("location", "rotation", "scale").
        interpolation: Typ interpolace křivek ("BEZIER", "LINEAR", "BOUNCE").
        modifier_type: Volitelný F-Curve modifikátor ("NOISE" pro roztřesení, "CYCLES" pro smyčku).
        keyframes: Volitelný seznam klíčových bodů [{"frame": 1, "value": [0,0,0]}, ...].
        start_frame: Počáteční snímek (pokud nejsou zadány keyframes).
        end_frame: Koncový snímek (pokud nejsou zadány keyframes).
        host: IP adresa Blender receiveru.
        port: Port Blender receiveru.
        timeout: Timeout v sekundách.
        raise_on_error: Zda vyvolat výjimku při chybě.

    Vrací strukturovaný slovník:
    {
        "status": "success",
        "action": "apply_fcurve_animation",
        "object_name": str,
        "property_name": str,
        "data_path": str,
        "interpolation": str,
        "modifier_type": str | None,
        "applied_modifiers": list[str],
        "fcurves_count": int,
        "keyframes_count": int,
        "frame_range": list[int],
    }
    """
    clean_prop = (property_name or "location").lower().strip()
    clean_interp = (interpolation or "BEZIER").upper().strip()
    clean_mod = (modifier_type or "").upper().strip() if modifier_type else None
    if clean_mod in ("NONE", "NULL", ""):
        clean_mod = None

    payload: dict[str, Any] = {
        "action": "apply_fcurve_animation",
        "property_name": clean_prop,
        "interpolation": clean_interp,
        "start_frame": int(start_frame),
        "end_frame": int(end_frame),
    }
    if clean_mod:
        payload["modifier_type"] = clean_mod
    if keyframes and isinstance(keyframes, list):
        payload["keyframes"] = keyframes

    return _send_blender_request(
        payload, host=host, port=port, timeout=timeout, raise_on_error=raise_on_error
    )


def request_motion_nodes(
    motion_type: str = "geometry_nodes",
    target_property: str = "rotation",
    axis: str = "Z",
    speed: float = 1.0,
    expression: str | None = None,
    host: str = DEFAULT_BLENDER_HOST,
    port: int = DEFAULT_BLENDER_PORT,
    timeout: float = 25.0,
    raise_on_error: bool = False,
) -> dict[str, Any]:
    """
    Odešle do Blenderu požadavek na vytvoření procedurální animace bez klíčových snímků
    pomocí Geometry Nodes (Scene Time -> Math -> Transform) nebo Driverů (action: create_motion_node_setup).

    Args:
        motion_type: Režim animace: "geometry_nodes" (uzlový graf) nebo "driver" (Python driver).
        target_property: Animovaná vlastnost: "rotation" nebo "location".
        axis: Osa pohybu: "X", "Y", "Z" nebo "ALL".
        speed: Rychlost pohybu / násobič času (default 1.0 pro GN, 0.05 pro driver).
        expression: Volitelný vlastní výraz pro driver (např. "frame * 0.05").
        host: IP adresa Blender receiveru.
        port: Port Blender receiveru.
        timeout: Timeout v sekundách.
        raise_on_error: Zda vyvolat výjimku při chybě.

    Vrací strukturovaný slovník:
    {
        "status": "success",
        "action": "create_motion_node_setup",
        "motion_type": str,
        "object_name": str,
        ...
    }
    """
    clean_motion = (motion_type or "geometry_nodes").lower().strip()
    clean_prop = (target_property or "rotation").lower().strip()
    clean_axis = (axis or "Z").upper().strip()

    payload: dict[str, Any] = {
        "action": "create_motion_node_setup",
        "motion_type": clean_motion,
        "target_property": clean_prop,
        "axis": clean_axis,
        "speed": float(speed),
    }
    if expression and str(expression).strip():
        payload["expression"] = str(expression).strip()

    return _send_blender_request(
        payload, host=host, port=port, timeout=timeout, raise_on_error=raise_on_error
    )


def request_blueprint_setup(
    image_path: str,
    axis: str = "FRONT",
    alpha: float = 0.5,
    name: str | None = None,
    host: str = DEFAULT_BLENDER_HOST,
    port: int = DEFAULT_BLENDER_PORT,
    timeout: float = 25.0,
    raise_on_error: bool = False,
) -> dict[str, Any]:
    """
    Odešle do Blenderu požadavek na nastavení referenčního blueprint obrázku
    ve zvoleném pohledu (action: setup_blueprint_reference).

    Args:
        image_path: Cesta k referenčnímu obrázku (PNG, JPG apod.).
        axis: Pohled/osa pro zarovnání ("FRONT", "TOP", "RIGHT", "BACK").
        alpha: Průhlednost (0.0 až 1.0, výchozí 0.5).
        name: Volitelný název Empty objektu.
        host: IP adresa Blender receiveru.
        port: Port Blender receiveru.
        timeout: Timeout v sekundách.
        raise_on_error: Zda vyvolat výjimku při chybě.

    Vrací strukturovaný slovník:
    {
        "status": "success",
        "action": "setup_blueprint_reference",
        "object_name": str,
        "image_path": str,
        "axis": str,
        "alpha": float,
        "location": list[float],
        "rotation_euler": list[float],
        "hide_select": True,
    }
    """
    clean_path = str(image_path or "").strip()
    clean_axis = (axis or "FRONT").upper().strip()

    payload: dict[str, Any] = {
        "action": "setup_blueprint_reference",
        "image_path": clean_path,
        "axis": clean_axis,
        "alpha": float(alpha),
    }
    if name and str(name).strip():
        payload["name"] = str(name).strip()

    return _send_blender_request(
        payload, host=host, port=port, timeout=timeout, raise_on_error=raise_on_error
    )


def request_vectorize_to_3d(
    image_path: str,
    extrude_depth: float = 0.02,
    bevel_depth: float = 0.002,
    target_size: float = 1.0,
    invert: bool = False,
    object_name: str | None = None,
    host: str = DEFAULT_BLENDER_HOST,
    port: int = DEFAULT_BLENDER_PORT,
    timeout: float = 25.0,
    raise_on_error: bool = False,
) -> dict[str, Any]:
    """
    Odešle do Blenderu požadavek na vektorizaci 2D obrázku (loga, ikony, siluety)
    a jeho převedení na plnohodnotný 3D MESH s extruzí a zkosením (action: vectorize_image_to_3d).

    Args:
        image_path: Cesta k 2D obrázku.
        extrude_depth: Hloubka vytažení / tloušťka v metrech (výchozí 0.02 = 20 mm).
        bevel_depth: Hloubka sražení hran v metrech (výchozí 0.002 = 2 mm).
        target_size: Cílová maximální velikost modelu v metrech (výchozí 1.0 m).
        invert: Zda invertovat popředí/pozadí.
        object_name: Volitelný název výsledného objektu.
        host: IP adresa Blender receiveru.
        port: Port Blender receiveru.
        timeout: Timeout v sekundách.
        raise_on_error: Zda vyvolat výjimku při chybě.

    Vrací strukturovaný slovník:
    {
        "status": "success",
        "action": "vectorize_image_to_3d",
        "object_name": str,
        "image_path": str,
        "svg_path": str,
        "contours_count": int,
        "vertex_count": int,
        "polygon_count": int,
        "extrude_depth": float,
        "bevel_depth": float,
        "dimensions": list[float],
    }
    """
    clean_path = str(image_path or "").strip()
    payload: dict[str, Any] = {
        "action": "vectorize_image_to_3d",
        "image_path": clean_path,
        "extrude_depth": float(extrude_depth),
        "bevel_depth": float(bevel_depth),
        "target_size": float(target_size),
        "invert": bool(invert),
    }
    if object_name and str(object_name).strip():
        payload["object_name"] = str(object_name).strip()

    return _send_blender_request(
        payload, host=host, port=port, timeout=timeout, raise_on_error=raise_on_error
    )


def request_compositor_setup(
    preset: str = "product_pop",
    glare_threshold: float = 0.75,
    glare_size: int = 8,
    dispersion: float = 0.015,
    vignette_strength: float = 0.8,
    host: str = DEFAULT_BLENDER_HOST,
    port: int = DEFAULT_BLENDER_PORT,
    timeout: float = 25.0,
    raise_on_error: bool = False,
) -> dict[str, Any]:
    """
    Odešle do Blenderu požadavek na nastavení nodového kompozitoru pro post-processing
    (action: setup_compositor).

    Args:
        preset: Zvolený styl postprodukce:
                - "product_pop": Fog Glow (odlesky) + Color Balance (kontrast)
                - "cinematic": Lens Distortion (chromatická aberace) + Ellipse Vignette
                - "denoise_only": Čisté odstranění šumu
        glare_threshold: Prahová hodnota pro Fog Glow (pro preset product_pop).
        glare_size: Velikost záře Fog Glow (pro preset product_pop).
        dispersion: Míra chromatické aberace (pro preset cinematic).
        vignette_strength: Intenzita vinětace (pro preset cinematic).
        host: IP adresa Blender receiveru.
        port: Port Blender receiveru.
        timeout: Timeout v sekundách.
        raise_on_error: Zda vyvolat výjimku při chybě.

    Vrací strukturovaný slovník:
    {
        "status": "success",
        "action": "setup_compositor",
        "preset": str,
        "node_count": int,
        "link_count": int,
        "nodes": list[dict],
        "use_nodes": bool,
    }
    """
    clean_preset = (preset or "product_pop").lower().strip()
    payload: dict[str, Any] = {
        "action": "setup_compositor",
        "preset": clean_preset,
        "glare_threshold": float(glare_threshold),
        "glare_size": int(glare_size),
        "dispersion": float(dispersion),
        "vignette_strength": float(vignette_strength),
    }

    return _send_blender_request(
        payload, host=host, port=port, timeout=timeout, raise_on_error=raise_on_error
    )


def request_local_ai_mesh(
    image_path: str,
    production_ready: bool = True,
    target_faces: int = 10000,
    texture_size: int = 2048,
    voxel_size: float = 0.02,
    object_name: str = "AI_Mesh_Production",
    host: str = DEFAULT_BLENDER_HOST,
    port: int = DEFAULT_BLENDER_PORT,
    timeout: float = 60.0,
    raise_on_error: bool = False,
) -> dict[str, Any]:
    """
    Odešle do Blenderu požadavek na spuštění produkční lokální Image-to-3D pipeline
    (action: generate_local_ai_mesh).

    Args:
        image_path: Cesta ke zdrojovému 2D obrázku.
        production_ready: Pokud je True, spustí Auto-Retopology (Voxel Remesh + QuadriFlow),
                          Smart UV unwrapping a pečení Vertex Colors do PBR textury.
        target_faces: Cílový počet polygonů pro retopologii (např. 10 000).
        texture_size: Rozlišení upečené PBR difúzní textury (např. 2048).
        voxel_size: Velikost voxelu pro sjednocení děr a uzavření topologie.
        object_name: Název výsledného 3D objektu.
        host: IP adresa Blender receiveru.
        port: Port Blender receiveru.
        timeout: Timeout v sekundách (výchozí 60s pro výpočetně náročnější operace).
        raise_on_error: Zda vyvolat výjimku při chybě.

    Vrací strukturovaný slovník:
    {
        "status": "success",
        "action": "generate_local_ai_mesh",
        "object_name": str,
        "production_ready": bool,
        "raw_vertex_count": int,
        "raw_face_count": int,
        "retopo_vertex_count": int,
        "retopo_face_count": int,
        "quad_percentage": float,
        "triangle_percentage": float,
        "reduction_ratio": float,
        "texture_name": str,
        "texture_resolution": list[int],
        "material_name": str,
        "uv_unwrapped": bool,
        "pbr_ready": bool,
        "retopology_method": str,
    }
    """
    payload: dict[str, Any] = {
        "action": "generate_local_ai_mesh",
        "image_path": str(image_path),
        "production_ready": bool(production_ready),
        "target_faces": int(target_faces),
        "texture_size": int(texture_size),
        "voxel_size": float(voxel_size),
        "object_name": str(object_name),
    }

    return _send_blender_request(
        payload, host=host, port=port, timeout=timeout, raise_on_error=raise_on_error
    )

