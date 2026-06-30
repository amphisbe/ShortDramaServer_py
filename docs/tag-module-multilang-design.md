# 标签管理模块 — 多语言设计规范

> 设计文档 | 2026-06-28 | 标签管理模块开发指导说明

---

## 一、核心设计原则：标签"归一化"而非"翻译化"

在处理多语言标签时，最常见的误区是直接把"甜宠"翻译成"Sweet Pet"给海外用户，这会造成严重的语义偏差。

正确的做法是引入**标签概念（Tag Concept）**作为唯一主键：

- **概念层（Concept）**：系统内部唯一标识，如 `CONCEPT_ROMANCE`。所有计算（热度、关联）都在这一层进行。
- **展示层（Label）**：每个概念在不同语言下的具体展示文本，如中文"甜宠"、英文"Romance"、西班牙语"Romance"。

Netflix 的实践也印证了这一思路：其对内容标签采用统一的 ID 编码，避免因语言差异导致推荐偏差。

---

## 二、数据库设计：四张核心表

### 表1：标签概念表 `tag_concepts` — 全局唯一标识

| 字段 | 类型 | 说明 |
|------|------|------|
| id | bigint | 主键 |
| concept_code | varchar(64) | 概念编码，唯一，如 `"ROMANCE"`、`"REBIRTH"` |
| created_at | datetime | 创建时间 |

### 表2：标签翻译表 `tag_translations` — 多语言展示文本

| 字段 | 类型 | 说明 |
|------|------|------|
| id | bigint | 主键 |
| concept_id | bigint | FK → `tag_concepts.id` |
| locale | varchar(10) | 语言代码，如 `"zh-CN"`、`"en-US"`、`"es-ES"`、`"ar-SA"` |
| label | varchar(100) | 该语言下的展示文本 |
| description | text | 该语言下的标签说明（可选） |

**唯一约束：** `(concept_id, locale)` 联合唯一。

### 表3：剧集-标签关联表 `drama_tag_relations` — 关联剧集与标签概念

| 字段 | 类型 | 说明 |
|------|------|------|
| id | bigint | 主键 |
| drama_id | bigint | FK → `dramas.id` |
| concept_id | bigint | FK → `tag_concepts.id` |
| source | varchar(20) | 标签来源：`"manual"` / `"ai"` / `"user"` |
| created_at | datetime | 创建时间 |

**唯一约束：** `(drama_id, concept_id)` 联合唯一。

**关键点：** 剧集关联的是 `concept_id` 而非具体语言的标签文本。一部剧无论在哪个语言环境下展示，关联逻辑完全一致，只需查询对应的翻译文本即可。

### 表4：标签热度表 `tag_hotness` — 存储计算结果

| 字段 | 类型 | 说明 |
|------|------|------|
| concept_id | bigint | FK → `tag_concepts.id`，主键 |
| hotness_score | decimal(10,2) | 综合热度分 |
| rank_global | int | 全球排名 |
| rank_region | int | 地区排名（可选，按地区分别存储或新增 region 字段） |
| updated_at | datetime | 更新时间 |

---

## 三、标签管理全流程

### 3.1 标签的创建与录入

**① 人工创建（策展模式）**

运营人员在 CMS 中创建一个新标签概念（如"重生"），同时填写多语言翻译（中文"重生"、英文"Rebirth"、西班牙语"Renacimiento"等）。系统生成唯一的 `concept_code`，写入 `tag_concepts` 和 `tag_translations` 表。

**② AI 自动打标 + 翻译**

对入库的短剧，通过 NLP 分析剧情简介、标题，自动推荐标签概念。若标签概念已存在，直接关联 `drama_tag_relations`；若不存在，调用翻译 API 生成多语言版本，经人工审核后入库。

**③ 用户生成标签（UGC）的归一化处理**

用户自由输入的标签（如"甜甜的恋爱"），通过语义相似度匹配到已有概念（如"甜宠"）。若无法匹配，暂存为"待审核"状态，由运营判断是否新建概念。

### 3.2 标签的维护与合并

- **同义词合并：** 当出现"甜宠"和"甜蜜爱情"两个概念时，运营可将后者合并到前者，所有 `drama_tag_relations` 关联自动迁移。
- **翻译补全：** 当系统上线新语言时，对现有标签批量生成翻译，人工校准后补入 `tag_translations` 表。

