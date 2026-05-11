"""
1 — AHN Processing.

For each tilecode: build convex-hull polygon from the LAZ point cloud,
crop the intersecting AHN tiles, and generate ground/building surface grids.
"""
from __future__ import annotations

import asyncio

import geopandas as gpd
from shapely.geometry import MultiPolygon

import config as cfg
from src.utils import ahn_utils, las_utils


async def main(tilecodes: list[str]) -> None:
    cfg.ensure_folders()

    print(f"Processing tilecodes: {tilecodes}")

    # 1. Build convex hull polygons
    polygons: dict[str, object] = {}
    for tilecode in tilecodes:
        input_file = cfg.POINTCLOUD_DIR / f"{tilecode}.laz"
        try:
            poly = las_utils.build_convex_hull_polygon(input_file)
            polygons[tilecode] = poly
            print(f"  Polygon built for {tilecode}")
        except Exception as e:
            print(f"  Failed polygon for {tilecode}: {e}")

    if not polygons:
        print("No valid polygons to process.")
        return

    # 2. Save polygons as GeoJSON
    for key, poly in polygons.items():
        gdf_poly = gpd.GeoDataFrame(
            {"tilecode": [key]}, geometry=[poly], crs=cfg.CRS
        )
        gdf_poly.to_file(cfg.BBOX_DIR / f"bbox_{key}.geojson", driver="GeoJSON")

    # 3. Load AHN grid
    print("Loading AHN grid...")
    gdf_ahn = gpd.read_file(cfg.AHN_GRID_PATH)

    # 4. Crop AHN tiles per tilecode
    for tilecode, poly in polygons.items():
        gdf_poly = gpd.GeoDataFrame(geometry=[poly], crs=cfg.CRS)
        intersecting = gpd.sjoin(gdf_ahn, gdf_poly, predicate="intersects")
        relevant_tiles = intersecting["GT_AHNSUB"].unique().tolist()

        if not relevant_tiles:
            print(f"  No AHN tiles intersect with {tilecode}")
            continue

        geometries = poly.geoms if isinstance(poly, MultiPolygon) else [poly]
        for geom in geometries:
            for ahn_tile in relevant_tiles:
                output_file = cfg.AHN_SUBSET_DIR / f"ahn_{tilecode}.laz"
                try:
                    las_utils.crop_laz_with_polygon(
                        input_file=cfg.AHN_RAW_DIR / f"{ahn_tile}.LAZ",
                        output_file=output_file,
                        polygon=geom,
                    )
                except Exception as e:
                    print(f"  Failed cropping {tilecode} from {ahn_tile}: {e}")

        print(f"  Cropped AHN for {tilecode} using {len(relevant_tiles)} tiles")

    # 5. Process AHN subsets into surface grids
    for tilecode, poly in polygons.items():
        subset_file = cfg.AHN_SUBSET_DIR / f"ahn_{tilecode}.laz"
        if not subset_file.exists():
            print(f"  Missing subset file for {tilecode}")
            continue

        try:
            npz_file = ahn_utils.process_subset_laz_file(
                subset_file, poly,
                out_folder=str(cfg.AHN_OUTPUT_DIR),
                resolution=cfg.AHN_RESOLUTION,
            )
            print(f"  Surface grid saved for {tilecode}: {npz_file}")
        except Exception as e:
            print(f"  Failed processing {tilecode}: {e}")


if __name__ == "__main__":
    asyncio.run(main(cfg.DEFAULT_TILECODES))
