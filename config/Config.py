import json


class Config:
    def __init__(self, file_path):
        self.config_file = file_path
        with open(file_path, 'r') as json_data_file:
            self.data = json.load(json_data_file)

    def get(self, attributes):
        att = attributes.split("/")
        curr = self.data
        for attribute in att:
            if attribute not in curr.keys():
                return None
            curr = curr[attribute]
        return curr

    def set(self, path, value):
        att = path.split("/")
        root = self.data
        curr = root
        for index, attribute in enumerate(att):
            if attribute not in curr.keys():
                curr[attribute] = {}
            if index == len(att) - 1:
                curr[attribute] = value
            curr = curr[attribute]
        with open(self.config_file, 'w') as file:
            file.write(json.dumps(root, indent=2))
