# 真实观看时长统计 设计与修改方案

> 状态：方案稿（未改代码）　日期：2026-10-19
> 关联文档：`docs/for-you-recommendation-design.md`（§4 有效观看时长、§9 数据模型、§10.1 上报接口）。本方案是其“观看贡献闭环”的落地版本，接口与表名沿用该文档，避免两套口径。
> 不涉及：Reward 后端 `/shortdrama/game/user/onlineTime` 的 App 在线时长（独立体系，不改）。

## 1. 现状（已核对代码）

| 项 | 现状 |
|---|---|
| 客户端上报 | `pages/index/index.uvue`、`pages/foryou/index.uvue`：`onTimeUpdate` → `recordProgress(ms)` 转秒，同视频 5s 节流调用 `saveProgress(...)`；`onEnded` → `markFinished()` 以 `lastPositionSec` 上报 `is_finished=true`。两页逻辑复制粘贴，index 页 `onTimeUpdate` 每帧 `console.log`。 |
| 进度接口 | `POST /api/v1/user/{user_id}/progress`。**注意：已鉴权**——`app/api/user.py` 的 router 级 `dependencies=[Depends(require_path_user)]` 要求 Bearer JWT 且路径 user_id == 令牌 sub（`tests/test_auth_guard.py` 覆盖了 user 路由的 401/403，但没有 progress 专项用例）。 |
| 进度存储 | `user_service.save_progress`：`UserEpisodeProgress.get_or_create`，`position = max(旧, 新)`，`is_finished` 置位后不回退；有调试 `print("user:", user)`。 |
| 进度用途 | 续播位置（episodes/play/for-you 响应）；Profile `watchedCount` = is_finished 行数（`user_service.get_user_profile`、`auth_service._format_auth_user` 两处）；观看历史按 `updated_at` 排序。 |
| 播放量 | `Drama.play_count`、`DramaEpisodeStat.play_count` 只有种子数据（seed.py 中 36 万～213 万的假值），**从未递增**；热门/趋势/推荐分（`drama_service.py` 多处 `order_by(Drama.play_count.desc())`、`play_count*0.6+follow_count*0.4`）全部依赖它。 |
| 观看贡献 | For You 设计文档要求的 `user_watch_sessions`、`user_episode_watch_daily`、标签权重更新均未实现；`user_tag_weights` 表已存在（`app/models/tag.py`）。 |
| 建表/迁移 | `app.main` lifespan → `initialize_runtime(create_schema=True)` → `create_tables(ALL_MODELS)`（`safe=True`，只建不存在的表）→ `ensure_demo_schema_compatibility()` 按表补列（`_migrate_users/_migrate_dramas/...`）。 |
| 并发经验 | `drama_service._preload_stats` 已用 `insert_many(...).on_conflict_ignore()` 解决 `drama_episode_stats` 的 1062；`like/favorite/share` 计数仍是读-改-写（`stat.like_count += 1; save()`），存在丢更新风险。 |
| 测试 | `tests/` 下用 `SqliteDatabase(tmp_path/...)` + `database_proxy.initialize` + `TestClient(app)`（不进 lifespan）；根目录 `test_progress.py` 在导入时 `initialize_runtime()` 连真实库，必须 `pytest tests`。 |

## 2. 目标与非目标

**目标**
1. 统计“有效观看时长”：只计前台真实播放的时间，可用于 Profile 统计、For You 观看贡献、热门排行。
2. 让 `DramaEpisodeStat.play_count` / `Drama.play_count` 按真实播放递增，并发安全、可防刷。
3. 不破坏旧客户端：旧版只调用 progress 接口，行为不变。

**非目标**
- 不做奖励/结算依据（不需要金融级精度）；不存每条心跳明细（与 For You 文档 §9.3 一致）。
- 不改 Reward 在线时长；第一版不做游客统计（未登录服务端不上报）。

## 3. 口径定义

