import os
import sys

sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "server"))

from app.services.learning_path_ai_planner import LearningPathAIPlanner, LearningPathWebResearcher
from app.services.learning_path_planner import LearningPathPlanner


def test_researcher_extracts_normalized_urls_without_duplicates():
    urls = LearningPathWebResearcher.extract_urls(
        "参考 https://github.com/langchain-ai/langchain，再看 github.com/langchain-ai/langchain。"
    )

    assert urls == ["https://github.com/langchain-ai/langchain"]


def test_ai_planner_normalizes_llm_json_and_keeps_verified_resource_urls():
    fallback = LearningPathPlanner.build_plan(
        title="机器学习项目复现",
        goal="能跑通常见实验",
        planning_text="从 GitHub 拉库到本地部署并提交实验报告",
    )
    research = {
        "enabled": True,
        "input_urls": ["https://github.com/owner/repo"],
        "items": [
            {
                "title": "owner/repo",
                "url": "https://github.com/owner/repo",
                "source_type": "github_repository",
                "content": "README: pip install -r requirements.txt; python demo.py",
                "metadata": {"readme_url": "https://github.com/owner/repo#readme"},
            }
        ],
        "errors": [],
    }
    llm_plan = {
        "stages": [
            {"title": "确认目标", "description": "明确仓库和验收标准"},
            {"title": "复现部署", "description": "跑通环境、demo 和实验"},
            {"title": "提交复盘", "description": "提交报告"},
        ],
        "nodes": [
            {
                "title": "确认仓库与验收标准",
                "description": "记录目标仓库、最小 demo、最终提交证据。",
                "node_type": "checkpoint",
                "stage_order": 0,
                "estimated_minutes": 30,
                "deliverable": "仓库链接和验收清单",
                "success_criteria": "能说明跑通标准",
                "resources": [
                    {"resource_type": "link", "title": "仓库", "url": "https://github.com/owner/repo"}
                ],
            },
            {
                "title": "阅读 README 与项目入口",
                "description": "找出安装命令、运行脚本、数据/权重位置。",
                "node_type": "reading",
                "stage_order": 0,
                "estimated_minutes": 45,
                "deliverable": "README 笔记",
                "success_criteria": "能定位核心入口",
                "resources": [
                    {"resource_type": "link", "title": "编造链接", "url": "https://example.com/not-allowed"}
                ],
            },
            {
                "title": "安装依赖并跑通 demo",
                "description": "创建隔离环境，安装依赖，执行 demo 命令。",
                "node_type": "practice",
                "stage_order": 1,
                "estimated_minutes": 120,
                "deliverable": "运行日志和截图",
                "success_criteria": "demo 可完整结束",
            },
            {
                "title": "提交复现实验报告",
                "description": "提交环境版本、命令、结果截图和失败记录。",
                "node_type": "submission",
                "stage_order": 2,
                "estimated_minutes": 60,
                "deliverable": "复现报告",
                "success_criteria": "教师可复查全过程",
            },
        ],
        "summary": "按项目复现流程组织路径。",
    }

    plan = LearningPathAIPlanner._normalize_llm_plan(
        llm_plan,
        fallback=fallback,
        research=research,
        model="test-model",
        provider="test-provider",
    )

    assert len(plan["nodes"]) == 4
    assert plan["nodes"][-1]["node_type"] == "submission"
    assert len(plan["edges"]) == 3
    assert plan["nodes"][0]["resources"][0]["url"] == "https://github.com/owner/repo"
    assert plan["nodes"][1]["resources"] == []
    assert plan["nodes"][0]["config"]["source"] == "llm_learning_path_planner"
    assert "联网资料" in plan["summary"]


def test_ai_planner_appends_submission_when_llm_omits_final_submission():
    fallback = LearningPathPlanner.build_plan(
        title="Python 入门",
        goal="能写一个命令行脚本",
        planning_text="学习语法并完成小练习",
    )
    llm_plan = {
        "stages": [{"title": "学习", "description": "学习和练习"}],
        "nodes": [
            {"title": "确认目标", "description": "写清楚脚本需求", "node_type": "checkpoint"},
            {"title": "学习基础语法", "description": "掌握变量、函数和文件读写", "node_type": "learning"},
            {"title": "完成脚本练习", "description": "实现命令行脚本并运行", "node_type": "practice"},
            {"title": "改造一个新案例", "description": "换一组输入重新运行", "node_type": "practice"},
        ],
    }

    plan = LearningPathAIPlanner._normalize_llm_plan(
        llm_plan,
        fallback=fallback,
        research={"enabled": False, "items": [], "errors": []},
    )

    assert plan["nodes"][-1]["node_type"] == "submission"
    assert plan["nodes"][-1]["config"]["structural_patch"] == "append_submission_node"
