"""
setup_paths.py — Run once after `uv sync` to add the project root
to the venv's sys.path.

Usage:
    uv run python setup_paths.py
"""
import site
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent

sp_dirs = site.getsitepackages() if hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix else [site.getusersitepackages()]

for sp in sp_dirs:
    sp_path = Path(sp)
    if sp_path.exists():
        pth_file = sp_path / "pointcloud-labeling.pth"
        pth_file.write_text(str(project_root) + "\n")
        print(f"Created {pth_file}")
        print(f"  → {project_root}")
        break
else:
    print(f'Add this to scripts:\n  import sys; sys.path.insert(0, r"{project_root}")')
