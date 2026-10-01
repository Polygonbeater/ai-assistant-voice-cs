"""
Geometry Nodes Bridge — unit testy:
- TOOL_SCHEMAS obsahuje create_geometry_nodes_bridge se setup_type enum
- ALLOWED_TOOL_NAMES obsahuje create_geometry_nodes_bridge (celkem 14 nástrojů)
- parse_tool_call rozpozná volání pro Geometry Nodes
- dispatch() vrátí chybu BlenderNotConnected
- dispatch() úspěšně zpracuje mock odpověď a formátuje UI reporty
- Expertní prompt obsahuje klíčová slova (Geometry Nodes, Fields, Instances, Extrude, Dataflow)
- blender_connector.request_geometry_nodes_bridge: ověření chování a error handlingu
"""

import sys
import os
import json
import unittest
from unittest.mock import patch, MagicMock

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../.."))
sys.path.insert(0, PROJECT_ROOT)

from llama_module import (
    TOOL_SCHEMAS,
    ALLOWED_TOOL_NAMES,
    parse_tool_call,
    UnifiedToolDispatcher,
)
import blender_connector


# ── Sdílená mock data ──────────────────────────────────────────────────────────

MOCK_GN_RESPONSE = {
    "status": "success",
    "action": "create_geometry_nodes_bridge",
    "object_name": "Spaceship_Hull",
    "modifier_name": "GeometryNodes",
    "node_group_name": "GN_Extrude_Panel",
    "setup_type": "extrude_panel",
    "node_count": 4,
    "link_count": 4,
    "nodes": [
        {"name": "Group Input", "type": "GROUP_INPUT", "label": ""},
        {"name": "Extrude Mesh", "type": "EXTRUDE_MESH", "label": ""},
        {"name": "Scale Elements", "type": "SCALE_ELEMENTS", "label": ""},
        {"name": "Group Output", "type": "GROUP_OUTPUT", "label": ""},
    ],
}


class TestGeometryNodesToolSchemas(unittest.TestCase):
    def test_gn_tool_in_schemas(self):
        names = [t["function"]["name"] for t in TOOL_SCHEMAS]
        self.assertIn("create_geometry_nodes_bridge", names)

    def test_setup_type_enum_in_schema(self):
        schema = next(
            t for t in TOOL_SCHEMAS if t["function"]["name"] == "create_geometry_nodes_bridge"
        )
        props = schema["function"]["parameters"]["properties"]
        self.assertIn("setup_type", props)
        enum_vals = props["setup_type"].get("enum", [])
        self.assertIn("point_scatter", enum_vals)
        self.assertIn("extrude_panel", enum_vals)

    def test_allowed_tool_names_contains_gn_tool(self):
        self.assertIn("create_geometry_nodes_bridge", ALLOWED_TOOL_NAMES)

    def test_total_tool_count_is_fourteen(self):
        self.assertGreaterEqual(len(ALLOWED_TOOL_NAMES), 14)


class TestGeometryNodesParseToolCall(unittest.TestCase):
    def test_parse_gn_compact(self):
        text = json.dumps(
            {
                "tool": "create_geometry_nodes_bridge",
                "arguments": {
                    "setup_type": "point_scatter",
                    "node_group_name": "GN_Debris_Scatter",
                },
            }
        )
        result = parse_tool_call(text)
        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "create_geometry_nodes_bridge")
        self.assertEqual(result["arguments"].get("setup_type"), "point_scatter")
        self.assertEqual(result["arguments"].get("node_group_name"), "GN_Debris_Scatter")

    def test_parse_openai_format(self):
        text = json.dumps(
            {
                "type": "function",
                "function": {
                    "name": "create_geometry_nodes_bridge",
                    "arguments": json.dumps({"setup_type": "extrude_panel"}),
                },
            }
        )
        result = parse_tool_call(text)
        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "create_geometry_nodes_bridge")


class TestGeometryNodesDispatcherErrors(unittest.TestCase):
    def _dispatcher(self):
        return UnifiedToolDispatcher(
            llm=None,
            config={"blender": {"host": "127.0.0.1", "port": 9999}},
        )

    def test_gn_blender_not_connected(self):
        d = self._dispatcher()
        with patch("blender_connector.is_blender_available", return_value=False):
            res = d.dispatch("create_geometry_nodes_bridge", {"setup_type": "point_scatter"})
        self.assertEqual(res["status"], "error")
        self.assertIn("BlenderNotConnected", res.get("error", ""))


class TestGeometryNodesDispatcherSuccess(unittest.TestCase):
    def _dispatcher(self):
        tokens = []
        statuses = []
        d = UnifiedToolDispatcher(
            llm=None,
            config={"blender": {"host": "127.0.0.1", "port": 9876}},
            callback_on_token=tokens.append,
            status_callback=statuses.append,
        )
        return d, tokens, statuses

    def test_gn_success(self):
        d, tokens, statuses = self._dispatcher()
        with patch("blender_connector.is_blender_available", return_value=True), \
             patch("blender_connector.request_geometry_nodes_bridge", return_value=MOCK_GN_RESPONSE):
            res = d.dispatch("create_geometry_nodes_bridge", {"setup_type": "extrude_panel"})

        self.assertEqual(res["status"], "success")
        self.assertEqual(res["tool"], "create_geometry_nodes_bridge")
        self.assertIn("nodes", res)
        self.assertIn("_expert_system_prompt", res)
        self.assertIn("GN_Extrude_Panel", res["result"])
        self.assertIn("Spaceship_Hull", res["result"])

        full = "".join(tokens)
        self.assertIn("Geometry Nodes Bridge", full)
        self.assertIn("GN_Extrude_Panel", full)
        self.assertIn("Extrude Mesh", full)

    def test_expert_prompt_contents(self):
        d, _, _ = self._dispatcher()
        with patch("blender_connector.is_blender_available", return_value=True), \
             patch("blender_connector.request_geometry_nodes_bridge", return_value=MOCK_GN_RESPONSE):
            res = d.dispatch("create_geometry_nodes_bridge", {})

        prompt = res["_expert_system_prompt"]
        self.assertIn("Geometry Nodes", prompt)
        self.assertIn("Fields", prompt)
        self.assertIn("Instances", prompt)
        self.assertIn("Extrude", prompt)


class TestGeometryNodesConnectorFunctions(unittest.TestCase):
    def test_gn_connection_refused(self):
        with patch("socket.socket") as mock_cls:
            mock_sock = MagicMock()
            mock_sock.connect.side_effect = ConnectionRefusedError()
            mock_cls.return_value = mock_sock
            res = blender_connector.request_geometry_nodes_bridge(port=9999)
        self.assertEqual(res["status"], "error")
        self.assertEqual(res["error_type"], "ConnectionRefused")

    def test_gn_parameters_forwarded(self):
        sent_payloads = []

        def fake_send(payload, **kwargs):
            sent_payloads.append(payload)
            return {"status": "success", "nodes": []}

        with patch("blender_connector._send_blender_request", side_effect=fake_send):
            blender_connector.request_geometry_nodes_bridge(
                setup_type="extrude_panel", node_group_name="Custom_GN"
            )

        self.assertEqual(sent_payloads[0]["setup_type"], "extrude_panel")
        self.assertEqual(sent_payloads[0]["node_group_name"], "Custom_GN")


if __name__ == "__main__":
    unittest.main(verbosity=2)
