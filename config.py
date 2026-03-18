from dataclasses import dataclass
from environs import Env


@dataclass
class Bot:
    """Настройки Telegram-бота."""
    token: str


@dataclass
class Database:
    """Параметры подключения к PostgreSQL."""
    name: str
    user: str
    password: str
    host: str


@dataclass
class Redis:
    """Параметры подключения к Redis."""
    host: str
    port: int


@dataclass
class Rabbit:
    """Параметры подключения к RabbitMQ."""
    url: str
    queue: str


@dataclass
class Config:
    """Корневая конфигурация приложения."""
    bot: Bot
    dbase: Database
    redis: Redis
    rabbit: Rabbit


def load_config(path: str | None = None) -> Config:
    """Собирает конфигурацию приложения из переменных окружения."""
    env = Env()
    env.read_env(path)
    return Config(
        bot=Bot(token=env.str("TOKEN")),
        dbase=Database(
            name=env.str("DBASE_NAME"),
            user=env.str("DBASE_USER"),
            password=env.str("DBASE_PASSWORD"),
            host=env.str("DBASE_HOST"),
        ),
        redis=Redis(
            host=env.str("REDIS_HOST"),
            port=env.str("REDIS_PORT")
        ),
        rabbit=Rabbit(
            url=env.str("RABBIT_URL"),
            queue=env.str("RABBIT_QUEUE", "aida"),
        ),
    )
