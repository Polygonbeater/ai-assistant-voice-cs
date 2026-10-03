"""
Bezpečnostní AST validátor Python kódu pro provádění skriptů v Blenderu.
Chrání instanci Blenderu a hostitelský systém před spuštěním nebezpečného
či škodlivého kódu (sandbox escape, neautorizované I/O, systémové příkazy).
"""

from __future__ import annotations

import ast
import logging
import pathlib
import tempfile

logger = logging.getLogger(__name__)

# Whitelist povolených modulů pro 3D grafiku, geometrii a matematiku
ALLOWED_MODULES: frozenset[str] = frozenset({
    "bpy",
    "bmesh",
    "mathutils",
    "math",
    "random",
    "colorsys",
    "json",
})

# Zákaz nebezpečných vestavěných a reflexních funkcí
BANNED_BUILTINS: frozenset[str] = frozenset({
    "eval",
    "exec",
    "compile",
    "__import__",
    "open",
    "globals",
    "locals",
    "vars",
    "dir",
    "exit",
    "quit",
    "getattr",
    "setattr",
    "hasattr",
    "delattr",
})

# Alias pro zpětnou kompatibilitu a audit
BLOCKED_FUNCTIONS: frozenset[str] = BANNED_BUILTINS

# Zákaz metod ukládání souborů a renderů na disk
BANNED_SAVE_METHODS: frozenset[str] = frozenset({
    "save",
    "save_render",
    "save_as",
    "save_all_modified",
    "save_sequence",
})

# Zákaz přístupu k dunder atributům pro zamezení reflexe a sandbox escape
BANNED_ATTRIBUTES: frozenset[str] = frozenset({
    "__subclasses__",
    "__builtins__",
    "__globals__",
    "__code__",
    "__closure__",
    "__reduce__",
    "__reduce_ex__",
    "__import__",
})

# Zákaz nebezpečných atributů a souborových I/O operací na objektu bpy
BANNED_BPY_PATTERNS: frozenset[str] = frozenset({
    "bpy.data.texts",
    "data.texts",
    "texts",
    "bpy.ops.text",
    "ops.text",
    "bpy.ops.script",
    "ops.script",
    "bpy.ops.console",
    "ops.console",
    "bpy.ops.image",
    "ops.image",
    "bpy.ops.render",
    "ops.render",
    "bpy.ops.sound",
    "ops.sound",
    "bpy.ops.render.render",
    "ops.render.render",
    "bpy.ops.render.opengl",
    "ops.render.opengl",
    "save",
    "save_render",
    "save_as",
    "save_all_modified",
    "save_sequence",
    "bpy.data.images.load",
    "data.images.load",
    "bpy.data.libraries.load",
    "data.libraries.load",
    "bpy.data.sounds.load",
    "data.sounds.load",
    "bpy.data.movieclips.load",
    "data.movieclips.load",
    "bpy.ops.wm.save_as_mainfile",
    "ops.wm.save_as_mainfile",
    "bpy.ops.wm.save_mainfile",
    "ops.wm.save_mainfile",
    "bpy.ops.wm.open_mainfile",
    "ops.wm.open_mainfile",
    "bpy.ops.wm.read_homefile",
    "ops.wm.read_homefile",
    "bpy.ops.wm.read_factory_settings",
    "ops.wm.read_factory_settings",
    "bpy.ops.wm.read_history",
    "ops.wm.read_history",
    "bpy.ops.wm.recover_auto_save",
    "ops.wm.recover_auto_save",
    "bpy.ops.wm.recover_last_session",
    "ops.wm.recover_last_session",
    "bpy.ops.wm.link",
    "ops.wm.link",
    "bpy.ops.wm.append",
    "ops.wm.append",
    "bpy.ops.wm.url_open",
    "ops.wm.url_open",
    "bpy.ops.wm.quit_blender",
    "ops.wm.quit_blender",
    "bpy.ops.wm.sysinfo_file_write",
    "ops.wm.sysinfo_file_write",
})

BANNED_BPY_PREFIXES: tuple[str, ...] = (
    "bpy.data.texts.",
    "data.texts.",
    "bpy.ops.text.",
    "ops.text.",
    "bpy.ops.script.",
    "ops.script.",
    "bpy.ops.console.",
    "ops.console.",
    "bpy.ops.image.",
    "ops.image.",
    "bpy.ops.render.",
    "ops.render.",
    "bpy.ops.sound.",
    "ops.sound.",
    "bpy.ops.export_",
    "ops.export_",
    "bpy.ops.import_",
    "ops.import_",
    "bpy.ops.wm.save_",
    "ops.wm.save_",
    "bpy.ops.wm.open_",
    "ops.wm.open_",
    "bpy.ops.wm.read_",
    "ops.wm.read_",
    "bpy.ops.wm.recover_",
    "ops.wm.recover_",
    "bpy.ops.wm.obj_export",
    "ops.wm.obj_export",
    "bpy.ops.wm.obj_import",
    "ops.wm.obj_import",
    "bpy.ops.wm.ply_export",
    "ops.wm.ply_export",
    "bpy.ops.wm.ply_import",
    "ops.wm.ply_import",
    "bpy.ops.wm.gltf_export",
    "ops.wm.gltf_export",
    "bpy.ops.wm.gltf_import",
    "ops.wm.gltf_import",
    "bpy.ops.wm.usd_export",
    "ops.wm.usd_export",
    "bpy.ops.wm.usd_import",
    "ops.wm.usd_import",
    "bpy.ops.wm.alembic_export",
    "ops.wm.alembic_export",
    "bpy.ops.wm.alembic_import",
    "ops.wm.alembic_import",
    "bpy.ops.wm.fbx_export",
    "ops.wm.fbx_export",
    "bpy.ops.wm.fbx_import",
    "ops.wm.fbx_import",
)


