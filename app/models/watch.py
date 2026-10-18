"""真实观看时长统计表（docs/watch-time-statistics-design.md 6.1）。

user / episode 关联沿用 UserTagWeight 的做法：保留 ORM 关系但不建物理外键（_deferred=True），
避免旧 MySQL users.id(INT) 与模型 BIGINT 的类型冲突；归属由已鉴权的服务层校验。
新表由启动时 create_tables(ALL_MODELS, safe=True) 自动创建，无需 ALTER。
内部时长统一用整数毫秒。started_at / last_received_at 存 naive UTC。
"""

from peewee import (
    BigAutoField,
    BigIntegerField,
    BooleanField,
    CharField,
    DateField,
    DateTimeField,
    ForeignKeyField,
    IntegerField,
)

from app.models.drama import BaseModel, DramaEpisode, User


class UserWatchSession(BaseModel):
    id = BigAutoField()
    # 签名会话 ID 中的随机 nonce（完整 ws1.<payload>.<sig> 超过 64 字符，不落库）
    session_id = CharField(max_length=64, unique=True)
    user = ForeignKeyField(User, backref="watch_sessions", column_name="user_id",
                           _deferred=True, lazy_load=False, index=False)
    episode = ForeignKeyField(DramaEpisode, backref="watch_sessions", column_name="episode_id",
                              _deferred=True, lazy_load=False)
    last_seq = IntegerField(default=0)
    # 客户端声称的累计时长（最大值）与服务端承认的累计时长，差值供日志告警
    reported_ms = BigIntegerField(default=0)
    accepted_ms = BigIntegerField(default=0)
    last_position_ms = BigIntegerField(default=0)
    started_at = DateTimeField()
    last_received_at = DateTimeField(null=True)

    class Meta:
        table_name = "user_watch_sessions"
        indexes = ((("user", "last_received_at"), False),)


class UserEpisodeWatchDaily(BaseModel):
    id = BigAutoField()
    user = ForeignKeyField(User, backref="episode_watch_daily", column_name="user_id",
                           _deferred=True, lazy_load=False, index=False)
    episode = ForeignKeyField(DramaEpisode, backref="user_watch_daily", column_name="episode_id",
                              _deferred=True, lazy_load=False)
    stat_date = DateField()  # UTC 日期
    watch_ms = BigIntegerField(default=0)
    credited_ms = BigIntegerField(default=0)
    play_counted = BooleanField(default=False)

    class Meta:
        table_name = "user_episode_watch_daily"
        indexes = ((("user", "episode", "stat_date"), True),)


class UserWatchDaily(BaseModel):
    id = BigAutoField()
    user = ForeignKeyField(User, backref="watch_daily", column_name="user_id",
                           _deferred=True, lazy_load=False, index=False)
    stat_date = DateField()  # UTC 日期
    watch_ms = BigIntegerField(default=0)
    play_count = IntegerField(default=0)

    class Meta:
        table_name = "user_watch_daily"
        indexes = ((("user", "stat_date"), True),)


WATCH_MODELS = [UserWatchSession, UserEpisodeWatchDaily, UserWatchDaily]