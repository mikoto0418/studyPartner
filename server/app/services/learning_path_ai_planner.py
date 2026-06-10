import base64
import html
import json
import logging
import os
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urlparse

import httpx

from app.services.learning_path_planner import LearningPathPlanner

logger = logging.getLogger(__name__)


@dataclass
class LearningPathResearchItem:
    title: str
    url: str
    source_type: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class LearningPathWebResearcher:
    """Collects real web evidence for path planning.

    The service intentionally keeps the first version provider-free: it can read
    explicit URLs, GitHub repositories, README files, and perform unauthenticated
    GitHub repository search when the request is clearly project/repo-oriented.
    """

    URL_PATTERN = re.compile(
        r"(https?://[^\s，。；;,)）]+|github\.com/[^\s，。；;,)）]+)",
        re.IGNORECASE,
    )
    GITHUB_REPO_PATTERN = re.compile(
        r"github\.com[:/](?P<owner>[^/\s#?]+)/(?P<repo>[^/\s#?.]+(?:\.[^/\s#?.]+)?)",
        re.IGNORECASE,
    )
    SCRIPT_STYLE_PATTERN = re.compile(r"<(script|style).*?</\1>", re.IGNORECASE | re.DOTALL)
    TAG_PATTERN = re.compile(r"<[^>]+>")
    PROJECT_HINTS = (
        "github",
        "仓库",
        "拉库",
        "代码库",
        "部署",
        "自部署",
        "复现",
        "实验",
        "demo",
        "baseline",
        "readme",
    )

    @classmethod
    async def collect(
        cls,
        title: Optional[str],
        goal: str,
        planning_text: str,
        enabled: bool = True,
    ) -> Dict[str, Any]:
        context = " ".join([title or "", goal or "", planning_text or ""])
        urls = cls.extract_urls(context)
        if not enabled:
            return {"enabled": False, "input_urls": urls, "items": [], "errors": []}

        timeout_seconds = cls._float_env("LEARNING_PATH_WEB_RESEARCH_TIMEOUT_SECONDS", 8.0)
        max_results = cls._int_env("LEARNING_PATH_WEB_RESEARCH_MAX_RESULTS", 5)
        items: List[LearningPathResearchItem] = []
        errors: List[str] = []
        headers = {
            "Accept": "application/vnd.github+json, text/html, text/plain;q=0.9, */*;q=0.8",
            "User-Agent": "StudyPartner-LearningPathPlanner/1.0",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        timeout = httpx.Timeout(timeout_seconds, connect=min(timeout_seconds, 5.0))
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers=headers) as client:
            for url in urls[:max_results]:
                try:
                    item = await cls._fetch_url(client, url)
                    if item:
                        items.append(item)
                except Exception as exc:
                    errors.append(f"{url}: {cls._short_error(exc)}")

            if len(items) < max_results and cls._should_search_github(context):
                try:
                    search_items = await cls._search_github_repositories(
                        client,
                        title=title,
                        goal=goal,
                        planning_text=planning_text,
                        limit=max_results - len(items),
                    )
                    items.extend(search_items)
                except Exception as exc:
                    errors.append(f"GitHub 搜索失败: {cls._short_error(exc)}")

        deduped = cls._dedupe_items(items)[:max_results]
        return {
            "enabled": True,
            "input_urls": urls,
            "items": [asdict(item) for item in deduped],
            "errors": errors[:5],
        }

    @classmethod
    def extract_urls(cls, text: str) -> List[str]:
        urls: List[str] = []
        seen: Set[str] = set()
        for raw in cls.URL_PATTERN.findall(text or ""):
            url = raw.strip().rstrip("。；;，,")
            if not url.lower().startswith("http"):
                url = f"https://{url}"
            if url not in seen:
                seen.add(url)
                urls.append(url)
        return urls

    @classmethod
    async def _fetch_url(cls, client: httpx.AsyncClient, url: str) -> Optional[LearningPathResearchItem]:
        github_repo = cls._github_repo_from_url(url)
        if github_repo:
            owner, repo = github_repo
            return await cls._fetch_github_repo(client, owner, repo)

        response = await client.get(url)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        text = response.text
        title = cls._title_from_html(text) or urlparse(str(response.url)).netloc or url
        if "html" in content_type.lower():
            text = cls._clean_html(text)
        return LearningPathResearchItem(
            title=title,
            url=str(response.url),
            source_type="web_page",
            content=cls._truncate(text, 3500),
            metadata={"content_type": content_type},
        )

    @classmethod
    async def _fetch_github_repo(
        cls,
        client: httpx.AsyncClient,
        owner: str,
        repo: str,
    ) -> LearningPathResearchItem:
        repo = repo.removesuffix(".git")
        repo_url = f"https://api.github.com/repos/{owner}/{repo}"
        repo_response = await client.get(repo_url)
        repo_response.raise_for_status()
        repo_data = repo_response.json()

        readme_text = ""
        readme_url = repo_data.get("html_url") or f"https://github.com/{owner}/{repo}"
        try:
            readme_response = await client.get(f"https://api.github.com/repos/{owner}/{repo}/readme")
            if readme_response.status_code == 200:
                readme_data = readme_response.json()
                readme_url = readme_data.get("html_url") or readme_url
                readme_text = cls._decode_github_content(readme_data.get("content", ""))
        except Exception as exc:
            logger.info("Failed to fetch GitHub README for %s/%s: %s", owner, repo, exc)

        topics = repo_data.get("topics") or []
        content_parts = [
            f"仓库：{repo_data.get('full_name') or f'{owner}/{repo}'}",
            f"描述：{repo_data.get('description') or '无描述'}",
            f"主要语言：{repo_data.get('language') or '未知'}",
            f"默认分支：{repo_data.get('default_branch') or '未知'}",
            f"主题：{', '.join(topics[:8]) if topics else '无'}",
            f"Stars：{repo_data.get('stargazers_count') or 0}",
        ]
        if readme_text:
            content_parts.append("README 摘要：\n" + cls._truncate(readme_text, 4200))

        return LearningPathResearchItem(
            title=repo_data.get("full_name") or f"{owner}/{repo}",
            url=repo_data.get("html_url") or f"https://github.com/{owner}/{repo}",
            source_type="github_repository",
            content=cls._truncate("\n".join(content_parts), 5200),
            metadata={
                "owner": owner,
                "repo": repo,
                "readme_url": readme_url,
                "language": repo_data.get("language"),
                "topics": topics,
                "default_branch": repo_data.get("default_branch"),
            },
        )

    @classmethod
    async def _search_github_repositories(
        cls,
        client: httpx.AsyncClient,
        title: Optional[str],
        goal: str,
        planning_text: str,
        limit: int,
    ) -> List[LearningPathResearchItem]:
        query = cls._github_query(title, goal, planning_text)
        if not query:
            return []

        response = await client.get(
            "https://api.github.com/search/repositories",
            params={
                "q": f"{query} in:name,description,readme",
                "sort": "stars",
                "order": "desc",
                "per_page": max(1, min(limit, 3)),
            },
        )
        response.raise_for_status()
        data = response.json()
        results: List[LearningPathResearchItem] = []
        for repo in data.get("items", [])[:limit]:
            html_url = repo.get("html_url")
            parsed = cls._github_repo_from_url(html_url or "")
            if not parsed:
                continue
            try:
                item = await cls._fetch_github_repo(client, parsed[0], parsed[1])
                item.metadata["search_query"] = query
                item.metadata["search_rank"] = len(results) + 1
                results.append(item)
            except Exception as exc:
                logger.info("Failed to hydrate GitHub search result %s: %s", html_url, exc)
                results.append(LearningPathResearchItem(
                    title=repo.get("full_name") or html_url or "GitHub 仓库",
                    url=html_url or "",
                    source_type="github_repository_search_result",
                    content=cls._truncate(
                        "\n".join([
                            f"仓库：{repo.get('full_name')}",
                            f"描述：{repo.get('description') or '无描述'}",
                            f"主要语言：{repo.get('language') or '未知'}",
                            f"Stars：{repo.get('stargazers_count') or 0}",
                        ]),
                        1200,
                    ),
                    metadata={"search_query": query, "search_rank": len(results) + 1},
                ))
        return results

    @classmethod
    def _github_repo_from_url(cls, url: str) -> Optional[tuple[str, str]]:
        match = cls.GITHUB_REPO_PATTERN.search(url or "")
        if not match:
            return None
        owner = match.group("owner").strip()
        repo = match.group("repo").strip().removesuffix(".git")
        if owner and repo:
            return owner, repo
        return None

    @classmethod
    def _should_search_github(cls, context: str) -> bool:
        lower_context = (context or "").lower()
        return any(hint in lower_context for hint in cls.PROJECT_HINTS)

    @classmethod
    def _github_query(cls, title: Optional[str], goal: str, planning_text: str) -> str:
        raw = " ".join([title or "", goal or "", planning_text or ""])
        raw = cls.URL_PATTERN.sub(" ", raw)
        tokens = re.findall(r"[A-Za-z0-9_\-+.]{2,}|[\u4e00-\u9fff]{2,}", raw)
        stopwords = {
            "github",
            "仓库",
            "拉库",
            "代码库",
            "部署",
            "自部署",
            "实验",
            "复现",
            "能够",
            "常见",
            "入门",
            "学习",
            "路径",
            "任务",
            "从小白到",
        }
        useful = [token for token in tokens if token.lower() not in stopwords]
        if not useful:
            return ""
        return " ".join(useful[:6])

    @classmethod
    def _clean_html(cls, text: str) -> str:
        cleaned = cls.SCRIPT_STYLE_PATTERN.sub(" ", text or "")
        cleaned = cls.TAG_PATTERN.sub(" ", cleaned)
        cleaned = html.unescape(cleaned)
        return re.sub(r"\s+", " ", cleaned).strip()

    @staticmethod
    def _title_from_html(text: str) -> Optional[str]:
        match = re.search(r"<title[^>]*>(.*?)</title>", text or "", re.IGNORECASE | re.DOTALL)
        if not match:
            return None
        return re.sub(r"\s+", " ", html.unescape(match.group(1))).strip()

    @staticmethod
    def _decode_github_content(content: str) -> str:
        if not content:
            return ""
        return base64.b64decode(content.encode("utf-8"), validate=False).decode("utf-8", errors="ignore")

    @staticmethod
    def _dedupe_items(items: List[LearningPathResearchItem]) -> List[LearningPathResearchItem]:
        deduped: List[LearningPathResearchItem] = []
        seen: Set[str] = set()
        for item in items:
            key = item.url.lower().rstrip("/")
            if not key or key in seen:
                continue
            seen.add(key)
            deduped.append(item)
        return deduped

    @staticmethod
    def _truncate(text: str, limit: int) -> str:
        compact = re.sub(r"\s+", " ", text or "").strip()
        if len(compact) <= limit:
            return compact
        return compact[:limit].rstrip() + "..."

    @staticmethod
    def _short_error(exc: Exception) -> str:
        return re.sub(r"\s+", " ", str(exc)).strip()[:180] or exc.__class__.__name__

    @staticmethod
    def _int_env(name: str, default: int) -> int:
        try:
            return max(1, int(os.getenv(name, default)))
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _float_env(name: str, default: float) -> float:
        try:
            return max(1.0, float(os.getenv(name, default)))
        except (TypeError, ValueError):
            return default


