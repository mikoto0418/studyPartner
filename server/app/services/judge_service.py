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

# 与 deploy/judge/Dockerfile 中安装的工具链对应。JavaScript 保留以兼容旧卷。
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
        "compile_args": ["/bin/sh", "-c", "javac -J-Xmx256m -encoding UTF-8 Main.java && jar cf program.jar *.class"],
        "run_args": ["/usr/bin/java", "-Xms16m", "-Xmx128m", "-XX:ReservedCodeCacheSize=32m", "-XX:+UseSerialGC", "-cp", "program.jar", "Main"],
        "artifact": "program.jar",
        "binary": True,
    },
    "c": {
        "label": "C17", "source_name": "main.c",
        "compile_args": ["/usr/bin/gcc", "-std=c17", "-O2", "main.c", "-o", "main", "-lm"],
        "run_args": ["/w/main"], "artifact": "main", "binary": True,
    },
    "cpp": {
        "label": "C++17", "source_name": "main.cpp",
        "compile_args": ["/usr/bin/g++", "-std=c++17", "-O2", "main.cpp", "-o", "main"],
        "run_args": ["/w/main"], "artifact": "main", "binary": True,
    },
}
CACHE_OUT_EXTRA = {key: [spec["artifact"] + "?"] for key, spec in LANGUAGE_SPECS.items() if spec["binary"]}

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


def release_compiled(file_id: Optional[str]) -> None:
    if not file_id:
        return
    headers = {"Authorization": f"Bearer {settings.JUDGE_AUTH_TOKEN}"} if settings.JUDGE_AUTH_TOKEN else {}
    req = urlrequest.Request(f"{settings.JUDGE_BASE_URL.rstrip('/')}/file/{file_id}", headers=headers, method="DELETE")
    try:
        with urlrequest.urlopen(req, timeout=5):
            pass
    except Exception:
        # 文件服务也有 TTL；清理故障不能覆盖已经得到的判题结果。
        logger.warning("Could not release judge cache %s", file_id)


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
                    "env": ["PATH=/usr/bin:/bin", "HOME=/tmp", "LANG=C.UTF-8"],
                    "files": _output_files(),
                    "copyIn": {spec["source_name"]: {"content": source}},
                    "copyOutCached": CACHE_OUT_EXTRA.get(language, []),
                    "copyOut": ["stdout", "stderr"],
                    "cpuLimit": settings.JUDGE_COMPILE_CPU_LIMIT_NS,
                    "clockLimit": settings.JUDGE_COMPILE_CPU_LIMIT_NS * 2,
                    "memoryLimit": settings.JUDGE_COMPILE_MEMORY_LIMIT_BYTES,
                    "procLimit": settings.JUDGE_PROC_LIMIT,
                }
            ]
        }
    )
    first = result[0] if result else {}
    if not first or first.get("status") in {"Internal Error", "File Error"}:
        raise JudgeUnavailable(first.get("error") or "编译环境未就绪")
    files = first.get("files") or {}
    stderr = files.get("stderr") or ""
    stdout = files.get("stdout") or ""
    if first.get("exitStatus") != 0 or first.get("status") != "Accepted":
        return None, (stderr or stdout or "编译失败").strip()[:4000]
    if not spec["binary"]:
        return None, ""
    file_ids = first.get("fileIds") or {}
    artifact = spec["artifact"]
    if artifact in file_ids:
        return file_ids[artifact], ""
    raise JudgeUnavailable("编译产物缺失")


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
        copy_in[spec["artifact"]] = {"fileId": compiled_id}
    else:
        copy_in[spec["source_name"]] = {"content": source}

    result = _post(
        {
            "cmd": [
                {
                    "args": spec["run_args"],
                    "env": ["PATH=/usr/bin:/bin", "HOME=/tmp", "LANG=C.UTF-8"],
                    "files": files,
                    "copyIn": copy_in,
                    "copyOut": ["stdout", "stderr"],
                    "cpuLimit": settings.JUDGE_CPU_LIMIT_NS,
                    "clockLimit": settings.JUDGE_CPU_LIMIT_NS * 3,
                    "memoryLimit": settings.JUDGE_MEMORY_LIMIT_BYTES,
                    "procLimit": settings.JUDGE_PROC_LIMIT,
                }
            ]
        }
    )
    first = result[0] if result else {}
    if not first or first.get("status") in {"Internal Error", "File Error"}:
        raise JudgeUnavailable(first.get("error") or "运行环境未就绪")
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
    if status in {"memory limit exceeded", "output limit exceeded", "signalled", "dangerous syscall"}:
        return "runtime_error"
    if status == "accepted" and raw.get("exitStatus") == 0:
        return "ok"
    raise JudgeUnavailable(f"未知判题状态：{status or '空'}")


