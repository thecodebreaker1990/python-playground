import os
import json
import uuid
from datetime import datetime

DB_FILE = "db.json"

def load_db():
    if not os.path.exists(DB_FILE):
        return {}
    with open(DB_FILE, "r") as f:
        return json.load(f)

def save_db(data):
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=2)

db = load_db()


def generate_unique_id():
    return str(uuid.uuid4())

def add_metadata(message):
    return {
        **message,
        "id": generate_unique_id(),
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

def remove_metadata(message):
    new_message = { **message }
    new_message.pop("id", None)
    new_message.pop("created_at", None)
    return new_message

def add_messages(messages):
    db.setdefault("messages", []).extend(add_metadata(message) for message in messages)
    save_db(db)

def get_messages():
    return [remove_metadata(message) for message in db.get("messages", [])]
