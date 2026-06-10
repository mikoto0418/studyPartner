import re
from typing import Any, Dict, List, Optional, Tuple


class LearningPathPlanner:
    """Instructional-design based deterministic planner.

    The planner borrows stable instructional design structures instead of
    slicing text mechanically: Backward Design for outcomes/evidence, Merrill's
    task-centered sequence for practice, and Gagne-style events for guidance and
    assessment. It remains deterministic and keeps the same JSON contract.
    """

    STEP_SPLIT_PATTERN = re.compile(r"(?:\s*(?:先|再|然后|接着|最后|其次|之后|，|。|；|;|\n)\s*)+")
    BV_PATTERN = re.compile(r"\b(BV[0-9A-Za-z]{10,})\b")
    URL_PATTERN = re.compile(r"(https?://[^\s，。；;]+|github\.com/[^\s，。；;]+)", re.IGNORECASE)
    FRAMEWORKS = ["backward_design", "merrill_first_principles", "gagne_events"]
    PROJECT_REPRODUCTION_KEYWORDS = (
        "github", "仓库", "拉库", "代码库", "部署", "自部署", "跑通", "实验", "复现", "baseline", "demo", "环境", "依赖"
    )
    PROJECT_ANCHOR_KEYWORDS = ("github", "仓库", "拉库", "代码库", "部署", "自部署", "环境", "依赖")
    ML_KEYWORDS = ("机器学习", "深度学习", "模型", "训练", "数据集", "pytorch", "tensorflow", "sklearn", "实验")

    @classmethod
    def build_plan(cls, goal: str, planning_text: str, title: Optional[str] = None) -> Dict[str, Any]:
        topic = cls._topic(title, goal)
        context = " ".join([title or "", goal or "", planning_text or ""]).lower()
        raw_parts = [part.strip(" ，。；;") for part in cls.STEP_SPLIT_PATTERN.split(planning_text or "") if part.strip()]
        scenario = cls._detect_scenario(context)

        if scenario == "project_reproduction":
            nodes = cls._project_reproduction_nodes(topic, goal, planning_text, context)
        elif len(raw_parts) >= 3:
            nodes = cls._nodes_from_teacher_outline(topic, goal, raw_parts)
        else:
            nodes = cls._general_skill_nodes(topic, goal, planning_text, context)

        nodes = cls._ensure_submission_node(nodes, topic, goal, scenario)
        stages = cls._build_stages_for_scenario(scenario)
        nodes, resources = cls._finalize_nodes(nodes, planning_text, stages)
        edges = [
            {"source_key": nodes[index]["key"], "target_key": nodes[index + 1]["key"]}
            for index in range(max(0, len(nodes) - 1))
        ]

        return {
            "stages": stages,
            "nodes": nodes,
            "edges": edges,
            "resources": resources,
            "summary": cls._summary(topic, goal, scenario, nodes),
        }

    @classmethod
    def _project_reproduction_nodes(cls, topic: str, goal: str, planning_text: str, context: str) -> List[Dict[str, Any]]:
        is_ml = cls._contains_any(context, cls.ML_KEYWORDS)
        stack_hint = "Python/Conda、Git、依赖安装、GPU/CPU 运行差异" if is_ml else "Git、依赖安装、配置文件和运行命令"
        experiment_hint = "训练/推理脚本、数据集、指标和随机种子" if is_ml else "启动脚本、样例数据、配置项和验收日志"
        final_goal = goal.strip() or f"跑通{topic}的核心实验"
        return [
            cls._node(
                "确定目标仓库与验收标准",
                f"围绕「{topic}」明确最终要达到的结果：{final_goal}。记录目标仓库、README 要求、需要跑通的 demo/实验、可接受的运行截图或日志。",
                "checkpoint",
                35,
                0,
                deliverable="仓库链接、验收标准、风险清单",
                success="能说清楚跑通标准、运行入口和最终提交物。",
            ),
            cls._node(
                "补齐复现实验前置基础",
                f"快速补齐 {stack_hint}。只学会本次复现会用到的命令和概念，不做泛泛的理论铺开。",
                "learning",
                60,
                0,
                deliverable="环境准备清单和常用命令速查",
                success="能独立解释每个安装/运行命令的作用。",
            ),
            cls._node(
                "拉取代码并阅读项目入口",
                f"克隆仓库，阅读 README、requirements、配置示例和主入口脚本，标出 {experiment_hint} 所在位置。",
                "reading",
                55,
                1,
                deliverable="项目结构笔记、入口脚本路径、关键配置项",
                success="能找到安装命令、运行命令、数据/权重放置位置。",
            ),
            cls._node(
                "创建隔离环境并安装依赖",
                "使用 Conda/venv/Docker 中的一种方式创建隔离环境，按 README 安装依赖；记录版本冲突、缺包、CUDA/CPU 适配等问题。",
                "practice",
                90,
                1,
                deliverable="可复用环境安装命令和问题记录",
                success="依赖安装完成，核心 import 或启动命令不再因环境问题失败。",
            ),
            cls._node(
                "准备数据、权重与配置文件",
                "按项目要求准备最小数据、预训练权重或示例配置；如果数据较大，先使用 toy data 或官方 sample 验证流程。",
                "practice",
                75,
                1,
                deliverable="数据/权重目录说明和配置文件备份",
                success="运行脚本能正确找到数据、权重和配置。",
            ),
            cls._node(
                "跑通最小 demo 并定位报错",
                "先跑官方 demo、quickstart 或最短推理/训练命令。遇到报错时按环境、路径、依赖、数据、显存五类归档排查。",
                "practice",
                110,
                2,
                deliverable="demo 运行日志、报错排查记录、成功截图",
                success="至少一次完整运行结束，并留下可复现命令。",
            ),
            cls._node(
                "复现一个常见实验并记录指标",
                f"选择一个难度可控的{topic}常见实验或 baseline，记录参数、运行耗时、输出指标，并和 README/论文预期结果做对照。",
                "practice",
                130,
                2,
                deliverable="实验命令、参数表、指标截图或日志",
                success="能解释实验输出是否合理，以及差异可能来自哪里。",
            ),
            cls._node(
                "整理部署脚本与复现说明",
                "把安装、配置、运行、常见报错整理成一份可交给同学复跑的说明；如需要自部署，补充启动脚本、端口、环境变量和资源需求。",
                "practice",
                80,
                2,
                deliverable="复现 README 或部署说明",
                success="别人按说明能复现你的最小运行流程。",
            ),
            cls._node(
                "提交复现实验报告与后续问题",
                f"提交「{topic}」复现实验报告，包含仓库链接、环境版本、运行命令、实验结果、失败记录、解决方案和下一步想深入的问题。",
                "submission",
                55,
                3,
                deliverable="实验报告、运行截图、日志或附件",
                success="报告能证明从拉库到跑通实验的完整闭环。",
            ),
        ]

    @classmethod
    def _nodes_from_teacher_outline(cls, topic: str, goal: str, parts: List[str]) -> List[Dict[str, Any]]:
        nodes = []
        total = len(parts)
        for index, part in enumerate(parts[:10]):
            node_type = cls._infer_node_type(part, index, total)
            stage_order = cls._stage_order_for_index(index, total, node_type)
            deliverable = cls._deliverable_for_node(node_type, topic)
            nodes.append(cls._node(
                cls._build_title(part, node_type, index, topic),
                cls._enrich_description(part, node_type, topic, goal, deliverable),
                node_type,
                cls._estimate_minutes(node_type),
                stage_order,
                deliverable=deliverable,
                success=cls._success_for_node(node_type, topic),
            ))
        return nodes

    @classmethod
    def _general_skill_nodes(cls, topic: str, goal: str, planning_text: str, context: str) -> List[Dict[str, Any]]:
        final_goal = goal.strip() or f"掌握{topic}"
        is_ml = cls._contains_any(context, cls.ML_KEYWORDS)
        concept_focus = "训练/验证/测试、特征、模型、损失函数、评估指标" if is_ml else "核心概念、关键术语、常见误区"
        practice_focus = "用 sklearn 或 PyTorch 跑通一个小数据集训练/评估流程" if is_ml else f"完成一个能验证「{final_goal}」的小练习"
        return [
            cls._node(
                "明确学习目标与验收方式",
                f"把「{final_goal}」改写成可验证结果，确认最终要提交什么、做到什么程度算完成。",
                "checkpoint",
                30,
                0,
                deliverable="目标清单、验收标准、已有基础自评",
                success="能用一句话说清最终产出和判断标准。",
            ),
            cls._node(
                f"建立{topic}核心概念地图",
                f"梳理本主题必须理解的 {concept_focus}，标记自己完全不懂和需要老师解释的部分。",
                "learning",
                60,
                0,
                deliverable="概念地图和问题清单",
                success="能解释关键概念之间的关系。",
            ),
            cls._node(
                "阅读/观看一份高质量入门材料",
                f"选择一份课程、文档或示例项目，围绕「{topic}」记录关键步骤、例子和容易卡住的点。",
                "reading",
                55,
                1,
                deliverable="材料笔记和关键问题",
                success="能复述材料中的主线，而不是只摘抄概念。",
            ),
            cls._node(
                "跟做一个最小示例",
                f"照着材料完成一个最小可运行示例，重点确认输入、处理过程、输出结果和评价方式。",
                "practice",
                90,
                1,
                deliverable="最小示例结果、运行截图或笔记",
                success="示例能跑通，且能解释每一步在做什么。",
            ),
            cls._node(
                "完成独立练习并记录反馈",
                practice_focus + "；记录第一次失败原因、修改过程和最终结果。",
                "practice",
                110,
                2,
                deliverable="练习结果、错误记录、改进说明",
                success="不看教程也能完成同类小任务。",
            ),
            cls._node(
                "做一次迁移应用",
                f"换一个数据、案例或约束条件，把前面学到的方法迁移到新场景，观察哪些步骤需要调整。",
                "practice",
                95,
                2,
                deliverable="迁移实验记录或对比表",
                success="能说明方法适用边界和调整原因。",
            ),
            cls._node(
                "提交学习总结与下一步问题",
                f"提交「{topic}」学习总结，包含概念图、练习结果、踩坑记录、仍不理解的问题和下一步计划。",
                "submission",
                50,
                3,
                deliverable="学习总结、练习附件、后续问题",
                success="总结能证明已从理解进入可应用阶段。",
            ),
        ]

    @staticmethod
    def _node(
        title: str,
        description: str,
        node_type: str,
        minutes: int,
        stage_order: int,
        deliverable: str,
        success: str,
    ) -> Dict[str, Any]:
        return {
            "key": "",
            "title": title,
            "description": description,
            "node_type": node_type,
            "order_index": 0,
            "estimated_minutes": minutes,
            "required": True,
            "config": {
                "source": "instructional_design_planner",
                "frameworks": LearningPathPlanner.FRAMEWORKS,
                "stage_order": stage_order,
                "deliverable": deliverable,
                "success_criteria": success,
            },
            "resources": [],
        }

    @classmethod
    def _finalize_nodes(
        cls,
        nodes: List[Dict[str, Any]],
        planning_text: str,
        stages: List[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        resources: List[Dict[str, Any]] = []
        global_resource_text = planning_text or ""
        seen_resource_keys = set()
        for index, node in enumerate(nodes[:12]):
            node_key = f"node_{index + 1}"
            node["key"] = node_key
            node["order_index"] = index
            stage_order = int((node.get("config") or {}).get("stage_order", 0) or 0)
            node["config"]["stage_order"] = min(max(stage_order, 0), len(stages) - 1)

            resource_text = f"{node.get('title', '')} {node.get('description', '')}"
            if any(keyword in node.get("title", "") for keyword in ["仓库", "README", "代码"]):
                resource_text = f"{resource_text} {global_resource_text}"
            node_resources = cls._extract_resources(resource_text, node_key)
            unique_node_resources = []
            for resource in node_resources:
                key = (resource.get("resource_type"), resource.get("url"), resource.get("bv_id"))
                if key in seen_resource_keys:
                    continue
                seen_resource_keys.add(key)
                unique_node_resources.append(resource)
                resources.append(resource)
            node["resources"] = unique_node_resources
        return nodes[:12], resources

    @classmethod
    def _ensure_submission_node(
        cls,
        nodes: List[Dict[str, Any]],
        topic: str,
        goal: str,
        scenario: str,
    ) -> List[Dict[str, Any]]:
        if any(node.get("node_type") == "submission" for node in nodes):
            return nodes
        deliverable = "复现实验报告、运行截图和部署说明" if scenario == "project_reproduction" else "学习总结、练习结果和后续问题"
        nodes.append(cls._node(
            f"提交{topic}学习成果",
            f"围绕「{goal.strip() or topic}」提交成果材料，说明完成了什么、证据是什么、还卡在哪里。",
            "submission",
            45,
            3,
            deliverable=deliverable,
            success="教师能根据提交物判断学习目标是否达成。",
        ))
        return nodes

    @classmethod
    def _build_stages_for_scenario(cls, scenario: str) -> List[Dict[str, Any]]:
        if scenario == "project_reproduction":
            return [
                {"title": "目标与准备", "description": "先明确最终验收，再补齐复现实验必需基础。", "order_index": 0},
                {"title": "环境与代码", "description": "读懂仓库入口，完成依赖、数据、配置准备。", "order_index": 1},
                {"title": "实验与部署", "description": "跑通最小 demo、复现实验，并沉淀部署脚本。", "order_index": 2},
                {"title": "交付复盘", "description": "提交证据、复盘问题，形成可复用说明。", "order_index": 3},
            ]
        return [
            {"title": "目标与前置", "description": "明确学习结果和验收方式，激活已有基础。", "order_index": 0},
            {"title": "输入与示范", "description": "通过材料、示例和讲解建立可跟做路径。", "order_index": 1},
            {"title": "练习与迁移", "description": "完成从跟做到独立应用的练习闭环。", "order_index": 2},
            {"title": "评估与复盘", "description": "提交成果、获得反馈，并整理后续问题。", "order_index": 3},
        ]

    @classmethod
    def _extract_resources(cls, text: str, node_key: str) -> List[Dict[str, Any]]:
        resources = []
        for match in cls.BV_PATTERN.findall(text or ""):
            resources.append({
                "resource_type": "bilibili",
                "title": f"B 站视频 {match}",
                "url": f"https://www.bilibili.com/video/{match}",
                "bv_id": match,
                "file_id": None,
                "metadata": {"node_key": node_key},
            })
        for raw_url in cls.URL_PATTERN.findall(text or ""):
            url = raw_url if raw_url.lower().startswith("http") else f"https://{raw_url}"
            resources.append({
                "resource_type": "link",
                "title": "GitHub 仓库" if "github.com" in url.lower() else "参考链接",
                "url": url,
                "bv_id": None,
                "file_id": None,
                "metadata": {"node_key": node_key},
            })
        return resources

    @classmethod
    def _detect_scenario(cls, context: str) -> str:
        keyword_hits = sum(1 for keyword in cls.PROJECT_REPRODUCTION_KEYWORDS if keyword in context)
        has_project_anchor = any(keyword in context for keyword in cls.PROJECT_ANCHOR_KEYWORDS)
        if has_project_anchor and keyword_hits >= 2:
            return "project_reproduction"
        return "general_skill"

    @staticmethod
    def _topic(title: Optional[str], goal: str) -> str:
        raw = (title or goal or "当前主题").strip()
        raw = re.sub(r"^(学习|掌握|了解|完成|实现|能|能够|会)", "", raw).strip()
        raw = re.sub(r"(入门|基础|学习路径|路径|任务)$", "", raw).strip()
        return raw or (goal.strip() or "当前主题")

    @staticmethod
    def _contains_any(text: str, keywords: Tuple[str, ...]) -> bool:
        return any(keyword.lower() in text for keyword in keywords)

    @classmethod
    def _infer_node_type(cls, text: str, index: int, total: int) -> str:
        lower_text = text.lower()
        if cls.BV_PATTERN.search(text) or "视频" in text or "b站" in lower_text or "bilibili" in lower_text:
            return "video"
        if any(keyword in text for keyword in ["阅读", "文档", "资料", "论文", "课件", "README", "readme"]):
            return "reading"
        if any(keyword in text for keyword in ["练习", "实验", "复现", "实现", "代码", "案例", "部署", "跑通", "安装"]):
            return "practice"
        if any(keyword in text for keyword in ["提交", "总结", "报告", "作业", "附件"]):
            return "submission"
        if any(keyword in text for keyword in ["检查", "测验", "自测", "阶段", "目标", "验收"]):
            return "checkpoint"
        if index == total - 1 and total <= 3:
            return "practice"
        return "learning"

    @staticmethod
    def _stage_order_for_index(index: int, total: int, node_type: str) -> int:
        if node_type == "submission":
            return 3
        if total <= 3:
            return min(index, 2)
        if index < max(1, total // 4):
            return 0
        if index < max(2, total // 2):
            return 1
        return 2

    @staticmethod
    def _build_title(text: str, node_type: str, index: int, topic: str) -> str:
        compact = re.sub(r"\s+", "", text)
        compact = re.sub(r"\bBV[0-9A-Za-z]{10,}\b", "", compact).strip(" ，。；;")
        compact = re.sub(r"https?://[^\s，。；;]+|github\.com/[^\s，。；;]+", "", compact).strip(" ，。；;")
        if compact:
            if len(compact) > 24:
                compact = compact[:24] + "..."
            return compact
        labels = {
            "video": f"观看{topic}示范材料",
            "reading": f"阅读{topic}核心资料",
            "practice": f"完成{topic}实践练习",
            "submission": f"提交{topic}学习成果",
            "checkpoint": f"确认{topic}阶段目标",
        }
        return labels.get(node_type, f"{topic}学习节点 {index + 1}")

    @staticmethod
    def _enrich_description(part: str, node_type: str, topic: str, goal: str, deliverable: str) -> str:
        success = LearningPathPlanner._success_for_node(node_type, topic)
        return f"{part}。本节点产出：{deliverable}。完成标准：{success}"

    @staticmethod
    def _deliverable_for_node(node_type: str, topic: str) -> str:
        return {
            "video": "观看笔记、关键截图或疑问清单",
            "reading": "资料笔记、术语表和关键问题",
            "practice": "可运行结果、代码/截图和错误记录",
            "submission": "总结报告、附件或反思文档",
            "checkpoint": "验收标准、阶段自评和风险清单",
            "learning": "概念图、关键术语和问题清单",
        }.get(node_type, f"{topic}学习记录")

    @staticmethod
    def _success_for_node(node_type: str, topic: str) -> str:
        return {
            "video": "能复述示范流程，并指出自己要照做的关键步骤。",
            "reading": "能找到关键入口、参数或概念，并记录不理解的问题。",
            "practice": "能得到可验证输出，并记录失败到成功的修改过程。",
            "submission": "提交物能证明目标达成，并能让教师追溯过程。",
            "checkpoint": "能判断当前是否具备进入下一阶段的条件。",
            "learning": "能用自己的话解释关键概念，而不是只复制定义。",
        }.get(node_type, f"能说明{topic}当前节点的完成证据。")

    @staticmethod
    def _estimate_minutes(node_type: str) -> int:
        return {
            "video": 45,
            "reading": 55,
            "practice": 95,
            "submission": 50,
            "checkpoint": 35,
            "learning": 60,
        }.get(node_type, 60)

    @staticmethod
    def _summary(topic: str, goal: str, scenario: str, nodes: List[Dict[str, Any]]) -> str:
        total_minutes = sum(int(node.get("estimated_minutes") or 0) for node in nodes)
        if scenario == "project_reproduction":
            return (
                f"已按项目复现路径将「{topic}」拆成 {len(nodes)} 个节点：先定义验收标准，"
                f"再完成环境/代码/数据准备，随后跑通 demo、复现实验并提交报告。预计约 {total_minutes} 分钟。"
            )
        return (
            f"已按目标-证据-学习活动的方式将「{goal.strip() or topic}」拆成 {len(nodes)} 个节点，"
            f"覆盖前置诊断、材料输入、实践迁移和提交复盘。预计约 {total_minutes} 分钟。"
        )
