import time
from ..serializer import Serializer
# Prova a importare redis se disponibile
try:
    import redis
except ImportError:
    redis = None
from typing import Any
from multiprocessing.managers import SyncManager
from multiprocessing import Event, Queue
from time import sleep
from fnmatch import fnmatchcase as fnmatch

class RedisSharedMemory:
    """
    Classe che fornisce un'interfaccia simile a Redis per la memorizzazione
    e l'accesso a dati condivisi.:

    Metodi disponibili:
    - set(key, value)
    - get(key)
    - delete(key)
    - keys()
    """

    def __init__(self, bucket: str=None, host='localhost', port=6379, db=0, compression: str = None, clevel: int = 5):
        """
        Inizializza l'oggetto ShardMemory con il backend desiderato.

        Parameters:
        - host, port, db: parametri per connessione Redis
        """
        self.compression = compression
        self.clevel = clevel
        self.bucket = bucket
        self.prefix = f"{bucket}:" if bucket else ""        

        if redis is None:
            raise ImportError("redis-py non è installato. Esegui: pip install redis")
        # Connessione a Redis
        self.client = redis.StrictRedis(host=host, port=port, db=db)

    
    def _key(self, key):
        return f"{self.prefix}{key}"

    def _remove_bucket(self, key: str):
        return key[len(self.prefix):] if key.startswith(self.prefix) else key
    
    def _in_bucket(self, key: str):
        return key.startswith(self.prefix) if self.bucket else True
    
    def set(self, key, value):
        """
        Salva un valore associato a una chiave.
        L'oggetto viene serializzato con pickle.
        """
        self.client.set(self._key(key), Serializer.serialize(value, compression=self.compression, clevel=self.clevel))
 
    def get(self, key):
        """
        Recupera il valore associato a una chiave.
        L'oggetto viene deserializzato con pickle.
        """
        data = self.client.get(self._key(key))
        return Serializer.deserialize(data, compression=self.compression) if data else None
 
    def delete(self, key):
        """
        Elimina una chiave dal key-value store.
        """
        self.client.delete(self._key(key))

    def clear(self):
        """
        Elimina tutte le chiavi dal key-value store.
        """
        if self.bucket:
            for key in self.client.keys():
                self.client.delete(key)
        else:
            raise ValueError("Non è possibile eliminare tutte le chiavi senza un bucket specificato.")

    def keys(self):
        """
        Restituisce la lista delle chiavi presenti nel key-value store.
        """
        return [k for k in self.scan_iter()]

    def scan_iter(self, match=None):
        for key in self.client.scan_iter():
            k=key.decode()
            if self._in_bucket(k):
                if match is None or fnmatch(match, k):
                    yield self._remove_bucket(k)
