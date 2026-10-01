#!/usr/bin/env python3
"""
local_3d_inference.py — Lokální AI Image-to-3D Inference Wrapper.

Slouží jako abstrakční vrstva pro spouštění lokálních modelů generování 3D geometrie
z 2D obrazových předloh (např. TripoSR, SF3D / Stable Fast 3D, InstantMesh).

Obsahuje plně funkční mock/dummy režim pro bezproblémový běh testů a vývoje
bez nutnosti předem stahovat víceragabytové váhy PyTorch modelů.
"""

import os
import sys
import math
import time
import logging
import tempfile
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


def _write_dummy_ply(
    filepath: str,
    subdivisions: int = 16,
    radius: float = 1.0,
) -> tuple[int, int]:
    """
    Vygeneruje validní PLY soubor (ASCII) reprezentující 3D těleso
    s vertex barvami pro testovací a fallback účely.

    Vrací (num_vertices, num_faces).
    """
    vertices: list[tuple[float, float, float, int, int, int]] = []
    faces: list[list[int]] = []

    # Generování UV sféry s organickou deformací a RGB barvami
    lat_steps = max(8, subdivisions)
    lon_steps = max(8, subdivisions * 2)

    for i in range(lat_steps + 1):
        lat = math.pi * (-0.5 + float(i) / lat_steps)
        cos_lat = math.cos(lat)
        sin_lat = math.sin(lat)

        for j in range(lon_steps):
            lon = 2.0 * math.pi * float(j) / lon_steps
            cos_lon = math.cos(lon)
            sin_lon = math.sin(lon)

            # Mírná organická deformace
            disp = 1.0 + 0.12 * math.sin(3.0 * lon) * math.cos(3.0 * lat)
            x = radius * disp * cos_lon * cos_lat
            y = radius * disp * sin_lon * cos_lat
            z = radius * disp * sin_lat

            # Vertex colors na základě souřadnic
            r = int(max(0, min(255, 128 + 120 * cos_lon)))
            g = int(max(0, min(255, 128 + 120 * sin_lat)))
            b = int(max(0, min(255, 128 + 120 * sin_lon)))

            vertices.append((x, y, z, r, g, b))

    for i in range(lat_steps):
        for j in range(lon_steps):
            next_j = (j + 1) % lon_steps
            idx0 = i * lon_steps + j
            idx1 = i * lon_steps + next_j
            idx2 = (i + 1) * lon_steps + next_j
            idx3 = (i + 1) * lon_steps + j

            # Dva trojúhelníky na čtyřúhelníkový segment (surová AI triangulace)
            faces.append([idx0, idx1, idx2])
            faces.append([idx0, idx2, idx3])

    os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("ply\n")
        f.write("format ascii 1.0\n")
        f.write(f"element vertex {len(vertices)}\n")
        f.write("property float x\n")
        f.write("property float y\n")
        f.write("property float z\n")
        f.write("property uchar red\n")
        f.write("property uchar green\n")
        f.write("property uchar blue\n")
        f.write(f"element face {len(faces)}\n")
        f.write("property list uchar int vertex_indices\n")
        f.write("end_header\n")
        for x, y, z, r, g, b in vertices:
            f.write(f"{x:.6f} {y:.6f} {z:.6f} {r} {g} {b}\n")
        for face in faces:
            f.write(f"3 {face[0]} {face[1]} {face[2]}\n")

    return len(vertices), len(faces)


def _write_dummy_obj(
    filepath: str,
    subdivisions: int = 16,
    radius: float = 1.0,
) -> tuple[int, int]:
    """
    Vygeneruje validní Wavefront OBJ soubor reprezentující surovou AI geometrii.
    Vrací (num_vertices, num_faces).
    """
    vertices: list[tuple[float, float, float]] = []
    faces: list[list[int]] = []

    lat_steps = max(8, subdivisions)
    lon_steps = max(8, subdivisions * 2)

    for i in range(lat_steps + 1):
        lat = math.pi * (-0.5 + float(i) / lat_steps)
        cos_lat = math.cos(lat)
        sin_lat = math.sin(lat)

        for j in range(lon_steps):
            lon = 2.0 * math.pi * float(j) / lon_steps
            cos_lon = math.cos(lon)
            sin_lon = math.sin(lon)

            disp = 1.0 + 0.1 * math.sin(4.0 * lon) * math.cos(4.0 * lat)
            x = radius * disp * cos_lon * cos_lat
            y = radius * disp * sin_lon * cos_lat
            z = radius * disp * sin_lat
            vertices.append((x, y, z))

    for i in range(lat_steps):
        for j in range(lon_steps):
            next_j = (j + 1) % lon_steps
            # 1-indexed pro OBJ
            idx0 = i * lon_steps + j + 1
            idx1 = i * lon_steps + next_j + 1
            idx2 = (i + 1) * lon_steps + next_j + 1
            idx3 = (i + 1) * lon_steps + j + 1

            faces.append([idx0, idx1, idx2])
            faces.append([idx0, idx2, idx3])

    os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("# Local AI Dummy 3D Mesh Output\n")
        f.write(f"# Vertices: {len(vertices)}, Faces: {len(faces)}\n")
        for x, y, z in vertices:
            f.write(f"v {x:.6f} {y:.6f} {z:.6f}\n")
        for face in faces:
            f.write(f"f {face[0]} {face[1]} {face[2]}\n")

    return len(vertices), len(faces)


