"""
Mesh Doctor — unit testy pro:
- TOOL_SCHEMAS obsahuje mesh_doctor_audit a mesh_doctor_repair
- ALLOWED_TOOL_NAMES obsahuje nové nástroje
- parse_tool_call rozpozná mesh_doctor_* nástroje
- UnifiedToolDispatcher.dispatch() vrátí chybu BlenderNotConnected (Blender neběží)
- blender_connector.request_mesh_audit / request_mesh_repair vrací chybu při nedostupném Blenderu
- _execute_mesh_doctor_audit formátuje správný UI report
- _execute_mesh_doctor_repair formátuje správný UI report
"""

import sys
import os
import json
import unittest
from unittest.mock import MagicMock, patch

# Přidat kořen projektu do PYTHONPATH
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../.."))
sys.path.insert(0, PROJECT_ROOT)

# Importy z projektu
from llama_module import (
    TOOL_SCHEMAS,
    ALLOWED_TOOL_NAMES,
    parse_tool_call,
    UnifiedToolDispatcher,
)
import blender_connector


class TestMeshDoctorToolSchemas(unittest.TestCase):
    """Ověření registrace nástrojů v TOOL_SCHEMAS a ALLOWED_TOOL_NAMES."""

    def test_mesh_doctor_audit_in_schemas(self):
        names = [t["function"]["name"] for t in TOOL_SCHEMAS]
        self.assertIn("mesh_doctor_audit", names, "mesh_doctor_audit musí být v TOOL_SCHEMAS")

    def test_mesh_doctor_repair_in_schemas(self):
        names = [t["function"]["name"] for t in TOOL_SCHEMAS]
        self.assertIn("mesh_doctor_repair", names, "mesh_doctor_repair musí být v TOOL_SCHEMAS")

    def test_mesh_doctor_repair_has_merge_distance_param(self):
        schema = next(
            t for t in TOOL_SCHEMAS if t["function"]["name"] == "mesh_doctor_repair"
        )
        props = schema["function"]["parameters"]["properties"]
        self.assertIn(
            "merge_distance",
            props,
            "mesh_doctor_repair musí mít parametr merge_distance",
        )

    def test_allowed_tool_names_contains_both(self):
        self.assertIn("mesh_doctor_audit", ALLOWED_TOOL_NAMES)
        self.assertIn("mesh_doctor_repair", ALLOWED_TOOL_NAMES)


class TestMeshDoctorParseToolCall(unittest.TestCase):
    """parse_tool_call musí rozpoznat JSON volání mesh_doctor_* nástrojů."""

    def test_parse_audit_compact(self):
        text = json.dumps({"tool": "mesh_doctor_audit", "arguments": {}})
        result = parse_tool_call(text)
        self.assertIsNotNone(result, "Kompaktní JSON audit musí být rozpoznán")
        self.assertEqual(result["name"], "mesh_doctor_audit")

    def test_parse_repair_with_merge_distance(self):
        text = json.dumps(
            {"tool": "mesh_doctor_repair", "arguments": {"merge_distance": 0.001}}
        )
        result = parse_tool_call(text)
        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "mesh_doctor_repair")
        self.assertAlmostEqual(result["arguments"].get("merge_distance", 0), 0.001)

    def test_parse_audit_openai_format(self):
        text = json.dumps(
            {
                "type": "function",
                "function": {"name": "mesh_doctor_audit", "arguments": "{}"},
            }
        )
        result = parse_tool_call(text)
        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "mesh_doctor_audit")