def is_safe_output_path(filepath: str, allowed_dirs: list[str] | None = None) -> tuple[bool, str, pathlib.Path | None]:
    """
    Bezpečnostní validace a sandboxing cílové cesty pro render/viewport/export.
    Ověří, že cílová cesta leží výhradně v povoleném adresáři (/tmp, tempfile, scratch/ uvnitř projektu)
    a neobsahuje nepovolený path traversal ('..').
    """
    if not filepath or not str(filepath).strip():
        return False, "Výstupní cesta nesmí být prázdná.", None

    clean_str = str(filepath).strip().strip("'\"`:*#")

    # Zákaz '..'
    if ".." in pathlib.Path(clean_str).parts:
        return False, f"Path traversal '..' je zakázán: {clean_str}", None

    try:
        resolved_path = pathlib.Path(clean_str).resolve()
    except Exception as e:
        return False, f"Neplatná cesta: {e}", None

    # Standardní povolené kořenové složky
    allowed_roots: list[pathlib.Path] = [
        pathlib.Path(tempfile.gettempdir()).resolve(),
        pathlib.Path("/tmp").resolve(),
    ]
    try:
        project_root = pathlib.Path(__file__).resolve().parent
        allowed_roots.append((project_root / "scratch").resolve())
        allowed_roots.append((project_root / "renders").resolve())
        allowed_roots.append((project_root / "rag_storage").resolve())
    except Exception:
        pass

    if allowed_dirs:
        for d in allowed_dirs:
            try:
                allowed_roots.append(pathlib.Path(d).resolve())
            except Exception:
                pass

    is_inside = any(
        root in resolved_path.parents or resolved_path.parent == root
        for root in allowed_roots
    )

    if not is_inside:
        return False, f"Zápis mimo povolené adresáře je zakázán: {resolved_path}", None

    return True, "", resolved_path


def get_attribute_chain(node: ast.AST) -> str:
    """Rekurzivně sestaví tečkový řetězec atributů, např. 'bpy.data.texts.load'."""
    parts: list[str] = []
    curr = node
    while isinstance(curr, ast.Attribute):
        parts.append(curr.attr)
        curr = curr.value
    if isinstance(curr, ast.Name):
        parts.append(curr.id)
        return ".".join(reversed(parts))
    return ""


class CodeValidationError(Exception):
    """Výjimka vyvolaná při porušení bezpečnostních pravidel AST validátoru."""