| 名词 | 定义 |
|---|---|
| 有效观看时长 | 播放中 + 页面前台 + 媒体位置在正常前进时，相邻两次 `onTimeUpdate` 之间的**墙钟时间**之和。暂停、缓冲（位置不动）、拖动、后台、循环回到开头的那一跳都不计；倍速按墙钟计（For You §4.1）。 |
| 会话（session） | 一个用户对一个分集的一次连续播放；切集/重进页面/会话过期都开新会话。 |
| 已接受时长 accepted | 服务端经时间间隔校验后承认的时长。 |
| 日计入时长 watch | 同一用户·分集·UTC 自然日的 accepted 合计，上限 = 该集时长（未知时长时为兜底 1800s）。用于 Profile、播放量判定。 |
| 推荐贡献 credited | 与 watch 同一份增量，但**仅当分集时长可靠（>0）时**计入；用于标签权重/热度（For You §4.3）。 |
| 一次播放（play） | 同一用户·分集·UTC 日内，watch 首次 ≥ `PLAY_THRESHOLD = min(5s, 分集时长)` 时计 1 次；当日后续再看不重复计。`Drama.play_count` 同步 +1（即剧的播放量 = 各集播放之和）。 |

## 4. 客户端方案（uni-app x）

### 4.1 新增共享模块 `api/utils/watchTracker.uts`

放在已有的 `api/utils/`（与 `luckyBox.uts` 同级），**纯逻辑、不依赖 uni API**，便于沿用 `tests/*.test.mjs`（`stripTypeScriptTypes` + `vm`）做单测。两个页面各持有一个 tracker 实例，网络请求通过注入的回调完成。

常量：

| 常量 | 值 | 说明 |
|---|---|---|
| `WATCH_REPORT_INTERVAL_MS` | 10000 | 周期上报（For You §4.2 定为 10s；如要省请求可调到 15000，见待决问题） |
| `MAX_TICK_GAP_MS` | 2000 | 两次 timeupdate 墙钟间隔超过它视为卡顿/后台恢复，该段不计 |
| `SEEK_JUMP_MS` | 3000 | 媒体位置单次前进超过 max(3000, 墙钟间隔×3) 视为拖动，不计 |
| `MAX_PLAYBACK_RATE` | 3 | 上面判定用的倍速上限 |
| `FINAL_FLUSH_RETRY_DELAY_MS` | 2000 | 切集/结束的最终补报失败后重试 1 次 |

状态：`videoId, sessionId, seq, watchedMs(累计), lastWallMs, lastMediaMs, playing, foreground, inflight, lastReportAt`。

### 4.2 累计规则（每次 `onTimeUpdate(videoId, currentTimeMs)`）

```text
若 videoId 变化 → finish(旧) 并 start(新)；
wall = now - lastWallMs；media = currentTimeMs - lastMediaMs
计入条件：playing && foreground && sessionId 已建立 && lastWallMs > 0
          && 0 < wall <= MAX_TICK_GAP_MS
          && 0 < media <= max(SEEK_JUMP_MS, wall * MAX_PLAYBACK_RATE)
满足 → watchedMs += wall；否则只重置基准（media<0 即回退/循环，media 过大即拖动，media==0 即缓冲）
更新 lastWallMs/lastMediaMs；若 now - lastReportAt >= WATCH_REPORT_INTERVAL_MS → report()
```

事件挂接（两页一致）：
- `onPlaying` → `playing=true`，清基准（避免把暂停期间算进去）；无会话则 `createWatchSession`。
- `onPause` / 页面 `onHide` → `playing=false` 或 `foreground=false`，立即 `report()`。`onShow` 只恢复 `foreground` 并清基准。
- `onEnded` → `report(final)`，保留现有 `markFinished()`。
- `onChange` / 选集切换 / `onUnload` → `finish()`：最终上报 + 丢弃会话。
- 未登录服务端（`getServerUserId()==''`）→ tracker 不工作。

### 4.3 上报与容错