class TestMeshDoctorDispatcherBlenderNotConnected(unittest.TestCase):
    """Dispatcher musí vrátit chybu BlenderNotConnected, pokud Blender neběží."""

    def _make_dispatcher(self):
        return UnifiedToolDispatcher(
            llm=None,
            config={"blender": {"host": "127.0.0.1", "port": 9999}},
        )

    def test_audit_blender_not_connected(self):
        dispatcher = self._make_dispatcher()
        with patch("blender_connector.is_blender_available", return_value=False):
            res = dispatcher.dispatch("mesh_doctor_audit", {})
        self.assertEqual(res["status"], "error")
        self.assertIn("BlenderNotConnected", res.get("error", ""))

    def test_repair_blender_not_connected(self):
        dispatcher = self._make_dispatcher()
        with patch("blender_connector.is_blender_available", return_value=False):
            res = dispatcher.dispatch("mesh_doctor_repair", {"merge_distance": 0.0001})
        self.assertEqual(res["status"], "error")
        self.assertIn("BlenderNotConnected", res.get("error", ""))


class TestMeshDoctorDispatcherSuccess(unittest.TestCase):
    """Dispatcher musí správně formátovat výsledek úspěšného auditu a opravy."""

    MOCK_AUDIT_RESPONSE = {
        "status": "success",
        "action": "mesh_doctor_audit",
        "audit": {
            "object_name": "Cube",
            "mesh_name": "Cube",
            "total_vertices": 8,
            "total_edges": 12,
            "total_faces": 6,
            "triangles": 0,
            "ngons": 0,
            "non_manifold_edges": 0,
            "loose_vertices": 0,
            "loose_edges": 0,
            "boundary_edges_holes": 0,
            "potentially_flipped_faces": 0,
            "is_watertight": True,
            "print_ready": True,
        },
    }

    MOCK_REPAIR_RESPONSE = {
        "status": "success",
        "action": "mesh_doctor_repair",
        "repairs_applied": [
            "merge_by_distance",
            "delete_loose_geometry",
            "recalculate_normals_outside",
        ],
        "post_repair_stats": {
            "object_name": "BrokenMesh",
            "total_vertices": 100,
            "total_edges": 200,
            "total_faces": 80,
            "non_manifold_edges": 0,
            "loose_vertices": 0,
            "loose_edges": 0,
            "boundary_edges_holes": 0,
            "is_watertight": True,
            "print_ready": True,
            "merge_distance_used": 0.0001,
        },
    }

    def _make_dispatcher(self):
        tokens = []
        statuses = []
        return (
            UnifiedToolDispatcher(
                llm=None,
                config={"blender": {"host": "127.0.0.1", "port": 9876}},
                callback_on_token=tokens.append,
                status_callback=statuses.append,
            ),
            tokens,
            statuses,
        )

    def test_audit_success_result_keys(self):
        dispatcher, tokens, statuses = self._make_dispatcher()
        with patch("blender_connector.is_blender_available", return_value=True), \
             patch("blender_connector.request_mesh_audit", return_value=self.MOCK_AUDIT_RESPONSE):
            res = dispatcher.dispatch("mesh_doctor_audit", {})

        self.assertEqual(res["status"], "success")
        self.assertEqual(res["tool"], "mesh_doctor_audit")
        self.assertIn("result", res)
        self.assertIn("audit", res)
        self.assertIn("_expert_system_prompt", res)
        # UI report byl emitován přes callback
        full_tokens = "".join(tokens)
        self.assertIn("Mesh Doctor", full_tokens)
        self.assertIn("Cube", full_tokens)
        # Watertight je ANO
        self.assertIn("ANO", full_tokens)

    def test_audit_success_result_text_contains_metrics(self):
        dispatcher, _, _ = self._make_dispatcher()
        with patch("blender_connector.is_blender_available", return_value=True), \
             patch("blender_connector.request_mesh_audit", return_value=self.MOCK_AUDIT_RESPONSE):
            res = dispatcher.dispatch("mesh_doctor_audit", {})

        result_text = res["result"]
        self.assertIn("Cube", result_text)
        self.assertIn("8", result_text)   # vrcholy
        self.assertIn("ANO", result_text)  # watertight

    def test_repair_success_result_keys(self):
        dispatcher, tokens, statuses = self._make_dispatcher()
        with patch("blender_connector.is_blender_available", return_value=True), \
             patch("blender_connector.request_mesh_repair", return_value=self.MOCK_REPAIR_RESPONSE):
            res = dispatcher.dispatch("mesh_doctor_repair", {"merge_distance": 0.0001})

        self.assertEqual(res["status"], "success")
        self.assertEqual(res["tool"], "mesh_doctor_repair")
        self.assertIn("repairs_applied", res)
        self.assertIn("post_repair_stats", res)
        self.assertIn("_expert_system_prompt", res)
        self.assertEqual(len(res["repairs_applied"]), 3)

    def test_repair_merge_distance_passed_correctly(self):
        dispatcher, _, _ = self._make_dispatcher()
        with patch("blender_connector.is_blender_available", return_value=True), \
             patch("blender_connector.request_mesh_repair", return_value=self.MOCK_REPAIR_RESPONSE) as mock_repair:
            dispatcher.dispatch("mesh_doctor_repair", {"merge_distance": 0.005})
        mock_repair.assert_called_once()
        call_kwargs = mock_repair.call_args
        self.assertAlmostEqual(
            call_kwargs.kwargs.get("merge_distance", call_kwargs.args[2] if len(call_kwargs.args) > 2 else 0),
            0.005,
            places=6,
        )

    def test_expert_prompt_content(self):
        dispatcher, _, _ = self._make_dispatcher()
        with patch("blender_connector.is_blender_available", return_value=True), \
             patch("blender_connector.request_mesh_audit", return_value=self.MOCK_AUDIT_RESPONSE):
            res = dispatcher.dispatch("mesh_doctor_audit", {})

        expert = res["_expert_system_prompt"]
        self.assertIn("watertight", expert.lower())
        self.assertIn("3D tisk", expert)
        self.assertIn("normál", expert.lower())


