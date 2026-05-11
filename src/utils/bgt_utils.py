"""
bgt_utils.py — Download BGT surface data from the PDOK API.

Replaces manual CSV loading with the same PDOK download API used
in the pedestrian-network pipeline. Downloads wegdeel features
for the area covered by tilecode bbox polygons, caches the result,
and provides a single ``load_bgt()`` entry point for scripts.

Usage
-----
    from src.utils import bgt_utils

    # In step 2 (road fusion)
    gdf_bgt = bgt_utils.load_bgt(tilecodes, functie_filter=cfg.BGT_ROAD_LAYERS)

    # In step 4 (curb heights)
    gdf_bgt = bgt_utils.load_bgt(tilecodes, functie_filter=cfg.BGT_SIDEWALK_LAYERS)
"""
from __future__ import annotations

import io
import json
import time
import zipfile
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests
from shapely.ops import unary_union

import config as cfg

# ── PDOK BGT download API ────────────────────────────────────────────────────

_BGT_DOWNLOAD_API = "https://api.pdok.nl/lv/bgt/download/v1_0"
_BGT_FEATURETYPES = ["wegdeel"]


# ── Core download functions ──────────────────────────────────────────────────


def _build_area_polygon(tilecodes: list[str]) -> gpd.GeoDataFrame:
    """Build a single dissolved polygon from tilecode bbox GeoJSONs."""
    bbox_dfs = []
    for tilecode in tilecodes:
        bbox_file = cfg.BBOX_DIR / f"bbox_{tilecode}.geojson"
        if bbox_file.exists():
            bbox_dfs.append(gpd.read_file(bbox_file))
        else:
            print(f"  WARNING: {bbox_file} not found")

    if not bbox_dfs:
        raise FileNotFoundError(
            f"No bbox polygon files found in {cfg.BBOX_DIR}. "
            f"Run step 1 (AHN processing) first."
        )

    combined = pd.concat(bbox_dfs, ignore_index=True)
    dissolved = gpd.GeoDataFrame(
        geometry=[unary_union(combined.geometry)], crs=cfg.CRS
    )
    return dissolved


def download_bgt(
    area_gdf: gpd.GeoDataFrame,
    featuretypes: list[str] | None = None,
    *,
    poll_interval: float = 2.0,
) -> io.BytesIO:
    """Request a custom BGT download from PDOK, poll until ready, return ZIP.

    Parameters
    ----------
    area_gdf
        GeoDataFrame (in RD New / EPSG:28992) whose first geometry
        is used as the spatial filter.
    featuretypes
        BGT layer names to request.  Defaults to ``["wegdeel"]``.
    poll_interval
        Seconds between status polls.

    Returns
    -------
    io.BytesIO — in-memory ZIP archive containing GML files.
    """
    ftypes = featuretypes or _BGT_FEATURETYPES
    geofilter_wkt = area_gdf.geometry.iloc[0].wkt

    print(f"Requesting BGT download ({ftypes}, WKT {len(geofilter_wkt)} chars)...")
    payload = {
        "featuretypes": ftypes,
        "format": "gmllight",
        "geofilter": geofilter_wkt,
    }
    r = requests.post(
        f"{_BGT_DOWNLOAD_API}/full/custom",
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        data=json.dumps(payload),
    )
    if r.status_code != 202:
        raise RuntimeError(f"BGT download request failed ({r.status_code}): {r.text}")

    status_url = f"https://api.pdok.nl{r.json()['_links']['status']['href']}"
    print(f"  Polling: {status_url}")

    while True:
        status_obj = requests.get(status_url).json()
        status = status_obj["status"]
        print(f"  status={status}  progress={status_obj.get('progress', '?')}")
        if status == "COMPLETED":
            download_url = (
                f"https://api.pdok.nl{status_obj['_links']['download']['href']}"
            )
            break
        if status in ("ERROR", "FAILED"):
            raise RuntimeError(f"BGT download failed: {status_obj}")
        time.sleep(poll_interval)

    print(f"Downloading...")
    r = requests.get(download_url)
    r.raise_for_status()
    return io.BytesIO(r.content)