- 上报**累计值**而不是增量：`{session_id, seq, video_id, watched_seconds, position_seconds, is_finished}`，`seq` 每次发送 +1。中间某次丢失时，下一次累计值自然覆盖，无需补发队列。
- 同一会话同时只允许 1 个在途请求；在途时到点的上报跳过，等下一次。
- 会话建立前的观看不回填（For You §4.2）；会话创建失败不影响播放，下次 `onPlaying`/定时再试。
- 业务码 `410`（会话过期）→ 丢弃会话，重新创建，旧累计不带入；`401` → 停止统计直到重新登录；其他失败静默，等待下次上报。
- 预期损失：进程被杀时最后 ≤10s 可能丢失，可接受。
- **保留**现有 `saveProgress` 5s 心跳和 `markFinished()`（第一阶段不动），顺手删除 index 页 `onTimeUpdate` 中的逐帧 `console.log`。

### 4.4 `api/dramaService.uts` 新增

- `createWatchSession(videoId, cb(ok, sessionId, code))` → `POST {BASE}/api/v1/me/watch-sessions`
- `reportWatchEvent(body, cb(ok, code, data))` → `POST {BASE}/api/v1/me/watch-events`
- 复用 `makePostHeader()`（已带 Bearer），需要把业务 `code` 回传给调用方（现有 `httpPost` 只回 bool，新增一个返回 code 的变体）。

## 5. 服务端接口

新路由文件 `app/api/watch.py`，`APIRouter(prefix="/api/v1/me", dependencies=[])`，各接口参数 `user_id: str = Depends(get_current_user)`；用户只取自 JWT，不接受路径/Body 用户 ID。错误沿用 HTTP 200 + 信封业务码。

### 5.1 `POST /api/v1/me/watch-sessions`

请求 `{ "video_id": "video_001" }`（外部分集 ID）。分集不存在/下架 → `404`。
响应 `data: { "session_id": "ws1.<payload>.<sig>", "expires_in": 1800 }`。

`session_id` = base64url(`{u: 用户 external_id, e: episode.id, t: 创建秒, n: 随机 8 字节}`) + HMAC-SHA256 截断签名（密钥 `WATCH_SESSION_SECRET`，缺省复用 `JWT_SECRET`）。同时插入一行 `user_watch_sessions`。会话创建不产生时长。限流：同一用户每分钟最多 `WATCH_SESSION_CREATE_PER_MIN=30` 次，超出返回 `429`。

### 5.2 `POST /api/v1/me/watch-events`

```json
{ "session_id": "ws1...", "seq": 3, "video_id": "video_001",
  "watched_seconds": 25.0, "position_seconds": 48.5, "is_finished": false }
```

响应 `data: { "accepted_seq": 3, "accepted_watched_seconds": 24.8, "credited_delta_seconds": 9.9, "play_counted": true }`。

校验顺序：
1. Pydantic 模型校验（放 `app/schemas`）：`seq` 1～100000，`watched_seconds` 0～21600，`position_seconds` ≥0 → 否则 `400`。
2. 验签；签名中的用户 ≠ 令牌用户、或 `video_id` 与会话绑定的分集不一致 → `403`/`400`。
3. 会话 `last_received_at`（无则 `started_at`）距今 > 30 分钟，或会话存续 > 6 小时 → `410`。
4. 幂等：`seq <= last_seq` → 直接返回当前已接受状态，增量 0（重复、乱序迟到都走这里）。
5. 同会话两次处理间隔 < 2s → 视作重复，返回当前状态（限频，减少写）。

### 5.3 防刷与上限（全部服务端判定）

```text
raw      = max(0, watched_ms - session.reported_ms)
delta    = min(raw,
               now - session.last_received_at + SLACK_MS(5000),      # 两次接收间隔
               (now - session.started_at + SLACK_MS) - session.accepted_ms)  # 会话总存续
并发会话：该用户 30s 内有增量的其他会话 >= 2 个 → delta = 0（防多开刷）
daily    = min(delta, 当集日上限 - ue_daily.watch_ms)        # 当集时长；未知时 1800s
daily    = min(daily, USER_DAILY_CAP(43200s=12h) - user_daily.watch_ms)
credited = daily if 分集时长 > 0 else 0
```

