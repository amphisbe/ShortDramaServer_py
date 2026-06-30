from datetime import datetime, timezone


def _utcnow() -> datetime:
    """返回 UTC 时区的当前时间（替代已废弃的 datetime.utcnow）。"""
    return datetime.now(timezone.utc)


from peewee import (
    BigAutoField,
    BigIntegerField,
    BooleanField,
    CharField,
    DateTimeField,
    ForeignKeyField,
    IntegerField,
    Model,
    TextField,
)

from app.db.database import database_proxy


class BaseModel(Model):
    created_at = DateTimeField(default=_utcnow)
    updated_at = DateTimeField(default=_utcnow)
    
    def save(self, *args, **kwargs):
        self.updated_at = _utcnow()
        return super().save(*args, **kwargs)
    
    class Meta:
        database = database_proxy


class User(BaseModel):
    id = BigAutoField()
    external_user_id = CharField(max_length=24, unique=True, index=True)
    nickname = CharField(max_length=100, default="")
    avatar_url = CharField(max_length=1024, default="")
    status = IntegerField(default=1, index=True)

    class Meta:
        table_name = "users"


class Drama(BaseModel):
    id = BigAutoField()
    external_drama_id = CharField(max_length=24, null=True, unique=True)
    title = CharField(max_length=255, default="")
    lang = CharField(max_length=255, default="en")
    description = TextField(default="")
    category = CharField(max_length=50, default="推荐", index=True)
    tags = TextField(default="[]")
    display_author_name = CharField(max_length=100, default="")
    author_user = ForeignKeyField(User, backref="dramas", column_name="author_user_id")
    total_episodes = IntegerField(default=0)
    cover_url = CharField(max_length=1024, default="")
    banner_url = CharField(max_length=1024, default="")
    vip_free = BooleanField(default=True)
    play_count = BigIntegerField(default=0)
    follow_count = BigIntegerField(default=0)
    status = IntegerField(default=1, index=True)
    hot = IntegerField(default=0)

    class Meta:
        table_name = "dramas"


class DramaEpisode(BaseModel):
    id = BigAutoField()
    drama = ForeignKeyField(Drama, backref="episodes", column_name="drama_id")
    external_video_id = CharField(max_length=24, unique=True, index=True)
    episode_no = IntegerField()
    title = CharField(max_length=500, default="")
    play_url = CharField(max_length=1024)
    poster_url = CharField(max_length=1024, default="")
    duration_seconds = IntegerField(default=0)
    sort_order = IntegerField(default=0, index=True)
    status = IntegerField(default=1, index=True)

    # 下列字段用于严格还原 data.json 中分集级别的前端展示配置。
    # 字段命名保持 Python snake_case，接口组装时转换为样例要求的 camelCase / 原始拼写。
    display_nickname = CharField(max_length=100, default="")
    loop = BooleanField(default=True)
    play_ing = BooleanField(default=False)
    muted = BooleanField(default=False)
    is_playing = BooleanField(default=False)
    show_title_arrow = BooleanField(default=True)
    show_look_all_btn = BooleanField(default=True)
    look_all_btn_text = CharField(max_length=255, default="")
    show_bottom_area = BooleanField(default=False)
    bottom_area_btn_text = CharField(max_length=255, default="")
    tool_info_json = TextField(default="")

    class Meta:
        table_name = "drama_episodes"
        indexes = ((("drama", "episode_no"), True),)


class DramaEpisodeStat(BaseModel):
    episode = ForeignKeyField(DramaEpisode, primary_key=True, backref="stat", column_name="episode_id")
    like_count = IntegerField(default=0)
    comment_count = IntegerField(default=0)
    share_count = IntegerField(default=0)
    play_count = BigIntegerField(default=0)
    favorite_count = IntegerField(default=0)

    class Meta:
        table_name = "drama_episode_stats"


class UserFollow(BaseModel):
    id = BigAutoField()
    follower_user = ForeignKeyField(User, backref="following", column_name="follower_user_id")
    followed_user = ForeignKeyField(User, backref="followers", column_name="followed_user_id")

    class Meta:
        table_name = "users_follows"
        indexes = ((("follower_user", "followed_user"), True),)


class UserEpisodeLike(BaseModel):
    id = BigAutoField()
    user = ForeignKeyField(User, backref="episode_likes", column_name="user_id")
    episode = ForeignKeyField(DramaEpisode, backref="user_likes", column_name="episode_id")

    class Meta:
        table_name = "users_episode_likes"
        indexes = ((("user", "episode"), True),)


class UserDramaFavorite(BaseModel):
    id = BigAutoField()
    user = ForeignKeyField(User, backref="drama_favorites", column_name="user_id")
    drama = ForeignKeyField(Drama, backref="user_favorites", column_name="drama_id")

    class Meta:
        table_name = "users_drama_favorites"
        indexes = ((("user", "drama"), True),)


class UserEpisodeProgress(BaseModel):
    id = BigAutoField()
    user = ForeignKeyField(User, backref="episode_progress", column_name="user_id")
    episode = ForeignKeyField(DramaEpisode, backref="user_progress", column_name="episode_id")
    position_seconds = IntegerField(default=0)
    is_finished = BooleanField(default=False)

    class Meta:
        table_name = "users_episode_progress"
        indexes = ((("user", "episode"), True),)


class EpisodeComment(BaseModel):
    id = BigAutoField()
    episode = ForeignKeyField(DramaEpisode, backref="comments", column_name="episode_id")
    user = ForeignKeyField(User, backref="comments", column_name="user_id")
    content = TextField()
    status = IntegerField(default=1, index=True)

    class Meta:
        table_name = "episode_comments"


class EpisodeShare(BaseModel):
    id = BigAutoField()
    episode = ForeignKeyField(DramaEpisode, backref="shares", column_name="episode_id")
    user = ForeignKeyField(User, backref="shares", column_name="user_id", null=True)
    channel = CharField(max_length=50, default="unknown")

    class Meta:
        table_name = "episode_shares"
