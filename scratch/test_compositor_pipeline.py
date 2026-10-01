#!/usr/bin/env python3
"""
Unit testy pro modul 'Compositing & Post-Processing Pipeline':
- Ověření JSON schématu pro setup_compositor v TOOL_SCHEMAS.
- Ověření přítomnosti setup_compositor v ALLOWED_TOOL_NAMES a celkového počtu 19 nástrojů.
- Ověření parsování tool calls pro setup_compositor (kompaktní i OpenAI formát).
- Ověření klientské funkce request_compositor_setup v blender_connector.py.
- Ověření UnifiedToolDispatcheru, expertního VFX promptu a Markdown reportingu.
"""

import json
import unittest
from unittest.mock import MagicMock, patch

from blender_connector import (
    request_compositor_setup,
)
from llama_module import (
    ALLOWED_TOOL_NAMES,
    TOOL_SCHEMAS,
    UnifiedToolDispatcher,
    parse_tool_call,
)

# ── Sdílená mock data ──────────────────────────────────────────────────────────

MOCK_PRODUCT_POP_RESPONSE = {
    "status": "success",
    "action": "setup_compositor",
    "preset": "product_pop",
    "node_count": 5,
    "link_count": 4,
    "nodes": [
        {"name": "Render Layers", "type": "R_LAYERS"},
        {"name": "Glare", "type": "GLARE"},
        {"name": "Color Balance", "type": "COLOR_BALANCE"},
        {"name": "Composite", "type": "COMPOSITE"},
        {"name": "Viewer", "type": "VIEWER"},
    ],
}

MOCK_CINEMATIC_RESPONSE = {
    "status": "success",
    "action": "setup_compositor",
    "preset": "cinematic",
    "node_count": 7,
    "link_count": 6,
    "nodes": [
        {"name": "Render Layers", "type": "R_LAYERS"},
        {"name": "Lens Distortion", "type": "LENSDIST"},
        {"name": "Vignette Mask", "type": "MASK_ELLIPSE"},
        {"name": "Vignette Blur", "type": "BLUR"},
        {"name": "Vignette Mix", "type": "MIX_RGB"},
        {"name": "Composite", "type": "COMPOSITE"},
        {"name": "Viewer", "type": "VIEWER"},
    ],
}

MOCK_DENOISE_RESPONSE = {
    "status": "success",
    "action": "setup_compositor",
    "preset": "denoise_only",
    "node_count": 4,
    "link_count": 3,
    "nodes": [
        {"name": "Render Layers", "type": "R_LAYERS"},
        {"name": "Denoise", "type": "DENOISE"},
        {"name": "Composite", "type": "COMPOSITE"},
        {"name": "Viewer", "type": "VIEWER"},
    ],
}


class TestCompositorToolSchemas(unittest.TestCase):
    def test_setup_compositor_in_schemas(self):
        names = [t["function"]["name"] for t in TOOL_SCHEMAS]
        self.assertIn("setup_compositor", names)

    def test_setup_compositor_properties(self):
        schema = next(
            t for t in TOOL_SCHEMAS if t["function"]["name"] == "setup_compositor"
        )
        props = schema["function"]["parameters"]["properties"]
        self.assertIn("preset", props)
        self.assertIn("glare_threshold", props)
        self.assertIn("dispersion", props)
        self.assertIn("vignette_strength", props)

        presets = props["preset"].get("enum", [])
        self.assertIn("product_pop", presets)
        self.assertIn("cinematic", presets)
        self.assertIn("denoise_only", presets)

    def test_allowed_tool_names_contains_setup_compositor(self):
        self.assertIn("setup_compositor", ALLOWED_TOOL_NAMES)

    def test_total_tool_count_is_nineteen(self):
        self.assertGreaterEqual(len(ALLOWED_TOOL_NAMES), 19)


class TestCompositorParseToolCall(unittest.TestCase):
    def test_parse_compact_format_product_pop(self):
        raw = json.dumps({
            "tool": "setup_compositor",
            "arguments": {
                "preset": "product_pop",
                "glare_threshold": 0.8,
            },
        })
        parsed = parse_tool_call(raw)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["name"], "setup_compositor")
        self.assertEqual(parsed["arguments"]["preset"], "product_pop")
        self.assertEqual(parsed["arguments"]["glare_threshold"], 0.8)

    def test_parse_openai_format_cinematic(self):
        raw = json.dumps({
            "type": "function",
            "function": {
                "name": "setup_compositor",
                "arguments": json.dumps({
                    "preset": "cinematic",
                    "dispersion": 0.02,
                    "vignette_strength": 0.85,
                }),
            },
        })
        parsed = parse_tool_call(raw)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["name"], "setup_compositor")
        self.assertEqual(parsed["arguments"]["preset"], "cinematic")
        self.assertEqual(parsed["arguments"]["dispersion"], 0.02)
        self.assertEqual(parsed["arguments"]["vignette_strength"], 0.85)

    def test_parse_denoise_only(self):
        raw = json.dumps({
            "tool": "setup_compositor",
            "arguments": {
                "preset": "denoise_only",
            },
        })
        parsed = parse_tool_call(raw)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["name"], "setup_compositor")
        self.assertEqual(parsed["arguments"]["preset"], "denoise_only")