`watch_seconds <= 分集时长` 的要求由“当集日上限”体现（单会话循环播放也会被封顶）。`reported_ms` 记录客户端声称值，与 `accepted_ms` 差值供日志告警（比例异常的用户可后续处理）。

## 6. 数据模型与并发

### 6.1 新增表（新文件 `app/models/watch.py`，加入 `ALL_MODELS`）

| 表 | 字段 | 约束 |
|---|---|---|
| `user_watch_sessions` | id, session_id(64), user_id, episode_id, last_seq, reported_ms, accepted_ms, last_position_ms, started_at, last_received_at, created_at, updated_at | `session_id` 唯一；索引 `(user_id, last_received_at)` |
| `user_episode_watch_daily` | id, user_id, episode_id, stat_date(UTC 日期), watch_ms, credited_ms, play_counted(bool), created_at, updated_at | `(user_id, episode_id, stat_date)` 唯一 |
| `user_watch_daily` | id, user_id, stat_date, watch_ms, play_count, created_at, updated_at | `(user_id, stat_date)` 唯一；用于用户日上限与 Profile 总时长 |
| `drama_watch_daily`（可选，二期） | id, drama_id, stat_date, watch_ms, play_count, updated_at | `(drama_id, stat_date)` 唯一；用于“近 7 日真实热门” |

- 内部统一用整数毫秒（避免每次取整丢小数，For You §9.2），接口对外用秒（1 位小数）。
- 外键：`UserTagWeight` 注释已说明旧 MySQL `users.id` 为 INT 而模型是 BIGINT，物理 FK 会类型冲突。新表的 user 关联照抄它的做法（`ForeignKeyField(User, ..., _deferred=True)` 不建物理 FK），episode/drama 同样处理；上线前只读执行 `SHOW CREATE TABLE users / drama_episodes` 确认列类型。
- 迁移：新表无需 ALTER，`create_tables(ALL_MODELS)`（safe=True）在启动时自动建；以后给这些表加列时在 `ensure_demo_schema_compatibility()` 中新增 `_migrate_watch_tables()`，写法同 `_migrate_dramas()`。

### 6.2 单次上报事务（`watch_service.report_event`，`db.atomic()` 内）

1. `SELECT ... FOR UPDATE` 锁会话行（加 `_for_update(query)` 辅助：仅 MySQL 加 `for_update()`，SQLite 跳过——peewee 在 SQLite 上会对 FOR UPDATE 报错；`tag_service` 已有 `SqliteDatabase` 判断可参考）。
2. `user_watch_daily`、`user_episode_watch_daily`：先 `insert(...).on_conflict_ignore().execute()` 保证行存在（与 `_preload_stats` 同一招，杜绝 1062），再按 **会话 → 用户日 → 分集日** 固定顺序加锁读取，避免死锁。
3. 计算 delta / daily / credited（§5.3），用 `Model.update(watch_ms=Model.watch_ms + d, updated_at=now)` 原子更新（注意 `update()` 不走 `BaseModel.save()`，要手动带 `updated_at`）。
4. 播放计数：若 `watch_ms` 跨过阈值，执行条件更新
   `UPDATE user_episode_watch_daily SET play_counted=1 WHERE id=? AND play_counted=0`，
   **仅当影响行数 = 1** 时：`DramaEpisodeStat.insert(episode=..).on_conflict_ignore()` 后 `UPDATE drama_episode_stats SET play_count=play_count+1`；`UPDATE dramas SET play_count=play_count+1`；`user_watch_daily.play_count+1`。并发两次请求最多只有一次拿到 rowcount=1。
5. 推荐贡献钩子：`credited>0` 时调用 `tag_service.apply_watch_contribution(user, drama, credited_seconds, now)`（二期实现 For You §5/§6 的衰减累加 + `tag_daily_stats`，一期为空实现），与上面同一事务提交，保证重试不重复加权。
6. 更新会话 `last_seq / reported_ms=max(...) / accepted_ms / last_position_ms / last_received_at`。

