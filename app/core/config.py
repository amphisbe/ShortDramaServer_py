from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用运行配置。

    Demo 默认使用 SQLite，便于本地快速启动；当 DB_DRIVER=mysql 时，Peewee 会使用
    MySQLDatabase 连接真实 MySQL。该设计便于开发阶段快速验证接口，生产阶段平滑切换。
    """

    app_name: str = Field(default="Short Drama FastAPI Server", alias="APP_NAME")
    app_env: str = Field(default="local", alias="APP_ENV")
    app_debug: bool = Field(default=True, alias="APP_DEBUG")
    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    db_driver: Literal["sqlite", "mysql"] = Field(default="sqlite", alias="DB_DRIVER")
    sqlite_database: str = Field(default="./runtime/short_drama_demo.db", alias="SQLITE_DATABASE")

    mysql_host: str = Field(default="127.0.0.1", alias="MYSQL_HOST")
    mysql_port: int = Field(default=3306, alias="MYSQL_PORT")
    mysql_database: str = Field(default="short_drama", alias="MYSQL_DATABASE")
    mysql_user: str = Field(default="root", alias="MYSQL_USER")
    mysql_password: str = Field(default="", alias="MYSQL_PASSWORD")
    mysql_charset: str = Field(default="utf8mb4", alias="MYSQL_CHARSET")
    mysql_max_connections: int = Field(default=32, alias="MYSQL_MAX_CONNECTIONS")
    mysql_stale_timeout: int = Field(default=300, alias="MYSQL_STALE_TIMEOUT")

    static_host: str = Field(default="https://v.shortdramago.win", alias="STATIC_HOST")
    static_img: str = Field(default="./static/img", alias="STATIC_IMG")
    static_demo: str = Field(default="./static/demo", alias="STATIC_DEMO")
    video_mode: Literal["demo", "online"] = Field(default="demo", alias="VIDEO_MODE")
    video_list: str = Field(default="", alias="VIDEO_LIST")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def sqlite_database_path(self) -> Path:
        return Path(self.sqlite_database).expanduser().resolve()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
