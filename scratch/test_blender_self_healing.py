import socket
import threading
import json
import time
from unittest.mock import MagicMock
from blender_connector import send_code_to_blender, BlenderExecutionError
from llama_module import handle_blender_command

class MockReceiver:
    def __init__(self, port=19876):
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(('127.0.0.1', self.port))
        self.sock.listen(5)
        self.running = True
        self.attempts = []
        self.fail_times = 1

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
            code = req.get("code", "")
            self.attempts.append(code)

            if len(self.attempts) <= self.fail_times:
                resp = {
                    "status": "error",
                    "error": "AttributeError: module 'bpy.ops.mesh' has no attribute 'primitive_cylinder_add'",
                    "traceback": "Traceback (most recent call last):\n  File \"<blender>\", line 2\nAttributeError: module 'bpy.ops.mesh' has no attribute 'primitive_cylinder_add'",
                    "output": "",
                }
            else:
                resp = {
                    "status": "success",
                    "output": "Created cylinder successfully",
                }
            conn.sendall((json.dumps(resp) + "\n").encode("utf-8"))
            conn.close()

    def stop(self):
        self.running = False
        try:
            self.sock.close()
        except Exception:
            pass


def run_tests():
    receiver = MockReceiver(port=19876)
    receiver.fail_times = 2  # Fail the first 2 calls
    receiver.start()
    time.sleep(0.1)

    try:
        # Test 1: error response dictionary structure
        err_res = send_code_to_blender("bpy.ops.mesh.primitive_cylinder_add()", port=19876)
        assert err_res["status"] == "error"
        assert "AttributeError" in err_res["error"]
        assert "Traceback" in err_res["traceback"]
        assert "detail" in err_res
        print("[OK] blender_connector error response verified")

        # Test 2: raise_on_error
        raised = False
        try:
            send_code_to_blender("bad code", port=19876, raise_on_error=True)
        except BlenderExecutionError as e:
            raised = True
            assert "AttributeError" in str(e)
            assert "bpy.ops.mesh" in e.error
            assert "Traceback" in e.traceback
        assert raised, "BlenderExecutionError should be raised"
        print("[OK] BlenderExecutionError raise_on_error verified")

        # Test 3: Self-healing loop in handle_blender_command (fail 1 time, then succeed)
        receiver.attempts.clear()
        receiver.fail_times = 1

        mock_llm = MagicMock()
        code_attempt_1 = "bpy.ops.mesh.primitive_cylinder_add()"
        code_attempt_2 = "bpy.ops.mesh.primitive_cylinder_add(radius=1, depth=2)"

        def fake_chat(**kwargs):
            call_count = len(mock_llm.create_chat_completion.call_args_list)
            if call_count == 1:
                ans = f"```python\n{code_attempt_1}\n```"
            else:
                ans = f"```python\n{code_attempt_2}\n```"
            return {"choices": [{"message": {"content": ans}}]}

        mock_llm.create_chat_completion.side_effect = fake_chat

        status_log = []
        tokens_log = []
        cfg = {"blender": {"host": "127.0.0.1", "port": 19876, "max_retries": 2}}

        out_chunks = list(
            handle_blender_command(
                mock_llm,
                "vytvoř válec v blenderu",
                cfg,
                callback_on_token=lambda t: tokens_log.append(t),
                status_callback=lambda s: status_log.append(s),
            )
        )

        print("[OK] Self-healing loop completed")
        assert len(receiver.attempts) == 2, f"Expected 2 attempts, got {len(receiver.attempts)}"
        print("Attempts recorded by receiver: 2")

        # Verify status updates
        print("Status log captured:", status_log)
        assert any("Self-Healing" in s or "oprav" in s.lower() for s in status_log), "Status bar should notify about self-healing"
        assert any("úspěšně opraven" in s.lower() or "úspěšně vykonán" in s.lower() for s in status_log), "Status bar should show final success"

        # Verify TTS chunk
        print("Final TTS chunk:", out_chunks[-1])
        assert "automatické opravě" in out_chunks[-1]

        # Verify second LLM call received previous code & error message
        second_call_messages = mock_llm.create_chat_completion.call_args_list[1][1]["messages"]
        user_repair_msg = second_call_messages[-1]["content"]
        print("Repair prompt sent to LLM:\n", user_repair_msg[:200])
        assert "AttributeError" in user_repair_msg
        assert "Tvůj předchozí kód pro Blender selhal" in user_repair_msg
        assert "TRACEBACK:" in user_repair_msg
        print("[OK] Self-healing prompt to LLM verified")

        # Test 4: Persistent failure stops at max_retries=2
        receiver.attempts.clear()
        receiver.fail_times = 10  # Always fail
        mock_llm_fail = MagicMock()
        mock_llm_fail.create_chat_completion.return_value = {
            "choices": [{"message": {"content": "```python\nbad_code()\n```"}}]
        }
        fail_status_log = []
        fail_chunks = list(
            handle_blender_command(
                mock_llm_fail,
                "vytvoř cokoliv",
                cfg,
                status_callback=lambda s: fail_status_log.append(s),
            )
        )
        # Should attempt: initial (1) + retry 1 + retry 2 = 3 total attempts
        assert len(receiver.attempts) == 3, f"Expected 3 attempts before stopping, got {len(receiver.attempts)}"
        assert "došlo k chybě i po automatických pokusech" in fail_chunks[-1]
        print("[OK] Max retries safety limit (2 retries / 3 total attempts) verified")

    finally:
        receiver.stop()

    print("\nALL SELF-HEALING BLENDER TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    run_tests()
