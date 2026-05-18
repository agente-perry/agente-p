import gzip
import json
from google.cloud import storage

_client = None


def _gcs():
    global _client
    if _client is None:
        _client = storage.Client()
    return _client


def stream_jsonl(bucket: str, blob_path: str):
    """Stream JSONL from GCS line by line, handling optional gzip."""
    b = _gcs().bucket(bucket)
    blob = b.blob(blob_path)
    with blob.open("rb") as raw:
        fh = gzip.open(raw) if blob_path.endswith(".gz") else raw
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


def read_json(bucket: str, blob_path: str) -> dict:
    b = _gcs().bucket(bucket)
    return json.loads(b.blob(blob_path).download_as_bytes())


def list_blobs(bucket: str, prefix: str) -> list[str]:
    return [b.name for b in _gcs().list_blobs(bucket, prefix=prefix)]
