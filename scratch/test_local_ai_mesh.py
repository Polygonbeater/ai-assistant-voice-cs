#!/usr/bin/env python3
"""
Unit testy pro modul 'Local AI 3D Mesh Generation & Production Retopology Pipeline' (20. nástroj):
- Ověření wrapperu local_3d_inference.py (generování PLY / OBJ, dummy režim).
- Ověření JSON schématu v TOOL_SCHEMAS a přítomnosti v ALLOWED_TOOL_NAMES (celkem 20 nástrojů).
- Ověření parsování tool calls pro generate_local_ai_mesh (kompaktní i OpenAI formát).
- Ověření klientské funkce request_local_ai_mesh v blender_connector.py.
- Ověření UnifiedToolDispatcheru, expertního Lead 3D AI Engineer promptu a Markdown tabulky retopologie.
"""

import os
import json
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from local_3d_inference import (
    Local3DInferencePipeline,
    generate_local_ai_3d_mesh,
    _write_dummy_ply,
    _write_dummy_obj,
)
from blender_connector import (
    request_local_ai_mesh,
)
from llama_module import (
    ALLOWED_TOOL_NAMES,
    TOOL_SCHEMAS,
    UnifiedToolDispatcher,
    parse_tool_call,
)

# ── Sdílená mock data ──────────────────────────────────────────────────────────

MOCK_AI_MESH_RESPONSE = {
    "status": "success",
    "action": "generate_local_ai_mesh",
    "object_name": "AI_Robot_Asset",
    "image_path": "/tmp/scifi_robot.png",
    "production_ready": True,
    "raw_vertex_count": 28450,
    "raw_face_count": 56890,
    "retopo_vertex_count": 10042,
    "retopo_face_count": 10000,
    "quad_percentage": 98.4,
    "triangle_percentage": 1.6,
    "reduction_ratio": 82.4,
    "texture_name": "AI_Robot_Asset_Baked_Diffuse",
    "texture_resolution": [2048, 2048],
    "material_name": "AI_Robot_Asset_PBR_Material",
    "uv_unwrapped": True,
    "pbr_ready": True,
    "retopology_method": "Voxel Remesh + QuadriFlow",
}


class TestLocal3DInferenceWrapper(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="test_ai_mesh_")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_write_dummy_ply(self):
        ply_file = os.path.join(self.temp_dir, "test_output.ply")
        verts, faces = _write_dummy_ply(ply_file, subdivisions=12, radius=1.0)
        self.assertTrue(os.path.isfile(ply_file))
        self.assertGreater(verts, 0)
        self.assertGreater(faces, 0)

        with open(ply_file, "r", encoding="utf-8") as f:
            header = f.read(200)
            self.assertIn("ply", header)
            self.assertIn("format ascii", header)
            self.assertIn("property uchar red", header)

    def test_write_dummy_obj(self):
        obj_file = os.path.join(self.temp_dir, "test_output.obj")
        verts, faces = _write_dummy_obj(obj_file, subdivisions=12, radius=1.0)
        self.assertTrue(os.path.isfile(obj_file))
        self.assertGreater(verts, 0)
        self.assertGreater(faces, 0)

        with open(obj_file, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("v ", content)
            self.assertIn("f ", content)

    def test_pipeline_generate_mesh_ply(self):
        pipeline = Local3DInferencePipeline(cache_dir=self.temp_dir)
        res = pipeline.generate_mesh("sample_hero.png", target_format="ply")
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["format"], "ply")
        self.assertTrue(res["has_vertex_colors"])
        self.assertTrue(res["is_mock"])
        self.assertTrue(os.path.isfile(res["mesh_path"]))

    def test_global_helper_generate_local_ai_3d_mesh(self):
        out_path = os.path.join(self.temp_dir, "custom_asset.obj")
        res = generate_local_ai_3d_mesh("concept_art.jpg", output_path=out_path, target_format="obj")
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["mesh_path"], out_path)
        self.assertTrue(os.path.isfile(out_path))


