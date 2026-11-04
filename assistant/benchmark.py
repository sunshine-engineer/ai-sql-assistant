"""Paired, quota-admitted synthetic regressions with distinct failure layers.

File: assistant/benchmark.py
Maintainer: sunshine-engineer
Modified: 2026-10-23
"""

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy.exc import SQLAlchemyError

from .budgets import BudgetExceeded, RequestBudget, provider_error
from .business import CONTRACT, preflight
from .config import (
    DEFAULT_BENCHMARK_SECONDS,
    DEFAULT_MODEL,
    DEFAULT_OUTPUT_TOKENS,
    DEFAULT_PROVIDER_TIMEOUT_SECONDS,
    DEFAULT_REQUESTS_PER_MINUTE,
    DEFAULT_TOKENS_PER_MINUTE,
    EVALUATION_DIRECTORY,
)
from .evaluation import CASE_FILE, load_cases, same_results
from .generation import database_error_category, run_workflow
from .scheduling import QuotaScheduler, ScheduledModel, prepare_call
from .tracing import PROMPT_VERSION, Trace, model_identifier
from .validation import UnsafeSQL

HELDOUT = EVALUATION_DIRECTORY / "heldout_v1.json"
PROSPECTIVE = EVALUATION_DIRECTORY / "prospective_v1.json"
TRIAGE_IDS = ("R09", "R13", "R28", "R30", "H04", "H05", "H07", "H08")
BASELINE_PROMPT_VERSION = "one-shot-v2-no-cte-policy"
PROVIDER_FAILURES = {
    "rate_limit",
    "authentication",
    "model_or_request",
    "provider_timeout",
    "provider_unavailable",
    "provider_connection",
    "provider_error",
}
# Import compatibility for callers of the original interval-only adapter.
PacedModel = ScheduledModel


def suites(include_prospective=False):
    """Load versioned question groups, including the prospective suite only on explicit opt-in.

    Args:
        include_prospective: Whether to explicitly load the frozen prospective suite.

    Returns:
        dict: Selected suite names mapped to versioned case lists.

    Raises:
        OSError: If a requested suite file cannot be read.
        json.JSONDecodeError: If a requested suite is not valid JSON.
    """
    groups = {"development": load_cases(), "heldout": json.loads(HELDOUT.read_text())["cases"]}
    if include_prospective:
        groups["prospective"] = json.loads(PROSPECTIVE.read_text())["cases"]
    return groups


def case_completion(rows, cases, repeats):
    """Count complete, consistent, incomplete, and unattempted cases separately.

    Args:
        rows: Recorded per-case benchmark attempts.
        cases: Selected versioned cases with expected outcomes and reference SQL or rows.
        repeats: Number of planned repetitions for every case and approach.

    Returns:
        dict: Complete, consistent, incomplete, and unattempted case counts.
    """
    counts = dict(consistent_cases=0, completed_cases=0, incomplete_cases=0, unattempted_cases=0)
    expected = list(range(1, repeats + 1))
    for case in cases:
        recorded = [row for row in rows if row["id"] == case["id"]]
        if not recorded:
            counts["unattempted_cases"] += 1
        elif sorted(row["repeat"] for row in recorded) != expected:
            counts["incomplete_cases"] += 1
        else:
            counts["completed_cases"] += 1
            counts["consistent_cases"] += all(row["passed"] for row in recorded)
    return counts


def execution_error(exc, reference=False):
    """Classify execution failures without exporting database exception text.

    Args:
        exc: Raised exception to classify without exposing its private message.
        reference: Whether the failure came from the reference oracle rather than candidate SQL.

    Returns:
        tuple: Sanitized failure category and optional database subcategory.
    """
    prefix = "reference_" if reference else ""
    if isinstance(exc, UnsafeSQL):
        return prefix + "policy_rejection", None
    if isinstance(exc, SQLAlchemyError):
        return prefix + "database_error", database_error_category(exc)[0]
    return prefix + "execution_error", None


def reference_results(services, case):
    """Execute each gold query on all instances and retain invalid-oracle errors separately.

    Args:
        services: Mapping from synthetic instance names to their controlled query services.
        case: One versioned question contract with expected result or control outcome.

    Returns:
        tuple: Reference results by instance and a list of oracle failures.
    """
    references, errors = {}, []
    for name, service in services.items():
        try:
            result = service.query(case["gold_sql"])
            if result.get("error") or result.get("truncated"):
                errors.append(
                    {"instance": name, "passed": False, "error": "reference_result_invalid"}
                )
            else:
                references[name] = {**case, "columns": result["columns"], "rows": result["rows"]}
        except Exception as exc:
            error, detail = execution_error(exc, reference=True)
            errors.append(
                {"instance": name, "passed": False, "error": error, "database_category": detail}
            )
    return references, errors


