"""
config.py — Central configuration for the point-cloud labeling pipeline.

All scripts import from here instead of defining their own paths.
Edit POINTCLOUD_DIR and tilecodes to process different datasets.
"""
from __future__ import annotations

from pathlib import Path

# =============================================================================
# Project root (where this file lives)
# =============================================================================

PROJECT_ROOT = Path(__file__).resolve().parent

# =============================================================================
# Input data directories
# =============================================================================

# Point cloud LAZ files (one per tilecode, e.g. 120300_489300.laz)
POINTCLOUD_DIR = PROJECT_ROOT / "data" / "input" / "pointcloud" / "raw"

# AHN grid shapefile
AHN_GRID_PATH = PROJECT_ROOT / "data" / "input" / "ahn" / "ahn_units_shapefile" / "AHN_subunits_GeoTiles.shp"

# AHN download URL template ({code} is replaced by tile code)
AHN_DOWNLOAD_URL = "https://geotiles.citg.tudelft.nl/AHN5_T/{code}.LAZ"

# BGT CSV layers
BGT_DIR = PROJECT_ROOT / "data" / "input" / "bgt"

# =============================================================================
# Output directories
# =============================================================================

AHN_RAW_DIR = PROJECT_ROOT / "data" / "input" / "ahn"
AHN_SUBSET_DIR = PROJECT_ROOT / "data" / "input" / "ahn" / "ahn_subsets"
AHN_OUTPUT_DIR = PROJECT_ROOT / "data" / "output" / "ahn"
BBOX_DIR = PROJECT_ROOT / "data" / "input" / "bbox_polygons"
LABELED_PC_DIR = PROJECT_ROOT / "data" / "output" / "labeled_pointcloud"

# =============================================================================
# Processing parameters
# =============================================================================

CRS = "EPSG:28992"
AHN_RESOLUTION = 0.1

# AHN fuser
AHN_GROUND_EPSILON = 0.2
AHN_GROUND_GRID_SIZE = 0.4
AHN_GROUND_MIN_COMP = 50
AHN_BUILDING_EPSILON = 0.2

# BGT road layers
BGT_ROAD_LAYERS = [
    "BGT_WGL_rijbaan_lokale_weg",
    "BGT_WGL_rijbaan_regionale_weg",
    "BGT_WGL_rijbaan_autoweg",
    "BGT_WGL_rijbaan_autosnelweg",
    "BGT_WGL_parkeervlak",
    "BGT_WGL_ov-baan",
    "BGT_WGL_fietspad",
]

# =============================================================================
# Default tilecodes (override via CLI or in scripts)
# =============================================================================

DEFAULT_TILECODES = [
    "120300_489300",
    "120300_488900",
]

# =============================================================================
# Step 3 — Obstacles
# =============================================================================

OBSTACLES_DIR = PROJECT_ROOT / "data" / "output" / "obstacles"
OBSTACLE_MAX_AREA = 10.0  # m² — filter out large objects

# =============================================================================
# Step 4 — Curb height estimation
# =============================================================================

CURB_HEIGHTS_DIR = PROJECT_ROOT / "data" / "output" / "curb_heights"

BGT_SIDEWALK_LAYERS = [
    "BGT_WGL_voetpad",
    "BGT_WGL_parkeervlak",
]

CURB_SAMPLE_DELTA = 1.0        # m — spacing between sample points on boundary lines
CURB_BUFFER_WIDTH = 0.5        # m — buffer around line segments for point selection
CURB_MIN_POINTS = 5            # minimum points needed for height calculation
CURB_MIN_HEIGHT = 0.05         # m — threshold for accessible curb


# =============================================================================
# Helpers
# =============================================================================

def ensure_folders() -> None:
    """Create all output directories if they don't exist."""
    for folder in (
        AHN_RAW_DIR, AHN_SUBSET_DIR, AHN_OUTPUT_DIR,
        BBOX_DIR, LABELED_PC_DIR,
        OBSTACLES_DIR, CURB_HEIGHTS_DIR,
    ):
        folder.mkdir(parents=True, exist_ok=True)
