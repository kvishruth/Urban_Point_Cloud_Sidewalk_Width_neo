# Point-Cloud Labeling Pipeline

Labels urban point-cloud tiles with ground, building, and road classes using AHN5 surface grids and BGT road polygons, then extracts 2D obstacle footprints and estimates curb heights along sidewalk boundaries.

## Setup

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh          # macOS / Linux
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"  # Windows

# Clone and install
git clone https://github.com/<your-org>/pointcloud-labeling.git
cd pointcloud-labeling
uv sync
uv run python setup_paths.py
```

## Data

Place input files in `data/` (git-ignored). The pipeline expects this layout:

```
data/
├── input/
│   ├── pointcloud/raw/                ← Your LAZ tiles go here
│   │   ├── 120300_489300.laz
│   │   └── 120300_488900.laz
│   ├── ahn/
│   │   └── ahn_units_shapefile/
│   │       └── AHN_subunits_GeoTiles.shp   ← AHN grid index
└── output/                            ← Created automatically
    ├── ahn/                           ← Surface grids (.npz)
    ├── labeled_pointcloud/            ← Labeled LAZ files
    ├── obstacles/                     ← Obstacle polygons (.geojson)
    └── curb_heights/                  ← Curb height segments (.geojson)
```

Tile filenames must follow the `{x}_{y}.laz` pattern (e.g. `120300_489300.laz`).

## Run

```bash
# Full pipeline with default tilecodes (from config.py)
uv run python run_pipeline.py

# Custom tilecodes
uv run python run_pipeline.py --tilecodes 120300_489300 120300_488900

# Skip AHN download (tiles already cached)
uv run python run_pipeline.py --skip-download

# Run only specific steps
uv run python run_pipeline.py --only 1 2
uv run python run_pipeline.py --only 3 4

# Preview what would run
uv run python run_pipeline.py --dry-run
```

Or run individual steps directly:

```bash
uv run python scripts/0__Get_AHN_tiles.py
uv run python scripts/3__Extract_2D_obstacles.py
```

## Pipeline

| # | Script | Input | Output |
|---|--------|-------|--------|
| 0 | `Get_AHN_tiles` | Tilecodes + AHN grid index | Downloaded AHN5 `.LAZ` tiles |
| 1 | `AHN_processing` | Point clouds + AHN tiles | Cropped subsets, ground/building surface grids (`.npz`) |
| 2 | `Ground_and_Road_fusion` | Surface grids + BGT road CSVs | Labeled point clouds (ground / building / road) |
| 3 | `Extract_2D_obstacles` | Labeled point clouds | Obstacle footprint polygons (`.geojson`) |
| 4 | `Height_estimation` | Labeled point clouds + BGT sidewalk CSVs | Curb height segments (`.geojson`) |

## Configuration

Edit `config.py` to change input paths, tilecodes, or processing parameters:

```python
# Input data
POINTCLOUD_DIR = PROJECT_ROOT / "data" / "input" / "pointcloud" / "raw"
BGT_DIR = PROJECT_ROOT / "data" / "input" / "bgt"

# Tilecodes to process
DEFAULT_TILECODES = ["120300_489300", "120300_488900"]

# Processing thresholds
AHN_GROUND_EPSILON = 0.2       # Height tolerance for ground classification
OBSTACLE_MAX_AREA = 10.0       # m² — drop obstacles larger than this
CURB_SAMPLE_DELTA = 1.0        # m — spacing between curb sample points
CURB_MIN_HEIGHT = 0.05         # m — curbs below this are "accessible"
```

## Project structure

```
├── config.py              # All paths, parameters, tilecodes
├── run_pipeline.py        # CLI runner (--tilecodes, --only, --skip-download)
├── pyproject.toml         # Dependencies (uv)
├── setup_paths.py         # One-time venv path setup
├── Dockerfile
├── .gitignore
├── scripts/               # Pipeline steps (0–4)
│   ├── 0__Get_AHN_tiles.py
│   ├── 1__AHN_processing.py
│   ├── 2__Ground_and_Road_fusion.py
│   ├── 3__Extract_2D_obstacles.py
│   └── 4__Height_estimation.py
├── src/utils/             # Reusable modules
│   ├── ahn_fuser.py       #   AHN surface → point label fusion
│   ├── ahn_utils.py       #   Surface grid interpolation
│   ├── analysis_tools.py  #   Label statistics
│   ├── bgt_fuser.py       #   BGT polygon → road label fusion
│   ├── clipping_tools.py  #   Polygon clipping (numba-accelerated)
│   ├── curb_utils.py      #   Curb height calculation
│   ├── get_ahn_tiles.py   #   Async AHN tile downloader
│   ├── labels.py          #   Label code constants
│   ├── las_utils.py       #   LAS/LAZ read/write/crop
│   ├── obstacles_utils.py #   Voxel clustering + concave hulls
│   └── pipeline.py        #   Sequential data-fusion pipeline
|   └── bgt_utils.py       #   PDOK bgt data download
└── data/                  # Git-ignored
```

## Docker

```bash
docker build -t pointcloud-labeling .
docker run -v $(pwd)/data:/app/data pointcloud-labeling \
    python run_pipeline.py --tilecodes 120300_489300
```
