import logging
from pathlib import Path
from typing import Iterable

from fastapi import FastAPI, Request
from peewee import Database, MySQLDatabase, Proxy, SqliteDatabase
from playhouse.pool import PooledMySQLDatabase

from app.core.config import Settings, get_settings

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
    _migrate_drama_episodes()
    _migrate_dramas()


def _get_existing_columns(table_name: str) -> set[str]:
    try:
        return {column.name for column in database_proxy.get_columns(table_name)}
    except Exception as exc:
        logger.warning("检查 %s 表字段失败：%s", table_name, exc)
        return set()


def _migrate_drama_episodes() -> None:
    existing = _get_existing_columns("drama_episodes")
    settings = get_settings()

    if settings.db_driver == "mysql":
        col_defs = {
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
        ql, qr = "`", "`"
    else:
        col_defs = {
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
        ql, qr = '"', '"'

    for col_name, definition in col_defs.items():
        if col_name in existing:
            continue
        sql = f"ALTER TABLE drama_episodes ADD COLUMN {ql}{col_name}{qr} {definition}"
        database_proxy.execute_sql(sql)
        logger.info("已补齐 drama_episodes.%s 字段", col_name)


def _migrate_dramas() -> None:
    existing = _get_existing_columns("dramas")
    settings = get_settings()

    if settings.db_driver == "mysql":
        col_defs = {
            "description": "TEXT NOT NULL DEFAULT ('')",
            "category": "VARCHAR(50) NOT NULL DEFAULT '推荐'",
            "tags": "TEXT NOT NULL DEFAULT ('[]')",
            "play_count": "BIGINT NOT NULL DEFAULT 0",
            "follow_count": "BIGINT NOT NULL DEFAULT 0",
        }
        ql, qr = "`", "`"
    else:
        col_defs = {
            "description": "TEXT NOT NULL DEFAULT ''",
            "category": "VARCHAR(50) NOT NULL DEFAULT '推荐'",
            "tags": "TEXT NOT NULL DEFAULT '[]'",
            "play_count": "INTEGER NOT NULL DEFAULT 0",
            "follow_count": "INTEGER NOT NULL DEFAULT 0",
        }
        ql, qr = '"', '"'

    for col_name, definition in col_defs.items():
        if col_name in existing:
            continue
        sql = f"ALTER TABLE dramas ADD COLUMN {ql}{col_name}{qr} {definition}"
        database_proxy.execute_sql(sql)
        logger.info("已补齐 dramas.%s 字段", col_name)


def initialize_runtime(create_schema: bool = False, seed: bool = False) -> None:
    '''项目一键初始化入口。

    使用 Peewee connection_context 管理连接生命周期，建表和种子数据
    完成后自动释放连接。其他脚本、测试与 Web 入口都可以复用该函数。
    '''

    db = initialize_database()
    with db.connection_context():
        if create_schema:
            from app.models import ALL_MODELS

            create_tables(ALL_MODELS)
            logger.info("数据库表结构已创建或已存在")

        if seed:
            from app.db.seed import seed_demo_data

            seed_demo_data()
            logger.info("Demo 种子数据已初始化")


def setup_db_middleware(app: FastAPI) -> None:
    """为每个 HTTP 请求添加数据库连接上下文管理。

    使用 Peewee 的 connection_context：请求进入时从连接池获取连接，
    请求结束后（正常或异常）自动释放回池，从根本上杜绝连接泄漏导致
    的 MaxConnectionsExceeded。
    """

    @app.middleware("http")
    async def db_connection_middleware(request: Request, call_next):
        db = database_proxy.obj
        if db is None or db.is_closed():
            db = initialize_database()
        with db.connection_context():
            response = await call_next(request)
        return response
