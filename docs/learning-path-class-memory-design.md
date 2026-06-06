# 学习路径任务、班级 Memory 看板与学生成长档案分层设计

版本：V0.1
状态：设计草案
适用阶段：下一阶段功能扩展
关联模块：任务系统、AI Memory、每日复盘、知识库、B站学习、教师端、学生端

---

## 一、设计结论

本次扩展不建议继续增强普通“任务管理”，而应新增一条更符合平台定位的核心业务线：

> 教师提出学习目标 → AI 拆解学习路径 → 教师图谱化微调 → 发布给班级或学生 → 学生按步骤完成 → 教师评分与追评 → Memory 沉淀 → 班级与个人看板复盘。

该能力分三层落地：

| 层级 | 模块 | 目标 |
|---|---|---|
| L1 | 学习路径任务 | 把“大目标”拆成可执行、可提交、可评分的步骤链 |
| L2 | 班级 Memory 看板 | 让教师从班级视角看整体趋势、共性薄弱点和风险学生 |
| L3 | 学生成长档案 | 让学生、教师或家长看到个人学习投入、成果与 Memory 演化 |

第一版应先做最小闭环：学习路径任务可发布、可执行、可提交、可评分；班级看板先做聚合概况；学生成长档案先做数据全览，不急于做复杂导出。

---

## 二、需求边界

### 2.1 本阶段要做

1. 教师端新增独立页面“学习路径任务”。
2. 教师输入大目标，AI 生成结构化学习路径。
3. 路径用图谱/结构化路径展示，支持老师微调节点。
4. 节点支持添加 B 站 BV 号、文档附件、提交要求、截止时间、评分规则。
5. 学生端新增学习路径执行视图，必须按步骤推进。
6. 学生可在节点提交文本和附件。
7. 教师可评分、写评语、退回、允许二次开放、追评。
8. 新增班级/分组概念，教师可按班级查看概况。
9. 班级概况基于行为数据、任务进度和 Memory 聚合生成。
10. 学生端新增个人数据全览，可作为成长档案基础。

### 2.2 本阶段不做

1. 不做完整学习通级别的题库、考试、自动阅卷。
2. 不强依赖真实读取 B 站播放器进度，仍沿用页面停留与心跳估算。
3. 不在第一版引入复杂图编辑依赖；MVP 可用原生 SVG/HTML 渲染路径，后续升级 Vue Flow 或 AntV X6。
4. 不把学生完整对话暴露给教师或家长。
5. 不让 AI 自动最终评分，AI 只生成评分草稿或评语建议，最终由教师确认。

---

## 三、业务闭环

### 3.1 教师创建路径任务

1. 教师选择发布对象：班级、学生组或单个学生。
2. 教师输入粗粒度目标、周期、难度、最终产出。
3. AI 根据目标生成阶段、步骤、依赖关系和建议资源类型。
4. 教师进入路径编辑器，调整节点、补充 BV 号、上传资料、设置提交要求。
5. 教师预览学生视角后发布。

### 3.2 学生执行路径任务

1. 学生在“学习路径”页面看到总任务进度。
2. 系统只解锁当前可执行节点。
3. 学生观看视频、阅读资料、完成节点提交。
4. 需要评分的节点进入“待批改”。
5. 被退回后，学生根据评语修改并重新提交。
6. 全部必做节点通过后，总任务完成。

### 3.3 教师评价与追踪

1. 教师在路径详情中查看班级整体进度。
2. 教师按节点查看学生提交。
3. 教师给分、写评语、退回或通过。
4. 教师可开启二次开放，允许学生补交或重交。
5. 教师可追加追评，形成完整评价链。
6. 评分、评语、退回原因进入学生 Memory 和每日复盘候选数据。

### 3.4 Memory 反哺

1. 学生在路径中的卡点会成为短期 Memory 候选。
2. 多次出现的薄弱点会升级为长期 Memory。
3. 班级中高频出现的问题会形成班级共性 Memory。
4. 后续 AI 伴学与教师看板都基于这些 Memory 给出建议。

---

## 四、学习路径任务设计

### 4.1 核心对象

学习路径任务由四类对象组成：

| 对象 | 说明 |
|---|---|
| Path Task | 总任务，如“3 周掌握 Transformer 基础” |
| Stage | 阶段，如“前置知识”“核心概念”“实践输出” |
| Node | 具体步骤，如“观看 Attention 视频”“提交学习笔记” |
| Edge | 节点依赖关系，如“完成 Step 1 后解锁 Step 2” |

