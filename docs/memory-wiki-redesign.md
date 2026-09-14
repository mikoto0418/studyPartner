# Memory Wiki 改造设计文档

> 基于 LLM Wiki 思想，将当前扁平的 `student_memories` 升级为“增量维护、结构化、可溯源、可检索”的学生长期记忆 Wiki。

---

## 1. 背景与问题

当前 `student_memories` 本质上是一个扁平的短文本列表：

- 每天由每日复盘流程从行为日志中提取一批 `short_term` 记忆。
- 通过一次 LLM 调用做“冲突检测/合并”。
- AI 对话时把所有 active memories 全量注入 System Prompt。

现有设计存在以下核心问题：

| 问题 | 影响 |
|---|---|
| 记忆结构扁平 | 无法表达“实体 / 概念 / 模式 / 事件”之间的关系 |
| 没有真正的长期记忆闭环 | `long_term` 只是字段，没有晋升、衰减、过期、归档机制 |
| 每次对话全量注入 | token 浪费，记忆越多越干扰，AI 抓不住重点 |
| 证据不可结构化溯源 | 无法支撑教师端 LearningInsight 的证据链 |
| 依赖一次 LLM JSON | 输出不稳定，没有确定性兜底，不可复现 |
| 没有交叉链接 | 记忆之间是孤岛，无法形成知识网络 |
| 审计日志是推断的 | 无法回答“哪条记忆在什么时候因为什么被改动” |

---

## 2. 设计目标

1. **结构化**：把记忆从“文本列表”升级为“页面 + 来源 + 链接 + 事件”的 Wiki 结构。
2. **增量维护**：每天/事件触发时只更新受影响的页面，不全量重建。
3. **可溯源**：每条记忆页面都有结构化证据，支持学生、教师、管理员追溯来源。
4. **可检索**：AI 对话时按相关性检索 top-k 记忆页，而不是全量塞入。
5. **可靠可控**：LLM 输出结构化、有确定性规则兜底、有人工确认入口、可审计回滚。
6. **兼容现有系统**：DailyReview、AIChat、LearningInsight、教师端洞察都能基于新结构升级，同时保留现有接口一段时间。

---

## 3. 总体架构

借鉴 LLM Wiki 的三层架构：

```text
┌─────────────────────────────────────────────────────────────┐
│  Raw Sources（原始证据层）                                    │
│  行为日志、AI对话、任务提交、B站记录、文件、复盘、公告等         │
│  不可变，只追加                                             │
└─────────────────────────────────────────────────────────────┘
                            │ ingest
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  Memory Wiki（记忆层）                                        │
│  memory_pages + memory_sources + memory_links + events       │
│  由 LLM 增量维护，人可确认/修正                              │
└─────────────────────────────────────────────────────────────┘
                            │ 读取 / 检索
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  Consumer（消费方）                                           │
│  AI Chat、Daily Review、LearningInsight、教师端、学生端        │
└─────────────────────────────────────────────────────────────┘
```

Schema（记忆规范）横跨 Human + LLM：

```text
Schema / AGENTS.md
- 页面类型定义
- 分类体系
- 必须包含的字段
- 更新规则
- 冲突处理规则
- 隐私边界
- Lint 规则
```

---

## 4. 核心概念

### 4.1 页面类型

| 类型 | 说明 | 示例 |
|---|---|---|
| `concept` | 知识概念/方法 | “动态规划状态定义” |
| `entity` | 具体实体 | “某课程”、“某比赛”、“某老师” |
| `pattern` | 学习模式/习惯 | “偏好在深夜编程” |
| `goal` | 目标/焦点 | “准备蓝桥杯” |
| `weakness` | 薄弱点 | “论文复现能力弱” |
| `event` | 时间性事件 | “3 月完成开题报告” |
| `relationship` | 关系页面（可选） | “A 是 B 的前置知识” |

### 4.2 页面状态

```text
draft → active → archived
           ↓
       superseded（被新页面/新版本取代）
```

### 4.3 证据来源

每条页面或页面片段可以关联多个结构化证据：

```json
{
  "source_type": "ai_chat | task_submission | daily_review | bilibili | file | behavior_log",
  "source_id": "uuid",
  "user_id": "uuid",
  "occurred_at": "2026-01-01T10:00:00Z",
  "snippet": "原始片段",
  "confidence": 0.8,
  "url": "可选，文件或外部链接"
}
```

---

## 5. 数据模型设计

### 5.1 `memory_pages` — 记忆页