def judge_code(
    language: str,
    source: str,
    test_cases: List[Dict[str, Any]],
) -> JudgeResult:
    """跑全部用例，返回逐用例结果与汇总。

    用例是教师侧的信息，只在这里被读取；任何面向学生的接口都不该带出内容。
    """
    try:
        spec = language_spec(language)
    except ValueError as exc:
        return JudgeResult(ok=False, status="judge_error", message=str(exc))

    cases: List[CaseResult] = []
    visible = list(enumerate(test_cases))
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
    try:
        for index, tc in visible:
            expected = tc.get("expected_output") or ""
            raw = run_case(language, source, tc.get("input") or "", compiled_id)
            state = _status_of(raw)
            actual = raw.get("stdout") or ""
            ok = state == "ok" and _normalize(actual) == _normalize(expected)
            if ok:
                passed += 1
            elif state in {"time_limit", "runtime_error"}:
                overall = state
            elif overall == "accepted":
                overall = "wrong_answer"
            cases.append(
                CaseResult(
                    index=index, passed=ok,
                    status=state if ok or state != "ok" else "wrong_answer",
                    input_text=tc.get("input") or "", expected=expected,
                    actual=actual[:4000], stderr=(raw.get("stderr") or "")[:2000],
                    time_ms=raw.get("time_ms"),
                )
            )
            if state in {"time_limit", "runtime_error"}:
                break
    except JudgeUnavailable as exc:
        return JudgeResult(ok=False, status="judge_error", message=str(exc))
    finally:
        release_compiled(compiled_id)

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


@dataclass
class DryRunCase:
    """自测的一次运行结果。没有期望输出，passed 恒为 None。"""

    index: int
    passed: Optional[bool]
    status: str
    input_text: str = ""
    actual: str = ""
    stderr: str = ""
    time_ms: Optional[int] = None


@dataclass
class DryRunResult:
    status: str  # ok / wrong_answer / compile_error / runtime_error / time_limit / judge_error
    message: str = ""
    compile_output: str = ""
    cases: List[DryRunCase] = field(default_factory=list)


def dry_run(
    language: str,
    source: str,
    stdin_text: Optional[str] = None,
) -> DryRunResult:
    """学生自测：在沙箱里跑一次，把标准输出给回去。

    只提供一个裸的运行环境，不比对任何期望输出，也绝不接触用例数据 ——
    判题用例是教师侧的信息，学生能读到就等于拿到了答案。

    空输入也是合法输入：很多题不需要读入，直接跑就行。
    """
    try:
        spec = language_spec(language)
    except ValueError as exc:
        return DryRunResult(status="judge_error", message=str(exc))

    try:
        compiled_id, compile_error = compile_source(language, source)
    except JudgeUnavailable as exc:
        return DryRunResult(status="judge_error", message=str(exc))
    if compile_error:
        return DryRunResult(
            status="compile_error", message="编译未通过", compile_output=compile_error
        )
    if spec["binary"] and not compiled_id:
        return DryRunResult(status="compile_error", message="编译产物缺失")

    try:
        raw = run_case(language, source, stdin_text or "", compiled_id)
        state = _status_of(raw)
    except JudgeUnavailable as exc:
        return DryRunResult(status="judge_error", message=str(exc))
    finally:
        release_compiled(compiled_id)

    cases = [
        DryRunCase(
            index=0,
            passed=None,  # 自测不比对期望值，跑成没跑成只看 status
            status=state,
            input_text=stdin_text or "",
            actual=(raw.get("stdout") or "")[:4000],
            stderr=(raw.get("stderr") or "")[:2000],
            time_ms=raw.get("time_ms"),
        )
    ]
    return DryRunResult(
        status=state,
        message="自测完成" if state == "ok" else "自测未通过",
        cases=cases,
    )