### 4.2 节点类型

| 类型 | 说明 | 是否需要提交 |
|---|---|---|
| `concept` | 概念学习节点 | 可选 |
| `bilibili_video` | B 站观看节点，绑定 BV 号 | 可选 |
| `reading` | 阅读资料节点，绑定附件或知识库文档 | 可选 |
| `practice` | 实践任务节点，如代码、实验、推导 | 通常需要 |
| `submission` | 正式提交节点，如报告、笔记、作业 | 必须 |
| `checkpoint` | 阶段检查点 | 可选 |
| `discussion` | 讨论或答疑节点 | 可选 |

### 4.3 节点状态

| 状态 | 含义 |
|---|---|
| `locked` | 前置节点未完成，暂不可做 |
| `todo` | 可开始 |
| `in_progress` | 学生已开始 |
| `submitted` | 学生已提交，等待教师评价 |
| `approved` | 教师通过 |
| `rejected` | 教师退回 |
| `reopened` | 教师开启二次开放 |
| `completed` | 无需评分节点已完成 |

### 4.4 教师微调能力

教师可对每个节点做以下调整：

1. 修改标题、说明、目标。
2. 调整所属阶段。
3. 调整前后依赖。
4. 设置是否必做。
5. 设置预计学习时长。
6. 添加 B 站 BV 号或普通链接。
7. 上传参考资料。
8. 选择是否要求提交。
9. 设置提交格式：文本、附件、链接、Markdown。
10. 设置评分规则：满分、评分维度、是否允许重交。
11. 设置截止时间。

### 4.5 AI 拆解输出结构

AI 不直接输出自由文本，而应输出结构化 JSON，后端校验后再入库。

```json
{
  "title": "Transformer 三周学习路径",
  "goal": "掌握 Transformer 基础并提交学习报告",
  "stages": [
    {
      "temp_id": "stage_1",
      "title": "前置知识",
      "description": "补齐理解 Attention 所需的数学和表示学习基础",
      "order_index": 1
    }
  ],
  "nodes": [
    {
      "temp_id": "node_1",
      "stage_temp_id": "stage_1",
      "type": "concept",
      "title": "复习矩阵乘法与向量表示",
      "objective": "理解后续 Attention 计算的基础",
      "estimated_minutes": 60,
      "is_required": true,
      "requires_submission": true,
      "submission_prompt": "提交一份 300 字学习笔记"
    }
  ],
  "edges": [
    {
      "from": "node_1",
      "to": "node_2",
      "relation": "must_finish_before"
    }
  ]
}
```

### 4.6 路径图谱展示

第一版采用“阶段泳道 + 节点卡 + 连线”的结构：

```text
阶段一：前置知识
[矩阵与向量] → [词嵌入] → [自注意力预习]

阶段二：核心概念
[Attention 视频] → [Multi-Head Attention] → [位置编码]

阶段三：实践输出
[论文阅读] → [报告初稿] → [教师评分] → [完成]
```

教师端重点是编辑能力；学生端重点是完成状态、当前步骤和反馈。

后续升级方向：

| 方案 | 使用场景 |
|---|---|
| 原生 SVG/HTML | 第一版，低依赖、可控 |
| Vue Flow | 中期升级，支持拖拽、连线、节点编辑 |
| AntV X6 | 更复杂编排场景 |

---

## 五、班级 Memory 看板设计

### 5.1 班级模型

新增班级/分组不是为了替代角色权限，而是为了让教师聚焦自己负责的学生集合。

班级支持：

1. 班级名称。
2. 任课/负责教师。
3. 学生成员。
4. 当前路径任务。
5. 班级概况统计。
6. 班级 Memory 快照。

### 5.2 班级看板核心指标

| 区块 | 指标 |
|---|---|
| 活跃趋势 | 每日活跃人数、平均学习时长、连续活跃人数 |
| 路径进度 | 每个学习路径完成率、卡点节点、逾期节点 |
| 任务质量 | 平均分、退回率、重交率、优秀提交数 |
| Memory 共性 | 高频薄弱点、共同兴趣、常见学习习惯 |
| 风险学生 | 连续不活跃、关键节点卡住、长期 Memory 显示拖延 |
| AI 总结 | 周总结、月总结、教学建议 |

