"""Testy správy projektů (Projects): vytváření prázdných složek, přepínání kontextu a vazba relací."""
import os
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import web_server
from history_repository import HistoryRepository
from llama_module import get_workspace_dir, reset_workspace_dir
from project_repository import ProjectRepository, resolve_project_path


class ProjectsApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(web_server.app, headers={"X-Polygon-Client": "true"})
        self.temp_root = tempfile.mkdtemp(prefix="projects-api-test-")
        self.history = HistoryRepository(path=os.path.join(self.temp_root, "chat_history.txt"))
        self.projects = ProjectRepository(os.path.join(self.temp_root, "projects.json"))
        self._patches = [
            patch.object(web_server, "history_repository", self.history),
            patch.object(web_server, "project_repository", self.projects),
        ]
        for active_patch in self._patches:
            active_patch.start()
        reset_workspace_dir()

    def tearDown(self):
        for active_patch in self._patches:
            active_patch.stop()
        reset_workspace_dir()
        shutil.rmtree(self.temp_root, ignore_errors=True)

    def test_create_project_creates_missing_empty_folder(self):
        new_project = os.path.join(self.temp_root, "brand-new-project")
        self.assertFalse(os.path.exists(new_project))

        response = self.client.post("/api/projects", json={"path": new_project, "name": "Brand New"})

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertTrue(os.path.isdir(new_project))
        self.assertEqual(os.listdir(new_project), [])
        self.assertEqual(data["project"]["name"], "Brand New")
        self.assertEqual(data["project"]["path"], os.path.realpath(new_project))
        self.assertTrue(data["session_id"])

        # Workspace musí být aktivován na nový projekt
        self.assertEqual(os.path.realpath(get_workspace_dir()), os.path.realpath(new_project))

        # Relace musí být svázána s projektem (datový model Konverzace -> Projekt)
        binding = self.history.get_session_project(data["session_id"])
        self.assertEqual(binding["workspace_path"], os.path.realpath(new_project))
        self.assertEqual(binding["project_name"], "Brand New")

    def test_create_project_without_creating_missing_folder_fails(self):
        missing = os.path.join(self.temp_root, "does-not-exist")

        response = self.client.post(
            "/api/projects",
            json={"path": missing, "create_if_missing": False},
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(os.path.exists(missing))

    def test_switch_project_changes_workspace_and_reuses_session(self):
        first = os.path.join(self.temp_root, "project-a")
        second = os.path.join(self.temp_root, "project-b")

        self.client.post("/api/projects", json={"path": first, "name": "A"})
        created = self.client.post("/api/projects", json={"path": second, "name": "B"}).json()
        session_of_b = created["session_id"]

        switched = self.client.post("/api/projects/switch", json={"path": first})

        self.assertEqual(switched.status_code, 200)
        payload = switched.json()
        self.assertEqual(payload["status"], "success")
        self.assertEqual(os.path.realpath(get_workspace_dir()), os.path.realpath(first))
        self.assertEqual(payload["project"]["name"], "A")
        self.assertTrue(any(s["session_id"] for s in payload["sessions"]))
        self.assertTrue(all(os.path.realpath(s["workspace_path"]) == os.path.realpath(first) for s in payload["sessions"]))

        switched_back = self.client.post(
            "/api/projects/switch",
            json={"path": second, "session_id": session_of_b},
        )
        self.assertEqual(switched_back.status_code, 200)
        self.assertEqual(switched_back.json()["session_id"], session_of_b)

    def test_list_projects_reports_active_project_and_conversation_count(self):
        project = os.path.join(self.temp_root, "listed-project")
        self.client.post("/api/projects", json={"path": project, "name": "Listed"})

        response = self.client.get("/api/projects")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(os.path.realpath(data["active"]["path"]), os.path.realpath(project))
        matching = [p for p in data["projects"] if os.path.realpath(p["path"]) == os.path.realpath(project)]
        self.assertEqual(len(matching), 1)
        self.assertTrue(matching[0]["is_active"])
        self.assertGreaterEqual(matching[0]["conversation_count"], 1)

    def test_sensitive_system_paths_are_rejected(self):
        for dangerous_path in ("/", "/etc", "/sys", "/proc", "/root"):
            with self.subTest(path=dangerous_path):
                response = self.client.post("/api/projects", json={"path": dangerous_path})
                self.assertEqual(response.status_code, 400)

    def test_session_detail_exposes_project_binding(self):
        project = os.path.join(self.temp_root, "detail-project")
        created = self.client.post("/api/projects", json={"path": project, "name": "Detail"}).json()
        session_id = created["session_id"]

        response = self.client.get(f"/api/sessions/{session_id}")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["project_name"], "Detail")
        self.assertEqual(os.path.realpath(data["workspace_path"]), os.path.realpath(project))

    def test_relative_path_is_resolved_against_home_directory(self):
        home = os.path.realpath(os.path.expanduser("~"))
        relative_name = f"polygon-projects-relative-{os.getpid()}"

        try:
            response = self.client.post("/api/projects", json={"path": relative_name})
            self.assertEqual(response.status_code, 200)
            expected = resolve_project_path(os.path.join(home, relative_name))
            self.assertEqual(os.path.realpath(response.json()["project"]["path"]), expected)
        finally:
            shutil.rmtree(os.path.join(home, relative_name), ignore_errors=True)

    # --- Výběr složky (browse-folder / quick-dirs) -------------------------

    def test_browse_folder_returns_path_chosen_in_zenity_dialog(self):
        picked = os.path.join(self.temp_root, "picked-project")
        os.makedirs(picked)

        with patch.object(web_server.subprocess, "run") as run_mock:
            run_mock.return_value = subprocess.CompletedProcess(
                args=["zenity"], returncode=0, stdout=f"{picked}\n", stderr=""
            )
            response = self.client.post("/api/projects/browse-folder")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["path"], os.path.realpath(picked))

        # Dialog musí být volán přes zenity s omezením času
        args, kwargs = run_mock.call_args
        command = args[0]
        self.assertEqual(command[0], "zenity")
        self.assertIn("--file-selection", command)
        self.assertIn("--directory", command)
        self.assertTrue(any(str(arg).startswith("--title=") for arg in command))
        self.assertEqual(kwargs.get("timeout"), 60)

    def test_browse_folder_reports_cancelled_dialog(self):
        with patch.object(web_server.subprocess, "run") as run_mock:
            run_mock.return_value = subprocess.CompletedProcess(
                args=["zenity"], returncode=1, stdout="", stderr=""
            )
            response = self.client.post("/api/projects/browse-folder")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "cancelled")
        self.assertIsNone(data["path"])

    def test_browse_folder_treats_timeout_as_cancelled(self):
        with patch.object(
            web_server.subprocess,
            "run",
            side_effect=subprocess.TimeoutExpired(cmd=["zenity"], timeout=60),
        ):
            response = self.client.post("/api/projects/browse-folder")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "cancelled")

    def test_browse_folder_falls_back_to_tkinter_when_zenity_missing(self):
        picked = os.path.join(self.temp_root, "tk-picked")
        os.makedirs(picked)

        with patch.object(web_server.subprocess, "run", side_effect=FileNotFoundError("zenity")), \
                patch.object(web_server, "_tkinter_folder_dialog", return_value=("success", picked)) as tk_mock:
            response = self.client.post("/api/projects/browse-folder")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["path"], os.path.realpath(picked))
        tk_mock.assert_called_once()

    def test_browse_folder_fails_when_no_dialog_backend_available(self):
        with patch.object(web_server.subprocess, "run", side_effect=FileNotFoundError("zenity")), \
                patch.object(web_server, "_tkinter_folder_dialog", return_value=("unavailable", None)):
            response = self.client.post("/api/projects/browse-folder")

        self.assertEqual(response.status_code, 503)

    def test_quick_dirs_returns_safe_default_folders(self):
        response = self.client.get("/api/fs/quick-dirs")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertTrue(data["dirs"])

        home = os.path.realpath(os.path.expanduser("~"))
        paths = [d["path"] for d in data["dirs"]]
        self.assertIn(home, paths)
        self.assertIn(os.path.realpath(get_workspace_dir()), paths)
        # Žádná složka nesmí být uvedena dvakrát
        self.assertEqual(len(paths), len(set(paths)))

        blocked_trees = (
            "/etc", "/sys", "/proc", "/usr", "/bin", "/sbin",
            "/boot", "/dev", "/lib", "/run", "/var",
        )
        for entry in data["dirs"]:
            with self.subTest(path=entry["path"]):
                self.assertIn(entry["key"], ("home", "workspace", "projects"))
                self.assertTrue(os.path.isdir(entry["path"]))
                resolved = os.path.realpath(entry["path"])
                for tree in blocked_trees:
                    canonical = os.path.realpath(tree)
                    self.assertFalse(resolved == canonical or resolved.startswith(canonical + os.sep))


if __name__ == "__main__":
    unittest.main()