class TestRealTripoSRInference(unittest.TestCase):
    def test_real_triposr_raises_when_tsr_none(self):
        from local_3d_inference import RealTripoSRInference
        with patch("local_3d_inference.TSR", None):
            with self.assertRaises(ImportError):
                RealTripoSRInference()

    @patch("local_3d_inference.rembg.remove")
    @patch("local_3d_inference.Image.open")
    def test_real_triposr_generate_pipeline(self, mock_img_open, mock_rembg_remove):
        from local_3d_inference import RealTripoSRInference

        mock_mesh = MagicMock()
        mock_model = MagicMock()
        mock_model.extract_mesh.return_value = [mock_mesh]
        mock_model.return_value = "fake_scene_codes"
        mock_model.device = "cpu"

        mock_tsr_cls = MagicMock()
        mock_tsr_cls.from_pretrained.return_value = mock_model

        with patch("local_3d_inference.TSR", mock_tsr_cls):
            infer = RealTripoSRInference(
                pretrained_model_name_or_path="stabilityai/TripoSR",
                config_name="TripoSR/config.yaml",
                weight_name="model.ckpt",
            )
            mock_tsr_cls.from_pretrained.assert_called_once()
            mock_model.to.assert_called_once()

            out_file = "/tmp/test_real_output.obj"
            res_path = infer.generate("sample_input.png", out_file)

            self.assertEqual(res_path, out_file)
            mock_img_open.assert_called_once_with("sample_input.png")
            mock_rembg_remove.assert_called_once()
            mock_model.extract_mesh.assert_called_once()
            mock_mesh.export.assert_called_once_with(out_file)

    @patch("local_3d_inference.RealTripoSRInference")
    def test_generate_local_ai_3d_mesh_real_branch(self, mock_real_cls):
        mock_instance = MagicMock()
        mock_instance.generate.return_value = "/tmp/real_generated.obj"
        mock_real_cls.return_value = mock_instance

        from local_3d_inference import generate_local_ai_3d_mesh
        res = generate_local_ai_3d_mesh("test_photo.png", output_path="/tmp/real_generated.obj")

        self.assertEqual(res["status"], "success")
        self.assertFalse(res["is_mock"])
        self.assertIn("TripoSR", res["model_name"])
        self.assertEqual(res["mesh_path"], "/tmp/real_generated.obj")


class TestLocalAIMeshToolSchemas(unittest.TestCase):
    def test_generate_local_ai_mesh_in_schemas(self):
        names = [t["function"]["name"] for t in TOOL_SCHEMAS]
        self.assertIn("generate_local_ai_mesh", names)

    def test_schema_properties(self):
        schema = next(
            t for t in TOOL_SCHEMAS if t["function"]["name"] == "generate_local_ai_mesh"
        )
        props = schema["function"]["parameters"]["properties"]
        self.assertIn("image_path", props)
        self.assertIn("production_ready", props)
        self.assertIn("target_faces", props)
        self.assertIn("texture_size", props)
        self.assertIn("object_name", props)
        self.assertEqual(schema["function"]["parameters"]["required"], ["image_path"])

    def test_allowed_tool_names_contains_local_ai_mesh(self):
        self.assertIn("generate_local_ai_mesh", ALLOWED_TOOL_NAMES)

    def test_total_tool_count_is_twenty(self):
        # Aktualizováno na 22 po přidání nástroje auto_rig_and_skin
        self.assertEqual(len(ALLOWED_TOOL_NAMES), 22)


class TestLocalAIMeshParseToolCall(unittest.TestCase):
    def test_parse_compact_format(self):
        raw = json.dumps({
            "tool": "generate_local_ai_mesh",
            "arguments": {
                "image_path": "/tmp/weapon_concept.png",
                "production_ready": True,
                "target_faces": 8000,
            },
        })
        parsed = parse_tool_call(raw)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["name"], "generate_local_ai_mesh")
        self.assertEqual(parsed["arguments"]["image_path"], "/tmp/weapon_concept.png")
        self.assertEqual(parsed["arguments"]["target_faces"], 8000)

    def test_parse_openai_format(self):
        raw = json.dumps({
            "type": "function",
            "function": {
                "name": "generate_local_ai_mesh",
                "arguments": json.dumps({
                    "image_path": "/tmp/creature.jpg",
                    "texture_size": 4096,
                    "object_name": "Alien_Boss",
                }),
            },
        })
        parsed = parse_tool_call(raw)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["name"], "generate_local_ai_mesh")
        self.assertEqual(parsed["arguments"]["texture_size"], 4096)
        self.assertEqual(parsed["arguments"]["object_name"], "Alien_Boss")