```text
id                  UUID PK
user_id             UUID FK -> users.id
slug                String，唯一（用户内）
page_type           concept | entity | pattern | goal | weakness | event
title               String
summary             Text
body                Text，Markdown
category            String（保留原有分类体系，兼容迁移）
tags                JSONB
confidence          Float
status              draft | active | superseded | archived
source_review_id    UUID FK -> daily_reviews.id（可空）
version             Int
last_reviewed_at    DateTime
expires_at          DateTime（可空）
created_at          DateTime
updated_at          DateTime
```

### 5.2 `memory_sources` — 证据表

```text
id                  UUID PK
page_id             UUID FK -> memory_pages.id
source_type         String
source_id           UUID（对应具体业务表记录）
user_id             UUID FK -> users.id
occurred_at         DateTime
snippet             Text
confidence          Float
metadata            JSONB
created_at          DateTime
```

### 5.3 `memory_links` — 页面关系/双向链接

```text
id                  UUID PK
user_id             UUID FK -> users.id
from_page_id        UUID FK -> memory_pages.id
to_page_id          UUID FK -> memory_pages.id
relation            String（related_to | prerequisite_of | evidence_for | conflicts_with 等）
strength            Float
created_at          DateTime
```

配合唯一约束：

```text
UNIQUE(user_id, from_page_id, to_page_id, relation)
```

### 5.4 `memory_events` — 审计日志

```text
id                  UUID PK
user_id             UUID FK -> users.id
page_id             UUID FK -> memory_pages.id（可空）
action              create | update | merge | split | archive | delete | confirm | reject
before              JSONB
after               JSONB
reason              Text
operator            String（system | student | teacher | admin）
review_id           UUID FK -> daily_reviews.id（可空）
created_at          DateTime
```

### 5.5 `memory_review_tasks` — 人工确认队列

```text
id                  UUID PK
user_id             UUID FK -> users.id
page_id             UUID FK -> memory_pages.id
task_type           create | update | merge | delete | confirm
payload             JSONB
status              pending | approved | rejected | expired
created_by          String
created_at          DateTime
handled_at          DateTime
handled_by          UUID
handled_reason      Text
```

### 5.6 与现有表的关系

- `student_memories` 可作为 **兼容视图/迁移来源** 保留一段时间。
- 迁移时：
  - `content` → `memory_pages.title/body/summary`
  - `evidence` → 拆成 `memory_sources`
  - `superseded_by` → 页面版本/状态
  - `version` → `memory_pages.version`
  - `status` → `memory_pages.status`

---

## 6. LLM 增量维护流水线

核心流程不再“每天全量重算”，而是：

```text
新增来源（行为/对话/任务/文件/复盘）
       │
       ▼
1. 收集增量事件
       │
       ▼
2. 判断影响范围（哪些 memory_pages 可能受影响）
       │
       ▼
3. 读取相关旧页面 + 新增来源
       │
       ▼
4. LLM 结构化输出操作指令
   - create_page
   - update_page
   - merge_pages
   - add_source
   - add_link
   - archive_page
       │
       ▼
5. 确定性规则校验
   - 重复检测（embedding 相似度）
   - 必填字段检查
   - 链接目标是否存在
   - 证据是否有效
       │
       ▼
6. 写入 memory_pages / sources / links / events
       │
       ▼
7. 运行 memory lint
       │
       ▼
8. 需要人工确认的变更进入 review_tasks
```

### 6.1 触发方式

| 触发类型 | 时机 | 示例 |
|---|---|---|
| 定时触发 | 每日 0 点 | 每日复盘后增量更新 |
| 事件触发 | 关键行为发生时 | 任务提交、AI 对话结束、B站观看结束、知识库问答 |
| 手动触发 | 学生/教师主动要求 | “重新分析我这周状态” |

### 6.2 LLM 输出协议

每条维护操作建议使用结构化输出，例如：

```json
{
  "operations": [
    {
      "op": "update_page",
      "page_id": "uuid",
      "changes": {
        "summary": "新的摘要",
        "body": "新的 Markdown",
        "confidence": 0.85
      },
      "reasons": ["今天两次提到动态规划状态定义困难"],
      "new_sources": [
        {
          "source_type": "ai_chat",
          "source_id": "uuid",
          "snippet": "我不确定 dp[i] 是什么意思"
        }
      ],
      "requires_confirmation": false
    },
    {
      "op": "create_page",
      "page": {
        "page_type": "weakness",
        "title": "动态规划状态定义",
        "summary": "学生在状态定义上反复卡住",
        "body": "...",
        "category": "weakness",
        "tags": ["动态规划", "算法"]
      },
      "links": [
        {
          "to_slug": "algorithm-dp",
          "relation": "related_to"
        }
      ]
    }
  ]
}
```

### 6.3 确定性兜底规则

即使 LLM 返回不可用，也要保证系统不崩：

