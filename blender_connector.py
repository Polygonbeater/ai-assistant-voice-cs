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


def send_code_to_blender(
    code: str,
    host: str = DEFAULT_BLENDER_HOST,
    port: int = DEFAULT_BLENDER_PORT,
    timeout: float = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    """
    Odešle Python kód do Blenderu k bezpečnému spuštění v hlavním vlákně Blenderu.
    Vrací slovník s výsledkem:
    - {"status": "success", "output": "..."} při úspěchu
    - {"status": "error", "error": "...", "message": "..."} při chybě
    """
    if not code or not code.strip():
        return {"status": "error", "message": "Kód k odeslání je prázdný."}

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
            return {
                "status": "error",
                "message": "Blender spojení uzavřel bez odpovědi.",
            }

        response = json.loads(response_bytes.decode("utf-8"))
        logger.info("Přijata odpověď od Blenderu: status=%s", response.get("status"))
        return response

    except ConnectionRefusedError:
        logger.warning("Připojení k Blenderu na %s:%d bylo odmítnuto.", host, port)
        return {
            "status": "error",
            "error_type": "ConnectionRefused",
            "message": (
                f"Nelze se spojit s Blenderem na {host}:{port}. "
                "Ujistěte se, že Blender běží a v Text Editoru má spuštěný skript 'blender_receiver.py'."
            ),
        }
    except socket.timeout:
        logger.error("Vypršel časový limit při čekání na odpověď od Blenderu.")
        return {
            "status": "error",
            "error_type": "Timeout",
            "message": f"Vypršel časový limit ({timeout} s) při vykonávání kódu v Blenderu.",
        }
    except Exception as exc:
        logger.exception("Chyba při komunikaci s Blenderem: %s", exc)
        return {
            "status": "error",
            "error_type": "CommunicationError",
            "message": f"Chyba při komunikaci s Blenderem: {exc}",
        }
    finally:
        if sock is not None:
            try:
                sock.close()
            except Exception:
                pass
