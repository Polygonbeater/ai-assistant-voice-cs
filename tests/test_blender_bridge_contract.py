import ast
import json
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from blender_connector import (
    DEFAULT_TIMEOUT,
    get_blender_auth_token,
    send_code_to_blender,
    ping_blender,
)
from self_dev_loop import is_safe_target_path, PROJECT_ROOT


class FakeSocket:
    def __init__(self):
        self.sent = b""

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def settimeout(self, _timeout):
        pass

    def connect(self, _address):
        pass

    def sendall(self, data):
        self.sent = data

    def recv(self, _size):
        return b'{"status":"success"}\n'

    def close(self):
        pass


class BlenderBridgeContractTests(unittest.TestCase):
    def setUp(self):
        self.test_token = "test-bridge-token-secure-123"
        self.env_patcher = patch.dict("os.environ", {"POLYGON_BLENDER_AUTH_TOKEN": self.test_token})
        self.env_patcher.start()

    def tearDown(self):
        self.env_patcher.stop()

    def test_connector_uses_whitelisted_run_script_action_and_auth_token(self):
        fake_socket = FakeSocket()
        with patch("blender_connector.socket.socket", return_value=fake_socket):
            response = send_code_to_blender("print('ok')")

        self.assertEqual(response["status"], "success")
        request = json.loads(fake_socket.sent)
        self.assertEqual(request["action"], "run_bpy_script")
        self.assertEqual(request["code"], "print('ok')")
        self.assertIn("auth_token", request)
        self.assertEqual(request["auth_token"], self.test_token)

    def test_ping_blender_includes_auth_token(self):
        fake_socket = FakeSocket()
        fake_socket.recv = lambda _size: b'{"status":"pong","blender_version":"4.2.0"}\n'
        with patch("blender_connector.socket.create_connection", return_value=fake_socket):
            res = ping_blender()

        self.assertEqual(res["status"], "pong")
        request = json.loads(fake_socket.sent)
        self.assertEqual(request["action"], "ping")
        self.assertEqual(request["auth_token"], self.test_token)

    def test_receiver_whitelist_contains_connector_action(self):
        source = Path("blender_receiver.py").read_text(encoding="utf-8")
        module = ast.parse(source)
        actions = next(
            ast.literal_eval(node.value)
            for node in module.body
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "ALLOWED_ACTIONS" for target in node.targets)
        )

        self.assertIn("run_bpy_script", actions)
        self.assertGreaterEqual(DEFAULT_TIMEOUT, 65.0)

    def test_receiver_fails_secure_when_no_token_configured(self):
        """Ověří, že receiver odmítne nabootovat a vyhodí chybu, pokud chybí token."""
        mock_bpy = MagicMock()
        mock_bpy.app.version = (4, 2, 0)
        mock_bpy.data.filepath = "test.blend"
        with patch.dict("sys.modules", {"bpy": mock_bpy}):
            import blender_receiver

            with patch.dict("os.environ", {}, clear=True), patch("pathlib.Path.is_file", return_value=False):
                with self.assertRaises(RuntimeError) as ctx:
                    blender_receiver.get_blender_auth_token(fail_closed=True)
                self.assertIn("Fail-Secure", str(ctx.exception))

                server = blender_receiver.BlenderSocketServer()
                with self.assertRaises(RuntimeError):
                    server.start()

    def test_receiver_rejects_missing_or_invalid_auth_token(self):
        mock_bpy = MagicMock()
        mock_bpy.app.version = (4, 2, 0)
        mock_bpy.data.filepath = "test.blend"
        with patch.dict("sys.modules", {"bpy": mock_bpy}):
            import blender_receiver

            server = blender_receiver.BlenderSocketServer()
            mock_conn = MagicMock()

            # Test 1: Chybějící token
            payload_no_token = json.dumps({"action": "ping"}).encode("utf-8") + b"\n"
            mock_conn.recv.side_effect = [payload_no_token, b""]
            server._handle_client(mock_conn, ("127.0.0.1", 12345))

            sent_data = b"".join(call.args[0] for call in mock_conn.sendall.call_args_list)
            resp = json.loads(sent_data.decode("utf-8").strip())
            self.assertEqual(resp.get("status"), "error")
            self.assertEqual(resp.get("error_type"), "Unauthorized")

            # Test 2: Neplatný token
            mock_conn.reset_mock()
            payload_bad_token = json.dumps({"action": "ping", "auth_token": "wrong-secret"}).encode("utf-8") + b"\n"
            mock_conn.recv.side_effect = [payload_bad_token, b""]
            server._handle_client(mock_conn, ("127.0.0.1", 12345))

            sent_data = b"".join(call.args[0] for call in mock_conn.sendall.call_args_list)
            resp = json.loads(sent_data.decode("utf-8").strip())
            self.assertEqual(resp.get("status"), "error")
            self.assertEqual(resp.get("error_type"), "Unauthorized")

            # Test 3: Platný token
            mock_conn.reset_mock()
            payload_valid_token = json.dumps({"action": "ping", "auth_token": blender_receiver.get_blender_auth_token()}).encode("utf-8") + b"\n"
            mock_conn.recv.side_effect = [payload_valid_token, b""]
            server._handle_client(mock_conn, ("127.0.0.1", 12345))

            sent_data = b"".join(call.args[0] for call in mock_conn.sendall.call_args_list)
            resp = json.loads(sent_data.decode("utf-8").strip())
            self.assertEqual(resp.get("status"), "pong")


class SelfDevLoopPathSecurityTests(unittest.TestCase):
    def test_safe_paths_in_allowed_directories(self):
        """Ověří, že validní cesty v tests/ a scratch/ jsou povoleny."""
        is_safe, msg, target = is_safe_target_path("tests/test_auto_rig.py")
        self.assertTrue(is_safe, msg)
        self.assertIsNotNone(target)
        self.assertEqual(target, (PROJECT_ROOT / "tests/test_auto_rig.py").resolve())

        is_safe, msg, target = is_safe_target_path("scratch/experiment.py")
        self.assertTrue(is_safe, msg)
        self.assertIsNotNone(target)
        self.assertEqual(target, (PROJECT_ROOT / "scratch/experiment.py").resolve())

    def test_path_traversal_attempts_are_blocked(self):
        """Ověří, že veškeré pokusy o path traversal jsou odmítnuty."""
        malicious_paths = [
            "../../etc/passwd",
            "tests/../../llama_module.py",
            "scratch/../blender_receiver.py",
            "/etc/shadow",
            "/tmp/evil.py",
            "llama_module.py",
            "blender_receiver.py",
            "web_server.py",
            "",
            "   ",
        ]
        for path in malicious_paths:
            is_safe, msg, target = is_safe_target_path(path)
            self.assertFalse(is_safe, f"Nebezpečná cesta '{path}' nebyla odmítnuta! Msg: {msg}")
            self.assertIsNone(target)


if __name__ == "__main__":
    unittest.main()
