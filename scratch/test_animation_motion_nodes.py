#!/usr/bin/env python3
"""
Unit testy pro modul 'Advanced Animation & Motion Nodes Engine':
- Ověření JSON schémat v TOOL_SCHEMAS a ALLOWED_TOOL_NAMES (16 nástrojů).
- Ověření parsování tool calls pro apply_fcurve_animation a create_motion_node_setup.
- Ověření klientských funkcí v blender_connector.py (request_fcurve_animation, request_motion_nodes).
- Ověření chování UnifiedToolDispatcheru (error handling, formátování výstupu, expertní systémový prompt).
"""

import json
import unittest
from unittest.mock import MagicMock, patch

from blender_connector import (
    request_fcurve_animation,
    request_motion_nodes,
)
from llama_module import (
    ALLOWED_TOOL_NAMES,
    TOOL_SCHEMAS,
    UnifiedToolDispatcher,
    parse_tool_call,
)

# ── Sdílená mock data ──────────────────────────────────────────────────────────

MOCK_FCURVE_RESPONSE = {
    "status": "success",
    "action": "apply_fcurve_animation",
    "object_name": "Camera_Rig",
    "property_name": "location",
    "data_path": "location",
    "interpolation": "BEZIER",
    "modifier_type": "NOISE",
    "applied_modifiers": ["NOISE"],
    "fcurves_count": 3,
    "keyframes_count": 6,
    "frame_range": [1, 60],
}

MOCK_MOTION_GN_RESPONSE = {
    "status": "success",
    "action": "create_motion_node_setup",
    "motion_type": "geometry_nodes",
    "object_name": "Turbine_Fan",
    "modifier_name": "MotionNodes",
    "node_group_name": "ProceduralMotion_Rotation",
    "target_property": "rotation",
    "axis": "Z",
    "speed": 2.5,
    "node_count": 6,
    "link_count": 5,
    "nodes": [
        {"name": "Group Input", "type": "GROUP_INPUT", "label": ""},
        {"name": "Scene Time", "type": "SCENE_TIME", "label": ""},
        {"name": "Math", "type": "MATH", "label": ""},
        {"name": "Combine XYZ", "type": "COMBINE_XYZ", "label": ""},
        {"name": "Transform Geometry", "type": "TRANSFORM", "label": ""},
        {"name": "Group Output", "type": "GROUP_OUTPUT", "label": ""},
    ],
}

MOCK_MOTION_DRIVER_RESPONSE = {
    "status": "success",
    "action": "create_motion_node_setup",
    "motion_type": "driver",
    "object_name": "Radar_Dish",
    "target_property": "rotation_euler",
    "axis": "Z",
    "speed": 0.05,
    "expression": "frame * 0.05",
    "drivers_count": 1,
    "drivers": [
        {"property": "rotation_euler", "index": 2, "expression": "frame * 0.05"}
    ],
}


class TestAnimationToolSchemas(unittest.TestCase):
    def test_animation_tools_in_schemas(self):
        names = [t["function"]["name"] for t in TOOL_SCHEMAS]
        self.assertIn("apply_fcurve_animation", names)
        self.assertIn("create_motion_node_setup", names)

    def test_fcurve_schema_properties(self):
        schema = next(
            t for t in TOOL_SCHEMAS if t["function"]["name"] == "apply_fcurve_animation"
        )
        props = schema["function"]["parameters"]["properties"]
        self.assertIn("property_name", props)
        self.assertIn("interpolation", props)
        self.assertIn("modifier_type", props)
        interp_enums = props["interpolation"].get("enum", [])
        self.assertIn("BEZIER", interp_enums)
        self.assertIn("LINEAR", interp_enums)
        self.assertIn("BOUNCE", interp_enums)

    def test_motion_nodes_schema_properties(self):
        schema = next(
            t for t in TOOL_SCHEMAS if t["function"]["name"] == "create_motion_node_setup"
        )
        props = schema["function"]["parameters"]["properties"]
        self.assertIn("motion_type", props)
        self.assertIn("target_property", props)
        self.assertIn("axis", props)
        motion_enums = props["motion_type"].get("enum", [])
        self.assertIn("geometry_nodes", motion_enums)
        self.assertIn("driver", motion_enums)

    def test_allowed_tool_names_contains_animation_tools(self):
        self.assertIn("apply_fcurve_animation", ALLOWED_TOOL_NAMES)
        self.assertIn("create_motion_node_setup", ALLOWED_TOOL_NAMES)

    def test_total_tool_count_is_sixteen(self):
        self.assertGreaterEqual(len(ALLOWED_TOOL_NAMES), 16)


