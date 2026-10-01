"""
Procedural Shader & Node Tree Generator — unit testy:
- TOOL_SCHEMAS obsahuje create_procedural_shader (se shader_type enum a material_name)
- ALLOWED_TOOL_NAMES obsahuje create_procedural_shader
- parse_tool_call rozpozná JSON volání create_procedural_shader
- dispatch() vrátí chybu BlenderNotConnected
- dispatch() úspěšně zpracuje mock odpověď a formátuje UI report
- Expertní prompt obsahuje klíčová slova (PBR, IOR, Roughness, Metallic, Bump, Fresnel)
- blender_connector.request_procedural_shader: validace parametrů + error handling
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

MOCK_SHADER_RESPONSE = {
    "status": "success",
    "action": "create_procedural_shader",
    "shader": {
        "material_name": "Titanium_Brushed",
        "shader_type": "brushed_metal",
        "assigned_to_object": "Suzanne",
        "node_count": 6,
        "link_count": 6,
        "nodes": [
            {"name": "Material Output", "type": "OUTPUT_MATERIAL", "label": ""},
            {"name": "Principled BSDF", "type": "BSDF_PRINCIPLED", "label": ""},
            {"name": "Texture Coordinate", "type": "TEX_COORD", "label": ""},
            {"name": "Mapping", "type": "MAPPING", "label": ""},
            {"name": "Noise Texture", "type": "TEX_NOISE", "label": ""},
            {"name": "Bump", "type": "BUMP", "label": ""},
        ],
        "key_parameters": {
            "shader_type": "brushed_metal",
            "metallic": 1.0,
            "base_color": "Silver/Alloy",
            "roughness": "0.2-0.35 (mapped)",
        },
    },
}


class TestProceduralShaderToolSchemas(unittest.TestCase):
    def test_create_procedural_shader_in_schemas(self):
        names = [t["function"]["name"] for t in TOOL_SCHEMAS]
        self.assertIn("create_procedural_shader", names)

    def test_shader_type_enum_in_schema(self):
        schema = next(
            t for t in TOOL_SCHEMAS if t["function"]["name"] == "create_procedural_shader"
        )
        props = schema["function"]["parameters"]["properties"]
        self.assertIn("shader_type", props)
        enum_vals = props["shader_type"].get("enum", [])
        self.assertIn("brushed_metal", enum_vals)
        self.assertIn("matte_plastic", enum_vals)
        self.assertIn("rusted_iron", enum_vals)
        self.assertIn("glossy_glass", enum_vals)

    def test_material_name_in_schema(self):
        schema = next(
            t for t in TOOL_SCHEMAS if t["function"]["name"] == "create_procedural_shader"
        )
        props = schema["function"]["parameters"]["properties"]
        self.assertIn("material_name", props)

    def test_allowed_tool_names_contains_shader(self):
        self.assertIn("create_procedural_shader", ALLOWED_TOOL_NAMES)

    def test_total_tool_count_is_nine(self):
        # Minimálně 9 nástrojů
        self.assertGreaterEqual(len(ALLOWED_TOOL_NAMES), 9)


class TestProceduralShaderParseToolCall(unittest.TestCase):
    def test_parse_compact_no_args(self):
        text = json.dumps({"tool": "create_procedural_shader", "arguments": {}})
        result = parse_tool_call(text)
        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "create_procedural_shader")

    def test_parse_with_type_and_name_args(self):
        text = json.dumps(
            {
                "tool": "create_procedural_shader",
                "arguments": {
                    "shader_type": "rusted_iron",
                    "material_name": "Old_Anchor",
                },
            }
        )
        result = parse_tool_call(text)
        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "create_procedural_shader")
        self.assertEqual(result["arguments"].get("shader_type"), "rusted_iron")
        self.assertEqual(result["arguments"].get("material_name"), "Old_Anchor")

    def test_parse_openai_format(self):
        text = json.dumps(
            {
                "type": "function",
                "function": {
                    "name": "create_procedural_shader",
                    "arguments": json.dumps({"shader_type": "glossy_glass"}),
                },
            }
        )
        result = parse_tool_call(text)
        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "create_procedural_shader")


class TestProceduralShaderDispatcherErrors(unittest.TestCase):
    def _dispatcher(self):
        return UnifiedToolDispatcher(
            llm=None,
            config={"blender": {"host": "127.0.0.1", "port": 9999}},
        )

    def test_blender_not_connected(self):
        d = self._dispatcher()
        with patch("blender_connector.is_blender_available", return_value=False):
            res = d.dispatch("create_procedural_shader", {"shader_type": "brushed_metal"})
        self.assertEqual(res["status"], "error")
        self.assertIn("BlenderNotConnected", res.get("error", ""))


class TestProceduralShaderDispatcherSuccess(unittest.TestCase):
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

    def _dispatch_with_mock(self, shader_type="brushed_metal", material_name="Titanium_Brushed"):
        d, tokens, statuses = self._dispatcher()
        with patch("blender_connector.is_blender_available", return_value=True), \
             patch("blender_connector.request_procedural_shader", return_value=MOCK_SHADER_RESPONSE):
            res = d.dispatch(
                "create_procedural_shader",
                {"shader_type": shader_type, "material_name": material_name},
            )
        return res, tokens, statuses

    def test_result_keys_present(self):
        res, _, _ = self._dispatch_with_mock()
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["tool"], "create_procedural_shader")
        self.assertIn("shader", res)
        self.assertIn("result", res)
        self.assertIn("_expert_system_prompt", res)

    def test_result_text_contains_key_data(self):
        res, _, _ = self._dispatch_with_mock()
        text = res["result"]
        self.assertIn("Titanium_Brushed", text)
        self.assertIn("brushed_metal", text)
        self.assertIn("Suzanne", text)
        self.assertIn("Noise Texture", text)
        self.assertIn("Bump", text)

    def test_ui_report_emitted_via_callback(self):
        _, tokens, _ = self._dispatch_with_mock()
        full = "".join(tokens)
        self.assertIn("Procedural Shader", full)
        self.assertIn("Titanium_Brushed", full)
        self.assertIn("Suzanne", full)
        self.assertIn("Počet uzlů", full)

    def test_status_callback_contains_node_count(self):
        _, _, statuses = self._dispatch_with_mock()
        combined = " ".join(statuses)
        self.assertIn("6 uzlů", combined)

    def test_expert_prompt_contains_shading_terms(self):
        res, _, _ = self._dispatch_with_mock()
        prompt = res["_expert_system_prompt"]
        self.assertIn("PBR", prompt)
        self.assertIn("Roughness", prompt)
        self.assertIn("Metallic", prompt)
        self.assertIn("Fresnel", prompt)
        self.assertIn("IOR", prompt)


class TestProceduralShaderConnectorFunction(unittest.TestCase):
    def test_connection_refused_returns_error(self):
        with patch("socket.socket") as mock_cls:
            mock_sock = MagicMock()
            mock_sock.connect.side_effect = ConnectionRefusedError()
            mock_cls.return_value = mock_sock
            res = blender_connector.request_procedural_shader(port=9999)
        self.assertEqual(res["status"], "error")
        self.assertEqual(res["error_type"], "ConnectionRefused")

    def test_invalid_type_normalized_to_default(self):
        sent_payloads = []

        def fake_send(payload, **kwargs):
            sent_payloads.append(payload)
            return {"status": "success", "shader": {}}

        with patch("blender_connector._send_blender_request", side_effect=fake_send):
            blender_connector.request_procedural_shader(shader_type="invalid_type")

        self.assertEqual(sent_payloads[0]["shader_type"], "brushed_metal")

    def test_valid_types_and_material_name_passed(self):
        for vtype in ("brushed_metal", "matte_plastic", "rusted_iron", "glossy_glass"):
            sent_payloads = []

            def fake_send(payload, **kwargs):
                sent_payloads.append(payload)
                return {"status": "success", "shader": {}}

            with patch("blender_connector._send_blender_request", side_effect=fake_send):
                blender_connector.request_procedural_shader(
                    material_name="Custom_Mat", shader_type=vtype
                )

            self.assertEqual(sent_payloads[0]["shader_type"], vtype)
            self.assertEqual(sent_payloads[0]["material_name"], "Custom_Mat")


if __name__ == "__main__":
    unittest.main(verbosity=2)
