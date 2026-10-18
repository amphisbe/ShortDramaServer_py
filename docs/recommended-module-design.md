# 猜你喜欢模块 — 设计规范

> 设计文档 | 2026-07-02 | 个性化推荐模块开发指导说明

---

## 一、核心策略

采用 **规则引擎 + 热门兜底** 的轻量级个性化方案。分两阶段实施：第一阶段基于现有 `dramas.category` / `dramas.tags` 字段快速上线，第二阶段切换到 `tag_concepts` 概念标签体系后升级。

### 推荐逻辑

**有行为数据的用户：**

1. 从 `user_drama_favorites` + `user_episode_progress` 提取用户接触过的短剧
2. 统计这些短剧的 `category` 和 `tags`（JSON 解析），按出现频次排序，形成用户偏好向量，如 `{"古装": 5, "言情": 3, "甜宠": 2}`
3. 按偏好权重生成三组候选池，**不设死比例，采用优先级填充**：
   - **同类热门池**: `category` 命中 Top 偏好，按 `play_count DESC`
   - **标签匹配池**: `tags` JSON 中包含偏好标签，按 `follow_count DESC`
   - **探索随机池**: 排除前两组已覆盖的短剧，`ORDER BY RANDOM()`
4. 整体排除已收藏/已观看的短剧
5. 每批 5 条，按优先级从三个池中取，**交叉排序**避免前 N 条全是同一类型：

```
优先级填充规则（每批 5 条）：
  1. 同类热门池（最多取 3 条）
  2. 标签匹配池（最多取 2 条，排除已入选的）
  3. 探索随机池（补齐到 5 条，排除已入选的）

例：热门池只有 2 条 → 标签池多取 1 条 → 还不够再随机补齐
例：热门池 5+ 条 → 取 3 热门 + 1 标签 + 1 随机（理想情况）

交叉排序（打散同类型）：
  列表顺序：[热门A, 标签A, 热门B, 随机A, 热门C]
  而非：    [热门A, 热门B, 热门C, 标签A, 随机A]
```

**无行为数据的用户（冷启动）：**

直接按 `play_count DESC` 返回全站热门，按 `category` 做一轮去重避免全是同一分类。

### 参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `viewer_user_id` | string | 否 | 传入则走个性化推荐，不传走热门兜底 |
| `count` | int | 否 | 每批返回数量，默认 5，最大 20 |
| `cursor` | string | 否 | 游标，首次请求不传，翻页时带上次响应中的 cursor |
| `exclude_id` | string | 否 | 排除指定短剧（保留兼容） |
| `category` | string | 否 | 分类筛选（保留兼容） |

---

## 二、游标分页

猜你喜欢是滑动刷新的 Feed 流场景，用户连续滑动时数据可能发生变化，传统 `page + OFFSET` 会导致重复或遗漏。采用游标分页（Cursor-based Pagination）。

### 游标设计

推荐结果按 `hotness_score DESC, id DESC` 排序。游标编码为 `hotness_score:id` 的组合，Base64 传输。

```python
import base64

def encode_cursor(hotness_score: float, drama_id: int) -> str:
    raw = f"{hotness_score}:{drama_id}"
    return base64.urlsafe_b64encode(raw.encode()).decode()

def decode_cursor(cursor: str) -> tuple[float, int]:
    raw = base64.urlsafe_b64decode(cursor.encode()).decode()
    score_str, id_str = raw.split(":")
    return float(score_str), int(id_str)
```

### 翻页 SQL

```sql
-- 首次请求（无 cursor）
WHERE status = 1 AND ...
ORDER BY hotness_score DESC, id DESC
LIMIT 5;

-- 后续请求（带 cursor）
WHERE status = 1 AND ...
  AND (hotness_score < :score
       OR (hotness_score = :score AND id < :last_id))
ORDER BY hotness_score DESC, id DESC
LIMIT 5;
```

### 请求/响应

```
# 首次
GET /api/v1/dramas/recommended?viewer_user_id=xxx&count=5

# 翻页
GET /api/v1/dramas/recommended?viewer_user_id=xxx&count=5&cursor=ODUwLjU6MTIzNDU=

# 返回
{
  "code": 0,
  "data": {
    "list": [ ... ],
    "cursor": "NzkwLjA6MTIzNDQ=",   // 最后一条的位置，下次请求带上
    "hasMore": true
  }
}
```

---

## 三、客户端加载策略

每批请求 5 条，当用户滑到倒数第 3 条时触发下一批预加载。

```
进入页面
  │
  ▼
请求第 1 批（无 cursor）
  │
  ▼
用户滑动到第 3 条（倒数第 3 条）
  │
  ▼
预加载第 2 批（cursor = 第 1 批最后一条的位置）
  │
  ▼
用户滑动到第 8 条
  │
  ▼
预加载第 3 批（cursor = 第 2 批最后一条的位置）
  │
  ...
  │
  ▼
hasMore = false → 展示"没有更多了"
  │
  ▼
用户下拉刷新 → 清空列表，重置 cursor，重新从第 1 批开始
```

