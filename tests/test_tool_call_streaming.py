import unittest
from unittest.mock import MagicMock, patch

from llama_module import generate_response


class ToolCallStreamingTests(unittest.TestCase):
    def _generate(self, first_stream):
        llm = MagicMock()
        llm.create_chat_completion.side_effect = [
            iter(first_stream),
            iter([{"choices": [{"delta": {"content": "Here is the result."}}]}]),
        ]
        dispatcher = MagicMock()
        dispatcher.dispatch.return_value = {
            "status": "success",
            "result": "Tool result",
        }
        emitted_tokens = []

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
                )
            )

        return response, emitted_tokens, dispatcher

    def test_split_markdown_json_call_is_dispatched_without_streaming_raw_json(self):
        response, emitted_tokens, dispatcher = self._generate(
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

    def test_openai_style_streamed_tool_call_is_dispatched(self):
        response, emitted_tokens, dispatcher = self._generate(
            [
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


if __name__ == "__main__":
    unittest.main()
