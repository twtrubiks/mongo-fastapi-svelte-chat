"""後端變異測試（mutation testing）工具

為什麼不用 mutmut 3：它以 trampoline 包裝函數，會跳過帶 decorator 的函數（所有
FastAPI 路由、Pydantic validator）、不變異 class 層級常數（Field 限制），且測試共用
同一個 MongoDB 資料庫，平行執行會互相干擾。本工具直接改寫原始碼：

- 變異以 AST 定位、以位元組精準替換原始碼，再重新 parse 驗證 AST 與預期一致
- 依 per-test coverage context 只跑「執行過該行」的測試；只在 import 期執行的
  module / class 層級程式碼則跑全套測試
- 每個 worker 擁有獨立的 backend 複本、MongoDB 資料庫名稱與 Redis DB 編號
- worker 預先 import 第三方套件後，每個變異體 fork 子程序在行程內執行 pytest；
  父程序從不 import app，且停用 bytecode，避免同大小同 mtime 的變異被舊 .pyc 遮蔽

使用方式（需先啟動與測試相同的 MongoDB / Redis，見 tests/test_config.py）：

    cd backend && python scripts/mutation_test.py all --workers 4

可分步執行：gen → coverage → setup → baseline → plan → run → report。
run 可中斷後續跑（以 claims 目錄記錄已領取的工作）。結果輸出於 .mutation/。
"""

from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
WORKDIR = BACKEND / ".mutation"

# ============================================================================
# 變異產生
# ============================================================================

LOG_METHODS = {"debug", "info", "warning", "warn", "error", "exception", "critical"}
LOG_OBJECTS = {"logger", "logging", "log", "_logger"}
# 這些 keyword 的字串只影響文件 / OpenAPI 描述，不變異
SKIP_KWARGS = {"description", "title", "summary", "example", "examples", "tags"}
NON_ASCII = re.compile(r"[^\x00-\x7f]")

CMP_SWAP = {
    ast.Eq: ast.NotEq,
    ast.NotEq: ast.Eq,
    ast.Lt: ast.LtE,
    ast.LtE: ast.Lt,
    ast.Gt: ast.GtE,
    ast.GtE: ast.Gt,
    ast.Is: ast.IsNot,
    ast.IsNot: ast.Is,
    ast.In: ast.NotIn,
    ast.NotIn: ast.In,
}
CMP_PATTERN = {
    ast.Eq: r"==",
    ast.NotEq: r"!=",
    ast.Lt: r"<(?!=)",
    ast.LtE: r"<=",
    ast.Gt: r">(?!=)",
    ast.GtE: r">=",
    ast.Is: r"\bis\b(?!\s+not\b)",
    ast.IsNot: r"\bis\s+not\b",
    ast.In: r"(?<!not )\bin\b",
    ast.NotIn: r"\bnot\s+in\b",
}
CMP_TEXT = {
    ast.Eq: "==",
    ast.NotEq: "!=",
    ast.Lt: "<",
    ast.LtE: "<=",
    ast.Gt: ">",
    ast.GtE: ">=",
    ast.Is: "is",
    ast.IsNot: "is not",
    ast.In: "in",
    ast.NotIn: "not in",
}
BIN_SWAP = {
    ast.Add: ast.Sub,
    ast.Sub: ast.Add,
    ast.Mult: ast.Div,
    ast.Div: ast.Mult,
    ast.FloorDiv: ast.Mult,
    ast.Mod: ast.Mult,
    ast.Pow: ast.Mult,
    ast.BitOr: ast.BitAnd,
    ast.BitAnd: ast.BitOr,
    ast.LShift: ast.RShift,
    ast.RShift: ast.LShift,
}
BIN_TEXT = {
    ast.Add: "+",
    ast.Sub: "-",
    ast.Mult: "*",
    ast.Div: "/",
    ast.FloorDiv: "//",
    ast.Mod: "%",
    ast.Pow: "**",
    ast.BitOr: "|",
    ast.BitAnd: "&",
    ast.LShift: "<<",
    ast.RShift: ">>",
}


def _dump(tree) -> str:
    return ast.dump(tree, include_attributes=False)


def _is_log_call(node) -> bool:
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Name) and func.id == "print":
        return True
    if isinstance(func, ast.Attribute) and func.attr in LOG_METHODS:
        owner = func.value
        if isinstance(owner, ast.Name) and owner.id in LOG_OBJECTS:
            return True
        if isinstance(owner, ast.Attribute) and owner.attr in LOG_OBJECTS:
            return True
    return False


