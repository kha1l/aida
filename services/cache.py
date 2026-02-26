from redis.asyncio import Redis
from config import Config, load_config

class RedisCache:

    def __init__(self, db: int):
        self.cfg: Config = load_config()
        self.db = db
        self.redis = Redis(
            host=self.cfg.redis.host,
            port=self.cfg.redis.port,
            decode_responses=True,
            db=self.db
        )

    def get_redis(self):
        return self.redis
