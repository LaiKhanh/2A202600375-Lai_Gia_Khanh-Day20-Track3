"""Benchmark report rendering."""

from __future__ import annotations

from collections.abc import Mapping
from statistics import mean

from multi_agent_research_lab.core.schemas import BenchmarkMetrics


def render_markdown_report(metrics: list[BenchmarkMetrics]) -> str:
    """Render benchmark metrics to markdown."""

    lines = [
        "# Benchmark Report",
        "",
        "| Run | Latency (s) | Cost (USD) | Quality | Citation Cov. | Error Rate | Notes |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for item in metrics:
        cost = "" if item.estimated_cost_usd is None else f"{item.estimated_cost_usd:.4f}"
        quality = "" if item.quality_score is None else f"{item.quality_score:.1f}"
        citation_coverage = "" if item.citation_coverage is None else f"{item.citation_coverage:.2f}"
        error_rate = "" if item.error_rate is None else f"{item.error_rate:.2f}"
        lines.append(
            f"| {item.run_name} | {item.latency_seconds:.2f} | {cost} | {quality} | {citation_coverage} | {error_rate} | {item.notes} |"
        )
    return "\n".join(lines) + "\n"


def render_benchmark_report(
    run_order: list[str],
    metrics_by_run: Mapping[str, BenchmarkMetrics | None],
) -> str:
    """Render a benchmark ledger with placeholder rows for pending runs."""

    lines = [
        "# Benchmark Report",
        "",
        "| Run | Latency (s) | Cost (USD) | Quality | Citation Cov. | Error Rate | Notes |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for run_name in run_order:
        metric = metrics_by_run.get(run_name)
        if metric is None:
            lines.append(f"| {run_name} |  |  |  |  |  |  |")
            continue
        cost = "" if metric.estimated_cost_usd is None else f"{metric.estimated_cost_usd:.4f}"
        quality = "" if metric.quality_score is None else f"{metric.quality_score:.1f}"
        citation_coverage = "" if metric.citation_coverage is None else f"{metric.citation_coverage:.2f}"
        error_rate = "" if metric.error_rate is None else f"{metric.error_rate:.2f}"
        lines.append(
            f"| {metric.run_name} | {metric.latency_seconds:.2f} | {cost} | {quality} | {citation_coverage} | {error_rate} | {metric.notes} |"
        )
    lines.extend(
        [
            "",
            "## Failure Mode",
            "",
            "A common failure mode is that the workflow stops too early or loops between writer and critic when evidence is thin or citations are incomplete. The fix is to keep the max-iterations guard, require explicit source-backed citations before finalizing, and fall back to the deterministic local writer/critic path whenever a provider call is unavailable or fails.",
        ]
    )
    return "\n".join(lines) + "\n"


def parse_benchmark_report(report_text: str) -> tuple[list[str], dict[str, BenchmarkMetrics]]:
    """Parse a benchmark ledger back into ordered metrics."""

    run_order: list[str] = []
    metrics_by_run: dict[str, BenchmarkMetrics] = {}
    for raw_line in report_text.splitlines():
        line = raw_line.strip()
        if not line.startswith("|"):
            continue
        if line.startswith("|---") or line.startswith("| Run "):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) < 7:
            continue
        run_name = cells[0]
        try:
            latency_seconds = float(cells[1])
        except ValueError:
            continue
        metric = BenchmarkMetrics(
            run_name=run_name,
            latency_seconds=latency_seconds,
            estimated_cost_usd=_parse_optional_float(cells[2]),
            quality_score=_parse_optional_float(cells[3]),
            citation_coverage=_parse_optional_float(cells[4]),
            error_rate=_parse_optional_float(cells[5]),
            notes=cells[6],
        )
        run_order.append(run_name)
        metrics_by_run[run_name] = metric
    return run_order, metrics_by_run


def render_benchmark_comparison_report(comparisons: list[tuple[str, BenchmarkMetrics, BenchmarkMetrics]]) -> str:
    """Render a single-vs-multi benchmark comparison report."""

    lines = [
        "# Benchmark Comparison Report",
        "",
        "| Query | Single Latency (s) | Multi Latency (s) | Latency Delta (s) | Single Quality | Multi Quality | Quality Delta | Single Cost (USD) | Multi Cost (USD) | Single Citation Cov. | Multi Citation Cov. |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    single_latencies: list[float] = []
    multi_latencies: list[float] = []
    single_quality: list[float] = []
    multi_quality: list[float] = []
    for query, single, multi in comparisons:
        single_latencies.append(single.latency_seconds)
        multi_latencies.append(multi.latency_seconds)
        if single.quality_score is not None:
            single_quality.append(single.quality_score)
        if multi.quality_score is not None:
            multi_quality.append(multi.quality_score)
        single_cost = "" if single.estimated_cost_usd is None else f"{single.estimated_cost_usd:.4f}"
        multi_cost = "" if multi.estimated_cost_usd is None else f"{multi.estimated_cost_usd:.4f}"
        single_citation = "" if single.citation_coverage is None else f"{single.citation_coverage:.2f}"
        multi_citation = "" if multi.citation_coverage is None else f"{multi.citation_coverage:.2f}"
        quality_delta = _format_delta(single.quality_score, multi.quality_score)
        latency_delta = multi.latency_seconds - single.latency_seconds
        lines.append(
            f"| {query} | {single.latency_seconds:.2f} | {multi.latency_seconds:.2f} | {latency_delta:.2f} | {single.quality_score or 0:.1f} | {multi.quality_score or 0:.1f} | {quality_delta} | {single_cost} | {multi_cost} | {single_citation} | {multi_citation} |"
        )

    if comparisons:
        lines.extend(
            [
                "",
                "## Summary",
                "",
                f"- Average single-agent latency: {mean(single_latencies):.2f}s",
                f"- Average multi-agent latency: {mean(multi_latencies):.2f}s",
                f"- Average single-agent quality: {mean(single_quality):.1f}" if single_quality else "- Average single-agent quality: ",
                f"- Average multi-agent quality: {mean(multi_quality):.1f}" if multi_quality else "- Average multi-agent quality: ",
                "- Use the latency and quality deltas to judge whether the multi-agent orchestration is paying for its extra coordination cost.",
            ]
        )
    return "\n".join(lines) + "\n"


def _format_delta(single: float | None, multi: float | None) -> str:
    if single is None or multi is None:
        return ""
    return f"{multi - single:+.1f}"


def _parse_optional_float(value: str) -> float | None:
    if not value:
        return None
    return float(value)