class LearningPathAIPlanner:
    TASK_TYPE = "learning_path_generate"
    ALLOWED_NODE_TYPES = {"learning", "video", "reading", "practice", "submission", "checkpoint"}
    FRAMEWORKS = [
        "backward_design",
        "merrill_first_principles",
        "gagne_events",
        "project_based_learning",
    ]

    @classmethod
    async def build_plan(
        cls,
        goal: str,
        planning_text: str,
        title: Optional[str] = None,
        user_id: Optional[Any] = None,
        enable_web_research: bool = True,
        allow_deterministic_fallback: bool = False,
    ) -> Dict[str, Any]:
        deterministic_draft = LearningPathPlanner.build_plan(goal, planning_text, title)
        research = await LearningPathWebResearcher.collect(
            title=title,
            goal=goal,
            planning_text=planning_text,
            enabled=enable_web_research,
        )
        messages = cls._messages(title, goal, planning_text, deterministic_draft, research)

        try:
            from app.core.llm import ChatMessage, llm_router

            response = await llm_router.route(
                cls.TASK_TYPE,
                [ChatMessage(role=item["role"], content=item["content"]) for item in messages],
                user_id=user_id,
                temperature=0.2,
                max_tokens=4096,
            )
        except Exception as exc:
            if allow_deterministic_fallback:
                return cls._fallback_plan(deterministic_draft, research, exc)
            raise RuntimeError(
                "LLM 学习路径通道不可用，请在模型配置中启用 learning_path_generate，"
                "或检查环境变量 SILICONFLOW_API_KEY。"
            ) from exc

        try:
            plan_obj = cls._extract_json_object(response.content)
            return cls._normalize_llm_plan(
                plan_obj,
                fallback=deterministic_draft,
                research=research,
                model=response.model,
                provider=response.provider,
            )
        except Exception as exc:
            if allow_deterministic_fallback:
                return cls._fallback_plan(deterministic_draft, research, exc)
            raise RuntimeError(
                "LLM 已返回内容，但不是有效学习路径 JSON；请重试或换用更强的规划模型。"
            ) from exc

    @classmethod
    def _messages(
        cls,
        title: Optional[str],
        goal: str,
        planning_text: str,
        deterministic_draft: Dict[str, Any],
        research: Dict[str, Any],
    ) -> List[Dict[str, str]]:
        draft_nodes = [
            {
                "title": node.get("title"),
                "node_type": node.get("node_type"),
                "deliverable": (node.get("config") or {}).get("deliverable"),
                "success_criteria": (node.get("config") or {}).get("success_criteria"),
            }
            for node in deterministic_draft.get("nodes", [])[:10]
        ]
        research_items = [
            {
                "title": item.get("title"),
                "url": item.get("url"),
                "source_type": item.get("source_type"),
                "content": item.get("content"),
                "metadata": item.get("metadata") or {},
            }
            for item in (research.get("items") or [])[:5]
        ]
        payload = {
            "task": {
                "title": title,
                "goal": goal,
                "planning_text": planning_text,
            },
            "web_research": {
                "enabled": research.get("enabled"),
                "input_urls": research.get("input_urls") or [],
                "items": research_items,
                "errors": research.get("errors") or [],
            },
            "rule_draft_for_reference_only": draft_nodes,
            "required_json_schema": {
                "stages": [
                    {"title": "阶段名", "description": "阶段说明", "order_index": 0}
                ],
                "nodes": [
                    {
                        "title": "节点标题",
                        "description": "具体学习动作、材料、产出和验收方式",
                        "node_type": "learning|video|reading|practice|submission|checkpoint",
                        "stage_order": 0,
                        "estimated_minutes": 60,
                        "deliverable": "本节点应提交/留下的证据",
                        "success_criteria": "判断完成质量的标准",
                        "resources": [
                            {
                                "resource_type": "link|bilibili|file|text",
                                "title": "资源标题",
                                "url": "只能使用联网资料或教师输入中出现过的 URL",
                                "bv_id": "仅 B 站资源填写",
                            }
                        ],
                    }
                ],
                "summary": "用一句话说明路径设计逻辑和预估投入",
            },
        }
        system_prompt = (
            "你是面向教师的学习路径规划 Agent。你必须把粗略目标升级为可执行、可验收、可追踪的学习路径，"
            "不要机械拆句。请采用目标反推、项目式学习、示范-练习-迁移-提交的教学设计思路。\n"
            "输出要求：只输出 JSON 对象，不要 Markdown，不要解释。\n"
            "节点要求：5 到 10 个节点；每个节点必须有具体动作、产出物 deliverable、验收标准 success_criteria；"
            "最后一个节点必须是 submission。node_type 只能从 learning、video、reading、practice、submission、checkpoint 中选择。\n"
            "如果任务包含 GitHub、仓库、复现、部署、实验等场景，路径必须覆盖：确认仓库和验收标准、阅读 README、"
            "环境/依赖安装、数据或权重准备、最小 demo、实验/部署、故障记录、最终报告。\n"
            "联网资料约束：resources.url 只能使用 web_research 中出现的 URL 或教师原始输入中的 URL；"
            "没有证据时不要编造具体链接、库名、论文或课程。可以写“待教师补充链接”。\n"
            "语言：中文。"
        )
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]

    @classmethod
    def _extract_json_object(cls, text: str) -> Dict[str, Any]:
        cleaned = (text or "").strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.IGNORECASE).strip()
            cleaned = re.sub(r"```$", "", cleaned).strip()
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("No JSON object found")
        return json.loads(cleaned[start:end + 1])

    @classmethod
    def _normalize_llm_plan(
        cls,
        plan_obj: Dict[str, Any],
        fallback: Dict[str, Any],
        research: Dict[str, Any],
        model: Optional[str] = None,
        provider: Optional[str] = None,
    ) -> Dict[str, Any]:
        raw_stages = plan_obj.get("stages") if isinstance(plan_obj, dict) else None
        stages = cls._normalize_stages(raw_stages, fallback.get("stages", []))
        raw_nodes = plan_obj.get("nodes") if isinstance(plan_obj, dict) else None
        if not isinstance(raw_nodes, list):
            raise ValueError("nodes must be a list")

        allowed_urls = cls._allowed_resource_urls(research)
        research_urls = list(allowed_urls)
        nodes: List[Dict[str, Any]] = []
        resources: List[Dict[str, Any]] = []
        seen_resource_keys: Set[tuple] = set()

        for index, raw_node in enumerate(raw_nodes[:12]):
            if not isinstance(raw_node, dict):
                continue
            title = cls._clean_text(raw_node.get("title"), limit=80)
            if not title:
                continue
            node_type = cls._normalize_node_type(raw_node.get("node_type"), title, raw_node.get("description"))
            description = cls._clean_text(raw_node.get("description"), limit=700) or title
            stage_order = cls._clamp_int(
                raw_node.get("stage_order", (raw_node.get("config") or {}).get("stage_order", 0)),
                0,
                max(0, len(stages) - 1),
                0,
            )
            estimated_minutes = cls._clamp_int(raw_node.get("estimated_minutes"), 15, 240, 60)
            node_key = f"node_{len(nodes) + 1}"
            deliverable = cls._clean_text(
                raw_node.get("deliverable") or (raw_node.get("config") or {}).get("deliverable"),
                limit=220,
            )
            success_criteria = cls._clean_text(
                raw_node.get("success_criteria")
                or raw_node.get("completion_criteria")
                or (raw_node.get("config") or {}).get("success_criteria"),
                limit=260,
            )
            if not deliverable:
                deliverable = cls._default_deliverable(node_type)
            if not success_criteria:
                success_criteria = cls._default_success_criteria(node_type)

            node_resources = cls._normalize_resources(
                raw_node.get("resources") or [],
                allowed_urls=allowed_urls,
                node_key=node_key,
            )
            for resource in node_resources:
                key = (resource.get("resource_type"), resource.get("url"), resource.get("bv_id"))
                if key in seen_resource_keys:
                    continue
                seen_resource_keys.add(key)
                resources.append(resource)

            config = raw_node.get("config") if isinstance(raw_node.get("config"), dict) else {}
            config.update({
                "source": "llm_learning_path_planner",
                "planner_version": "llm_web_research_v1",
                "frameworks": cls.FRAMEWORKS,
                "stage_order": stage_order,
                "deliverable": deliverable,
                "success_criteria": success_criteria,
                "research_used": bool(research.get("items")),
                "research_urls": research_urls[:5],
                "llm_model": model,
                "llm_provider": provider,
            })
            nodes.append({
                "key": node_key,
                "title": title,
                "description": description,
                "node_type": node_type,
                "order_index": len(nodes),
                "estimated_minutes": estimated_minutes,
                "required": bool(raw_node.get("required", True)),
                "config": config,
                "resources": node_resources,
            })

        if len(nodes) < 4:
            raise ValueError("LLM plan contains too few usable nodes")

        if nodes[-1]["node_type"] != "submission":
            submission = cls._submission_node_from_fallback(fallback, len(nodes), len(stages), model, provider, research)
            if len(nodes) >= 12:
                nodes = nodes[:11]
            nodes.append(submission)

        nodes = nodes[:12]
        for index, node in enumerate(nodes):
            node["key"] = f"node_{index + 1}"
            node["order_index"] = index
            if node.get("resources"):
                for resource in node["resources"]:
                    resource.setdefault("metadata", {})
                    resource["metadata"]["node_key"] = node["key"]

        edges = [
            {"source_key": nodes[index]["key"], "target_key": nodes[index + 1]["key"]}
            for index in range(max(0, len(nodes) - 1))
        ]
        summary = cls._clean_text(plan_obj.get("summary"), limit=260)
        if not summary:
            total_minutes = sum(int(node.get("estimated_minutes") or 0) for node in nodes)
            summary = f"已由大模型生成 {len(nodes)} 个可验收节点，预估约 {total_minutes} 分钟。"
        if research.get("items"):
            summary = f"{summary} 已结合 {len(research.get('items') or [])} 条联网资料。"

        return {
            "stages": stages,
            "nodes": nodes,
            "edges": edges,
            "resources": resources,
            "summary": summary,
        }

    @classmethod
    def _normalize_stages(cls, raw_stages: Any, fallback_stages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        stages: List[Dict[str, Any]] = []
        if isinstance(raw_stages, list):
            for index, raw_stage in enumerate(raw_stages[:6]):
                if not isinstance(raw_stage, dict):
                    continue
                title = cls._clean_text(raw_stage.get("title"), limit=40)
                if not title:
                    continue
                stages.append({
                    "title": title,
                    "description": cls._clean_text(raw_stage.get("description"), limit=160),
                    "order_index": index,
                })
        if stages:
            return stages
        return [
            {
                "title": stage.get("title") or f"阶段 {index + 1}",
                "description": stage.get("description"),
                "order_index": index,
            }
            for index, stage in enumerate(fallback_stages[:4])
        ] or [{"title": "学习路径", "description": "大模型生成的学习路径", "order_index": 0}]

    @classmethod
    def _normalize_resources(
        cls,
        raw_resources: Any,
        allowed_urls: Set[str],
        node_key: str,
    ) -> List[Dict[str, Any]]:
        if not isinstance(raw_resources, list):
            return []
        resources: List[Dict[str, Any]] = []
        for raw in raw_resources[:5]:
            if isinstance(raw, str):
                raw = {"title": raw}
            if not isinstance(raw, dict):
                continue
            bv_id = cls._clean_text(raw.get("bv_id"), limit=40)
            url = cls._clean_text(raw.get("url"), limit=500)
            resource_type = cls._clean_text(raw.get("resource_type"), limit=40) or "text"
            if bv_id:
                resource_type = "bilibili"
                url = f"https://www.bilibili.com/video/{bv_id}"
            elif url and not cls._url_allowed(url, allowed_urls):
                continue
            elif url:
                resource_type = "link" if resource_type not in {"link", "bilibili", "file", "text"} else resource_type
            title = cls._clean_text(raw.get("title"), limit=80) or bv_id or url or "参考资料"
            resources.append({
                "resource_type": resource_type,
                "title": title,
                "url": url or None,
                "bv_id": bv_id or None,
                "file_id": raw.get("file_id"),
                "metadata": {"node_key": node_key, **(raw.get("metadata") or {})},
            })
        return resources

    @classmethod
    def _allowed_resource_urls(cls, research: Dict[str, Any]) -> Set[str]:
        urls: Set[str] = set()
        for url in research.get("input_urls") or []:
            if url:
                urls.add(cls._normalize_url(url))
        for item in research.get("items") or []:
            url = item.get("url")
            if url:
                urls.add(cls._normalize_url(url))
            metadata = item.get("metadata") or {}
            readme_url = metadata.get("readme_url")
            if readme_url:
                urls.add(cls._normalize_url(readme_url))
        return urls

    @classmethod
    def _url_allowed(cls, url: str, allowed_urls: Set[str]) -> bool:
        normalized = cls._normalize_url(url)
        if normalized in allowed_urls:
            return True
        if "bilibili.com/video/BV" in normalized:
            return True
        return any(normalized.startswith(allowed.rstrip("/") + "/") for allowed in allowed_urls)

    @staticmethod
    def _normalize_url(url: str) -> str:
        return (url or "").strip().rstrip("/")

    @classmethod
    def _submission_node_from_fallback(
        cls,
        fallback: Dict[str, Any],
        index: int,
        stage_count: int,
        model: Optional[str],
        provider: Optional[str],
        research: Dict[str, Any],
    ) -> Dict[str, Any]:
        raw = next(
            (node for node in reversed(fallback.get("nodes", [])) if node.get("node_type") == "submission"),
            None,
        ) or {}
        stage_order = max(0, stage_count - 1)
        config = raw.get("config") if isinstance(raw.get("config"), dict) else {}
        config.update({
            "source": "llm_learning_path_planner",
            "planner_version": "llm_web_research_v1",
            "frameworks": cls.FRAMEWORKS,
            "stage_order": stage_order,
            "deliverable": config.get("deliverable") or "学习报告、运行证据、问题记录与后续计划",
            "success_criteria": config.get("success_criteria") or "教师能根据提交物判断目标是否达成",
            "research_used": bool(research.get("items")),
            "llm_model": model,
            "llm_provider": provider,
            "structural_patch": "append_submission_node",
        })
        return {
            "key": f"node_{index + 1}",
            "title": raw.get("title") or "提交学习成果与复盘报告",
            "description": raw.get("description") or "提交本次学习路径的成果证据、关键问题、复盘结论和下一步计划。",
            "node_type": "submission",
            "order_index": index,
            "estimated_minutes": int(raw.get("estimated_minutes") or 50),
            "required": True,
            "config": config,
            "resources": [],
        }

    @classmethod
    def _fallback_plan(
        cls,
        fallback: Dict[str, Any],
        research: Dict[str, Any],
        exc: Exception,
    ) -> Dict[str, Any]:
        reason = re.sub(r"\s+", " ", str(exc)).strip()[:180] or exc.__class__.__name__
        plan = json.loads(json.dumps(fallback, ensure_ascii=False))
        plan["summary"] = f"LLM 规划失败，已返回规则草案；原因：{reason}"
        for node in plan.get("nodes", []):
            node.setdefault("config", {})
            node["config"]["source"] = "deterministic_fallback_after_llm_error"
            node["config"]["research_used"] = bool(research.get("items"))
        return plan

    @staticmethod
    def _clean_text(value: Any, limit: int) -> str:
        if value is None:
            return ""
        text = re.sub(r"\s+", " ", str(value)).strip()
        if len(text) <= limit:
            return text
        return text[:limit].rstrip() + "..."

    @classmethod
    def _normalize_node_type(cls, value: Any, title: str, description: Any) -> str:
        node_type = str(value or "").strip().lower()
        if node_type in cls.ALLOWED_NODE_TYPES:
            return node_type
        text = f"{title} {description or ''}".lower()
        if "bv" in text or "视频" in text or "b站" in text:
            return "video"
        if any(keyword in text for keyword in ["阅读", "readme", "文档", "资料", "论文"]):
            return "reading"
        if any(keyword in text for keyword in ["实验", "练习", "部署", "复现", "运行", "实现", "代码"]):
            return "practice"
        if any(keyword in text for keyword in ["提交", "报告", "总结", "附件"]):
            return "submission"
        if any(keyword in text for keyword in ["检查", "验收", "自测", "目标"]):
            return "checkpoint"
        return "learning"

    @staticmethod
    def _clamp_int(value: Any, min_value: int, max_value: int, default: int) -> int:
        try:
            number = int(value)
        except (TypeError, ValueError):
            number = default
        return min(max(number, min_value), max_value)

    @staticmethod
    def _default_deliverable(node_type: str) -> str:
        return {
            "video": "观看笔记和关键截图",
            "reading": "阅读笔记、术语表和问题清单",
            "practice": "可运行结果、代码或实验记录",
            "submission": "学习报告、附件和复盘问题",
            "checkpoint": "验收清单和自评结论",
            "learning": "概念图、笔记和疑问清单",
        }.get(node_type, "学习记录")

    @staticmethod
    def _default_success_criteria(node_type: str) -> str:
        return {
            "video": "能复述示范流程并指出要照做的关键步骤",
            "reading": "能找到关键入口、参数或概念，并记录疑问",
            "practice": "能得到可验证输出，并记录从失败到成功的过程",
            "submission": "提交物能证明目标达成，教师可以追踪过程",
            "checkpoint": "能判断是否具备进入下一阶段的条件",
            "learning": "能用自己的话解释关键概念",
        }.get(node_type, "能说明当前节点的完成证据")
