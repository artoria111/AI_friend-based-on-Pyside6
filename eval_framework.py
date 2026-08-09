"""Evaluation framework for AI Desktop Pet.

Runs automated tests across 4 dimensions:
  - Tool Calling: does the LLM invoke the right function?
  - Memory Recall: can the LLM retrieve stored facts?
  - Mood Perception: does the LLM detect user emotion correctly?
  - Persona Consistency: does the reply follow character rules?

Usage:  python eval_framework.py
Output: eval_report.md
"""

import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime

# Ensure local imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import yaml
from openai import OpenAI

from mood_tracker import MoodTracker
from tools import TOOLS, execute

# ---------------------------------------------------------------------------
# ANSI colour helpers
# ---------------------------------------------------------------------------
COLORS = {
    "green": "\033[92m",
    "red": "\033[91m",
    "yellow": "\033[93m",
    "cyan": "\033[96m",
    "bold": "\033[1m",
    "dim": "\033[2m",
    "reset": "\033[0m",
}


def c(text: str, color: str) -> str:
    return f"{COLORS.get(color, '')}{text}{COLORS['reset']}"


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------
@dataclass
class TestResult:
    dimension: str
    name: str
    input_text: str
    expected: str
    actual: str
    passed: bool
    score: float
    details: dict = field(default_factory=dict)


