import unittest

from llama_module import (
    PRESETS_CATALOG,
    WORKSPACE_AGENT_TOOL_NAMES,
    WORKSPACE_QUERY_PATTERNS,
    _try_evaluate_math,
    classify_methodology,
    detect_analytical_mode,
    detect_workspace_request,
)

# Dotaz, který dříve vygeneroval falešnou odpověď „Výsledek je 0.“
ORIGINAL_BUG_QUERY = (
    "prozkoumej strukturu souborů v tomto projektu a vytvoř v src/pages/index.astro "
    "moderní úvodní stránku pro Polygon Beater v tmavém stylu ladícím s tímto rozhraním."
)


class MathFallbackTests(unittest.TestCase):
    """Kalkulační fallback se nesmí spouštět na běžných větách ani RAG kontextu."""

    def test_regular_sentence_never_triggers_calculator(self):
        self.assertIsNone(_try_evaluate_math(ORIGINAL_BUG_QUERY))
        self.assertIsNone(_try_evaluate_math("Vytvoř v složce docs nový soubor readme."))
        self.assertIsNone(_try_evaluate_math("Jaký je rok 2026 a co znamená IPv4?"))
        self.assertIsNone(_try_evaluate_math(""))

    def test_rag_wrapped_prompt_never_triggers_calculator(self):
        rag_prompt = (
            "RELEVANTNÍ DOKUMENTOVÝ KONTEXT (LOKÁLNÍ RAG ZAČÁTEK):\n"
            "[Úsek 1 | Zdroj: sample.py (relevance: 0.32)]\n"
            "<untrusted_context>\ndef ratio(x):\n    return 0/8\n</untrusted_context>\n"
            "LOKÁLNÍ RAG KONEC\n\nDOTAZ UŽIVATELE:\n" + ORIGINAL_BUG_QUERY
        )
        self.assertIsNone(_try_evaluate_math(rag_prompt))

    def test_actual_math_still_works(self):
        self.assertEqual(_try_evaluate_math("2+2"), "Výsledek je 4.")
        self.assertEqual(_try_evaluate_math("kolik je 100/4?"), "Výsledek je 25.")
        self.assertEqual(_try_evaluate_math("Kolik je 10 krát 5"), "Výsledek je 50.")
        self.assertEqual(_try_evaluate_math("6x7"), "Výsledek je 42.")
        self.assertEqual(_try_evaluate_math("(2+3)*4"), "Výsledek je 20.")
        self.assertEqual(_try_evaluate_math("2,5 + 3"), "Výsledek je 5.5.")
        self.assertEqual(_try_evaluate_math("5/0"), "Dělení nulou není povoleno.")


class WorkspaceDetectionTests(unittest.TestCase):
    """Detekce souborových/vývojářských dotazů pro agentní režim."""

    def test_workspace_queries_detected(self):
        queries = [
            ORIGINAL_BUG_QUERY,
            "prozkoumej strukturu souborů v tomto projektu",
            "vytvoř v adresáři src nový skript",
            "přidej složku tests a přečti soubor main.py",
            "zkontroluj kód v souboru app.ts",
            "list the files in the project directory",
            "create a new folder and write the script",
            "what does this code in module.js do",
        ]
        for query in queries:
            with self.subTest(query=query):
                self.assertTrue(detect_workspace_request(query), query)

    def test_ordinary_queries_not_detected(self):
        queries = [
            "ahoj jak se máš?",
            "kolik je 2+2?",
            "popiš mi děj filmu Metropolis",
            "jak funguje kvantové zapletení?",
            "",
        ]
        for query in queries:
            with self.subTest(query=query):
                self.assertFalse(detect_workspace_request(query), query)

    def test_rag_context_ignored_user_text_analyzed(self):
        # Klíčové slovo jen v RAG kontextu → neaktivuje detekci.
        rag_only = (
            "<untrusted_context>\nvytvoř soubor alpha.py\n</untrusted_context>\n\n"
            "DOTAZ UŽIVATELE:\nahoj, jak se máš?"
        )
        self.assertFalse(detect_workspace_request(rag_only))
        # Klíčové slovo v uživatelském dotazu → aktivuje detekci.
        rag_with_query = rag_only.replace("ahoj, jak se máš?", "prozkoumej projekt")
        self.assertTrue(detect_workspace_request(rag_with_query))

    def test_patterns_have_no_regex_syntax_errors(self):
        import re
        for pattern in WORKSPACE_QUERY_PATTERNS:
            with self.subTest(pattern=pattern):
                re.compile(pattern)


class AutoRoutingTests(unittest.TestCase):
    """Režim Auto: workspace dotazy VŽDY do agentního režimu, nikdy standard."""

    CS_STANDARD = PRESETS_CATALOG["standard"]["name_cs"]
    EN_STANDARD = PRESETS_CATALOG["standard"]["name_en"]
    CS_FIRST_PRINCIPLES = PRESETS_CATALOG["first_principles"]["name_cs"]
    EN_FIRST_PRINCIPLES = PRESETS_CATALOG["first_principles"]["name_en"]

    def test_workspace_query_never_routed_to_standard_cs(self):
        detected = classify_methodology(None, ORIGINAL_BUG_QUERY, language="cs")
        self.assertNotEqual(detected, self.CS_STANDARD)
        self.assertEqual(detected, self.CS_FIRST_PRINCIPLES)

    def test_workspace_query_never_routed_to_standard_en(self):
        detected = classify_methodology(None, ORIGINAL_BUG_QUERY, language="en")
        self.assertNotEqual(detected, self.EN_STANDARD)
        self.assertEqual(detected, self.EN_FIRST_PRINCIPLES)

    def test_detect_analytical_mode_workspace_without_llm(self):
        # Bez LLM klasifikátoru (allow_llm_classifier=False) musí pravidla stačit.
        detected = detect_analytical_mode(ORIGINAL_BUG_QUERY, language="cs")
        self.assertEqual(detected, self.CS_FIRST_PRINCIPLES)

    def test_ordinary_query_still_falls_back_to_standard(self):
        detected = classify_methodology(None, "ahoj, jak se máš?", language="cs")
        self.assertEqual(detected, self.CS_STANDARD)

    def test_explicit_framework_pattern_takes_priority_over_workspace(self):
        # Red team detekce (fáze 1) má přednost před workspace fallbackem.
        query = "udělej red team audit předpokladů projektu"
        detected = detect_analytical_mode(query, language="cs")
        self.assertEqual(detected, PRESETS_CATALOG["red_team"]["name_cs"])


class WorkspaceToolSetTests(unittest.TestCase):
    """ReAct smyčka musí mít k dispozici 8 workspace nástrojů (3 web + 5 system)."""

    def test_eight_workspace_tools(self):
        self.assertEqual(len(WORKSPACE_AGENT_TOOL_NAMES), 8, WORKSPACE_AGENT_TOOL_NAMES)

    def test_contains_file_and_web_tools(self):
        expected = {
            "search_web",
            "query_local_rag",
            "query_memory_rag",
            "analyze_viewport_image",
            "list_directory",
            "read_file",
            "write_file",
            "search_in_files",
        }
        self.assertEqual(set(WORKSPACE_AGENT_TOOL_NAMES), expected)


if __name__ == "__main__":
    unittest.main()