- 解析失败：本次变更不落库，记录 `memory_events` 失败事件，保留原始 LLM 输出。
- 重复检测：使用 embedding 相似度，`similarity > 0.92` 时优先走 `update` 而不是 `create`。
- 置信度计算：
  - 新证据支持 +0.1
  - 矛盾证据 -0.2
  - 超过 30 天未出现 -0.05/周
  - 下限 0，上限 1
- 长期记忆晋升条件：
  - `short_term` 记忆在 3 个不同日期被证据支持
  - 或连续 2 周内出现 5 次
  - 且无矛盾证据
- 过期/归档：
  - `event` 类型超过期限自动 `archived`
  - `pattern` 类连续 60 天未出现，降为 `short_term`

---

## 7. 检索与 AI 注入

### 7.1 检索策略

AI 对话时不再全量注入，改为：

```text
query + 最近上下文
  → 向量检索（embedding）
  + 全文检索（title/summary/tags）
  + 最近活跃页面（last_reviewed_at）
  → 混合排序（RRF 或加权）
  → rerank（可选）
  → 取 top-k（默认 5～10 页）
  → 附带相关证据片段
```

### 7.2 Prompt 注入模板

```text
【学生学习画像（Memory Wiki）】
1. [weakness] 动态规划状态定义
   - 摘要：学生在状态定义上反复卡住
   - 证据：2026-01-02 AI对话：“我不确定 dp[i] 是什么意思”
   - 置信度：0.85
2. [pattern] 偏好在深夜编程
   - 摘要：连续 2 周深夜学习，效率较高
   - 证据：2026-01-01 行为日志 23:30-01:00
   - 置信度：0.78
```

### 7.3 上下文预算

- 设置 Memory Token 预算，例如最多占 System Prompt 的 30%。
- 超出预算时按 `confidence × recency × relevance` 截断。
- 学生可手动开关“是否启用记忆”。

---

## 8. 长期记忆生命周期

```text
                第一次出现
                    │
                    ▼
              short_term
              /          \
      多次证据支持      长期未出现
          │                 │
          ▼                 ▼
      long_term         衰减/归档
          │
          ├─ 矛盾证据 ──→ 冲突检测 → 人工确认
          ├─ 过期 ──────→ archived
          └─ 错误 ──────→ 学生/管理员删除
```

---

## 9. 与现有模块的衔接

| 模块 | 改造前 | 改造后 |
|---|---|---|
| AI Chat | 全量注入 `student_memories` | 检索 top-k 后注入 Memory Wiki 页面 + 证据 |
| Daily Review | 每天生成文本 + 提取短记忆 | 作为 Raw Source 之一，增量触发 Memory Wiki 更新 |
| LearningInsight | 基于扁平 Memory 聚合 | 基于 `memory_pages + memory_sources + memory_links` 生成可溯源洞察 |
| 教师端 | 看到分类数量/文本 | 看到“洞察卡片 + 证据链 + 受影响学生” |
| 管理端 | 查看 Memory 更新日志（推断） | 查看真正 `memory_events` 审计日志 |
| 学生端 | 查看/删除记忆列表 | 可视化 Wiki、证据时间线、确认/修正/删除 |

---

## 10. API 设计

### 10.1 记忆页

```http
GET    /api/v1/memory/pages
GET    /api/v1/memory/pages/{page_id}
POST   /api/v1/memory/pages
PATCH  /api/v1/memory/pages/{page_id}
POST   /api/v1/memory/pages/{page_id}/archive
DELETE /api/v1/memory/pages/{page_id}
```

### 10.2 证据与链接

```http
GET    /api/v1/memory/pages/{page_id}/sources
POST   /api/v1/memory/pages/{page_id}/sources
GET    /api/v1/memory/pages/{page_id}/links
POST   /api/v1/memory/pages/{page_id}/links
```

### 10.3 检索

```http
POST /api/v1/memory/search
Body: { "query": "...", "top_k": 10, "filters": { "page_type": "weakness" } }
```

### 10.4 审计与确认

```http
GET    /api/v1/memory/events
GET    /api/v1/memory/review-tasks
POST   /api/v1/memory/review-tasks/{id}/approve
POST   /api/v1/memory/review-tasks/{id}/reject
```

### 10.5 兼容接口

```http
GET /api/v1/ai/memory  # 返回兼容格式，内部改为读取 memory_pages
GET /api/v1/reviews    # 保留，内部可关联 memory_events
```

---

## 11. 前端设计

### 11.1 学生端