跨 UTC 日的上报按服务端接收日期归集（For You §9.3），不拆分。

### 6.3 清理

启动或每日任务删除 `last_received_at` 超过 30 天的会话；daily 表保留（数据量 = 用户×当日看过的集数，可接受），如需再加 90 天清理。

## 7. 下游使用

- **Profile**：`get_user_profile` 与 `_format_auth_user` 新增 `totalWatchSeconds`（`SUM(user_watch_daily.watch_ms)/1000`）和 `todayWatchSeconds`；`watchedCount` 暂保持 is_finished 口径不变（旧客户端兼容）。建议两处抽一个公共函数避免口径分叉。客户端 `pages/profile` 可选展示“观看 N 分钟”。
- **For You**：一期只落库 `credited_ms`；二期在钩子里实现标签权重与每日热度，`for_you_service` 再接入偏好（按 For You 文档 §7）。
- **热门排行**：一期继续用 `Drama.play_count` 排序，但它开始真实递增。种子假值（百万级）会长期压住真实增量，三种处理见待决问题；推荐：二期热门/趋势改用 `drama_watch_daily` 近 7 日 `play_count`（或 watch_ms）排序，`Drama.play_count` 仅作展示的累计播放量。

## 8. 顺带修复

1. progress 接口鉴权：现已由 router 级 `require_path_user` 保证（JWT + 路径用户一致），无需改逻辑；补一条专项测试（他人 user_id → 403、无令牌 → 401）。长期可新增 `POST /api/v1/me/progress`（用户取自令牌），旧路径保留。
2. 删除调试输出：`user_service.save_progress` 的 `print("user:", user)`，同文件 `toggle_like`/`toggle_favorite` 的 print，`app/api/user.py` 中 `user_profile`/`user_history`/`toggle_like` 的 print；需要时改 `logger.debug`。
3. `save_progress` 的 `get_or_create` 在并发首写时同样可能 1062：改为 `insert(...).on_conflict_ignore()` + 更新。
4. （可选）`like/favorite/share` 计数改为 `SET x = x + 1` 原子更新，与本方案一致。

## 9. 测试计划

新增 `tests/test_watch.py`，fixture 照搬 `tests/test_auth_guard.py`（tmp_path SQLite、monkeypatch `jwt_secret`、`TestClient(app)` 不进 lifespan）。`watch_service` 的“当前时间”通过模块级 `_now()` 注入，测试用 monkeypatch 推进时间。运行：`pytest tests`（**不要在仓库根目录跑**，根目录 `test_progress.py` 导入即连 MySQL）。

| 用例 | 期望 |
|---|---|
| 无令牌 / 他人会话 / 伪造签名 | 401 / 403 / 403 |
| 正常 3 次上报（间隔 10s，累计 10/20/30） | accepted ≈ 30s |
| 时间只过 10s 却上报 300s | accepted ≤ 15s |
| 重复 seq、乱序旧 seq | 增量 0，返回当前状态 |
| 中间一次丢失（seq1→seq3） | seq3 的累计被完整接受 |
| 循环看同一集超过时长 | 当日 watch_ms 封顶 = 时长 |
| duration=0 的分集 | watch 封顶 1800s，credited=0 |
| 跨过 5s 阈值 | episode stat 与 drama play_count 各 +1，同日再看不再 +1，次日再 +1 |
| 阈值附近两次并发上报（线程 + 文件型 SQLite） | play_count 只 +1 |
| 会话 31 分钟无上报 | 410 |
| 同用户 3 个会话并发 | 第 3 个增量 0 |
| profile | 返回 totalWatchSeconds |
| progress 接口回归 | 旧行为不变，他人路径 403 |

客户端：新增 `tests/watch-tracker.test.mjs`，覆盖正常累计、拖动、回退/循环、缓冲、暂停、后台、切集结算、累计+seq 生成。真机手测：拖动进度条、倍速、切后台 1 分钟、断网恢复。

