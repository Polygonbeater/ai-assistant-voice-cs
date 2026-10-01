"""
Smart UV Unpacking & Texel Density Pipeline — unit testy:
- TOOL_SCHEMAS obsahuje uv_texel_audit a smart_uv_pack (s parametry)
- ALLOWED_TOOL_NAMES obsahuje oba nástroje
- parse_tool_call rozpozná volání uv_texel_audit i smart_uv_pack
- dispatch() vrátí chybu BlenderNotConnected
- dispatch() úspěšně zpracuje mock audit i pack odpověď a formátuje UI reporty
- Expertní prompt obsahuje klíčová slova (Texel Density, Padding, Margin, Coverage, Baking)
- blender_connector.request_uv_audit a request_uv_pack: ověření chování a error handlingu
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

MOCK_AUDIT_RESPONSE = {
    "status": "success",
    "action": "uv_texel_audit",
    "metrics": {
        "has_uv": True,
        "object_name": "Hero_Prop",
        "texture_resolution": 2048,
        "total_3d_area_m2": 2.4512,
        "total_uv_area": 0.7654,
        "uv_space_coverage_pct": 76.54,
        "texel_density_px_m": 1148.5,
        "texel_density_px_cm": 11.49,
        "uv_islands_count": 8,
        "flipped_faces_count": 0,
        "potential_overlaps": False,
    },
}

MOCK_PACK_RESPONSE = {
    "status": "success",
    "action": "smart_uv_pack",
    "target_texel_density": 10.24,
    "margin": 0.015,
    "angle_limit": 66.0,
    "scaled_to_target": True,
    "post_pack_metrics": {
        "has_uv": True,
        "object_name": "Hero_Prop",
        "texture_resolution": 2048,
        "total_3d_area_m2": 2.4512,
        "total_uv_area": 0.7231,
        "uv_space_coverage_pct": 72.31,
        "texel_density_px_m": 1024.0,
        "texel_density_px_cm": 10.24,
        "uv_islands_count": 8,
        "flipped_faces_count": 0,
        "potential_overlaps": False,
    },
}


class TestUVToolSchemas(unittest.TestCase):
    def test_uv_tools_in_schemas(self):
        names = [t["function"]["name"] for t in TOOL_SCHEMAS]
        self.assertIn("uv_texel_audit", names)
        self.assertIn("smart_uv_pack", names)

    def test_smart_uv_pack_parameters(self):
        schema = next(
            t for t in TOOL_SCHEMAS if t["function"]["name"] == "smart_uv_pack"
        )
        props = schema["function"]["parameters"]["properties"]
        self.assertIn("target_texel_density", props)
        self.assertIn("margin", props)
        self.assertIn("angle_limit", props)
        self.assertIn("texture_res", props)

    def test_allowed_tool_names_contains_uv_tools(self):
        self.assertIn("uv_texel_audit", ALLOWED_TOOL_NAMES)
        self.assertIn("smart_uv_pack", ALLOWED_TOOL_NAMES)

    def test_total_tool_count_is_eleven(self):
        # Minimálně 11 nástrojů
        self.assertGreaterEqual(len(ALLOWED_TOOL_NAMES), 11)


class TestUVParseToolCall(unittest.TestCase):
    def test_parse_audit_compact(self):
        text = json.dumps({"tool": "uv_texel_audit", "arguments": {"texture_res": 4096}})
        result = parse_tool_call(text)
        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "uv_texel_audit")
        self.assertEqual(result["arguments"].get("texture_res"), 4096)

    def test_parse_smart_pack_with_args(self):
        text = json.dumps(
            {
                "tool": "smart_uv_pack",
                "arguments": {
                    "target_texel_density": 10.24,
                    "margin": 0.02,
                },
            }
        )
        result = parse_tool_call(text)
        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "smart_uv_pack")
        self.assertEqual(result["arguments"].get("target_texel_density"), 10.24)
        self.assertEqual(result["arguments"].get("margin"), 0.02)

    def test_parse_openai_format(self):
        text = json.dumps(
            {
                "type": "function",
                "function": {
                    "name": "smart_uv_pack",
                    "arguments": json.dumps({"margin": 0.01}),
                },
            }
        )
        result = parse_tool_call(text)
        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "smart_uv_pack")


class TestUVDispatcherErrors(unittest.TestCase):
    def _dispatcher(self):
        return UnifiedToolDispatcher(
            llm=None,
            config={"blender": {"host": "127.0.0.1", "port": 9999}},
        )

    def test_audit_blender_not_connected(self):
        d = self._dispatcher()
        with patch("blender_connector.is_blender_available", return_value=False):
            res = d.dispatch("uv_texel_audit", {"texture_res": 2048})
        self.assertEqual(res["status"], "error")
        self.assertIn("BlenderNotConnected", res.get("error", ""))

    def test_pack_blender_not_connected(self):
        d = self._dispatcher()
        with patch("blender_connector.is_blender_available", return_value=False):
            res = d.dispatch("smart_uv_pack", {"target_texel_density": 10.24})
        self.assertEqual(res["status"], "error")
        self.assertIn("BlenderNotConnected", res.get("error", ""))


class TestUVDispatcherSuccess(unittest.TestCase):
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

    def test_audit_success(self):
        d, tokens, statuses = self._dispatcher()
        with patch("blender_connector.is_blender_available", return_value=True), \
             patch("blender_connector.request_uv_audit", return_value=MOCK_AUDIT_RESPONSE):
            res = d.dispatch("uv_texel_audit", {"texture_res": 2048})

        self.assertEqual(res["status"], "success")
        self.assertEqual(res["tool"], "uv_texel_audit")
        self.assertIn("metrics", res)
        self.assertIn("_expert_system_prompt", res)
        self.assertIn("Hero_Prop", res["result"])
        self.assertIn("11.49 px/cm", res["result"])

        full = "".join(tokens)
        self.assertIn("UV Texel Audit", full)
        self.assertIn("Hero_Prop", full)
        self.assertIn("76.5 %", full)

    def test_pack_success(self):
        d, tokens, statuses = self._dispatcher()
        with patch("blender_connector.is_blender_available", return_value=True), \
             patch("blender_connector.request_uv_pack", return_value=MOCK_PACK_RESPONSE):
            res = d.dispatch("smart_uv_pack", {"target_texel_density": 10.24, "margin": 0.015})

        self.assertEqual(res["status"], "success")
        self.assertEqual(res["tool"], "smart_uv_pack")
        self.assertIn("post_pack_metrics", res)
        self.assertIn("_expert_system_prompt", res)
        self.assertIn("Hero_Prop", res["result"])
        self.assertIn("10.24 px/cm", res["result"])

        full = "".join(tokens)
        self.assertIn("Smart UV Pack Dokončen", full)
        self.assertIn("Hero_Prop", full)
        self.assertIn("10.24 px/cm", full)

    def test_expert_prompt_contents(self):
        d, _, _ = self._dispatcher()
        with patch("blender_connector.is_blender_available", return_value=True), \
             patch("blender_connector.request_uv_audit", return_value=MOCK_AUDIT_RESPONSE):
            res = d.dispatch("uv_texel_audit", {})

        prompt = res["_expert_system_prompt"]
        self.assertIn("Texel Density", prompt)
        self.assertIn("Coverage", prompt)
        self.assertIn("Padding", prompt)
        self.assertIn("Baking", prompt)


class TestUVConnectorFunctions(unittest.TestCase):
    def test_audit_connection_refused(self):
        with patch("socket.socket") as mock_cls:
            mock_sock = MagicMock()
            mock_sock.connect.side_effect = ConnectionRefusedError()
            mock_cls.return_value = mock_sock
            res = blender_connector.request_uv_audit(port=9999)
        self.assertEqual(res["status"], "error")
        self.assertEqual(res["error_type"], "ConnectionRefused")

    def test_pack_connection_refused(self):
        with patch("socket.socket") as mock_cls:
            mock_sock = MagicMock()
            mock_sock.connect.side_effect = ConnectionRefusedError()
            mock_cls.return_value = mock_sock
            res = blender_connector.request_uv_pack(port=9999)
        self.assertEqual(res["status"], "error")
        self.assertEqual(res["error_type"], "ConnectionRefused")

    def test_pack_parameters_forwarded(self):
        sent_payloads = []

        def fake_send(payload, **kwargs):
            sent_payloads.append(payload)
            return {"status": "success", "post_pack_metrics": {}}

        with patch("blender_connector._send_blender_request", side_effect=fake_send):
            blender_connector.request_uv_pack(
                target_texel_density=5.12, margin=0.02, angle_limit=45.0, texture_res=1024
            )

        self.assertEqual(sent_payloads[0]["target_texel_density"], 5.12)
        self.assertEqual(sent_payloads[0]["margin"], 0.02)
        self.assertEqual(sent_payloads[0]["angle_limit"], 45.0)
        self.assertEqual(sent_payloads[0]["texture_res"], 1024)


if __name__ == "__main__":
    unittest.main(verbosity=2)
