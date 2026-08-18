"""
IGRIS OS V2.0 - Exercise Evaluator
====================================
Runs the validation function of every exercise in exercises/ and reports
which ones pass or fail, with execution time per exercise.

Usage:
    python exercises/evaluator.py
    python exercises/evaluator.py --only level1
    python exercises/evaluator.py --only level2
"""

from __future__ import annotations

import argparse
import asyncio
import importlib
import inspect
import sys
import time
from pathlib import Path
from typing import Callable

EXERCISES_DIR = Path(__file__).resolve().parent

# Explicit mapping: module -> validation function (avoids picking up
# generated helpers such as test_{name}_basic inside exercise 2.2).
EXERCISES: dict[str, str] = {
    "level1_exercise1_1_pubsub": "test_pubsub",
    "level1_exercise1_2_actor_model": "test_actor_model",
    "level1_exercise1_3_chat_system": "test_chat_system",
    "level1_exercise1_4_logging_system": "test_logging_system",
    "level1_exercise1_5_circuit_breaker": "test_circuit_breaker",
    "level1_exercise1_6_rate_limiting": "test_rate_limiting",
    "level1_simulation_puzzle_distributed": "test_puzzle_distributed",
    "level2_exercise2_1_ast_parsing": "test_ast_parsing",
    "level2_exercise2_2_test_generation": "test_test_generation",
    "level2_exercise2_3_bug_detection": "test_bug_detection",
    "level2_exercise2_4_async_refactoring": "test_async_refactoring",
    "level2_exercise2_5_fuzzing": "test_fuzzing",
    "level2_exercise2_6_cicd": "test_cicd",
    "level2_simulation_web_app": "test_web_app_generation",
    "level3_exercise3_1_microservices": "test_microservices",
    "level3_exercise3_2_load_balancing": "test_load_balancing",
    "level3_exercise3_3_caching": "test_caching",
    "level3_exercise3_4_sharding": "test_sharding",
    "level3_exercise3_5_logging": "test_logging",
    "level3_exercise3_6_monitoring": "test_monitoring",
    "level3_simulation_million_users": "test_million_users",
    "level4_exercise4_1_few_shot": "test_few_shot",
    "level4_exercise4_2_rlhf": "test_rlhf",
    "level4_exercise4_3_continual_learning": "test_continual_learning",
    "level4_exercise4_4_multimodal": "test_multimodal",
    "level4_exercise4_5_tool_use": "test_tool_use",
    "level4_exercise4_6_safety": "test_safety",
    "level4_simulation_self_improvement": "test_self_improvement",
    "graduation_project": "test_graduation",
}


def run_exercise(module_name: str, test_name: str) -> tuple[bool, float, str]:
    """Execute one exercise validation. Returns (passed, seconds, error)."""
    if str(EXERCISES_DIR) not in sys.path:
        sys.path.insert(0, str(EXERCISES_DIR))

    start = time.perf_counter()
    try:
        module = importlib.import_module(module_name)
        test_fn = getattr(module, test_name)
        if inspect.iscoroutinefunction(test_fn):
            result = asyncio.run(test_fn())
        else:
            result = test_fn()
        elapsed = time.perf_counter() - start
        return bool(result), elapsed, ""
    except Exception as exc:  # noqa: BLE001 - report every failure mode
        elapsed = time.perf_counter() - start
        return False, elapsed, f"{type(exc).__name__}: {exc}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run all IGRIS OS exercises.")
    parser.add_argument("--only", choices=["level1", "level2", "level3", "level4"],
                        default=None, help="Run only one level.")
    args = parser.parse_args()

    entries = list(EXERCISES.items())
    if args.only:
        entries = [(n, f) for n, f in entries if n.startswith(args.only)]

    print("=" * 62)
    print("IGRIS OS V2.0 - EXERCISE EVALUATION")
    print(f"{len(entries)} exercises | criteria from docs/SIMULATIONS_EXERCISES.md")
    print("=" * 62)

    passed = 0
    results: list[tuple[str, bool, float, str]] = []

    for module_name, test_name in entries:
        ok, elapsed, error = run_exercise(module_name, test_name)
        results.append((module_name, ok, elapsed, error))
        status = "PASS" if ok else "FAIL"
        marker = "✅" if ok else "❌"
        print(f"{marker} [{status}] {module_name:44s} {elapsed:6.1f}s")
        if error:
            print(f"     ! {error}")

    print("=" * 62)
    print(f"RESULT: {sum(1 for _, ok, _, _ in results if ok)}/{len(results)} passed")
    for module_name, ok, elapsed, _ in results:
        if not ok:
            print(f"  FAILED: {module_name} ({elapsed:.1f}s)")
    return 0 if all(ok for _, ok, _, _ in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())