import asyncio
import logging
import os
import time
import threading
from typing import Optional

logger = logging.getLogger(__name__)

_CACHE_DISABLED = os.environ.get("RAGFLOW_DISABLE_CACHE", "").lower() in ("1", "true", "yes")


class _CacheEntry:
    __slots__ = ("value", "created_at", "ttl", "last_access")
    def __init__(self, value, ttl=300.0):
        self.value = value
        self.created_at = time.monotonic()
        self.ttl = ttl
        self.last_access = time.monotonic()
    @property
    def expired(self): return (time.monotonic() - self.created_at) > self.ttl
    def touch(self): self.last_access = time.monotonic()


class LLMBundleCache:
    _instance = None
    _lock = threading.Lock()
    def __init__(self, ttl=300.0, max_size=64):
        self._cache = {}
        self._ttl = ttl
        self._max_size = max_size
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance
    def _make_key(self, tenant_id, model_config):
        return (tenant_id, model_config.get("llm_factory",""), model_config.get("llm_name",""), model_config.get("model_type",""))
    def get(self, tenant_id, model_config):
        key = self._make_key(tenant_id, model_config)
        entry = self._cache.get(key)
        if entry is None: return None
        if entry.expired:
            try: entry.value.close()
            except: pass
            del self._cache[key]
            return None
        entry.touch()
        return entry.value
    def put(self, tenant_id, model_config, bundle):
        key = self._make_key(tenant_id, model_config)
        if len(self._cache) >= self._max_size: self._evict_one()
        existing = self._cache.get(key)
        if existing is not None:
            try: existing.value.close()
            except: pass
        self._cache[key] = _CacheEntry(bundle, ttl=self._ttl)
    def _evict_one(self):
        if not self._cache: return
        best_key, best_age = None, -1.0
        for key, entry in self._cache.items():
            age = time.monotonic() - entry.created_at
            if age > best_age: best_age, best_key = age, key
        if best_key is not None:
            entry = self._cache.pop(best_key)
            try: entry.value.close()
            except: pass
    def clear(self):
        for key, entry in list(self._cache.items()):
            try: entry.value.close()
            except: pass
        self._cache.clear()
    def __len__(self): return len(self._cache)


class LangfuseCache:
    _instance = None
    _lock = threading.Lock()
    def __init__(self, ttl=600.0):
        self._cache = {}
        self._ttl = ttl
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None: cls._instance = cls()
        return cls._instance
    def get(self, tenant_id):
        entry = self._cache.get(tenant_id)
        if entry is None: return None
        if entry.expired:
            try:
                if hasattr(entry.value, "shutdown"): entry.value.shutdown()
            except: pass
            del self._cache[tenant_id]
            return None
        entry.touch()
        return entry.value
    def put(self, tenant_id, client):
        existing = self._cache.get(tenant_id)
        if existing is not None:
            try:
                if hasattr(existing.value, "shutdown"): existing.value.shutdown()
            except: pass
        self._cache[tenant_id] = _CacheEntry(client, ttl=self._ttl)
    def clear(self):
        for tenant_id, entry in list(self._cache.items()):
            try:
                if hasattr(entry.value, "shutdown"): entry.value.shutdown()
            except: pass
        self._cache.clear()


class ChatConcurrencyLimiter:
    _instance = None
    _lock = threading.Lock()
    def __init__(self, max_concurrent=10):
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._max_concurrent = max_concurrent
    @classmethod
    def get_instance(cls, max_concurrent=10):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None: cls._instance = cls(max_concurrent=max_concurrent)
        return cls._instance
    @property
    def max_concurrent(self): return self._max_concurrent
    async def acquire(self): await self._semaphore.acquire()
    def release(self): self._semaphore.release()
    async def __aenter__(self):
        await self.acquire()
        return self
    async def __aexit__(self, *args): self.release()


def get_or_create_bundle(tenant_id, model_config, lang="Chinese", **kwargs):
    from api.db.services.llm_service import LLMBundle
    if _CACHE_DISABLED:
        return LLMBundle(tenant_id, model_config, lang=lang, **kwargs)
    cache = LLMBundleCache.get_instance()
    bundle = cache.get(tenant_id, model_config)
    if bundle is not None: return bundle
    bundle = LLMBundle(tenant_id, model_config, lang=lang, **kwargs)
    cache.put(tenant_id, model_config, bundle)
    return bundle