class TestAnimationParseToolCall(unittest.TestCase):
    def test_parse_fcurve_compact(self):
        text = json.dumps(
            {
                "tool": "apply_fcurve_animation",
                "arguments": {
                    "property_name": "rotation",
                    "interpolation": "BOUNCE",
                    "modifier_type": "CYCLES",
                },
            }
        )
        result = parse_tool_call(text)
        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "apply_fcurve_animation")
        self.assertEqual(result["arguments"].get("property_name"), "rotation")
        self.assertEqual(result["arguments"].get("interpolation"), "BOUNCE")
        self.assertEqual(result["arguments"].get("modifier_type"), "CYCLES")

    def test_parse_motion_nodes_compact(self):
        text = json.dumps(
            {
                "tool": "create_motion_node_setup",
                "arguments": {
                    "motion_type": "geometry_nodes",
                    "target_property": "rotation",
                    "axis": "Z",
                    "speed": 1.5,
                },
            }
        )
        result = parse_tool_call(text)
        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "create_motion_node_setup")
        self.assertEqual(result["arguments"].get("motion_type"), "geometry_nodes")
        self.assertEqual(result["arguments"].get("axis"), "Z")
        self.assertEqual(result["arguments"].get("speed"), 1.5)

    def test_parse_openai_format(self):
        text = json.dumps(
            {
                "type": "function",
                "function": {
                    "name": "create_motion_node_setup",
                    "arguments": json.dumps({"motion_type": "driver", "axis": "X"}),
                },
            }
        )
        result = parse_tool_call(text)
        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "create_motion_node_setup")
        self.assertEqual(result["arguments"].get("motion_type"), "driver")


class TestAnimationConnectorFunctions(unittest.TestCase):
    def test_fcurve_parameters_forwarded(self):
        sent_payloads = []

        def fake_send(payload, **kwargs):
            sent_payloads.append(payload)
            return MOCK_FCURVE_RESPONSE

        with patch("blender_connector._send_blender_request", side_effect=fake_send):
            resp = request_fcurve_animation(
                property_name="location",
                interpolation="BEZIER",
                modifier_type="NOISE",
                start_frame=1,
                end_frame=60,
            )
        self.assertEqual(resp["status"], "success")
        self.assertEqual(resp["action"], "apply_fcurve_animation")
        self.assertEqual(resp["object_name"], "Camera_Rig")
        self.assertEqual(sent_payloads[0]["action"], "apply_fcurve_animation")
        self.assertEqual(sent_payloads[0]["property_name"], "location")
        self.assertEqual(sent_payloads[0]["interpolation"], "BEZIER")
        self.assertEqual(sent_payloads[0]["modifier_type"], "NOISE")
        self.assertEqual(sent_payloads[0]["start_frame"], 1)
        self.assertEqual(sent_payloads[0]["end_frame"], 60)

    def test_motion_nodes_parameters_forwarded(self):
        sent_payloads = []

        def fake_send(payload, **kwargs):
            sent_payloads.append(payload)
            return MOCK_MOTION_GN_RESPONSE

        with patch("blender_connector._send_blender_request", side_effect=fake_send):
            resp = request_motion_nodes(
                motion_type="geometry_nodes",
                target_property="rotation",
                axis="Z",
                speed=2.5,
            )
        self.assertEqual(resp["status"], "success")
        self.assertEqual(resp["action"], "create_motion_node_setup")
        self.assertEqual(resp["motion_type"], "geometry_nodes")
        self.assertEqual(sent_payloads[0]["action"], "create_motion_node_setup")
        self.assertEqual(sent_payloads[0]["motion_type"], "geometry_nodes")
        self.assertEqual(sent_payloads[0]["target_property"], "rotation")
        self.assertEqual(sent_payloads[0]["axis"], "Z")
        self.assertEqual(sent_payloads[0]["speed"], 2.5)

    def test_fcurve_connection_refused(self):
        with patch("socket.socket") as mock_cls:
            mock_sock = MagicMock()
            mock_sock.connect.side_effect = ConnectionRefusedError()
            mock_cls.return_value = mock_sock
            resp = request_fcurve_animation(port=9999, raise_on_error=False)
        self.assertEqual(resp["status"], "error")
        self.assertEqual(resp["error_type"], "ConnectionRefused")