class TestCompositorConnector(unittest.TestCase):
    @patch("blender_connector._send_blender_request")
    def test_request_compositor_setup_product_pop(self, mock_send):
        mock_send.return_value = MOCK_PRODUCT_POP_RESPONSE

        res = request_compositor_setup(
            preset="product_pop",
            glare_threshold=0.7,
            glare_size=7,
        )
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["preset"], "product_pop")
        self.assertEqual(res["node_count"], 5)

        mock_send.assert_called_once()
        cmd = mock_send.call_args[0][0]
        self.assertEqual(cmd["action"], "setup_compositor")
        self.assertEqual(cmd["preset"], "product_pop")
        self.assertEqual(cmd["glare_threshold"], 0.7)
        self.assertEqual(cmd["glare_size"], 7)

    @patch("blender_connector._send_blender_request")
    def test_request_compositor_setup_cinematic(self, mock_send):
        mock_send.return_value = MOCK_CINEMATIC_RESPONSE

        res = request_compositor_setup(
            preset="cinematic",
            dispersion=0.025,
            vignette_strength=0.9,
        )
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["preset"], "cinematic")
        self.assertEqual(res["node_count"], 7)

        cmd = mock_send.call_args[0][0]
        self.assertEqual(cmd["preset"], "cinematic")
        self.assertEqual(cmd["dispersion"], 0.025)
        self.assertEqual(cmd["vignette_strength"], 0.9)

    @patch("blender_connector._send_blender_request")
    def test_request_compositor_setup_error_forwarding(self, mock_send):
        mock_send.return_value = {
            "status": "error",
            "message": "Compositor error",
        }
        res = request_compositor_setup(preset="product_pop", raise_on_error=False)
        self.assertEqual(res["status"], "error")
        self.assertEqual(res["message"], "Compositor error")
        self.assertFalse(mock_send.call_args[1]["raise_on_error"])

    @patch("blender_connector._send_blender_request")
    def test_request_compositor_setup_raise_on_error(self, mock_send):
        from blender_connector import BlenderExecutionError
        mock_send.side_effect = BlenderExecutionError("Compositor failure")

        with self.assertRaises(BlenderExecutionError):
            request_compositor_setup(preset="product_pop", raise_on_error=True)



class TestCompositorDispatcher(unittest.TestCase):
    def setUp(self):
        self.config = {
            "blender": {"host": "127.0.0.1", "port": 9876},
        }

    @patch("blender_connector.is_blender_available", return_value=False)
    def test_dispatch_blender_unavailable(self, mock_avail):
        tokens = []
        dispatcher = UnifiedToolDispatcher(
            config=self.config,
            callback_on_token=tokens.append,
        )
        res = dispatcher.dispatch("setup_compositor", {"preset": "product_pop"})
        self.assertEqual(res["status"], "error")
        self.assertEqual(res["error"], "BlenderNotConnected")
        self.assertTrue(any("není připojen" in t for t in tokens))

    @patch("blender_connector.is_blender_available", return_value=True)
    @patch("blender_connector.request_compositor_setup")
    def test_dispatch_product_pop_success(self, mock_req, mock_avail):
        mock_req.return_value = MOCK_PRODUCT_POP_RESPONSE
        tokens = []
        statuses = []

        dispatcher = UnifiedToolDispatcher(
            config=self.config,
            status_callback=statuses.append,
            callback_on_token=tokens.append,
        )

        res = dispatcher.dispatch(
            "setup_compositor",
            {"preset": "product_pop", "glare_threshold": 0.75},
        )
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["preset"], "product_pop")
        self.assertEqual(res["node_count"], 5)
        self.assertEqual(res["link_count"], 4)

        # Expertní systémový prompt
        expert_prompt = res.get("_expert_system_prompt", "")
        self.assertIn("Senior Compositing & VFX Artist", expert_prompt)
        self.assertIn("Fog Glow", expert_prompt)
        self.assertIn("Color Balance", expert_prompt)
        self.assertIn("Lens Distortion", expert_prompt)
        self.assertIn("vinětace", expert_prompt)
        self.assertIn("Denoising", expert_prompt)

        # UI report
        report_text = "".join(tokens)
        self.assertIn("Compositor & VFX Post-Processing", report_text)
        self.assertIn("product_pop", report_text)
        self.assertIn("Katalogový prémiový look", report_text)
        self.assertIn("scene.use_nodes = True", report_text)
        self.assertIn("Glare", report_text)
        self.assertIn("Composite", report_text)

    @patch("blender_connector.is_blender_available", return_value=True)
    @patch("blender_connector.request_compositor_setup")
    def test_dispatch_cinematic_success(self, mock_req, mock_avail):
        mock_req.return_value = MOCK_CINEMATIC_RESPONSE
        tokens = []

        dispatcher = UnifiedToolDispatcher(
            config=self.config,
            callback_on_token=tokens.append,
        )

        res = dispatcher.dispatch(
            "setup_compositor",
            {"preset": "cinematic", "dispersion": 0.015, "vignette_strength": 0.8},
        )
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["preset"], "cinematic")
        report_text = "".join(tokens)
        self.assertIn("Filmový styl", report_text)
        self.assertIn("Lens Distortion", report_text)
        self.assertIn("Vignette Blur", report_text)

    @patch("blender_connector.is_blender_available", return_value=True)
    @patch("blender_connector.request_compositor_setup")
    def test_dispatch_error_from_blender(self, mock_req, mock_avail):
        mock_req.return_value = {
            "status": "error",
            "error": "Failed to create node tree",
        }
        tokens = []
        dispatcher = UnifiedToolDispatcher(
            config=self.config,
            callback_on_token=tokens.append,
        )

        res = dispatcher.dispatch("setup_compositor", {"preset": "product_pop"})
        self.assertEqual(res["status"], "error")
        self.assertEqual(res["error"], "Failed to create node tree")
        self.assertTrue(any("selhalo" in t for t in tokens))


if __name__ == "__main__":
    unittest.main()