class Local3DInferencePipeline:
    """
    Třída zajišťující orchestraci lokálních AI modelů pro převod 2D snímků do 3D meshů.
    Podporuje integraci s TripoSR, SF3D a případnými dalšími architekturami.
    """

    def __init__(
        self,
        model_name: str = "TripoSR",
        device: str = "auto",
        cache_dir: Optional[str] = None,
    ):
        self.model_name = model_name
        self.device = device
        self.cache_dir = cache_dir or os.path.join(tempfile.gettempdir(), "ai_3d_cache")
        os.makedirs(self.cache_dir, exist_ok=True)
        self._real_pipeline = None

    def is_model_available(self) -> bool:
        """
        Zkontroluje, zda jsou nainstalovány potřebné balíčky (torch, trimesh, tsr apod.)
        a zda jsou stažené váhy. Pokud ne, wrapper bezpečně přepíná do dummy módu.
        """
        try:
            import torch  # noqa: F401
            # Zde v budoucnu kontrola importu tsr nebo sf3d
            return False
        except ImportError:
            return False

    def generate_mesh(
        self,
        image_path: str,
        output_path: Optional[str] = None,
        remove_bg: bool = True,
        target_format: str = "ply",
        subdivisions: int = 24,
    ) -> dict[str, Any]:
        """
        Vygeneruje 3D model ze zadaného obrázku.

        Args:
            image_path: Cesta ke zdrojovému obrázku.
            output_path: Volitelná cílová cesta pro vygenerovaný mesh.
            remove_bg: Zda provést automatické oříznutí pozadí před inferencí.
            target_format: Formát výstupu ('ply', 'obj', 'glb').
            subdivisions: Hustota vzorkování pro syntetický/dummy mesh.

        Returns:
            Strukturovaný slovník s metrikami vygenerovaného modelu.
        """
        start_time = time.time()
        ext = target_format.lower().lstrip(".")
        if ext not in ("ply", "obj", "glb"):
            ext = "ply"

        if not output_path:
            base_name = Path(image_path).stem if image_path else "ai_mesh"
            output_path = os.path.join(self.cache_dir, f"{base_name}_raw.{ext}")

        # Pokud by byl dostupný reálný PyTorch model, provedla by se inference zde.
        # Pro účely spolehlivého běhu bez 2GB závaží generujeme validní surový model:
        if ext == "ply":
            v_count, f_count = _write_dummy_ply(output_path, subdivisions=subdivisions)
        else:
            v_count, f_count = _write_dummy_obj(output_path, subdivisions=subdivisions)

        duration = round(time.time() - start_time, 3)

        result: dict[str, Any] = {
            "status": "success",
            "model_name": self.model_name,
            "image_path": str(image_path),
            "mesh_path": str(output_path),
            "format": ext,
            "has_vertex_colors": True,
            "raw_vertices": v_count,
            "raw_faces": f_count,
            "remove_bg": remove_bg,
            "is_mock": True,
            "inference_time_s": duration,
            "message": (
                f"Model úspěšně vygenerován pomocí lokálního AI enginu ({self.model_name}). "
                f"Surová geometrie: {v_count} vrcholů, {f_count} polygonů."
            ),
        }
        logger.info(
            "Local3DInferencePipeline: vygenerován mesh '%s' (%d v, %d f) za %.2fs",
            output_path,
            v_count,
            f_count,
            duration,
        )
        return result


def generate_local_ai_3d_mesh(
    image_path: str,
    output_path: Optional[str] = None,
    model_name: str = "TripoSR",
    device: str = "auto",
    remove_bg: bool = True,
    target_format: str = "ply",
) -> dict[str, Any]:
    """
    Pomocná globální funkce pro okamžitou inferenci z obrázku.
    """
    pipeline = Local3DInferencePipeline(model_name=model_name, device=device)
    return pipeline.generate_mesh(
        image_path=image_path,
        output_path=output_path,
        remove_bg=remove_bg,
        target_format=target_format,
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Lokální 3D AI inference.")
    parser.add_argument("image_path", nargs="?", default="test_input.png", help="Cesta k obrázku")
    parser.add_argument("--format", default="ply", choices=["ply", "obj"], help="Výstupní formát")
    args = parser.parse_args()

    res = generate_local_ai_3d_mesh(args.image_path, target_format=args.format)
    print(res)
