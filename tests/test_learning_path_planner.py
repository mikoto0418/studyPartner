import os
import sys

sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "server"))

from app.services.learning_path_planner import LearningPathPlanner


def test_planner_turns_teacher_outline_into_ordered_path():
    plan = LearningPathPlanner.build_plan(
        goal="学习 Transformer 入门",
        planning_text="先理解注意力机制，再学习多头注意力，然后动手复现一个小实验，最后提交学习总结。",
    )

    assert plan["stages"]
    assert len(plan["nodes"]) >= 4
    assert "理解" in plan["nodes"][0]["title"]
    assert plan["nodes"][-1]["node_type"] == "submission"
    assert len(plan["edges"]) == len(plan["nodes"]) - 1
    assert plan["edges"][0]["source_key"] == plan["nodes"][0]["key"]
    assert plan["edges"][0]["target_key"] == plan["nodes"][1]["key"]
    assert plan["nodes"][0]["config"]["source"] == "instructional_design_planner"


def test_planner_extracts_bilibili_resource_from_bv_code():
    plan = LearningPathPlanner.build_plan(
        goal="学习 PyTorch 张量基础",
        planning_text="观看 B 站课程 BV1xx411c7mD，整理张量运算笔记，再完成练习。",
    )

    resources = plan["resources"]
    assert resources
    assert resources[0]["resource_type"] == "bilibili"
    assert resources[0]["bv_id"] == "BV1xx411c7mD"


def test_planner_builds_project_reproduction_path_for_ml_github_task():
    plan = LearningPathPlanner.build_plan(
        title="机器学习入门",
        goal="能跑通常见实验",
        planning_text="从 github 拉库到自部署，从小白到能初步跑通实验",
    )

    titles = [node["title"] for node in plan["nodes"]]
    descriptions = "\n".join(node["description"] for node in plan["nodes"])

    assert len(plan["nodes"]) >= 8
    assert plan["stages"][0]["title"] == "目标与准备"
    assert any("目标仓库" in title or "验收标准" in title for title in titles)
    assert any("安装依赖" in title or "隔离环境" in title for title in titles)
    assert any("最小 demo" in title for title in titles)
    assert any("复现一个常见实验" in title for title in titles)
    assert plan["nodes"][-1]["node_type"] == "submission"
    assert "机器学习" in descriptions
    assert "实验报告" in plan["nodes"][-1]["config"]["deliverable"]
