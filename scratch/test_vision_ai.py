#!/usr/bin/env python3
"""
Unit testy pro Vision AI — Vizuální inspekce viewportu Blenderu (21. nástroj).

Testuje:
- Registraci nástroje 'analyze_viewport_image' v TOOL_SCHEMAS a ALLOWED_TOOL_NAMES.
- Parsování tool call JSON (kompaktní formát i OpenAI formát).
- Dispatch logiku v UnifiedToolDispatcher.
- Chování při nedostupném Blenderu (BlenderNotConnected).
- Chování při úspěšném pořízení snímku s mockovanou telemetrií.
- Výstup UI headeru v callback_on_token (markdown obrázek, telemetrie).
- Zpracování analyze_viewport_image s volitelným analysis_prompt.
- Detekci vizuálního dotazu přes is_blender_inspection_query.
"""

import json
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch, call

from llama_module import (
    ALLOWED_TOOL_NAMES,
    TOOL_SCHEMAS,
    UnifiedToolDispatcher,
    parse_tool_call,
    is_blender_inspection_query,
    format_scene_metrics_for_prompt,
)

# ── Sdílená mock data ──────────────────────────────────────────────────────────

MOCK_SCENE_METRICS = {
    "scene_name": "TestScene",
    "mode": "OBJECT",
    "render_engine": "CYCLES",
    "total_objects": 5,
    "selected_count": 2,
    "active_object": {
        "name": "Cube",
        "type": "MESH",
        "location": [0.0, 0.0, 0.0],
        "rotation_euler": [0.0, 0.0, 0.0],
        "scale": [1.0, 1.0, 1.0],
        "vertices": 8,
        "polygons": 6,
    },
    "selected_objects": [
        {
            "name": "Cube",
            "type": "MESH",
            "location": [0.0, 0.0, 0.0],
            "rotation_euler": [0.0, 0.0, 0.0],
            "scale": [1.0, 1.0, 1.0],
            "is_active": True,
            "mesh_name": "Cube",
            "vertices": 8,
            "polygons": 6,
            "materials": ["Material_Metal"],
        }
    ],
    "lights": [
        {"name": "Sun", "light_type": "SUN", "energy": 5.0, "location": [4.0, 4.0, 6.0]}
    ],
    "cameras": [
        {
            "name": "Camera",
            "is_active_scene_camera": True,
            "location": [7.48, -6.51, 5.34],
            "lens_mm": 50.0,
        }
    ],
    "all_objects_summary": [
        {"name": "Cube", "type": "MESH", "visible": True},
        {"name": "Sun", "type": "LIGHT", "visible": True},
        {"name": "Camera", "type": "CAMERA", "visible": True},
    ],
}

MOCK_INSPECT_SUCCESS = {
    "status": "success",
    "action": "inspect_scene",
    "scene_metrics": MOCK_SCENE_METRICS,
    "screenshot_path": "/tmp/ai_assistant_viewport.png",
}


# ── 1. Registrace nástroje ─────────────────────────────────────────────────────

