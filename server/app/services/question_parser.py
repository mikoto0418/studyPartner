import json
import logging
import re
from typing import Any, Awaitable, Callable, List, Optional

from app.core.llm import ChatMessage, llm_router

logger = logging.getLogger(__name__)

ALLOWED_TYPES = {"single", "multiple", "judge", "fill", "short", "essay"}

TYPE_ALIASES = {
    "single_choice": "single",
    "单选": "single",
    "单选题": "single",
    "multiple_choice": "multiple",
    "多选": "multiple",
    "多选题": "multiple",
    "judge": "judge",
    "判断": "judge",
    "判断题": "judge",
    "fill": "fill",
    "填空": "fill",
    "填空题": "fill",
    "short": "short",
    "简答": "short",
    "简答题": "short",
    "问答": "short",
    "问答题": "short",
    "essay": "essay",
    "论述": "essay",
    "论述题": "essay",
}

QUESTION_START_RE = re.compile(
    r"^\s*(\d{1,3})\s*[.、．)）]\s*"
    r"|^\s*第\s*[一二三四五六七八九十百\d]+\s*题\s*"
    r"|^\s*(?:选择题|单选题|多项选择题|多选题|判断题|填空题|简答题|问答题|论述题|计算题)\b"
)

SYSTEM_PROMPT = """你是一名专业的教育题目结构化提取助手。请把输入文本中的题目逐题提取为严格 JSON。

要求：
1. 只输出一个 JSON 对象，不要输出任何解释、思考过程、推理内容、Markdown 代码块标记或多余文字。
2. JSON 结构必须是：
{
  "complete": true或false,
  "questions": [
    {
      "type": "single|multiple|judge|fill|short|essay",
      "stem": "题干文本",
      "options": [{"key": "A", "text": "选项内容"}],
      "answer": "答案（选择题填正确选项字母或数字，判断题填 true/false 或 对/错，主观题填参考答案或空字符串）",
      "analysis": "答案解析",
      "score": 每题分值数字,
      "tags": ["可选标签"]
    }
  ]
}
3. type 取值只能是 single（单选）、multiple（多选）、judge（判断）、fill（填空）、short（简答/问答/编程/计算）、essay（论述）。
4. 数学公式一律输出为 LaTeX：行内公式用 \\(...\\)，独立公式用 \\[...\\]。
5. 图片一律用占位符 [[IMG:n]]（n 从 1 开始），不要臆造图片内容，图片位置保留占位符即可。
6. complete 表示：该输入块是否已包含"完整且未被拦腰截断"的题目。若最后一个题目疑似被截断，complete 填 false，且只把完整题目放进 questions；被截断的残题不要放进 questions。
7. 不要遗漏题干、选项和答案；主观题没有标准答案时 answer 填空字符串。
8. 铁律：原文中出现几道题，就必须输出几道题。禁止漏题、禁止把多道题合并成一道、禁止只输出部分题目。即使某道题没有选项（如编程题、简答题、填空题），也必须完整输出。
"""


def mechanical_chunk(text: str, max_block_chars: int = 2000) -> List[dict]:
    """第一层：机械粗切。按题号正则/空行边界把原文切成候选题目块，尽量不拦腰断题。"""
    if not text or not text.strip():
        return []

    lines = text.split("\n")
    blocks: List[dict] = []
    start = 0
    i = 0
    total = len(lines)

    while i < total:
        line = lines[i]
        is_question_start = bool(QUESTION_START_RE.match(line))
        cur_size = sum(len(l) for l in lines[start:i + 1])

        if is_question_start and i > start:
            _append_block(blocks, lines, start, i)
            start = i
        elif cur_size > max_block_chars and not is_question_start:
            _append_block(blocks, lines, start, i + 1)
            start = i + 1

        i += 1

    _append_block(blocks, lines, start, total)
    return blocks


def _append_block(blocks: List[dict], lines: List[str], start: int, end: int) -> None:
    if start >= end:
        return
    text = "\n".join(lines[start:end]).strip()
    if text:
        blocks.append({"line_start": start, "line_end": end - 1, "text": text})


def normalize_ai_json(content: str) -> dict:
    """容错地把 LLM 输出解析为 JSON 对象。"""
    if not content:
        return {}
    text = content.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return {}
    try:
        data = json.loads(text[start:end + 1])
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def _coerce_question(raw: dict, fallback_index: int) -> dict:
    qtype = str(raw.get("type") or "").strip()
    qtype = TYPE_ALIASES.get(qtype, qtype if qtype in ALLOWED_TYPES else "short")
    options = raw.get("options")
    answer = raw.get("answer")
    if options is None and qtype in {"single", "multiple", "judge"}:
        options = []
    return {
        "question_type": qtype,
        "stem": str(raw.get("stem") or "").strip(),
        "stem_images": raw.get("stem_images") or [],
        "options": options,
        "answer": answer,
        "analysis": str(raw.get("analysis") or "").strip() or None,
        "score": _to_float(raw.get("score"), 0.0),
        "difficulty": _to_float(raw.get("difficulty"), None),
        "tags": raw.get("tags") or [],
        "order_index": fallback_index,
    }


def _to_float(value: Any, default: Optional[float]) -> Optional[float]:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


async def _extract_one_chunk(chunk_text: str) -> dict:
    messages = [
        ChatMessage(role="system", content=SYSTEM_PROMPT),
        ChatMessage(role="user", content=chunk_text),
    ]
    response = await llm_router.route(
        task_type="question_parsing",
        messages=messages,
        require_task_config=True,
        temperature=0.2,
        max_tokens=8192,
        timeout_seconds=180,
    )
    return normalize_ai_json(response.content)


async def parse_text_to_questions(
    raw_text: str,
    on_progress: Optional[Callable[[str, int], Awaitable[None]]] = None,
) -> List[dict]:
    """三层拆题编排：机械粗切 -> AI 完整性校验与修正 -> AI 结构化提取。"""
    chunks = mechanical_chunk(raw_text)
    if not chunks:
        return []

    if on_progress:
        await on_progress("mechanical", len(chunks))

    questions: List[dict] = []
    i = 0
    done = 0
    while i < len(chunks):
        chunk_text = chunks[i]["text"]
        data = await _extract_one_chunk(chunk_text)
        complete = bool(data.get("complete", True))
        qs = data.get("questions") or []

        # 第二层修正：若 AI 判定块被拦腰截断，合并相邻块重解一次（最多一次）。
        if not complete and i + 1 < len(chunks):
            merged_text = chunk_text + "\n" + chunks[i + 1]["text"]
            merged = await _extract_one_chunk(merged_text)
            if bool(merged.get("complete", True)):
                qs = merged.get("questions") or []
                i += 2
                done += 2
            else:
                i += 1
                done += 1
        else:
            i += 1
            done += 1

        for raw in qs:
            normalized = _coerce_question(raw, len(questions))
            if normalized["stem"]:
                questions.append(normalized)

        if on_progress:
            await on_progress("chunk", done)

    for idx, q in enumerate(questions):
        q["order_index"] = idx
        q["score"] = _to_float(q.get("score"), 0.0) or 0.0

    return questions