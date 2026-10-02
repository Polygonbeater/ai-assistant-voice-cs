import ast
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from blender_connector import DEFAULT_TIMEOUT, send_code_to_blender


class FakeSocket:
    def __init__(self):
        self.sent = b""

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
    def test_connector_uses_whitelisted_run_script_action(self):
        fake_socket = FakeSocket()
        with patch("blender_connector.socket.socket", return_value=fake_socket):
            response = send_code_to_blender("print('ok')")

        self.assertEqual(response["status"], "success")
        request = json.loads(fake_socket.sent)
        self.assertEqual(request["action"], "run_bpy_script")
        self.assertEqual(request["code"], "print('ok')")

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


if __name__ == "__main__":
    unittest.main()
