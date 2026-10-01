"""
Procedural Modeling & Parametric Engine — unit testy:
- TOOL_SCHEMAS obsahuje generate_parametric_model a apply_modifier_stack
- ALLOWED_TOOL_NAMES obsahuje oba nástroje
- parse_tool_call rozpozná volání pro generování modelů i aplikaci modifikátorů
- dispatch() vrátí chybu BlenderNotConnected
- dispatch() úspěšně zpracuje mock model i modifier stack odpověď a formátuje UI reporty
- Expertní prompt obsahuje klíčová slova (CAD, Hard-Surface, Tolerance, Weighted Normal, Bevel)
- blender_connector.request_parametric_model a request_modifier_stack: ověření chování a error handlingu
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

MOCK_MODEL_RESPONSE = {
    "status": "success",
    "action": "generate_parametric_model",
    "model": {
        "object_name": "Parametric_Enclosure",
        "model_type": "enclosure",
        "dimensions": {
            "width_mm": 100.0,
            "depth_mm": 80.0,
            "height_mm": 40.0,
            "wall_thickness_mm": 3.0,
        },
        "vertex_count": 48,
        "polygon_count": 46,
        "modifiers": ["Solidify", "Bevel"],
    },
}

MOCK_MODIFIER_RESPONSE = {
    "status": "success",
    "action": "apply_modifier_stack",
    "object_name": "Parametric_Enclosure",
    "stack_type": "hard_surface",
    "applied_immediately": False,
    "modifiers_count": 2,
    "modifiers": [
        {"name": "HS_Bevel", "type": "BEVEL", "width": 0.002, "segments": 3},
        {"name": "HS_WeightedNormal", "type": "WEIGHTED_NORMAL", "keep_sharp": True},
    ],
}


class TestParametricToolSchemas(unittest.TestCase):
    def test_parametric_tools_in_schemas(self):
        names = [t["function"]["name"] for t in TOOL_SCHEMAS]
        self.assertIn("generate_parametric_model", names)
        self.assertIn("apply_modifier_stack", names)

    def test_model_type_enum_in_schema(self):
        schema = next(
            t for t in TOOL_SCHEMAS if t["function"]["name"] == "generate_parametric_model"
        )
        props = schema["function"]["parameters"]["properties"]
        self.assertIn("model_type", props)
        enum_vals = props["model_type"].get("enum", [])
        self.assertIn("enclosure", enum_vals)
        self.assertIn("gear", enum_vals)
        self.assertIn("bracket", enum_vals)

    def test_stack_type_enum_in_schema(self):
        schema = next(
            t for t in TOOL_SCHEMAS if t["function"]["name"] == "apply_modifier_stack"
        )
        props = schema["function"]["parameters"]["properties"]
        self.assertIn("stack_type", props)
        enum_vals = props["stack_type"].get("enum", [])
        self.assertIn("hard_surface", enum_vals)
        self.assertIn("clean_solidify", enum_vals)
        self.assertIn("subdivision_bevel", enum_vals)

    def test_allowed_tool_names_contains_parametric_tools(self):
        self.assertIn("generate_parametric_model", ALLOWED_TOOL_NAMES)
        self.assertIn("apply_modifier_stack", ALLOWED_TOOL_NAMES)

    def test_total_tool_count_is_thirteen(self):
        self.assertGreaterEqual(len(ALLOWED_TOOL_NAMES), 13)


class TestParametricParseToolCall(unittest.TestCase):
    def test_parse_generate_model_compact(self):
        text = json.dumps(
            {
                "tool": "generate_parametric_model",
                "arguments": {
                    "model_type": "gear",
                    "dimensions": {"teeth_count": 24, "radius": 0.06},
                },
            }
        )
        result = parse_tool_call(text)
        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "generate_parametric_model")
        self.assertEqual(result["arguments"].get("model_type"), "gear")
        self.assertEqual(result["arguments"]["dimensions"].get("teeth_count"), 24)

    def test_parse_modifier_stack_with_args(self):
        text = json.dumps(
            {
                "tool": "apply_modifier_stack",
                "arguments": {
                    "stack_type": "hard_surface",
                    "params": {"bevel_width": 0.003},
                },
            }
        )
        result = parse_tool_call(text)
        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "apply_modifier_stack")
        self.assertEqual(result["arguments"].get("stack_type"), "hard_surface")

    def test_parse_openai_format(self):
        text = json.dumps(
            {
                "type": "function",
                "function": {
                    "name": "generate_parametric_model",
                    "arguments": json.dumps({"model_type": "bracket"}),
                },
            }
        )
        result = parse_tool_call(text)
        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "generate_parametric_model")


class TestParametricDispatcherErrors(unittest.TestCase):
    def _dispatcher(self):
        return UnifiedToolDispatcher(
            llm=None,
            config={"blender": {"host": "127.0.0.1", "port": 9999}},
        )

    def test_model_blender_not_connected(self):
        d = self._dispatcher()
        with patch("blender_connector.is_blender_available", return_value=False):
            res = d.dispatch("generate_parametric_model", {"model_type": "enclosure"})
        self.assertEqual(res["status"], "error")
        self.assertIn("BlenderNotConnected", res.get("error", ""))

    def test_modifier_blender_not_connected(self):
        d = self._dispatcher()
        with patch("blender_connector.is_blender_available", return_value=False):
            res = d.dispatch("apply_modifier_stack", {"stack_type": "hard_surface"})
        self.assertEqual(res["status"], "error")
        self.assertIn("BlenderNotConnected", res.get("error", ""))


class TestParametricDispatcherSuccess(unittest.TestCase):
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

    def test_generate_model_success(self):
        d, tokens, statuses = self._dispatcher()
        with patch("blender_connector.is_blender_available", return_value=True), \
             patch("blender_connector.request_parametric_model", return_value=MOCK_MODEL_RESPONSE):
            res = d.dispatch("generate_parametric_model", {"model_type": "enclosure"})

        self.assertEqual(res["status"], "success")
        self.assertEqual(res["tool"], "generate_parametric_model")
        self.assertIn("model", res)
        self.assertIn("_expert_system_prompt", res)
        self.assertIn("Parametric_Enclosure", res["result"])
        self.assertIn("enclosure", res["result"])

        full = "".join(tokens)
        self.assertIn("Parametric CAD Model", full)
        self.assertIn("Parametric_Enclosure", full)
        self.assertIn("100.0", full)

    def test_apply_modifier_stack_success(self):
        d, tokens, statuses = self._dispatcher()
        with patch("blender_connector.is_blender_available", return_value=True), \
             patch("blender_connector.request_modifier_stack", return_value=MOCK_MODIFIER_RESPONSE):
            res = d.dispatch("apply_modifier_stack", {"stack_type": "hard_surface"})

        self.assertEqual(res["status"], "success")
        self.assertEqual(res["tool"], "apply_modifier_stack")
        self.assertIn("modifiers", res)
        self.assertIn("_expert_system_prompt", res)
        self.assertIn("HS_WeightedNormal", res["result"])

        full = "".join(tokens)
        self.assertIn("Modifier Stack Aplikován", full)
        self.assertIn("HS_Bevel", full)
        self.assertIn("HS_WeightedNormal", full)

    def test_expert_prompt_contents(self):
        d, _, _ = self._dispatcher()
        with patch("blender_connector.is_blender_available", return_value=True), \
             patch("blender_connector.request_parametric_model", return_value=MOCK_MODEL_RESPONSE):
            res = d.dispatch("generate_parametric_model", {})

        prompt = res["_expert_system_prompt"]
        self.assertIn("CAD", prompt)
        self.assertIn("Hard-Surface", prompt)
        self.assertIn("Weighted Normal", prompt)
        self.assertIn("Bevel", prompt)


class TestParametricConnectorFunctions(unittest.TestCase):
    def test_model_connection_refused(self):
        with patch("socket.socket") as mock_cls:
            mock_sock = MagicMock()
            mock_sock.connect.side_effect = ConnectionRefusedError()
            mock_cls.return_value = mock_sock
            res = blender_connector.request_parametric_model(port=9999)
        self.assertEqual(res["status"], "error")
        self.assertEqual(res["error_type"], "ConnectionRefused")

    def test_modifier_connection_refused(self):
        with patch("socket.socket") as mock_cls:
            mock_sock = MagicMock()
            mock_sock.connect.side_effect = ConnectionRefusedError()
            mock_cls.return_value = mock_sock
            res = blender_connector.request_modifier_stack(port=9999)
        self.assertEqual(res["status"], "error")
        self.assertEqual(res["error_type"], "ConnectionRefused")

    def test_model_parameters_forwarded(self):
        sent_payloads = []

        def fake_send(payload, **kwargs):
            sent_payloads.append(payload)
            return {"status": "success", "model": {}}

        with patch("blender_connector._send_blender_request", side_effect=fake_send):
            blender_connector.request_parametric_model(
                model_type="gear", dimensions={"teeth_count": 30}
            )

        self.assertEqual(sent_payloads[0]["model_type"], "gear")
        self.assertEqual(sent_payloads[0]["dimensions"]["teeth_count"], 30)

    def test_modifier_parameters_forwarded(self):
        sent_payloads = []

        def fake_send(payload, **kwargs):
            sent_payloads.append(payload)
            return {"status": "success", "modifiers": []}

        with patch("blender_connector._send_blender_request", side_effect=fake_send):
            blender_connector.request_modifier_stack(
                stack_type="clean_solidify", params={"thickness": 0.005}, apply_immediately=True
            )

        self.assertEqual(sent_payloads[0]["stack_type"], "clean_solidify")
        self.assertEqual(sent_payloads[0]["params"]["thickness"], 0.005)
        self.assertTrue(sent_payloads[0]["apply_immediately"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
