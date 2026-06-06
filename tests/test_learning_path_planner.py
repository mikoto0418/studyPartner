import os
import sys

sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "server"))

from app.services.learning_path_service import LearningPathPlanner


def test_planner_turns_teacher_outline_into_ordered_path():
    plan = LearningPathPlanner.build_plan(
        goal="学习 Transformer 入门",
        planning_text="先理解注意力机制，再学习多头注意力，然后动手复现一个小实验，最后提交学习总结。",
    )

    assert plan["stages"]
    assert len(plan["nodes"]) >= 4
    assert plan["nodes"][0]["title"].startswith("理解")
    assert plan["nodes"][-1]["node_type"] == "submission"
    assert len(plan["edges"]) == len(plan["nodes"]) - 1
    assert plan["edges"][0]["source_key"] == plan["nodes"][0]["key"]
    assert plan["edges"][0]["target_key"] == plan["nodes"][1]["key"]


def test_planner_extracts_bilibili_resource_from_bv_code():
    plan = LearningPathPlanner.build_plan(
        goal="学习 PyTorch 张量基础",
        planning_text="观看 B 站课程 BV1xx411c7mD，整理张量运算笔记，再完成练习。",
    )

    resources = plan["resources"]
    assert resources
    assert resources[0]["resource_type"] == "bilibili"
    assert resources[0]["bv_id"] == "BV1xx411c7mD"
