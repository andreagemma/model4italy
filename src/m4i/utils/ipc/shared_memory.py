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


class _SharedKVStore:
    """
    Classe interna che implementa un semplice key-value store
    in memoria condivisa usando un dizionario Python + pickle.
    Viene registrata come oggetto condivisibile da SyncManager.
    """

    def __init__(self):
        self._store = {}

    def set(self, key, value):
        """Serializza e salva il valore associato alla chiave."""
        self._store[key] = value

    def get(self, key):
        """Recupera e deserializza il valore associato alla chiave."""
        return self._store.get(key)

    def delete(self, key):
        """Rimuove la chiave dal dizionario, se presente."""
        self._store.pop(key, None)

    def keys(self):
        """Restituisce l'elenco delle chiavi presenti."""
        return list(self._store.keys())

    def __len__(self):
        """Restituisce il numero di chiavi presenti."""
        return len(self._store)


# Definizione dinamica del manager
class KVManager(SyncManager):
    pass


KVManager.register("SharedKVStore", _SharedKVStore)


class SharedMemory:
    """
    Classe che fornisce un'interfaccia simile a Redis per la memorizzazione
    e l'accesso a dati condivisi su memoria condivisa.

    Metodi disponibili:
    - set(key, value)
    - get(key)
    - delete(key)
    - keys()
    """

    def __init__(self, bucket: str = None, compression: str = None, clevel: int = 5):
        """
        Inizializza l'oggetto ShardMemory.

        """
        self.compression = compression
        self.clevel = clevel
        self.bucket = bucket
        self.prefix = f"{bucket}:" if bucket else ""

        # Registrazione del tipo condiviso
        KVManager.register("SharedKVStore", _SharedKVStore)
        # Avvio del manager
        self._manager = KVManager()
        self._manager.start()
        # Istanza condivisa
        self.client = self._manager.SharedKVStore()

    def _key(self, key):
        return f"{self.prefix}{key}"

    def _remove_bucket(self, key: str):
        return key[len(self.prefix) :] if key.startswith(self.prefix) else key

    def _in_bucket(self, key: str):
        return key.startswith(self.prefix) if self.bucket else True

    def set(self, key, value):
        """
        Salva un valore associato a una chiave.
        L'oggetto viene serializzato con pickle.
        """
        self.client.set(
            self._key(key),
            Serializer.serialize(value, compression=self.compression, clevel=self.clevel),
        )

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
        """
        Itera sulle chiavi del key-value store.
        """
        # match = self._key(match) if match else self.prefix+"*"
        for k in self.client.keys():
            if self._in_bucket(k):
                if match is None or fnmatch(match, k):
                    yield self._remove_bucket(k)