class BlenderCodeValidator(ast.NodeVisitor):
    """
    AST Visitor pro statickou analýzu a validaci Python (bpy) skriptů
    před jejich odesláním do běžící instance Blenderu.
    """

    def __init__(self) -> None:
        super().__init__()
        self.errors: list[str] = []

    def _check_attribute_chain_safety(self, node: ast.AST) -> None:
        chain = get_attribute_chain(node)
        if not chain:
            return
        if (
            chain in BANNED_BPY_PATTERNS
            or any(chain.startswith(p) for p in BANNED_BPY_PREFIXES)
            or any(chain.endswith("." + m) for m in BANNED_SAVE_METHODS)
            or chain in BANNED_SAVE_METHODS
        ):
            raise ValueError(
                f"Bezpečnostní pojistka: Přístup k nebezpečnému atributu nebo souborové I/O operaci '{chain}' je zakázán."
            )

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            root_module = alias.name.split(".")[0]
            if root_module not in ALLOWED_MODULES:
                raise ValueError(
                    f"Bezpečnostní pojistka: Importování modulu '{alias.name}' není povoleno. "
                    f"Povolené moduly jsou: {', '.join(sorted(ALLOWED_MODULES))}."
                )
            if alias.name in BANNED_BPY_PATTERNS or any(alias.name.startswith(p) for p in BANNED_BPY_PREFIXES):
                raise ValueError(f"Bezpečnostní pojistka: Importování nebezpečného modulu/prvku '{alias.name}' je zakázáno.")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        mod_name = node.module or ""
        root_module = mod_name.split(".")[0] if mod_name else ""
        if root_module not in ALLOWED_MODULES:
            raise ValueError(
                f"Bezpečnostní pojistka: Importování z modulu '{mod_name}' není povoleno. "
                f"Povolené moduly jsou: {', '.join(sorted(ALLOWED_MODULES))}."
            )
        for alias in node.names:
            full_imported = f"{mod_name}.{alias.name}" if mod_name else alias.name
            if alias.name in BANNED_BUILTINS or alias.name in BANNED_ATTRIBUTES or alias.name.startswith("__"):
                raise ValueError(f"Bezpečnostní pojistka: Importování prvku '{alias.name}' je z bezpečnostních důvodů zakázáno.")
            if (
                full_imported in BANNED_BPY_PATTERNS
                or alias.name in BANNED_BPY_PATTERNS
                or any(full_imported.startswith(p) for p in BANNED_BPY_PREFIXES)
                or any(alias.name.startswith(p) for p in BANNED_BPY_PREFIXES)
            ):
                raise ValueError(f"Bezpečnostní pojistka: Importování nebezpečného prvku '{full_imported}' je zakázáno.")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        # Přímé volání funkce podle jména (např. eval(), open(), exec(), getattr())
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
            if func_name in BLOCKED_FUNCTIONS:
                raise ValueError(f"Bezpečnostní pojistka: Zneužití zakázané funkce nebo proměnné '{func_name}' je striktně zakázáno.")

        # Volání přes atribut (např. os.system(), builtins.eval(), obj.__subclasses__(), bpy.ops.wm.save_as_mainfile(), img.save_render())
        elif isinstance(node.func, ast.Attribute):
            attr_name = node.func.attr
            if attr_name in BLOCKED_FUNCTIONS:
                raise ValueError(f"Bezpečnostní pojistka: Volání zakázané funkce/metody '{attr_name}()' je zakázáno.")
            elif attr_name.startswith("__") or attr_name in BANNED_ATTRIBUTES:
                raise ValueError(f"Bezpečnostní pojistka: Přístup k interním dunder atributům (.{attr_name}) je striktně zakázán.")
            elif attr_name in BANNED_SAVE_METHODS or attr_name.endswith("save_render") or attr_name.endswith("_save") or attr_name.startswith("save_"):
                raise ValueError(f"Bezpečnostní pojistka: Volání metody ukládání souborů/renderu '{attr_name}()' je zakázáno.")
            self._check_attribute_chain_safety(node.func)

        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr.startswith("__"):
            raise ValueError(f"Bezpečnostní pojistka: Přístup k interním dunder atributům (.{node.attr}) je striktně zakázán.")
        if node.attr in BANNED_ATTRIBUTES:
            raise ValueError(f"Bezpečnostní pojistka: Přístup k atributu '{node.attr}' je z bezpečnostních důvodů zakázán.")
        if node.attr in BANNED_SAVE_METHODS or node.attr.endswith("save_render") or node.attr.endswith("_save") or node.attr.startswith("save_"):
            raise ValueError(f"Bezpečnostní pojistka: Přístup k metodě/atributu ukládání '{node.attr}' je z bezpečnostních důvodů zakázán.")
        self._check_attribute_chain_safety(node)
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        """Zablokuje použití zakázaných funkcí i jako aliasů nebo proměnných."""
        if node.id in BLOCKED_FUNCTIONS:
            raise ValueError(f"Bezpečnostní pojistka: Zneužití zakázané funkce nebo proměnné '{node.id}' je striktně zakázáno.")
        if node.id in ("__builtins__", "__globals__") or node.id.startswith("__") or node.id in BANNED_ATTRIBUTES:
            raise ValueError(f"Bezpečnostní pojistka: Přímý přístup k internímu identifikátoru '{node.id}' je striktně zakázán.")
        self.generic_visit(node)


def validate_blender_code(code: str) -> tuple[bool, str]:
    """
    Zkontroluje zadaný Python kód pro Blender pomocí AST.

    Vrací tuple (is_valid, message):
    - (True, "") pokud kód vyhovuje všem bezpečnostním a syntaktickým pravidlům.
    - (False, "Chyba syntaxe v Python kódu: ...") při syntaktické chybě.
    - (False, "Bezpečnostní pojistka: ...") při pokusu o spuštění nepovoleného kódu.
    """
    if not code or not code.strip():
        return False, "Kód k odeslání je prázdný."

    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        line = exc.lineno or "?"
        col = exc.offset or "?"
        msg = exc.msg or str(exc)
        return False, f"Chyba syntaxe v Python kódu: {msg} (řádek {line}, sloupec {col})"
    except Exception as exc:
        return False, f"Chyba syntaxe v Python kódu: {exc}"

    validator = BlenderCodeValidator()
    try:
        validator.visit(tree)
    except ValueError as exc:
        val_msg = str(exc)
        logger.warning("AST validace kódu selhala (ValueError): %s", val_msg)
        if not val_msg.startswith("Bezpečnostní pojistka:"):
            val_msg = f"Bezpečnostní pojistka: {val_msg}"
        return False, val_msg
    except Exception as exc:
        logger.warning("AST validace kódu selhala (Exception): %s", exc)
        return False, f"Bezpečnostní pojistka: {exc}"

    if validator.errors:
        first_error = validator.errors[0]
        logger.warning("AST validace kódu selhala: %s", first_error)
        return False, f"Bezpečnostní pojistka: {first_error}"

    return True, ""
