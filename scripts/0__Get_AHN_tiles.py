"""
0 — Download AHN tiles for the given tilecodes.

Spatially joins tilecode centroids with the AHN grid to determine
which AHN sub-unit tiles to download, then fetches them asynchronously.
"""
from __future__ import annotations

import asyncio

import geopandas as gpd
from shapely.geometry import Point

import config as cfg
from src.utils import get_ahn_tiles


async def main(tilecodes: list[str]) -> None:
    cfg.ensure_folders()

    gdf_ahn = gpd.read_file(cfg.AHN_GRID_PATH)

    ahn_tiles: list[str] = []
    for tilecode in tilecodes:
        x, y = map(float, tilecode.split("_"))
        gdf_tile = gpd.GeoDataFrame(
            {"tilecode": [tilecode]},
            geometry=[Point(x, y)],
            crs=cfg.CRS,
        )
        joined = gpd.sjoin(gdf_tile, gdf_ahn)
        ahn_tiles.extend(joined["GT_AHNSUB"].unique().tolist())

    ahn_tiles = list(set(ahn_tiles))
    print(f"AHN tiles to download: {len(ahn_tiles)}")

    await get_ahn_tiles.download_all_tiles(
        ahn_tiles,
        str(cfg.AHN_RAW_DIR),
        cfg.AHN_DOWNLOAD_URL,
    )


if __name__ == "__main__":
    asyncio.run(main(cfg.DEFAULT_TILECODES))
