"""
3 — Extract 2D Obstacles.

Clusters above-ground points from labeled point clouds into obstacle
polygons using voxelization + connected components + concave hulls.
"""
from __future__ import annotations

import asyncio

import config as cfg
from src.utils import obstacles_utils


def process_tilecodes(tilecodes: list[str]) -> None:
    cfg.ensure_folders()

    for tilecode in tilecodes:
        laz_file = cfg.LABELED_PC_DIR / f"road_ground_labeled_{tilecode}.laz"
        if not laz_file.exists():
            print(f"  WARNING: {laz_file} not found, skipping")
            continue

        clusters = obstacles_utils.cluster_obstacles(str(laz_file))
        print(f"  {tilecode}: {len(clusters)} obstacle clusters")

        gdf = obstacles_utils.clusters_to_concave_polygons(clusters, cfg.CRS)
        gdf["tilecode"] = tilecode
        gdf["area"] = gdf.geometry.area
        gdf = gdf[gdf["area"] < cfg.OBSTACLE_MAX_AREA]

        out_file = cfg.OBSTACLES_DIR / f"obstacles_{tilecode}.geojson"
        gdf.to_file(out_file, driver="GeoJSON")
        print(f"  Saved: {out_file} ({len(gdf)} polygons)")


async def main(tilecodes: list[str]) -> None:
    process_tilecodes(tilecodes)


if __name__ == "__main__":
    asyncio.run(main(cfg.DEFAULT_TILECODES))
