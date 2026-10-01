#!/usr/bin/env python3
"""
Unit testy pro modul 'Image-to-3D Bridge':
- Ověření JSON schémat pro setup_blueprint_reference a vectorize_image_to_3d.
- Ověření celkového počtu 18 nástrojů v ALLOWED_TOOL_NAMES.
- Ověření kognitivní parametrizace (Vision AI) v DEFAULT_SYSTEM_PROMPT a build_tool_use_prompt.
- Ověření parsování tool calls.
- Ověření klientských funkcí v blender_connector.py.
- Ověření UnifiedToolDispatcheru a expertního systémového promptu.
"""

import json
import unittest
from unittest.mock import MagicMock, patch

from blender_connector import (
    request_blueprint_setup,
    request_vectorize_to_3d,
)
from llama_module import (
    ALLOWED_TOOL_NAMES,
    DEFAULT_SYSTEM_PROMPT,
    TOOL_SCHEMAS,
    UnifiedToolDispatcher,
    build_tool_use_prompt,
    parse_tool_call,
)

# ── Sdílená mock data ──────────────────────────────────────────────────────────

MOCK_BLUEPRINT_RESPONSE = {
    "status": "success",
    "action": "setup_blueprint_reference",
    "object_name": "Blueprint_FRONT",
    "image_path": "/tmp/gear_blueprint.png",
    "axis": "FRONT",
    "alpha": 0.5,
    "location": [0.0, 0.05, 0.0],
    "rotation_euler": [1.5708, 0.0, 0.0],
    "hide_select": True,
}

MOCK_VECTORIZE_RESPONSE = {
    "status": "success",
    "action": "vectorize_image_to_3d",
    "object_name": "Vectorized_Logo_3D",
    "image_path": "/tmp/company_logo.png",
    "svg_path": "/tmp/vectorized_company_logo.svg",
    "contours_count": 3,
    "vertex_count": 142,
    "polygon_count": 138,
    "extrude_depth": 0.02,
    "bevel_depth": 0.002,
    "dimensions": [1.0, 0.85, 0.02],
}


class TestImageTo3DToolSchemas(unittest.TestCase):
    def test_image_tools_in_schemas(self):
        names = [t["function"]["name"] for t in TOOL_SCHEMAS]
        self.assertIn("setup_blueprint_reference", names)
        self.assertIn("vectorize_image_to_3d", names)

    def test_blueprint_schema_properties(self):
        schema = next(
            t for t in TOOL_SCHEMAS if t["function"]["name"] == "setup_blueprint_reference"
        )
        props = schema["function"]["parameters"]["properties"]
        self.assertIn("image_path", props)
        self.assertIn("axis", props)
        self.assertIn("alpha", props)
        axis_enums = props["axis"].get("enum", [])
        self.assertIn("FRONT", axis_enums)
        self.assertIn("TOP", axis_enums)
        self.assertIn("RIGHT", axis_enums)

    def test_vectorize_schema_properties(self):
        schema = next(
            t for t in TOOL_SCHEMAS if t["function"]["name"] == "vectorize_image_to_3d"
        )
        props = schema["function"]["parameters"]["properties"]
        self.assertIn("image_path", props)
        self.assertIn("extrude_depth", props)
        self.assertIn("bevel_depth", props)
        self.assertIn("target_size", props)
        self.assertIn("invert", props)

    def test_allowed_tool_names_contains_image_tools(self):
        self.assertIn("setup_blueprint_reference", ALLOWED_TOOL_NAMES)
        self.assertIn("vectorize_image_to_3d", ALLOWED_TOOL_NAMES)

    def test_total_tool_count_is_eighteen(self):
        self.assertGreaterEqual(len(ALLOWED_TOOL_NAMES), 18)