### 5.3 班级 Memory 聚合规则

班级 Memory 只能是聚合洞察，不暴露个人隐私原文。

可展示：

```text
班级共性观察：
- 68% 学生在 Attention 公式推导节点停留时间较长。
- 45% 学生的 Memory 显示“更偏好视频先导入，再阅读论文”。
- 近 7 天任务退回原因主要集中在“概念复述不完整”。
```

不可展示：

```text
某学生完整 AI 对话内容。
某学生私密 Memory 原文。
与教学无关的个人信息。
```

### 5.4 定期总结

班级看板应支持：

1. 每周班级总结。
2. 每月班级总结。
3. 指定学习路径总结。
4. 教师可手动生成总结。

总结输入：

- 班级任务完成数据。
- 学习路径节点进度。
- 学生每日复盘摘要。
- Memory 聚合统计。
- 教师评分与评语标签。

总结输出：

- 本周期班级学习状态。
- 共性薄弱点。
- 进度异常。
- 下周教学建议。
- 值得表扬的学习行为类型。

---

## 六、学生成长档案设计

### 6.1 目标

学生成长档案面向学生本人，也可生成教师/家长可读的脱敏视图。它回答三个问题：

1. 我最近学了什么？
2. 我在哪些能力上进步了？
3. 我的学习习惯和薄弱点发生了什么变化？

### 6.2 页面内容

| 区块 | 内容 |
|---|---|
| 学习总览 | 学习时长、活跃天数、任务完成率、路径完成率 |
| 学习路径 | 正在进行和已完成的路径任务 |
| 能力雷达 | 根据节点类型、评分、Memory 标签形成能力维度 |
| Memory 演化 | 新增 Memory、置信度变化、已归档 Memory |
| 成果档案 | 提交过的报告、笔记、文档、代码链接 |
| 教师评价 | 最近评分、评语、追评 |
| AI 阶段总结 | 周总结、月总结 |
| 导出报告 | Markdown 或 PDF 成长报告 |

### 6.3 家长/外部视图

导出给家长或外部人员时默认脱敏：

1. 不展示完整 AI 对话。
2. 不展示私密 Memory。
3. 不展示具体敏感文件内容。
4. 展示学习投入、路径进度、教师评价、成果摘要。

---

## 七、数据模型草案

### 7.1 班级相关

#### `classes`

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | UUID | 主键 |
| `name` | VARCHAR | 班级名称 |
| `description` | TEXT | 班级说明 |
| `owner_teacher_id` | UUID | 负责教师 |
| `status` | VARCHAR | active / archived |
| `created_at` | TIMESTAMPTZ | 创建时间 |
| `updated_at` | TIMESTAMPTZ | 更新时间 |

#### `class_members`

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | UUID | 主键 |
| `class_id` | UUID | 班级 ID |
| `student_id` | UUID | 学生 ID |
| `joined_at` | TIMESTAMPTZ | 加入时间 |

### 7.2 学习路径任务相关

#### `learning_path_tasks`

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | UUID | 主键 |
| `creator_id` | UUID | 创建教师 |
| `class_id` | UUID | 所属班级，可空 |
| `title` | VARCHAR | 路径任务标题 |
| `goal` | TEXT | 总目标 |
| `description` | TEXT | 说明 |
| `status` | VARCHAR | draft / published / archived |
| `difficulty` | VARCHAR | easy / medium / hard |
| `start_at` | TIMESTAMPTZ | 开始时间 |
| `due_at` | TIMESTAMPTZ | 总截止时间 |
| `ai_plan_source` | JSONB | AI 原始拆解结果 |
| `created_at` | TIMESTAMPTZ | 创建时间 |
| `updated_at` | TIMESTAMPTZ | 更新时间 |

#### `learning_path_stages`

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | UUID | 主键 |
| `path_task_id` | UUID | 路径任务 ID |
| `title` | VARCHAR | 阶段标题 |
| `description` | TEXT | 阶段说明 |
| `order_index` | INTEGER | 排序 |

