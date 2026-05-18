"""
File-based checkpoint for resumable ingestion.
Stores last successfully flushed record index per loader.
On restart, loaders skip records up to the checkpoint.
"""
import json
import os

_DIR = os.path.join(os.path.dirname(__file__), ".checkpoints")


def save(name: str, last_record: int) -> None:
    os.makedirs(_DIR, exist_ok=True)
    with open(os.path.join(_DIR, f"{name}.json"), "w") as f:
        json.dump({"last_record": last_record}, f)


def load(name: str) -> int:
    """Return last successfully flushed record index, or -1 if no checkpoint."""
    path = os.path.join(_DIR, f"{name}.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f).get("last_record", -1)
    return -1


def clear(name: str) -> None:
    path = os.path.join(_DIR, f"{name}.json")
    if os.path.exists(path):
        os.remove(path)


def status() -> dict:
    """Return all current checkpoints."""
    if not os.path.exists(_DIR):
        return {}
    result = {}
    for fname in os.listdir(_DIR):
        if fname.endswith(".json"):
            with open(os.path.join(_DIR, fname)) as f:
                result[fname[:-5]] = json.load(f).get("last_record", -1)
    return result
