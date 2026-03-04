import threading


class Controller:
    def __init__(self):
        self.store = Store()
        self.init_store()

    def init_store(self):
        pass


class Store:
    def __init__(self):
        self.storage = {}
        self._lock = threading.Lock()

    def get(self, key):
        with self._lock:
            return self.storage.get(key)

    def put(self, key, value):
        with self._lock:
            self.storage[key] = value
