# %%
import osmnx as ox
import networkx as nx
import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString
import requests
import sqlalchemy as sa

# -----------------------------------------------------------
# 1. DOWNLOAD GRAFO + NORMALIZZAZIONE DIREZIONALITÀ
# -----------------------------------------------------------

def build_directed_osm_graph(gdf_area, network_type="drive"):
    # usa il poligono (assicurati sia in EPSG:4326)
    if gdf_area.crs.to_epsg() != 4326:
        gdf_area = gdf_area.to_crs(4326)

    poly = gdf_area.union_all()

    G = ox.graph_from_polygon(poly, network_type=network_type, simplify=True)

    # forza MultiDiGraph orientato in modo compatibile con diverse versioni di osmnx
    if hasattr(ox, "utils_graph") and hasattr(ox.utils_graph, "get_digraph"):
        # versioni vecchie di osmnx
        G = ox.utils_graph.get_digraph(G)
    elif hasattr(ox, "utils_graph") and hasattr(ox.utils_graph, "graph_to_digraph"):
        # versioni più recenti di osmnx
        G = ox.utils_graph.graph_to_digraph(G)
    else:
        # ripiego: assicura comunque un MultiDiGraph diretto
        if not isinstance(G, nx.MultiDiGraph):
            G = nx.MultiDiGraph(G)

    return G


# -----------------------------------------------------------
# 2. SDOPPIA ARCHI BIDIREZIONALI
# -----------------------------------------------------------

def explode_bidirectional_edges(G):
    G2 = nx.MultiDiGraph()

    for u, v, k, data in G.edges(keys=True, data=True):

        oneway = data.get("oneway", False)

        # forward
        G2.add_edge(u, v, key=f"{k}_fwd", **data, direction="fwd")

        # backward se non oneway
        if not oneway or oneway in ["no", "False", 0]:
            # inverti geometria
            geom = data.get("geometry", None)
            if geom:
                geom = LineString(list(geom.coords)[::-1])

            data_rev = data.copy()
            data_rev["geometry"] = geom

            G2.add_edge(v, u, key=f"{k}_rev", **data_rev, direction="rev")

    return G2


# -----------------------------------------------------------
# 3. DOWNLOAD TURN RESTRICTIONS (OVERPASS)
# -----------------------------------------------------------

def download_turn_restrictions(gdf_area):
        # usa union_all (più recente) evitando l'avviso su unary_union
        poly = gdf_area.union_all()

        # costruiamo la coordinata poligonale per Overpass (lat lon)
        coords = " ".join([f"{y} {x}" for x, y in poly.exterior.coords])

        query = f"""
        [out:json][timeout:60];
        (
            relation["type"="restriction"](poly:"{coords}");
        );
        out body;
        >;
        out skel qt;
        """

        url = "https://overpass-api.de/api/interpreter"
        r = requests.post(url, data=query)

        # gestione robusta del parsing JSON (Overpass può rispondere con HTML / errori)
        try:
                data = r.json()
        except Exception as e:
                print("Warning: Overpass JSON parse failed (turn restrictions disabilitate):", e)
                print("HTTP status:", r.status_code)
                print("Response content:", r.text[:500])  # stampa i primi 500 caratteri della risposta
                # niente restriction: restituisco struttura vuota compatibile con parse_restrictions
                return {"elements": []}

        return data


# -----------------------------------------------------------
# 4. PARSE RESTRICTIONS
# -----------------------------------------------------------

def parse_restrictions(overpass_json):
    # se la risposta è vuota o non ha 'elements', ritorna DF vuoto
    if not overpass_json or "elements" not in overpass_json:
        return pd.DataFrame(columns=["id", "type", "from", "to", "via"])

    restrictions = []

    for el in overpass_json["elements"]:
        if el["type"] != "relation":
            continue

        tags = el.get("tags", {})
        if "restriction" not in tags:
            continue

        rel = {
            "id": el["id"],
            "type": tags["restriction"],
            "from": None,
            "to": None,
            "via": None
        }

        for m in el["members"]:
            if m["role"] == "from":
                rel["from"] = m["ref"]
            elif m["role"] == "to":
                rel["to"] = m["ref"]
            elif m["role"] == "via":
                rel["via"] = m["ref"]

        restrictions.append(rel)

    return pd.DataFrame(restrictions)


# -----------------------------------------------------------
# 5. EDGE-BASED GRAPH (MANOVRE)
# -----------------------------------------------------------

def build_edge_based_graph(G):

    LG = nx.DiGraph()

    # nodo = arco originale
    edge_nodes = {}

    for u, v, k, data in G.edges(keys=True, data=True):
        edge_id = (u, v, k)
        LG.add_node(edge_id, **data)
        edge_nodes[(u, v, k)] = edge_id

    # archi = manovre
    for u, v, k in G.edges(keys=True):
        for _, w, k2 in G.out_edges(v, keys=True):
            LG.add_edge((u, v, k), (v, w, k2))

    return LG


# -----------------------------------------------------------
# 6. APPLICA RESTRICTIONS
# -----------------------------------------------------------

def apply_turn_restrictions(LG, restrictions, G):

    # mappa way_id → archi
    way_to_edges = {}

    for u, v, k, data in G.edges(keys=True, data=True):
        way_id = data.get("osmid")
        if way_id is None:
            continue

        if isinstance(way_id, list):
            for wid in way_id:
                way_to_edges.setdefault(wid, []).append((u, v, k))
        else:
            way_to_edges.setdefault(way_id, []).append((u, v, k))

    forbidden = set()

    for _, r in restrictions.iterrows():

        from_edges = way_to_edges.get(r["from"], [])
        to_edges = way_to_edges.get(r["to"], [])

        if r["type"].startswith("no_"):
            for e1 in from_edges:
                for e2 in to_edges:
                    forbidden.add((e1, e2))

        elif r["type"].startswith("only_"):
            # tutte le altre manovre sono vietate
            for e1 in from_edges:
                for e2 in LG.successors(e1):
                    if e2 not in to_edges:
                        forbidden.add((e1, e2))

    # rimuovi archi vietati
    LG.remove_edges_from(forbidden)

    return LG


# -----------------------------------------------------------
# PIPELINE COMPLETA
# -----------------------------------------------------------

def build_routing_graph_from_gdf(gdf_area):

    G = build_directed_osm_graph(gdf_area)
    G = explode_bidirectional_edges(G)

    overpass = download_turn_restrictions(gdf_area)
    restrictions = parse_restrictions(overpass)

    LG = build_edge_based_graph(G)
    LG = apply_turn_restrictions(LG, restrictions, G)

    return G, LG, restrictions

# %%
engine =sa.create_engine("postgresql://postgres:lDvdc15dcd5@192.168.133.80:5432/m4i")
with engine.connect() as conn:
    ok = conn.execute(sa.text("SELECT 1")).fetchone()[0]==1
    if ok:
        print("Connection successful")
area = gpd.read_postgis("SELECT * FROM eur2.zones", con=engine, geom_col="geom")

# %%
G, LG, restrictions = build_routing_graph_from_gdf(area)

# %%



