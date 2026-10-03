"""
Unit testy pro bezpečnostní AST validátor kódu (code_validator.py)
a integraci s blender_connector.py.
"""

import unittest
from unittest.mock import patch

from blender_connector import BlenderExecutionError, send_code_to_blender
from code_validator import BlenderCodeValidator, validate_blender_code


class TestBlenderCodeValidator(unittest.TestCase):
    """Testy statické analýzy a bezpečnostních pravidel AST validátoru."""

    def test_legitimate_bpy_code_passes(self):
        """Ověří, že standardní bpy a 3D modelovací skripty jsou povoleny."""
        code = """
import bpy

# Vymazat staré objekty
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

# Vytvořit kostku a kouli
bpy.ops.mesh.primitive_cube_add(size=2.0, location=(0, 0, 1))
cube = bpy.context.active_object
cube.name = "TestCube"

bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, location=(3, 0, 1))
"""
        is_valid, msg = validate_blender_code(code)
        self.assertTrue(is_valid, f"Legitimní bpy kód neprošel: {msg}")
        self.assertEqual(msg, "")

    def test_legitimate_bmesh_and_mathutils_code_passes(self):
        """Ověří, že práce s bmesh a mathutils je povolena."""
        code = """
import bpy
import bmesh
import mathutils

mesh = bpy.data.meshes.new("ProceduralMesh")
bm = bmesh.new()
bmesh.ops.create_cube(bm, size=2.0, matrix=mathutils.Matrix.Translation((0, 0, 0)))
bm.to_mesh(mesh)
bm.free()
"""
        is_valid, msg = validate_blender_code(code)
        self.assertTrue(is_valid, f"bmesh kód neprošel: {msg}")
        self.assertEqual(msg, "")

    def test_allowed_helper_modules_pass(self):
        """Ověří, že moduly math, random, colorsys a json jsou povoleny."""
        code = """
import math
import random
import colorsys
import json
import bpy

angle = math.sin(math.pi / 4)
factor = random.uniform(0.1, 0.9)
rgb = colorsys.hsv_to_rgb(0.5, 0.8, factor)
data_str = json.dumps({"r": rgb[0], "g": rgb[1], "b": rgb[2]})
"""
        is_valid, msg = validate_blender_code(code)
        self.assertTrue(is_valid, f"Povolené pomocné moduly neprošly: {msg}")
        self.assertEqual(msg, "")

    def test_dangerous_import_os_fails(self):
        """Ověří, že pokus o import os je zablokován."""
        code = "import os\nos.system('ls')"
        is_valid, msg = validate_blender_code(code)
        self.assertFalse(is_valid)
        self.assertIn("Bezpečnostní pojistka", msg)
        self.assertIn("os", msg)

    def test_dangerous_import_subprocess_fails(self):
        """Ověří, že pokus o import subprocess je zablokován."""
        code = "import subprocess\nsubprocess.run(['echo', 'hello'])"
        is_valid, msg = validate_blender_code(code)
        self.assertFalse(is_valid)
        self.assertIn("Bezpečnostní pojistka", msg)
        self.assertIn("subprocess", msg)

    def test_dangerous_from_sys_import_fails(self):
        """Ověří, že import from sys import ... je zablokován."""
        code = "from sys import exit\nexit(0)"
        is_valid, msg = validate_blender_code(code)
        self.assertFalse(is_valid)
        self.assertIn("Bezpečnostní pojistka", msg)
        self.assertIn("sys", msg)

    def test_dangerous_import_socket_or_requests_fails(self):
        """Ověří, že síťové knihovny (socket, requests, urllib) jsou zablokovány."""
        for mod in ("socket", "requests", "urllib", "urllib.request", "shutil", "pathlib"):
            code = f"import {mod}"
            is_valid, msg = validate_blender_code(code)
            self.assertFalse(is_valid, f"Modul {mod} nebyl zablokován!")
            self.assertIn("Bezpečnostní pojistka", msg)

    def test_eval_exec_compile_calls_fail(self):
        """Ověří, že dynamické vykonávání kódu (eval, exec, compile) je zablokováno."""
        for func in ("eval('1+1')", "exec('a = 1')", "compile('2+2', '', 'eval')"):
            code = f"import bpy\n{func}"
            is_valid, msg = validate_blender_code(code)
            self.assertFalse(is_valid, f"Funkce {func} nebyla zablokována!")
            self.assertIn("Bezpečnostní pojistka", msg)

    def test_open_file_fails(self):
        """Ověří, že pokus o I/O operaci open(...) je zablokován."""
        code = "import bpy\nf = open('/etc/passwd', 'r')"
        is_valid, msg = validate_blender_code(code)
        self.assertFalse(is_valid)
        self.assertIn("Bezpečnostní pojistka", msg)
        self.assertIn("open", msg)

    def test_builtins_globals_dunder_access_fails(self):
        """Ověří ochranu před pokusy o sandbox escape pomocí reflexe."""
        escape_snippets = [
            "().__class__.__bases__[0].__subclasses__()",
            "x = __builtins__",
            "g = globals()",
            "l = locals()",
            "v = vars()",
            "d = dir()",
            "getattr(bpy, '__subclasses__')",
            "getattr(bpy, 'eval')",
            "func.__globals__",
            "f.__code__",
        ]
        for snippet in escape_snippets:
            code = f"import bpy\n{snippet}"
            is_valid, msg = validate_blender_code(code)
            self.assertFalse(is_valid, f"Escape snippet '{snippet}' nebyl zablokován!")
            self.assertIn("Bezpečnostní pojistka", msg)

    def test_syntax_error_handling(self):
        """Ověří, že syntaktická chyba v kódu nezhroutí proces a vrátí srozumitelnou zprávu."""
        broken_code = "import bpy\ndef broken_function(\n  bpy.ops.mesh.primitive_cube_add()"
        is_valid, msg = validate_blender_code(broken_code)
        self.assertFalse(is_valid)
        self.assertIn("Chyba syntaxe v Python kódu", msg)

    def test_empty_code_fails(self):
        """Ověří, že prázdný kód je odmítnut."""
        is_valid, msg = validate_blender_code("   ")
        self.assertFalse(is_valid)
        self.assertIn("Kód k odeslání je prázdný", msg)

    @patch("socket.socket")
    def test_send_code_to_blender_blocks_dangerous_code_before_socket(self, mock_socket):
        """Ověří, že send_code_to_blender odmítne škodlivý kód dříve než otevře socket."""
        res = send_code_to_blender("import os\nos.system('whoami')")
        self.assertEqual(res["status"], "error")
        self.assertEqual(res["error"], "CodeValidationError")
        self.assertIn("Bezpečnostní pojistka", res["message"])
        mock_socket.assert_not_called()

    @patch("socket.socket")
    def test_send_code_to_blender_blocks_dangerous_code_with_raise(self, mock_socket):
        """Ověří, že send_code_to_blender vyvolá BlenderExecutionError při raise_on_error=True."""
        with self.assertRaises(BlenderExecutionError) as ctx:
            send_code_to_blender("import subprocess", raise_on_error=True)
        self.assertIn("Bezpečnostní pojistka", str(ctx.exception))
        mock_socket.assert_not_called()


if __name__ == "__main__":
    unittest.main()
