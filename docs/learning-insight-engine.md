# LearningInsight 洞察引擎设计

## 定位

`LearningInsight` 是教师端 Agent 平台的核心中间层：它把学生学情记忆、学习路径进度、提交批改状态转成教师可处理的“洞察卡片”。它不是前端展示字段，也不是临时 mock，而是有数据库表、生成逻辑、证据链和状态流转的业务对象。

## 数据模型

表：`learning_insights`

| 字段 | 说明 |
|---|---|
| `scope` | 洞察范围，当前支持 `class`，后续可扩展 `student` |
| `class_id` | 关联班级 |
| `student_id` | 单学生洞察时使用 |
| `teacher_id` | 洞察所属教师 |
| `title` | 教师可直接理解的标题 |
| `insight_type` | `memory_pattern`、`progress_risk`、`review_backlog` 等 |
| `severity` | `high`、`medium`、`low` |
| `summary` | 面向教师的内容摘要 |
| `affected_student_ids` | 受影响学生 ID 列表 |
| `evidence` | 证据链，包含来源、学生、片段和时间 |
| `suggested_actions` | Agent 可执行动作建议 |
| `status` | `new`、`acknowledged`、`resolved`、`dismissed` |
| `source_fingerprint` | 系统生成洞察的稳定指纹，用于去重和状态保留 |

## 当前生成来源

1. **学情记忆内容聚合**
   - 来源：`student_memories`
   - 聚合方式：按 `category + content` 归并相近内容。
   - 输出：共性薄弱点、学习习惯、学习目标等内容型洞察。

2. **学习路径进度风险**
   - 来源：`learning_path_assignees`
   - 规则：未完成路径平均进度低于 60%。
   - 输出：需要跟进的学生名单和进度证据。

3. **待批改提交积压**
   - 来源：`learning_node_submissions`
   - 规则：班级下 `review_status=pending` 的学习路径节点提交。
   - 输出：待处理提交数量、涉及路径和学生。

## API

```http
GET /api/v1/learning-paths/classes/{class_id}/overview
```

返回班级概况，并在 `insights` 字段中包含当前可见洞察。

```http
PATCH /api/v1/learning-paths/insights/{insight_id}/status
Content-Type: application/json

{ "status": "acknowledged" }
```

用于教师更新洞察状态。

## 状态闭环

| 状态 | 含义 |
|---|---|
| `new` | 系统新发现，教师尚未处理 |
| `acknowledged` | 教师已读，仍保留在看板 |
| `resolved` | 已处理或系统判断不再存在 |
| `dismissed` | 教师手动忽略 |

系统刷新洞察时会保留已解决/已忽略状态，避免同一条指纹反复打扰教师。

## 设计约束

- 不允许兜底 mock；无真实数据时返回空洞察。
- 所有教师可见结论必须带证据链。
- Agent 动作先以 `suggested_actions` 表示，执行发布/通知/批量改动时必须进入人在回路确认。
- 未来可把规则生成器替换为 LLM/Agent，但必须保持同一数据合同。