def _replace_in_parent(tree, target, new) -> bool:
    """在 tree 中把 target 節點換成 new（new 為 None 表示換成 pass 敘述）"""
    for parent in ast.walk(tree):
        for field, value in ast.iter_fields(parent):
            if value is target:
                setattr(parent, field, new)
                return True
            if isinstance(value, list):
                for i, item in enumerate(value):
                    if item is target:
                        value[i] = new
                        return True
    return False


class MutantGenerator:
    """針對單一檔案產生變異體"""

    def __init__(self, path: Path, rel: str):
        self.rel = rel
        self.text = path.read_text()
        self.raw = self.text.encode()
        self.lines = self.text.splitlines()
        self.line_start = [0]
        for line in self.raw.splitlines(keepends=True):
            self.line_start.append(self.line_start[-1] + len(line))
        self.tree = ast.parse(self.text)
        self.parent = {
            child: node
            for node in ast.walk(self.tree)
            for child in ast.iter_child_nodes(node)
        }
        self.nodes = list(ast.walk(self.tree))
        self.index = {id(n): i for i, n in enumerate(self.nodes)}
        self.excluded = self._excluded_ids()
        self.mutants: list[dict] = []
        self.seen: set[str] = set()
        self.dropped = 0

    # ---- 位置工具（ast 的 col_offset 為 UTF-8 位元組偏移）--------------------
    def _off(self, lineno: int, col: int) -> int:
        return self.line_start[lineno - 1] + col

    def _span(self, node) -> tuple[int, int]:
        return (
            self._off(node.lineno, node.col_offset),
            self._off(node.end_lineno, node.end_col_offset),
        )

    def _seg(self, a: int, b: int) -> str:
        return self.raw[a:b].decode()

    def _find_between(self, left, right, pattern: str) -> tuple[int, int] | None:
        """在兩個節點之間的原始碼中搜尋運算子位置"""
        a = self._off(left.end_lineno, left.end_col_offset)
        b = self._off(right.lineno, right.col_offset)
        between = self._seg(a, b)
        found = re.search(pattern, between)
        if not found:
            return None
        start = a + len(between[: found.start()].encode())
        end = a + len(between[: found.end()].encode())
        return start, end

    # ---- 排除規則 --------------------------------------------------------
    def _excluded_ids(self) -> set[int]:
        excluded: set[int] = set()

        def mark(node):
            excluded.update(id(x) for x in ast.walk(node))

        for node in ast.walk(self.tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                args = node.args
                for arg in [*args.posonlyargs, *args.args, *args.kwonlyargs]:
                    if arg.annotation is not None:
                        mark(arg.annotation)
                for arg in (args.vararg, args.kwarg):
                    if arg is not None and arg.annotation is not None:
                        mark(arg.annotation)
                if node.returns is not None:
                    mark(node.returns)
            if isinstance(node, ast.AnnAssign):
                mark(node.annotation)
            if isinstance(
                node,
                (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef),
            ):
                first = node.body[0] if node.body else None
                if (
                    isinstance(first, ast.Expr)
                    and isinstance(first.value, ast.Constant)
                    and isinstance(first.value.value, str)
                ):
                    mark(first)  # docstring
            if _is_log_call(node) or isinstance(node, ast.JoinedStr):
                mark(node)
            if isinstance(node, ast.If):
                test = node.test
                if isinstance(test, ast.Name) and test.id == "TYPE_CHECKING":
                    mark(node)
                if (
                    isinstance(test, ast.Compare)
                    and isinstance(test.left, ast.Name)
                    and test.left.id == "__name__"
                ):
                    mark(node)
            if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id in ("__all__", "logger")
                for t in node.targets
            ):
                mark(node)
            if isinstance(node, ast.keyword) and node.arg in SKIP_KWARGS:
                mark(node)
            if isinstance(node, (ast.Import, ast.ImportFrom, ast.Global, ast.Nonlocal)):
                mark(node)
            lineno = getattr(node, "lineno", None)
            if lineno and "pragma: no mutate" in self.lines[lineno - 1]:
                excluded.add(id(node))
        return excluded

    # ---- 共用 -------------------------------------------------------------
    def _intended(self, node, apply) -> str | None:
        """在樹的深拷貝上套用變異，回傳預期的 AST dump"""
        tree = copy.deepcopy(self.tree)
        target = list(ast.walk(tree))[self.index[id(node)]]
        if apply(target, tree) is False:
            return None
        return _dump(tree)

    def _enclosing(self, node) -> str:
        current = node
        while current in self.parent:
            current = self.parent[current]
            if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
                return current.name
            if isinstance(current, ast.ClassDef):
                return f"<class {current.name}>"
        return "<module>"

    def _scope(self, node) -> str:
        """func：函數本體（可用行覆蓋率對應測試）；def:a-b：decorator / 預設值
        （對應該函數本體行）；module：import 期執行的程式碼"""
        current = node
        while current in self.parent:
            parent = self.parent[current]
            if isinstance(parent, ast.Lambda):
                if current is parent.body:
                    return "func"
            elif isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if current in parent.body:
                    return "func"
                return f"def:{parent.body[0].lineno}-{parent.body[-1].end_lineno}"
            current = parent
        return "module"

    def _add(self, node, op: str, candidates, want: str | None):
        """candidates：依序嘗試的 (a, b, 新文字) 替換；成功條件為 AST 與預期一致"""
        if want is None:
            return
        for a, b, new in candidates:
            mutated = (self.raw[:a] + new.encode() + self.raw[b:]).decode()
            try:
                tree = ast.parse(mutated)
            except SyntaxError:
                continue
            if _dump(tree) != want:
                continue
            digest = hashlib.sha1(mutated.encode()).hexdigest()[:12]
            if digest in self.seen:
                return
            self.seen.add(digest)
            self.mutants.append(
                {
                    "file": self.rel,
                    "line": node.lineno,
                    "end_line": getattr(node, "end_lineno", node.lineno),
                    "op": op,
                    "func": self._enclosing(node),
                    "scope": self._scope(node),
                    "orig": self._seg(a, b),
                    "new": new,
                    "a": a,
                    "b": b,
                }
            )
            return
        self.dropped += 1

    def _unparse_fallback(self, node, mutated_node) -> tuple[int, int, str]:
        a, b = self._span(node)
        return a, b, "(" + ast.unparse(mutated_node) + ")"

    def _replace_stmt(self, node, op: str, text: str, new_node):
        a, b = self._span(node)
        want = self._intended(
            node, lambda c, t: _replace_in_parent(t, c, new_node) or False
        )
        self._add(node, op, [(a, b, text)], want)

    def run(self) -> list[dict]:
        for node in self.nodes:
            if id(node) in self.excluded:
                continue
            handler = getattr(self, "_m_" + type(node).__name__, None)
            if handler:
                handler(node)
        return self.mutants

    # ---- 變異運算子 -------------------------------------------------------
    def _m_Compare(self, node):
        prev = node.left
        for i, op in enumerate(node.ops):
            nxt = node.comparators[i]
            new_op = CMP_SWAP.get(type(op))
            if new_op:

                def apply(c, t, i=i, new_op=new_op):
                    c.ops[i] = new_op()

                cands = []
                pos = self._find_between(prev, nxt, CMP_PATTERN[type(op)])
                if pos:
                    cands.append((*pos, CMP_TEXT[new_op]))
                mutated = copy.deepcopy(node)
                mutated.ops[i] = new_op()
                cands.append(self._unparse_fallback(node, mutated))
                label = f"cmp {CMP_TEXT[type(op)]} -> {CMP_TEXT[new_op]}"
                self._add(node, label, cands, self._intended(node, apply))
            prev = nxt

    def _m_BoolOp(self, node):
        old, new = ("and", "or") if isinstance(node.op, ast.And) else ("or", "and")
        new_cls = ast.Or if isinstance(node.op, ast.And) else ast.And
        for i in range(len(node.values) - 1):

            def apply(c, t, i=i):
                def group(values):
                    if len(values) == 1:
                        return values[0]
                    return ast.BoolOp(op=type(c.op)(), values=values)

                swapped = ast.BoolOp(
                    op=new_cls(),
                    values=[group(c.values[: i + 1]), group(c.values[i + 1 :])],
                )
                return _replace_in_parent(t, c, swapped) or False

            cands = []
            pos = self._find_between(node.values[i], node.values[i + 1], rf"\b{old}\b")
            if pos:
                cands.append((*pos, new))
            a, b = self._span(node)
            left = f" {old} ".join(
                "(" + self._seg(*self._span(v)) + ")" for v in node.values[: i + 1]
            )
            right = f" {old} ".join(
                "(" + self._seg(*self._span(v)) + ")" for v in node.values[i + 1 :]
            )
            cands.append((a, b, f"(({left}) {new} ({right}))"))
            self._add(node, f"bool {old} -> {new}", cands, self._intended(node, apply))

    def _m_UnaryOp(self, node):
        if not isinstance(node.op, ast.Not):
            return
        a, b = self._span(node)
        operand_a, operand_b = self._span(node.operand)
        want = self._intended(
            node, lambda c, t: _replace_in_parent(t, c, c.operand) or False
        )
        cands = [
            (a, operand_a, ""),
            (a, b, "(" + self._seg(operand_a, operand_b) + ")"),
        ]
        self._add(node, "not x -> x", cands, want)

    def _m_BinOp(self, node):
        new_op = BIN_SWAP.get(type(node.op))
        if not new_op:
            return
        if isinstance(node.op, ast.Mod) and isinstance(node.left, ast.Constant):
            return  # 字串 % 格式化

        def apply(c, t):
            c.op = new_op()

        old_text = BIN_TEXT[type(node.op)]
        cands = []
        pos = self._find_between(node.left, node.right, re.escape(old_text))
        if pos:
            cands.append((*pos, BIN_TEXT[new_op]))
        mutated = copy.deepcopy(node)
        mutated.op = new_op()
        cands.append(self._unparse_fallback(node, mutated))
        label = f"binop {old_text} -> {BIN_TEXT[new_op]}"
        self._add(node, label, cands, self._intended(node, apply))

    def _m_AugAssign(self, node):
        new_op = BIN_SWAP.get(type(node.op))
        if not new_op:
            return

        def apply(c, t):
            c.op = new_op()

        old_text = BIN_TEXT[type(node.op)] + "="
        pos = self._find_between(node.target, node.value, re.escape(old_text))
        if pos:
            new_text = BIN_TEXT[new_op] + "="
            self._add(
                node,
                f"augassign {old_text} -> {new_text}",
                [(*pos, new_text)],
                self._intended(node, apply),
            )

    def _m_Constant(self, node):
        value = node.value
        a, b = self._span(node)

        def set_value(new_value):
            def apply(c, t):
                c.value = new_value

            return apply

        if isinstance(value, bool):
            new = "False" if value else "True"
            self._add(
                node,
                f"const {value} -> {new}",
                [(a, b, new)],
                self._intended(node, set_value(not value)),
            )
        elif isinstance(value, (int, float)):
            plus = value + 1
            self._add(
                node,
                f"num {value!r} -> {plus!r}",
                [(a, b, repr(plus))],
                self._intended(node, set_value(plus)),
            )
            if isinstance(value, int) and value not in (0, 1):
                self._add(
                    node,
                    f"num {value!r} -> 0",
                    [(a, b, "0")],
                    self._intended(node, set_value(0)),
                )
        elif isinstance(value, str):
            # 含非 ASCII 的多為給人看的訊息；單獨成敘述的字串無作用
            if NON_ASCII.search(value) or isinstance(self.parent.get(node), ast.Expr):
                return
            mutated = "XX" + value + "XX"
            self._add(
                node,
                "str mutate",
                [(a, b, json.dumps(mutated))],
                self._intended(node, set_value(mutated)),
            )

    def _m_Expr(self, node):
        call = node.value.value if isinstance(node.value, ast.Await) else node.value
        if isinstance(call, ast.Call) and not _is_log_call(call):
            self._replace_stmt(node, "delete call stmt", "pass", ast.Pass())

    def _m_Assign(self, node):
        # 只刪除屬性 / 下標賦值；刪除區域變數賦值幾乎必然 NameError，沒有資訊量
        if all(isinstance(t, (ast.Subscript, ast.Attribute)) for t in node.targets):
            if self._enclosing(node) != "__init__":
                self._replace_stmt(node, "delete attr/item assign", "pass", ast.Pass())

    def _m_Raise(self, node):
        if node.exc is not None:
            self._replace_stmt(node, "delete raise", "pass", ast.Pass())

    def _m_Return(self, node):
        value = node.value
        if value is None or (
            isinstance(value, ast.Constant)
            and (value.value is None or isinstance(value.value, bool))
        ):
            return
        a, b = self._span(value)

        def apply(c, t):
            c.value = ast.Constant(value=None)

        self._add(
            node,
            "return x -> return None",
            [(a, b, "None")],
            self._intended(node, apply),
        )

    def _negate(self, node, label: str):
        test = node.test
        if isinstance(test, (ast.Compare, ast.BoolOp, ast.Constant)):
            return  # 已由比較 / 布林運算子變異涵蓋
        if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
            return
        a, b = self._span(test)

        def apply(c, t):
            c.test = ast.UnaryOp(op=ast.Not(), operand=c.test)

        self._add(
            node,
            label,
            [(a, b, "not (" + self._seg(a, b) + ")")],
            self._intended(node, apply),
        )

    def _m_If(self, node):
        self._negate(node, "negate if-cond")

    def _m_IfExp(self, node):
        self._negate(node, "negate ternary-cond")

    def _m_Break(self, node):
        self._replace_stmt(node, "break -> continue", "continue", ast.Continue())

    def _m_Continue(self, node):
        self._replace_stmt(node, "continue -> break", "break", ast.Break())


