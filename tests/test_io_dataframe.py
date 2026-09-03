import os
import pandas as pd
import geopandas as gpd
import pytest
from m4i.utils.io.io_dataframe import IO_DataFrame
import warnings, logging


@pytest.mark.parametrize("ext", ["geoparquet", "parquet"])
def test_io_dataframe_export_import(tmp_path, ext):
    df = pd.DataFrame(
        {
            "source": [1, 2, 3, 4],
            "target": [5, 6, 7, 8],
            "t": [1, 2, 1, 2],
            "geometry": ["Point(1 1)", "Point(2 2)", "Point(3 3)", "Point(4 4)"],
            "tot_cost": [10, 20, 30, 40],
        }
    )
    df2 = pd.DataFrame(
        {
            "source": [11, 12, 13, 14],
            "target": [5, 6, 7, 8],
            "t": [1, 3, 1, 3],
            "geometry": ["Point(1 1)", "Point(2 2)", "Point(3 3)", "Point(4 4)"],
            "tot_cost": [10, 20, 30, 40],
        }
    )
    df3 = pd.DataFrame(
        {
            "source": [21, 22, 23, 24],
            "target": [5, 6, 7, 8],
            "t": [1, 3, 1, 4],
            "geometry": ["Point(1 1)", "Point(2 2)", "Point(3 3)", "Point(4 4)"],
            "tot_cost": [10, 20, 30, 40],
        }
    )
    io = IO_DataFrame()

    gdf = df.copy()
    gdf["geometry"] = gpd.GeoSeries.from_wkt(gdf["geometry"])
    gdf = gpd.GeoDataFrame(gdf, geometry="geometry", crs="EPSG:4326")

    gdf2 = df3.copy()
    gdf2["geometry"] = gpd.GeoSeries.from_wkt(gdf2["geometry"])
    gdf2 = gpd.GeoDataFrame(gdf2, geometry="geometry", crs="EPSG:4326")

    folder = tmp_path / "test_folder"
    warnings.warn(str(folder))
    folder.mkdir()
    file1 = f"test1.{ext}"
    filename = folder / file1
    IO_DataFrame.remove_path(str(folder))
    io.export_dataframe(
        gdf,
        path=str(filename),
        mode="w",
        partitionby=None,
        template="{filename}-{partition}-{i}",
        index=False,
    )
    assert os.path.exists(filename), "Export failed"
    assert os.path.getsize(filename) > 0, "Export failed"
    assert os.path.isfile(filename), "Export failed"
    io.export_dataframe(
        gdf2,
        path=str(filename),
        mode="a",
        partitionby=None,
        template="{filename}-{partition}-{i}",
        index=False,
    )
    assert os.path.exists(filename), "Export failed"
    assert os.path.isdir(filename), "Export failed"
    tmp = io.import_dataframe(str(filename))
    assert not tmp.empty, "Import failed"