#### `learning_path_nodes`

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | UUID | 主键 |
| `path_task_id` | UUID | 路径任务 ID |
| `stage_id` | UUID | 阶段 ID |
| `type` | VARCHAR | 节点类型 |
| `title` | VARCHAR | 节点标题 |
| `objective` | TEXT | 学习目标 |
| `instructions` | TEXT | 操作说明 |
| `order_index` | INTEGER | 排序 |
| `estimated_minutes` | INTEGER | 预计耗时 |
| `is_required` | BOOLEAN | 是否必做 |
| `requires_submission` | BOOLEAN | 是否要求提交 |
| `submission_prompt` | TEXT | 提交要求 |
| `score_max` | INTEGER | 满分 |
| `due_at` | TIMESTAMPTZ | 节点截止时间 |
| `metadata` | JSONB | 图谱坐标、样式等扩展信息 |

#### `learning_path_edges`

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | UUID | 主键 |
| `path_task_id` | UUID | 路径任务 ID |
| `from_node_id` | UUID | 起点节点 |
| `to_node_id` | UUID | 终点节点 |
| `relation` | VARCHAR | must_finish_before / recommended_before |

#### `learning_path_resources`

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | UUID | 主键 |
| `node_id` | UUID | 节点 ID |
| `resource_type` | VARCHAR | bilibili / file / link / knowledge_doc |
| `title` | VARCHAR | 资源标题 |
| `bvid` | VARCHAR | B 站 BV 号 |
| `file_id` | UUID | 文件 ID |
| `url` | VARCHAR | 外部链接 |
| `metadata` | JSONB | 分 P、观看要求等 |

#### `learning_path_assignees`

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | UUID | 主键 |
| `path_task_id` | UUID | 路径任务 ID |
| `student_id` | UUID | 学生 ID |
| `status` | VARCHAR | not_started / in_progress / completed |
| `progress_percent` | FLOAT | 完成进度 |
| `assigned_at` | TIMESTAMPTZ | 分配时间 |
| `completed_at` | TIMESTAMPTZ | 完成时间 |

#### `learning_node_progress`

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | UUID | 主键 |
| `node_id` | UUID | 节点 ID |
| `student_id` | UUID | 学生 ID |
| `status` | VARCHAR | locked / todo / in_progress / submitted / approved / rejected / reopened / completed |
| `started_at` | TIMESTAMPTZ | 开始时间 |
| `submitted_at` | TIMESTAMPTZ | 最近提交时间 |
| `completed_at` | TIMESTAMPTZ | 完成时间 |
| `attempt_count` | INTEGER | 提交次数 |

#### `learning_node_submissions`

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | UUID | 主键 |
| `node_id` | UUID | 节点 ID |
| `student_id` | UUID | 学生 ID |
| `content` | TEXT | 提交文本 |
| `attachment_ids` | JSONB | 附件 ID 列表 |
| `status` | VARCHAR | submitted / approved / rejected |
| `created_at` | TIMESTAMPTZ | 提交时间 |

#### `learning_node_reviews`

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | UUID | 主键 |
| `submission_id` | UUID | 提交 ID |
| `reviewer_id` | UUID | 教师 ID |
| `score` | FLOAT | 得分 |
| `feedback` | TEXT | 评语 |
| `review_type` | VARCHAR | first_review / rereview / followup |
| `allow_resubmit` | BOOLEAN | 是否允许重交 |
| `created_at` | TIMESTAMPTZ | 评价时间 |

### 7.3 聚合快照相关

#### `class_memory_snapshots`

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | UUID | 主键 |
| `class_id` | UUID | 班级 ID |
| `period_start` | DATE | 周期开始 |
| `period_end` | DATE | 周期结束 |
| `memory_summary` | JSONB | 聚合 Memory 摘要 |
| `risk_summary` | JSONB | 风险摘要 |
| `ai_report` | TEXT | AI 生成总结 |
| `created_at` | TIMESTAMPTZ | 创建时间 |

#### `student_growth_reports`

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | UUID | 主键 |
| `student_id` | UUID | 学生 ID |
| `period_start` | DATE | 周期开始 |
| `period_end` | DATE | 周期结束 |
| `report_type` | VARCHAR | weekly / monthly / custom |
| `report_content` | TEXT | 报告正文 |
| `metrics` | JSONB | 指标快照 |
| `visibility` | VARCHAR | private / teacher / guardian_safe |
| `created_at` | TIMESTAMPTZ | 创建时间 |

---

## 八、接口设计草案

