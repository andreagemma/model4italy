#%%
import time

import geopandas as gpd
import pandas as pd
from shapely.ops import linemerge
from shapely.geometry import LineString
#%%
df_links = gpd.read_file(r"dati/grafo_nuovo/mv_sim_roads_wide.shp")
df_nodes = gpd.read_file(r"dati/grafo_nuovo/mv_sim_nodes_wide.shp")
#%%
def can_merge(l1,l2):
    if l1["is_connect"] == 1 or l2["is_connect"] == 1:
        return False
    #if pd.notna(l1["ramps"]) or pd.notna(l2["ramps"]):
    #    return False
    #if l1["network"] == 1 or l2["network"] == 1:
    #    return False
    if l1["network"] != l2["network"]:
        return False
    if l1["lanes"] != l2["lanes"]:
        return False
    if l1["speed"] != l2["speed"]:
        return False
    if l1["capacity"] != l2["capacity"]:
        return False
    return True

def merge(l1,l2):
    ret = l1.copy()
    ret["nb"] = l2["nb"]
    ret["links"] += l2["links"]
    #ret["links"] = list(set(ret["links"]))
    ret["lenght"] += l2["lenght"]
    ret["geometry"] = LineString(list(l1["geometry"].coords)+list(l2["geometry"].coords))
    return ret

class LinksCollection:

    def __init__(self) -> None:
        self.d_da = {}
        self.d_a = {}
        pass

    @staticmethod
    def load(df):
        lc = LinksCollection()
        for _, row in df.iterrows():
            lc.add(row)
        return lc

    def add(self,l):
        if l["na"] in self.d_da:
            self.d_da[l["na"]].append(l)
        else:
            self.d_da[l["na"]] = [l]
        if l["nb"] in self.d_a:
            self.d_a[l["nb"]].append(l)
        else:
            self.d_a[l["nb"]] = [l]

    def rem(self,l):
        if l["na"] in self.d_da:
            self.d_da[l["na"]] = [l1 for l1 in self.d_da[l["na"]] if l1["idx"]!=l["idx"]]
        if l["nb"] in self.d_a:
            self.d_a[l["nb"]] = [l1 for l1 in self.d_a[l["nb"]] if l1["idx"]!=l["idx"]]

    def fws(self,n):
        if n["n"] in self.d_da:
            return self.d_da[n["n"]]
        else:
            return []

    def bws(self,n):
        if n["n"] in self.d_a:
            return self.d_a[n["n"]]
        else:
            return []

t1 = time.time()
dfl = df_links.copy()
dfl["links"]=dfl.id.apply(lambda x: [x])
dfl["idx"] = dfl.index.values
dfl = LinksCollection.load(dfl)
protected = [187210,877219,1039213,188596,188597,460810,1039210,1039211,1039212,438601,438593,438552]
df_nodes=df_nodes.assign(protected=0)
for p in protected:
    b=df_nodes["n"]==p
    df_nodes.loc[b,"protected"]=1
nodes = df_nodes.assign(to_remove=0).to_dict("records")
modificato = True
while modificato:
    print(f"N° nodi {len(nodes)}")
    modificato=False
    for n in nodes:
        if n["is_centroi"] == 1 or n["protected"]==1:
            continue
        fws = dfl.fws(n)
        if len(fws) not in (1,2):
            continue
        bws = dfl.bws(n)
        if len(bws) not in (1,2) or len(bws)!=len(fws):
            continue
        if len(fws) == 1:
            l1 = bws[0]
            l2 = fws[0]
            if l1["idx"]==l2["idx"]:
                continue
            if can_merge(l1,l2):
                l = merge(l1,l2)
                dfl.rem(l1)
                dfl.rem(l2)
                dfl.add(l)
                n["to_remove"] = 1
                #print(f"Eliminato nodo {n['n']}")
                modificato=True
        elif len(fws) == 2:
            l1a = bws[0]
            l1b = bws[1]
            l2a = fws[0]
            l2b = fws[1]

            if l1a["na"] == l2a["nb"]:
                l2a, l2b = l2b, l2a
            else:
                pass
            if l1a["na"] != l2b["nb"] or l2a["nb"] != l1b["na"]:
                continue
            if l1a["idx"] in (l1b["idx"],l2a["idx"],l2b["idx"]):
                continue
            if l1b["idx"] in (l2a["idx"],l2b["idx"]):
                continue
            if l2a["idx"] == l2b["idx"]:
                continue

            if can_merge(l1a,l2a) and can_merge(l1b,l2b):
                l = merge(l1a,l2a)
                dfl.rem(l1a)
                dfl.rem(l2a)
                dfl.add(l)

                l = merge(l1b,l2b)
                dfl.rem(l1b)
                dfl.rem(l2b)
                dfl.add(l)
                # print(f"Eliminato nodo {n['n']}")
                
                n["to_remove"] = 1
                modificato=True
    
    nodes = [n for n in nodes if n["to_remove"]==0]
print(time.time()-t1)
# %%
links = []
convert = []
for ll in dfl.d_da.values():
    for l in ll:
        ld = l.to_dict()
        links.append(ld)
        for i in range(len(ld["links"])):
            link = ld["links"][i]
            convert.append({"id_orig": link, "id_simpl": ld["id"], "ord": i})

ret = gpd.GeoDataFrame(links, crs='EPSG:25832')
ret["links"] = ret["links"].apply(lambda x: ','.join(map(str,x)))
ret.to_file(r'dati/grafo_nuovo/mv_sim_roads_wide_ag.shp')

ret2 = pd.DataFrame(convert)
ret2.to_csv(r'dati/grafo_nuovo/tabella_di_conversione.csv',index=False)
df_links.merge(ret2, left_on="id", right_on="id_orig").to_file(r'dati/grafo_nuovo/mv_sim_roads_wide_with_simply_id.shp')

# %%
"""
SELECT 
simply_id as id,
(array_agg(na order by ord))[1] as na,
(array_agg(nb order by ord desc))[1] as nb,
capacity, lanes, speed, sum(lenght) as lenght,
ramps,tsysset,is_connect,network
--st_multi(ST_LineMerge(st_multi(st_union(geom order by ord))))::geometry(Multilinestring,3044) as geom
FROM public.mv_sim_roads_wide_with_simply_id
group by capacity, lanes, speed, ramps,tsysset,is_connect,network,simply_id
"""
