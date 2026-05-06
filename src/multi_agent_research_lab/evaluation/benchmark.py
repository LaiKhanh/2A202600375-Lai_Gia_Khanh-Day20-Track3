"""Benchmark helpers for single-agent vs multi-agent."""

from __future__ import annotations

import re
from time import perf_counter
from typing import Callable

from multi_agent_research_lab.core.schemas import BenchmarkMetrics
from multi_agent_research_lab.core.state import ResearchState


Runner = Callable[[str], ResearchState]


def run_benchmark(run_name: str, query: str, runner: Runner) -> tuple[ResearchState, BenchmarkMetrics]:
    """Measure latency and derive lightweight quality signals."""

    started = perf_counter()
    state = runner(query)
    latency = perf_counter() - started
    return state, build_metrics_from_state(run_name, state, latency)


def build_metrics_from_state(run_name: str, state: ResearchState, latency_seconds: float) -> BenchmarkMetrics:
    """Build benchmark metrics from an already executed workflow state."""

    estimated_tokens = _estimate_tokens(state)
    citation_coverage = _citation_coverage(state)
    error_rate = 1.0 if state.errors else 0.0
    quality_score = _quality_score(state, citation_coverage, error_rate)
    return BenchmarkMetrics(
        run_name=run_name,
        latency_seconds=latency_seconds,
        estimated_cost_usd=_estimate_cost_usd(estimated_tokens),
        quality_score=quality_score,
        citation_coverage=citation_coverage,
        error_rate=error_rate,
        notes=_benchmark_notes(state, estimated_tokens),
    )


def _estimate_tokens(state: ResearchState) -> int:
    token_total = 0
    for result in state.agent_results:
        token_total += int(result.metadata.get("input_tokens", 0) or 0)
        token_total += int(result.metadata.get("output_tokens", 0) or 0)
        if token_total == 0:
            token_total += max(len(result.content) // 4, 1)
    return token_total


def _estimate_cost_usd(token_total: int) -> float | None:
    if token_total <= 0:
        return None
    return round(token_total * 0.0000025, 4)


def _citation_coverage(state: ResearchState) -> float | None:
    if not state.sources or not state.final_answer:
        return 0.0 if state.final_answer else None
    cited = {int(match) for match in re.findall(r"\[(\d+)\]", state.final_answer)}
    return min(len(cited) / len(state.sources), 1.0) if cited else 0.0


def _quality_score(state: ResearchState, citation_coverage: float | None, error_rate: float) -> float:
    score = 0.0
    if state.sources:
        score += 2.0
    if state.research_notes:
        score += 2.0
    if state.analysis_notes:
        score += 2.0
    if state.final_answer:
        score += 2.0
    if citation_coverage:
        score += min(citation_coverage * 2.0, 2.0)
    if error_rate == 0.0:
        score += 1.0
    return round(min(score, 10.0), 1)


def _benchmark_notes(state: ResearchState, estimated_tokens: int) -> str:
    parts = [f"sources={len(state.sources)}", f"tokens≈{estimated_tokens}"]
    if state.errors:
        parts.append(f"errors={len(state.errors)}")
    return "; ".join(parts)
