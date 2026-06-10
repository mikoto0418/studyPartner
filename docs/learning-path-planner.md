# 学习路径 AI 规划器设计

## 结论

学习路径生成已经从“规则切句”升级为 **LLM 主体规划 + 真实联网取证 + 规则结构校验**。

旧的 `LearningPathPlanner` 仍保留，但定位变为：

- 给 LLM 提供教学设计草稿参考；
- 当 LLM 漏掉提交节点、阶段等结构时做协议修补；
- 支撑手动创建路径时的兼容逻辑。

教师点击“AI 生成路径”时不再静默返回机械草案。模型通道不可用、JSON 无效或生成失败时，接口会明确返回错误，避免产生“看起来生成了，实际不可用”的路径。

## 设计目标

| 目标 | 实现 |
|---|---|
| 不再机械拆句 | 由 LLM 根据目标、粗略规划、联网资料生成节点 |
| 可联网 | 支持显式 URL 读取、GitHub 仓库 README 读取、GitHub 仓库搜索 |
| 不编造资源 | `resources.url` 只保留联网资料或教师输入中出现过的 URL |
| 可验证 | 每个节点必须包含动作、产出物、验收标准 |
| 可落库 | 返回结构仍兼容 `stages / nodes / edges / resources / summary` |
| 可配置 | 通过 LLM 任务类型 `learning_path_generate` 单独配置模型 |

## 生成链路

1. 教师输入标题、学习目标、粗略规划，并可勾选“联网增强”。
2. 后端先用 `LearningPathPlanner` 生成一份教学设计草稿，仅作为参考和结构校验。
3. `LearningPathWebResearcher` 收集真实资料：
   - 输入中的 `https://...` 或 `github.com/...`；
   - GitHub 仓库元数据、README、语言、主题、默认分支；
   - 当输入明显是“仓库/复现/部署/实验”场景时，调用 GitHub Search API 搜索候选仓库。
4. `LearningPathAIPlanner` 调用 LLM 网关任务 `learning_path_generate`，要求模型只输出 JSON。
5. 服务端归一化和校验：
   - 节点类型限定为 `learning / video / reading / practice / submission / checkpoint`；
   - 至少 4 个可用节点；
   - 最后一个节点必须是 `submission`；
   - 外链资源必须来自联网资料白名单；
   - 自动生成线性 `edges`。
6. 前端进入“路径草案微调”，教师仍可编辑节点、资源和发布范围。

## 联网边界

当前版本不做不稳定的网页爬虫式全网搜索。联网能力聚焦在教学路径最需要闭环的资料来源：

| 来源 | 用途 |
|---|---|
| 显式 URL | 教师给出的课程、文档、项目页作为证据 |
| GitHub 仓库 | 读取仓库描述、语言、主题、README |
| GitHub Search API | 在“仓库/复现/部署/实验”场景下检索候选项目 |

如果 GitHub 限流或网络失败，错误会进入生成上下文；系统不会伪造搜索结果。

## LLM 输出协议

模型必须输出 JSON 对象：

```json
{
  "stages": [
    {
      "title": "阶段名",
      "description": "阶段说明",
      "order_index": 0
    }
  ],
  "nodes": [
    {
      "title": "节点标题",
      "description": "具体学习动作、材料、产出和验收方式",
      "node_type": "learning",
      "stage_order": 0,
      "estimated_minutes": 60,
      "deliverable": "本节点应提交或留下的证据",
      "success_criteria": "判断完成质量的标准",
      "resources": [
        {
          "resource_type": "link",
          "title": "资源标题",
          "url": "只能使用联网资料或教师输入中出现过的 URL"
        }
      ]
    }
  ],
  "summary": "路径设计说明"
}
```

服务端会把它归一化为现有 `LearningPathPlanOut`。

节点 `config` 会记录：

| 字段 | 说明 |
|---|---|
| `source` | `llm_learning_path_planner` |
| `planner_version` | `llm_web_research_v1` |
| `frameworks` | 使用的教学设计框架 |
| `stage_order` | 所属阶段 |
| `deliverable` | 节点产出 |
| `success_criteria` | 完成标准 |
| `research_used` | 是否使用联网资料 |
| `research_urls` | 实际使用的资料 URL |
| `llm_model` | 本次调用模型 |
| `llm_provider` | 本次调用供应商 |

## 配置

管理端 LLM 配置页新增任务类型：

```text
learning_path_generate
```

建议给它配置上下文能力较强、JSON 输出稳定的模型。环境变量兜底仍沿用现有 SiliconFlow 配置：

```env
SILICONFLOW_API_KEY=...
SILICONFLOW_BASE_URL=https://api.siliconflow.cn/v1
SILICONFLOW_CHAT_MODEL=...
```

联网参数：

```env
LEARNING_PATH_WEB_RESEARCH_TIMEOUT_SECONDS=8
LEARNING_PATH_WEB_RESEARCH_MAX_RESULTS=5
```

## 失败策略

| 场景 | 行为 |
|---|---|
| LLM 未配置 | 返回 `LEARNING_PATH_AI_GENERATION_FAILED` |
| LLM 调用失败 | 返回明确错误，不静默生成机械路径 |
| LLM JSON 无效 | 返回明确错误，提示重试或换更强模型 |
| 联网失败 | 记录错误，仍把真实错误交给 LLM 作为上下文 |
| 教师手动创建节点 | 不依赖 LLM，仍可保存发布 |

## 参考来源

- GitHub REST API：Search repositories
  https://docs.github.com/rest/search/search#search-repositories
- GitHub REST API：Get a repository README
  https://docs.github.com/rest/repos/contents#get-a-repository-readme
- OpenAI Structured Outputs
  https://platform.openai.com/docs/guides/structured-outputs