class TestLocalAIMeshConnector(unittest.TestCase):
    @patch("blender_connector._send_blender_request")
    def test_request_local_ai_mesh_payload_forwarding(self, mock_send):
        mock_send.return_value = MOCK_AI_MESH_RESPONSE

        res = request_local_ai_mesh(
            image_path="/tmp/scifi_robot.png",
            production_ready=True,
            target_faces=10000,
            texture_size=2048,
            voxel_size=0.015,
            object_name="AI_Robot_Asset",
            timeout=60.0,
        )
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["object_name"], "AI_Robot_Asset")
        self.assertEqual(res["quad_percentage"], 98.4)

        mock_send.assert_called_once()
        cmd = mock_send.call_args[0][0]
        self.assertEqual(cmd["action"], "generate_local_ai_mesh")
        self.assertEqual(cmd["image_path"], "/tmp/scifi_robot.png")
        self.assertTrue(cmd["production_ready"])
        self.assertEqual(cmd["target_faces"], 10000)
        self.assertEqual(cmd["texture_size"], 2048)
        self.assertEqual(cmd["voxel_size"], 0.015)
        self.assertEqual(cmd["object_name"], "AI_Robot_Asset")

    @patch("blender_connector._send_blender_request")
    def test_request_local_ai_mesh_error_raising(self, mock_send):
        from blender_connector import BlenderExecutionError
        mock_send.side_effect = BlenderExecutionError("QuadriFlow remesh failed")

        with self.assertRaises(BlenderExecutionError):
            request_local_ai_mesh(image_path="/tmp/test.png", raise_on_error=True)


class TestLocalAIMeshDispatcher(unittest.TestCase):
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
        res = dispatcher.dispatch(
            "generate_local_ai_mesh",
            {"image_path": "/tmp/scifi_robot.png"},
        )
        self.assertEqual(res["status"], "error")
        self.assertEqual(res["error"], "BlenderNotConnected")
        self.assertTrue(any("není připojen" in t for t in tokens))

    @patch("blender_connector.is_blender_available", return_value=True)
    @patch("blender_connector.request_local_ai_mesh")
    def test_dispatch_success_formatting_and_prompt(self, mock_req, mock_avail):
        mock_req.return_value = MOCK_AI_MESH_RESPONSE
        tokens = []
        statuses = []

        dispatcher = UnifiedToolDispatcher(
            config=self.config,
            status_callback=statuses.append,
            callback_on_token=tokens.append,
        )

        res = dispatcher.dispatch(
            "generate_local_ai_mesh",
            {
                "image_path": "/tmp/scifi_robot.png",
                "production_ready": True,
                "target_faces": 10000,
                "texture_size": 2048,
            },
        )
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["object_name"], "AI_Robot_Asset")
        self.assertEqual(res["raw_face_count"], 56890)
        self.assertEqual(res["retopo_face_count"], 10000)
        self.assertEqual(res["quad_percentage"], 98.4)
        self.assertEqual(res["reduction_ratio"], 82.4)

        # Expertní systémový prompt pro Lead 3D AI Engineera
        expert_prompt = res.get("_expert_system_prompt", "")
        self.assertIn("Lead 3D AI Engineer", expert_prompt)
        self.assertIn("retopologie", expert_prompt)
        self.assertIn("Quad topologii", expert_prompt)
        self.assertIn("QuadriFlow", expert_prompt)
        self.assertIn("Texture Baking", expert_prompt)
        self.assertIn("PBR standardy", expert_prompt)

        # UI Markdown tabulka
        report_text = "".join(tokens)
        self.assertIn("Local AI 3D Mesh Generation & Production Retopology", report_text)
        self.assertIn("AI_Robot_Asset", report_text)
        self.assertIn("Počet polygonů (Faces)", report_text)
        self.assertIn("56,890 tris", report_text)
        self.assertIn("-82.4%", report_text)
        self.assertIn("redukce", report_text)
        self.assertIn("98.4% Quady", report_text)
        self.assertIn("Smart UV Project", report_text)
        self.assertIn("Principled BSDF", report_text)

    @patch("blender_connector.is_blender_available", return_value=True)
    @patch("blender_connector.request_local_ai_mesh")
    def test_dispatch_blender_error(self, mock_req, mock_avail):
        mock_req.return_value = {
            "status": "error",
            "error": "Failed during Voxel Remesh",
        }
        tokens = []
        dispatcher = UnifiedToolDispatcher(
            config=self.config,
            callback_on_token=tokens.append,
        )

        res = dispatcher.dispatch(
            "generate_local_ai_mesh",
            {"image_path": "/tmp/scifi_robot.png"},
        )
        self.assertEqual(res["status"], "error")
        self.assertEqual(res["error"], "Failed during Voxel Remesh")
        self.assertTrue(any("selhalo" in t for t in tokens))


if __name__ == "__main__":
    unittest.main()