class TestCognitiveVisionParametrization(unittest.TestCase):
    def test_default_system_prompt_contains_vision_instruction(self):
        self.assertIn("KOGNITIVNÍ PARAMETRIZACE (VISION AI)", DEFAULT_SYSTEM_PROMPT)
        self.assertIn("generate_parametric_model", DEFAULT_SYSTEM_PROMPT)
        self.assertIn("odhadni poměry a reálné rozměry v mm", DEFAULT_SYSTEM_PROMPT)

    def test_tool_use_prompt_contains_vision_instruction(self):
        prompt = build_tool_use_prompt()
        self.assertIn("KOGNITIVNÍ VIZUÁLNÍ PARAMETRIZACE", prompt)
        self.assertIn("generate_parametric_model", prompt)
        self.assertIn("odhadni poměry a reálné rozměry v mm", prompt)


class TestImageTo3DParseToolCall(unittest.TestCase):
    def test_parse_blueprint_compact(self):
        text = json.dumps(
            {
                "tool": "setup_blueprint_reference",
                "arguments": {
                    "image_path": "/home/polygon/blueprints/chassis_front.png",
                    "axis": "FRONT",
                    "alpha": 0.5,
                },
            }
        )
        result = parse_tool_call(text)
        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "setup_blueprint_reference")
        self.assertEqual(result["arguments"].get("axis"), "FRONT")
        self.assertEqual(result["arguments"].get("alpha"), 0.5)

    def test_parse_vectorize_compact(self):
        text = json.dumps(
            {
                "tool": "vectorize_image_to_3d",
                "arguments": {
                    "image_path": "/home/polygon/logo.png",
                    "extrude_depth": 0.03,
                    "bevel_depth": 0.003,
                },
            }
        )
        result = parse_tool_call(text)
        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "vectorize_image_to_3d")
        self.assertEqual(result["arguments"].get("extrude_depth"), 0.03)

    def test_parse_openai_format(self):
        text = json.dumps(
            {
                "type": "function",
                "function": {
                    "name": "setup_blueprint_reference",
                    "arguments": json.dumps({"image_path": "/tmp/plan.jpg", "axis": "TOP"}),
                },
            }
        )
        result = parse_tool_call(text)
        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "setup_blueprint_reference")
        self.assertEqual(result["arguments"].get("axis"), "TOP")


class TestImageTo3DConnectorFunctions(unittest.TestCase):
    def test_blueprint_parameters_forwarded(self):
        sent_payloads = []

        def fake_send(payload, **kwargs):
            sent_payloads.append(payload)
            return MOCK_BLUEPRINT_RESPONSE

        with patch("blender_connector._send_blender_request", side_effect=fake_send):
            resp = request_blueprint_setup(
                image_path="/tmp/test.png",
                axis="TOP",
                alpha=0.6,
                name="My_Blueprint",
            )
        self.assertEqual(resp["status"], "success")
        self.assertEqual(resp["action"], "setup_blueprint_reference")
        self.assertEqual(sent_payloads[0]["action"], "setup_blueprint_reference")
        self.assertEqual(sent_payloads[0]["image_path"], "/tmp/test.png")
        self.assertEqual(sent_payloads[0]["axis"], "TOP")
        self.assertEqual(sent_payloads[0]["alpha"], 0.6)
        self.assertEqual(sent_payloads[0]["name"], "My_Blueprint")

    def test_vectorize_parameters_forwarded(self):
        sent_payloads = []

        def fake_send(payload, **kwargs):
            sent_payloads.append(payload)
            return MOCK_VECTORIZE_RESPONSE

        with patch("blender_connector._send_blender_request", side_effect=fake_send):
            resp = request_vectorize_to_3d(
                image_path="/tmp/logo.png",
                extrude_depth=0.04,
                bevel_depth=0.005,
                target_size=1.5,
                invert=True,
                object_name="Brand_3D",
            )
        self.assertEqual(resp["status"], "success")
        self.assertEqual(resp["action"], "vectorize_image_to_3d")
        self.assertEqual(sent_payloads[0]["action"], "vectorize_image_to_3d")
        self.assertEqual(sent_payloads[0]["image_path"], "/tmp/logo.png")
        self.assertEqual(sent_payloads[0]["extrude_depth"], 0.04)
        self.assertEqual(sent_payloads[0]["bevel_depth"], 0.005)
        self.assertEqual(sent_payloads[0]["target_size"], 1.5)
        self.assertTrue(sent_payloads[0]["invert"])
        self.assertEqual(sent_payloads[0]["object_name"], "Brand_3D")

    def test_blueprint_connection_refused(self):
        with patch("socket.socket") as mock_cls:
            mock_sock = MagicMock()
            mock_sock.connect.side_effect = ConnectionRefusedError()
            mock_cls.return_value = mock_sock
            resp = request_blueprint_setup(image_path="/tmp/none.png", port=9999, raise_on_error=False)
        self.assertEqual(resp["status"], "error")
        self.assertEqual(resp["error_type"], "ConnectionRefused")


