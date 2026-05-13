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
    ensure_demo_schema_compatibility()


def ensure_demo_schema_compatibility() -> None:
    """补齐早期 Demo SQLite/MySQL 表结构中缺失的分集展示字段。

    Peewee 的 safe=True 只会创建不存在的表，不会修改已存在表。为了让用户在本地旧库上
    直接执行 init_db.py 也能升级到 data.json 对齐版，这里用最小 ALTER TABLE 语句补齐
    新增字段。生产环境仍建议使用正式迁移工具管理 schema 变更。
    """

    connect_database()
    try:
        existing_columns = {column.name for column in database_proxy.get_columns("drama_episodes")}
    except Exception as exc:  # pragma: no cover - 数据库驱动差异下的保护性日志
        logger.warning("检查 drama_episodes 表字段失败，跳过兼容迁移：%s", exc)
        return

    settings = get_settings()
    if settings.db_driver == "mysql":
        column_definitions = {
            "display_nickname": "VARCHAR(100) NOT NULL DEFAULT ''",
            "loop": "TINYINT(1) NOT NULL DEFAULT 1",
            "play_ing": "TINYINT(1) NOT NULL DEFAULT 0",
            "muted": "TINYINT(1) NOT NULL DEFAULT 0",
            "is_playing": "TINYINT(1) NOT NULL DEFAULT 0",
            "show_title_arrow": "TINYINT(1) NOT NULL DEFAULT 1",
            "show_look_all_btn": "TINYINT(1) NOT NULL DEFAULT 1",
            "look_all_btn_text": "VARCHAR(255) NOT NULL DEFAULT ''",
            "show_bottom_area": "TINYINT(1) NOT NULL DEFAULT 0",
            "bottom_area_btn_text": "VARCHAR(255) NOT NULL DEFAULT ''",
            "tool_info_json": "TEXT NOT NULL",
        }
        quote_left, quote_right = "`", "`"
    else:
        column_definitions = {
            "display_nickname": "VARCHAR(100) NOT NULL DEFAULT ''",
            "loop": "INTEGER NOT NULL DEFAULT 1",
            "play_ing": "INTEGER NOT NULL DEFAULT 0",
            "muted": "INTEGER NOT NULL DEFAULT 0",
            "is_playing": "INTEGER NOT NULL DEFAULT 0",
            "show_title_arrow": "INTEGER NOT NULL DEFAULT 1",
            "show_look_all_btn": "INTEGER NOT NULL DEFAULT 1",
            "look_all_btn_text": "VARCHAR(255) NOT NULL DEFAULT ''",
            "show_bottom_area": "INTEGER NOT NULL DEFAULT 0",
            "bottom_area_btn_text": "VARCHAR(255) NOT NULL DEFAULT ''",
            "tool_info_json": "TEXT NOT NULL DEFAULT ''",
        }
        quote_left, quote_right = '"', '"'

    for column_name, definition in column_definitions.items():
        if column_name in existing_columns:
            continue
        sql = f"ALTER TABLE drama_episodes ADD COLUMN {quote_left}{column_name}{quote_right} {definition}"
        database_proxy.execute_sql(sql)
        logger.info("已补齐 drama_episodes.%s 字段", column_name)


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
