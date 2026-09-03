# Calcolo azimuth tra due punti
# %%
import math
import geopandas as gpd
import pandas as pd
import numpy as np
from shapely.geometry import LineString, Point
from math import degrees, atan2, exp
import logging
from ..utils import Parallel


class MapMatching:
    def __init__(
        self, links_gdf, links_id_col="id", links_direction_col=None, segments_gdf=None
    ):
        self.links_gdf = links_gdf
        self.links_id_col = links_id_col
        self.link_direction_col = links_direction_col
        self._segments_gdf = segments_gdf

    @property
    def segments_gdf(self):
        if self._segments_gdf is None:
            self._segments_gdf = MapMatching.split_links_to_segments(
                self.links_gdf,
                link_id_col=self.links_id_col,
                link_direction_col=self.link_direction_col,
            )
        return self._segments_gdf

    @staticmethod
    def calculate_azimuth(p1, p2):
        angle = degrees(atan2(p2.x - p1.x, p2.y - p1.y))
        return (angle + 360) % 360

    # Funzione per calcolare differenza angolare
    @staticmethod
    def angular_difference(a1, a2):
        return min(abs(a1 - a2), 360 - abs(a1 - a2))

    # Suddivisione link in segmenti elementari utilizzando GeoPandas
    @staticmethod
    def split_links_to_segments(
        links_gdf, link_id_col="id_link", link_direction_col=None
    ):
        segments_list = []
        if (
            link_direction_col
        ):  # Se i link hanno una direzione calcolo gli archi in direzione opposta
            dir_reverse = links_gdf[link_direction_col] == -1
            links_gdf.loc[dir_reverse, "geometry"] = links_gdf[
                dir_reverse
            ].geometry.apply(lambda x: LineString(list(x.coords)[::-1]))

            double_direction = links_gdf[link_direction_col] == 0
            links_to_add_reverse = links_gdf[double_direction].copy()
            links_to_add_reverse.loc[:, "geometry"] = (
                links_to_add_reverse.geometry.apply(
                    lambda x: LineString(list(x.coords)[::-1])
                )
            )
            links_to_add_reverse.loc[:, link_id_col] = -links_to_add_reverse[
                link_id_col
            ]
            links_gdf = pd.concat([links_gdf, links_to_add_reverse], ignore_index=True)

        for _, row in links_gdf.iterrows():
            geom = row.geometry
            points = list(geom.coords)
            total_length = geom.length

            # spezzo il link in segmenti
            for i in range(len(points) - 1):
                segment_geom = LineString([points[i], points[i + 1]])
                start_pos = geom.project(Point(points[i])) / total_length
                end_pos = geom.project(Point(points[i + 1])) / total_length
                azimuth = MapMatching.calculate_azimuth(
                    Point(points[i]), Point(points[i + 1])
                )

                segments_list.append(
                    {
                        "id_link": row[link_id_col],
                        "geometry": segment_geom,
                        "start_pos": start_pos,
                        "end_pos": end_pos,
                        "azimuth": azimuth,
                    }
                )

        return gpd.GeoDataFrame(segments_list, crs=links_gdf.crs)

    # Matching segmento-FCD
    def match(
        self,
        gps_gdf,
        max_distance=50,
        max_angle=45,
        fcd_id_col="id_fcd",
        fcd_dir_col="heading",
        fcd_state_col="engine",
        all_matches=False,
    ):
        # logging.getLogger(self.__class__.__name__).debug("Matching FCD...")
        matched_results = []
        segments_gdf = self.segments_gdf
        segments_sindex = segments_gdf.sindex

        for idx, gps in gps_gdf.iterrows():
            possible_matches_index = list(
                segments_sindex.intersection(gps.geometry.buffer(max_distance).bounds)
            )
            possible_matches = segments_gdf.iloc[possible_matches_index].copy()

            possible_matches["dist"] = possible_matches.geometry.distance(gps.geometry)
            possible_matches["alpha"] = possible_matches["azimuth"].apply(
                lambda x: MapMatching.angular_difference(x, gps[fcd_dir_col])
            )

            candidates = possible_matches[
                (possible_matches["dist"] <= max_distance)
                & (possible_matches["alpha"] < max_angle)
            ].copy()

            if candidates.empty:
                # print("No candidates found for GPS trace with ID: ", gps[gps_id_col])
                continue

            candidates["p_alpha"] = candidates["alpha"].apply(
                lambda alpha: (
                    0.1
                    if alpha <= 5 or gps[fcd_state_col] in [0, 2]
                    else 0.1 * exp(-(alpha - 5) / 5)
                )
            )
            candidates["p_distance"] = candidates["dist"].apply(
                lambda dist: 0.183024 * exp(-dist / 5.46376)
            )
            candidates["prob"] = candidates["p_alpha"] * candidates["p_distance"]

            sum_prob = candidates["prob"].sum()
            candidates["prob"] /= sum_prob

            idx_best = candidates["prob"].idxmax()

            best_candidate = candidates.loc[idx_best].copy()
            relative_pos = best_candidate.geometry.project(
                gps.geometry, normalized=True
            )
            best_candidate["matched_pos"] = best_candidate[
                "start_pos"
            ] + relative_pos * (best_candidate["end_pos"] - best_candidate["start_pos"])
            link_best = best_candidate["id_link"]

            best_candidate["link_prob"] = candidates[
                candidates["id_link"] == link_best
            ]["prob"].sum()

            matched_results.append(
                {
                    fcd_id_col: gps[fcd_id_col],
                    "mm_id_link": link_best,
                    "mm_pos": best_candidate["matched_pos"],
                    #'mm_seg_prob': best_candidate['prob'],
                    "mm_link_prob": best_candidate["link_prob"],
                }
            )
            if all_matches:
                candidates["matched_pos"] = candidates[
                    "start_pos"
                ] + candidates.geometry.project(gps.geometry, normalized=True) * (
                    candidates["end_pos"] - candidates["start_pos"]
                )
                df_all_matches = (
                    candidates[["id_link", "matched_pos", "prob"]]
                    .groupby("id_link")
                    .apply(
                        lambda x: pd.Series(
                            {
                                "mm_link_prob": x["prob"].sum(),
                                "mm_pos": x.loc[x["prob"].idxmax(), "matched_pos"],
                            }
                        ),
                        include_groups=False,
                    )
                    .reset_index()
                    .rename(columns={"id_link": "mm_id_link"})
                )
                matched_results[-1]["all_matches"] = df_all_matches.sort_values(
                    "mm_link_prob", ascending=False
                ).to_dict(orient="records")
        if len(matched_results) == 0:
            if all_matches:
                match = pd.DataFrame(
                    columns=[
                        fcd_id_col,
                        "mm_id_link",
                        "mm_pos",
                        "mm_seg_prob",
                        "mm_link_prob",
                        "all_matches",
                    ]
                )
            else:
                match = pd.DataFrame(
                    columns=[
                        fcd_id_col,
                        "mm_id_link",
                        "mm_pos",
                        "mm_seg_prob",
                        "mm_link_prob",
                    ]
                )
        else:
            match = pd.DataFrame(matched_results)
        return match

    def parallel_match(
        self,
        gps_gdf,
        max_distance=50,
        max_angle=45,
        fcd_id_col="id_fcd",
        fcd_dir_col="heading",
        fcd_state_col="engine",
        all_matches=False,
        chunksize: int = 10000,
        n_workers: int = None,
    ):
        n_partitions = max(1, len(gps_gdf) // chunksize)
        tasks = np.array_split(gps_gdf, n_partitions)
        match = None
        for df_mm in Parallel.execute(
            self.match,
            tasks,
            n_workers=n_workers,
            max_distance=max_distance,
            max_angle=max_angle,
            fcd_id_col=fcd_id_col,
            fcd_dir_col=fcd_dir_col,
            fcd_state_col=fcd_state_col,
            all_matches=all_matches,
        ):
            if match is None:
                match = df_mm
            else:
                match = pd.concat([match, df_mm], ignore_index=True)
        return match
