class Controller:
    def __init__(self):
        self.store = Store()
        self.init_store()

    def init_store(self):
        pass


class Store:
    def __init__(self):
        self.storage = {}

    def get(self, key):
        if key not in self.storage.keys():
            return None
        return self.storage[key]

    def put(self, key, value):
        self.storage[key] = value
