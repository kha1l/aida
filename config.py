"""Конфигурация `aida3`, собираемая из переменных окружения."""

from dataclasses import dataclass
from environs import Env


@dataclass
class Bot:
    """Настройки Telegram-бота."""
    token: str
    proxy_url: str | None = None


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
class Dagster:
    """Параметры запуска Dagster job через GraphQL."""
    graphql_url: str | None
    repository_location_name: str | None
    repository_name: str
    auth_header_name: str | None
    auth_header_value: str | None
    request_timeout_seconds: int


@dataclass
class WebApp:
    """Параметры web-отчетов, открываемых из Telegram-кнопок."""
    report_url: str | None
    direct_link_url: str | None
    signing_secret: str | None
    link_ttl_seconds: int


@dataclass
class Config:
    """Корневая конфигурация приложения."""
    bot: Bot
    dbase: Database
    redis: Redis
    rabbit: Rabbit
    dagster: Dagster
    webapp: WebApp


def load_config(path: str | None = None) -> Config:
    """Собирает конфигурацию приложения из переменных окружения."""
    env = Env()
    env.read_env(path)
    telegram_proxy_url = env.str("TELEGRAM_PROXY_URL", "").strip() or env.str("BOT_PROXY_URL", "").strip() or None
    return Config(
        bot=Bot(token=env.str("TOKEN"), proxy_url=telegram_proxy_url),
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
        dagster=Dagster(
            graphql_url=env.str("DAGSTER_GRAPHQL_URL", "").strip() or None,
            repository_location_name=env.str("DAGSTER_REPOSITORY_LOCATION", "").strip() or None,
            repository_name=env.str("DAGSTER_REPOSITORY_NAME", "__repository__"),
            auth_header_name=env.str("DAGSTER_AUTH_HEADER_NAME", "").strip() or None,
            auth_header_value=env.str("DAGSTER_AUTH_HEADER_VALUE", "").strip() or None,
            request_timeout_seconds=env.int("DAGSTER_REQUEST_TIMEOUT_SECONDS", 15),
        ),
        webapp=WebApp(
            report_url=env.str("AIDA_REPORT_WEBAPP_URL", "").strip() or None,
            direct_link_url=env.str("AIDA_REPORT_WEBAPP_DIRECT_URL", "").strip().rstrip("/") or None,
            signing_secret=env.str("AIDA_WEBAPP_SIGNING_SECRET", "").strip() or None,
            link_ttl_seconds=env.int("AIDA_WEBAPP_LINK_TTL_SECONDS", 3600),
        ),
    )