### 8.1 教师端学习路径任务

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/v1/learning-paths/generate` | 根据教师目标生成 AI 路径草稿 |
| POST | `/api/v1/learning-paths` | 创建路径任务 |
| GET | `/api/v1/learning-paths` | 教师查看自己创建的路径任务 |
| GET | `/api/v1/learning-paths/{id}` | 获取路径任务详情 |
| PUT | `/api/v1/learning-paths/{id}` | 更新路径任务基础信息 |
| POST | `/api/v1/learning-paths/{id}/publish` | 发布路径任务 |
| POST | `/api/v1/learning-paths/{id}/nodes` | 新增节点 |
| PUT | `/api/v1/learning-paths/nodes/{node_id}` | 更新节点 |
| DELETE | `/api/v1/learning-paths/nodes/{node_id}` | 删除节点 |
| POST | `/api/v1/learning-paths/nodes/{node_id}/resources` | 添加节点资源 |
| GET | `/api/v1/learning-paths/{id}/submissions` | 查看路径下全部提交 |
| POST | `/api/v1/learning-paths/submissions/{submission_id}/review` | 教师评价提交 |

### 8.2 学生端学习路径

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/learning-paths/student` | 学生查看分配给自己的路径 |
| GET | `/api/v1/learning-paths/student/{id}` | 学生查看路径详情 |
| POST | `/api/v1/learning-paths/nodes/{node_id}/start` | 标记节点开始 |
| POST | `/api/v1/learning-paths/nodes/{node_id}/complete` | 完成无需提交节点 |
| POST | `/api/v1/learning-paths/nodes/{node_id}/submit` | 提交节点作业 |

### 8.3 班级与班级看板

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/v1/classes` | 创建班级 |
| GET | `/api/v1/classes` | 获取教师负责班级 |
| GET | `/api/v1/classes/{id}` | 班级详情 |
| POST | `/api/v1/classes/{id}/members` | 添加班级成员 |
| DELETE | `/api/v1/classes/{id}/members/{student_id}` | 移除成员 |
| GET | `/api/v1/classes/{id}/overview` | 班级概况看板 |
| GET | `/api/v1/classes/{id}/memory-summary` | 班级 Memory 聚合 |
| POST | `/api/v1/classes/{id}/memory-snapshots/generate` | 生成班级周期总结 |

### 8.4 学生成长档案

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/growth/me` | 学生查看自己的成长档案 |
| GET | `/api/v1/growth/students/{student_id}` | 教师查看关联学生成长档案 |
| POST | `/api/v1/growth/reports/generate` | 生成阶段成长报告 |
| GET | `/api/v1/growth/reports/{report_id}` | 查看成长报告 |

---

## 九、前端页面规划

### 9.1 教师端页面

#### `/teacher/learning-paths`

学习路径任务列表。

主要内容：

1. 路径任务列表。
2. 状态筛选：草稿、已发布、已归档。
3. 班级筛选。
4. 新建路径任务按钮。
5. 每条路径显示完成率、卡点节点、待批改数。

#### `/teacher/learning-paths/:id`

学习路径编辑与批改页。

布局：

| 区域 | 内容 |
|---|---|
| 左侧 | 路径阶段与节点导航 |
| 中间 | 图谱路径画布 |
| 右侧 | 当前节点配置或提交详情 |
| 底部 | 发布、保存草稿、学生视角预览 |

#### `/teacher/classes`

班级概况页。

主要内容：

1. 班级选择器。
2. 活跃趋势折线图。
3. 路径任务完成漏斗。
4. 共性 Memory 标签云。
5. 风险学生列表。
6. AI 周总结。

### 9.2 学生端页面

#### `/student/learning-paths`

学生学习路径列表。

主要内容：

1. 进行中的路径。
2. 已完成路径。
3. 总完成率。
4. 当前待完成节点。

#### `/student/learning-paths/:id`

路径执行页。

主要内容：

1. 总目标与进度。
2. 路径图谱缩略图。
3. 当前节点操作面板。
4. 资源区：B 站视频、附件、知识库文档。
5. 提交区：文本、附件。
6. 教师反馈区：评分、评语、追评。

#### `/student/growth`

学生成长档案。

主要内容：

1. 学习数据总览。
2. 学习路径进度。
3. Memory 演化。
4. 教师评价摘要。
5. 成果档案。
6. 阶段报告。

---

## 十、与现有模块的关系

