import time
import json

class History(json.JSONEncoder):
    def __init__(self, id, name = "empty", model = "empty", info_text = ""):
        self.id = id
        self.name = name
        self.model = model
        self.info_text = info_text
        self.created_at = time.time()

    def to_json(self):
        return {
            "id": self.id,
            "name": self.name,
            "model": self.model,
            "info_text": self.info_text,
            "created_at": self.created_at,
        }