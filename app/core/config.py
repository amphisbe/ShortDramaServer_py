from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
from dotenv import load_dotenv
load_dotenv(_PROJECT_ROOT / ".env", override=True)


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
    mysql_pool_timeout: int = Field(default=5, alias="MYSQL_POOL_TIMEOUT")

    static_host: str = Field(default="https://v.shortdramago.win", alias="STATIC_HOST")
    static_img: str = Field(default="./static/img", alias="STATIC_IMG")
    static_demo: str = Field(default="./static/demo", alias="STATIC_DEMO")
    video_mode: Literal["demo", "online"] = Field(default="demo", alias="VIDEO_MODE")
    video_list: str = Field(default="", alias="VIDEO_LIST")
    google_web_client_id: str = Field(default="", alias="GOOGLE_WEB_CLIENT_ID")
    jwt_secret: str = Field(default="change-me-in-production", alias="JWT_SECRET")
    jwt_expire_seconds: int = Field(default=60 * 60 * 24 * 30, alias="JWT_EXPIRE_SECONDS")
    # 管理接口（/api/v1/admin/*）令牌，请求头 X-Admin-Token；为空时管理接口禁用
    admin_token: str = Field(default="", alias="ADMIN_TOKEN")

    # 真实观看时长统计（docs/watch-time-statistics-design.md）
    # 会话签名密钥，为空时复用 JWT_SECRET
    watch_session_secret: str = Field(default="", alias="WATCH_SESSION_SECRET")
    # 关闭时 watch 接口返回 code 0 且增量 0
    watch_events_enabled: bool = Field(default=True, alias="WATCH_EVENTS_ENABLED")
    # 同一用户·分集·UTC 日累计观看达到 min(该值, 分集时长) 秒计一次播放
    watch_play_threshold_seconds: int = Field(default=5, alias="WATCH_PLAY_THRESHOLD_SECONDS")
    # 分集时长未知（duration_seconds=0）时的当集日上限
    watch_unknown_duration_cap_seconds: int = Field(default=1800, alias="WATCH_UNKNOWN_DURATION_CAP_SECONDS")
    watch_user_daily_cap_seconds: int = Field(default=43200, alias="WATCH_USER_DAILY_CAP_SECONDS")
    # 会话超过该秒数无上报即过期（410）
    watch_session_idle_seconds: int = Field(default=1800, alias="WATCH_SESSION_IDLE_SECONDS")
    watch_session_max_age_seconds: int = Field(default=21600, alias="WATCH_SESSION_MAX_AGE_SECONDS")
    # 单进程内存限流：同一用户每分钟最多创建会话数
    watch_session_create_per_min: int = Field(default=30, alias="WATCH_SESSION_CREATE_PER_MIN")

    model_config = SettingsConfigDict(
        env_file=str(_PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def sqlite_database_path(self) -> Path:
        return Path(self.sqlite_database).expanduser().resolve()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    s = Settings()
    # 启动时打印关键配置，便于排查是否读到了错误的 .env 或环境变量
    import logging
    logger = logging.getLogger(__name__)
    logger.info(
        "配置加载完成: DB_DRIVER=%s, MYSQL_HOST=%s, MYSQL_PORT=%s, MYSQL_DATABASE=%s, "
        "APP_PORT=%s, VIDEO_MODE=%s, env_file=%s",
        s.db_driver, s.mysql_host, s.mysql_port, s.mysql_database,
        s.app_port, s.video_mode, _PROJECT_ROOT / ".env",
    )
    return s