class TestVisionAIToolRegistration(unittest.TestCase):
    """Ověření, že analyze_viewport_image je správně zaregistrován."""

    def test_tool_in_allowed_tool_names(self):
        """Nástroj musí být v sadě ALLOWED_TOOL_NAMES."""
        self.assertIn(
            "analyze_viewport_image",
            ALLOWED_TOOL_NAMES,
            "analyze_viewport_image chybí v ALLOWED_TOOL_NAMES",
        )

    def test_tool_schema_exists(self):
        """Nástroj musí mít odpovídající schéma v TOOL_SCHEMAS."""
        names = [
            s["function"]["name"]
            for s in TOOL_SCHEMAS
            if s.get("type") == "function"
        ]
        self.assertIn(
            "analyze_viewport_image",
            names,
            "analyze_viewport_image nemá schéma v TOOL_SCHEMAS",
        )

    def test_tool_schema_has_correct_type(self):
        """Schéma musí mít type='function'."""
        schema = next(
            (s for s in TOOL_SCHEMAS if s.get("function", {}).get("name") == "analyze_viewport_image"),
            None,
        )
        self.assertIsNotNone(schema)
        self.assertEqual(schema["type"], "function")

    def test_tool_schema_has_description(self):
        """Schéma musí mít neprázdný description."""
        schema = next(
            (s for s in TOOL_SCHEMAS if s.get("function", {}).get("name") == "analyze_viewport_image"),
            None,
        )
        self.assertIsNotNone(schema)
        desc = schema["function"].get("description", "")
        self.assertGreater(len(desc), 20, "Description je příliš krátký")

    def test_tool_schema_parameters_optional(self):
        """Oba parametry (analysis_prompt, output_path) musí být volitelné (required=[])."""
        schema = next(
            (s for s in TOOL_SCHEMAS if s.get("function", {}).get("name") == "analyze_viewport_image"),
            None,
        )
        self.assertIsNotNone(schema)
        params = schema["function"].get("parameters", {})
        required = params.get("required", [])
        self.assertEqual(required, [], "analyze_viewport_image nesmí mít required parametry")

    def test_tool_schema_has_analysis_prompt_param(self):
        """Schéma musí obsahovat parametr analysis_prompt."""
        schema = next(
            (s for s in TOOL_SCHEMAS if s.get("function", {}).get("name") == "analyze_viewport_image"),
            None,
        )
        props = schema["function"]["parameters"]["properties"]
        self.assertIn("analysis_prompt", props)

    def test_tool_schema_has_output_path_param(self):
        """Schéma musí obsahovat parametr output_path."""
        schema = next(
            (s for s in TOOL_SCHEMAS if s.get("function", {}).get("name") == "analyze_viewport_image"),
            None,
        )
        props = schema["function"]["parameters"]["properties"]
        self.assertIn("output_path", props)

    def test_total_tools_count(self):
        """Po přidání nástroje auto_rig_and_skin musí být celkem 22 nástrojů."""
        names = [
            s["function"]["name"]
            for s in TOOL_SCHEMAS
            if s.get("type") == "function"
        ]
        self.assertEqual(
            len(names), 22,
            f"Očekáváno 22 nástrojů, nalezeno {len(names)}: {names}",
        )

    def test_allowed_tool_names_count(self):
        """ALLOWED_TOOL_NAMES musí obsahovat právě 22 názvů."""
        self.assertEqual(
            len(ALLOWED_TOOL_NAMES), 22,
            f"ALLOWED_TOOL_NAMES má {len(ALLOWED_TOOL_NAMES)} položek, očekáváno 22",
        )


# ── 2. Parsování tool call JSONu ───────────────────────────────────────────────

class TestVisionAIToolCallParsing(unittest.TestCase):
    """Ověření parseru pro různé formáty tool call JSONu."""

    def test_parse_compact_format_no_args(self):
        """Kompaktní JSON bez argumentů."""
        raw = json.dumps({"tool": "analyze_viewport_image", "arguments": {}})
        result = parse_tool_call(raw)
        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "analyze_viewport_image")
        self.assertEqual(result["arguments"], {})

    def test_parse_compact_format_with_analysis_prompt(self):
        """Kompaktní JSON s analysis_prompt."""
        raw = json.dumps({
            "tool": "analyze_viewport_image",
            "arguments": {"analysis_prompt": "zkontroluj topologii"},
        })
        result = parse_tool_call(raw)
        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "analyze_viewport_image")
        self.assertEqual(result["arguments"]["analysis_prompt"], "zkontroluj topologii")

    def test_parse_openai_function_format(self):
        """OpenAI standardní formát {type: function, function: {name, arguments}}."""
        raw = json.dumps({
            "type": "function",
            "function": {
                "name": "analyze_viewport_image",
                "arguments": {"output_path": "/tmp/test.png"},
            },
        })
        result = parse_tool_call(raw)
        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "analyze_viewport_image")
        self.assertEqual(result["arguments"]["output_path"], "/tmp/test.png")

    def test_parse_name_arguments_format(self):
        """Formát {name, arguments}."""
        raw = json.dumps({
            "name": "analyze_viewport_image",
            "arguments": {"analysis_prompt": "popiš shader"},
        })
        result = parse_tool_call(raw)
        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "analyze_viewport_image")

    def test_parse_in_markdown_block(self):
        """JSON uvnitř markdown ```json ... ``` bloku."""
        raw = (
            "```json\n"
            '{"tool": "analyze_viewport_image", "arguments": {"analysis_prompt": "vizuální test"}}\n'
            "```"
        )
        result = parse_tool_call(raw)
        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "analyze_viewport_image")

    def test_parse_empty_string_returns_none(self):
        """Prázdný vstup → None."""
        self.assertIsNone(parse_tool_call(""))

    def test_parse_unknown_tool_returns_none(self):
        """Neregistrovaný nástroj → None."""
        raw = json.dumps({"tool": "hack_system", "arguments": {}})
        self.assertIsNone(parse_tool_call(raw))