## 10. 上线与兼容

1. 服务端先发：新表启动自动创建；旧客户端只调 progress，零影响。发布前确认 users/drama_episodes id 列类型；不改动现有数据。
2. 配置开关 `WATCH_EVENTS_ENABLED`（默认 true）：关闭时 watch 接口返回 `code 0` 且增量 0，客户端不报错。
3. 客户端发版：`watchTracker` 加 `WATCH_REPORT_ENABLED` 常量便于回退。
4. 观察 1～2 周：日志统计 `reported_ms` 与 `accepted_ms` 比例、410/429 次数、单用户日时长分布，再决定是否调阈值。
5. 二期：For You 贡献钩子、`drama_watch_daily` 与热门改造；客户端评估用 watch-events 的 `position_seconds` 合并进度上报，去掉 5s `saveProgress`。

## 11. 任务拆分

**服务端（ShortDramaServer_py）**
- [ ] `app/core/config.py`：`WATCH_SESSION_SECRET`、`WATCH_EVENTS_ENABLED`、`WATCH_PLAY_THRESHOLD_SECONDS=5`、`WATCH_UNKNOWN_DURATION_CAP_SECONDS=1800`、`WATCH_USER_DAILY_CAP_SECONDS=43200`、`WATCH_SESSION_IDLE_SECONDS=1800`。
- [ ] `app/models/watch.py`（新）+ `app/models/__init__.py` 注册到 `ALL_MODELS`/`__all__`。
- [ ] `app/schemas/watch.py`（新）：请求体模型。
- [ ] `app/services/watch_service.py`（新）：会话签发/验签、`report_event` 事务、`_for_update`、播放计数、用户总时长查询。
- [ ] `app/api/watch.py`（新）+ `app/main.py` `include_router`。
- [ ] `app/services/tag_service.py`：`apply_watch_contribution` 空实现（二期填充）。
- [ ] `app/services/user_service.py`、`app/services/auth_service.py`：Profile 新字段；删除 print；`save_progress` 改 on_conflict。
- [ ] `app/api/user.py`：删除 print。
- [ ] `tests/test_watch.py`（新）、`tests/test_auth_guard.py` 补 progress 用例。
- [ ] `docs/API_EXAMPLES.md`、`docs/shortdrama-api.postman_collection.json` 补两个接口。

**客户端（ShortDrama_03）**
- [ ] `api/utils/watchTracker.uts`（新）：累计/判定/上报调度纯逻辑。
- [ ] `api/dramaService.uts`：`createWatchSession`、`reportWatchEvent`、带业务码的 POST 变体。
- [ ] `pages/index/index.uvue`、`pages/foryou/index.uvue`：在 `onPlay/onPause/onEnd/onTimeUpdate/onChange/onHide/onShow/onUnload` 接入 tracker；删除逐帧 log。
- [ ] `pages/profile`：可选展示观看分钟数。
- [ ] `tests/watch-tracker.test.mjs`（新）。

## 12. 待决问题

1. 播放判定阈值：5s（本稿）还是更高（如 10s / 时长 20%）？去重粒度按“用户·分集·UTC 日”还是“每个会话”？
2. `Drama.play_count` 口径：各集播放之和（本稿）还是“用户·剧·日”去重一次？
3. 种子假播放量：保留并在其上累加（本稿一期）／清零只看真实值／新增 `real_play_count` 列分开存？
4. 统计日按 UTC（与 For You 文档一致，本稿）还是按北京时间（UTC+8）？
5. 上报间隔 10s（For You 文档）还是放宽到 15～30s？
6. For You 文档要求续播位置用“最新位置”而非“历史最大位置”，当前 `save_progress` 取 max；是否在本次一并改口径？
7. 部署是否多 worker/多实例？若是，会话创建限流需换成 Redis 或数据库计数（本稿按单进程内存限流）。
8. 大量分集 `duration_seconds=0`：是否先补齐真实时长（否则推荐贡献为 0，日上限只能用 1800s 兜底）？
