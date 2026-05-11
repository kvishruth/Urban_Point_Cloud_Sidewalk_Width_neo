"""
2 — Ground and Road Fusion.

Labels point-cloud tiles with ground, building, and road classes using
AHN surface grids and BGT road polygons.
"""
from __future__ import annotations

import asyncio

import geopandas as gpd

import config as cfg
from src.utils import ahn_fuser, bgt_fuser, bgt_utils, labels as Labels, pipeline as Pipeline


def process_tilecodes(tilecodes: list[str]) -> None:
    cfg.ensure_folders()

    # Load BGT road polygons (downloads from PDOK on first run, then cached)
    gdf_bgt = bgt_utils.load_bgt(tilecodes, functie_filter=cfg.BGT_ROAD_LAYERS)
    if gdf_bgt.empty:
        raise RuntimeError("No BGT road features found for the given tilecodes.")

    # Subset BGT per tilecode
    gdf_bgt_tiles = {}
    for tilecode in tilecodes:
        bbox_file = cfg.BBOX_DIR / f"bbox_{tilecode}.geojson"
        if not bbox_file.exists():
            print(f"  WARNING: {bbox_file} not found")
            continue
        bbox = gpd.read_file(bbox_file)
        gdf_bgt_tiles[tilecode] = gpd.sjoin(
            gdf_bgt, bbox, how="inner", predicate="intersects"
        )

    # Process each tilecode
    for tilecode in tilecodes:
        print(f"\nProcessing {tilecode}...")

        npz_path = str(cfg.AHN_OUTPUT_DIR / f"ahn_{tilecode}.npz")

        ground_fuser = ahn_fuser.NPZAHNFuser(
            label=Labels.Labels.GROUND,
            npz_reader=npz_path,
            target="ground",
            epsilon=cfg.AHN_GROUND_EPSILON,
            grid_size=cfg.AHN_GROUND_GRID_SIZE,
            min_comp_size=cfg.AHN_GROUND_MIN_COMP,
        )

        building_fuser = ahn_fuser.NPZAHNFuser(
            label=Labels.Labels.BUILDING,
            npz_reader=npz_path,
            target="building",
            epsilon=cfg.AHN_BUILDING_EPSILON,
        )

        road_fuser = bgt_fuser.BGTRoadFuser(
            label=Labels.Labels.ROAD,
            bgt_gdf=gdf_bgt_tiles[tilecode],
            bgt_types=None,
            offset=0,
        )

        pipe = Pipeline.Pipeline(
            processors=(ground_fuser, building_fuser, road_fuser),
            caching=False,
        )

        in_file = str(cfg.POINTCLOUD_DIR / f"{tilecode}.laz")
        out_file = str(cfg.LABELED_PC_DIR / f"road_ground_labeled_{tilecode}.laz")
        pipe.process_file(in_file, out_file=out_file)
        print(f"  Saved: {out_file}")


async def main(tilecodes: list[str]) -> None:
    process_tilecodes(tilecodes)


if __name__ == "__main__":
    asyncio.run(main(cfg.DEFAULT_TILECODES))
