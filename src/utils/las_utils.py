import re
import laspy
import numpy as np

from scipy.spatial import ConvexHull
from shapely.geometry import Polygon
from shapely.prepared import prep
from pathlib import Path

def get_tilecode_from_filename(filename):
    """Extract the tile code from a file name."""
    return re.match(r'.*(\d{6}_\d{6}).*', filename)[1]

def read_las(las_file):
    """Read a las file and return the las object."""
    return laspy.read(las_file)

def read_las_with_labels(las_path):
    """
    Read LAS file and extract point coordinates and labels.

    Parameters:
    - las_path (str): Path to the LAS file.

    Returns:
    Tuple of NumPy arrays (points, labels).
    """
    pointcloud = laspy.read(las_path)

    if 'label' not in pointcloud.point_format.extra_dimension_names:
        labels = np.zeros((len(pointcloud.x),), dtype='uint16')
    else:
        labels = pointcloud.label
    
    x = (np.array(pointcloud.x))
    y = (np.array(pointcloud.y))
    z = (np.array(pointcloud.z))
    points = np.vstack((x, y, z)).T

    return points, labels

def label_and_save_las(las, labels, outfile):
    """Label a las file using the provided class labels and save to outfile."""
    assert len(labels) == las.header.point_count
    if 'label' not in las.point_format.extra_dimension_names:
        las.add_extra_dim(laspy.ExtraBytesParams(name="label", type="uint8",
                          description="Labels"))
    las.label = labels
    las.write(outfile)

def crop_laz_with_polygon(input_file: Path, output_file: Path, polygon: Polygon):
    """
    Crop LAZ file by Shapely polygon using laspy.
    Preserves attributes and header metadata.
    """
    if polygon.is_empty:
        raise ValueError("Polygon is empty.")

    if not polygon.is_valid:
        polygon = polygon.buffer(0)

    output_file.parent.mkdir(parents=True, exist_ok=True)

    las = laspy.read(input_file)
    prepared = prep(polygon)

    # Vectorized bounding-box pre-filter
    x, y = np.array(las.x), np.array(las.y)
    xmin, ymin, xmax, ymax = polygon.bounds
    bbox_mask = (x >= xmin) & (x <= xmax) & (y >= ymin) & (y <= ymax)

    # Fine filter with prepared polygon (only on bbox candidates)
    candidates = np.where(bbox_mask)[0]
    from shapely.geometry import Point
    inside = np.array([
        prepared.contains(Point(x[i], y[i]))
        for i in candidates
    ]) if len(candidates) > 0 else np.array([], dtype=bool)

    final_mask = np.zeros(len(las.points), dtype=bool)
    if len(candidates) > 0:
        final_mask[candidates[inside]] = True

    las.points = las.points[final_mask]

    if len(las.points) == 0:
        print(f"Warning: No points written to {output_file}")

    las.write(output_file)
    return int(final_mask.sum())

def build_convex_hull_polygon(las_path: Path) -> Polygon:
    """
    Reads a LAS/LAZ file and returns a Shapely Polygon
    representing the convex hull of its XY coordinates.
    """
    if not las_path.exists():
        raise FileNotFoundError(f"File not found: {las_path}")

    # Read point cloud
    with laspy.open(las_path) as reader:
        las = reader.read()

    # Extract XY only (avoid unnecessary Z in memory)
    coords = np.column_stack((las.x, las.y))

    if coords.shape[0] < 3:
        raise ValueError(f"Not enough points to compute convex hull: {las_path}")

    # Compute convex hull
    hull = ConvexHull(coords)

    # Build polygon from hull vertices
    polygon = Polygon(coords[hull.vertices])

    if not polygon.is_valid:
        polygon = polygon.buffer(0)  # Fix minor geometry issues

    return polygon
