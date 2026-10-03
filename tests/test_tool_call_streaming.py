import unittest
from unittest.mock import MagicMock, patch

from llama_module import generate_response


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


if __name__ == "__main__":
    unittest.main()
