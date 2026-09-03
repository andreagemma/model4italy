from __future__ import annotations
from typing import *
from types import FunctionType
from numbers import Number
from .path import Path
from .path_container import PathContainer
import numpy as np
from abc import ABC, abstractmethod


class KPathContainer(PathContainer):
    def __init__(self, **kwargs):
        super().__init__()
        self.update(**kwargs)
        self["type"] = self.__class__.__name__

    def add_path(self, to_add: Path, k: Optional[int] = None, **kwargs):
        raise NotImplementedError()

    def merge(
        self,
        to_add: Union[Path, PathContainer, KPathContainer],
        override_k=False,
        **kwargs,
    ):
        if isinstance(to_add, Path):
            self.add_path(to_add, k=path.get("k") if override_k else None, **kwargs)
        elif isinstance(to_add, PathContainer):
            for path in to_add.all_paths(**kwargs):
                self.add_path(path, k=path.get("k") if override_k else None)
        else:
            raise NotImplementedError(
                f"la funzione merge per la {type} non è stata implementata"
            )

    @abstractmethod
    def get_sources(
        self,
        target: Optional[Hashable] = None,
        t_start: Optional[Number] = None,
        mode: Optional[str] = None,
        **kwargs,
    ) -> Tuple[Hashable]:
        raise NotImplementedError()

    @abstractmethod
    def get_targets(
        self,
        source: Optional[Hashable] = None,
        t_start: Optional[Number] = None,
        mode: Optional[str] = None,
        **kwargs,
    ) -> Optional[Tuple[Hashable]]:
        raise NotImplementedError()

    @abstractmethod
    def get_t_starts(
        self,
        source: Optional[Hashable] = None,
        target: Optional[Hashable] = None,
        mode: Optional[str] = None,
        **kwargs,
    ) -> Tuple[Number]:
        raise NotImplementedError()

    @abstractmethod
    def get_modes(
        self,
        source: Optional[Hashable] = None,
        target: Optional[Hashable] = None,
        t_start: Optional[Number] = None,
        **kwargs,
    ) -> Tuple[Hashable]:
        raise NotImplementedError()

    def paths(
        self, source: Hashable, target: Hashable, t_start: Number, *args, **kwargs
    ) -> Generator[Path]:
        raise NotImplementedError()

    def path(
        self,
        source: Hashable,
        target: Hashable,
        t_start: Number,
        mode: str,
        k: int,
        **kwargs,
    ) -> Path:
        raise NotImplementedError()

    def all_paths(self, **kwargs) -> Generator[Path]:
        raise NotImplementedError()

    def all_kpaths(self, **kwargs) -> Generator[List[Path]]:
        raise NotImplementedError()

    def n_paths(self, **kwargs) -> int:
        return len(self.all_paths(**kwargs))

    def n_unique_paths(self, **kwargs) -> int:
        return len(self.all_paths(**kwargs))

    def k_paths(self, **kwargs) -> int:
        return max(path["k"] for path in self.all_paths(**kwargs))

    def counts_tot_links(self, **kwargs) -> int:
        return sum([len(path.get_links()) for path in self.all_paths(**kwargs)])

    def counts_link(self, id_link: Hashable, **kwargs) -> int:
        return sum([int(path.has_link(id_link)) for path in self.all_paths(**kwargs)])

    def from_pandas(self, df, **kwargs) -> KPathList:
        import pandas as pd

        df: pd.DataFrame = df if isinstance(df, pd.DataFrame) else pd.DataFrame(df)

        grps = df.groupby(["source", "target", "t_start", "mode"])
        for key, index in grps.groups.items():
            group = df.loc[index, :].copy()
            group.sort_values(by="tot_cost", inplace=True)
            for k, (_, row) in enumerate(group.iterrows()):
                args = row.to_dict()
                args["k"] = k
                path = Path.load_from_dict(args)
                self.add_path(path, **kwargs)
        return self

    def to_pandas(self, G, crs_link):
        df_paths: pd.DataFrame = pd.DataFrame(self.all_paths())
        if df_paths.empty:
            df_paths = gpd.GeoDataFrame(df_paths, geometry=[], crs=crs_link)
            return df_paths
        l = next(G.get_all_links())
        for geom in ("geom", "geometry"):
            if geom in l:
                df_paths[geom] = [
                    MultiLineString(
                        [
                            multi_line_to_line(G.get_link(l_idx).get_value(geom))
                            for l_idx in links
                        ]
                    )
                    for links in df_paths["links"]
                ]
                df_paths = gpd.GeoDataFrame(df_paths, geometry=geom, crs=crs_link)
                return df_paths
        return None