def read_bgt_from_zip(
    zip_bytes: io.BytesIO,
    crs: str = "EPSG:28992",
) -> gpd.GeoDataFrame:
    """Read wegdeel GML from a BGT ZIP and return a GeoDataFrame."""
    gdfs = []
    with zipfile.ZipFile(zip_bytes) as z:
        for gml_file in z.namelist():
            if not gml_file.endswith(".gml"):
                continue
            layer_name = (
                gml_file.replace(".gml", "")
                .replace("bgt_", "")
                .split("/")[-1]
            )
            if layer_name not in _BGT_FEATURETYPES:
                continue
            try:
                gdf = gpd.read_file(io.BytesIO(z.read(gml_file))).set_crs(crs)
                gdfs.append(gdf)
                print(f"  {layer_name}: {len(gdf):,} features")
            except Exception as exc:
                print(f"  {layer_name}: failed ({exc})")

    if not gdfs:
        return gpd.GeoDataFrame(columns=["geometry", "bgt-functie"], crs=crs)
    return pd.concat(gdfs, ignore_index=True)


# ── Cache path ───────────────────────────────────────────────────────────────


def _cache_path() -> Path:
    return cfg.BGT_DIR / "bgt_wegdeel_cached.gpkg"


# ── Public API ───────────────────────────────────────────────────────────────


def load_bgt(
    tilecodes: list[str],
    *,
    functie_filter: list[str] | None = None,
    use_cache: bool = True,
) -> gpd.GeoDataFrame:
    """Load BGT wegdeel data for the given tilecodes.

    Downloads from PDOK on first call, caches to disk. Subsequent calls
    read from cache. Optionally filters by ``bgt-functie`` values.

    Parameters
    ----------
    tilecodes
        List of tilecodes whose bbox polygons define the download area.
    functie_filter
        List of BGT functie names to keep (e.g. ``cfg.BGT_ROAD_LAYERS``).
        The filter names can be either full layer names like
        ``"BGT_WGL_rijbaan_lokale_weg"`` or just the functie value like
        ``"rijbaan lokale weg"`` — both are handled.
    use_cache
        If True, read from disk cache when available.

    Returns
    -------
    GeoDataFrame with ``geometry`` and ``bgt-functie`` columns.
    """
    cache = _cache_path()

    if use_cache and cache.exists():
        print(f"Loading BGT from cache: {cache}")
        gdf_bgt = gpd.read_file(cache)
    else:
        area_gdf = _build_area_polygon(tilecodes)
        zip_bytes = download_bgt(area_gdf)
        gdf_bgt = read_bgt_from_zip(zip_bytes)

        if not gdf_bgt.empty:
            cache.parent.mkdir(parents=True, exist_ok=True)
            gdf_bgt.to_file(cache, driver="GPKG")
            print(f"  Cached: {cache}")

    if gdf_bgt.empty:
        print("  WARNING: No BGT features downloaded")
        return gdf_bgt

    # Apply functie filter
    if functie_filter and "bgt-functie" in gdf_bgt.columns:
        # Normalize filter: "BGT_WGL_rijbaan_lokale_weg" → "rijbaan lokale weg"
        normalized = set()
        for f in functie_filter:
            clean = f.replace("BGT_WGL_", "").replace("_", " ").replace("-", " ")
            # Also keep the original in case it matches directly
            normalized.add(clean)
            normalized.add(f)
            # Handle bgt-functie values like "OV-baan", "fietspad", "voetpad"
            if f.startswith("BGT_WGL_"):
                normalized.add(f[8:])  # strip prefix

        gdf_bgt = gdf_bgt[
            gdf_bgt["bgt-functie"].isin(normalized)
        ].copy()
        print(f"  Filtered to {len(gdf_bgt):,} features")

    return gdf_bgt