def cmd_gen(args):
    WORKDIR.mkdir(exist_ok=True)
    mutants: list[dict] = []
    for path in sorted((BACKEND / "app").rglob("*.py")):
        rel = str(path.relative_to(BACKEND))
        gen = MutantGenerator(path, rel)
        found = gen.run()
        mutants.extend(found)
        if found or gen.dropped:
            print(f"  {rel:55s} {len(found):5d}  (dropped {gen.dropped})")
    for i, mutant in enumerate(mutants):
        mutant["id"] = i
    (WORKDIR / "mutants.json").write_text(json.dumps(mutants, ensure_ascii=False))
    print(f"共產生 {len(mutants)} 個變異體")


# ============================================================================
# 覆蓋率對應、worker 複本、隔離基準
# ============================================================================


def cmd_coverage(args):
    WORKDIR.mkdir(exist_ok=True)
    env = {**os.environ, "COVERAGE_FILE": str(WORKDIR / ".coverage_ctx")}
    base = [sys.executable, "-m", "pytest", "tests/", "-p", "no:cacheprovider"]
    collected = subprocess.run(
        [*base, "-o", "addopts=", "--collect-only", "-q"],
        cwd=BACKEND,
        capture_output=True,
        text=True,
        check=True,
    )
    node_ids = [ln for ln in collected.stdout.splitlines() if "::" in ln]
    (WORKDIR / "nodeids.json").write_text(json.dumps(node_ids))
    print(f"收集到 {len(node_ids)} 個測試，以 per-test context 執行覆蓋率…")
    subprocess.run(
        [
            *base,
            "-q",
            "-o",
            "addopts=",
            "--cov=app",
            "--cov-context=test",
            "--cov-report=",
        ],
        cwd=BACKEND,
        env=env,
        check=True,
    )


