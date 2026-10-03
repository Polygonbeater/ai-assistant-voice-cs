import os
import shutil
import tempfile
import unittest
from pathlib import Path

from llama_module import (
    DEFAULT_WORKSPACE_DIR,
    TOOL_SCHEMAS,
    UnifiedToolDispatcher,
    get_workspace_dir,
    reset_workspace_dir,
    set_workspace_dir,
    validate_workspace_path,
)


class WorkspaceToolsTests(unittest.TestCase):
    def setUp(self):
        reset_workspace_dir()
        self.workspace = tempfile.mkdtemp(prefix="workspace-tools-test-", dir=get_workspace_dir())
        self.workspace_rel = os.path.relpath(self.workspace, get_workspace_dir())
        self.dispatcher = UnifiedToolDispatcher()

    def tearDown(self):
        shutil.rmtree(self.workspace)
        reset_workspace_dir()

    def test_workspace_path_rejects_absolute_traversal_and_sensitive_paths(self):
        with self.assertRaises(PermissionError):
            validate_workspace_path("../outside.txt")
        with self.assertRaises(PermissionError):
            validate_workspace_path(os.path.join(get_workspace_dir(), "llama_module.py"))
        for sensitive_path in (".git/config", ".env", "cache/__pycache__/module.pyc", "keys/private.pem", "keys/private.key"):
            with self.subTest(path=sensitive_path), self.assertRaises(PermissionError):
                validate_workspace_path(sensitive_path)

    def test_workspace_path_rejects_symlinks_outside_project(self):
        with tempfile.TemporaryDirectory(prefix="workspace-tools-outside-") as outside:
            external_file = Path(outside, "secret.txt")
            external_file.write_text("secret", encoding="utf-8")
            link_path = Path(self.workspace, "outside-link")
            try:
                link_path.symlink_to(external_file)
            except (OSError, NotImplementedError):
                self.skipTest("Symlinks are unavailable in this environment.")
            with self.assertRaises(PermissionError):
                validate_workspace_path(os.path.relpath(link_path, get_workspace_dir()))

    def test_workspace_path_rejects_sensitive_symlink_aliases(self):
        target = Path(self.workspace, "ordinary", "secret.txt")
        target.parent.mkdir()
        target.write_text("secret", encoding="utf-8")
        git_link = Path(self.workspace, ".git")
        try:
            git_link.symlink_to(target.parent, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("Symlinks are unavailable in this environment.")

        with self.assertRaises(PermissionError):
            validate_workspace_path(f"{self.workspace_rel}/.git/secret.txt")

    def test_write_read_search_and_list_project_files(self):
        relative_file = f"{self.workspace_rel}/nested/sample.py"
        write_result = self.dispatcher.dispatch(
            "write_file",
            {"file_path": relative_file, "content": "first needle_token\nsecond line\n"},
        )
        self.assertEqual(write_result["status"], "success")
        self.assertEqual(
            Path(get_workspace_dir(), relative_file).read_text(encoding="utf-8"),
            "first needle_token\nsecond line\n",
        )

        read_result = self.dispatcher.dispatch(
            "read_file",
            {"file_path": relative_file, "start_line": 2, "end_line": 2},
        )
        self.assertEqual(read_result["result"], "2: second line")

        search_result = self.dispatcher.dispatch(
            "search_in_files",
            {"query": "needle_token", "file_pattern": "sample.py"},
        )
        self.assertEqual(search_result["matches"], 1)
        self.assertIn(f"{relative_file}:1: first needle_token", search_result["result"])

        listing = self.dispatcher.dispatch("list_directory", {"rel_path": f"{self.workspace_rel}/nested"})
        self.assertEqual(
            listing["entries"],
            [{"name": "sample.py", "type": "file", "size": len("first needle_token\nsecond line\n")}],
        )

    def test_read_file_caps_output_at_500_kb(self):
        relative_file = f"{self.workspace_rel}/large.txt"
        Path(get_workspace_dir(), relative_file).write_text("x" * (600 * 1024), encoding="utf-8")

        result = self.dispatcher.dispatch("read_file", {"file_path": relative_file})

        self.assertTrue(result["truncated"])
        self.assertLessEqual(len(result["result"].encode("utf-8")), 500 * 1024)

    def test_file_tools_are_registered_as_system_tools(self):
        schemas = {schema["function"]["name"]: schema for schema in TOOL_SCHEMAS}
        for name in ("list_directory", "read_file", "write_file", "search_in_files"):
            with self.subTest(tool=name):
                self.assertIn(name, schemas)
                self.assertIn("description", schemas[name]["function"])

    def test_workspace_can_be_switched_and_reset(self):
        with tempfile.TemporaryDirectory(prefix="workspace-tools-dynamic-") as alternate:
            alternate_file = Path(alternate, "alternate.txt")
            alternate_file.write_text("dynamic root", encoding="utf-8")

            active = set_workspace_dir(alternate)

            self.assertEqual(active, os.path.realpath(alternate))
            self.assertEqual(validate_workspace_path("alternate.txt"), str(alternate_file))
            self.assertEqual(
                self.dispatcher.dispatch("read_file", {"file_path": "alternate.txt"})["result"],
                "1: dynamic root",
            )
            with self.assertRaises(PermissionError):
                validate_workspace_path(".env")
            self.assertEqual(reset_workspace_dir(), DEFAULT_WORKSPACE_DIR)

    def test_workspace_manager_rejects_missing_relative_and_system_directories(self):
        with self.assertRaises(ValueError):
            set_workspace_dir("relative/project")
        with self.assertRaises(ValueError):
            set_workspace_dir(os.path.join(get_workspace_dir(), "does-not-exist"))
        for dangerous_path in ("/", "/etc", "/sys", "/proc", "/root"):
            with self.subTest(path=dangerous_path), self.assertRaises(PermissionError):
                set_workspace_dir(dangerous_path)


if __name__ == "__main__":
    unittest.main()