- **记忆主页**：以 Wiki 页面卡片形式展示，支持搜索/筛选。
- **详情页**：显示正文、证据时间线、相关页面、反向链接。
- **知识图谱**：用 `memory_links` 可视化实体/概念之间的关系。
- **人工确认中心**：展示待确认的记忆变更，可批准/拒绝/修改。
- **隐私控制**：可查看哪些记忆被 AI 使用，可一键屏蔽某类记忆。

### 11.2 教师端

- 不直接展示学生原始记忆，而是展示基于 Memory Wiki 生成的洞察。
- 每条洞察可展开证据链：页面 → 来源 → 原文片段 → 时间。

### 11.3 管理端

- 查看 `memory_events` 审计日志。
- 查看 Memory Wiki 健康度：重复页、孤立页、过期页、无证据页。

---

## 12. 权限与隐私

| 数据 | 可见范围 |
|---|---|
| Memory Wiki 页面 | 仅学生本人；教师只能看聚合洞察 |
| 原始证据片段 | 仅学生本人；教师只能在授权范围内看教学相关摘要 |
| memory_events | 学生本人 + 管理员审计 |
| review_tasks | 学生本人；涉及教师洞察的由教师确认 |
| LLM 调用内容 | 按现有安全策略记录，不默认暴露完整私密对话 |

隐私规则：

1. 不自动将敏感个人信息写入长期记忆。
2. 长期记忆必须有多条独立证据支撑。
3. 学生可删除记忆，删除后 AI 不再使用。
4. 删除/合并等敏感操作进入人工确认队列。
5. 所有 AI 维护动作必须写 `memory_events`。

---

## 13. 落地步骤

### Phase 1：数据层改造
- 新增 `memory_pages`、`memory_sources`、`memory_links`、`memory_events`、`memory_review_tasks` 表。
- 编写从 `student_memories` 到新表的迁移脚本。
- 保留旧表兼容，不删数据。

### Phase 2：Memory Wiki Service
- 实现页面 CRUD。
- 实现结构化证据写入。
- 实现链接管理。
- 实现事件审计。
- 实现基础 lint（孤立页、重复页、无证据页、过期页）。

### Phase 3：LLM 增量维护
- 实现增量 ingest pipeline。
- 接入每日复盘触发。
- 接入关键事件触发（任务提交、AI 对话结束等）。
- 实现 embedding 重复检测。
- 实现长期记忆晋升/衰减/归档规则。
- 实现人工确认队列。

### Phase 4：AI 对话检索接入
- 替换全量 Memory 注入。
- 实现混合检索 + top-k 注入。
- 支持 Memory Token 预算。

### Phase 5：前端与洞察
- 学生端 Memory Wiki 页面。
- 证据时间线。
- 知识图谱可视化。
- 教师端洞察改为基于 Memory Wiki 证据链。
- 管理端审计日志页面。

### Phase 6：测试与验收
- Memory pipeline 单元测试。
- LLM 输出解析容错测试。
- 迁移测试。
- 权限/隐私测试。
- 性能测试：千级记忆页检索耗时。

---

## 14. 测试与验收标准

### 14.1 必须通过

1. 同一行为连续出现 3 天后，能自动从 `short_term` 晋升为 `long_term`。
2. 两条相似记忆不会被重复创建，而是合并/提升置信度。
3. 每条长期记忆都至少有一个可点击的结构化证据。
4. AI 对话只注入 top-k 记忆，不超过 Token 预算。
5. 学生拒绝某条记忆后，AI 不再使用。
6. 所有变更都能在 `memory_events` 中查到 before/after/reason。
7. 删除记忆可回滚或至少可审计。

### 14.2 非功能要求

- 单次增量 ingest 在无 LLM 情况下也有确定性兜底结果。
- 千级记忆页检索 P95 < 300ms。
- LLM 解析失败不导致任务失败，能记录并重试。

---

## 15. 风险与对策

| 风险 | 对策 |
|---|---|
| LLM 输出不稳定 | 结构化输出 + 确定性规则 + 失败不落库 |
| 迁移后旧数据不可用 | 保留旧表兼容，提供迁移工具 |
| 增量维护不及时 | 定时 + 事件触发 + 手动触发 |
| 记忆检索不准 | 混合检索 + rerank + 反馈闭环 |
| 隐私风险 | 默认最小可见范围，所有敏感操作确认 + 审计 |
| 维护成本上升 | 先做 Pipeline 核心，再逐步接前端可视化 |

---

## 16. 总结

这个改造的本质是：

> 把“每天让 LLM 从一堆日志里猜几条记忆”变成“让 LLM 像维护个人 Wiki 一样，增量整理一份有来源、有链接、有版本、可审计的学生长期记忆档案”。

它会让 AI 更懂学生、教师洞察更可信、系统长期使用后“越用越准”。