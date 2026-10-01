#!/usr/bin/env python3
"""
Testovací skript pro ověření Nativního Function Callingu (JSON Tool-Use Architecture):
1. Registr nástrojů (TOOL_SCHEMAS & build_tool_use_prompt)
2. Robustní Parser (parse_tool_call pro různé JSON/Markdown/XML formáty)
3. UnifiedToolDispatcher (dispečink všech 5 nástrojů + Self-Healing Blender smyčka)
4. End-to-end cyklus v generate_response (vyvolání nástroje, předání výsledku a finální syntéza)
"""

import json
import unittest
from unittest.mock import MagicMock, patch

from llama_module import (
    TOOL_SCHEMAS,
    ALLOWED_TOOL_NAMES,
    build_tool_use_prompt,
    parse_tool_call,
    UnifiedToolDispatcher,
    generate_response,
)


class TestFunctionCallingArchitecture(unittest.TestCase):
    def test_tool_schemas_and_prompt(self):
        # 1. Ověření registru nástrojů (aktuálně 21)
        names = {t["function"]["name"] for t in TOOL_SCHEMAS}
        expected = {
            "search_web",
            "query_local_rag",
            "query_memory_rag",
            "execute_blender_code",
            "inspect_blender_scene",
            "mesh_doctor_audit",
            "mesh_doctor_repair",
            "create_product_studio",
            "create_procedural_shader",
            "uv_texel_audit",
            "smart_uv_pack",
            "generate_parametric_model",
            "apply_modifier_stack",
            "create_geometry_nodes_bridge",
            "apply_fcurve_animation",
            "create_motion_node_setup",
            "setup_blueprint_reference",
            "vectorize_image_to_3d",
            "setup_compositor",
            "generate_local_ai_mesh",
            "analyze_viewport_image",
        }
        self.assertEqual(names, expected)
        self.assertEqual(ALLOWED_TOOL_NAMES, expected)

        # 2. Ověření sestavení promptu
        prompt = build_tool_use_prompt()
        self.assertIn("## DOSTUPNÉ NÁSTROJE (TOOLS):", prompt)
        self.assertIn("search_web", prompt)
        self.assertIn("execute_blender_code", prompt)
        self.assertIn("inspect_blender_scene", prompt)
        self.assertIn("mesh_doctor_audit", prompt)
        self.assertIn("mesh_doctor_repair", prompt)
        self.assertIn("create_product_studio", prompt)
        self.assertIn("create_procedural_shader", prompt)
        self.assertIn("uv_texel_audit", prompt)
        self.assertIn("smart_uv_pack", prompt)
        self.assertIn("generate_parametric_model", prompt)
        self.assertIn("apply_modifier_stack", prompt)
        self.assertIn("create_geometry_nodes_bridge", prompt)
        self.assertIn("apply_fcurve_animation", prompt)
        self.assertIn("create_motion_node_setup", prompt)
        self.assertIn("setup_blueprint_reference", prompt)
        self.assertIn("vectorize_image_to_3d", prompt)
        self.assertIn("setup_compositor", prompt)
        self.assertIn("generate_local_ai_mesh", prompt)
        self.assertIn("analyze_viewport_image", prompt)
        self.assertIn("KOGNITIVNÍ VIZUÁLNÍ PARAMETRIZACE", prompt)

    def test_parse_tool_call_formats(self):
        # A. Stručný formát s 'tool'
        text_a = '{"tool": "search_web", "arguments": {"query": "nejnovější zprávy"}}'
        call_a = parse_tool_call(text_a)
        self.assertIsNotNone(call_a)
        self.assertEqual(call_a["name"], "search_web")
        self.assertEqual(call_a["arguments"]["query"], "nejnovější zprávy")

        # B. Standardní OpenAI formát
        text_b = '''
        {
            "type": "function",
            "function": {
                "name": "query_local_rag",
                "arguments": {"query": "rozpočet 2026"}
            }
        }
        '''
        call_b = parse_tool_call(text_b)
        self.assertIsNotNone(call_b)
        self.assertEqual(call_b["name"], "query_local_rag")
        self.assertEqual(call_b["arguments"]["query"], "rozpočet 2026")

        # C. Markdown blok s ```json
        text_c = '''
        Zde je volání nástroje:
        ```json
        {
            "tool": "execute_blender_code",
            "arguments": {
                "code": "import bpy\\nbpy.ops.mesh.primitive_cube_add()"
            }
        }
        ```
        '''
        call_c = parse_tool_call(text_c)
        self.assertIsNotNone(call_c)
        self.assertEqual(call_c["name"], "execute_blender_code")
        self.assertIn("primitive_cube_add", call_c["arguments"]["code"])

        # D. XML obal <tool_call>...</tool_call>
        text_d = '<tool_call>{"name": "inspect_blender_scene", "arguments": {}}</tool_call>'
        call_d = parse_tool_call(text_d)
        self.assertIsNotNone(call_d)
        self.assertEqual(call_d["name"], "inspect_blender_scene")
        self.assertEqual(call_d["arguments"], {})

        # E. Stringifikované argumenty
        text_e = '{"tool": "query_memory_rag", "arguments": "{\\"query\\": \\"oblíbená barva\\"}"}'
        call_e = parse_tool_call(text_e)
        self.assertIsNotNone(call_e)
        self.assertEqual(call_e["name"], "query_memory_rag")
        self.assertEqual(call_e["arguments"]["query"], "oblíbená barva")

        # F. Běžný konverzační text (nemá detekovat volání nástroje)
        self.assertIsNone(parse_tool_call("Ahoj, jak ti mohu dnes pomoci?"))
        self.assertIsNone(parse_tool_call("Kód v Pythonu: def foo(): return 42"))
        self.assertIsNone(parse_tool_call('{"neznámý_klíč": 123}'))
        self.assertIsNone(parse_tool_call('{"tool": "neexistujici_nastroj", "arguments": {}}'))

    def test_dispatcher_web_search(self):
        with patch("web_search.search_web_multi_source") as mock_search:
            mock_search.return_value = "Obsah z webu: Mise Artemis úspěšně pokračuje."
            dispatcher = UnifiedToolDispatcher()
            res = dispatcher.dispatch("search_web", {"query": "Artemis zprávy"})
            self.assertEqual(res["status"], "success")
            self.assertIn("Mise Artemis", res["result"])
            mock_search.assert_called_once_with("Artemis zprávy", max_sources=3)

    def test_dispatcher_local_rag(self):
        mock_doc_service = MagicMock()
        mock_doc_service.total_chunks.return_value = 5
        mock_doc_service.top_k = 2
        mock_doc_service.search.return_value = [{"doc_name": "manual.pdf", "text": "Instrukce k Blender receiveru"}]
        mock_doc_service.format_chunks_for_prompt.return_value = "[Úsek 1 | manual.pdf]\nInstrukce k Blender receiveru"

        dispatcher = UnifiedToolDispatcher(document_service=mock_doc_service)
        res = dispatcher.dispatch("query_local_rag", {"query": "přijímač"})
        self.assertEqual(res["status"], "success")
        self.assertIn("manual.pdf", res["result"])
        mock_doc_service.search.assert_called_once_with("přijímač", top_k=2)

    def test_dispatcher_memory_rag(self):
        mock_mem_service = MagicMock()
        mock_mem_service.get_memory_stats.return_value = {"total_chunks": 3}
        mock_mem_service.search_memory.return_value = [{"session_title": "Minulý chat", "text": "Nastaveno zlato hex #FFD700"}]
        mock_mem_service.format_memory_for_prompt.return_value = "RELEVANTNÍ HISTORICKÁ PAMĚŤ:\nZlato hex #FFD700"

        dispatcher = UnifiedToolDispatcher(memory_service=mock_mem_service, active_session_id="session_current")
        res = dispatcher.dispatch("query_memory_rag", {"query": "jakou barvu zlata"})
        self.assertEqual(res["status"], "success")
        self.assertIn("#FFD700", res["result"])
        mock_mem_service.search_memory.assert_called_once()

    def test_dispatcher_blender_code_self_healing(self):
        # Test Self-Healing smyčky: první pokus selže s chybou, LLM vygeneruje opravu, druhý pokus uspěje!
        with patch("blender_connector.is_blender_available", return_value=True), \
             patch("blender_connector.send_code_to_blender") as mock_send:

            # 1. volání selže, 2. volání uspěje
            mock_send.side_effect = [
                {"status": "error", "error": "AttributeError: 'NoneType' object has no attribute 'name'", "traceback": "Traceback..."},
                {"status": "success", "output": "Krychle vytvořena"},
            ]

            mock_llm = MagicMock()
            mock_llm.create_chat_completion.return_value = {
                "choices": [{
                    "message": {
                        "content": "import bpy\nbpy.ops.mesh.primitive_cube_add()"
                    }
                }]
            }

            tokens = []
            dispatcher = UnifiedToolDispatcher(
                llm=mock_llm,
                config={"blender": {"max_retries": 2}},
                callback_on_token=tokens.append,
            )

            res = dispatcher.dispatch("execute_blender_code", {"code": "import bpy\nbpy.context.active_object.name = 'Test'"})
            self.assertEqual(res["status"], "success")
            self.assertTrue(res["repaired"])
            self.assertEqual(res["attempts"], 2)
            self.assertEqual(mock_send.call_count, 2)
            self.assertEqual(mock_llm.create_chat_completion.call_count, 1)

    def test_dispatcher_inspect_blender_scene(self):
        with patch("blender_connector.is_blender_available", return_value=True), \
             patch("blender_connector.request_scene_inspection") as mock_inspect:

            mock_inspect.return_value = {
                "status": "success",
                "scene_metrics": {
                    "total_objects": 2,
                    "mode": "OBJECT",
                    "render_engine": "EEVEE",
                    "active_object": {"name": "Cube", "type": "MESH", "location": [0, 0, 0], "rotation_euler": [0, 0, 0], "scale": [1, 1, 1]},
                    "selected_objects": [{"name": "Cube", "type": "MESH", "location": [0, 0, 0], "rotation_euler": [0, 0, 0], "scale": [1, 1, 1]}],
                    "lights": [{"name": "Light", "light_type": "POINT", "energy": 1000, "location": [4, 1, 6]}],
                    "cameras": [{"name": "Camera"}],
                },
                "screenshot_path": "/tmp/blender_viewport.png"
            }

            tokens = []
            dispatcher = UnifiedToolDispatcher(callback_on_token=tokens.append)
            res = dispatcher.dispatch("inspect_blender_scene", {})
            self.assertEqual(res["status"], "success")
            self.assertIn("Cube", res["result"])
            self.assertIn("Light", res["result"])
            mock_inspect.assert_called_once()

    def test_end_to_end_generate_response_with_tool_call(self):
        # Ověření dvoukolového běhu:
        # Tah 1: Model vrátí JSON volání nástroje search_web
        # Tah 2: Model obdrží výsledek nástroje a zformuluje odpověď
        mock_llm = MagicMock()

        # Tah 1 (vrací JSON volání)
        chunk_t1_1 = {"choices": [{"delta": {"content": '{"tool": "search_web", '}}]}
        chunk_t1_2 = {"choices": [{"delta": {"content": '"arguments": {"query": "Mars 2026"}}\n'}}]}

        # Tah 2 (vrací finální syntézu)
        chunk_t2_1 = {"choices": [{"delta": {"content": "Na základě vyhledávání "}}]}
        chunk_t2_2 = {"choices": [{"delta": {"content": "probíhají na Marsu nové mise."}}]}

        mock_llm.create_chat_completion.side_effect = [
            iter([chunk_t1_1, chunk_t1_2]),
            iter([chunk_t2_1, chunk_t2_2]),
        ]

        with patch("web_search.search_web_multi_source", return_value="Aktuality o Marsu 2026: rover našel vodu."):
            tokens = []
            status_log = []
            output_sentences = list(generate_response(
                mock_llm,
                "Jaké jsou novinky o Marsu?",
                config={"llama": {"temperature": 0.3}},
                callback_on_token=tokens.append,
                status_callback=status_log.append,
            ))

            # Ověříme, že proběhly 2 tahy inference
            self.assertEqual(mock_llm.create_chat_completion.call_count, 2)
            # Ověříme, že surový JSON volání nebyl předán do finálních vět pro TTS
            full_out = " ".join(output_sentences)
            self.assertNotIn('{"tool":', full_out)
            self.assertIn("Na základě vyhledávání", full_out)

    def test_end_to_end_generate_response_direct_no_tool(self):
        # Ověření, že když model odpovídá přímo (běžný text), streamuje se bez zpoždění a bez 2. tahu
        mock_llm = MagicMock()
        chunk1 = {"choices": [{"delta": {"content": "Ahoj! "}}]}
        chunk2 = {"choices": [{"delta": {"content": "Ráda ti pomohu."}}]}
        mock_llm.create_chat_completion.side_effect = [iter([chunk1, chunk2])]

        tokens = []
        output = list(generate_response(
            mock_llm,
            "Ahoj",
            config={"llama": {"temperature": 0.5}},
            callback_on_token=tokens.append,
        ))

        # Pouze 1 tah, žádné volání nástroje
        self.assertEqual(mock_llm.create_chat_completion.call_count, 1)
        full_text = " ".join(output)
        self.assertIn("Ahoj!", full_text)


if __name__ == "__main__":
    unittest.main()