def grade_sql(sql, services, case, references=None):
    """Compare the same candidate SQL with the reference results on every instance.

    Args:
        sql: Untrusted SQL text to validate before any execution.
        services: Mapping from synthetic instance names to their controlled query services.
        case: One versioned question contract with expected result or control outcome.
        references: Optional precomputed reference results keyed by synthetic instance name.

    Returns:
        list[dict]: Instance-level pass flags and sanitized mismatch or error categories.
    """
    if references is None:
        references, errors = reference_results(services, case)
        if errors:
            return errors
    outcomes = []
    for name, service in services.items():
        try:
            actual = service.query(sql)
            passed = same_results(actual, references[name])
            shape = len(actual.get("columns", [])) != len(references[name]["columns"]) or len(
                actual.get("rows", [])
            ) != len(references[name]["rows"])
            error = (
                None
                if passed
                else "result_invalid"
                if actual.get("error") or actual.get("truncated")
                else "result_mismatch"
            )
            outcomes.append(
                {
                    "instance": name,
                    "passed": passed,
                    "error": error,
                    "mismatch": None if passed else "shape" if shape else "values",
                }
            )
        except Exception as exc:
            error, detail = execution_error(exc)
            outcomes.append(
                {"instance": name, "passed": False, "error": error, "database_category": detail}
            )
    return outcomes


def one_shot(model, service, question, budget=None):
    """Generate SQL once under the same business contract without tools or SQL repair.

    Args:
        model: Model adapter supporting invoke and, for workflows, tool binding.
        service: Controlled QueryService used for schema inspection and SQL execution.
        question: Current natural-language analysis request.
        budget: RequestBudget shared by setup, provider admission, and execution.

    Returns:
        dict: Generated SQL or sanitized terminal failure with a trace.
    """
    decision = preflight(question)
    if decision:
        return {"outcome": decision[0], "sql": None, "answer_verified": None, "trace": None}
    system = (
        "Return ONLY JSON with one key sql containing one SQLite SELECT. No tools, no repairs. "
        "The execution policy forbids CTEs (WITH) and SQL comments. Use only approved tables. "
        "Use this retail contract: "
        + json.dumps(CONTRACT)
        + ". Metadata: "
        + service.describe(question)
    )
    messages = [SystemMessage(content=system), HumanMessage(content=question)]
    budget = budget or RequestBudget()
    trace = Trace(model=model_identifier(model))
    started, admitted = perf_counter(), False
    try:
        kwargs, reserved = prepare_call(model, budget, messages, [])
        admitted = True
        reply = model.invoke(messages, response_format={"type": "json_object"}, **kwargs)
        trace.usage(reply)
        budget.charge(reply, reserved)
        trace.model_calls.append(
            {"outcome": "succeeded", "duration_ms": round((perf_counter() - started) * 1000, 2)}
        )
        payload = json.loads(reply.content)
        if (
            not isinstance(payload, dict)
            or set(payload) != {"sql"}
            or not isinstance(payload["sql"], str)
        ):
            raise ValueError("invalid_baseline_output")
        return {
            "outcome": "answered",
            "sql": payload["sql"],
            "answer_verified": None,
            "trace": trace.export("answered"),
        }
    except Exception as exc:
        error = (
            "budget_exhausted"
            if isinstance(exc, BudgetExceeded)
            else "generation_or_format_failure"
            if isinstance(exc, (ValueError, TypeError))
            else provider_error(exc)
        )
        if admitted and not trace.model_calls:
            trace.model_calls.append(
                {
                    "outcome": "failed",
                    "error_category": error,
                    "duration_ms": round((perf_counter() - started) * 1000, 2),
                }
            )
        outcome = "budget_exhausted" if isinstance(exc, BudgetExceeded) else "failed"
        return {
            "outcome": outcome,
            "sql": None,
            "answer_verified": None,
            "trace": trace.export(outcome),
            "error": error,
        }


