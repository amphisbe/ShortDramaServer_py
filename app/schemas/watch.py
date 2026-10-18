"""观看统计接口请求体（docs/watch-time-statistics-design.md 5.1 / 5.2）。"""

from pydantic import BaseModel, ConfigDict, Field


class WatchSessionIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    video_id: str = Field(min_length=1, max_length=64)


class WatchEventIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    session_id: str = Field(min_length=1, max_length=512)
    seq: int = Field(ge=1, le=100000)
    video_id: str = Field(min_length=1, max_length=64)
    # 本会话累计观看秒数（不是增量）
    watched_seconds: float = Field(ge=0, le=21600, allow_inf_nan=False)
    position_seconds: float = Field(default=0, ge=0, le=604800, allow_inf_nan=False)
    is_finished: bool = False