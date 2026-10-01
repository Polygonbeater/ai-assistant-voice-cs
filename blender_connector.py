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

    except ConnectionRefusedError:
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
