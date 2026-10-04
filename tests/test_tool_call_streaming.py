import json
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from llama_module import (
    _repair_truncated_json_object,
    classify_bare_tool_call_prefix,
    generate_response,
    parse_tool_call,
)


class ToolCallStreamingTests(unittest.TestCase):
    def _generate(self, first_stream, second_stream=None):
        llm = MagicMock()
        llm.create_chat_completion.side_effect = [
            iter(first_stream),
            iter(
                second_stream
                or [{"choices": [{"delta": {"content": "Here is the result."}}]}]
            ),
        ]
        dispatcher = MagicMock()
        dispatcher.dispatch.return_value = {
            "status": "success",
            "result": "Tool result",
        }
        emitted_tokens = []
        emitted_answer_tokens = []

        with (
            patch("llama_module._try_evaluate_math", return_value=None),
            patch("llama_module.detect_analytical_mode", return_value=None),
            patch("llama_module.get_contextual_tools", return_value=[]),
            patch("llama_module.UnifiedToolDispatcher", return_value=dispatcher),
        ):
            response = list(
                generate_response(
                    llm,
                    "Search for the weather.",
                    {
                        "llama": {
                            "function_calling": True,
                            "analytical_preset": "standard",
                            "language": "en",
                            "max_tokens": 128,
                        }
                    },
                    callback_on_token=emitted_tokens.append,
                    callback_on_answer_token=emitted_answer_tokens.append,
                )
            )

        self.assertEqual(
            [
                call.kwargs["max_tokens"]
                for call in llm.create_chat_completion.call_args_list
            ],
            [128, 128],
        )
        return response, emitted_tokens, emitted_answer_tokens, dispatcher

    def test_split_markdown_json_call_is_dispatched_without_streaming_raw_json(self):
        response, emitted_tokens, emitted_answer_tokens, dispatcher = self._generate(
            [
                {"choices": [{"delta": {"content": "`"}}]},
                {"choices": [{"delta": {"content": "``"}}]},
                {
                    "choices": [{
                        "delta": {
                            "content": 'json\n{"tool":"search_web","arguments":'
                        }
                    }]
                },
                {"choices": [{"delta": {"content": '{"query":"weather"}}'}}]},
                {"choices": [{"delta": {"content": "\n```"}}]},
            ]
        )

        dispatcher.dispatch.assert_called_once_with(
            "search_web", {"query": "weather"}
        )
        self.assertEqual(response, ["Here is the result."])
        self.assertNotIn("search_web", "".join(emitted_tokens))
        self.assertNotIn("```", "".join(emitted_tokens))
        self.assertEqual(emitted_answer_tokens, ["Here is the result."])

    def test_openai_style_streamed_tool_call_is_dispatched(self):
        response, emitted_tokens, emitted_answer_tokens, dispatcher = self._generate(
            [
                None,
                {"choices": []},
                {
                    "choices": [{
                        "delta": {
                            "tool_calls": [{
                                "index": 0,
                                "function": {"name": "search_", "arguments": '{"query":'},
                            }]
                        }
                    }]
                },
                {
                    "choices": [{
                        "delta": {
                            "tool_calls": [{
                                "index": 0,
                                "function": {"name": "web", "arguments": '"weather"}'},
                            }]
                        }
                    }]
                },
            ]
        )

        dispatcher.dispatch.assert_called_once_with(
            "search_web", {"query": "weather"}
        )
        self.assertEqual(response, ["Here is the result."])
        self.assertEqual(emitted_tokens, ["Here is the result."])
        self.assertEqual(emitted_answer_tokens, ["Here is the result."])

    def test_text_tool_json_after_prose_is_hidden_from_stream(self):
        response, emitted_tokens, _, dispatcher = self._generate(
            [
                {"choices": [{"delta": {"content": "Searching now: "}}]},
                {
                    "choices": [{
                        "delta": {
                            "content": '{"tool":"search_web","arguments":'
                        }
                    }]
                },
                {"choices": [{"delta": {"content": '{"query":"weather"}}'}}]},
            ]
        )

        dispatcher.dispatch.assert_called_once_with(
            "search_web", {"query": "weather"}
        )
        streamed_text = "".join(emitted_tokens)
        self.assertIn("Searching now: ", streamed_text)
        self.assertNotIn('"tool"', streamed_text)
        self.assertNotIn('"query"', streamed_text)
        self.assertEqual(response[-1], "Here is the result.")

    def test_second_stream_skips_non_text_chunks_and_yields_complete_response(self):
        response, emitted_tokens, emitted_answer_tokens, _ = self._generate(
            [
                {
                    "choices": [{
                        "delta": {
                            "tool_calls": [{
                                "index": 0,
                                "function": {"name": "search_web", "arguments": '{"query":"weather"}'},
                            }]
                        }
                    }]
                },
            ],
            [
                {"choices": []},
                {"choices": [{"delta": {"content": "The "}}]},
                {"choices": [{"delta": {"content": "answer is 42"}}]},
            ],
        )

        self.assertEqual(response, ["The answer is 42"])
        self.assertEqual(emitted_tokens, ["The ", "answer is 42"])
        self.assertEqual(emitted_answer_tokens, ["The ", "answer is 42"])

    def test_bare_tool_name_before_json_is_dispatched_without_leaking(self):
        response, emitted_tokens, _, dispatcher = self._generate(
            [
                {"choices": [{"delta": {"content": "read"}}]},
                {"choices": [{"delta": {"content": "_file "}}]},
                {"choices": [{"delta": {"content": '{"file_path": '}}]},
                {"choices": [{"delta": {"content": '"test.py"}'}}]},
            ]
        )

        dispatcher.dispatch.assert_called_once_with("read_file", {"file_path": "test.py"})
        streamed_text = "".join(emitted_tokens)
        self.assertNotIn("read_file", streamed_text)
        self.assertNotIn("file_path", streamed_text)
        self.assertEqual(response, ["Here is the result."])

    def test_plain_answer_resembling_tool_name_is_not_swallowed(self):
        llm = MagicMock()
        llm.create_chat_completion.side_effect = [iter([
            {"choices": [{"delta": {"content": "search"}}]},
            {"choices": [{"delta": {"content": " is an English word."}}]},
        ])]
        dispatcher = MagicMock()
        tokens = []
        with (
            patch("llama_module._try_evaluate_math", return_value=None),
            patch("llama_module.detect_analytical_mode", return_value=None),
            patch("llama_module.get_contextual_tools", return_value=[]),
            patch("llama_module.UnifiedToolDispatcher", return_value=dispatcher),
        ):
            list(generate_response(
                llm, "What does search mean?",
                {"llama": {"function_calling": True, "analytical_preset": "standard",
                           "language": "en", "max_tokens": 128}},
                callback_on_token=tokens.append,
            ))
        dispatcher.dispatch.assert_not_called()
        self.assertEqual("".join(tokens), "search is an English word.")

    def _generate_multi(self, streams, results, prompt="Prozkoumej strukturu a vytvor soubor."):
        llm = MagicMock()
        llm.create_chat_completion.side_effect = [iter(s) for s in streams]
        dispatcher = MagicMock()
        dispatcher.dispatch.side_effect = [
            {"status": "success", "result": r} for r in results
        ]
        tokens = []
        answers = []
        with (
            patch("llama_module._try_evaluate_math", return_value=None),
            patch("llama_module.detect_analytical_mode", return_value=None),
            patch("llama_module.get_contextual_tools", return_value=[]),
            patch("llama_module.UnifiedToolDispatcher", return_value=dispatcher),
        ):
            response = list(
                generate_response(
                    llm,
                    prompt,
                    {
                        "llama": {
                            "function_calling": True,
                            "analytical_preset": "standard",
                            "language": "cs",
                            "max_tokens": 128,
                            "react_max_steps": 5,
                        }
                    },
                    callback_on_token=tokens.append,
                    callback_on_answer_token=answers.append,
                )
            )
        return response, tokens, answers, dispatcher, llm

    @staticmethod
    def _tc(name, args):
        return {"choices": [{"delta": {"content": (
            '{"tool": "%s", "arguments": %s}' % (name, args)
        )}}]}

    def test_react_chain_executes_second_tool_call(self):
        response, tokens, _, dispatcher, llm = self._generate_multi(
            [
                [self._tc("list_directory", '{"rel_path": "."}')],
                [self._tc("read_file", '{"file_path": "a.py"}')],
                [{"choices": [{"delta": {"content": "Hotovo."}}]}],
            ],
            ["listing: a.py", "content of a.py"],
        )
        self.assertEqual(dispatcher.dispatch.call_count, 2)
        dispatcher.dispatch.assert_any_call("list_directory", {"rel_path": "."})
        dispatcher.dispatch.assert_any_call("read_file", {"file_path": "a.py"})
        self.assertEqual(llm.create_chat_completion.call_count, 3)
        streamed = "".join(tokens)
        self.assertNotIn("list_directory", streamed)
        self.assertNotIn("rel_path", streamed)
        self.assertEqual(response[-1], "Hotovo.")

    def test_react_write_file_ends_loop_without_raw_json(self):
        response, tokens, _, dispatcher, llm = self._generate_multi(
            [
                [self._tc("list_directory", '{"rel_path": "."}')],
                [self._tc(
                    "write_file",
                    '{"file_path": "x.txt", "content": "hi"}',
                )],
                [{"choices": [{"delta": {"content": "Ulozeno."}}]}],
            ],
            ["listing: .", "written"],
        )
        self.assertEqual(dispatcher.dispatch.call_count, 2)
        self.assertEqual(llm.create_chat_completion.call_count, 3)
        streamed = "".join(tokens)
        self.assertNotIn("write_file", streamed)
        self.assertNotIn("file_path", streamed)
        self.assertEqual(response[-1], "Ulozeno.")

    def test_react_max_steps_stops_loop(self):
        # 1. tah list_directory + 4 navazne read_file = 5 dispatchi (MAX),
        # pak finalni synteza "Konec." = 6 LLM volani celkem.
        streams = [[self._tc("list_directory", '{"rel_path": "."}')]]
        streams += [[self._tc("read_file", '{"file_path": "a.py"}')]] * 4
        streams.append([{"choices": [{"delta": {"content": "Konec."}}]}])
        response, _, _, dispatcher, llm = self._generate_multi(
            streams, ["obs"] * 5,
        )
        # 1. tah + max 5 ReAct kroku + 1 finalni synteza
        self.assertEqual(dispatcher.dispatch.call_count, 5)
        self.assertEqual(llm.create_chat_completion.call_count, 6)
        self.assertEqual(response[-1], "Konec.")

    def test_react_duplicate_call_adds_system_warning(self):
        response, _, _, dispatcher, llm = self._generate_multi(
            [
                [self._tc("list_directory", '{"rel_path": "."}')],
                [self._tc("list_directory", '{"rel_path": "."}')],
                [{"choices": [{"delta": {"content": "Hotovo."}}]}],
            ],
            ["listing: .", "listing: ."],
        )
        self.assertEqual(dispatcher.dispatch.call_count, 2)
        context = llm.create_chat_completion.call_args_list[-1].kwargs["messages"]
        joined = "\n".join(str(m.get("content", "")) for m in context)
        self.assertIn("Tento výpis jsi již obdržel.", joined)
        self.assertIn("Nyní pokračuj dalším krokem nebo vytvoř soubor pomocí write_file.", joined)
        self.assertEqual(response[-1], "Hotovo.")

    def test_react_distinct_call_has_no_duplicate_warning(self):
        response, _, _, _, llm = self._generate_multi(
            [
                [self._tc("list_directory", '{"rel_path": "."}')],
                [self._tc("list_directory", '{"rel_path": "web_ui"}')],
                [{"choices": [{"delta": {"content": "Hotovo."}}]}],
            ],
            ["listing: .", "listing: web_ui"],
        )
        context = llm.create_chat_completion.call_args_list[-1].kwargs["messages"]
        joined = "\n".join(str(m.get("content", "")) for m in context)
        self.assertNotIn("Tento výpis jsi již obdržel.", joined)
        self.assertEqual(response[-1], "Hotovo.")

    def test_react_deadline_warning_when_write_file_missing(self):
        # limit 5, po 3. a 4. kroku zbývají 2 a 1 krok → výzva k write_file
        streams = [[self._tc("list_directory", '{"rel_path": "."}')]]
        streams += [[self._tc("read_file", '{"file_path": "a.py"}')]] * 3
        streams.append([{"choices": [{"delta": {"content": "Konec."}}]}])
        _, _, _, _, llm = self._generate_multi(
            streams, ["obs"] * 4, prompt="Vytvor novy soubor src/pages/index.astro",
        )
        joined = "\n".join(
            str(m.get("content", ""))
            for call in llm.create_chat_completion.call_args_list
            for m in call.kwargs["messages"]
        )
        self.assertIn(
            "VAROVÁNÍ: Blíží se limit kroků. "
            "Okamžitě přejdi k vytvoření návrhu a zavolej write_file.",
            joined,
        )

    def test_react_no_deadline_warning_without_write_intent(self):
        streams = [[self._tc("list_directory", '{"rel_path": "."}')]]
        streams += [[self._tc("read_file", '{"file_path": "a.py"}')]] * 3
        streams.append([{"choices": [{"delta": {"content": "Konec."}}]}])
        _, _, _, _, llm = self._generate_multi(
            streams, ["obs"] * 4, prompt="Jak se mašina lisuje?",
        )
        joined = "\n".join(
            str(m.get("content", ""))
            for call in llm.create_chat_completion.call_args_list
            for m in call.kwargs["messages"]
        )
        self.assertNotIn("Blíží se limit kroků", joined)

    def test_react_no_deadline_warning_after_write_file_called(self):
        streams = [[self._tc("write_file", '{"file_path": "x.txt", "content": "hi"}')]]
        streams.append([{"choices": [{"delta": {"content": "Hotovo."}}]}])
        _, _, _, _, llm = self._generate_multi(
            streams, ["written"], prompt="Vytvor novy soubor x.txt",
        )
        joined = "\n".join(
            str(m.get("content", ""))
            for call in llm.create_chat_completion.call_args_list
            for m in call.kwargs["messages"]
        )
        self.assertNotIn("Blíží se limit kroků", joined)

    def test_react_final_synthesis_raw_json_replaced_by_czech_summary(self):
        response, tokens, answers, _, _ = self._generate_multi(
            [
                [self._tc("write_file", '{"file_path": "index.astro", "content": "x"}')],
                [
                    {"choices": [{"delta": {"content": '{"tool": "write_file", "arguments": '}}]},
                    {"choices": [{"delta": {"content": '{"file_path": "index.astro", "content": "x"}}'}}]},
                ],
            ],
            ["written"],
        )
        streamed = "".join(tokens) + "".join(answers)
        self.assertNotIn('"tool"', streamed)
        self.assertIn("Připravil jsem návrh souboru index.astro", response[-1])
        self.assertIn("Kód & Diff", response[-1])

    def test_truncated_tool_json_in_content_is_dispatched_not_dumped(self):
        """Model vrací obrovský write_file JSON v message.content (bez tool_calls)."""
        broken = (
            '{"tool":"write_file","arguments":'
            '{"file_path":"src/pages/index.astro","content":"' + "x" * 120
        )
        response, tokens, answers, dispatcher, _ = self._generate_multi(
            [
                [
                    {"choices": [{"delta": {"content": broken[:80]}}]},
                    {"choices": [{"delta": {"content": broken[80:]}}]},
                ],
                [{"choices": [{"delta": {"content": "Hotovo."}}]}],
            ],
            ["written"],
            prompt="Vytvor novy soubor src/pages/index.astro",
        )
        name, args = dispatcher.dispatch.call_args.args
        self.assertEqual(name, "write_file")
        expected_args = {
            "file_path": "src/pages/index.astro",
            "content": "x" * 120,
            "_is_truncated": True,
        }
        dispatcher.dispatch.assert_called_once_with("write_file", expected_args)
        self.assertEqual(args["content"], "x" * 120)
        streamed = "".join(tokens) + "".join(answers)
        self.assertNotIn('"tool"', streamed)
        self.assertNotIn('"arguments"', streamed)
        self.assertEqual(response[-1], "Hotovo.")

    def test_truncated_tool_json_with_salvage_still_dispatches(self):
        """Kdyz se nestihnou ani argumenty, zachrani se alespon nazev nastroje."""
        broken = '{"tool":"write_file","arguments":{"file_path":"a.txt","conte'
        response, tokens, answers, dispatcher, _ = self._generate_multi(
            [
                [
                    {"choices": [{"delta": {"content": broken[:50]}}]},
                    {"choices": [{"delta": {"content": broken[50:]}}]},
                ],
                [{"choices": [{"delta": {"content": "Hotovo."}}]}],
            ],
            ["written"],
            prompt="Vytvor novy soubor a.txt",
        )
        dispatcher.dispatch.assert_called_once_with(
            "write_file", {"file_path": "a.txt", "_is_truncated": True},
        )
        self.assertNotIn('"tool"', "".join(tokens) + "".join(answers))
        self.assertEqual(response[-1], "Hotovo.")

    def test_truncated_salvage_marks_tool_call_truncated(self):
        """Záchrana nedokonceného JSONu musí predat _is_truncated do dispatchu."""
        broken = (
            '{"tool":"write_file","arguments":'
            '{"file_path":"src/pages/index.astro","content":"' + "x" * 60
        )
        _, _, _, dispatcher, _ = self._generate_multi(
            [
                [
                    {"choices": [{"delta": {"content": broken[:60]}}]},
                    {"choices": [{"delta": {"content": broken[60:]}}]},
                ],
                [{"choices": [{"delta": {"content": "Hotovo."}}]}],
            ],
            ["written"],
            prompt="Vytvor novy soubor src/pages/index.astro",
        )
        name, args = dispatcher.dispatch.call_args.args
        self.assertEqual(name, "write_file")
        self.assertTrue(args.get("_is_truncated"))
        # Obsah se presto musi zachovat
        self.assertEqual(args["content"], "x" * 60)

    def test_finish_reason_length_marks_tool_call_truncated(self):
        """finish_reason == 'length' musí označit návrh jako zkrácený."""
        llm = MagicMock()
        llm.create_chat_completion.side_effect = [
            iter([
                {"choices": [{
                    "delta": {"content": '{"tool":"write_file","arguments":'},
                    "finish_reason": None,
                }]},
                {"choices": [{
                    "delta": {"content": '{"file_path":"a.txt","content":"hi"}}'},
                    "finish_reason": "length",
                }]},
            ]),
        ]
        dispatcher = MagicMock()
        dispatcher.dispatch.return_value = {"status": "success", "result": "written"}
        with (
            patch("llama_module._try_evaluate_math", return_value=None),
            patch("llama_module.detect_analytical_mode", return_value=None),
            patch("llama_module.get_contextual_tools", return_value=[]),
            patch("llama_module.UnifiedToolDispatcher", return_value=dispatcher),
        ):
            list(generate_response(
                llm, "Vytvor soubor a.txt",
                {"llama": {"function_calling": True, "analytical_preset": "standard",
                           "language": "cs", "max_tokens": 128}},
            ))
        name, args = dispatcher.dispatch.call_args.args
        self.assertEqual(name, "write_file")
        self.assertTrue(args.get("_is_truncated"))
        self.assertNotIn("_is_truncated", json.dumps(
            [c.kwargs["messages"] for c in llm.create_chat_completion.call_args_list],
            default=str,
        ))

    def test_proposal_carries_is_truncated_flag(self):
        """create_workspace_write_proposal vrací příznak is_truncated."""
        from llama_module import create_workspace_write_proposal
        with tempfile.TemporaryDirectory() as tmp:
            with patch("llama_module.get_workspace_dir", return_value=tmp):
                normal = create_workspace_write_proposal("a.txt", "hello")
                cut = create_workspace_write_proposal("a.txt", "hello", is_truncated=True)
        self.assertIs(normal["is_truncated"], False)
        self.assertIs(cut["is_truncated"], True)

    def test_write_file_content_key_aliases(self):
        """Synonyma klíče 'content' se musí normalizovat."""
        from llama_module import extract_write_file_content
        self.assertEqual(extract_write_file_content({"content": "A"}), "A")
        self.assertEqual(extract_write_file_content({"code": "B"}), "B")
        self.assertEqual(extract_write_file_content({"text": "C"}), "C")
        self.assertEqual(extract_write_file_content({"file_content": "D"}), "D")
        self.assertEqual(extract_write_file_content({"body": "E"}), "E")
        self.assertEqual(extract_write_file_content({"file_path": "x"}), "")
        self.assertEqual(extract_write_file_content({}), "")
        # 'content' má přednost před synonyamy
        self.assertEqual(
            extract_write_file_content({"content": "A", "code": "B"}), "A",
        )

    def test_write_file_via_alias_key_is_dispatched(self):
        """Model použil místo 'content' klíč 'code' – musí fungovat."""
        _, _, _, dispatcher, _ = self._generate_multi(
            [
                [
                    {"choices": [{"delta": {"content":
                        '{"tool":"write_file","arguments":{"file_path":"a.txt","code":"print(1)"}}'}}]},
                ],
                [{"choices": [{"delta": {"content": "Hotovo."}}]}],
            ],
            ["written"],
            prompt="Vytvor soubor a.txt",
        )
        name, args = dispatcher.dispatch.call_args.args
        self.assertEqual(name, "write_file")
        self.assertEqual(args["code"], "print(1)")

    def test_write_file_without_content_is_rejected(self):
        """Prázdný obsah se nesmí spustit naslepo – musí vyhodit chybu."""
        from llama_module import UnifiedToolDispatcher
        dispatcher = UnifiedToolDispatcher.__new__(UnifiedToolDispatcher)
        with self.assertRaises(ValueError) as ctx:
            dispatcher.dispatch("write_file", {"file_path": "src/pages/index.astro"})
        self.assertIn("content", str(ctx.exception))
        with self.assertRaises(ValueError):
            dispatcher.dispatch("write_file", {"file_path": "a.txt", "content": "   "})
        with self.assertRaises(ValueError):
            dispatcher.dispatch("write_file", {"file_path": "a.txt", "code": ""})

    def test_salvage_keeps_file_path_and_stays_truncated(self):
        """Záchrana smí zachránit file_path, ale musí zůstat označená jako zkrácená."""
        from llama_module import _salvage_partial_arguments
        salvaged = _salvage_partial_arguments(
            '{"tool":"write_file","arguments":{"file_path":"src/pages/index.astro","conte'
        )
        self.assertIsNotNone(salvaged)
        data = json.loads(salvaged)
        self.assertEqual(data["tool"], "write_file")
        self.assertEqual(data["arguments"]["file_path"], "src/pages/index.astro")
        # Obsah v poškozeném JSONu chybí -> nesmí být vymyšlený
        self.assertNotIn("content", data["arguments"])

    def test_write_file_schema_requires_content(self):
        """Schema musí 'content' výslovně vyžadovat jako povinný řetězec."""
        import llama_module as lm
        schema = next(
            t for t in lm.TOOL_SCHEMAS
            if t["function"]["name"] == "write_file"
        )
        params = schema["function"]["parameters"]
        self.assertIn("content", params["required"])
        self.assertEqual(params["properties"]["content"]["type"], "string")
        self.assertEqual(params["properties"]["content"]["minLength"], 1)
        self.assertIn("POVINNÝ", params["properties"]["content"]["description"])

    def test_normal_text_with_json_like_content_is_not_stolen(self):
        """Běžná odpoveď nesmi být chybně povazována za tool-call."""
        response, tokens, _, dispatcher, _ = self._generate_multi(
            [
                [{"choices": [{"delta": {"content": "Ukazal jsem ti priklad: {\"name\": \"pepe\"}"}}]}],
            ],
            [],
            prompt="Jak se mašina lisuje?",
        )
        dispatcher.dispatch.assert_not_called()
        self.assertIn("pepe", "".join(tokens))

    def test_repair_keeps_full_content_for_completed_json(self):
        full = '{"tool":"write_file","arguments":{"file_path":"a.py","content":"print(1)\\nprint(2)"}}'
        repaired = _repair_truncated_json_object(full)
        self.assertEqual(repaired["tool"], "write_file")
        self.assertEqual(repaired["arguments"]["content"], "print(1)\nprint(2)")