| 现有模块 | 接入方式 |
|---|---|
| 任务系统 | 路径任务是更高阶任务，不替换普通任务 |
| B站模块 | 节点资源可绑定 BV 号并复用观看记录 |
| 文件系统 | 节点资源和学生提交均复用文件上传 |
| 知识库 | 节点可绑定知识库文档，AI 可基于节点资源问答 |
| AI 对话 | 学生询问时注入当前路径、当前节点和节点资源 |
| Memory | 节点完成、卡点、退回、评分进入 Memory 候选 |
| 每日复盘 | 增加路径任务维度：当前节点、卡点、提交质量 |
| 热力图 | 路径节点完成与视频学习计入活跃度 |

---

## 十一、权限与隐私规则

1. 教师只能查看自己负责班级或关联学生。
2. 学生只能查看分配给自己的路径任务。
3. 班级 Memory 只展示聚合结果，不展示完整个人对话。
4. 家长/外部视图默认脱敏。
5. AI 评语只能作为草稿，教师确认后才对学生可见。
6. 学生可对进入 Memory 的评价结论提出纠错或删除申请。
7. 管理员可审计任务、评价和 AI 调用日志，但不默认展示私密对话全文。

---

## 十二、分层实施计划

### Phase A：文档与数据模型

1. 完成本设计文档评审。
2. 补充数据库设计文档。
3. 补充 API 设计文档。
4. 明确最小验收标准。

### Phase B：后端基础层

1. 新增班级表与成员表。
2. 新增学习路径任务、阶段、节点、边、资源表。
3. 新增学生节点进度、提交、评价表。
4. 实现基础 CRUD。
5. 实现权限过滤。

### Phase C：AI 拆解层

1. 新增 `learning_path_generate` LLM 任务类型。
2. 实现路径生成 Prompt。
3. 实现 JSON Schema 校验。
4. 支持教师二次编辑后保存。

### Phase D：教师端页面

1. 学习路径任务列表。
2. 路径编辑器。
3. 资源配置。
4. 批改与追评。
5. 班级概况看板第一版。

### Phase E：学生端页面

1. 学习路径列表。
2. 路径执行页。
3. 节点提交。
4. 反馈查看。
5. 学生成长档案第一版。

### Phase F：Memory 与总结增强

1. 每日复盘纳入学习路径数据。
2. Memory 提取纳入节点卡点、评分、退回原因。
3. 班级 Memory 快照生成。
4. 学生成长报告生成。

---

## 十三、第一版验收标准

1. 教师可以创建班级并添加学生。
2. 教师可以输入学习目标并生成路径草稿。
3. 教师可以编辑路径节点，添加 BV 号和附件。
4. 教师可以发布路径任务给班级或学生。
5. 学生可以看到路径任务并按节点推进。
6. 学生可以在要求提交的节点提交文本和附件。
7. 教师可以评分、写评语、退回。
8. 教师可以允许二次提交并追加追评。
9. 班级看板可以展示路径完成率、活跃趋势、风险学生和 Memory 聚合摘要。
10. 学生成长档案可以展示个人学习数据、路径进度、Memory 摘要和教师评价摘要。

---

## 十四、风险与控制

| 风险 | 影响 | 控制 |
|---|---|---|
| 功能面过大 | 开发周期变长 | 分阶段做，先完成路径任务最小闭环 |
| AI 拆解质量不稳定 | 路径不可用 | 使用结构化输出、Schema 校验、教师必须确认 |
| 图谱编辑复杂 | 前端实现成本高 | 第一版先用阶段节点图，后续升级 Vue Flow |
| 班级 Memory 涉及隐私 | 教师看到过多个人信息 | 只展示聚合摘要和教学相关标签 |
| 学习时长数据不精确 | 误导评价 | 标注为估算数据，不作为唯一评分依据 |
| 文件和提交链路复杂 | 权限风险 | 复用现有 files 权限，节点提交单独校验 |

---

## 十五、推荐下一步

下一步不直接全量编码，建议先做 Phase A 的文档补齐：

1. 将本文拆分同步到数据库设计文档。
2. 将接口草案同步到 API 设计文档。
3. 建立第一版开发清单。
4. 从后端数据模型开始实现。

第一批实现建议只包含：

1. `classes`、`class_members`。
2. `learning_path_tasks`、`learning_path_stages`、`learning_path_nodes`、`learning_path_edges`。
3. `learning_path_assignees`、`learning_node_progress`。
4. 教师端路径任务列表与创建草稿。
5. 学生端路径列表与详情只读展示。

这样可以先把结构跑通，再继续做提交、评分、追评、班级 Memory 和成长档案。