def benchmark(
    model,
    services,
    cases,
    repeats=2,
    split="heldout",
    diagnostics=None,
    request_seconds=DEFAULT_BENCHMARK_SECONDS,
    progress=None,
):
    """Evaluate paired workflow and baseline attempts across synthetic instances and repetitions.

    Args:
        model: Model adapter supporting invoke and, for workflows, tool binding.
        services: Mapping from synthetic instance names to their controlled query services.
        cases: Selected versioned cases with expected outcomes and reference SQL or rows.
        repeats: Number of planned repetitions for every case and approach.
        split: Evaluation group label recorded in the report.
        diagnostics: Optional authorized synthetic-only collector for raw plans and SQL.
        request_seconds: Wall-clock budget for each individual workflow or baseline attempt.
        progress: Optional callback receiving sanitized completion fields for each attempt.

    Returns:
        dict: Versioned paired report, completion counts, outcomes, and scheduling evidence.

    Raises:
        ValueError: If cases are empty or repeats is not positive.
        PermissionError: If diagnostic ownership or case authorization is invalid.
    """
    if repeats < 1 or not cases:
        raise ValueError("Use nonempty cases and positive repeats.")
    if diagnostics is not None:
        from .diagnostics import SyntheticDiagnostics

        if not isinstance(diagnostics, SyntheticDiagnostics):
            raise PermissionError("Use the benchmark-owned synthetic diagnostic collector.")
        diagnostics._owner.authorize(services)
        diagnostics.validate_cases(cases)
    source = hashlib.sha256()
    for path in sorted(Path(__file__).parent.glob("*.py")):
        source.update(path.name.encode() + path.read_bytes())
    rows = []
    consecutive_provider_failures = 0
    stopped = False
    # Preflight every oracle before spending provider quota. Cache only in memory.
    references = {
        c["id"]: reference_results(services, c)
        for c in cases
        if c["expected_outcome"] == "answered"
    }
    for repetition in range(repeats):
        if stopped:
            break
        for index, case in enumerate(cases):
            if stopped:
                break
            approaches = (
                ("workflow", "one_shot")
                if (index + repetition) % 2 == 0
                else ("one_shot", "workflow")
            )
            for approach in approaches:
                started = perf_counter()
                attempts, sql = [], None
                try:
                    oracle, invalid = references.get(case["id"], ({}, []))
                    if invalid:
                        rows.append(
                            {
                                "id": case["id"],
                                "split": split,
                                "repeat": repetition + 1,
                                "approach": approach,
                                "expected_outcome": case["expected_outcome"],
                                "outcome": "invalid_reference",
                                "passed": False,
                                "sql_suite_passed": None,
                                "answer_verified": None,
                                "displayed_answer_verified": None,
                                "answer_method": None,
                                "instances": invalid,
                                "trace": None,
                                "error": invalid[0]["error"],
                                "duration_ms": round((perf_counter() - started) * 1000, 2),
                            }
                        )
                        continue
                    budget = RequestBudget(seconds=request_seconds)
                    if approach == "workflow":
                        report = run_workflow(
                            model,
                            services["base"],
                            [{"role": "user", "content": case["question"]}],
                            budget=budget,
                        )
                        attempts = report.attempts
                        sql = next((a["sql"] for a in reversed(attempts) if a.get("result")), None)
                        status = report.answer_validation.get("status")
                        candidate = {
                            "outcome": report.outcome,
                            "sql": sql,
                            "answer_verified": report.answer_validation.get("model_verified")
                            if status in {"verified", "rejected"}
                            else None,
                            "displayed_answer_verified": report.answer_validation.get(
                                "displayed_verified"
                            ),
                            "answer_method": report.answer_validation.get("method", status),
                            "trace": report.trace,
                        }
                    else:
                        candidate = one_shot(
                            model, services["base"], case["question"], budget=budget
                        )
                        sql = candidate["sql"]
                    instances = (
                        grade_sql(sql, services, case, references=oracle)
                        if case["expected_outcome"] == "answered" and sql
                        else []
                    )
                    sql_passed = bool(instances) and all(i["passed"] for i in instances)
                    passed = candidate["outcome"] == case["expected_outcome"] and (
                        sql_passed if case["expected_outcome"] == "answered" else True
                    )
                    error = candidate.get("error")
                    if not passed and not error:
                        failure = next((i["error"] for i in instances if not i["passed"]), None)
                        error = failure or "outcome_mismatch"
                    trace = candidate.get("trace")
                    if trace:
                        failures = [
                            c.get("error_category")
                            for c in trace["model_calls"]
                            if c.get("error_category")
                        ]
                        if failures:
                            error = failures[-1]
                        elif not passed and not instances:
                            failures = [
                                c.get("error_category")
                                for c in trace["tool_calls"]
                                if c.get("error_category")
                            ]
                            error = failures[-1] if failures else error
                    row = {
                        "outcome": candidate["outcome"],
                        "passed": passed,
                        "sql_suite_passed": sql_passed
                        if case["expected_outcome"] == "answered"
                        else None,
                        "answer_verified": candidate["answer_verified"],
                        "displayed_answer_verified": candidate.get("displayed_answer_verified"),
                        "answer_method": candidate.get("answer_method"),
                        "instances": instances,
                        "trace": trace,
                        "error": error,
                    }
                except Exception as exc:
                    row = {
                        "outcome": "failed",
                        "passed": False,
                        "sql_suite_passed": False
                        if case["expected_outcome"] == "answered"
                        else None,
                        "answer_verified": None,
                        "displayed_answer_verified": None,
                        "answer_method": None,
                        "instances": [],
                        "trace": None,
                        "error": "generation_or_format_failure"
                        if isinstance(exc, (ValueError, TypeError))
                        else provider_error(exc),
                    }
                if diagnostics is not None:
                    diagnostics.record(case, approach, repetition + 1, sql, attempts)
                rows.append(
                    {
                        "id": case["id"],
                        "split": split,
                        "repeat": repetition + 1,
                        "approach": approach,
                        "expected_outcome": case["expected_outcome"],
                        "duration_ms": round((perf_counter() - started) * 1000, 2),
                        **row,
                    }
                )
                if progress is not None:
                    progress(
                        {k: rows[-1][k] for k in ("id", "repeat", "approach", "outcome", "error")}
                    )
                consecutive_provider_failures = (
                    consecutive_provider_failures + 1 if row["error"] in PROVIDER_FAILURES else 0
                )
                if consecutive_provider_failures >= 3:
                    stopped = True
                    break
    summary = {}
    for approach in ("workflow", "one_shot"):
        selected = [r for r in rows if r["approach"] == approach]
        sql_rows = [r for r in selected if r["sql_suite_passed"] is not None]
        answers = [r for r in selected if r["answer_verified"] is not None]
        displayed = [r for r in selected if r.get("displayed_answer_verified") is not None]
        summary[approach] = {
            "passed": sum(r["passed"] for r in selected),
            "total": len(selected),
            "invalid_references": sum(r["outcome"] == "invalid_reference" for r in selected),
            "sql_suite_passed": sum(r["sql_suite_passed"] for r in sql_rows),
            "sql_total": len(sql_rows),
            "answer_verified": sum(r["answer_verified"] for r in answers),
            "answer_total": len(answers),
            "displayed_answer_verified": sum(r["displayed_answer_verified"] for r in displayed),
            "displayed_answer_total": len(displayed),
            "canonical_answers": sum(r.get("answer_method") == "canonical_plan" for r in selected),
            **case_completion(selected, cases, repeats),
            "cases": len(cases),
        }
    scheduler = getattr(model, "scheduler", None)
    return {
        "mode": "live_paired_benchmark",
        "benchmark_version": "v4-complete-repetitions",
        "model": model_identifier(model),
        "prompt_version": PROMPT_VERSION,
        "source_sha256": source.hexdigest(),
        "baseline_prompt_version": BASELINE_PROMPT_VERSION,
        "model_parameters": {
            "temperature": 0,
            "max_output_tokens": DEFAULT_OUTPUT_TOKENS,
            "reasoning_effort": "none",
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "split": split,
        "repeats": repeats,
        "request_seconds": request_seconds,
        "suite_sha256": hashlib.sha256(json.dumps(cases, sort_keys=True).encode()).hexdigest(),
        "case_contract_version": json.loads(PROSPECTIVE.read_text())["version"]
        if split == "prospective"
        else json.loads(CASE_FILE.read_text())["case_contract_version"]
        + "/"
        + json.loads(HELDOUT.read_text())["version"],
        "evaluation_role": "prospective_holdout_same_author"
        if split == "prospective"
        else "regression",
        "instance_version": "retail-instances-v1",
        "instances": list(services),
        "scheduling": scheduler.summary() if isinstance(scheduler, QuotaScheduler) else None,
        "completion": {
            "planned_attempts": len(cases) * repeats * 2,
            "recorded_attempts": len(rows),
            "not_attempted": len(cases) * repeats * 2 - len(rows),
            "stop_reason": "consecutive_provider_failures" if stopped else None,
        },
        "scope": (
            "Prospective prompts frozen before this run, authored by the implementation agent: not independently authored or external. "
            if split == "prospective"
            else "Previously exposed questions are regression cases, not independent held-out evidence. "
        )
        + "Same SQL across synthetic instances. Canonical answers are deterministic; model-answer scores exclude them. Baseline has no answer stage.",
        "summary": summary,
        "rows": rows,
    }


def main():
    """Run a quota-admitted paired synthetic benchmark and persist its report.

    Returns:
        int: Zero after report generation, even if some attempts fail or the run stops early.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--split", choices=["development", "heldout", "triage", "prospective"], default="triage"
    )
    parser.add_argument(
        "--case-ids", help="Comma-separated IDs; select explicitly without editing suites."
    )
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument(
        "--interval",
        type=float,
        default=0,
        help="Additional minimum interval; quota admission is also enforced.",
    )
    parser.add_argument("--requests-per-minute", type=int, default=DEFAULT_REQUESTS_PER_MINUTE)
    parser.add_argument("--tokens-per-minute", type=int, default=DEFAULT_TOKENS_PER_MINUTE)
    parser.add_argument("--request-seconds", type=float, default=DEFAULT_BENCHMARK_SECONDS)
    parser.add_argument(
        "--synthetic-diagnostics",
        type=Path,
        help="Explicit opt-in to raw synthetic plan/SQL capture in a separate file.",
    )
    parser.add_argument(
        "--progress",
        action="store_true",
        help="Print sanitized per-case progress, never SQL or provider messages.",
    )
    parser.add_argument("--output", type=Path, default=Path("evaluation/results/benchmark-v2.json"))
    args = parser.parse_args()
    if (
        not 1 <= args.repeats <= 5
        or not 1 <= args.limit <= 50
        or not 0 < args.request_seconds <= 300
    ):
        parser.error("repeats 1..5, limit 1..50, request-seconds >0 and <=300")
    all_cases = suites(include_prospective=args.split == "prospective")
    pool = (
        [c for cases in all_cases.values() for c in cases]
        if args.split == "triage"
        else all_cases[args.split]
    )
    ids = (
        args.case_ids.split(",")
        if args.case_ids
        else TRIAGE_IDS
        if args.split == "triage"
        else None
    )
    if ids and (len(set(ids)) != len(ids) or not set(ids) <= set(c["id"] for c in pool)):
        parser.error("Use distinct known case IDs from the selected split.")
    cases = ([next(c for c in pool if c["id"] == i) for i in ids] if ids else pool)[: args.limit]
    try:
        scheduler = QuotaScheduler(args.requests_per_minute, args.tokens_per_minute, args.interval)
    except ValueError as exc:
        parser.error(str(exc))
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        parser.error("Configure GROQ_API_KEY locally; never pass credentials as CLI arguments.")
    from contextlib import nullcontext

    import langchain_groq

    from .diagnostics import SyntheticSuite

    llm = langchain_groq.ChatGroq(
        api_key=key,
        model=args.model,
        temperature=0,
        max_retries=0,
        timeout=DEFAULT_PROVIDER_TIMEOUT_SECONDS,
        max_tokens=DEFAULT_OUTPUT_TOKENS,
        reasoning_effort="none",
    )
    model = ScheduledModel(llm, scheduler=scheduler)
    with SyntheticSuite() as suite:
        with (
            suite.capture(suite.services)
            if args.synthetic_diagnostics
            else nullcontext(None) as capture
        ):
            report = benchmark(
                model,
                suite.services,
                cases,
                args.repeats,
                args.split,
                capture,
                args.request_seconds,
                progress=(lambda row: print(json.dumps(row), flush=True))
                if args.progress
                else None,
            )
            if capture is not None:
                args.synthetic_diagnostics.parent.mkdir(parents=True, exist_ok=True)
                args.synthetic_diagnostics.write_text(json.dumps(capture.export(), indent=2) + "\n")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {
                "model": report["model"],
                "summary": report["summary"],
                "scheduling": report["scheduling"],
                "output": str(args.output),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
