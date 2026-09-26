import asyncio
import json
import logging
import re
import time
from typing import Any, Awaitable, Callable, List, Optional

from app.core.llm import ChatMessage, llm_router

logger = logging.getLogger(__name__)

ALLOWED_TYPES = {"single", "multiple", "judge", "fill", "short", "essay", "code"}
CODE_LANGUAGES = {"python", "javascript", "java"}
CODE_LANGUAGE_ALIASES = {
    "py": "python", "python3": "python", "python2": "python",
    "js": "javascript", "node": "javascript", "nodejs": "javascript", "ts": "javascript",
    "typescript": "javascript", "java8": "java", "java11": "java", "java17": "java",
}

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
    "code": "code",
    "coding": "code",
    "program": "code",
    "programming": "code",
    "编程": "code",
    "编程题": "code",
    "代码": "code",
    "代码题": "code",
    "算法题": "code",
}

QUESTION_START_RE = re.compile(
    r"^\s*(\d{1,3})\s*[.、．)）]\s*"
    r"|^\s*第\s*[一二三四五六七八九十百\d]+\s*题\s*"
    r"|^\s*(?:选择题|单选题|多项选择题|多选题|判断题|填空题|简答题|问答题|论述题|计算题|编程题|代码题)\b"
)

SYSTEM_PROMPT = """你是一名专业的教育题目结构化提取助手。请把输入文本中的题目逐题提取为严格 JSON。

要求：
1. 只输出一个 JSON 对象，不要输出任何解释、思考过程、推理内容、Markdown 代码块标记或多余文字。
2. JSON 结构必须是：
{
  "complete": true或false,
  "questions": [
    {
      "type": "single|multiple|judge|fill|short|essay|code",
      "stem": "题干文本",
      "options": [{"key": "A", "text": "选项内容"}],
      "answer": "答案（选择题填正确选项字母或数字，判断题填 true/false 或 对/错，主观题填参考答案或空字符串，编程题填可AC的标准代码）",
      "analysis": "答案解析",
      "language": "编程题的语言：python|javascript|java（非编程题省略）",
      "test_cases": [{"input": "标准输入", "expected_output": "期望输出", "is_sample": true}],
      "starter_code": "给学生预填的代码骨架（可选）",
      "score": 每题分值数字（原文明确标注了分值才填；原文没有就省略该字段或填 null，不要自己估一个）,
      "tags": ["可选标签"]
    }
  ]
}
3. type 取值只能是 single（单选）、multiple（多选）、judge（判断）、fill（填空）、short（简答/问答/计算）、essay（论述）、code（编程/算法/代码题）。
   凡是要求「写代码 / 写程序 / 实现函数 / 补全算法」的题一律用 code，不要用 short 或 essay。
   code 题必须额外给出 language 与 test_cases：
   - language 只能是 python、javascript、java 之一。原文指定了其他语言（C/C++/Go/Rust）时，
     也要落到这三个里最接近的，并在 analysis 里注明原语言。
   - test_cases 是 [{"input": "标准输入", "expected_output": "期望的标准输出", "is_sample": true/false}]，
     至少给 2 条；其中 is_sample=true 的会展示给学生，最多 2 条是样例。
     原文没给样例输入输出时，按题意自己构造能验证解题正确性的用例。
   - answer 填一份可AC的标准代码。starter_code 填给学生预填的代码骨架（没有就省略）。
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
    language = None
    test_cases = None
    starter_code = None
    if qtype == "code":
        language = normalize_code_language(raw.get("language"))
        test_cases = normalize_test_cases(raw.get("test_cases"))
        raw_starter = raw.get("starter_code")
        starter_code = str(raw_starter).strip() if raw_starter else None
    return {
        "question_type": qtype,
        "stem": str(raw.get("stem") or "").strip(),
        "stem_images": raw.get("stem_images") or [],
        "options": options,
        "answer": answer,
        "analysis": str(raw.get("analysis") or "").strip() or None,
        "language": language,
        "test_cases": test_cases,
        "starter_code": starter_code,
        # 原文没标分值时为 None，交给教师在校对页填写；不要用 0 冒充
        "score": _to_float(raw.get("score"), None),
        "difficulty": _to_float(raw.get("difficulty"), None),
        "tags": raw.get("tags") or [],
        "order_index": fallback_index,
    }


def normalize_code_language(raw: Any) -> str:
    """把模型给出的语言名收敛到沙箱真正支持的三选一，默认 python。"""
    key = str(raw or "").strip().lower()
    if key in CODE_LANGUAGES:
        return key
    return CODE_LANGUAGE_ALIASES.get(key, "python")


def normalize_test_cases(raw: Any) -> List[dict]:
    """收敛测试用例形状。

    模型可能给成 {"1": "2"}、[["1","2"]] 或 [{"input":..,"output":..}]。
    落库前必须统一成 [{input, expected_output, is_sample}]：
    读侧按这个形状渲染，形状不对会在教师校对页或学生答题页直接 500。
    """
    if not isinstance(raw, (list, tuple)):
        return []
    out: List[dict] = []
    for index, item in enumerate(raw):
        text_in: Any = None
        expected: Any = None
        sample: Optional[bool] = None
        if isinstance(item, dict):
            text_in = item.get("input")
            if text_in is None:
                text_in = item.get("stdin")
            expected = item.get("expected_output")
            if expected is None:
                expected = item.get("output")
            if expected is None:
                expected = item.get("expected")
            if "is_sample" in item:
                sample = bool(item.get("is_sample"))
            elif "sample" in item:
                sample = bool(item.get("sample"))
            if text_in is None and expected is None:
                # {"1": "2"} 这种把输入当键的写法
                pairs = [(k, v) for k, v in item.items() if k not in ("is_sample", "sample")]
                if len(pairs) == 1:
                    text_in, expected = pairs[0]
                else:
                    continue
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            text_in, expected = item[0], item[1]
        else:
            continue
        out.append(
            {
                "input": "" if text_in is None else str(text_in),
                "expected_output": "" if expected is None else str(expected),
                "is_sample": sample if sample is not None else index < 2,
            }
        )
    # 模型没标任何样例时，把前两条当样例展示，保证学生至少看到一组输入输出
    if out and not any(case["is_sample"] for case in out):
        for case in out[:2]:
            case["is_sample"] = True
    return out


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