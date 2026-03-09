import copy
import dataclasses
from m4i.utils.io.io_dataframe import IO_DataFrame
import pandas as pd
import geopandas as gpd
import os


df = pd.DataFrame({
    "source": [1,2,3,4],
    "target": [5,6,7,8],
    "t": [1,2,1,2],
    "geometry": ['Point(1 1)', 'Point(2 2)', 'Point(3 3)', 'Point(4 4)'],
    "tot_cost": [10, 20, 30, 40],
})
df2 = pd.DataFrame({
    "source": [11,12,13,14],
    "target": [5,6,7,8],
    "t": [1,3,1,3],
    "geometry": ['Point(1 1)', 'Point(2 2)', 'Point(3 3)', 'Point(4 4)'],
    "tot_cost": [10, 20, 30, 40],
})
df3 = pd.DataFrame({
    "source": [21,22,23,24],
    "target": [5,6,7,8],
    "t": [1,3,1,4],
    "geometry": ['Point(1 1)', 'Point(2 2)', 'Point(3 3)', 'Point(4 4)'],
    "tot_cost": [10, 20, 30, 40],
})
io = IO_DataFrame()

gdf=df.copy()
gdf['geometry'] = gpd.GeoSeries.from_wkt(gdf['geometry'])
gdf=gpd.GeoDataFrame(gdf, geometry='geometry', crs="EPSG:4326")

gdf1=df2.copy()
gdf1['geometry'] = gpd.GeoSeries.from_wkt(gdf1['geometry'])
gdf1=gpd.GeoDataFrame(gdf1, geometry='geometry', crs="EPSG:4326")

gdf2=df3.copy()
gdf2['geometry'] = gpd.GeoSeries.from_wkt(gdf2['geometry'])
gdf2=gpd.GeoDataFrame(gdf2, geometry='geometry', crs="EPSG:4326")

folder = "test_folder"

file1 = "test1.geoparquet"
filename = os.path.join(folder, file1)
IO_DataFrame.remove_path(folder)
io.export_dataframe(gdf, path=filename, mode="w", partitionby=None, template="{filename}-{partition}-{i}", index=False)
assert os.path.exists(filename), f"Export failed ({file1})" 
assert os.path.getsize(filename) > 0, f"Empty File ({file1})"
assert os.path.isfile(filename), f"Export is not a file ({file1})"
io.export_dataframe(gdf2, path=filename, mode="a", partitionby=None, template="{filename}-{partition}-{i}", index=False)
assert os.path.exists(filename), f"Export failed ({file1})" 
assert os.path.isfile(filename), f"Export is not a directory ({file1})"


tmp = io.import_dataframe(filename).set_index(['source', 'target', 't'], drop=False)
tmp1 = pd.concat([gdf, gdf2], ignore_index=True).set_index(['source', 'target', 't'], drop=False)
tmp = tmp[tmp1.columns]  # Ensure columns match
assert (tmp1==tmp).all(axis=None), f"Import failed, dataframes do not match ({file1})"
assert isinstance(tmp, gpd.GeoDataFrame), f"Import failed, result is not a GeoDataFrame ({file1})"

file1 = "test1.parquet"
filename = os.path.join(folder, file1)
io.export_dataframe(gdf, path=filename, mode="w", partitionby=None, template="{filename}-{partition}-{i}", index=False)
assert os.path.exists(filename), f"Export failed ({file1})" 
assert os.path.getsize(filename) > 0, f"Empty File ({file1})"
assert os.path.isfile(filename), f"Export is not a file ({file1})"
io.export_dataframe(gdf2, path=filename, mode="a", partitionby=None, template="{filename}-{partition}-{i}", index=False)
assert os.path.exists(filename), f"Export failed ({file1})" 
assert os.path.isfile(filename), f"Export is not a file ({file1})"

tmp = io.import_dataframe(filename).set_index(['source', 'target', 't'], drop=False)
tmp1 = pd.concat([gdf, gdf2], ignore_index=True).set_index(['source', 'target', 't'], drop=False)
tmp = tmp.loc[:, tmp1.columns]  # Ensure columns match
assert (tmp1==tmp).drop(columns="geometry").all(axis=None), f"Import failed, dataframes do not match ({file1})"
assert isinstance(tmp, gpd.GeoDataFrame), f"Import failed, result is not a GeoDataFrame ({file1})"

file1 = "test1.csv"
filename = os.path.join(folder, file1)
io.export_dataframe(gdf, path=filename, mode="w", partitionby=None, template="{filename}-{partition}-{i}", index=False)
assert os.path.exists(filename), f"Export failed ({file1})" 
assert os.path.getsize(filename) > 0, f"Empty File ({file1})"
assert os.path.isfile(filename), f"Export is not a file ({file1})"
io.export_dataframe(gdf2, path=filename, mode="a", partitionby=None, template="{filename}-{partition}-{i}", index=False)
assert os.path.exists(filename), f"Export failed ({file1})" 
assert os.path.isfile(filename), f"Export is not a directory ({file1})"

tmp = io.import_dataframe(filename).set_index(['source', 'target', 't'], drop=False)
tmp1 = pd.concat([gdf, gdf2], ignore_index=True).set_index(['source', 'target', 't'], drop=False)
tmp = tmp.loc[:, tmp1.columns]  # Ensure columns match
assert (tmp1==tmp).all(axis=None), f"Import failed, dataframes do not match ({file1})"
assert isinstance(tmp, gpd.GeoDataFrame), f"Import failed, result is not a GeoDataFrame ({file1})"

