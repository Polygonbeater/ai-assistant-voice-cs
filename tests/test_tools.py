import unittest
from llama_module.tools import tools

class TestTools(unittest.TestCase):
    def test_registered_tools(self):
        self.assertEqual(len(tools.registered_tools), 22)

if __name__ == '__main__':
    unittest.main()
