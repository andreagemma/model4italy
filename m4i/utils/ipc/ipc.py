import operator
from m4i.monitor import run_from_command_line
import pickle
from .shared_memory import SharedMemory
from .redis_ipc import RedisIPC
from .redis_shared_memory import RedisSharedMemory
from .web_socket_ipc import WebSocketIPC
from typing import Callable, Any, Generator
class IPC:

    def __init__(self,bucket: str=None, host='localhost', port=6379, db=0, compression: str = None, compression_level: int = 5, backend: str = "redis"):
        """
        Inizializza l'oggetto IPC con il backend desiderato.
        """
        self.bucket = bucket
        self.host = host
        self.port = port
        self.db = db
        self.compression = compression
        self.compression_level = compression_level
        self.backend = backend
        self.prefix = f"{bucket}:" if bucket else ""     
        assert backend in ["redis", "local"], f"Backend {backend} non supportato. Scegli tra 'redis' o 'local'."

        if backend == "redis":
            self.ipc = RedisIPC(host=host, port=port, db=db)
            self.shdmem = RedisSharedMemory(bucket=bucket, host=host, port=port, db=db, compression=compression, clevel=compression_level)
        elif backend == "local":
            self.ipc = WebSocketIPC(host="localhost", port=port)
            self.shdmem = SharedMemory(bucket=bucket, compression=compression, clevel=compression_level)

    def _key(self, key) ->str:
        return f"{self.prefix}{key}"

    def _remove_bucket(self, key: str)->str:
        return key[len(self.prefix):] if key.startswith(self.prefix) else key
    
    def _in_bucket(self, key: str)->bool:
        return key.startswith(self.prefix) if self.bucket else True


    def subscribe(self, channel:str , callback:Callable) -> None:
        channel = self._key(channel)
        self.ipc.subscribe(channel, callback)

    def publish(self, channel:str, message: Any) -> None:
        channel = self._key(channel)
        self.ipc.publish(channel, message)

    def listen(self) -> None:
        self.ipc.listen()

    def start(self)-> None:
        self.ipc.start()

    def set(self, key:str, value: Any)-> None:
        """
        Salva un valore associato a una chiave.
        L'oggetto viene serializzato con pickle.
        """
        self.shdmem.set(key, value)
    
    def get(self, key:str)-> Any:
        """
        Recupera il valore associato a una chiave.
        L'oggetto viene deserializzato con pickle.
        """
        return self.shdmem.get(key)

    def delete(self, key:str)-> None:
        """
        Elimina una chiave dal key-value store.
        """
        self.shdmem.delete(key)
    def clear(self)-> None:
        """
        Elimina tutte le chiavi dal key-value store.
        """
        self.shdmem.clear()
    def keys(self)-> list[str]:
        """
        Restituisce tutte le chiavi nel key-value store.
        """
        return self.shdmem.keys()
    
    def scan_iter(self, match=None)-> Generator[str, None, None]:
        for k in self.shdmem.scan_iter(match=match):
            yield k

    def set_data(self,**kwargs)-> None:
        """
        Salva più valori associati a più chiavi.
        """
        for k, v in kwargs.items():
            self.set(k, v)
    
    def get_data(self, keys: list[str])-> dict[str, Any]:
        """
        Recupera più valori associati a più chiavi.
        """
        return {k: self.get(k) for k in keys}
    
    def delete_data(self, keys: list[str])-> None:
        """
        Elimina più chiavi dal key-value store.
        """
        for k in keys:
            self.delete(k)
    def init(self) -> None:
        """
        Inizializza il client Redis.
        """
        self.ipc.init()
    def running(self) -> bool:
        """
        Verifica se il client Redis è in esecuzione.
        """
        return self.ipc.running()
    def run_client(self):
        import ast
        while True:
            try:
                command = input("Inserisci il comando (set/get/delete/keys/publish/subscribe/exit): ")
                if command == "exit":
                    break
                elif command.startswith("set"):
                    key = input("Inserisci chiave: ").strip()                
                    value = input("Inserisci valore: ").strip()
                    value = ast.literal_eval(value) if value.startswith("{") else value
                    self.set(key, value)
                elif command.startswith("get"):
                    key = input("Inserisci chiave: ").strip()
                    value = self.get(key)
                    print(f"Valore di {key}: {value}")
                elif command.startswith("delete"):
                    key = input("Inserisci chiave o 'all': ").strip()
                    if key == "all":
                        self.clear()
                        print("Tutte le chiavi eliminate.")
                    else:
                        self.delete(key)
                        print(f"Chiave {key} eliminata.")
                elif command == "keys":
                    keys = self.keys()
                    print(f"Chiavi: {keys}")
                elif command.startswith("publish"):
                    channel = input("Inserisci canale: ").strip()
                    message = input("Inserisci messaggio: ").strip()
                    message = ast.literal_eval(message) if message.startswith("{") else message
                    self.publish(channel, message)
                elif command.startswith("subscribe"):
                    channel = input("Inserisci canale: ").strip()
                    def callback(message):
                        print(f"Messaggio ricevuto: {message}")
                    self.subscribe(channel, callback)
                    print(f"Sottoscritto al canale {channel}.")
                elif command.startswith("ping"):
                    if self.ipc.running():
                        print("Ping OK")
                    else:
                        print("Ping KO")
                else:
                    print("Comando non valido.")
            except Exception as e:
                print(f"Errore: {e}")
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        mode = sys.argv[1]
    ipc = IPC(host="localhost", port=6379, db=0, backend="redis")
    if mode == "server":        
        ipc.start()
    elif mode == "producer":
        import time
        for i in range(30000):
            message = f"Messaggio {i} dal producer"
            ipc.publish("notifiche", message)
            time.sleep(2)
    elif mode == "consumer":
        def callback(message):
            print(f"Messaggio ricevuto: {message}")
        ipc.subscribe("notifiche", callback)
        ipc.listen()

