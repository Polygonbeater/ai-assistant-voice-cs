#!/usr/bin/env python3
"""
Testovací skript pro ověření funkčnosti Sémantické paměti konverzací (Long-Term Vector Memory):
1. ConversationMemoryService: chunking, embedding, indexace, dohledávání, persistence, mazání.
2. HistoryRepository integrace: automatická indexace a reindexace.
3. llama_module integrace: dohledání a formátování do promptu.
"""

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from document_service import (
    ConversationMemoryService,
    smart_chunk_text,
    MemoryChunk,
)
from history_repository import HistoryRepository
from llama_module import generate_response, DEFAULT_SYSTEM_PROMPT


class TestSemanticMemory(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="test_semantic_mem_")
        self.mem_dir = Path(self.test_dir) / "memory"
        self.sessions_dir = Path(self.test_dir) / "chat_history"
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

        self.memory_service = ConversationMemoryService(
            storage_dir=self.mem_dir,
            top_k=2,
            chunk_size=400,
            chunk_overlap=50,
        )

        self.history_repo = HistoryRepository(
            path=Path(self.test_dir) / "chat_history.txt",
            memory_service=self.memory_service,
        )

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_chunking_and_indexing(self):
        # 1. Otestovat indexaci starší relace o Blenderu
        session_id = "session_blender_001"
        title = "Tvorba animace a shaderu v Blenderu"
        messages = [
            {"role": "user", "content": "Jak mám v Blenderu vytvořit proceduralní materiál pro zlato?"},
            {"role": "assistant", "content": "Pro zlatý materiál v Blenderu použij Principled BSDF s Metallic=1.0, Roughness=0.1 a Base Color nastavenou na hex #FFD700."},
            {"role": "user", "content": "Skvělé, a jak nastavím kameru na vycentrování scény?"},
            {"role": "assistant", "content": "Použij klávesovou zkratku Ctrl+Alt+Numpad 0 nebo v Pythonu bpy.ops.view3d.camera_to_view_selected()."},
        ]

        chunks_count = self.memory_service.index_session(session_id, title, messages)
        self.assertGreater(chunks_count, 0)
        self.assertEqual(self.memory_service.get_memory_stats()["total_sessions"], 1)

        # 2. Indexace druhé relace o Python webovém scraperu
        session_id_2 = "session_python_002"
        title = "Asynchronní stahování v Pythonu"
        messages_2 = [
            {"role": "user", "content": "Jak funguje aiohttp a asyncio v Pythonu?"},
            {"role": "assistant", "content": "Knihovna aiohttp umožňuje neblokující HTTP requesty pomocí ClientSession a asyncio.gather()."},
        ]
        self.memory_service.index_session(session_id_2, title, messages_2)
        self.assertEqual(self.memory_service.get_memory_stats()["total_sessions"], 2)

        # 3. Vyhledání sémantické shody na Blender shader
        results = self.memory_service.search_memory("zlatý materiál metallic blender", top_k=2, score_threshold=0.2)
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0]["session_id"], session_id)
        self.assertIn("Principled BSDF", results[0]["text"])

        # 4. Otestovat vyloučení aktuální relace (exclude_session_id)
        excluded_results = self.memory_service.search_memory(
            "zlatý materiál metallic blender",
            top_k=2,
            score_threshold=0.2,
            exclude_session_id=session_id,
        )
        # Relace session_blender_001 byla vyloučena, takže by neměla být ve výsledcích
        for r in excluded_results:
            self.assertNotEqual(r["session_id"], session_id)

        # 5. Formátování paměti pro LLM prompt
        formatted = self.memory_service.format_memory_for_prompt(results)
        self.assertIn("RELEVANTNÍ HISTORICKÁ PAMĚŤ:", formatted)
        self.assertIn("Principled BSDF", formatted)

        # 6. Smazání jedné relace
        deleted = self.memory_service.delete_session(session_id)
        self.assertTrue(deleted)
        self.assertEqual(self.memory_service.get_memory_stats()["total_sessions"], 1)

        # Ověřit, že po smazání už Blender výsledky nejsou
        after_del = self.memory_service.search_memory("zlatý materiál metallic blender", score_threshold=0.4)
        self.assertEqual(len(after_del), 0)

    def test_history_repository_auto_indexing_and_reindex(self):
        summary = self.history_repo.create_session(title="Nastavení Blender TCP")
        session_id = summary["session_id"]
        self.history_repo.append(session_id, "user", "Ahoj, jak nastavit TCP port v Blenderu?")
        self.history_repo.append(session_id, "assistant", "TCP port pro Blender receiver je defaultně 9876 v blender_receiver.py.")

        # Počkat na dokončení background threadu indexace
        import time
        indexed = False
        for _ in range(80):
            if self.memory_service.get_memory_stats()["total_chunks"] >= 1:
                indexed = True
                break
            time.sleep(0.1)

        self.assertTrue(indexed, "Automatická indexace na pozadí nedokončila uložení bloků včas.")
        stats = self.memory_service.get_memory_stats()
        self.assertGreaterEqual(stats["total_chunks"], 1)

        # Reindexace všech relací
        reindex_res = self.history_repo.reindex_all_to_memory()
        self.assertIn(session_id, reindex_res)
        self.assertGreater(reindex_res[session_id], 0)

        # Smazání relace přes HistoryRepository musí smazat i paměť
        self.history_repo.delete_session(session_id)
        self.assertEqual(self.memory_service.get_memory_stats()["total_chunks"], 0)

    def test_generate_response_semantic_memory_retrieval(self):
        # 1. Uložit minulé preference uživatele do sémantické paměti
        self.memory_service.index_session(
            "old_blender_session",
            "Můj starý projekt v Blenderu",
            [
                {"role": "user", "content": "Moje oblíbená barva pro krychli je smaragdově zelená s hex kódem #50C878."},
                {"role": "assistant", "content": "Rozumím, nastavil jsem pro tebe smaragdově zelenou #50C878."},
            ]
        )

        captured_messages = []

        class MockLLM:
            def create_chat_completion(self, messages, **kwargs):
                captured_messages.extend(messages)
                yield {"choices": [{"delta": {"content": "Jasně, smaragdová barva je #50C878."}}]}

        mock_llm = MockLLM()
        config = {
            "llama": {"online_mode": False, "analytical_preset": "Vypnuto (Standardní chat)"},
            "rag": {"memory_top_k": 2, "memory_score_threshold": 0.25},
        }

        tokens = []
        status_updates = []
        chunks = list(generate_response(
            mock_llm,
            "Jakou barvu jsem minule chtěl pro krychli?",
            config,
            memory_service=self.memory_service,
            active_session_id="new_session_123",
            callback_on_token=tokens.append,
            status_callback=status_updates.append,
        ))

        self.assertGreater(len(chunks), 0)
        self.assertTrue(any("historická paměť" in s.lower() for s in status_updates))
        self.assertTrue(any("RELEVANTNÍ HISTORICKÁ PAMĚŤ:" in m.get("content", "") for m in captured_messages))
        self.assertTrue(any("#50C878" in m.get("content", "") for m in captured_messages))


if __name__ == "__main__":
    unittest.main()