file1 = "test1.xlsx"
filename = os.path.join(folder, file1)
io.export_dataframe(gdf, path=filename, mode="w", partitionby=None, template="{filename}-{partition}-{i}", index=False)
assert os.path.exists(filename), f"Export failed ({file1})" 
assert os.path.getsize(filename) > 0, f"Empty File ({file1})"
assert os.path.isfile(filename), f"Export is not a file ({file1})"
io.export_dataframe(gdf2, path=filename, mode="a", partitionby=None, template="{filename}-{partition}-{i}", index=False)
assert os.path.exists(filename), f"Export failed ({file1})" 
assert os.path.isdir(filename), f"Export is not a directory ({file1})"

tmp = io.import_dataframe(filename).set_index(['source', 'target', 't'], drop=False)
tmp1 = pd.concat([gdf, gdf2], ignore_index=True).set_index(['source', 'target', 't'], drop=False)
tmp = tmp.loc[:, tmp1.columns]  # Ensure columns match
assert (tmp1==tmp).all(axis=None), f"Import failed, dataframes do not match ({file1})"
assert isinstance(tmp, gpd.GeoDataFrame), f"Import failed, result is not a GeoDataFrame ({file1})"

file1 = "test1.feather"
filename = os.path.join(folder, file1)
io.export_dataframe(gdf, path=filename, mode="w", partitionby=None, template="{filename}-{partition}-{i}", index=False)
assert os.path.exists(filename), f"Export failed ({file1})" 
assert os.path.getsize(filename) > 0, f"Empty File ({file1})"
assert os.path.isfile(filename), f"Export is not a file ({file1})"
io.export_dataframe(gdf2, path=filename, mode="a", partitionby=None, template="{filename}-{partition}-{i}", index=False)
assert os.path.exists(filename), f"Export failed ({file1})" 
assert os.path.isdir(filename), f"Export is not a directory ({file1})"

tmp = io.import_dataframe(filename).set_index(['source', 'target', 't'], drop=False)
tmp1 = pd.concat([gdf, gdf2], ignore_index=True).set_index(['source', 'target', 't'], drop=False)
tmp = tmp.loc[:, tmp1.columns]  # Ensure columns match
assert (tmp1==tmp).all(axis=None), f"Import failed, dataframes do not match ({file1})"
assert isinstance(tmp, gpd.GeoDataFrame), f"Import failed, result is not a GeoDataFrame ({file1})"

file1 = "test1.shp"
filename = os.path.join(folder, file1)
io.export_dataframe(gdf, path=filename, mode="w", partitionby=None, template="{filename}-{partition}-{i}", index=False)
assert os.path.exists(filename), f"Export failed ({file1})" 
assert os.path.getsize(filename) > 0, f"Empty File ({file1})"
assert os.path.isfile(filename), f"Export is not a file ({file1})"
io.export_dataframe(gdf2, path=filename, mode="a", partitionby=None, template="{filename}-{partition}-{i}", index=False)
assert os.path.exists(filename), f"Export failed ({file1})" 
assert os.path.isfile(filename), f"Export is not a directory ({file1})"

tmp = io.import_dataframe(filename).set_index(['source', 'target', 't'], drop=False)
tmp1 = pd.concat([gdf, gdf2], ignore_index=True).set_index(['source', 'target', 't'], drop=False)
tmp = tmp.loc[:, tmp1.columns]  # Ensure columns match
assert (tmp1==tmp).all(axis=None), f"Import failed, dataframes do not match ({file1})"
assert isinstance(tmp, gpd.GeoDataFrame), f"Import failed, result is not a GeoDataFrame ({file1})"


file1 = "test1.gpkg"
filename = os.path.join(folder, file1)
io.export_dataframe(gdf, path=filename, mode="w", partitionby=None, template="{filename}-{partition}-{i}", index=False)
assert os.path.exists(filename), f"Export failed ({file1})" 
assert os.path.getsize(filename) > 0, f"Empty File ({file1})"
assert os.path.isfile(filename), f"Export is not a file ({file1})"
io.export_dataframe(gdf2, path=filename, mode="a", partitionby=None, template="{filename}-{partition}-{i}", index=False)
assert os.path.exists(filename), f"Export failed ({file1})" 
assert os.path.isfile(filename), f"Export is not a directory ({file1})"

tmp = io.import_dataframe(filename).set_index(['source', 'target', 't'], drop=False)
tmp1 = pd.concat([gdf, gdf2], ignore_index=True).set_index(['source', 'target', 't'], drop=False)
tmp = tmp.loc[:, tmp1.columns]  # Ensure columns match
assert (tmp1==tmp).all(axis=None), f"Import failed, dataframes do not match ({file1})"
assert isinstance(tmp, gpd.GeoDataFrame), f"Import failed, result is not a GeoDataFrame ({file1})"


file1 = "test2.geoparquet"
filename = os.path.join(folder, file1)
io.export_dataframe(gdf, path=filename, mode="w", partitionby=["t"], template="{filename}-{partition}-{i}", index=False)
assert os.path.exists(filename), f"Export failed ({file1})" 
assert os.path.isdir(filename), f"Export is not a file ({file1})"
io.export_dataframe(gdf2, path=filename, mode="a", partitionby=["t"], template="{filename}-{partition}-{i}", index=False)
assert os.path.exists(filename), f"Export failed ({file1})" 
assert os.path.isdir(filename), f"Export is not a directory ({file1})"

tmp = io.import_dataframe(filename).set_index(['source', 'target', 't'], drop=False)
tmp1 = pd.concat([gdf, gdf2], ignore_index=True).set_index(['source', 'target', 't'], drop=False)
tmp = tmp.loc[tmp1.index, tmp1.columns]  # Ensure columns match
assert (tmp1.values==tmp.values).all(), f"Import failed, dataframes do not match ({file1})"
assert isinstance(tmp, gpd.GeoDataFrame), f"Import failed, result is not a GeoDataFrame ({file1})"