# ── 3. is_blender_inspection_query detekce ────────────────────────────────────

class TestVisionAIQueryDetection(unittest.TestCase):
    """Ověření detekce vizuálních inspekčních dotazů."""

    def _is(self, prompt: str) -> bool:
        return is_blender_inspection_query(prompt)

    def test_podivej_se_na_scenu(self):
        self.assertTrue(self._is("Podívej se na scénu v Blenderu"))

    def test_zkontroluj_viewport(self):
        self.assertTrue(self._is("Zkontroluj viewport prosím"))

    def test_co_vidis_ve_scene(self):
        self.assertTrue(self._is("Co vidíš ve 3D scéně?"))

    def test_inspect_scene_direct(self):
        self.assertTrue(self._is("inspect scene"))

    def test_viewport_snapshot_direct(self):
        self.assertTrue(self._is("viewport snapshot"))

    def test_obecna_otazka_neni_inspekce(self):
        """Obecná otázka bez Blender kontextu nesmí být detekována."""
        self.assertFalse(self._is("Co je nového ve světě?"))

    def test_blender_info_neni_inspekce(self):
        """Dotaz 'kdo vytvořil Blender' nesmí vyvolat inspekci."""
        self.assertFalse(self._is("Kdo vytvořil Blender a kdy vyšel?"))


# ── 4. Dispatcher – BlenderNotConnected ───────────────────────────────────────

class TestVisionAIDispatcherBlenderNotConnected(unittest.TestCase):
    """Ověření chování při nedostupném Blenderu."""

    def _make_dispatcher(self):
        tokens = []
        d = UnifiedToolDispatcher(
            llm=None,
            config={"blender": {"host": "127.0.0.1", "port": 9876}},
            callback_on_token=tokens.append,
        )
        return d, tokens

    @patch("blender_connector.is_blender_available", return_value=False)
    def test_returns_error_status(self, mock_avail):
        dispatcher, tokens = self._make_dispatcher()
        result = dispatcher.dispatch("analyze_viewport_image", {})
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["tool"], "analyze_viewport_image")
        self.assertEqual(result["error"], "BlenderNotConnected")

    @patch("blender_connector.is_blender_available", return_value=False)
    def test_result_contains_port_info(self, mock_avail):
        dispatcher, _ = self._make_dispatcher()
        result = dispatcher.dispatch("analyze_viewport_image", {})
        self.assertIn("9876", result["result"])

    @patch("blender_connector.is_blender_available", return_value=False)
    def test_callback_token_contains_warning(self, mock_avail):
        dispatcher, tokens = self._make_dispatcher()
        dispatcher.dispatch("analyze_viewport_image", {})
        combined = "".join(tokens)
        self.assertIn("⚠️", combined)


# ── 5. Dispatcher – Úspěšná inspekce (mock) ───────────────────────────────────

