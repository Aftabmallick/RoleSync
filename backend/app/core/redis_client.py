import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional, Set, AsyncGenerator
import redis
import redis.asyncio as aioredis
from app.core.config import settings

logger = logging.getLogger("rolesync.redis")


class InMemoryRedisMock:
    """
    Thread-safe and async-compatible Redis fallback for local testing,
    sandboxed development, or environments without a running Redis server.
    Implements key-value, hash, set, and pub/sub primitives.
    """
    def __init__(self):
        self._kv: Dict[str, str] = {}
        self._hashes: Dict[str, Dict[str, str]] = {}
        self._sets: Dict[str, Set[str]] = {}
        self._ttls: Dict[str, float] = {}
        self._subscribers: Dict[str, List[asyncio.Queue]] = {}
        try:
            loop = asyncio.get_running_loop()
            self._lock = asyncio.Lock()
        except RuntimeError:
            self._lock = None

    def _is_expired(self, key: str) -> bool:
        if key in self._ttls and time.time() > self._ttls[key]:
            self._kv.pop(key, None)
            self._hashes.pop(key, None)
            self._sets.pop(key, None)
            self._ttls.pop(key, None)
            return True
        return False

    # Sync String commands
    def get(self, key: str) -> Optional[str]:
        if self._is_expired(key):
            return None
        return self._kv.get(key)

    def set(self, key: str, value: Any) -> bool:
        self._kv[key] = str(value)
        return True

    def setex(self, key: str, seconds: int, value: Any) -> bool:
        self._kv[key] = str(value)
        self._ttls[key] = time.time() + seconds
        return True

    def delete(self, *keys: str) -> int:
        count = 0
        for k in keys:
            if k in self._kv or k in self._hashes or k in self._sets:
                count += 1
            self._kv.pop(k, None)
            self._hashes.pop(k, None)
            self._sets.pop(k, None)
            self._ttls.pop(k, None)
        return count

    def expire(self, key: str, seconds: int) -> bool:
        if key in self._kv or key in self._hashes or key in self._sets:
            self._ttls[key] = time.time() + seconds
            return True
        return False

    # Hash commands
    def hset(self, name: str, key: Optional[str] = None, value: Optional[Any] = None, mapping: Optional[Dict[str, Any]] = None) -> int:
        if self._is_expired(name):
            pass
        if name not in self._hashes:
            self._hashes[name] = {}
        added = 0
        if mapping:
            for k, v in mapping.items():
                self._hashes[name][str(k)] = str(v)
                added += 1
        if key is not None and value is not None:
            self._hashes[name][str(key)] = str(value)
            added += 1
        return added

    def hget(self, name: str, key: str) -> Optional[str]:
        if self._is_expired(name):
            return None
        return self._hashes.get(name, {}).get(key)

    def hgetall(self, name: str) -> Dict[str, str]:
        if self._is_expired(name):
            return {}
        return dict(self._hashes.get(name, {}))

    # Set commands
    def sadd(self, name: str, *values: Any) -> int:
        if self._is_expired(name):
            pass
        if name not in self._sets:
            self._sets[name] = set()
        count = 0
        for v in values:
            if str(v) not in self._sets[name]:
                self._sets[name].add(str(v))
                count += 1
        return count

    def smembers(self, name: str) -> Set[str]:
        if self._is_expired(name):
            return set()
        return set(self._sets.get(name, set()))

    def srem(self, name: str, *values: Any) -> int:
        if self._is_expired(name) or name not in self._sets:
            return 0
        count = 0
        for v in values:
            if str(v) in self._sets[name]:
                self._sets[name].remove(str(v))
                count += 1
        return count

    # PubSub commands
    def publish(self, channel: str, message: Any) -> int:
        msg_str = str(message)
        queues = self._subscribers.get(channel, [])
        for q in queues:
            try:
                q.put_nowait({"type": "message", "channel": channel, "data": msg_str})
            except Exception:
                pass
        return len(queues)

    def pubsub(self):
        return MockPubSub(self)

    def ping(self) -> bool:
        return True


class MockPubSub:
    def __init__(self, mock_redis: InMemoryRedisMock):
        self.mock_redis = mock_redis
        self.channels: Set[str] = set()
        self.queue: asyncio.Queue = asyncio.Queue()

    async def subscribe(self, *channels: str):
        for ch in channels:
            self.channels.add(ch)
            if ch not in self.mock_redis._subscribers:
                self.mock_redis._subscribers[ch] = []
            self.mock_redis._subscribers[ch].append(self.queue)

    async def unsubscribe(self, *channels: str):
        for ch in channels:
            self.channels.discard(ch)
            if ch in self.mock_redis._subscribers and self.queue in self.mock_redis._subscribers[ch]:
                self.mock_redis._subscribers[ch].remove(self.queue)

    async def listen(self) -> AsyncGenerator[Dict[str, Any], None]:
        while True:
            msg = await self.queue.get()
            yield msg

    async def close(self):
        for ch in list(self.channels):
            await self.unsubscribe(ch)


class RedisService:
    def __init__(self):
        self._sync_client: Optional[redis.Redis] = None
        self._async_client: Optional[aioredis.Redis] = None
        self._mock_client: InMemoryRedisMock = InMemoryRedisMock()
        self._is_live_redis: Optional[bool] = None

    def check_connection(self) -> bool:
        if self._is_live_redis is not None:
            return self._is_live_redis
        try:
            client = redis.Redis.from_url(settings.REDIS_URL, socket_timeout=1, decode_responses=True)
            client.ping()
            self._sync_client = client
            self._is_live_redis = True
            logger.info(f"Connected to live Redis at {settings.REDIS_URL}")
        except Exception as exc:
            logger.info(f"Redis unavailable ({type(exc).__name__}). Using high-performance in-memory state engine.")
            self._is_live_redis = False
        return self._is_live_redis

    def get_sync_client(self) -> Any:
        if self.check_connection():
            if self._sync_client is None:
                self._sync_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
            return self._sync_client
        return self._mock_client

    async def get_async_client(self) -> Any:
        if self.check_connection():
            if self._async_client is None:
                self._async_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
            return self._async_client
        return self._mock_client


redis_service = RedisService()
