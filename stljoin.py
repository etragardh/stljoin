#!/usr/bin/env python3
"""
stljoin.py - Combine multiple STL files into one.

Usage as a library:
    from stljoin import create_objects

    objects = [
        {"name": "Object A", "parts": ["parts/part-a1.stl", "parts/part-a2.stl"]},
        {"name": "Object B", "parts": ["parts/part-a1.stl", "parts/part-b.stl"]},
    ]
    create_objects(objects)

Usage from the command line:
    python stljoin.py output.stl input1.stl input2.stl [input3.stl ...]
"""

import struct
import os
import sys
from pathlib import Path


def read_stl(path: str) -> list[tuple]:
    """
    Read an STL file (binary or ASCII) and return a list of triangles.
    Each triangle is a tuple: (normal, v1, v2, v3)
    where each is a tuple of 3 floats.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"STL file not found: {path}")

    with open(path, "rb") as f:
        header = f.read(80)
        if len(header) < 80:
            raise ValueError(f"File too short to be a valid STL: {path}")

        # Check if binary (ASCII STL starts with "solid")
        # but some binary files also start with "solid", so check triangle count
        count_data = f.read(4)
        if len(count_data) < 4:
            raise ValueError(f"File too short to be a valid binary STL: {path}")
        triangle_count = struct.unpack("<I", count_data)[0]
        expected_size = 80 + 4 + triangle_count * 50
        actual_size = path.stat().st_size

        if actual_size == expected_size:
            return _read_binary_stl(f, triangle_count)
        else:
            return _read_ascii_stl(path)


def _read_binary_stl(f, triangle_count: int) -> list[tuple]:
    triangles = []
    for _ in range(triangle_count):
        data = f.read(50)
        if len(data) < 50:
            break
        vals = struct.unpack("<12fH", data)
        normal = (vals[0], vals[1], vals[2])
        v1 = (vals[3], vals[4], vals[5])
        v2 = (vals[6], vals[7], vals[8])
        v3 = (vals[9], vals[10], vals[11])
        triangles.append((normal, v1, v2, v3))
    return triangles


def _read_ascii_stl(path: Path) -> list[tuple]:
    triangles = []
    with open(path, "r", errors="replace") as f:
        normal = (0.0, 0.0, 0.0)
        verts = []
        for line in f:
            line = line.strip()
            if line.startswith("facet normal"):
                parts = line.split()
                normal = (float(parts[2]), float(parts[3]), float(parts[4]))
                verts = []
            elif line.startswith("vertex"):
                parts = line.split()
                verts.append((float(parts[1]), float(parts[2]), float(parts[3])))
            elif line.startswith("endfacet") and len(verts) == 3:
                triangles.append((normal, verts[0], verts[1], verts[2]))
    return triangles


def write_stl(path: str, triangles: list[tuple]) -> None:
    """Write triangles to a binary STL file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "wb") as f:
        header = b"stljoin combined STL" + b" " * 60
        f.write(header[:80])
        f.write(struct.pack("<I", len(triangles)))
        for normal, v1, v2, v3 in triangles:
            f.write(struct.pack("<12fH",
                normal[0], normal[1], normal[2],
                v1[0], v1[1], v1[2],
                v2[0], v2[1], v2[2],
                v3[0], v3[1], v3[2],
                0  # attribute byte count
            ))


verbose = False


def log(msg: str) -> None:
    if verbose:
        print(msg)


def join_stl_files(input_paths: list[str], output_path: str) -> int:
    """
    Join multiple STL files into one. Returns total triangle count.
    """
    all_triangles = []
    for path in input_paths:
        triangles = read_stl(path)
        all_triangles.extend(triangles)
        log(f"  + {path} ({len(triangles)} triangles)")

    write_stl(output_path, all_triangles)
    return len(all_triangles)


def create_objects(objects: list[dict], output_dir: str = "output") -> None:
    """
    Create combined STL files from a list of object definitions.

    Args:
        objects: List of dicts with 'name' and 'parts' keys.
                 'parts' is a list of STL file paths (with or without .stl extension).
        output_dir: Directory to write the combined STL files to.

    Example:
        objects = [
            {"name": "Object A", "parts": ["parts/part-a1", "parts/part-a2"]},
            {"name": "Object B", "parts": ["parts/part-a1", "parts/part-b"]},
        ]
        create_objects(objects)
    """
    for obj in objects:
        name = obj["name"]
        parts = obj["parts"]

        # Normalize part paths (add .stl if missing)
        normalized = []
        for p in parts:
            p = str(p)
            if not p.lower().endswith(".stl"):
                p += ".stl"
            normalized.append(p)

        # Slugify name for filename
        slug = name.lower().replace(" ", "-")
        for ch in ["\\", "/", ":", "*", "?", '"', "<", ">", "|"]:
            slug = slug.replace(ch, "")
        output_path = os.path.join(output_dir, f"{slug}.stl")

        log(f"\n[{name}] -> {output_path}")
        total = join_stl_files(normalized, output_path)
        log(f"  = {total} total triangles")

    log(f"\nDone. {len(objects)} object(s) written to '{output_dir}/'")


# ---------------------------------------------------------------------------
# CLI usage: python stljoin.py [-v] output.stl input1.stl input2.stl ...
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    args = sys.argv[1:]

    if "-v" in args:
        verbose = True
        args.remove("-v")

    if len(args) < 3:
        print("Usage: python stljoin.py [-v] output.stl input1.stl input2.stl [...]")
        print()
        print("Or use as a library:")
        print("  from stljoin import create_objects")
        sys.exit(1)

    output = args[0]
    inputs = args[1:]
    log(f"Joining {len(inputs)} file(s) into {output}")
    total = join_stl_files(inputs, output)
    log(f"Done. {total} total triangles written to {output}")
