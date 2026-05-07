import logging
from pathlib import Path
from typing import Iterable

from peewee import Database, MySQLDatabase, Proxy, SqliteDatabase
from playhouse.pool import PooledMySQLDatabase

from app.core.config import Settings, get_settings
from app.core.logging import setup_logging

logger = logging.getLogger(__name__)

database_proxy: Proxy = Proxy()


def build_database(settings: Settings | None = None) -> Database:
    """根据环境变量创建 Peewee 数据库对象。

    Demo 默认使用 SQLite，便于无 MySQL 环境直接运行；生产环境使用 MySQL 时，设置
    DB_DRIVER=mysql 即可切换到 PooledMySQLDatabase。
    """

    settings = settings or get_settings()

    if settings.db_driver == "mysql":
        return PooledMySQLDatabase(
            settings.mysql_database,
            user=settings.mysql_user,
            password=settings.mysql_password,
            host=settings.mysql_host,
            port=settings.mysql_port,
            charset=settings.mysql_charset,
            max_connections=settings.mysql_max_connections,
            stale_timeout=settings.mysql_stale_timeout,
        )

    sqlite_path: Path = settings.sqlite_database_path
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    return SqliteDatabase(
        sqlite_path,
        pragmas={
            "journal_mode": "wal",
            "foreign_keys": 1,
            "cache_size": -64 * 1000,
        },
    )


def initialize_database(settings: Settings | None = None) -> Database:
    """初始化数据库代理并返回数据库实例。"""

    settings = settings or get_settings()
    if database_proxy.obj is None:
        database = build_database(settings)
        database_proxy.initialize(database)
        logger.info("数据库代理已初始化，driver=%s", settings.db_driver)
    return database_proxy.obj


def connect_database() -> None:
    """按需打开数据库连接。"""

    database = initialize_database()
    if database.is_closed():
        database.connect(reuse_if_open=True)


def close_database() -> None:
    """按需关闭数据库连接。"""

    if database_proxy.obj is not None and not database_proxy.obj.is_closed():
        database_proxy.obj.close()


def create_tables(models: Iterable[type]) -> None:
    """创建数据表。"""

    connect_database()
    database_proxy.create_tables(list(models), safe=True)


def initialize_runtime(create_schema: bool = False, seed: bool = False) -> None:
    """项目一键初始化入口。

    该函数符合项目偏好的“一键初始化”方式：统一完成日志、配置、数据库代理、连接、建表与
    可选种子数据。其他脚本、测试与 Web 入口都可以复用该函数。
    """

    settings = get_settings()
    setup_logging(settings.log_level)
    initialize_database(settings)
    connect_database()

    if create_schema:
        from app.models import ALL_MODELS

        create_tables(ALL_MODELS)
        logger.info("数据库表结构已创建或已存在")

    if seed:
        from app.db.seed import seed_demo_data

        seed_demo_data()
        logger.info("Demo 种子数据已初始化")
