"""
Storage abstraction for the I-love-geekos marketplace.

DEMO SCENARIO:
  - Phase 1 (current): FileStorage stores cart/session data on a PersistentVolume.
    This will eventually fill up the disk (out-of-disk / OOM-like scenario).
  - Phase 2 (the fix): Replace FileStorage with RedisStorage by setting
    STORAGE_BACKEND=redis and providing REDIS_HOST/REDIS_PORT env vars.

To switch backends set the environment variable:
  STORAGE_BACKEND=file   (default)
  STORAGE_BACKEND=redis
"""

import json
import logging
import os
import time

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


# ── Redis-based storage (Phase 2 – the fix) ──────────────────────────────────

class RedisStorage:
    """
    Stores shopping-cart data in Redis.

    No files are written to disk, so the PersistentVolume is no longer needed.
    Environment variables:
      REDIS_HOST  (default: redis)
      REDIS_PORT  (default: 6379)
      REDIS_DB    (default: 0)
    Cart keys expire after CART_TTL_SECONDS (default: 3600).
    """

    CART_TTL = int(os.environ.get("CART_TTL_SECONDS", "3600"))

    def __init__(self):
        import redis as redis_lib  # imported lazily so the file backend doesn't need it

        host = os.environ.get("REDIS_HOST", "redis")
        port = int(os.environ.get("REDIS_PORT", "6379"))
        db = int(os.environ.get("REDIS_DB", "0"))
        self._r = redis_lib.Redis(host=host, port=port, db=db, decode_responses=True)
        logger.info("RedisStorage initialized – %s:%s db=%s", host, port, db)

    # ── cart ─────────────────────────────────────────────────────────────────

    def get_cart(self, session_id: str) -> list:
        raw = self._r.get(f"cart:{session_id}")
        if raw is None:
            return []
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return []

    def save_cart(self, session_id: str, cart: list) -> None:
        self._r.setex(f"cart:{session_id}", self.CART_TTL, json.dumps(cart))

    def clear_cart(self, session_id: str) -> None:
        self._r.delete(f"cart:{session_id}")

    # ── visit counter ─────────────────────────────────────────────────────────

    def increment_visits(self) -> int:
        return self._r.incr("visits")

    def get_visits(self) -> int:
        val = self._r.get("visits")
        return int(val) if val else 0

    # ── info ──────────────────────────────────────────────────────────────────

    def storage_info(self) -> dict:
        info = self._r.info("memory")
        return {
            "backend": "redis",
            "used_memory": info.get("used_memory"),
            "used_memory_human": info.get("used_memory_human"),
            "maxmemory": info.get("maxmemory"),
            "maxmemory_human": info.get("maxmemory_human"),
        }


# ── Factory ───────────────────────────────────────────────────────────────────

def create_storage():
    """
    Return the correct storage backend based on the STORAGE_BACKEND env var.

    STORAGE_BACKEND=file   → FileStorage  (default, Phase 1)
    STORAGE_BACKEND=redis  → RedisStorage (Phase 2 – the fix)
    """
    backend = os.environ.get("STORAGE_BACKEND", "file").lower()
    if backend == "redis":
        return RedisStorage()
    return FileStorage()
