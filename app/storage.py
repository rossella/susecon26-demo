"""
Storage layer for the I-love-geekos marketplace.

CURRENT STATE (Phase 1):
  FileStorage writes one JSON file per visitor session to DATA_DIR, which is
  mounted from a Kubernetes PersistentVolumeClaim.  Files are never cleaned up,
  so the volume gradually fills until writes fail with "No space left on device".

THE FIX (Phase 2 – to be implemented during the demo):
  Add a RedisStorage class that stores cart data in Redis using SETEX so keys
  expire automatically.  Then update create_storage() to return RedisStorage
  when STORAGE_BACKEND=redis is set.

  Required interface (same methods as FileStorage):
    get_cart(session_id)      → list
    save_cart(session_id, cart)
    clear_cart(session_id)
    increment_visits()        → int
    get_visits()              → int
    storage_info()            → dict with key "backend" = "redis"

  Useful env vars: REDIS_HOST (default: "redis"), REDIS_PORT (default: 6379),
                   REDIS_DB (default: 0), CART_TTL_SECONDS (default: 3600)
"""

import json
import logging
import os

logger = logging.getLogger(__name__)

# ── helpers ──────────────────────────────────────────────────────────────────

DATA_DIR = os.environ.get("DATA_DIR", "/data")


def _cart_path(session_id: str) -> str:
    return os.path.join(DATA_DIR, f"cart_{session_id}.json")


def _stats_path() -> str:
    return os.path.join(DATA_DIR, "stats.json")


# ── File-based storage (Phase 1 – stored on PersistentVolume) ────────────────

class FileStorage:
    """
    Stores shopping-cart data as JSON files on a PersistentVolume.

    WARNING: Every session creates a new file that is never automatically
    cleaned up, which will gradually fill the volume.  This is intentional
    for the demo – it makes the out-of-disk error easy to reproduce.
    """

    def __init__(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        logger.info("FileStorage initialized – data dir: %s", DATA_DIR)

    # ── cart ─────────────────────────────────────────────────────────────────

    def get_cart(self, session_id: str) -> list:
        path = _cart_path(session_id)
        if not os.path.exists(path):
            return []
        try:
            with open(path, "r") as fh:
                return json.load(fh)
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("Failed to read cart %s: %s", path, exc)
            return []

    def save_cart(self, session_id: str, cart: list) -> None:
        path = _cart_path(session_id)
        try:
            with open(path, "w") as fh:
                json.dump(cart, fh)
        except OSError as exc:
            # In the demo this will eventually throw when the volume is full
            logger.error("Failed to write cart %s: %s", path, exc)
            raise

    def clear_cart(self, session_id: str) -> None:
        path = _cart_path(session_id)
        if os.path.exists(path):
            os.remove(path)

    # ── visit counter (stored in a single JSON file) ─────────────────────────

    def increment_visits(self) -> int:
        stats = self._read_stats()
        stats["visits"] = stats.get("visits", 0) + 1
        self._write_stats(stats)
        return stats["visits"]

    def get_visits(self) -> int:
        return self._read_stats().get("visits", 0)

    def _read_stats(self) -> dict:
        path = _stats_path()
        if not os.path.exists(path):
            return {}
        try:
            with open(path, "r") as fh:
                return json.load(fh)
        except (json.JSONDecodeError, OSError):
            return {}

    def _write_stats(self, stats: dict) -> None:
        with open(_stats_path(), "w") as fh:
            json.dump(stats, fh)

    # ── disk-usage helper (used by the /storage-status endpoint) ─────────────

    def storage_info(self) -> dict:
        files = []
        total_bytes = 0
        try:
            for fname in os.listdir(DATA_DIR):
                fpath = os.path.join(DATA_DIR, fname)
                size = os.path.getsize(fpath)
                total_bytes += size
                files.append({"name": fname, "size_bytes": size})
            stat = os.statvfs(DATA_DIR)
            free_bytes = stat.f_bavail * stat.f_frsize
            total_disk = stat.f_blocks * stat.f_frsize
        except OSError:
            free_bytes = 0
            total_disk = 0
        return {
            "backend": "file",
            "data_dir": DATA_DIR,
            "file_count": len(files),
            "used_bytes": total_bytes,
            "free_bytes": free_bytes,
            "total_disk_bytes": total_disk,
            "files": sorted(files, key=lambda f: f["name"]),
        }


# TODO: implement RedisStorage here (Phase 2 – the fix).
# See the module docstring above for the required interface and env vars.


# ── Factory ───────────────────────────────────────────────────────────────────

def create_storage():
    """Return the storage backend for the application.

    Currently only FileStorage is supported.  After implementing RedisStorage
    above, update this function to return RedisStorage() when the environment
    variable STORAGE_BACKEND=redis is set.
    """
    return FileStorage()
