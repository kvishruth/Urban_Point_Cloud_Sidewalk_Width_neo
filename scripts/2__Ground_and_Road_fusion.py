"""
2 — Ground and Road Fusion.

Labels point-cloud tiles with ground, building, and road classes using
AHN surface grids and BGT road polygons.
"""
from __future__ import annotations

import asyncio

import geopandas as gpd
import pandas as pd
from shapely import wkt

import config as cfg
from src.utils import ahn_fuser, bgt_fuser, labels as Labels, pipeline as Pipeline


def process_tilecodes(tilecodes: list[str]) -> None:
    cfg.ensure_folders()

    # Load BGT layers
    dfs = []
    for layer in cfg.BGT_ROAD_LAYERS:
        csv_path = cfg.BGT_DIR / f"{layer}.csv"
        if csv_path.exists():
            dfs.append(
                pd.read_csv(csv_path, sep=";", usecols=["bgt-functie", "geometrie"])
            )
        else:
            print(f"  WARNING: {csv_path} not found, skipping")

    if not dfs:
        raise FileNotFoundError(f"No BGT CSV files found in {cfg.BGT_DIR}")

    df_bgt = pd.concat(dfs, ignore_index=True).rename(columns={"geometrie": "geometry"})
    df_bgt["geometry"] = df_bgt["geometry"].apply(wkt.loads)
    gdf_bgt = gpd.GeoDataFrame(df_bgt, geometry="geometry", crs=cfg.CRS)

    # Load bbox polygons and subset BGT per tilecode
    bbox_dfs = []
    for tilecode in tilecodes:
        bbox_file = cfg.BBOX_DIR / f"bbox_{tilecode}.geojson"
        if bbox_file.exists():
            bbox_dfs.append(gpd.read_file(bbox_file))
        else:
            print(f"  WARNING: {bbox_file} not found")

    if not bbox_dfs:
        raise FileNotFoundError("No bbox polygon files found. Run step 1 first.")

    bbox_polygons = pd.concat(bbox_dfs, ignore_index=True)
    gdf_bgt_tiles = {}
    for tilecode in tilecodes:
        bbox = bbox_polygons[bbox_polygons["tilecode"] == tilecode]
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