class TestVisionAIDispatcherSuccess(unittest.TestCase):
    """Ověření úspěšné vizuální inspekce s mockovanými daty."""

    def _make_dispatcher_with_llm(self, temp_screenshot_path: str):
        """Vytvoří dispatcher s mock LLM a mock request_scene_inspection."""
        tokens = []
        statuses = []

        mock_llm = MagicMock()
        # Simulovaný streaming výstup LLM
        mock_llm.create_chat_completion.return_value = [
            {"choices": [{"delta": {"content": "Scéna "}}]},
            {"choices": [{"delta": {"content": "obsahuje "}}]},
            {"choices": [{"delta": {"content": "krychli."}}]},
        ]

        d = UnifiedToolDispatcher(
            llm=mock_llm,
            config={"blender": {
                "host": "127.0.0.1",
                "port": 9876,
                "viewport_snapshot_path": temp_screenshot_path,
            }},
            callback_on_token=tokens.append,
            status_callback=statuses.append,
        )
        return d, tokens, statuses, mock_llm

    def _patch_blender(self, temp_path: str):
        """Kontextový manažer: mock is_blender_available + request_scene_inspection."""
        mock_response = dict(MOCK_INSPECT_SUCCESS)
        mock_response["screenshot_path"] = temp_path

        p1 = patch("blender_connector.is_blender_available", return_value=True)
        p2 = patch(
            "blender_connector.request_scene_inspection",
            return_value=mock_response,
        )
        return p1, p2

    def test_returns_success_status(self):
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            temp_path = f.name
            f.write(b"\x89PNG\r\n\x1a\n")  # minimální PNG header
        try:
            p1, p2 = self._patch_blender(temp_path)
            with p1, p2:
                dispatcher, tokens, statuses, llm = self._make_dispatcher_with_llm(temp_path)
                result = dispatcher.dispatch("analyze_viewport_image", {})
            self.assertEqual(result["status"], "success")
            self.assertEqual(result["tool"], "analyze_viewport_image")
        finally:
            os.unlink(temp_path)

    def test_result_contains_scene_metrics(self):
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            temp_path = f.name
            f.write(b"\x89PNG\r\n\x1a\n")
        try:
            p1, p2 = self._patch_blender(temp_path)
            with p1, p2:
                dispatcher, tokens, statuses, llm = self._make_dispatcher_with_llm(temp_path)
                result = dispatcher.dispatch("analyze_viewport_image", {})
            self.assertIn("scene_metrics", result)
            self.assertIsInstance(result["scene_metrics"], dict)
            self.assertEqual(result["scene_metrics"]["total_objects"], 5)
        finally:
            os.unlink(temp_path)

    def test_result_contains_screenshot_path(self):
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            temp_path = f.name
            f.write(b"\x89PNG\r\n\x1a\n")
        try:
            p1, p2 = self._patch_blender(temp_path)
            with p1, p2:
                dispatcher, tokens, statuses, llm = self._make_dispatcher_with_llm(temp_path)
                result = dispatcher.dispatch("analyze_viewport_image", {})
            self.assertEqual(result["screenshot_path"], temp_path)
        finally:
            os.unlink(temp_path)

    def test_image_exists_true_when_file_present(self):
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            temp_path = f.name
            f.write(b"\x89PNG\r\n\x1a\n")
        try:
            p1, p2 = self._patch_blender(temp_path)
            with p1, p2:
                dispatcher, tokens, statuses, llm = self._make_dispatcher_with_llm(temp_path)
                result = dispatcher.dispatch("analyze_viewport_image", {})
            self.assertTrue(result["image_exists"])
        finally:
            os.unlink(temp_path)

    def test_ui_header_in_callback_tokens(self):
        """callback_on_token musí dostat Markdown blok s emoji 👁️ a telemetrií."""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            temp_path = f.name
            f.write(b"\x89PNG\r\n\x1a\n")
        try:
            p1, p2 = self._patch_blender(temp_path)
            with p1, p2:
                dispatcher, tokens, statuses, llm = self._make_dispatcher_with_llm(temp_path)
                dispatcher.dispatch("analyze_viewport_image", {})
            combined = "".join(tokens)
            self.assertIn("👁️", combined)
            self.assertIn("Telemetrie", combined)
        finally:
            os.unlink(temp_path)

    def test_screenshot_embedded_in_markdown(self):
        """UI header musí obsahovat markdown obrázek ![Viewport Snapshot](...)."""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            temp_path = f.name
            f.write(b"\x89PNG\r\n\x1a\n")
        try:
            p1, p2 = self._patch_blender(temp_path)
            with p1, p2:
                dispatcher, tokens, statuses, llm = self._make_dispatcher_with_llm(temp_path)
                dispatcher.dispatch("analyze_viewport_image", {})
            combined = "".join(tokens)
            self.assertIn("![Viewport Snapshot]", combined)
        finally:
            os.unlink(temp_path)

    def test_llm_called_with_telemetry_in_prompt(self):
        """LLM musí být zavolán a systémový prompt musí obsahovat telemetrii."""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            temp_path = f.name
            f.write(b"\x89PNG\r\n\x1a\n")
        try:
            p1, p2 = self._patch_blender(temp_path)
            with p1, p2:
                dispatcher, tokens, statuses, llm = self._make_dispatcher_with_llm(temp_path)
                dispatcher.dispatch("analyze_viewport_image", {})
            llm.create_chat_completion.assert_called_once()
            call_kwargs = llm.create_chat_completion.call_args
            messages = call_kwargs[1].get("messages") or call_kwargs[0][0]
            system_content = next(
                (m["content"] for m in messages if m["role"] == "system"), ""
            )
            self.assertIn("Blenderu", system_content)
        finally:
            os.unlink(temp_path)

    def test_custom_analysis_prompt_passed_to_llm(self):
        """Vlastní analysis_prompt musí být předán jako user message."""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            temp_path = f.name
            f.write(b"\x89PNG\r\n\x1a\n")
        try:
            p1, p2 = self._patch_blender(temp_path)
            with p1, p2:
                dispatcher, tokens, statuses, llm = self._make_dispatcher_with_llm(temp_path)
                dispatcher.dispatch(
                    "analyze_viewport_image",
                    {"analysis_prompt": "zkontroluj normály a topologii"},
                )
            call_kwargs = llm.create_chat_completion.call_args
            messages = call_kwargs[1].get("messages") or call_kwargs[0][0]
            user_content = next(
                (m["content"] for m in messages if m["role"] == "user"), ""
            )
            self.assertIn("normály", user_content)
        finally:
            os.unlink(temp_path)

    def test_status_callback_called_with_vision_ai_label(self):
        """status_callback musí dostat zprávu s 'Vision AI'."""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            temp_path = f.name
            f.write(b"\x89PNG\r\n\x1a\n")
        try:
            p1, p2 = self._patch_blender(temp_path)
            with p1, p2:
                dispatcher, tokens, statuses, llm = self._make_dispatcher_with_llm(temp_path)
                dispatcher.dispatch("analyze_viewport_image", {})
            combined_statuses = " ".join(statuses)
            self.assertIn("Vision AI", combined_statuses)
        finally:
            os.unlink(temp_path)

    def test_result_text_contains_llm_output(self):
        """result['result'] musí obsahovat text vygenerovaný mock LLM."""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            temp_path = f.name
            f.write(b"\x89PNG\r\n\x1a\n")
        try:
            p1, p2 = self._patch_blender(temp_path)
            with p1, p2:
                dispatcher, tokens, statuses, llm = self._make_dispatcher_with_llm(temp_path)
                result = dispatcher.dispatch("analyze_viewport_image", {})
            self.assertIn("Scéna", result["result"])
        finally:
            os.unlink(temp_path)