class TestAnimationDispatcherSuccess(unittest.TestCase):
    @patch("blender_connector.is_blender_available", return_value=True)
    @patch("blender_connector.request_fcurve_animation", return_value=MOCK_FCURVE_RESPONSE)
    def test_fcurve_success(self, mock_req, mock_avail):
        tokens = []
        dispatcher = UnifiedToolDispatcher(callback_on_token=tokens.append)
        res = dispatcher.dispatch(
            "apply_fcurve_animation",
            {"property_name": "location", "interpolation": "BEZIER", "modifier_type": "NOISE"},
        )
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["tool"], "apply_fcurve_animation")
        self.assertEqual(res["object_name"], "Camera_Rig")
        self.assertIn("F-Curve Animation Studio", "".join(tokens))
        self.assertIn("_expert_system_prompt", res)

    @patch("blender_connector.is_blender_available", return_value=True)
    @patch("blender_connector.request_motion_nodes", return_value=MOCK_MOTION_GN_RESPONSE)
    def test_motion_gn_success(self, mock_req, mock_avail):
        tokens = []
        dispatcher = UnifiedToolDispatcher(callback_on_token=tokens.append)
        res = dispatcher.dispatch(
            "create_motion_node_setup",
            {"motion_type": "geometry_nodes", "target_property": "rotation", "axis": "Z", "speed": 2.5},
        )
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["tool"], "create_motion_node_setup")
        self.assertEqual(res["object_name"], "Turbine_Fan")
        self.assertIn("Motion Nodes Setup", "".join(tokens))
        self.assertIn("_expert_system_prompt", res)

    @patch("blender_connector.is_blender_available", return_value=True)
    @patch("blender_connector.request_motion_nodes", return_value=MOCK_MOTION_DRIVER_RESPONSE)
    def test_motion_driver_success(self, mock_req, mock_avail):
        tokens = []
        dispatcher = UnifiedToolDispatcher(callback_on_token=tokens.append)
        res = dispatcher.dispatch(
            "create_motion_node_setup",
            {"motion_type": "driver", "axis": "Z", "speed": 0.05},
        )
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["tool"], "create_motion_node_setup")
        self.assertEqual(res["object_name"], "Radar_Dish")
        self.assertIn("Procedural Motion Driver", "".join(tokens))

    @patch("blender_connector.is_blender_available", return_value=True)
    @patch("blender_connector.request_fcurve_animation", return_value=MOCK_FCURVE_RESPONSE)
    def test_expert_prompt_contents(self, mock_req, mock_avail):
        dispatcher = UnifiedToolDispatcher()
        res = dispatcher.dispatch("apply_fcurve_animation", {})
        prompt = res.get("_expert_system_prompt", "")
        self.assertIn("Lead 3D Animátor", prompt)
        self.assertIn("Graph Editor", prompt)
        self.assertIn("Scene Time", prompt)
        self.assertIn("Motion Blur", prompt)


class TestAnimationDispatcherErrors(unittest.TestCase):
    @patch("blender_connector.is_blender_available", return_value=False)
    def test_fcurve_blender_not_connected(self, mock_avail):
        dispatcher = UnifiedToolDispatcher()
        res = dispatcher.dispatch("apply_fcurve_animation", {"property_name": "location"})
        self.assertEqual(res["status"], "error")
        self.assertEqual(res["error"], "BlenderNotConnected")

    @patch("blender_connector.is_blender_available", return_value=False)
    def test_motion_blender_not_connected(self, mock_avail):
        dispatcher = UnifiedToolDispatcher()
        res = dispatcher.dispatch("create_motion_node_setup", {"motion_type": "geometry_nodes"})
        self.assertEqual(res["status"], "error")
        self.assertEqual(res["error"], "BlenderNotConnected")


if __name__ == "__main__":
    unittest.main()
