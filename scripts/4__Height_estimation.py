"""
4 — Curb Height Estimation.

Estimates curb heights along sidewalk boundaries by comparing road
and ground point-cloud heights on either side of each boundary segment.
"""
from __future__ import annotations

import asyncio

import geopandas as gpd
import pandas as pd
import shapely
from shapely.ops import unary_union
from tqdm import tqdm

import config as cfg
from src.utils import curb_utils, las_utils


def process_tilecodes(tilecodes: list[str]) -> None:
    cfg.ensure_folders()

    # Load BGT sidewalk + parking layers
    dfs = []
    for layer in cfg.BGT_SIDEWALK_LAYERS:
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
    df_bgt["geometry"] = df_bgt["geometry"].apply(shapely.wkt.loads)
    gdf_bgt = gpd.GeoDataFrame(df_bgt, geometry="geometry", crs=cfg.CRS)

    # Build per-tile data
    tiles: dict[str, dict] = {}
    for tilecode in tilecodes:
        pc_file = cfg.LABELED_PC_DIR / f"road_ground_labeled_{tilecode}.laz"
        bbox_file = cfg.BBOX_DIR / f"bbox_{tilecode}.geojson"

        if not pc_file.exists():
            print(f"  Skipping {tilecode}: no labeled point cloud")
            continue
        if not bbox_file.exists():
            print(f"  Skipping {tilecode}: no bbox polygon")
            continue

        bbox = gpd.read_file(bbox_file)
        tile_polygon = bbox.geometry.iloc[0]
        bgt_in_tile = gpd.sjoin(gdf_bgt, bbox, how="inner", predicate="intersects")

        sw_geoms = bgt_in_tile.loc[
            bgt_in_tile["bgt-functie"] == "voetpad", "geometry"
        ].tolist()
        pkv_geoms = bgt_in_tile.loc[
            bgt_in_tile["bgt-functie"] == "parkeervlak", "geometry"
        ].tolist()

        tiles[tilecode] = {
            "pc_file": str(pc_file),
            "tile_polygon": tile_polygon,
            "sw_geoms": sw_geoms,
            "pkv_geoms": pkv_geoms,
        }

    # Compute boundary lines per tile
    for tilecode, t in tiles.items():
        if not t["sw_geoms"]:
            t["crossing_lines"] = None
            continue

        sidewalks_merged = unary_union(t["sw_geoms"])
        boundary = sidewalks_merged.intersection(t["tile_polygon"]).boundary
        lines_in_tile = boundary.intersection(t["tile_polygon"].buffer(-0.5))

        if t["pkv_geoms"]:
            parking_union = unary_union(t["pkv_geoms"])
            lines_in_tile = lines_in_tile.difference(parking_union)

        t["crossing_lines"] = lines_in_tile

    # Estimate curb heights
    results: list[dict] = []

    for tilecode, t in tqdm(tiles.items(), desc="Processing tiles"):
        crossing_lines = t.get("crossing_lines")
        if crossing_lines is None or crossing_lines.is_empty:
            print(f"  {tilecode}: no boundary lines, skipping")
            continue

        if crossing_lines.geom_type == "LineString":
            lines = [crossing_lines]
        elif crossing_lines.geom_type == "MultiLineString":
            lines = list(crossing_lines.geoms)
        else:
            print(f"  {tilecode}: unexpected geometry {crossing_lines.geom_type}")
            continue

        try:
            points, labels = las_utils.read_las_with_labels(t["pc_file"])
        except Exception as e:
            print(f"  {tilecode}: failed to read point cloud — {e}")
            continue

        for line in lines:
            if line.length == 0:
                continue

            sample_pts = curb_utils.get_points_on_line(line, cfg.CURB_SAMPLE_DELTA)
            segments = curb_utils.split_line_by_points(line, sample_pts)

            for seg in segments:
                if seg.length < cfg.CURB_BUFFER_WIDTH:
                    continue

                poly_outer = seg.buffer(cfg.CURB_BUFFER_WIDTH, single_sided=True)
                poly_inner = seg.buffer(-cfg.CURB_BUFFER_WIDTH, single_sided=True)
                poly_union = unary_union([poly_outer, poly_inner])

                if poly_union.is_empty or poly_union.geom_type not in (
                    "Polygon", "MultiPolygon"
                ):
                    continue

                try:
                    curb_height, available = curb_utils.calculate_curb_height(
                        points, labels, poly_union, cfg.CURB_MIN_POINTS
                    )
                except Exception as e:
                    print(f"  {tilecode} segment failed: {e}")
                    continue

                results.append({
                    "tilecode": tilecode,
                    "geometry": seg,
                    "line_segm_polygon": poly_union.wkt,
                    "overarching_line_segm": line.wkt,
                    "curb_height": curb_height,
                })

    # Save results
    if results:
        gdf_results = gpd.GeoDataFrame(results, geometry="geometry", crs=cfg.CRS)
        for tilecode in tilecodes:
            subset = gdf_results[gdf_results["tilecode"] == tilecode]
            if not subset.empty:
                out_file = cfg.CURB_HEIGHTS_DIR / f"curb_height_{tilecode}.geojson"
                subset.to_file(out_file, driver="GeoJSON")
                print(f"  Saved: {out_file} ({len(subset)} segments)")
    else:
        print("  No curb height results produced.")

    print("Curb height estimation complete.")


async def main(tilecodes: list[str]) -> None:
    process_tilecodes(tilecodes)


if __name__ == "__main__":
    asyncio.run(main(cfg.DEFAULT_TILECODES))