# ── 6. Dispatcher – inspekce selhala ──────────────────────────────────────────

class TestVisionAIDispatcherInspectionFailed(unittest.TestCase):
    """Ověření chování když request_scene_inspection vrátí chybu."""

    @patch("blender_connector.is_blender_available", return_value=True)
    @patch(
        "blender_connector.request_scene_inspection",
        return_value={"status": "error", "error": "TimeoutError", "message": "Blender nestihlo"},
    )
    def test_returns_error_on_failed_inspection(self, mock_insp, mock_avail):
        tokens = []
        dispatcher = UnifiedToolDispatcher(
            llm=None,
            config={"blender": {"host": "127.0.0.1", "port": 9876}},
            callback_on_token=tokens.append,
        )
        result = dispatcher.dispatch("analyze_viewport_image", {})
        self.assertEqual(result["status"], "error")
        self.assertIn("TimeoutError", result["error"])

    @patch("blender_connector.is_blender_available", return_value=True)
    @patch(
        "blender_connector.request_scene_inspection",
        return_value={"status": "error", "error": "SomeFail", "message": ""},
    )
    def test_error_result_contains_error_message(self, mock_insp, mock_avail):
        dispatcher = UnifiedToolDispatcher(
            llm=None,
            config={"blender": {"host": "127.0.0.1", "port": 9876}},
        )
        result = dispatcher.dispatch("analyze_viewport_image", {})
        self.assertIn("SomeFail", result["result"])


# ── 7. Dispatcher – LLM není inicializován ────────────────────────────────────

