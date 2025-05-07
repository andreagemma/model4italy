import pickle
import threading
import logging
from collections import defaultdict
import redis

try:
    import dill as pickle
except ImportError:
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
            if message['type'] == 'message':
                channel = message['channel'].decode() if isinstance(message['channel'], bytes) else message['channel']
                data = pickle.loads(message['data'])
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

    def start(self):
        """Avvia l'ascolto in un thread separato (compatibilità interfaccia)."""
        self.logger.debug(f"Starting Redis IPC on server {self.host}:{self.port}")
        import time
        while True:
            time.sleep(1)

# === Esempio di esecuzione ===
if __name__ == "__main__":
    ipc = RedisIPC("172.0.0.6", 6379)
    ipc.start()

