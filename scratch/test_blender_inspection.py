import json
import socket
import sys
import threading
import time
from unittest.mock import MagicMock

from blender_connector import (
    BlenderExecutionError,
    request_scene_inspection,
    is_blender_available,
)
from llama_module import (
    is_blender_inspection_query,
    is_blender_command,
    format_scene_metrics_for_prompt,
    handle_blender_inspection,
    generate_response,
)


class MockBlenderInspectionServer:
    """Mock server simulující Blender s novou akcí inspect_scene."""

    def __init__(self, port=19877):
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", self.port))
        self.sock.listen(5)
        self.running = True
        self.requests = []
        self.return_error = False

    def start(self):
        t = threading.Thread(target=self._loop, daemon=True)
        t.start()

    def _loop(self):
        while self.running:
            try:
                self.sock.settimeout(1.0)
                conn, _ = self.sock.accept()
            except socket.timeout:
                continue
            except Exception:
                break

            data = b""
            while not data.endswith(b"\n"):
                chunk = conn.recv(1024)
                if not chunk:
                    break
                data += chunk

            if not data:
                conn.close()
                continue

            req = json.loads(data.decode("utf-8"))
            self.requests.append(req)

            if self.return_error:
                resp = {
                    "status": "error",
                    "error": "RenderError: OpenGL context not found",
                    "traceback": "Traceback (most recent call last):\n  File 'blender_receiver.py', line 123\nRenderError: OpenGL context not found",
                }
            elif req.get("action") == "inspect_scene":
                resp = {
                    "status": "success",
                    "action": "inspect_scene",
                    "scene_metrics": {
                        "scene_name": "Scene_Studio",
                        "mode": "OBJECT",
                        "total_objects": 4,
                        "selected_count": 1,
                        "active_object": {
                            "name": "Hero_Suzanne",
                            "type": "MESH",
                            "location": [0.0, 0.0, 1.25],
                            "rotation_euler": [0.0, 0.0, 0.785],
                            "scale": [1.0, 1.0, 1.0],
                            "vertices": 507,
                            "polygons": 500,
                        },
                        "selected_objects": [
                            {
                                "name": "Hero_Suzanne",
                                "type": "MESH",
                                "location": [0.0, 0.0, 1.25],
                                "rotation_euler": [0.0, 0.0, 0.785],
                                "scale": [1.0, 1.0, 1.0],
                                "vertices": 507,
                                "polygons": 500,
                                "materials": ["Gold_Shader"],
                                "is_active": True,
                            }
                        ],
                        "lights": [
                            {
                                "name": "Key_Light",
                                "light_type": "AREA",
                                "energy": 500.0,
                                "location": [3.0, -3.0, 4.0],
                            }
                        ],
                        "cameras": [
                            {
                                "name": "Main_Camera",
                                "is_active_scene_camera": True,
                                "location": [0.0, -5.0, 2.0],
                                "lens_mm": 50.0,
                            }
                        ],
                        "all_objects_summary": [
                            {"name": "Hero_Suzanne", "type": "MESH", "visible": True},
                            {"name": "Floor_Plane", "type": "MESH", "visible": True},
                            {"name": "Key_Light", "type": "LIGHT", "visible": True},
                            {"name": "Main_Camera", "type": "CAMERA", "visible": True},
                        ],
                        "render_engine": "CYCLES",
                    },
                    "screenshot_path": "/tmp/blender_viewport.png",
                }
            else:
                resp = {"status": "error", "error": f"Unknown action: {req.get('action')}"}

            conn.sendall((json.dumps(resp) + "\n").encode("utf-8"))
            conn.close()

    def stop(self):
        self.running = False
        try:
            self.sock.close()
        except Exception:
            pass


def test_intent_detection():
    print("\n--- Test 1: Intent Detection (is_blender_inspection_query vs is_blender_command) ---")
    positives = [
        "podívej se na scénu",
        "podívej se do blenderu",
        "podívej se co je ve scéně",
        "zkontroluj co je ve viewportu",
        "zkontroluj viewport",
        "zkontroluj scénu",
        "co vidíš ve scéně?",
        "co je ve viewportu",
        "co máme ve scéně v Blenderu",
        "jak vypadá scéna",
        "jak vypadá 3d scéna v blenderu",
        "udělej snímek viewportu",
        "inspekce scény",
        "analyzuj scénu v blenderu",
        "zhodnoť scénu v blenderu",
        "viewport snapshot",
        "inspect scene",
    ]
    for q in positives:
        assert is_blender_inspection_query(q), f"Failed to detect inspection query: '{q}'"
        assert not is_blender_command(q), f"Inspection query '{q}' should NOT trigger is_blender_command"

    negatives = [
        "vycentruj pivoty a aplikuj scale",
        "vytvoř krychli v blenderu",
        "smaž vybrané objekty",
        "co je to Blender?",
        "kdo vytvořil Blender?",
        "jaké je dnes počasí?",
        "vysvětli mi teorii relativity",
    ]
    for q in negatives:
        assert not is_blender_inspection_query(q), f"False positive inspection detection for: '{q}'"

    # Command detection for actual actions
    assert is_blender_command("vycentruj pivoty a aplikuj scale")
    assert is_blender_command("vytvoř krychli v blenderu")
    print("[OK] Intent detection test passed for all phrases!")


