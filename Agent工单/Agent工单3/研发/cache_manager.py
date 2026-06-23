# -*- coding: utf-8 -*-
"""
==============================================================================
功能说明：Redis 缓存管理模块
==============================================================================
本文件实现了基于 Redis 的图像生成结果缓存功能。
当 Redis 不可用或认证失败时，自动降级停用，避免重复刷屏报错。
==============================================================================
"""

import json
import base64
import hashlib
import logging
import cv2
import numpy as np
from typing import Optional, Dict, Any
import redis

from config import redis_config

logger = logging.getLogger(__name__)


class CacheManager:
    """Redis 缓存管理器"""

    def __init__(self):
        self.client = None
        self.connected = False
        self.disabled = False
        self.disable_reason = ""
        logger.info("缓存管理器初始化完成")

    def connect(self):
        """连接 Redis 服务；失败时自动停用缓存能力"""
        if self.connected or self.disabled:
            return
        try:
            self.client = redis.Redis(
                host=redis_config.host,
                port=redis_config.port,
                db=redis_config.db,
                password=redis_config.password or None,
                decode_responses=True,
                socket_timeout=5
            )
            self.client.ping()
            self.connected = True
            logger.info(f"Redis 连接成功: {redis_config.host}:{redis_config.port}")
        except Exception as e:
            self.disabled = True
            self.disable_reason = str(e)
            logger.warning(f"Redis 不可用，已自动降级停用缓存: {e}")

    def _make_key(self, token: str) -> str:
        return f"{redis_config.cache_prefix}{token}"

    @staticmethod
    def hash_prompt(prompt: str) -> str:
        return hashlib.md5(prompt.encode("utf-8")).hexdigest()

    @staticmethod
    def hash_image(image: np.ndarray) -> str:
        success, buffer = cv2.imencode(".png", image)
        if not success:
            raise ValueError("图像编码失败，无法生成缓存哈希")
        return hashlib.md5(buffer.tobytes()).hexdigest()

    def build_cache_token(self, prompt: str, image: Optional[np.ndarray] = None, extra_meta: Optional[Dict[str, Any]] = None) -> str:
        token_data = {
            "prompt": prompt,
            "image_hash": self.hash_image(image) if image is not None else "",
            "extra_meta": extra_meta or {}
        }
        token_text = json.dumps(token_data, ensure_ascii=False, sort_keys=True)
        return hashlib.md5(token_text.encode("utf-8")).hexdigest()

    def cache_result(self, prompt: str, image: np.ndarray, task_type: str = "rotation", extra_meta: Optional[Dict[str, Any]] = None, cache_token: Optional[str] = None) -> bool:
        self._ensure_connected()
        if self.disabled or self.client is None:
            return False
        try:
            _, buffer = cv2.imencode(".png", image)
            img_b64 = base64.b64encode(buffer).decode("utf-8")
            token = cache_token or self.build_cache_token(prompt, image, extra_meta)
            cache_data = {
                "prompt": prompt,
                "task_type": task_type,
                "cache_token": token,
                "image_base64": img_b64,
                "image_shape": list(image.shape),
                "extra_meta": extra_meta or {}
            }
            key = self._make_key(token)
            self.client.setex(key, redis_config.expire_seconds, json.dumps(cache_data, ensure_ascii=False))
            logger.info(f"缓存写入成功, key={key[:24]}...")
            return True
        except Exception as e:
            logger.warning(f"缓存写入失败，已跳过: {e}")
            return False

    def get_cached(self, prompt: str, cache_token: Optional[str] = None) -> Optional[Dict[str, Any]]:
        self._ensure_connected()
        if self.disabled or self.client is None:
            return None
        token = cache_token or self.hash_prompt(prompt)
        key = self._make_key(token)
        data = self.client.get(key)
        if data is None:
            return None
        return json.loads(data)

    def get_cached_image(self, prompt: str, cache_token: Optional[str] = None) -> Optional[np.ndarray]:
        cached = self.get_cached(prompt, cache_token)
        if cached is None:
            return None
        img_b64 = cached["image_base64"]
        img_bytes = base64.b64decode(img_b64)
        img_array = np.frombuffer(img_bytes, np.uint8)
        return cv2.imdecode(img_array, cv2.IMREAD_COLOR)

    def delete_cache(self, prompt: str, cache_token: Optional[str] = None) -> bool:
        self._ensure_connected()
        if self.disabled or self.client is None:
            return False
        token = cache_token or self.hash_prompt(prompt)
        key = self._make_key(token)
        deleted = self.client.delete(key)
        return deleted > 0

    def get_cache_stats(self) -> Dict[str, Any]:
        self._ensure_connected()
        if self.disabled or self.client is None:
            return {
                "total_keys": 0,
                "prefix": redis_config.cache_prefix,
                "used_memory": "N/A",
                "expire_seconds": redis_config.expire_seconds,
                "disabled": True,
                "reason": self.disable_reason
            }
        keys = self.client.keys(f"{redis_config.cache_prefix}*")
        info = self.client.info("memory")
        return {
            "total_keys": len(keys),
            "prefix": redis_config.cache_prefix,
            "used_memory": info.get("used_memory_human", "N/A"),
            "expire_seconds": redis_config.expire_seconds,
            "disabled": False,
            "reason": ""
        }

    def _ensure_connected(self):
        if not self.connected and not self.disabled:
            self.connect()


_cache_manager: Optional[CacheManager] = None


def get_cache_manager() -> CacheManager:
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager()
    return _cache_manager
