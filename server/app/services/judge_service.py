"""编程题判题：在 go-judge 沙箱里编译运行学生代码，再逐用例比对输出。

设计约束：
- 判题结果只信沙箱返回的 stdout 与退出码，不在本进程里 eval 任何学生代码。
- 沙箱不可用（未起服务、鉴权失败）时必须显式报错，不能把「没跑成」当成「答对」或「答错」，
  否则一次基础设施故障就会把全班编程题判成 0 分。
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from urllib import request as urlrequest

from app.config import settings

logger = logging.getLogger(__name__)

# 只放行这三种：沙箱镜像里确实装了对应工具链。
# 其余语言（c/cpp/go/rust）在 v1.12.2-languages 镜像里没有编译器，放进来只会让教师
# 建出永远判不了的题。
LANGUAGE_SPECS: Dict[str, Dict[str, Any]] = {
    "python": {
        "label": "Python 3",
        "source_name": "main.py",
        # 解释型语言没有编译步骤，但语法错误必须与运行期错误区分开：
        # 学生看到「语法错误」和「某个用例挂了」的下一步动作完全不同。
        "check_args": ["/usr/bin/python3", "-m", "py_compile", "main.py"],
        "run_args": ["/usr/bin/python3", "main.py"],
        "binary": False,
    },
    "javascript": {
        "label": "JavaScript (Node)",
        "source_name": "main.js",
        "check_args": ["/usr/bin/node", "--check", "main.js"],
        "run_args": ["/usr/bin/node", "main.js"],
        "binary": False,
    },
    "java": {
        "label": "Java 17",
        "source_name": "Main.java",
        # 必须指定 UTF-8：镜像默认编码不是 UTF-8，中文注释/字符串会编译失败
        "compile_args": ["/usr/bin/javac", "-encoding", "UTF-8", "Main.java"],
        "run_args": ["/usr/bin/java", "-cp", ".", "Main"],
        "binary": True,
    },
}
# Java 的 class 文件会多个产出，按后缀收
CACHE_OUT_EXTRA = {"java": ["Main.class"]}

SOURCE_CODE_MAX = 100_000  # 单份代码上限，避免把超大文件塞进沙箱


class JudgeUnavailable(RuntimeError):
    """沙箱本身不可用（未启动、鉴权失败、网络错误）。"""


@dataclass
class CaseResult:
    index: int
    passed: bool
    status: str
    input_text: str = ""
    expected: str = ""
    actual: str = ""
    stderr: str = ""
    time_ms: Optional[int] = None
    is_sample: bool = False


@dataclass
class JudgeResult:
    ok: bool
    status: str  # accepted / wrong_answer / compile_error / runtime_error / time_limit / judge_error
    message: str = ""
    passed: int = 0
    total: int = 0
    compile_output: str = ""
    cases: List[CaseResult] = field(default_factory=list)


def language_spec(language: str) -> Dict[str, Any]:
    spec = LANGUAGE_SPECS.get(str(language or "").strip().lower())
    if not spec:
        raise ValueError(f"不支持的编程语言：{language}")
    return spec


def _post(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    headers = {"Content-Type": "application/json"}
    if settings.JUDGE_AUTH_TOKEN:
        headers["Authorization"] = f"Bearer {settings.JUDGE_AUTH_TOKEN}"
    req = urlrequest.Request(
        f"{settings.JUDGE_BASE_URL.rstrip('/')}/run",
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urlrequest.urlopen(req, timeout=settings.JUDGE_TIMEOUT_SECONDS) as resp:
            body = resp.read().decode("utf-8", "replace")
    except Exception as exc:  # URLError / HTTPError / timeout
        raise JudgeUnavailable(f"判题服务不可用：{exc}") from exc
    try:
        data = json.loads(body)
    except json.JSONDecodeError as exc:
        raise JudgeUnavailable("判题服务返回了非 JSON 响应") from exc
    if not isinstance(data, list):
        raise JudgeUnavailable("判题服务返回格式异常")
    return data


def _output_files() -> List[Dict[str, Any]]:
    limit = settings.JUDGE_OUTPUT_LIMIT_BYTES
    return [
        {"content": ""},  # 位置 0 预留给 stdin
        {"name": "stdout", "max": limit},
        {"name": "stderr", "max": limit},
    ]


def _normalize(text: str) -> str:
    """逐行比较时忽略行尾空白与末尾空行 —— 判题只看内容对不对，不纠缠格式。"""
    lines = [line.rstrip() for line in (text or "").replace("\r\n", "\n").split("\n")]
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)


def compile_source(language: str, source: str) -> Tuple[Optional[str], str]:
    """返回 (编译产物 fileId, 错误信息)。

    解释型语言跑一次语法检查，把语法错误和运行错误分开；Java 真正编译并缓存 class。
    """
    spec = language_spec(language)
    if len(source) > SOURCE_CODE_MAX:
        return None, "代码过长"
    args = spec.get("compile_args") or spec.get("check_args")
    if not args:
        return None, ""
    result = _post(
        {
            "cmd": [
                {
                    "args": args,
                    "env": ["PATH=/usr/bin:/bin", "HOME=/tmp"],
                    "files": _output_files(),
                    "copyIn": {spec["source_name"]: {"content": source}},
                    "copyOutCached": CACHE_OUT_EXTRA.get(language, []),
                    "cpuLimit": settings.JUDGE_COMPILE_CPU_LIMIT_NS,
                    "memoryLimit": settings.JUDGE_COMPILE_MEMORY_LIMIT_BYTES,
                    "procLimit": settings.JUDGE_PROC_LIMIT,
                }
            ]
        }
    )
    first = result[0] if result else {}
    files = first.get("files") or {}
    stderr = files.get("stderr") or ""
    stdout = files.get("stdout") or ""
    if first.get("exitStatus") != 0:
        return None, (stderr or stdout or "编译失败").strip()[:4000]
    if not spec["binary"]:
        return None, ""
    file_ids = first.get("fileIds") or {}
    # Java 只需 Main.class；其余语言不会走到这里
    for name in CACHE_OUT_EXTRA.get(language, []):
        if name in file_ids:
            return file_ids[name], ""
    return None, "编译产物缺失，判题服务可能未正确返回缓存文件"


def run_case(
    language: str,
    source: str,
    stdin_text: str,
    compiled_id: Optional[str] = None,
) -> Dict[str, Any]:
    """在沙箱里跑一次输入，返回 stdout/stderr/退出码/状态。"""
    spec = language_spec(language)
    if len(source) > SOURCE_CODE_MAX:
        return {"status": "compile_error", "stdout": "", "stderr": "代码过长", "exitStatus": 1}

    files = _output_files()
    files[0] = {"content": stdin_text or ""}
    copy_in: Dict[str, Any] = {}
    if spec["binary"]:
        copy_in["Main.class"] = {"fileId": compiled_id}
    else:
        copy_in[spec["source_name"]] = {"content": source}

    result = _post(
        {
            "cmd": [
                {
                    "args": spec["run_args"],
                    "env": ["PATH=/usr/bin:/bin", "HOME=/tmp"],
                    "files": files,
                    "copyIn": copy_in,
                    "copyOut": ["stdout", "stderr"],
                    "cpuLimit": settings.JUDGE_CPU_LIMIT_NS,
                    "memoryLimit": settings.JUDGE_MEMORY_LIMIT_BYTES,
                    "procLimit": settings.JUDGE_PROC_LIMIT,
                }
            ]
        }
    )
    first = result[0] if result else {}
    out_files = first.get("files") or {}
    return {
        "status": first.get("status") or "",
        "exitStatus": first.get("exitStatus"),
        "stdout": out_files.get("stdout") or "",
        "stderr": out_files.get("stderr") or "",
        "time_ms": int((first.get("time") or 0) / 1_000_000),
    }


def _status_of(raw: Dict[str, Any]) -> str:
    status = str(raw.get("status") or "").lower()
    if "time limit" in status or "timeout" in status:
        return "time_limit"
    if "non zero" in status or "nonzero" in status or (raw.get("exitStatus") or 0) != 0:
        return "runtime_error"
    if "memory limit" in status:
        return "runtime_error"
    return "ok"


def judge_code(
    language: str,
    source: str,
    test_cases: List[Dict[str, Any]],
    *,
    include_hidden: bool = True,
) -> JudgeResult:
    """跑全部（或仅样例）用例，返回逐用例结果与汇总。"""
    try:
        spec = language_spec(language)
    except ValueError as exc:
        return JudgeResult(ok=False, status="judge_error", message=str(exc))

    cases: List[CaseResult] = []
    visible = [
        (i, tc)
        for i, tc in enumerate(test_cases)
        if include_hidden or tc.get("is_sample")
    ]
    if not visible:
        return JudgeResult(
            ok=False,
            status="judge_error",
            message="这道题还没有测试用例，无法自动判分",
        )

    try:
        compiled_id, compile_error = compile_source(language, source)
    except JudgeUnavailable as exc:
        return JudgeResult(ok=False, status="judge_error", message=str(exc))
    if compile_error:
        return JudgeResult(
            ok=False,
            status="compile_error",
            message="编译未通过",
            compile_output=compile_error,
            total=len(visible),
        )
    if spec["binary"] and not compiled_id:
        return JudgeResult(
            ok=False, status="compile_error", message="编译产物缺失", total=len(visible)
        )

    passed = 0
    overall = "accepted"
    for index, tc in visible:
        expected = tc.get("expected_output") or ""
        try:
            raw = run_case(language, source, tc.get("input") or "", compiled_id)
        except JudgeUnavailable as exc:
            return JudgeResult(ok=False, status="judge_error", message=str(exc))
        state = _status_of(raw)
        actual = raw.get("stdout") or ""
        ok = state == "ok" and _normalize(actual) == _normalize(expected)
        if ok:
            passed += 1
        elif state == "time_limit":
            overall = "time_limit" if overall == "accepted" else overall
        elif state == "runtime_error":
            overall = "runtime_error" if overall == "accepted" else overall
        elif overall == "accepted":
            overall = "wrong_answer"
        cases.append(
            CaseResult(
                index=index,
                passed=ok,
                status=state if ok or state != "ok" else "wrong_answer",
                input_text=tc.get("input") or "",
                expected=expected,
                actual=actual[:4000],
                stderr=(raw.get("stderr") or "")[:2000],
                time_ms=raw.get("time_ms"),
                is_sample=bool(tc.get("is_sample")),
            )
        )

    if passed == len(visible):
        overall = "accepted"
    return JudgeResult(
        ok=overall == "accepted",
        status=overall,
        message="全部用例通过" if overall == "accepted" else "存在未通过的用例",
        passed=passed,
        total=len(visible),
        cases=cases,
    )
