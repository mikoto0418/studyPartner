import asyncio
import json
import logging
import re
import time
from typing import Any, Awaitable, Callable, List, Optional

from app.core.llm import ChatMessage, llm_router

logger = logging.getLogger(__name__)

ALLOWED_TYPES = {"single", "multiple", "judge", "fill", "short", "essay"}

# 相邻两次调用的最小间隔。网关对同一把密钥按分钟限流：实测 5 次/50 秒稳定通过，
# 而 5 次/25 秒会被 429。所以既要减少调用次数（见 mechanical_chunk 的合并），
# 也要在每次调用前真正等够 —— 光靠重试救不回来，配额窗口没走完重试也是白等。
CHUNK_INTERVAL_SECONDS = 10.0

# 上次发起拆题调用的单调时钟，用来在进程内给调用节流。
_last_call_at: float = 0.0

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
      "score": 每题分值数字（原文明确标注了分值才填；原文没有就省略该字段或填 null，不要自己估一个）,
      "tags": ["可选标签"]
    }
  ]
}
3. type 取值只能是 single（单选）、multiple（多选）、judge（判断）、fill（填空）、short（简答/问答/编程/计算）、essay（论述）。
4. 数学公式一律输出为 LaTeX：行内公式用 \\(...\\)，独立公式用 \\[...\\]。
5. 图片一律用占位符 [[IMG:n]]（n 从 1 开始），不要臆造图片内容，图片位置保留占位符即可。
6. complete 表示：该输入块是否已包含"完整且未被拦腰截断"的题目。若最后一个题目疑似被截断，complete 填 false，且只把完整题目放进 questions；被截断的残题不要放进 questions。
7. 不要遗漏题干、选项和答案；主观题没有标准答案时 answer 填空字符串。
8. score 只在原文明确标注了分值时才填；原文没写就省略，绝对不要臆造一个分值。
9. 铁律：原文中出现几道题，就必须输出几道题。禁止漏题、禁止把多道题合并成一道、禁止只输出部分题目。即使某道题没有选项（如编程题、简答题、填空题），也必须完整输出。
"""


def mechanical_chunk(
    text: str,
    max_block_chars: int = 4000,
    min_block_chars: int = 1800,
) -> List[dict]:
    """第一层：机械粗切。按题号正则/空行边界把原文切成候选题目块，尽量不拦腰断题。

    切完之后把过小的相邻块合并：一份整卷常被切成几十个小块，而每一块都要单独
    调一次大模型。块越碎调用次数越多，越容易撞上网关的按分钟限流，拆题整体失败。
    合并只影响送进模型的粒度，题目边界仍由模型逐块判定。
    """
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
    return _merge_small_blocks(blocks, min_block_chars)


def _merge_small_blocks(blocks: List[dict], min_block_chars: int) -> List[dict]:
    """把小于 min_block_chars 的块并入前一块，减少送模型的次数。"""
    if not blocks:
        return []
    merged: List[dict] = []
    for block in blocks:
        if merged and len(block["text"]) < min_block_chars:
            prev = merged[-1]
            prev["text"] = f"{prev['text']}\n{block['text']}"
            prev["line_end"] = block["line_end"]
            continue
        merged.append(dict(block))
    return merged


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


_OPTION_PREFIX_RE = re.compile(r"^\s*[（(]?([A-Za-z])[）).、．:：]\s*")


def normalize_options(raw: Any) -> Optional[List[dict]]:
    """把 LLM 返回的任意 options 形状收敛成 [{"key": "A", "text": "..."}]。

    落库前必须收敛：读侧的 schema 是 List[dict]，形状不对会让教师校对页和
    学生答题页在序列化时直接 500。LLM 常见几种形状都要兼容：
    - [{"key": "A", "text": "甲"}]   标准
    - ["A. 甲", "B. 乙"]             带前缀的字符串数组
    - ["甲", "乙"]                   纯文本数组，按顺序补 A/B/C
    - {"A": "甲", "B": "乙"}         字典
    """
    if raw is None:
        return None
    if isinstance(raw, dict):
        raw = list(raw.items())
        items = [{"key": str(k), "text": v} for k, v in raw]
    elif isinstance(raw, (list, tuple)):
        items = list(raw)
    else:
        return []

    out: List[dict] = []
    for index, item in enumerate(items):
        fallback_key = chr(ord("A") + index) if index < 26 else str(index + 1)
        if isinstance(item, dict):
            key = str(item.get("key") or fallback_key).strip() or fallback_key
            text = item.get("text")
            if text is None:
                text = item.get("value") or item.get("content") or ""
            merged = dict(item)
            merged["key"] = key
            merged["text"] = str(text)
            out.append(merged)
            continue
        text = str(item)
        match = _OPTION_PREFIX_RE.match(text)
        if match:
            out.append({"key": match.group(1).upper(), "text": text[match.end():].strip()})
        else:
            out.append({"key": fallback_key, "text": text})
    return out


def _coerce_question(raw: dict, fallback_index: int) -> dict:
    qtype = str(raw.get("type") or "").strip()
    qtype = TYPE_ALIASES.get(qtype, qtype if qtype in ALLOWED_TYPES else "short")
    options = normalize_options(raw.get("options"))
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
        # 原文没标分值时为 None，交给教师在校对页填写；不要用 0 冒充
        "score": _to_float(raw.get("score"), None),
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


async def _throttle() -> None:
    """保证相邻两次拆题调用之间有足够间隔。

    节流放在真正发起调用的地方，而不是循环体里 —— 一个分块可能因为「被截断」
    而触发第二次调用，那条路径同样要占用网关配额。
    """
    global _last_call_at
    now = time.monotonic()
    wait = CHUNK_INTERVAL_SECONDS - (now - _last_call_at)
    if wait > 0:
        await asyncio.sleep(wait)
    _last_call_at = time.monotonic()


async def _extract_one_chunk(chunk_index: int, chunk_text: str) -> dict:
    await _throttle()
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
    data = normalize_ai_json(response.content)
    if not data and (response.content or "").strip():
        # 模型返回了内容但不是合法 JSON —— 最常见的原因是输出被 max_tokens 截断。
        # 这一块里的题目会整块丢失，若不记日志，教师只会看到「题目少了一截」而无从排查。
        logger.warning(
            "Chunk %d: LLM output is not valid JSON (len=%d), head=%r",
            chunk_index,
            len(response.content),
            response.content[:200],
        )
    return data


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
        data = await _extract_one_chunk(i, chunk_text)
        complete = bool(data.get("complete", True))
        qs = data.get("questions") or []

        # 第二层修正：若 AI 判定块被拦腰截断，合并相邻块重解一次（最多一次）。
        if not complete and i + 1 < len(chunks):
            merged_text = chunk_text + "\n" + chunks[i + 1]["text"]
            merged = await _extract_one_chunk(i, merged_text)
            if bool(merged.get("complete", True)):
                qs = merged.get("questions") or []
                i += 2
                done += 2
            else:
                i += 1
                done += 1
        else:
            if not complete:
                logger.warning(
                    "Chunk %d reported incomplete but is the last chunk; its tail is dropped",
                    i,
                )
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
        q["score"] = _to_float(q.get("score"), None)

    return questions