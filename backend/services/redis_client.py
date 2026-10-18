"""Redis client with in-memory fallback for local/dev."""
import time
from collections import defaultdict
from typing import Optional, Any

from config import get_settings

_memory_store: dict[str, list] = defaultdict(list)
_cache: dict[str, tuple] = {}  # key -> (value, expires_at)
_redis = None
_redis_failed = False


def get_redis():
    global _redis, _redis_failed
    if _redis_failed:
        return None
    if _redis is not None:
        return _redis
    try:
        import redis
        settings = get_settings()
        client = redis.from_url(settings.REDIS_URL, decode_responses=True, socket_connect_timeout=1)
        client.ping()
        _redis = client
        return _redis
    except Exception:
        _redis_failed = True
        return None


def cache_get(key: str) -> Optional[str]:
    r = get_redis()
    if r:
        try:
            return r.get(key)
        except Exception:
            pass
    entry = _cache.get(key)
    if not entry:
        return None
    value, expires = entry
    if expires and time.time() > expires:
        _cache.pop(key, None)
        return None
    return value


def cache_set(key: str, value: str, ttl_seconds: int = 86400):
    r = get_redis()
    if r:
        try:
            r.setex(key, ttl_seconds, value)
            return
        except Exception:
            pass
    _cache[key] = (value, time.time() + ttl_seconds)


def cache_delete(key: str) -> None:
    r = get_redis()
    if r:
        try:
            r.delete(key)
        except Exception:
            pass
    _cache.pop(key, None)


def cache_delete_prefix(prefix: str) -> int:
    """Best-effort delete for in-memory keys; Redis SCAN not required for local."""
    removed = 0
    for k in list(_cache.keys()):
        if k.startswith(prefix):
            _cache.pop(k, None)
            removed += 1
    r = get_redis()
    if r:
        try:
            for k in r.scan_iter(match=f"{prefix}*", count=200):
                r.delete(k)
                removed += 1
        except Exception:
            pass
    return removed


def count_and_incr_daily(bucket: str, limit: int) -> tuple[bool, int]:
    """
    Returns (allowed, remaining). Increments only if under limit.
    """
    key = f"rl:{bucket}:{time.strftime('%Y%m%d')}"
    r = get_redis()
    if r:
        try:
            current = int(r.get(key) or 0)
            if current >= limit:
                return False, 0
            pipe = r.pipeline()
            pipe.incr(key)
            pipe.expire(key, 86400)
            pipe.execute()
            remaining = max(0, limit - current - 1)
            return True, remaining
        except Exception:
            pass

    # Memory fallback (24h window)
    now = time.time()
    cutoff = now - 86400
    _memory_store[key] = [t for t in _memory_store[key] if t > cutoff]
    if len(_memory_store[key]) >= limit:
        return False, 0
    _memory_store[key].append(now)
    remaining = max(0, limit - len(_memory_store[key]))
    return True, remaining


def peek_daily(bucket: str, limit: int) -> int:
    key = f"rl:{bucket}:{time.strftime('%Y%m%d')}"
    r = get_redis()
    if r:
        try:
            current = int(r.get(key) or 0)
            return max(0, limit - current)
        except Exception:
            pass
    now = time.time()
    cutoff = now - 86400
    entries = [t for t in _memory_store.get(key, []) if t > cutoff]
    return max(0, limit - len(entries))


def incr_daily(bucket: str, limit: int) -> tuple[bool, int]:
    """Increment only after success. Returns (ok, remaining)."""
    return count_and_incr_daily(bucket, limit)


def cache_json_get(key: str) -> Optional[Any]:
    """Retrieve and deserialize JSON from Redis or in-memory cache."""
    raw = cache_get(key)
    if not raw:
        return None
    try:
        import json
        return json.loads(raw)
    except Exception:
        return None


def cache_json_set(key: str, data: Any, ttl_seconds: int = 120) -> None:
    """Serialize and store JSON in Redis or in-memory cache."""
    try:
        import json
        serialized = json.dumps(data, default=str)
        cache_set(key, serialized, ttl_seconds=ttl_seconds)
    except Exception:
        pass


def get_cached_or_compute(key: str, compute_fn, ttl_seconds: int = 120, is_async: bool = False):
    """Fetch from cache or execute compute_fn and cache result."""
    cached = cache_json_get(key)
    if cached is not None:
        return cached
    # If not cached, compute
    if is_async:
        async def _run():
            res = await compute_fn()
            if res is not None:
                cache_json_set(key, res, ttl_seconds)
            return res
        return _run()
    else:
        res = compute_fn()
        if res is not None:
            cache_json_set(key, res, ttl_seconds)
        return res

