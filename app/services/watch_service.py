"""真实观看时长统计（docs/watch-time-statistics-design.md）。

- 会话签发/验签：session_id = "ws1.<base64url(payload)>.<base64url(HMAC-SHA256 截断 16 字节)>"，
  payload = {u: 用户 external_id, e: episode.id, t: 创建秒, n: 随机 8 字节 hex}；库里只存 n。
- report_event：单事务内 会话 -> 用户日 -> 分集日 固定顺序加锁，服务端判定增量上限、日上限、播放计数。
- 内部统一整数毫秒，接口对外秒（1 位小数）；统计日按 UTC。
- 会话创建限流为单进程内存实现（部署为单实例）。
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import secrets
import threading
from collections import deque
from datetime import date, datetime, timedelta, timezone
from typing import Any

from peewee import IntegrityError, SqliteDatabase, fn

from app.core.config import get_settings
from app.db.database import initialize_database
from app.models import (
    Drama,
    DramaEpisode,
    DramaEpisodeStat,
    User,
    UserEpisodeWatchDaily,
    UserWatchDaily,
    UserWatchSession,
)
from app.services import tag_service

logger = logging.getLogger(__name__)

SESSION_PREFIX = "ws1"
# 时间间隔校验的宽限（网络抖动、客户端计时误差）
SLACK_MS = 5000
# 同会话两次处理间隔小于该值视作重复
MIN_PROCESS_INTERVAL_MS = 2000
# 并发会话判定：该用户 30s 内有增量的其他会话 >= 2 个时，本次增量记 0
CONCURRENT_WINDOW_SECONDS = 30
MAX_CONCURRENT_OTHER_SESSIONS = 2
# 清理：last_received_at（无则 started_at）超过该天数的会话
SESSION_RETENTION_DAYS = 30


class WatchError(Exception):
    """业务错误，code 为信封业务码。"""

    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _now() -> datetime:
    """当前 UTC 时间（aware）。测试通过 monkeypatch 本函数推进时间。"""
    return datetime.now(timezone.utc)


def _naive_utc(value: Any) -> datetime | None:
    """统一为 naive UTC（SQLite 可能返回字符串，MySQL 返回 naive datetime）。"""
    if value is None:
        return None
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def _ms_between(later: datetime, earlier: datetime) -> int:
    return int((later - earlier).total_seconds() * 1000)


def _seconds(ms: int | float) -> float:
    return round(float(ms) / 1000.0, 1)


def _is_sqlite() -> bool:
    return isinstance(initialize_database(), SqliteDatabase)


def _for_update(query):
    """仅 MySQL 加 FOR UPDATE；SQLite 不支持该语法（以 IMMEDIATE 事务串行化写入）。"""
    return query if _is_sqlite() else query.for_update()


def _atomic():
    db = initialize_database()
    if isinstance(db, SqliteDatabase):
        # 事务开始即取写锁，避免并发 读->写 升级时 SQLITE_BUSY
        return db.atomic("IMMEDIATE")
    return db.atomic()


# ============ 会话签名 ============


def _secret() -> bytes:
    settings = get_settings()
    return (settings.watch_session_secret or settings.jwt_secret).encode("utf-8")


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64decode(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _sign(signing_input: str) -> str:
    digest = hmac.new(_secret(), signing_input.encode("utf-8"), hashlib.sha256).digest()
    return _b64encode(digest[:16])


def issue_session_token(user_external_id: str, episode_id: int, created_ts: int, nonce: str) -> str:
    payload = json.dumps(
        {"u": user_external_id, "e": int(episode_id), "t": int(created_ts), "n": nonce},
        separators=(",", ":"),
    ).encode("utf-8")
    head = f"{SESSION_PREFIX}.{_b64encode(payload)}"
    return f"{head}.{_sign(head)}"


def parse_session_token(token: str) -> dict[str, Any] | None:
    """验签并解析会话 ID；签名无效或格式错误返回 None。"""
    if not token or len(token) > 512:
        return None
    parts = token.split(".")
    if len(parts) != 3 or parts[0] != SESSION_PREFIX or not parts[1] or not parts[2]:
        return None
    head = f"{parts[0]}.{parts[1]}"
    if not hmac.compare_digest(_sign(head), parts[2]):
        return None
    try:
        claims = json.loads(_b64decode(parts[1]))
    except (ValueError, UnicodeDecodeError):
        return None
    if not isinstance(claims, dict):
        return None
    if not isinstance(claims.get("u"), str) or not isinstance(claims.get("n"), str):
        return None
    if not isinstance(claims.get("e"), int) or not isinstance(claims.get("t"), int):
        return None
    return claims


# ============ 会话创建限流（单进程内存） ============

_create_lock = threading.Lock()
_create_log: dict[str, deque] = {}


def _allow_session_create(user_external_id: str, now_ts: float) -> bool:
    limit = max(1, int(get_settings().watch_session_create_per_min))
    with _create_lock:
        if len(_create_log) > 10000:
            for key in [k for k, q in _create_log.items() if not q or now_ts - q[-1] >= 60]:
                _create_log.pop(key, None)
        log = _create_log.setdefault(user_external_id, deque())
        while log and now_ts - log[0] >= 60:
            log.popleft()
        if len(log) >= limit:
            return False
        log.append(now_ts)
        return True


def reset_rate_limits() -> None:
    with _create_lock:
        _create_log.clear()


# ============ 公共查询 ============


def _active_user(external_user_id: str) -> User:
    user = User.get_or_none((User.external_user_id == external_user_id) & (User.status == 1))
    if user is None:
        raise WatchError(401, "用户不存在或已停用")
    return user


def _episode_cap_ms(duration_ms: int) -> int:
    if duration_ms > 0:
        return duration_ms
    return int(get_settings().watch_unknown_duration_cap_seconds) * 1000


def _play_threshold_ms(duration_ms: int) -> int:
    threshold = int(get_settings().watch_play_threshold_seconds) * 1000
    if duration_ms > 0:
        threshold = min(threshold, duration_ms)
    return threshold


def get_user_watch_totals(user: User) -> dict[str, float]:
    """Profile 用：totalWatchSeconds = SUM(user_watch_daily.watch_ms)，todayWatchSeconds 为当前 UTC 日。"""
    try:
        total = (
            UserWatchDaily.select(fn.COALESCE(fn.SUM(UserWatchDaily.watch_ms), 0))
            .where(UserWatchDaily.user == user.id)
            .scalar()
        )
        today = (
            UserWatchDaily.select(UserWatchDaily.watch_ms)
            .where((UserWatchDaily.user == user.id) & (UserWatchDaily.stat_date == _now().date()))
            .scalar()
        )
    except Exception as exc:  # 统计表异常不影响 Profile 主体
        logger.warning("查询用户观看时长失败 user=%s：%s", user.id, exc)
        total, today = 0, 0
    return {
        "totalWatchSeconds": _seconds(int(total or 0)),
        "todayWatchSeconds": _seconds(int(today or 0)),
    }


# ============ 会话创建 ============


def create_session(external_user_id: str, video_id: str) -> dict[str, Any]:
    settings = get_settings()
    if not settings.watch_events_enabled:
        return {"session_id": "", "expires_in": 0}
    user = _active_user(external_user_id)
    episode = (
        DramaEpisode.select(DramaEpisode, Drama)
        .join(Drama)
        .where(
            (DramaEpisode.external_video_id == video_id)
            & (DramaEpisode.status == 1)
            & (Drama.status == 1)
        )
        .first()
    )
    if episode is None:
        raise WatchError(404, "剧集不存在或已下架")

    now = _now()
    if not _allow_session_create(user.external_user_id, now.timestamp()):
        raise WatchError(429, "创建观看会话过于频繁")

    for _ in range(3):
        nonce = secrets.token_hex(8)
        try:
            UserWatchSession.create(
                session_id=nonce,
                user=user.id,
                episode=episode.id,
                started_at=_naive_utc(now),
            )
            break
        except IntegrityError:
            continue
    else:
        raise WatchError(500, "创建观看会话失败")

    token = issue_session_token(user.external_user_id, episode.id, int(now.timestamp()), nonce)
    return {"session_id": token, "expires_in": int(settings.watch_session_idle_seconds)}


# ============ 上报 ============


def _zero_result(seq: int = 0, accepted_ms: int = 0, play_counted: bool = False) -> dict[str, Any]:
    return {
        "accepted_seq": seq,
        "accepted_watched_seconds": _seconds(accepted_ms),
        "credited_delta_seconds": 0.0,
        "play_counted": play_counted,
    }


def _current_state(session: UserWatchSession, user_id: int, episode_id: int, stat_date: date) -> dict[str, Any]:
    ue = UserEpisodeWatchDaily.get_or_none(
        (UserEpisodeWatchDaily.user == user_id)
        & (UserEpisodeWatchDaily.episode == episode_id)
        & (UserEpisodeWatchDaily.stat_date == stat_date)
    )
    return _zero_result(session.last_seq, session.accepted_ms, bool(ue.play_counted) if ue else False)


def _locked_row(model, where, insert_values: dict[str, Any]):
    """加锁读取统计行；不存在时 INSERT IGNORE 后再读。

    先 SELECT ... FOR UPDATE 再按需插入：行已存在时不走 INSERT IGNORE，避免其在重复键上
    持有的共享锁与随后的排他锁在并发事务间形成死锁（MySQL 1213）。
    """
    row = _for_update(model.select().where(where)).first()
    if row is None:
        model.insert(**insert_values).on_conflict_ignore().execute()
        row = _for_update(model.select().where(where)).get()
    return row


def _concurrent_other_sessions(user_id: int, session: UserWatchSession, started: datetime, now: datetime) -> int:
    """该用户在 30s 内（且在本会话开始之后）仍有增量的其他会话数；顺序切集的旧会话不计。"""
    since = max(now - timedelta(seconds=CONCURRENT_WINDOW_SECONDS), started)
    return (
        UserWatchSession.select()
        .where(
            (UserWatchSession.user == user_id)
            & (UserWatchSession.id != session.id)
            & (UserWatchSession.accepted_ms > 0)
            & (UserWatchSession.last_received_at >= since)
        )
        .count()
    )


def report_event(external_user_id: str, event) -> dict[str, Any]:
    """处理一次累计值上报。event 为 app.schemas.watch.WatchEventIn。"""
    settings = get_settings()
    if not settings.watch_events_enabled:
        return _zero_result()

    claims = parse_session_token(event.session_id)
    if claims is None:
        raise WatchError(403, "观看会话签名无效")
    if claims["u"] != external_user_id:
        raise WatchError(403, "无权上报该观看会话")
    user = _active_user(external_user_id)

    with _atomic():
        # 1) 会话行加锁
        session = _for_update(
            UserWatchSession.select().where(UserWatchSession.session_id == claims["n"])
        ).first()
        if session is None:
            raise WatchError(410, "观看会话已过期")
        if session.user_id != user.id or session.episode_id != claims["e"]:
            raise WatchError(403, "无权上报该观看会话")

        episode = (
            DramaEpisode.select(DramaEpisode, Drama)
            .join(Drama)
            .where(DramaEpisode.id == session.episode_id)
            .first()
        )
        if episode is None:
            raise WatchError(404, "剧集不存在或已下架")
        if episode.external_video_id != event.video_id:
            raise WatchError(400, "video_id 与观看会话不一致")

        now = _now()
        now_naive = _naive_utc(now)
        started = _naive_utc(session.started_at)
        last = _naive_utc(session.last_received_at) or started
        if (
            _ms_between(now_naive, last) > int(settings.watch_session_idle_seconds) * 1000
            or _ms_between(now_naive, started) > int(settings.watch_session_max_age_seconds) * 1000
        ):
            raise WatchError(410, "观看会话已过期")

        stat_date = now.date()  # UTC 日；跨日上报按服务端接收日期归集

        # 幂等：重复 / 乱序迟到
        if event.seq <= session.last_seq:
            return _current_state(session, user.id, episode.id, stat_date)
        # 限频：同会话两次处理间隔过短视作重复
        if session.last_received_at is not None and _ms_between(now_naive, last) < MIN_PROCESS_INTERVAL_MS:
            return _current_state(session, user.id, episode.id, stat_date)

        watched_ms = int(round(event.watched_seconds * 1000))
        position_ms = int(round(event.position_seconds * 1000))

        # 2) 服务端增量上限
        raw = max(0, watched_ms - session.reported_ms)
        gap_cap = _ms_between(now_naive, last) + SLACK_MS
        total_cap = _ms_between(now_naive, started) + SLACK_MS - session.accepted_ms
        delta = max(0, min(raw, gap_cap, total_cap))
        if delta > 0 and _concurrent_other_sessions(user.id, session, started, now_naive) >= MAX_CONCURRENT_OTHER_SESSIONS:
            logger.warning("watch: 并发会话过多，增量记 0 user=%s session_row=%s", user.id, session.id)
            delta = 0
        if raw > delta + SLACK_MS:
            logger.info(
                "watch: 上报被截断 user=%s session_row=%s raw_ms=%s accepted_delta_ms=%s",
                user.id, session.id, raw, delta,
            )

        # 3) 日统计行：按 用户日 -> 分集日 固定顺序加锁读取（不存在则 INSERT IGNORE，杜绝 1062）
        user_daily = _locked_row(
            UserWatchDaily,
            (UserWatchDaily.user == user.id) & (UserWatchDaily.stat_date == stat_date),
            {"user": user.id, "stat_date": stat_date},
        )
        ue_daily = _locked_row(
            UserEpisodeWatchDaily,
            (UserEpisodeWatchDaily.user == user.id)
            & (UserEpisodeWatchDaily.episode == episode.id)
            & (UserEpisodeWatchDaily.stat_date == stat_date),
            {"user": user.id, "episode": episode.id, "stat_date": stat_date},
        )

        duration_ms = max(0, int(episode.duration_seconds or 0)) * 1000
        daily = min(delta, max(0, _episode_cap_ms(duration_ms) - ue_daily.watch_ms))
        daily = min(daily, max(0, int(settings.watch_user_daily_cap_seconds) * 1000 - user_daily.watch_ms))
        credited = daily if duration_ms > 0 else 0

        if daily > 0:
            UserWatchDaily.update(
                watch_ms=UserWatchDaily.watch_ms + daily, updated_at=now
            ).where(UserWatchDaily.id == user_daily.id).execute()
            UserEpisodeWatchDaily.update(
                watch_ms=UserEpisodeWatchDaily.watch_ms + daily,
                credited_ms=UserEpisodeWatchDaily.credited_ms + credited,
                updated_at=now,
            ).where(UserEpisodeWatchDaily.id == ue_daily.id).execute()

        # 4) 播放计数：同一用户·分集·UTC 日首次跨过阈值计 1 次；条件更新保证并发只计一次
        play_counted = bool(ue_daily.play_counted)
        if not play_counted and ue_daily.watch_ms + daily >= _play_threshold_ms(duration_ms):
            rows = (
                UserEpisodeWatchDaily.update(play_counted=True, updated_at=now)
                .where((UserEpisodeWatchDaily.id == ue_daily.id) & (UserEpisodeWatchDaily.play_counted == False))  # noqa: E712
                .execute()
            )
            if rows == 1:
                # 只递增真实播放量列；种子 play_count 保持不变
                # 先 UPDATE，行不存在才 INSERT IGNORE（热门分集并发时避免共享锁升级死锁）
                bump = DramaEpisodeStat.update(
                    real_play_count=DramaEpisodeStat.real_play_count + 1
                ).where(DramaEpisodeStat.episode == episode.id)
                if bump.execute() == 0:
                    DramaEpisodeStat.insert(episode=episode.id).on_conflict_ignore().execute()
                    DramaEpisodeStat.update(
                        real_play_count=DramaEpisodeStat.real_play_count + 1
                    ).where(DramaEpisodeStat.episode == episode.id).execute()
                Drama.update(real_play_count=Drama.real_play_count + 1).where(
                    Drama.id == episode.drama_id
                ).execute()
                UserWatchDaily.update(
                    play_count=UserWatchDaily.play_count + 1, updated_at=now
                ).where(UserWatchDaily.id == user_daily.id).execute()
            play_counted = True

        # 5) 推荐贡献钩子（同一事务）
        if credited > 0:
            tag_service.apply_watch_contribution(user, episode.drama, credited / 1000.0, now)

        # 6) 更新会话
        accepted_total = session.accepted_ms + delta
        UserWatchSession.update(
            last_seq=event.seq,
            reported_ms=max(session.reported_ms, watched_ms),
            accepted_ms=accepted_total,
            last_position_ms=position_ms,
            last_received_at=now_naive,
            updated_at=now,
        ).where(UserWatchSession.id == session.id).execute()

    return {
        "accepted_seq": event.seq,
        "accepted_watched_seconds": _seconds(accepted_total),
        "credited_delta_seconds": _seconds(credited),
        "play_counted": play_counted,
    }


# ============ 清理 ============


def cleanup_stale_sessions(days: int = SESSION_RETENTION_DAYS) -> int:
    """删除 last_received_at（无则 started_at）早于 days 天的会话；daily 表保留。"""
    cutoff = _naive_utc(_now()) - timedelta(days=days)
    return (
        UserWatchSession.delete()
        .where(fn.COALESCE(UserWatchSession.last_received_at, UserWatchSession.started_at) < cutoff)
        .execute()
    )