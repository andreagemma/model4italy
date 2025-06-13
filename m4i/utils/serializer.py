import logging
import io
import re
from typing import Any

try:
    import dill as pickle
except ImportError:
    import pickle

class Serializer:
    CNAME_BLOSCLZ = "blosclz"
    CNAME_LZ4 = "lz4"
    CNAME_LZ4HC = "lz4hc"
    CNAME_SNAPPY = "snappy"
    CNAME_ZLIB = "zlib"
    CNAME_ZSTD = "zstd"
    CNAME_GZIP = "gzip"
    CNAME_BZ2 = "bz2"
    CNAME_ZIP = "zip"
    CNAME_LZMA = "lzma"

    def serialize(obj: Any, compression: str=None, clevel:int=5) -> bytes:
        assert compression in (None, "blosclz", "lz4", "lz4hc", "snappy", "zlib", "zstd", "gzip", "bz2", "zip", "lzma"), f"compression {compression} not supported"

        if compression in ("blosclz", "lz4", "lz4hc", "zlib", "zstd"):
            try:
                import blosc
            except ImportError:
                compression = None
                logging.info("blosc is not installed. Please install it to use this compression method. Compression set to None.")
        elif compression in ("gzip",):
            try:
                import gzip
            except ImportError:
                compression = None
                logging.info("gzip is not installed. Please install it to use this compression method. Compression set to None.")
        elif compression in ("bz2",):
            try:
                import bz2
            except ImportError:
                compression = None
                logging.info("bz2 is not installed. Please install it to use this compression method. Compression set to None.")
        elif compression in ("zip",):
            try:
                import zipfile
            except ImportError:
                compression = None
                logging.info("zipfile is not installed. Please install it to use this compression method. Compression set to None.")
        elif compression in ("lzma",):
            try:
                import lzma
            except ImportError:
                compression = None
                logging.info("lzma is not installed. Please install it to use this compression method. Compression set to None.")
        elif compression in ("snappy",):
            try:
                import snappy
            except ImportError:
                compression = None
                logging.info("snappy is not installed. Please install it to use this compression method. Compression set to None.")
        else:
            if compression is not None:
                logging.info(f"Compression {compression} not supported. Compression set to None.")
            compression = None
            

        # serialize
        pickled = pickle.dumps(obj, protocol=pickle.HIGHEST_PROTOCOL)

        if compression is None:
            return pickled
        elif compression in ("blosclz", "lz4", "lz4hc", "zlib", "zstd"):
            return blosc.compress(pickled, typesize=8, cname=compression, clevel=clevel)
        elif compression == "gzip":            
            return gzip.compress(pickled, compresslevel=clevel)
        elif compression == "bz2":
            return bz2.compress(pickled, compresslevel=clevel)
        elif compression == "zip":
            zip_buffer = io.BytesIO()
            if clevel ==0:
                compression_type = zipfile.ZIP_STORED
            else:
                compression_type = zipfile.ZIP_DEFLATED
            with zipfile.ZipFile(zip_buffer, "w", compression=compression_type, compresslevel=clevel) as zf:
                with zf.open("temp.pkl", "w") as f:
                    pickle.dump(pickled, f)
            return zip_buffer.getvalue()
        elif compression == "lzma":
            return lzma.compress(pickled, preset=clevel)
        elif compression == "snappy":
            return snappy.compress(pickled)
        

    def deserialize(data: bytes, compression: str=None) -> Any:
        assert compression in (None, "blosclz", "lz4", "lz4hc", "snappy", "zlib", "zstd", "gzip", "bz2", "zip", "lzma"), f"compression {compression} not supported"

        if compression in ("blosclz", "lz4", "lz4hc", "zlib", "zstd"):
            try:
                import blosc
            except ImportError:
                compression = None
                logging.info("blosc is not installed. Please install it to use this compression method. Compression set to None.")
        elif compression in ("gzip",):
            try:
                import gzip
            except ImportError:
                compression = None
                logging.info("gzip is not installed. Please install it to use this compression method. Compression set to None.")
        elif compression in ("bz2",):
            try:
                import bz2
            except ImportError:
                compression = None
                logging.info("bz2 is not installed. Please install it to use this compression method. Compression set to None.")
        elif compression in ("zip",):
            try:
                import zipfile
            except ImportError:
                compression = None
                logging.info("zipfile is not installed. Please install it to use this compression method. Compression set to None.")
        elif compression in ("lzma",):
            try:
                import lzma
            except ImportError:
                compression = None
                logging.info("lzma is not installed. Please install it to use this compression method. Compression set to None.")
        elif compression in ("snappy",):
            try:
                import snappy
            except ImportError:
                compression = None
                logging.info("snappy is not installed. Please install it to use this compression method. Compression set to None.")
        else:
            if compression is not None:
                logging.info(f"Compression {compression} not supported. Compression set to None.")
            compression = None

        if data is None or len(data) == 0:
            return data

        if compression is None:
            return pickle.loads(data)
        elif compression in ("blosclz", "lz4", "lz4hc", "zlib", "zstd"):
            return pickle.loads(blosc.decompress(data))
        elif compression == "gzip":
            return pickle.loads(gzip.decompress(data))
        elif compression == "bz2":
            return pickle.loads(bz2.decompress(data))
        elif compression == "zip":
            with zipfile.ZipFile(io.BytesIO(data), 'r') as zf:
                with zf.open("temp.pkl") as f:
                    return pickle.load(f)
        elif compression == "lzma":
            return pickle.loads(lzma.decompress(data))
        elif compression == "snappy":
            return pickle.loads(snappy.decompress(data))
                



if __name__ == "__main__":
# test all compression methods with dimensions resulting in 1MB
    def test_compression_methods():
        import numpy as np
        import time
        import random

        # Create a random array of size 1MB
        data = np.random.rand(1000000).astype(np.float32)

        # Test all compression methods
        for method in [None, Serializer.CNAME_BLOSCLZ, Serializer.CNAME_LZ4, Serializer.CNAME_LZ4HC, Serializer.CNAME_SNAPPY, Serializer.CNAME_ZLIB, Serializer.CNAME_ZSTD, Serializer.CNAME_GZIP, Serializer.CNAME_BZ2, Serializer.CNAME_ZIP, Serializer.CNAME_LZMA]:
            start_time = time.time()
            compressed_data = Serializer.serialize(data, compression=method)
            end_time = time.time()
            decompressed_data = Serializer.deserialize(compressed_data, compression=method)
            end_time2 = time.time()
            
            # Print the results in one row
            print(f"Compression method: {method}, CTime: {end_time - start_time:.4f}, DTime: {end_time2 - end_time:.4f}, size: {len(data)} bytes, Csize: {len(compressed_data)} bytes")

    # Test the Serializer class
    test_compression_methods()