**时序示意（每批 5 条，预加载阈值为倒数第 3 条）：**

```
列表数据            已展示    触发预加载?
─────────────────────────────────────
[0,1,2,3,4]          5 条     第 3 条(索引 2) 触发第 2 批
[0..9]               10 条     第 8 条(索引 7) 触发第 3 批
[0..14]              15 条     第 13 条(索引 12) 触发第 4 批
...
hasMore=false → 停止
```

---

## 四、两阶段实施计划

### 第一阶段（当前可做）

基于现有字段 `category` / `tags`（JSON 文本），不涉及数据库迁移。

| 文件 | 改动 |
|------|------|
| `app/api/drama.py:59-69` | 路由新增 `viewer_user_id`、`cursor` 参数 |
| `app/services/drama_service.py:126-136` | `get_recommended_dramas` 重写，拆分为 `_recommend_personalized` + `_recommend_hot_fallback` + 游标编解码 |

### 第二阶段（`tag_concepts` 上线后）

将 `category` / `tags` 字符串匹配替换为基于 `drama_tag_relations.concept_id` 的关联查询。

```sql
-- 提取用户偏好标签
SELECT dtr.concept_id, COUNT(*) AS weight
FROM drama_tag_relations dtr
JOIN user_drama_favorites udf ON dtr.drama_id = udf.drama_id
WHERE udf.user_id = ?
GROUP BY dtr.concept_id
ORDER BY weight DESC;

-- 基于偏好标签推荐
SELECT d.*, COUNT(dtr.concept_id) AS match_count,
       d.play_count * 0.6 + d.follow_count * 0.4 AS hotness_score
FROM dramas d
JOIN drama_tag_relations dtr ON d.id = dtr.drama_id
WHERE dtr.concept_id IN (用户 Top 标签)
  AND d.id NOT IN (用户已观看/已收藏)
  AND d.status = 1
GROUP BY d.id
ORDER BY match_count * 0.7 + hotness_score * 0.3 DESC
LIMIT 5;
```

---

## 五、推荐池刷新策略

| 场景 | 行为 |
|------|------|
| 用户下拉刷新 | 清空列表，重新计算偏好向量，cursor 重置 |
| 用户连续翻页 | 同一批推荐结果内游标翻页，不重算偏好 |
| 推荐池耗尽（hasMore=false） | 展示结束提示 |
| 用户新增收藏/观看行为 | 下次下拉刷新时偏好向量更新（不对当前浏览中的列表生效） |

---

## 六、与现有接口的关系

当前 `GET /api/v1/dramas/recommended` 保持不变（向后兼容），新增可选参数：

```
# 现有调用方式（无变更）
GET /api/v1/dramas/recommended?exclude_id=drama_001&category=古装&count=4

# 个性化调用（新增）
GET /api/v1/dramas/recommended?viewer_user_id=user_mama&count=5

# 翻页（新增）
GET /api/v1/dramas/recommended?viewer_user_id=user_mama&count=5&cursor=ODUw...
```

不传 `viewer_user_id` 时行为与当前完全一致。

---

## 七、涉及的数据库字段

推荐引擎依赖以下表中字段，部署前请确认均已存在：

### `dramas` 表

| 字段 | 类型 | 用途 |
|------|------|------|
| `id` | bigint | 游标编码中的锚点 ID |
| `external_drama_id` | varchar(24) | 排除已看过/已收藏时使用 |
| `category` | varchar(50) | 提取用户偏好，同类热门候选池 |
| `tags` | text (JSON) | 提取用户偏好标签，标签匹配候选池 |
| `play_count` | bigint | 热门候选池排序 + 综合热度计算 |
| `follow_count` | bigint | 标签匹配候选池排序 + 综合热度计算 |
| `status` | int | 过滤（只取 status=1 的在线短剧） |
| `hot` | int | 综合热度分默认值（当 play_count / follow_count 均为 0 时作为兜底排序值） |

### `users_drama_favorites` 表

| 字段 | 类型 | 用途 |
|------|------|------|
| `user_id` | bigint | 关联用户 |
| `drama_id` | bigint | 提取用户已收藏的短剧，用于计算偏好向量 + 排除已收藏 |

### `users_episode_progress` 表

| 字段 | 类型 | 用途 |
|------|------|------|
| `user_id` | bigint | 关联用户 |
| `episode_id` | bigint | 通过 DramaEpisode.drama_id 反查短剧，提取用户已观看的短剧用于排除 |

### `users` 表

| 字段 | 类型 | 用途 |
|------|------|------|
| `id` | bigint | 内部主键 |
| `external_user_id` | varchar(24) | API 传入的 viewer_user_id 通过此字段查找用户内部 ID |

### 热度计算公式

```
hotness_score = play_count * 0.6 + follow_count * 0.4
```

当 `play_count` 和 `follow_count` 均为 0 时，回退使用 `hot` 字段作为初始排序值。
