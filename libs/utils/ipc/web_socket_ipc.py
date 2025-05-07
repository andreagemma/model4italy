import asyncio
import websockets
import pickle
from collections import defaultdict

import websockets.sync
import websockets.sync.client
from libs.utils.decorators import log_execution
import logging
try:
    import dill as pickle
except ImportError:
    import pickle

class WebSocketIPC:
    """
    Classe che implementa un sistema IPC basato su WebSocket.

    Funzionalità principali:
    - start(): avvia il server WebSocket.
    - subscribe(channel, callback): si sottoscrive a un canale e registra una funzione di callback.
    - publish(channel, message): invia un messaggio su un canale.
    - listen(): ascolta i messaggi ricevuti e invoca le callback registrate.
    """

    def __init__(self, host="localhost", port=8765):
        """Inizializza l'istanza con parametri di connessione e strutture interne."""
        self.logger = logging.getLogger(__name__)
        self.host = host
        self.port = port
        self.clients = {}  # websocket -> set(canali sottoscritti)
        self.callbacks = defaultdict(list)  # {channel: [callback_fn, ...]}
        self._conn = None

    @property
    def conn(self):
        """Apre e restituisce la connessione WebSocket se non già aperta."""
        if self._conn is None:
            uri = f"ws://{self.host}:{self.port}"
            self.logger.debug(f"Opening connection to {uri}")
            self._conn = websockets.sync.client.connect(uri)
        return self._conn

    async def handler(self, websocket):
        """Gestisce le connessioni in ingresso lato server."""
        self.logger.debug(f"Handling new connection from {websocket.remote_address}")
        self.clients[websocket] = set()
        try:
            async for message in websocket:
                data = pickle.loads(message)
                msg_type = data.get("type")
                channel = data.get("channel")

                if msg_type == "subscribe":
                    self.logger.debug(f"Client subscribed to channel '{channel}'")
                    self.clients[websocket].add(channel)

                elif msg_type == "publish":
                    payload = data.get("message")
                    if isinstance(payload, str):
                        self.logger.debug(f"Client published message on channel '{channel}': {payload}")
                    else:
                        self.logger.debug(f"Client published binary message on channel '{channel}'")
                    await self.broadcast(channel, payload)

        except websockets.ConnectionClosed:
            pass
        finally:
            del self.clients[websocket]

    async def broadcast(self, channel, payload):
        """Invia un messaggio a tutti i client sottoscritti a uno specifico canale."""
        msg = pickle.dumps({"channel": channel, "message": payload})
        for ws, chans in self.clients.items():
            if channel in chans:
                try:
                    await ws.send(msg)
                except Exception as e:
                    self.logger.error(f"Error sending message to {ws}: {e}")

    def subscribe(self, channel, callback):
        """Sottoscrive il client al canale e registra una callback."""
        self.logger.debug(f"Subscribing to channel '{channel}'")
        self.callbacks[channel].append(callback)
        self.conn.send(pickle.dumps({
            "type": "subscribe",
            "channel": channel
        }))

    def listen(self):
        """Ascolta i messaggi in arrivo e invoca le callback associate al canale."""
        self.logger.debug(f"Listening for messages on channels: {', '.join(self.callbacks.keys())}")
        while True:
            data = self.conn.recv()
            msg = pickle.loads(data)
            if isinstance(msg.get("message"), str):
                self.logger.debug(f"Received message: {msg}")
            else:
                self.logger.debug(f"Received message: {msg | {'message': 'blob'}}")

            channel = msg.get("channel")
            if channel in self.callbacks:
                for cb in self.callbacks[channel]:
                    cb(msg.get("message"))

    def publish(self, channel, message):
        """Pubblica un messaggio su un canale specifico."""
        msg = {
            "type": "publish",
            "channel": channel,
            "message": message
        }
        self.conn.send(pickle.dumps(msg))
        if isinstance(message, str):
            self.logger.debug(f"Publishing: {message}")
        else:
            self.logger.debug(f"Publishing: {{'message': 'blob'}}")

    def start(self):
        """Avvia il server WebSocket."""
        async def fn(self):
            self.logger.debug(f"Starting WebSocket IPC server on {self.host}:{self.port}")
            async with websockets.serve(self.handler, self.host, self.port):
                await asyncio.Future()  # run forever
        asyncio.run(fn(self))

# === Esempio di esecuzione server ===
if __name__ == "__main__":
    ipc = WebSocketIPC()
    ipc.start()