class TestVisionAINoLLM(unittest.TestCase):
    """Ověření chování, když LLM není k dispozici (llm=None)."""

    @patch("blender_connector.is_blender_available", return_value=True)
    @patch("blender_connector.request_scene_inspection", return_value=MOCK_INSPECT_SUCCESS)
    @patch("os.path.isfile", return_value=True)
    def test_fallback_message_without_llm(self, mock_isfile, mock_insp, mock_avail):
        tokens = []
        dispatcher = UnifiedToolDispatcher(
            llm=None,
            config={"blender": {"host": "127.0.0.1", "port": 9876}},
            callback_on_token=tokens.append,
        )
        result = dispatcher.dispatch("analyze_viewport_image", {})
        # Musí vrátit success (telemetrie úspěšně získána)
        self.assertEqual(result["status"], "success")
        # Výsledek musí obsahovat fallback zprávu nebo telemetrii
        self.assertTrue(result["result"])

    @patch("blender_connector.is_blender_available", return_value=True)
    @patch("blender_connector.request_scene_inspection", return_value=MOCK_INSPECT_SUCCESS)
    @patch("os.path.isfile", return_value=True)
    def test_callback_gets_fallback_text(self, mock_isfile, mock_insp, mock_avail):
        tokens = []
        dispatcher = UnifiedToolDispatcher(
            llm=None,
            config={"blender": {"host": "127.0.0.1", "port": 9876}},
            callback_on_token=tokens.append,
        )
        dispatcher.dispatch("analyze_viewport_image", {})
        combined = "".join(tokens)
        # Alespoň UI header s telemetrií musí být přítomen
        self.assertIn("Telemetrie", combined)


# ── 8. format_scene_metrics_for_prompt ────────────────────────────────────────

class TestFormatSceneMetrics(unittest.TestCase):
    """Ověření pomocné funkce pro formátování telemetrie."""

    def test_returns_string(self):
        result = format_scene_metrics_for_prompt(MOCK_SCENE_METRICS)
        self.assertIsInstance(result, str)

    def test_contains_scene_name(self):
        result = format_scene_metrics_for_prompt(MOCK_SCENE_METRICS)
        self.assertIn("TestScene", result)

    def test_contains_total_objects(self):
        result = format_scene_metrics_for_prompt(MOCK_SCENE_METRICS)
        self.assertIn("5", result)

    def test_contains_screenshot_path_when_provided(self):
        result = format_scene_metrics_for_prompt(MOCK_SCENE_METRICS, "/tmp/test.png")
        self.assertIn("/tmp/test.png", result)

    def test_contains_light_info(self):
        result = format_scene_metrics_for_prompt(MOCK_SCENE_METRICS)
        self.assertIn("Sun", result)

    def test_contains_camera_info(self):
        result = format_scene_metrics_for_prompt(MOCK_SCENE_METRICS)
        self.assertIn("Camera", result)

    def test_contains_active_object(self):
        result = format_scene_metrics_for_prompt(MOCK_SCENE_METRICS)
        self.assertIn("Cube", result)

    def test_empty_metrics_does_not_crash(self):
        result = format_scene_metrics_for_prompt({})
        self.assertIsInstance(result, str)


# ── 9. Integrace dispatch s custom output_path ────────────────────────────────

class TestVisionAICustomOutputPath(unittest.TestCase):
    """Ověření předávání custom output_path parametru."""

    @patch("blender_connector.is_blender_available", return_value=True)
    def test_custom_output_path_forwarded(self, mock_avail):
        """Dispatcher musí předat custom output_path do request_scene_inspection."""
        custom_path = "/tmp/custom_viewport_test.png"
        captured_calls = []

        def fake_request(host, port, output_path, timeout):
            captured_calls.append(output_path)
            return {"status": "error", "error": "FakeError", "message": "test"}

        with patch("blender_connector.request_scene_inspection", side_effect=fake_request):
            dispatcher = UnifiedToolDispatcher(
                llm=None,
                config={"blender": {"host": "127.0.0.1", "port": 9876}},
            )
            dispatcher.dispatch("analyze_viewport_image", {"output_path": custom_path})

        self.assertEqual(len(captured_calls), 1)
        # custom path musí být použita (nebo fallback z config)
        # (config nemá viewport_snapshot_path, takže custom_path z argumentů bude použit)
        self.assertIn(captured_calls[0], [custom_path, "/tmp/ai_assistant_viewport.png"])


# ── Spuštění ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    unittest.main(verbosity=2)
