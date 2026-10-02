import unittest
from llama_module import TOOL_SCHEMAS, ALLOWED_TOOL_NAMES

class TestTools(unittest.TestCase):
    def test_registered_tools(self):
        self.assertEqual(len(TOOL_SCHEMAS), 22)
        self.assertEqual(len(ALLOWED_TOOL_NAMES), 22)

if __name__ == '__main__':
    unittest.main()
