# data.json 接口结构对齐记录

## 样例顶层结构

`data.json` 的顶层结构是 **JSON 数组**，数组中的每个元素代表一个短剧分集播放卡片。当前 `/api/v1/video/play-list/raw` 已经返回顶层数组，方向正确；`/api/v1/video/play-list` 作为包装格式可保留，但必须保证内部 `data.list` 的 item 与样例 item 完全一致。

## 样例字段清单

| 字段 | 样例类型 | 当前实现状态 | 处理策略 |
|---|---:|---|---|
| `userId` | string | 已实现 | 来源于作者用户 `external_user_id` |
| `avatar` | string | 已实现 | 来源于作者头像 |
| `nickname` | string | 已实现 | 来源于短剧/作者昵称，需支持样例中每集可不同的展示昵称 |
| `isfollow` | boolean | 已实现 | 当前无 viewer 时为 false，符合样例 |
| `videoId` | string | 已实现 | 来源于分集外部视频 ID |
| `playurl` | string | 已实现 | 来源于分集播放地址 |
| `poster` | string | 已实现 | 来源于分集封面/海报地址 |
| `vduser` | string | 已实现 | 来源于短剧展示作者名 |
| `vdtitle` | string | 已实现 | 来源于分集标题 |
| `loop` | boolean | 硬编码 true | 应入库到分集播放配置 |
| `duration` | number | 已实现 | 来源于分集时长 |
| `playIng` | boolean | 硬编码 false | 应入库到分集播放配置，注意字段拼写保留样例的 `playIng` |
| `muted` | boolean | 硬编码 false | 应入库到分集播放配置 |
| `likeSum` | number | 已实现 | 来源于统计表 |
| `isLiked` | boolean | 已实现 | 当前无 viewer 时为 false，符合样例 |
| `commemtSum` | number | 已实现 | 字段拼写按样例保留 `commemtSum` |
| `shareSum` | number | 已实现 | 来源于统计表 |
| `isPlaying` | boolean | 硬编码 false | 应入库到分集播放配置 |
| `position` | number | 已实现 | 当前无 viewer 时为 0，符合样例 |
| `showTitleArrow` | boolean | 硬编码 true | 应入库到分集播放配置 |
| `showLookAllBtn` | boolean | 硬编码 true | 样例中不同分集 true/false 不同，应入库到分集播放配置 |
| `lookAllBtnText` | string | 拼接生成 | 应支持入库覆盖，默认仍可拼接 |
| `total` | number | 已实现 | 来源于短剧总集数 |
| `showBottomArea` | boolean | 硬编码 false | 样例中不同分集 true/false 不同，应入库到分集播放配置 |
| `bottomAreaBtnText` | string | 拼接生成 | 应支持入库覆盖，默认仍可拼接 |
| `toolInfo` | array<object> | 已实现但不完全 | 样例中点赞 `num` 可与 `likeSum` 不一致，应支持独立工具栏 JSON 入库 |

## 主要差异结论

当前接口字段名称基本覆盖了样例，但有两个核心问题。第一，部分 UI 控制字段当前是服务层硬编码，例如 `showLookAllBtn`、`showBottomArea`、`loop`、`muted`、`playIng`、`isPlaying` 等，无法还原样例中每个分集不同的布尔配置。第二，`toolInfo` 当前固定按统计表拼接，而样例中点赞工具栏 `num` 与 `likeSum` 并非总是完全相同，因此更合理的做法是在 `drama_episodes` 中增加 `tool_info_json` 这类字段，允许短剧数据源按前端标准直接配置工具栏结构。

## 修改方案

对 `DramaEpisode` 增加与播放接口强相关的展示配置字段，包括 `display_nickname`、`loop`、`play_ing`、`muted`、`is_playing`、`show_title_arrow`、`show_look_all_btn`、`look_all_btn_text`、`show_bottom_area`、`bottom_area_btn_text`、`tool_info_json`。服务层构造响应时优先使用分集配置字段，缺省时再回退到短剧/作者/统计表默认值。种子数据应直接按 `data.json` 四条样例写入，从而保证 raw 接口的返回结构与样例字段、类型、可变 UI 状态一致。
