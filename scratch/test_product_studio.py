"""
Product Viz Studio Automator — unit testy:
- TOOL_SCHEMAS obsahuje create_product_studio (se style enum)
- ALLOWED_TOOL_NAMES obsahuje create_product_studio
- parse_tool_call rozpozná JSON volání create_product_studio
- dispatch() vrátí chybu BlenderNotConnected
- dispatch() úspěšně zpracuje mock odpověď a formátuje UI report
- Expertní prompt obsahuje klíčová klíčová slova (key light, fill, rim, backdrop)
- blender_connector.request_product_studio: validace stylu + error handling
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

MOCK_STUDIO_RESPONSE = {
    "status": "success",
    "action": "create_product_studio",
    "studio": {
        "backdrop": {
            "name": "Studio_Backdrop",
            "dimensions_m": [6.0, 4.5, 3.75],
            "material": "Studio_Backdrop_Mat",
            "modifiers": ["SimpleDeform(Bend)", "Solidify", "Bevel"],
        },
        "lights": [
            {
                "name": "Studio_Key_Light",
                "role": "key",
                "location": [-1.54, -1.76, 2.64],
                "energy": 800,
                "color_temp": "warm white",
                "size": 1.6,
            },
            {
                "name": "Studio_Fill_Light",
                "role": "fill",
                "location": [1.98, -1.32, 0.88],
                "energy": 200,
                "color_temp": "cool blue-white",
                "size": 2.4,
            },
            {
                "name": "Studio_Rim_Light",
                "role": "rim",
                "location": [-1.1, 2.42, 2.2],
                "energy": 400,
                "color_temp": "neutral white",
                "size": 1.0,
            },
        ],
        "camera": {
            "name": "Studio_Camera",
            "location": [0.77, -7.7, 2.31],
            "focal_length_mm": 85,
            "resolution": "2048x2048",
            "is_active_camera": True,
        },
        "style": "standard",
        "scale_factor": 2.2,
        "target_object": "Cube",
    },
}


class TestProductStudioToolSchemas(unittest.TestCase):
    def test_create_product_studio_in_schemas(self):
        names = [t["function"]["name"] for t in TOOL_SCHEMAS]
        self.assertIn("create_product_studio", names)

    def test_style_enum_in_schema(self):
        schema = next(
            t for t in TOOL_SCHEMAS if t["function"]["name"] == "create_product_studio"
        )
        props = schema["function"]["parameters"]["properties"]
        self.assertIn("style", props)
        enum_vals = props["style"].get("enum", [])
        self.assertIn("standard", enum_vals)
        self.assertIn("dramatic", enum_vals)
        self.assertIn("soft", enum_vals)

    def test_allowed_tool_names_contains_studio(self):
        self.assertIn("create_product_studio", ALLOWED_TOOL_NAMES)

    def test_total_tool_count_is_eight(self):
        # Minimálně 8 nástrojů (včetně mesh doctor a product studio)
        self.assertGreaterEqual(len(ALLOWED_TOOL_NAMES), 8)


class TestProductStudioParseToolCall(unittest.TestCase):
    def test_parse_compact_no_args(self):
        text = json.dumps({"tool": "create_product_studio", "arguments": {}})
        result = parse_tool_call(text)
        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "create_product_studio")

    def test_parse_with_style_arg(self):
        text = json.dumps(
            {"tool": "create_product_studio", "arguments": {"style": "dramatic"}}
        )
        result = parse_tool_call(text)
        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "create_product_studio")
        self.assertEqual(result["arguments"].get("style"), "dramatic")

    def test_parse_openai_format(self):
        text = json.dumps(
            {
                "type": "function",
                "function": {
                    "name": "create_product_studio",
                    "arguments": json.dumps({"style": "soft"}),
                },
            }
        )
        result = parse_tool_call(text)
        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "create_product_studio")


class TestProductStudioDispatcherErrors(unittest.TestCase):
    def _dispatcher(self):
        return UnifiedToolDispatcher(
            llm=None,
            config={"blender": {"host": "127.0.0.1", "port": 9999}},
        )

    def test_blender_not_connected(self):
        d = self._dispatcher()
        with patch("blender_connector.is_blender_available", return_value=False):
            res = d.dispatch("create_product_studio", {"style": "standard"})
        self.assertEqual(res["status"], "error")
        self.assertIn("BlenderNotConnected", res.get("error", ""))

    def test_invalid_style_normalised_to_standard(self):
        """Invalid style should be coerced to 'standard' before dispatch."""
        d = self._dispatcher()
        captured_styles = []

        def fake_request_product_studio(**kwargs):
            captured_styles.append(kwargs.get("style"))
            return MOCK_STUDIO_RESPONSE

        with patch("blender_connector.is_blender_available", return_value=True), \
             patch("blender_connector.request_product_studio", side_effect=fake_request_product_studio):
            d.dispatch("create_product_studio", {"style": "neon_cyberpunk"})

        self.assertEqual(captured_styles[0], "standard")


class TestProductStudioDispatcherSuccess(unittest.TestCase):
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

    def _dispatch_with_mock(self, style="standard"):
        d, tokens, statuses = self._dispatcher()
        with patch("blender_connector.is_blender_available", return_value=True), \
             patch("blender_connector.request_product_studio", return_value=MOCK_STUDIO_RESPONSE):
            res = d.dispatch("create_product_studio", {"style": style})
        return res, tokens, statuses

    def test_result_keys_present(self):
        res, _, _ = self._dispatch_with_mock()
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["tool"], "create_product_studio")
        self.assertIn("studio", res)
        self.assertIn("result", res)
        self.assertIn("_expert_system_prompt", res)

    def test_result_text_contains_key_data(self):
        res, _, _ = self._dispatch_with_mock()
        text = res["result"]
        self.assertIn("standard", text)
        self.assertIn("Cube", text)  # target_object
        self.assertIn("85", text)    # focal length
        self.assertIn("KEY", text)
        self.assertIn("FILL", text)
        self.assertIn("RIM", text)

    def test_ui_report_emitted_via_callback(self):
        _, tokens, _ = self._dispatch_with_mock()
        full = "".join(tokens)
        self.assertIn("Product Viz Studio", full)
        self.assertIn("Backdrop", full)
        self.assertIn("Key Light", full)
        self.assertIn("Fill Light", full)
        self.assertIn("Rim Light", full)
        self.assertIn("85 mm", full)
        self.assertIn("2048x2048", full)

    def test_status_callback_contains_light_count(self):
        _, _, statuses = self._dispatch_with_mock()
        combined = " ".join(statuses)
        self.assertIn("3", combined)  # 3 světla

    def test_expert_prompt_contains_photography_terms(self):
        res, _, _ = self._dispatch_with_mock()
        prompt = res["_expert_system_prompt"]
        self.assertIn("Key light", prompt)
        self.assertIn("Fill light", prompt)
        self.assertIn("Rim", prompt)
        self.assertIn("backdrop", prompt.lower())
        self.assertIn("85mm", prompt)

    def test_dramatic_style_dispatched(self):
        res, _, _ = self._dispatch_with_mock(style="dramatic")
        # Studio byl vytvořen (style v mock response je 'standard', ale dispatch proběhl)
        self.assertEqual(res["status"], "success")

    def test_backdrop_info_in_ui_report(self):
        _, tokens, _ = self._dispatch_with_mock()
        full = "".join(tokens)
        self.assertIn("Studio_Backdrop", full)
        self.assertIn("Studio_Backdrop_Mat", full)
        self.assertIn("Solidify", full)


class TestProductStudioConnectorFunction(unittest.TestCase):
    def test_connection_refused_returns_error(self):
        with patch("socket.socket") as mock_cls:
            mock_sock = MagicMock()
            mock_sock.connect.side_effect = ConnectionRefusedError()
            mock_cls.return_value = mock_sock
            res = blender_connector.request_product_studio(port=9999)
        self.assertEqual(res["status"], "error")
        self.assertEqual(res["error_type"], "ConnectionRefused")

    def test_invalid_style_coerced_before_send(self):
        """request_product_studio validates style before sending payload."""
        sent_payloads = []

        def fake_send(payload, **kwargs):
            sent_payloads.append(payload)
            return {"status": "success", "studio": {}}

        with patch("blender_connector._send_blender_request", side_effect=fake_send):
            blender_connector.request_product_studio(style="INVALID_STYLE")

        self.assertEqual(sent_payloads[0]["style"], "standard")

    def test_valid_styles_passed_through(self):
        for valid_style in ("standard", "dramatic", "soft"):
            sent_payloads = []

            def fake_send(payload, **kwargs):
                sent_payloads.append(payload)
                return {"status": "success", "studio": {}}

            with patch("blender_connector._send_blender_request", side_effect=fake_send):
                blender_connector.request_product_studio(style=valid_style)

            self.assertEqual(
                sent_payloads[0]["style"],
                valid_style,
                f"Styl '{valid_style}' musí být předán beze změny",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
