# redis_utils.py

import redis
from threading import Lock

class RedisSingleton:
    """
    Singleton class to manage a Redis connection.

    This ensures only one connection to Redis exists throughout the application.
    """

    _instance = None
    _lock = Lock()

    def __new__(cls, host='localhost', port=6379, db=0, password='redis2024'):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super(RedisSingleton, cls).__new__(cls)
                    cls._instance._initialize(host, port, db, password)
        return cls._instance

    def _initialize(self, host, port, db, password):
        self._client = redis.StrictRedis(
            host=host,
            port=port,
            db=db,
            password=password,
            decode_responses=True
        )

    @property
    def client(self):
        """Get the Redis client instance."""
        return self._client


class RedisUtils:
    """
    Wrapper class for Redis operations.

    Provides methods for common Redis tasks, such as setting, getting, deleting, and
    checking the existence of keys.
    """

    def __init__(self, host='localhost', port=6379, db=0, password=None):
        self.redis = RedisSingleton(host, port, db, password).client

    def set_key(self, key, value, expire=None):
        """
        Set a key-value pair in Redis with optional expiration time.

        :param key: Redis key
        :param value: Value to store
        :param expire: Expiration time in seconds (optional)
        :return: Boolean indicating if the operation was successful
        """
        return self.redis.set(key, value, ex=expire)

    def get_key(self, key):
        """
        Retrieve a value by key from Redis.

        :param key: Redis key
        :return: Value of the key, or None if key does not exist
        """
        return self.redis.get(key)

    def delete_key(self, key):
        """
        Delete a key from Redis.

        :param key: Redis key to delete
        :return: Number of keys deleted (0 if the key does not exist)
        """
        return self.redis.delete(key)

    def exists_key(self, key):
        """
        Check if a key exists in Redis.

        :param key: Redis key to check
        :return: Boolean indicating if the key exists
        """
        return self.redis.exists(key) == 1

    def increment_key(self, key, amount=1):
        """
        Increment a key's value in Redis by a specified amount.

        :param key: Redis key
        :param amount: Amount to increment by (default is 1)
        :return: New value after increment, or None if the key does not exist
        """
        return self.redis.incr(key, amount)

    def set_hash(self, name, key, value):
        """
        Set a field in a Redis hash.

        :param name: Name of the hash
        :param key: Field key within the hash
        :param value: Value to set for the field
        :return: Boolean indicating if the operation was successful
        """
        return self.redis.hset(name, key, value)

    def get_hash(self, name, key):
        """
        Get a field value from a Redis hash.

        :param name: Name of the hash
        :param key: Field key within the hash
        :return: Value of the field, or None if field or hash does not exist
        """
        return self.redis.hget(name, key)

    def delete_hash_field(self, name, key):
        """
        Delete a field from a Redis hash.

        :param name: Name of the hash
        :param key: Field key within the hash to delete
        :return: Boolean indicating if the field was deleted
        """
        return self.redis.hdel(name, key) == 1

    def get_all_hash(self, name):
        """
        Get all fields and values from a Redis hash.

        :param name: Name of the hash
        :return: Dictionary of all fields and values, or None if hash does not exist
        """
        return self.redis.hgetall(name)

    def list_all_keys(self, pattern='*'):
        """
        List all keys in Redis that match a specific pattern.

        :param pattern: Pattern to match keys against (default is '*' to match all keys)
        :return: List of keys matching the pattern
        """
        return self.redis.keys(pattern)

    def get_list_length(self, key):
        """
        Get the number of elements in a Redis list.

        :param key: Redis list key
        :return: Integer representing the number of elements in the list, or 0 if the list does not exist
        """
        return self.redis.llen(key)


# Example usage:
# redis_util = RedisUtils(host='localhost', port=6379, db=0, password=None)
# redis_util.set_key('test_key', 'test_value')
# print(redis_util.get_key('test_key'))