def cmd_setup(args):
    for i in range(args.workers):
        dst = WORKDIR / f"w{i}" / "backend"
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(
            BACKEND,
            dst,
            ignore=shutil.ignore_patterns(
                "__pycache__",
                "htmlcov",
                ".coverage*",
                "uploads",
                ".pytest_cache",
                ".mutation",
                "*.pyc",
            ),
        )
    print(f"已建立 {args.workers} 個 worker 複本（各自的 MongoDB DB 與 Redis DB）")


def _worker_test_env(index: int) -> dict[str, str]:
    """每個 worker 使用自己的 MongoDB DB 與 Redis DB（見 tests/test_config.py）"""
    return {
        "TEST_DATABASE_NAME": f"test_chatroom_mut{index}",
        "TEST_REDIS_URL": f"redis://localhost:6379/{2 + index}",
    }


def _launch_workers(jobs_file: Path, workers: int):
    procs = [
        subprocess.Popen(
            [
                sys.executable,
                str(Path(__file__).resolve()),
                "worker",
                str(i),
                str(jobs_file),
            ],
            cwd=WORKDIR / f"w{i}" / "backend",
            env={**os.environ, **_worker_test_env(i)},
        )
        for i in range(workers)
    ]
    for proc in procs:
        proc.wait()


def _results() -> dict[str, dict]:
    out = {}
    for path in (WORKDIR / "results").glob("*.jsonl"):
        for line in path.read_text().splitlines():
            row = json.loads(line)
            out[row["key"]] = row
    return out


