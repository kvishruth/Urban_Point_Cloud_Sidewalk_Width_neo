#!/usr/bin/env python3
"""
run_pipeline.py — Run the point-cloud labeling pipeline (steps 0–2).

Usage
-----
    uv run python run_pipeline.py
    uv run python run_pipeline.py --tilecodes 120300_489300 120300_488900
    uv run python run_pipeline.py --only 1 2
    uv run python run_pipeline.py --skip-download
    uv run python run_pipeline.py --dry-run
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import textwrap
import time
from pathlib import Path

# Windows asyncio fix
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Ensure project root is on sys.path (so `import config` and `from src.utils` work)
_PROJECT_ROOT = str(Path(__file__).resolve().parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


STEPS = {
    0: ("Download AHN tiles", "scripts/0__Get_AHN_tiles.py"),
    1: ("AHN processing", "scripts/1__AHN_processing.py"),
    2: ("Ground & Road fusion", "scripts/2__Ground_and_Road_fusion.py"),
    3: ("Extract 2D obstacles", "scripts/3__Extract_2D_obstacles.py"),
    4: ("Curb height estimation", "scripts/4__Height_estimation.py"),
}


async def _run_step(step_num: int, tilecodes: list[str]) -> bool:
    """Import and run a pipeline step."""
    label, script_path = STEPS[step_num]
    print(f"\n{'─' * 60}")
    print(f"  [{step_num}]  {label}")
    print(f"{'─' * 60}")

    t0 = time.time()
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            f"step_{step_num}", script_path
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        await mod.main(tilecodes)

        elapsed = time.time() - t0
        print(f"  ✓ {label}  ({elapsed:.0f}s)")
        return True
    except Exception as e:
        elapsed = time.time() - t0
        print(f"  ✗ {label}  FAILED after {elapsed:.0f}s")
        print(f"    {type(e).__name__}: {e}")
        return False


async def run_pipeline(
    tilecodes: list[str],
    steps: list[int],
    dry_run: bool = False,
) -> None:
    print("=" * 60)
    print("  Point-Cloud Labeling Pipeline")
    print("=" * 60)
    print(f"  Tilecodes: {tilecodes}")
    print(f"  Steps    : {[STEPS[s][0] for s in steps]}")
    print()

    if dry_run:
        print("  [DRY RUN] Would execute:")
        for s in steps:
            print(f"    {s}. {STEPS[s][0]}  ({STEPS[s][1]})")
        return

    t_start = time.time()
    for s in steps:
        ok = await _run_step(s, tilecodes)
        if not ok:
            print("\n  Stopping pipeline due to failure.")
            break

    total = time.time() - t_start
    print(f"\n{'=' * 60}")
    print(f"  Pipeline finished in {total:.0f}s")
    print("=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the point-cloud labeling pipeline.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples:
              uv run python run_pipeline.py
              uv run python run_pipeline.py --tilecodes 120300_489300
              uv run python run_pipeline.py --skip-download
              uv run python run_pipeline.py --only 2
        """),
    )
    parser.add_argument(
        "--tilecodes",
        nargs="+",
        default=None,
        help='Tilecodes to process (e.g. 120300_489300 120300_488900)',
    )
    parser.add_argument(
        "--only",
        nargs="+",
        type=int,
        default=None,
        help="Run only these step numbers (e.g. --only 0 1)",
    )
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Skip step 0 (AHN download). Use when tiles are already cached.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be executed without running anything.",
    )

    args = parser.parse_args()

    # Resolve tilecodes
    if args.tilecodes:
        tilecodes = args.tilecodes
    else:
        import config as cfg
        tilecodes = cfg.DEFAULT_TILECODES

    # Resolve steps
    if args.only is not None:
        steps = sorted(s for s in args.only if s in STEPS)
    elif args.skip_download:
        steps = [1, 2]
    else:
        steps = list(STEPS.keys())

    asyncio.run(run_pipeline(tilecodes, steps, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