def test_request_scene_inspection():
    print("\n--- Test 2: request_scene_inspection via blender_connector ---")
    server = MockBlenderInspectionServer(port=19877)
    server.start()
    time.sleep(0.1)

    try:
        assert is_blender_available(port=19877)

        # Successful inspection
        res = request_scene_inspection(port=19877)
        assert res["status"] == "success"
        assert "scene_metrics" in res
        assert res["screenshot_path"] == "/tmp/blender_viewport.png"
        metrics = res["scene_metrics"]
        assert metrics["total_objects"] == 4
        assert metrics["active_object"]["name"] == "Hero_Suzanne"
        assert len(metrics["lights"]) == 1
        assert len(metrics["cameras"]) == 1
        print("[OK] request_scene_inspection returned valid metrics and snapshot path")

        # Test error handling
        server.return_error = True
        err_res = request_scene_inspection(port=19877)
        assert err_res["status"] == "error"
        assert "RenderError" in err_res["error"]

        # Test raise_on_error
        raised = False
        try:
            request_scene_inspection(port=19877, raise_on_error=True)
        except BlenderExecutionError as e:
            raised = True
            assert "RenderError" in str(e)
        assert raised, "Expected BlenderExecutionError to be raised when raise_on_error=True"
        print("[OK] Error response and raise_on_error verified")

    finally:
        server.stop()

    # Test connection refused when server is down
    refused = request_scene_inspection(port=19877)
    assert refused["status"] == "error"
    assert refused["error_type"] == "ConnectionRefused"
    print("[OK] Connection refused handled cleanly")


def test_metrics_formatting():
    print("\n--- Test 3: format_scene_metrics_for_prompt ---")
    sample_metrics = {
        "scene_name": "TestScene",
        "mode": "OBJECT",
        "total_objects": 2,
        "active_object": {
            "name": "Cube",
            "type": "MESH",
            "location": [0.0, 1.0, 2.0],
            "rotation_euler": [0.0, 0.0, 0.0],
            "scale": [1.0, 1.0, 2.5],
            "vertices": 8,
            "polygons": 6,
        },
        "selected_objects": [
            {
                "name": "Cube",
                "type": "MESH",
                "location": [0.0, 1.0, 2.0],
                "rotation_euler": [0.0, 0.0, 0.0],
                "scale": [1.0, 1.0, 2.5],
                "vertices": 8,
                "polygons": 6,
                "materials": ["Material_01"],
            }
        ],
        "lights": [
            {
                "name": "Sun",
                "light_type": "SUN",
                "energy": 1000.0,
                "location": [5.0, 5.0, 10.0],
            }
        ],
        "cameras": [],
        "all_objects_summary": [
            {"name": "Cube", "type": "MESH", "visible": True},
            {"name": "Sun", "type": "LIGHT", "visible": True},
        ],
        "render_engine": "BLENDER_EEVEE",
    }
    formatted = format_scene_metrics_for_prompt(sample_metrics, "/tmp/blender_viewport.png")
    assert "TestScene" in formatted
    assert "Cube" in formatted
    assert "Sun" in formatted
    assert "Žádná kamera" in formatted or "chybí jakákoliv kamera" in formatted
    assert "/tmp/blender_viewport.png" in formatted
    print("[OK] Scene metrics formatted cleanly for prompt:")
    print(formatted)


def test_handle_blender_inspection_e2e():
    print("\n--- Test 4: handle_blender_inspection and generate_response routing ---")
    server = MockBlenderInspectionServer(port=19877)
    server.start()
    time.sleep(0.1)

    try:
        mock_llm = MagicMock()
        def fake_stream(*args, **kwargs):
            return iter([
                {"choices": [{"delta": {"content": "Na scéně se nachází model opičky Suzanne. "}}]},
                {"choices": [{"delta": {"content": "Objekt má vycentrovanou pozici a aplikované rotace. "}}]},
                {"choices": [{"delta": {"content": "Ve scéně je jedno plošné světlo a kamera s ohniskem 50 milimetrů."}}]},
            ])
        mock_llm.create_chat_completion.side_effect = fake_stream

        tokens = []
        statuses = []
        cfg = {
            "blender": {
                "host": "127.0.0.1",
                "port": 19877,
                "enabled": True,
            }
        }

        # 4a: handle_blender_inspection directly
        tts_chunks = list(
            handle_blender_inspection(
                mock_llm,
                "podívej se na scénu a popiš ji",
                cfg,
                callback_on_token=lambda t: tokens.append(t),
                status_callback=lambda s: statuses.append(s),
            )
        )

        all_tokens = "".join(tokens)
        assert "📸 **3D Viewport Snapshot:**" in all_tokens
        assert "![Viewport Snapshot](/tmp/blender_viewport.png)" in all_tokens
        assert "Hero_Suzanne" in all_tokens or "Telemetrie scény" in all_tokens
        assert any("Suzanne" in c for c in tts_chunks)
        assert any("Inspekce 3D scény dokončena" in s for s in statuses)
        print("[OK] handle_blender_inspection completed and streamed correctly")

        # 4b: verify generate_response routes "podívej se na scénu"
        gen_tokens = []
        gen_tts = list(
            generate_response(
                mock_llm,
                "podívej se na scénu",
                cfg,
                callback_on_token=lambda t: gen_tokens.append(t),
            )
        )
        assert len(gen_tts) > 0
        assert "![Viewport Snapshot](/tmp/blender_viewport.png)" in "".join(gen_tokens)
        print("[OK] generate_response successfully routed inspection query to handle_blender_inspection")

    finally:
        server.stop()


def main():
    test_intent_detection()
    test_request_scene_inspection()
    test_metrics_formatting()
    test_handle_blender_inspection_e2e()
    print("\n🎉 ALL MULTIMODAL VIEWPORT INSPECTION TESTS PASSED SUCCESSFULLY! 🎉\n")


if __name__ == "__main__":
    main()