def _prepare_run_dirs():
    for name in ("claims", "results", "logs"):
        (WORKDIR / name).mkdir(parents=True, exist_ok=True)
    # 清掉已領取但沒有結果的 claim（上次被中斷的工作）
    done = set(_results())
    for claim in (WORKDIR / "claims").iterdir():
        if claim.name not in done:
            claim.unlink()


def cmd_baseline(args):
    """每個測試單獨跑一次：確認無順序相依，並量測耗時供 timeout 使用"""
    _prepare_run_dirs()
    node_ids = json.loads((WORKDIR / "nodeids.json").read_text())
    jobs = [
        {"key": f"iso_{i}", "kind": "iso", "tests": [t], "timeout": 120}
        for i, t in enumerate(node_ids)
    ]
    jobs_file = WORKDIR / "jobs_baseline.json"
    jobs_file.write_text(json.dumps(jobs))
    _launch_workers(jobs_file, args.workers)
    results = _results()
    failed = [
        node_ids[int(k[4:])]
        for k, r in results.items()
        if k.startswith("iso_") and not (r["how"] == "exit" and r["code"] == 0)
    ]
    if failed:
        print("以下測試單獨執行會失敗（順序相依或不穩定），請先修正：")
        for node_id in failed:
            print("  ", node_id)
        raise SystemExit(1)
    print(f"{len(jobs)} 個測試單獨執行皆通過")