# ===================================================================
#  EvalFramework
# ===================================================================
class EvalFramework:
    def __init__(self, config_path: str = "config.yaml"):
        # --- config ---
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)

        self.llm_client = OpenAI(
            base_url=self.config["llm"]["api_url"],
            api_key=self.config["llm"]["api_key"],
        )
        self.llm_model = self.config["llm"]["api_model"]
        self.system_prompt = self.config["prompt"]["content"]

        # --- MemoryManager (may fail gracefully) ---
        self.memory_manager = None
        mem_cfg = self.config.get("memory", {})
        if mem_cfg.get("enabled", True):
            try:
                from memory_manager import MemoryManager

                print(c("[Eval] Loading MemoryManager...", "dim"))
                self.memory_manager = MemoryManager(
                    llm_client=self.llm_client,
                    llm_config=self.config.get("llm", {}),
                    retrieval_k=mem_cfg.get("retrieval_k", 3),
                    embed_mode=mem_cfg.get("embed_mode", "local"),
                )
                print(c("[Eval] MemoryManager ready.", "green"))
            except Exception as e:
                print(c(f"[Eval] MemoryManager unavailable: {e}", "yellow"))

        # --- MoodTracker ---
        from mood_tracker import MoodTracker

        self.mood_tracker = MoodTracker()

        self.results: list[TestResult] = []

    # ------------------------------------------------------------------
    # Tool-call loop (replicates LLMWorker.run(), synchronous)
    # ------------------------------------------------------------------
    def _call_llm_tool_round(
        self, messages: list[dict], max_rounds: int = 5, inject_context: str = ""
    ) -> tuple[str, list[dict]]:
        """Returns (final_reply_text, all_tool_calls_made)."""
        msgs = list(messages)

        # Optionally inject extra context into system prompt
        if inject_context and msgs and msgs[0]["role"] == "system":
            msgs[0] = dict(msgs[0])
            msgs[0]["content"] = msgs[0]["content"] + "\n\n" + inject_context

        all_tool_calls: list[dict] = []

        for _ in range(max_rounds):
            try:
                response = self.llm_client.chat.completions.create(
                    model=self.llm_model,
                    messages=msgs,
                    tools=TOOLS,
                    temperature=0.7,
                )
            except Exception as e:
                return f"[API Error] {e}", all_tool_calls

            msg = response.choices[0].message

            if msg.tool_calls:
                assistant_msg: dict = {
                    "role": "assistant",
                    "content": msg.content or "",
                }
                rc = getattr(msg, "reasoning_content", None)
                if rc:
                    assistant_msg["reasoning_content"] = rc

                tc_list = []
                for tc in msg.tool_calls:
                    tc_list.append(
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                    )
                    try:
                        args = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        args = {}
                    all_tool_calls.append({"name": tc.function.name, "arguments": args})
                assistant_msg["tool_calls"] = tc_list
                msgs.append(assistant_msg)

                for tc in msg.tool_calls:
                    try:
                        args = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        args = {}
                    result = execute(
                        tc.function.name,
                        args,
                        memory_manager=self.memory_manager,
                        alarm_callback=None,
                        mood_tracker=self.mood_tracker,
                    )
                    msgs.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": result,
                        }
                    )
                continue  # next round

            else:
                return msg.content or "", all_tool_calls

        return "", all_tool_calls  # max rounds exhausted

    # ------------------------------------------------------------------
    # 1. Tool Calling tests
    # ------------------------------------------------------------------
    def tool_calling_tests(self) -> list[TestResult]:
        cases = [
            {
                "name": "write_memory",
                "input": "帮我记下我的生日是4月2日",
                "expected_tool": "write_memory",
            },
            {
                "name": "set_alarm",
                "input": "提醒我5分钟后喝水",
                "expected_tool": "set_alarm",
            },
            {
                "name": "search_memory",
                "input": "你还记得我喜欢喝什么吗？",
                "expected_tool": "search_memory",
            },
            {
                "name": "get_time",
                "input": "现在几点了？",
                "expected_tool": "get_time",
            },
            {
                "name": "set_mood",
                "input": "今天好开心！涨工资了！",
                "expected_tool": "set_mood",
            },
        ]

        results = []
        for case in cases:
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": case["input"]},
            ]
            reply, tool_calls = self._call_llm_tool_round(messages)
            called = [tc["name"] for tc in tool_calls]
            passed = case["expected_tool"] in called

            results.append(
                TestResult(
                    dimension="Tool Calling",
                    name=case["name"],
                    input_text=case["input"],
                    expected=f"LLM calls {case['expected_tool']}",
                    actual=f"called {called} → {reply[:60]}"
                    if called
                    else f"no tool calls → {reply[:80]}",
                    passed=passed,
                    score=1.0 if passed else 0.0,
                    details={"tool_calls": called, "reply": reply},
                )
            )

        # Clean up any facts stored during these tests
        if self.memory_manager:
            try:
                self.memory_manager.clear_all()
            except Exception:
                pass
        self.mood_tracker = MoodTracker()

        return results

    # ------------------------------------------------------------------
    # 2. Memory Recall tests
    # ------------------------------------------------------------------
    def memory_recall_tests(self) -> list[TestResult]:
        if self.memory_manager is None:
            return [
                TestResult(
                    dimension="Memory Recall",
                    name="SKIP",
                    input_text="",
                    expected="",
                    actual="MemoryManager not available",
                    passed=False,
                    score=0.0,
                )
            ]

        cases = [
            {
                "name": "recall_birthday",
                "facts": ["用户的生日是4月2日"],
                "input": "你知道我生日是什么时候吗？",
                "expected_keyword": "4月2日",
            },
            {
                "name": "recall_drink",
                "facts": ["用户喜欢喝红茶"],
                "input": "你记得我平时喜欢喝什么吗？",
                "expected_keyword": "红茶",
            },
            {
                "name": "recall_pet",
                "facts": ["用户养了一只叫团子的猫"],
                "input": "我的猫叫什么名字？",
                "expected_keyword": "团子",
            },
        ]

        results = []
        for case in cases:
            # Isolated setup
            self.memory_manager.clear_all()
            for fact in case["facts"]:
                self.memory_manager.add_fact(fact)

            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": case["input"]},
            ]
            reply, tool_calls = self._call_llm_tool_round(messages)
            passed = case["expected_keyword"] in reply

            results.append(
                TestResult(
                    dimension="Memory Recall",
                    name=case["name"],
                    input_text=case["input"],
                    expected=f"reply contains '{case['expected_keyword']}'",
                    actual=reply[:100],
                    passed=passed,
                    score=1.0 if passed else 0.0,
                    details={"tool_calls": [tc["name"] for tc in tool_calls]},
                )
            )

        self.memory_manager.clear_all()
        return results

    # ------------------------------------------------------------------
    # 3. Mood Perception tests
    # ------------------------------------------------------------------
    def mood_perception_tests(self) -> list[TestResult]:
        cases = [
            {
                "name": "mood_happy",
                "input": "今天好开心！涨工资了！",
                "expected_moods": ["happy"],
            },
            {
                "name": "mood_stressed",
                "input": "最近压力好大，睡不着觉",
                "expected_moods": ["worried", "sad", "tired"],
            },
            {
                "name": "mood_angry",
                "input": "气死我了，怎么会有这种人！",
                "expected_moods": ["angry"],
            },
            {
                "name": "mood_sad",
                "input": "心情不好，今天被老板骂了",
                "expected_moods": ["sad", "tired", "worried"],
            },
            {
                "name": "mood_excited",
                "input": "太棒了！我拿到offer了！",
                "expected_moods": ["excited", "happy"],
            },
        ]

        results = []
        for case in cases:
            self.mood_tracker = MoodTracker()
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": case["input"]},
            ]
            reply, tool_calls = self._call_llm_tool_round(messages)
            set_mood_calls = [tc for tc in tool_calls if tc["name"] == "set_mood"]

            if set_mood_calls:
                detected = set_mood_calls[0]["arguments"].get("mood", "")
                passed = detected in case["expected_moods"]
                actual = f"set_mood({detected})"
            else:
                detected = ""
                passed = False
                actual = f"no set_mood call → {reply[:60]}"

            results.append(
                TestResult(
                    dimension="Mood Perception",
                    name=case["name"],
                    input_text=case["input"],
                    expected=f"set_mood in {case['expected_moods']}",
                    actual=actual,
                    passed=passed,
                    score=1.0 if passed else 0.0,
                    details={"detected": detected, "reply": reply},
                )
            )

        return results

    # ------------------------------------------------------------------
    # 4. Persona Consistency tests
    # ------------------------------------------------------------------
    def persona_consistency_tests(self) -> list[TestResult]:
        greeting = "你好！今天天气真好呀～"
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": greeting},
        ]
        reply, _ = self._call_llm_tool_round(messages)

        forbidden_terms = ["AI", "程序", "人工智能", "language model", "LLM"]
        checks = [
            {
                "name": "no_forbidden_terms",
                "desc": "reply must not contain AI/program terms",
                "passed": not any(t in reply for t in forbidden_terms),
                "actual": f"reply: {reply[:60]}",
            },
            {
                "name": "uses_tilde",
                "desc": "reply should use '～' (speech style)",
                "passed": "～" in reply,
                "actual": f"reply: {reply[:60]}",
            },
            {
                "name": "short_reply",
                "desc": "reply must be <= 50 characters",
                "passed": len(reply) <= 50,
                "actual": f"{len(reply)} chars: {reply[:60]}",
            },
        ]

        results = []
        for chk in checks:
            results.append(
                TestResult(
                    dimension="Persona Consistency",
                    name=chk["name"],
                    input_text=greeting,
                    expected=chk["desc"],
                    actual=chk["actual"],
                    passed=chk["passed"],
                    score=1.0 if chk["passed"] else 0.0,
                )
            )

        return results

    # ------------------------------------------------------------------
    # Run & Report
    # ------------------------------------------------------------------
    def _print_header(self, title: str):
        print()
        print(c(f"  {title}", "bold"))
        print(c("  " + "-" * 50, "dim"))

    def _print_result(self, r: TestResult):
        icon = c("PASS", "green") if r.passed else c("FAIL", "red")
        print(f"    [{icon}] {r.name}")
        if not r.passed:
            print(c(f"          expected: {r.expected}", "dim"))
            print(c(f"          actual:   {r.actual}", "yellow"))

    def _run_group(self, title: str, fn) -> list[TestResult]:
        self._print_header(title)
        results = fn()
        for r in results:
            self._print_result(r)
        return results

    def run_all(self):
        print(c("\n╔══════════════════════════════════════╗", "bold"))
        print(c("║  AI Desktop Pet - Evaluation Suite   ║", "bold"))
        print(c("╚══════════════════════════════════════╝", "bold"))
        print(c(f"  Model: {self.llm_model}", "dim"))

        self.results = []
        self.results += self._run_group("1. Tool Calling", self.tool_calling_tests)
        self.results += self._run_group("2. Memory Recall", self.memory_recall_tests)
        self.results += self._run_group(
            "3. Mood Perception", self.mood_perception_tests
        )
        self.results += self._run_group(
            "4. Persona Consistency", self.persona_consistency_tests
        )

        self._print_summary()
        self._write_report()

    def _print_summary(self):
        dims = {}
        for r in self.results:
            dims.setdefault(r.dimension, []).append(r)

        print()
        print(c("  ══ SUMMARY ══", "bold"))
        total_passed = 0
        total_tests = 0
        for dim, items in dims.items():
            passed = sum(1 for r in items if r.passed)
            score = passed / len(items) if items else 0
            pct = f"{score * 100:.0f}%"
            colour = "green" if score >= 0.7 else ("yellow" if score >= 0.4 else "red")
            print(f"    {dim:22s} {passed}/{len(items)}  {c(pct, colour)}")
            total_passed += passed
            total_tests += len(items)

        overall = total_passed / total_tests if total_tests else 0
        overall_colour = (
            "green" if overall >= 0.7 else ("yellow" if overall >= 0.4 else "red")
        )
        print(
            c(
                f"    {'TOTAL':22s} {total_passed}/{total_tests}  {c(f'{overall * 100:.0f}%', overall_colour)}",
                "bold",
            )
        )
        print()

    def _write_report(self):
        dims: dict[str, list[TestResult]] = {}
        for r in self.results:
            dims.setdefault(r.dimension, []).append(r)

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        lines = [
            "# AI Desktop Pet Evaluation Report",
            f"**Date:** {now}",
            f"**Model:** {self.llm_model}",
            "**Config:** config.yaml",
            "",
            "## Summary",
            "",
            "| Dimension | Score | Details |",
            "|-----------|-------|---------|",
        ]

        total_passed = 0
        total_tests = 0
        for dim, items in dims.items():
            passed = sum(1 for r in items if r.passed)
            pct = f"{passed / len(items) * 100:.0f}%" if items else "N/A"
            details = ", ".join(
                f"{'PASS' if r.passed else 'FAIL'}: {r.name}" for r in items
            )
            lines.append(f"| {dim} | {passed}/{len(items)} ({pct}) | {details} |")
            total_passed += passed
            total_tests += len(items)

        overall_pct = (
            f"{total_passed / total_tests * 100:.0f}%" if total_tests else "N/A"
        )
        lines.append(
            f"| **Total** | **{total_passed}/{total_tests} ({overall_pct})** | |"
        )
        lines.append("")

        for dim, items in dims.items():
            lines.append(f"## {dim}")
            lines.append("")
            for i, r in enumerate(items, 1):
                status = "PASS" if r.passed else "FAIL"
                lines.append(f"### {i}. {r.name}  {status} ({r.score:.0f})")
                lines.append(f"- **Input:** {r.input_text}")
                lines.append(f"- **Expected:** {r.expected}")
                lines.append(f"- **Actual:** {r.actual}")
                if r.details:
                    safe_details = {k: v for k, v in r.details.items() if v}
                    if safe_details:
                        lines.append(
                            f"- **Details:** {json.dumps(safe_details, ensure_ascii=False)}"
                        )
                lines.append("")

        lines.append("---")
        lines.append(f"*Report generated {now}*")
        lines.append("")

        report = "\n".join(lines)
        with open("eval_report.md", "w", encoding="utf-8") as f:
            f.write(report)
        print(c("  Report saved to eval_report.md", "cyan"))


# ===================================================================
#  Main
# ===================================================================
if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    try:
        framework = EvalFramework("config.yaml")
    except Exception as e:
        print(c(f"[FATAL] Failed to initialise: {e}", "red"))
        sys.exit(1)

    framework.run_all()