class ParseBareToolCallTests(unittest.TestCase):
    def test_bare_name_before_json(self):
        res = parse_tool_call('read_file {"file_path": "test.py"}')
        self.assertEqual(res["name"], "read_file")
        self.assertEqual(res["arguments"], {"file_path": "test.py"})

    def test_bare_name_with_backticks_and_colon(self):
        res = parse_tool_call('`read_file`: {"file_path": "web_search.py"}')
        self.assertEqual(res["name"], "read_file")

    def test_bare_name_inside_markdown_block(self):
        res = parse_tool_call('```\nlist_directory {"rel_path": "."}\n```')
        self.assertEqual(res["name"], "list_directory")

    def test_unknown_bare_name_is_rejected(self):
        self.assertIsNone(parse_tool_call('delete_everything {"path": "/"}'))

    def test_standard_formats_still_work(self):
        self.assertEqual(parse_tool_call('{"tool": "read_file", "arguments": {"file_path": "a.py"}}')["name"], "read_file")
        self.assertEqual(parse_tool_call('{"name": "read_file", "arguments": {"file_path": "a.py"}}')["name"], "read_file")
        openai = '{"type": "function", "function": {"name": "read_file", "arguments": {"file_path": "a.py"}}}'
        self.assertEqual(parse_tool_call(openai)["arguments"], {"file_path": "a.py"})

    def test_prefix_classifier(self):
        self.assertEqual(classify_bare_tool_call_prefix("read"), "maybe")
        self.assertEqual(classify_bare_tool_call_prefix("read_file "), "maybe")
        self.assertEqual(classify_bare_tool_call_prefix('read_file {"'), "yes")
        self.assertEqual(classify_bare_tool_call_prefix("Ahoj"), "no")
        self.assertEqual(classify_bare_tool_call_prefix("search the web"), "no")


if __name__ == "__main__":
    unittest.main()