class TestImageTo3DDispatcherSuccess(unittest.TestCase):
    @patch("blender_connector.is_blender_available", return_value=True)
    @patch("blender_connector.request_blueprint_setup", return_value=MOCK_BLUEPRINT_RESPONSE)
    def test_blueprint_success(self, mock_req, mock_avail):
        tokens = []
        dispatcher = UnifiedToolDispatcher(callback_on_token=tokens.append)
        res = dispatcher.dispatch(
            "setup_blueprint_reference",
            {"image_path": "/tmp/gear_blueprint.png", "axis": "FRONT", "alpha": 0.5},
        )
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["tool"], "setup_blueprint_reference")
        self.assertEqual(res["object_name"], "Blueprint_FRONT")
        self.assertIn("Blueprint Reference Setup", "".join(tokens))
        self.assertIn("_expert_system_prompt", res)

    @patch("blender_connector.is_blender_available", return_value=True)
    @patch("blender_connector.request_vectorize_to_3d", return_value=MOCK_VECTORIZE_RESPONSE)
    def test_vectorize_success(self, mock_req, mock_avail):
        tokens = []
        dispatcher = UnifiedToolDispatcher(callback_on_token=tokens.append)
        res = dispatcher.dispatch(
            "vectorize_image_to_3d",
            {"image_path": "/tmp/company_logo.png", "extrude_depth": 0.02},
        )
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["tool"], "vectorize_image_to_3d")
        self.assertEqual(res["object_name"], "Vectorized_Logo_3D")
        self.assertIn("Image-to-3D Vectorizer", "".join(tokens))
        self.assertIn("_expert_system_prompt", res)

    @patch("blender_connector.is_blender_available", return_value=True)
    @patch("blender_connector.request_vectorize_to_3d", return_value=MOCK_VECTORIZE_RESPONSE)
    def test_expert_prompt_contents(self, mock_req, mock_avail):
        dispatcher = UnifiedToolDispatcher()
        res = dispatcher.dispatch("vectorize_image_to_3d", {"image_path": "/tmp/test.png"})
        prompt = res.get("_expert_system_prompt", "")
        self.assertIn("3D Concept Artist", prompt)
        self.assertIn("blueprint", prompt)
        self.assertIn("Bevel", prompt)
        self.assertIn("ortografick", prompt)


class TestImageTo3DDispatcherErrors(unittest.TestCase):
    @patch("blender_connector.is_blender_available", return_value=False)
    def test_blueprint_blender_not_connected(self, mock_avail):
        dispatcher = UnifiedToolDispatcher()
        res = dispatcher.dispatch("setup_blueprint_reference", {"image_path": "/tmp/img.png"})
        self.assertEqual(res["status"], "error")
        self.assertEqual(res["error"], "BlenderNotConnected")

    @patch("blender_connector.is_blender_available", return_value=False)
    def test_vectorize_blender_not_connected(self, mock_avail):
        dispatcher = UnifiedToolDispatcher()
        res = dispatcher.dispatch("vectorize_image_to_3d", {"image_path": "/tmp/logo.png"})
        self.assertEqual(res["status"], "error")
        self.assertEqual(res["error"], "BlenderNotConnected")


if __name__ == "__main__":
    unittest.main()