class TestBlenderConnectorMeshFunctions(unittest.TestCase):
    """blender_connector.request_mesh_audit / request_mesh_repair: error handling."""

    def test_request_mesh_audit_connection_refused(self):
        with patch("socket.socket") as mock_sock_cls:
            mock_sock = MagicMock()
            mock_sock.connect.side_effect = ConnectionRefusedError()
            mock_sock_cls.return_value = mock_sock
            res = blender_connector.request_mesh_audit(port=9999)
        self.assertEqual(res["status"], "error")
        self.assertIn("ConnectionRefused", res["error_type"])

    def test_request_mesh_repair_connection_refused(self):
        with patch("socket.socket") as mock_sock_cls:
            mock_sock = MagicMock()
            mock_sock.connect.side_effect = ConnectionRefusedError()
            mock_sock_cls.return_value = mock_sock
            res = blender_connector.request_mesh_repair(port=9999)
        self.assertEqual(res["status"], "error")
        self.assertIn("ConnectionRefused", res["error_type"])

    def test_request_mesh_audit_returns_success_structure(self):
        fake_response = {
            "status": "success",
            "action": "mesh_doctor_audit",
            "audit": {"object_name": "Sphere", "is_watertight": False},
        }
        raw = (json.dumps(fake_response) + "\n").encode()

        with patch("socket.socket") as mock_sock_cls:
            mock_sock = MagicMock()
            mock_sock.recv.side_effect = [raw, b""]
            mock_sock_cls.return_value = mock_sock
            mock_sock.__enter__ = lambda s: s
            mock_sock.__exit__ = MagicMock(return_value=False)

            # Simulace recv vracejícího celý JSON najednou
            def recv_side(n):
                d = raw
                raw_holder = [d]
                if raw_holder[0]:
                    ret = raw_holder[0]
                    raw_holder[0] = b""
                    return ret
                return b""

            mock_sock.recv = recv_side
            res = blender_connector.request_mesh_audit()
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["audit"]["object_name"], "Sphere")


if __name__ == "__main__":
    unittest.main(verbosity=2)
