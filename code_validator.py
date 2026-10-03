"""
Bezpečnostní AST validátor Python kódu pro provádění skriptů v Blenderu.
Chrání instanci Blenderu a hostitelský systém před spuštěním nebezpečného
či škodlivého kódu (sandbox escape, neautorizované I/O, systémové příkazy).
"""

from __future__ import annotations

import ast
import logging
from typing import ClassVar

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
    "exit",
    "quit",
    "getattr",
    "setattr",
    "hasattr",
    "delattr",
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

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            root_module = alias.name.split(".")[0]
            if root_module not in ALLOWED_MODULES:
                self.errors.append(
                    f"Importování modulu '{alias.name}' není povoleno. "
                    f"Povolené moduly jsou: {', '.join(sorted(ALLOWED_MODULES))}."
                )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        mod_name = node.module or ""
        root_module = mod_name.split(".")[0] if mod_name else ""
        if root_module not in ALLOWED_MODULES:
            self.errors.append(
                f"Importování z modulu '{mod_name}' není povoleno. "
                f"Povolené moduly jsou: {', '.join(sorted(ALLOWED_MODULES))}."
            )
        for alias in node.names:
            if alias.name in BANNED_BUILTINS or alias.name in BANNED_ATTRIBUTES or alias.name.startswith("__"):
                self.errors.append(f"Importování prvku '{alias.name}' je z bezpečnostních důvodů zakázáno.")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        # Přímé volání funkce podle jména (např. eval(), open(), exec(), getattr())
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
            if func_name in BANNED_BUILTINS:
                self.errors.append(f"Volání vestavěné/reflexní funkce '{func_name}()' je z bezpečnostních důvodů zakázáno.")

        # Volání přes atribut (např. os.system(), builtins.eval(), obj.__subclasses__())
        elif isinstance(node.func, ast.Attribute):
            attr_name = node.func.attr
            if attr_name in BANNED_BUILTINS:
                self.errors.append(f"Volání zakázané funkce/metody '{attr_name}()' je zakázáno.")
            elif attr_name.startswith("__") or attr_name in BANNED_ATTRIBUTES:
                raise ValueError(f"Bezpečnostní pojistka: Přístup k interním dunder atributům (.{attr_name}) je striktně zakázán.")

        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr.startswith("__"):
            raise ValueError(f"Bezpečnostní pojistka: Přístup k interním dunder atributům (.{node.attr}) je striktně zakázán.")
        if node.attr in BANNED_ATTRIBUTES:
            self.errors.append(f"Přístup k atributu '{node.attr}' je z bezpečnostních důvodů zakázán.")
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if node.id in ("__builtins__", "__globals__") or node.id.startswith("__"):
            self.errors.append(f"Přímý přístup k identifikátoru '{node.id}' je zakázán.")
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
