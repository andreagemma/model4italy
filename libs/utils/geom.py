from shapely import MultiLineString, MultiPoint, MultiPolygon, Point, Polygon, LineString

def ST_Multi(geom):
    if isinstance(geom, Point):
        return MultiPoint([geom])
    if isinstance(geom, LineString):
        return MultiLineString([geom])
    if isinstance(geom, Polygon):
        return MultiPolygon([geom])
    if isinstance(geom, MultiLineString):
        return geom
    if isinstance(geom, MultiPoint):
        return geom
    if isinstance(geom, MultiPolygon):
        return geom
    raise ValueError(f"Cannot convert {type(geom)} to Multi*")

def multi_line_to_line(multi_line, get_first=False):
    if multi_line is None:
        return None
    if isinstance(multi_line, LineString):
        return multi_line
    
    if not isinstance(multi_line, MultiLineString):
        raise ValueError(f"Expected MultiLineString, got {type(multi_line)}")

    if get_first:
        if len(multi_line) == 0:
            return LineString()
        return multi_line[0]
    
    # Extract all coordinates from the MultiLineString
    all_coords = []
    for line in multi_line.geoms:
        all_coords.extend(line.coords)

    # Create a new LineString with the concatenated coordinates
    return LineString(all_coords)