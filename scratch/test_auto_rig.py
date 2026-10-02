import unittest
from unittest.mock import patch, MagicMock
from llama_module import TOOL_SCHEMAS, ALLOWED_TOOL_NAMES, UnifiedToolDispatcher, parse_tool_call
from blender_connector import request_auto_rig

class TestAutoRig(unittest.TestCase):
    def test_allowed_tool_names(self):
        self.assertIn("auto_rig_and_skin", ALLOWED_TOOL_NAMES)

    def test_tool_schema(self):
        names = [s["function"]["name"] for s in TOOL_SCHEMAS if s.get("type") == "function"]
        self.assertIn("auto_rig_and_skin", names)

    @patch("blender_connector.is_blender_available", return_value=True)
    @patch("blender_connector.request_auto_rig", return_value={"status": "success", "bone_count": 5})
    def test_dispatcher(self, mock_rig, mock_avail):
        dispatcher = UnifiedToolDispatcher()
        res = dispatcher.dispatch("auto_rig_and_skin", {"rig_type": "basic"})
        self.assertEqual(res["status"], "success")

if __name__ == "__main__":
    unittest.main()
