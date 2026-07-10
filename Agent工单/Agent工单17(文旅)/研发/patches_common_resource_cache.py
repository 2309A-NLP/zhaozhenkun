#
#  Copyright 2026 The InfiniFlow Authors. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
"""
Resource cache manager for LLMBundle, Langfuse clients, and other heavy resources.

Provides process-level caching with TTL to avoid repeated initialization
of expensive model wrappers, HTTP sessions, and tracing clients per request.

Key features:
- Thread-safe singleton cache stores
- TTL-based expiration (default: 300s for models, 600s for Langfuse)
- Automatic cleanup of expired entries
- Connection pool size limits
"""

import asyncio
import logging
import time
import threading
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Cache entry with TTL
# ---------------------------------------------------------------------------

class _CacheEntry:
    """A cache entry with TTL tracking."""
    __slots__ = ("value", "created_at", "ttl", "last_access")

    def __init__(self, value, ttl: float = 300.0):
        self.value = value
        self.created_at = time.monotonic()
        self.ttl = ttl
        self.last_access = time.monotonic()

    @property
    def expired(self) -> bool:
        return (time.monotonic() - self.created_at) > self.ttl

    def touch(self):
        self.last_access = time.monotonic()


# ---------------------------------------------------------------------------
# LLMBundle Cache
# ---------------------------------------------------------------------------

class LLMBundleCache:
    """
    Process-level cache for LLMBundle instances.

    Keyed by (tenant_id, llm_factory, llm_name, model_type) to ensure
    unique instances per model configuration.

    Default TTL: 300 seconds. Entries are lazily evicted on access.
    """
    _instance: Optional["LLMBundleCache"] = None
    _lock = threading.Lock()

    def __init__(self, ttl: float = 300.0, max_size: int = 64):
        self._cache: dict[tuple, _CacheEntry] = {}
        self._ttl = ttl
        self._max_size = max_size

    @classmethod
    def get_instance(cls) -> "LLMBundleCache":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def _make_key(self, tenant_id: str, model_config: dict) -> tuple:
        return (
            tenant_id,
            model_config.get("llm_factory", ""),
            model_config.get("llm_name", ""),
            model_config.get("model_type", ""),
        )

    def get(self, tenant_id: str, model_config: dict):
        """Get a cached LLMBundle or return None."""
        key = self._make_key(tenant_id, model_config)
        entry = self._cache.get(key)
        if entry is None:
            return None
        if entry.expired:
            # Lazy eviction
            try:
                entry.value.close()
            except Exception:
                pass
            del self._cache[key]
            return None
        entry.touch()
        return entry.value

    def put(self, tenant_id: str, model_config: dict, bundle) -> None:
        """Store an LLMBundle in the cache."""
        key = self._make_key(tenant_id, model_config)
        # Enforce max size
        if len(self._cache) >= self._max_size:
            self._evict_one()
        # Close existing entry if overwriting
        existing = self._cache.get(key)
        if existing is not None:
            try:
                existing.value.close()
            except Exception:
                pass
        self._cache[key] = _CacheEntry(bundle, ttl=self._ttl)
        logger.debug("LLMBundleCache: cached %s (size=%d)", key, len(self._cache))

    def _evict_one(self):
        """Evict the most expired entry."""
        if not self._cache:
            return
        best_key = None
        best_age = -1.0
        now = time.monotonic()
        for key, entry in self._cache.items():
            age = now - entry.created_at
            if age > best_age:
                best_age = age
                best_key = key
        if best_key is not None:
            entry = self._cache.pop(best_key)
            try:
                entry.value.close()
            except Exception:
                pass
            logger.debug("LLMBundleCache: evicted %s", best_key)

    def clear(self):
        """Close all cached bundles and clear the cache."""
        for key, entry in list(self._cache.items()):
            try:
                entry.value.close()
            except Exception:
                pass
        self._cache.clear()
        logger.info("LLMBundleCache: cleared all entries")

    def __len__(self):
        return len(self._cache)


# ---------------------------------------------------------------------------
# Langfuse Client Cache
# ---------------------------------------------------------------------------

class LangfuseCache:
    """
    Per-tenant cache for Langfuse clients.

    Creating a Langfuse client involves network auth-check and
    HTTP connection pool setup. Reusing clients avoids that overhead.
    """
    _instance: Optional["LangfuseCache"] = None
    _lock = threading.Lock()

    def __init__(self, ttl: float = 600.0):
        self._cache: dict[str, _CacheEntry] = {}
        self._ttl = ttl

    @classmethod
    def get_instance(cls) -> "LangfuseCache":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def get(self, tenant_id: str):
        entry = self._cache.get(tenant_id)
        if entry is None:
            return None
        if entry.expired:
            try:
                if hasattr(entry.value, "shutdown"):
                    entry.value.shutdown()
            except Exception:
                pass
            del self._cache[tenant_id]
            return None
        entry.touch()
        return entry.value

    def put(self, tenant_id: str, client) -> None:
        existing = self._cache.get(tenant_id)
        if existing is not None:
            try:
                if hasattr(existing.value, "shutdown"):
                    existing.value.shutdown()
            except Exception:
                pass
        self._cache[tenant_id] = _CacheEntry(client, ttl=self._ttl)

    def clear(self):
        for tenant_id, entry in list(self._cache.items()):
            try:
                if hasattr(entry.value, "shutdown"):
                    entry.value.shutdown()
            except Exception:
                pass
        self._cache.clear()


# ---------------------------------------------------------------------------
# Concurrency limiter for chat requests
# ---------------------------------------------------------------------------

class ChatConcurrencyLimiter:
    """
    Semaphore-based concurrency limiter for chat/completion requests.

    Prevents resource saturation under high concurrency by limiting
    simultaneous in-flight requests. Excess requests queue up.
    """

    _instance: Optional["ChatConcurrencyLimiter"] = None
    _lock = threading.Lock()

    def __init__(self, max_concurrent: int = 10):
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._max_concurrent = max_concurrent

    @classmethod
    def get_instance(cls, max_concurrent: int = 10) -> "ChatConcurrencyLimiter":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(max_concurrent=max_concurrent)
        return cls._instance

    @property
    def max_concurrent(self) -> int:
        return self._max_concurrent

    async def acquire(self):
        """Acquire a slot, waiting if necessary."""
        await self._semaphore.acquire()

    def release(self):
        """Release a slot."""
        self._semaphore.release()

    async def __aenter__(self):
        await self.acquire()
        return self

    async def __aexit__(self, *args):
        self.release()


# ---------------------------------------------------------------------------
# Cleanup helper
# ---------------------------------------------------------------------------

def get_or_create_bundle(tenant_id: str, model_config: dict, lang: str = "Chinese", **kwargs):
    """
    Get a cached LLMBundle or create and cache a new one.

    Replacement for direct LLMBundle() constructor calls to enable
    automatic caching of model instances.

    Usage:
        chat_mdl = get_or_create_bundle(tenant_id, chat_model_config)
    """
    from api.db.services.llm_service import LLMBundle

    cache = LLMBundleCache.get_instance()
    bundle = cache.get(tenant_id, model_config)
    if bundle is not None:
        return bundle

    bundle = LLMBundle(tenant_id, model_config, lang=lang, **kwargs)
    cache.put(tenant_id, model_config, bundle)
    return bundle