---

## 四、热门标签计算的多语言适配

### 第一步：概念层热度计算（与语言无关）

所有热度计算在 `concept_id` 层面进行，不涉及任何具体语言。

```
标签热度 = 爆款剧集贡献分 × 0.6 + 用户搜索行为分 × 0.4 × 时间衰减因子
```

计算出每个 `concept_id` 的热度分，写入 `tag_hotness` 表。

### 第二步：按地区加权（差异化排名）

不同地区的用户偏好不同。例如"霸总"标签在中国热度极高，但在欧美可能水土不服。引入地区权重：

```
地区热度分 = 全球热度分 × 地区偏好系数
```

地区偏好系数可根据该地区用户对该标签相关剧集的点击率、完播率动态计算。

### 第三步：多语言榜单生成

- 查询 `tag_hotness` 表，按热度分排序取 Top N。
- 根据用户当前语言（从 `Accept-Language` 头或用户设置获取），关联 `tag_translations` 表取出对应语言的标签文本。
- 若某标签在用户语言下无翻译，则 **回退（Fallback）** 到默认语言（如英语）。

**SQL 示例**（查询某语言下的 Top 10 热门标签）：

```sql
SELECT
    tc.concept_code,
    tt.label,
    th.hotness_score,
    th.rank_global
FROM tag_hotness th
JOIN tag_concepts tc ON th.concept_id = tc.id
JOIN tag_translations tt ON tc.id = tt.concept_id AND tt.locale = 'en-US'
ORDER BY th.hotness_score DESC
LIMIT 10;
```

---

## 五、前端展示与用户体验

- **语言自动适配：** 系统检测用户设备语言，自动展示对应语言的标签文本。支持 RTL 语言（如阿拉伯语）的界面布局适配。
- **双语展示（可选）：** 在标签旁用小字显示原文或英文，帮助多语言用户理解，例如：`甜宠 (Romance)`。
- **搜索的跨语言支持：** 用户用中文搜索"爱情"，系统应能匹配到标签概念 `ROMANCE`，并展示英文标签 `Romance`。实现方式：将用户输入映射到 `concept_code`，再返回对应语言的标签结果。

---

## 六、运营与维护策略

| 维度 | 建议 |
|------|------|
| 翻译质量 | AI 预翻译 + 人工校准 + 用户反馈闭环优化；核心标签（Top 100）建议人工精翻 |
| 文化适配 | 不同地区可启用不同的标签集合，如印度市场增加"Bollywood"，巴西市场突出"Telenovelas" |
| 敏感内容 | 结合地区政策，对某些标签（如"宗教""政治"）进行地域屏蔽或降权 |
| 数据一致性 | 所有统计报表、推荐算法均基于 `concept_id`，确保全球数据可比对、可聚合 |

---

## 七、方案总结

| 层级 | 核心机制 | 关键产出 |
|------|---------|---------|
| 数据层 | 标签概念（Concept）作为唯一主键，多语言翻译独立存储 | 一套标签、多种语言展示 |
| 计算层 | 热度在概念层计算，按地区加权，按语言展示 | 各地区看到不同的 Top 10 榜单 |
| 展示层 | 自动语言适配 + Fallback 机制 | 用户始终看到母语标签 |
| 运营层 | AI 辅助翻译 + 人工校准 + 文化适配 | 标签体系可规模化、可持续 |

---

## 八、与现有系统的对接

当前 `dramas` 表的 `tags` 字段是 `TEXT` 列，存储 JSON 数组（如 `["甜宠","都市"]`），属于纯文本标签。

对接时需要：
1. 将现有标签文本迁移为 `tag_concepts` 记录（以中文 label 生成 `concept_code`）。
2. 将 `dramas.tags` JSON 数组拆解为 `drama_tag_relations` 行（`source = "manual"`）。
3. 新增的 `/api/v1/dramas` 等接口返回标签时，根据 `Accept-Language` 查询 `tag_translations` 替换展示文本。
4. `dramas.tags` 字段保留但不作为主数据源，逐步废弃。

---

> 核心思想：**标签的本质是概念，而非词汇。** 把"概念"和"翻译"解耦，既能保证全球数据的一致性，又能灵活适配各个本地市场。
