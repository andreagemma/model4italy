import pickle
import threading
import logging
from collections import defaultdict
import warnings

try:
    import redis
except ImportError:
    warnings.warn(
        "Redis library not found. Please install it with 'pip install redis' to use it.",
        ImportWarning,
    )


import socket

try:
    import dill as pickle
except ImportError:
    warnings.warn(
        "Dill library not found. Using standard pickle instead. Install it with 'pip install dill' for better serialization support.",
        ImportWarning,
    )
    import pickle

logging.basicConfig(level=logging.DEBUG)


class RedisIPC:
    """
    Classe che implementa un sistema IPC basato su Redis Pub/Sub.

    Metodi principali:
    - subscribe(channel, callback): sottoscrive il client a un canale e registra una funzione di callback.
    - publish(channel, message): invia un messaggio su un canale.
    - listen(): ascolta i messaggi ricevuti e invoca le callback registrate.
    - start(): avvia un thread di ascolto (non necessario in Redis, mantenuto per compatibilità di interfaccia).
    """

    def __init__(self, host="localhost", port=6379, db=0):
        self.logger = logging.getLogger(__name__)
        self.host = host
        self.port = port
        self.callbacks = defaultdict(list)  # {channel: [callback_fn, ...]}
        self.redis_client = redis.Redis(host=self.host, port=self.port, db=db)
        self.pubsub = self.redis_client.pubsub()

    def subscribe(self, channel, callback):
        """Sottoscrive a un canale Redis e registra la callback."""
        self.logger.debug(f"Subscribing to channel '{channel}'")
        self.callbacks[channel].append(callback)
        self.pubsub.subscribe(channel)

    def listen(self):
        """Ascolta i messaggi in arrivo e invoca le callback registrate."""
        self.logger.debug(f"Listening for messages on channels: {', '.join(self.callbacks.keys())}")
        for message in self.pubsub.listen():
            if message["type"] == "message":
                channel = message["channel"].decode() if isinstance(message["channel"], bytes) else message["channel"]
                data = pickle.loads(message["data"])
                if isinstance(data, str):
                    self.logger.debug(f"Received message: {{'channel': '{channel}', 'message': '{data}'}}")
                else:
                    self.logger.debug(f"Received message: {{'channel': '{channel}', 'message': 'blob'}}")

                if channel in self.callbacks:
                    for cb in self.callbacks[channel]:
                        cb(data)

    def publish(self, channel, message):
        """Pubblica un messaggio su un canale Redis."""
        payload = pickle.dumps(message)
        self.redis_client.publish(channel, payload)
        if isinstance(message, str):
            self.logger.debug(f"Publishing: {message}")
        else:
            self.logger.debug(f"Publishing: {{'message': 'blob'}}")

    def start(self, blocking=True):
        """Avvia l'ascolto in un thread separato (compatibilità interfaccia)."""
        self.logger.debug(f"Starting Redis IPC on server {self.host}:{self.port}")
        if blocking:
            import time

            while True:
                time.sleep(1)

    def running(self) -> bool:
        try:
            client = redis.Redis(host=self.host, port=self.port, db=self.db, socket_connect_timeout=1)
            return client.ping()
        except (redis.ConnectionError, redis.TimeoutError):
            return False

    def init(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1.0)
            ret = s.connect_ex((self.host, self.port)) == 0
        if not ret:
            self.logger.error(f"Port {self.port} is not available. Please check if Redis is running.")
            return False


# === Esempio di esecuzione ===
if __name__ == "__main__":
    ipc = RedisIPC("172.0.0.6", 6379)
    ipc.start()