# ============================================================================
# 規劃：每個變異體要跑哪些測試
# ============================================================================


def cmd_plan(args):
    from coverage import CoverageData

    node_ids = json.loads((WORKDIR / "nodeids.json").read_text())
    order = {t: i for i, t in enumerate(node_ids)}
    results = _results()
    durations = {
        node_ids[int(k[4:])]: r["dt"]
        for k, r in results.items()
        if k.startswith("iso_")
    }
    sorted_dt = sorted(durations.values())
    overhead = sorted_dt[len(sorted_dt) // 10]
    cost = {t: max(0.03, d - overhead) for t, d in durations.items()}

    data = CoverageData(str(WORKDIR / ".coverage_ctx"))
    data.read()
    raw: dict[str, dict[int, set[str]]] = {}
    by_test: dict[str, dict[int, set[str]]] = {}
    for measured in data.measured_files():
        rel = str(Path(measured).relative_to(BACKEND))
        contexts = data.contexts_by_lineno(measured)
        raw[rel] = contexts
        by_test[rel] = {
            line: {
                c.rsplit("|", 1)[0] for c in ctxs if c and c.rsplit("|", 1)[0] in order
            }
            for line, ctxs in contexts.items()
        }

    mutants = json.loads((WORKDIR / "mutants.json").read_text())
    jobs, no_cov = [], []
    for mutant in mutants:
        file_cov = by_test.get(mutant["file"], {})
        scope = mutant["scope"]
        if scope.startswith("def:"):
            start, end = map(int, scope[4:].split("-"))
            lines = range(start, end + 1)
        else:
            lines = range(mutant["line"], mutant["end_line"] + 1)
        if scope != "module":
            tests = set().union(*(file_cov.get(ln, set()) for ln in lines))
            executed = any(ln in raw.get(mutant["file"], {}) for ln in lines)
            if not tests and executed:
                scope = "module"  # 只在 import 期執行過
        if scope == "module":
            # 跑全套測試，覆蓋同檔案的測試排前面（搭配 -x 可更快殺死）
            related = set().union(*file_cov.values()) if file_cov else set()
            ordered = sorted(related, key=order.get) + [
                t for t in node_ids if t not in related
            ]
        else:
            ordered = sorted(tests, key=order.get)
        if not ordered:
            no_cov.append(mutant["id"])
            continue
        estimate = overhead + sum(cost.get(t, 1.0) for t in ordered)
        jobs.append(
            {
                "key": f"m{mutant['id']}",
                "kind": "mut",
                "mid": mutant["id"],
                "tests": ordered,
                "timeout": round(2.5 * estimate + 20, 1),
                "extra": ["-x"],
                "estimate": estimate,
            }
        )
    jobs.sort(key=lambda j: -j["estimate"])  # 長的先跑，負載較平均
    (WORKDIR / "jobs_mutants.json").write_text(json.dumps(jobs))
    (WORKDIR / "nocov.json").write_text(json.dumps(no_cov))
    hours = sum(j["estimate"] for j in jobs) / 3600
    print(
        f"{len(jobs)} 個變異體需執行，{len(no_cov)} 個落在無覆蓋程式碼；"
        f"上限估計 {hours:.1f} CPU 小時"
    )


def cmd_run(args):
    _prepare_run_dirs()
    started = time.monotonic()
    _launch_workers(WORKDIR / "jobs_mutants.json", args.workers)
    print(f"完成，耗時 {(time.monotonic() - started) / 60:.1f} 分鐘")


# ============================================================================
# worker（fork-server）
# ============================================================================

PRELOAD = [
    "asyncio",
    "PIL.Image",
    "aiofiles",
    "bcrypt",
    "bson",
    "fastapi",
    "fastapi.responses",
    "fastapi.security",
    "fastapi.middleware.cors",
    "fastapi.middleware.trustedhost",
    "fastapi.testclient",
    "httpx",
    "jwt",
    "pydantic",
    "pydantic_settings",
    "pymongo",
    "redis.asyncio",
    "starlette.middleware.base",
    "pydantic_ai",
    "pydantic_ai.models.google",
    "pydantic_ai.models.openai",
    "pydantic_ai.models.function",
    "pydantic_ai.models.test",
    "pytest",
    "pytest_asyncio",
    "unittest.mock",
]
FAIL_LINE = re.compile(r"^(?:FAILED|ERROR) (\S+)", re.M)


def _run_child(tests: list[str], log: Path, extra: list[str]) -> int:
    pid = os.fork()
    if pid == 0:
        try:
            fd = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
            os.dup2(fd, 1)
            os.dup2(fd, 2)
            os.setpgid(0, 0)
            import pytest

            code = pytest.main(
                [
                    "-q",
                    "-p",
                    "no:cacheprovider",
                    "-p",
                    "no:cov",
                    "-o",
                    "addopts=",
                    "--tb=line",
                    "-rfE",
                    "-W",
                    "ignore",
                    *extra,
                    *tests,
                ]
            )
            sys.stdout.flush()
            sys.stderr.flush()
            os._exit(int(code))
        except BaseException as exc:  # noqa: BLE001 - 子程序任何例外都要以 exit code 回報
            os.write(2, f"CHILD-EXC {exc!r}\n".encode())
            os._exit(99)
    return pid


def _wait_child(pid: int, timeout: float) -> tuple[str, int | None, float]:
    started = time.monotonic()
    while True:
        done, status = os.waitpid(pid, os.WNOHANG)
        elapsed = time.monotonic() - started
        if done:
            if os.WIFEXITED(status):
                return "exit", os.WEXITSTATUS(status), elapsed
            return "signal", -os.WTERMSIG(status), elapsed
        if elapsed > timeout:
            try:
                os.killpg(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            os.waitpid(pid, 0)
            return "timeout", None, elapsed
        time.sleep(0.02)


def cmd_worker(args):
    import importlib

    base = Path.cwd()
    sys.path.insert(0, str(base))
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    os.environ.setdefault("JWT_SECRET", "test-secret-key-very-long-and-secure")
    sys.dont_write_bytecode = True
    for cache in (base / "app").rglob("__pycache__"):
        shutil.rmtree(cache)
    for module in PRELOAD:
        try:
            importlib.import_module(module)
        except ImportError as exc:
            print(f"[w{args.index}] 預載 {module} 失敗：{exc}", file=sys.stderr)
    if any(m == "app" or m.startswith(("app.", "tests")) for m in sys.modules):
        raise SystemExit("app 不可在 worker 父程序中被 import")

    jobs = json.loads(Path(args.jobs).read_text())
    mutants = {m["id"]: m for m in json.loads((WORKDIR / "mutants.json").read_text())}
    originals: dict[str, bytes] = {}
    out = open(WORKDIR / "results" / f"w{args.index}.jsonl", "a", buffering=1)

    for job in jobs:
        key = job["key"]
        try:
            fd = os.open(WORKDIR / "claims" / key, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
        except FileExistsError:
            continue
        target = None
        if job["kind"] == "mut":
            mutant = mutants[job["mid"]]
            target = base / mutant["file"]
            original = originals.setdefault(mutant["file"], target.read_bytes())
            if original[mutant["a"] : mutant["b"]].decode() != mutant["orig"]:
                raise SystemExit(f"{key}：原始碼與變異位置不符，請重新執行 gen")
            target.write_bytes(
                original[: mutant["a"]]
                + mutant["new"].encode()
                + original[mutant["b"] :]
            )
        log = WORKDIR / "logs" / f"{key}.log"
        try:
            pid = _run_child(job["tests"], log, job.get("extra", []))
            how, code, elapsed = _wait_child(pid, job["timeout"])
        finally:
            if target is not None:
                target.write_bytes(originals[mutant["file"]])
        text = log.read_text(errors="replace") if log.exists() else ""
        tail = text.strip().splitlines()[-1] if text.strip() else ""
        row = {
            "key": key,
            "how": how,
            "code": code,
            "dt": round(elapsed, 2),
            "fails": FAIL_LINE.findall(text)[:3],
            "tail": tail[-300:],
        }
        if how == "exit" and code == 0 and job["kind"] == "mut":
            log.unlink(missing_ok=True)
        out.write(json.dumps(row, ensure_ascii=False) + "\n")
    out.close()


# ============================================================================
# 報告
# ============================================================================


def _status(mutant_id: int, no_cov: set[int], results: dict[str, dict]) -> str:
    if mutant_id in no_cov:
        return "no_cov"
    row = results.get(f"m{mutant_id}")
    if row is None:
        return "pending"
    if row["how"] == "timeout":
        return "killed"
    if row["how"] == "exit" and row["code"] == 0:
        return "survived"
    # 1：測試失敗；2：中斷 / 收集錯誤；3、4：變異讓 conftest 或 app import 時崩潰
    if row["how"] == "exit" and row["code"] in (1, 2, 3, 4):
        return "killed"
    return "error"


def cmd_report(args):
    mutants = json.loads((WORKDIR / "mutants.json").read_text())
    no_cov = set(json.loads((WORKDIR / "nocov.json").read_text()))
    results = _results()
    per_file: dict[str, Counter] = defaultdict(Counter)
    for mutant in mutants:
        mutant["status"] = _status(mutant["id"], no_cov, results)
        per_file[mutant["file"]][mutant["status"]] += 1
    total = Counter(m["status"] for m in mutants)
    killed, survived = total["killed"], total["survived"]

    lines = [
        "# 變異測試結果",
        "",
        f"- 變異體：{len(mutants)}（killed {killed} / survived {survived} / "
        f"無覆蓋 {total['no_cov']} / 未完成 {total['pending']} / 錯誤 {total['error']}）",
        f"- Mutation score：{killed / max(len(mutants), 1):.1%}"
        f"（僅計有覆蓋：{killed / max(killed + survived, 1):.1%}）",
        "",
        "| 檔案 | 總數 | killed | survived | 無覆蓋 | score | 有覆蓋 score |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    rows = []
    for file, counts in per_file.items():
        n = sum(counts.values())
        covered = counts["killed"] + counts["survived"]
        rows.append(
            (
                counts["killed"] / n,
                f"| `{file}` | {n} | {counts['killed']} | {counts['survived']} | "
                f"{counts['no_cov']} | {counts['killed'] / n:.0%} | "
                + (f"{counts['killed'] / covered:.0%} |" if covered else "— |"),
            )
        )
    lines += [row for _, row in sorted(rows)]
    lines += ["", "## 存活的變異體", ""]
    for mutant in sorted(mutants, key=lambda m: (m["file"], m["line"])):
        if mutant["status"] == "survived":
            lines.append(
                f"- `#{mutant['id']}` `{mutant['file']}:{mutant['line']}` "
                f"({mutant['func']}) {mutant['op']}：`{mutant['orig'][:60]!r}` → "
                f"`{mutant['new'][:60]!r}`"
            )
    report = WORKDIR / "report.md"
    report.write_text("\n".join(lines) + "\n")
    print("\n".join(lines[:5]))
    print(f"完整報告：{report}")


def cmd_all(args):
    for step in (cmd_gen, cmd_coverage, cmd_setup, cmd_baseline, cmd_plan, cmd_run):
        step(args)
    cmd_report(args)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("gen", "coverage", "plan", "report"):
        sub.add_parser(name)
    for name in ("setup", "baseline", "run", "all"):
        sub.add_parser(name).add_argument("--workers", type=int, default=os.cpu_count())
    worker = sub.add_parser("worker")
    worker.add_argument("index", type=int)
    worker.add_argument("jobs")
    args = parser.parse_args()
    {
        "gen": cmd_gen,
        "coverage": cmd_coverage,
        "setup": cmd_setup,
        "baseline": cmd_baseline,
        "plan": cmd_plan,
        "run": cmd_run,
        "report": cmd_report,
        "all": cmd_all,
        "worker": cmd_worker,
    }[args.cmd](args)


if __name__ == "__main__":
    main()
