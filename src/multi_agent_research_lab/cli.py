"""Command-line entrypoint for the lab starter."""

import re
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Annotated
from statistics import mean

import typer
import yaml
from rich.console import Console
from rich.panel import Panel

from multi_agent_research_lab.core.config import get_settings
from multi_agent_research_lab.core.schemas import AgentName, AgentResult, BenchmarkMetrics, ResearchQuery
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.evaluation.benchmark import build_metrics_from_state
from multi_agent_research_lab.evaluation.report import parse_benchmark_report, render_benchmark_report, render_markdown_report
from multi_agent_research_lab.graph.workflow import MultiAgentWorkflow
from multi_agent_research_lab.observability.logging import configure_logging
from multi_agent_research_lab.observability.tracing import render_json_trace
from multi_agent_research_lab.services.storage import LocalArtifactStore
from multi_agent_research_lab.services.llm_client import LLMClient
from multi_agent_research_lab.services.search_client import SearchClient

app = typer.Typer(help="Multi-Agent Research Lab starter CLI")
console = Console()


def _init() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)


@app.command()
def baseline(
    query: Annotated[str, typer.Option("--query", "-q", help="Research query")],
) -> None:
    """Run a minimal single-agent baseline."""

    _init()
    state, latency_seconds = _run_single_agent(query)
    _write_run_artifacts("baseline", query, state, latency_seconds)
    console.print(Panel.fit(state.final_answer, title="Single-Agent Baseline"))


@app.command("multi-agent")
def multi_agent(
    query: Annotated[str, typer.Option("--query", "-q", help="Research query")],
) -> None:
    """Run the multi-agent workflow skeleton."""

    _init()
    result, latency_seconds = _run_multi_agent(query)
    _write_run_artifacts("multi-agent", query, result, latency_seconds)
    console.print(result.model_dump_json(indent=2))


@app.command()
def benchmark(
    config_path: Annotated[
        Path,
        typer.Option(
            "--config",
            "-c",
            help="Path to a YAML config with benchmark queries",
        ),
    ] = Path("configs/lab_default.yaml"),
) -> None:
    """Run single-agent vs multi-agent benchmarks for all queries in a YAML config."""

    _init()
    queries = _load_benchmark_queries(config_path)
    store = LocalArtifactStore()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report_path = Path("reports/benchmark_report.md")
    run_order, metrics_by_run = _load_benchmark_ledger(report_path)
    planned_order = ["baseline"] + [f"baseline q{index}" for index in range(1, len(queries) + 1)] + [
        f"multi-agent q{index}" for index in range(1, len(queries) + 1)
    ]
    run_order = _merge_run_order(run_order, planned_order)
    single_agent_metrics: list[BenchmarkMetrics] = []

    for index, query in enumerate(queries, start=1):
        single_state, single_latency = _run_single_agent(query)
        single_run_name = f"baseline q{index}"
        single_metric = build_metrics_from_state(single_run_name, single_state, single_latency)
        single_agent_metrics.append(single_metric)
        metrics_by_run[single_run_name] = single_metric
        _write_trace_artifact(single_run_name, query, single_state, single_latency, store, timestamp)
        _write_benchmark_report(store, run_order, metrics_by_run)

    if single_agent_metrics:
        metrics_by_run["baseline"] = _summarize_single_agent_metrics(single_agent_metrics)
        _write_benchmark_report(store, run_order, metrics_by_run)

    for index, query in enumerate(queries, start=1):
        multi_state, multi_latency = _run_multi_agent(query)
        multi_run_name = f"multi-agent q{index}"
        metrics_by_run[multi_run_name] = build_metrics_from_state(multi_run_name, multi_state, multi_latency)
        _write_trace_artifact(multi_run_name, query, multi_state, multi_latency, store, timestamp)
        _write_benchmark_report(store, run_order, metrics_by_run)

    console.print((store.root / "benchmark_report.md").read_text(encoding="utf-8"))


def _run_single_agent(query: str) -> tuple[ResearchState, float]:
    request = ResearchQuery(query=query)
    state = ResearchState(request=request)
    search_client = SearchClient()
    llm_client = LLMClient()
    started = perf_counter()
    sources = search_client.search(request.query, max_results=request.max_sources)
    source_block = "\n".join(
        f"- [{index}] {source.title} | {source.url or 'n/a'} | {source.snippet}" for index, source in enumerate(sources, start=1)
    )
    response = llm_client.complete(
        "You are a single-agent research assistant. Search, synthesize, and answer clearly with citations.",
        f"Query: {request.query}\n\nAudience: {request.audience}\n\nSources:\n{source_block or '- No sources available.'}\n",
    )
    state.sources = sources
    state.final_answer = response.content.strip()
    state.agent_results.append(
        AgentResult(
            agent=AgentName.WRITER,
            content=state.final_answer,
            metadata={"source_count": len(sources)},
        )
    )
    state.add_trace_event("baseline.run", {"source_count": len(sources)})
    latency_seconds = perf_counter() - started
    return state, latency_seconds


def _run_multi_agent(query: str) -> tuple[ResearchState, float]:
    state = ResearchState(request=ResearchQuery(query=query))
    workflow = MultiAgentWorkflow()
    started = perf_counter()
    result = workflow.run(state)
    latency_seconds = perf_counter() - started
    return result, latency_seconds


def _write_run_artifacts(run_name: str, query: str, state: ResearchState, latency_seconds: float) -> None:
    store = LocalArtifactStore()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    _write_trace_artifact(run_name, query, state, latency_seconds, store, timestamp)
    metrics = build_metrics_from_state(run_name, state, latency_seconds)
    report_path = store.root / "benchmark_report.md"
    existing_order, existing_rows = _load_benchmark_ledger(report_path)
    if run_name not in existing_order:
        existing_order.append(run_name)
    existing_rows[run_name] = metrics
    report_markdown = render_benchmark_report(existing_order, existing_rows)
    store.write_text("benchmark_report.md", report_markdown)
    store.write_text(f"benchmark/{run_name}-{_slugify(query)}-{timestamp}.md", report_markdown)
    console.print(f"Saved trace to reports/traces/{run_name}-{_slugify(query)}-{timestamp}.json")
    console.print(f"Saved benchmark report to reports/benchmark_report.md and reports/benchmark/{run_name}-{_slugify(query)}-{timestamp}.md")


def _write_trace_artifact(
    run_name: str,
    query: str,
    state: ResearchState,
    latency_seconds: float,
    store: LocalArtifactStore,
    timestamp: str,
) -> None:
    slug = _slugify(query)
    trace_payload = {
        "run_name": run_name,
        "query": query,
        "latency_seconds": latency_seconds,
        "route_history": state.route_history,
        "errors": state.errors,
        "research_notes": state.research_notes,
        "analysis_notes": state.analysis_notes,
        "final_answer": state.final_answer,
        "sources": [source.model_dump() for source in state.sources],
        "trace": state.trace,
        "agent_results": [result.model_dump() for result in state.agent_results],
    }
    trace_json = render_json_trace(trace_payload)
    store.write_text(f"traces/{run_name}-{slug}-{timestamp}.json", trace_json)
    console.print(f"Saved trace to reports/traces/{run_name}-{slug}-{timestamp}.json")


def _load_benchmark_ledger(report_path: Path) -> tuple[list[str], dict[str, BenchmarkMetrics | None]]:
    if not report_path.exists():
        return [], {}
    run_order, metrics_by_run = parse_benchmark_report(report_path.read_text(encoding="utf-8"))
    return run_order, metrics_by_run


def _merge_run_order(existing_order: list[str], planned_order: list[str]) -> list[str]:
    merged = list(planned_order)
    for run_name in existing_order:
        if run_name not in merged:
            merged.append(run_name)
    return merged


def _write_benchmark_report(
    store: LocalArtifactStore,
    run_order: list[str],
    metrics_by_run: dict[str, BenchmarkMetrics | None],
) -> None:
    report_markdown = render_benchmark_report(run_order, metrics_by_run)
    store.write_text("benchmark_report.md", report_markdown)


def _summarize_single_agent_metrics(metrics: list[BenchmarkMetrics]) -> BenchmarkMetrics:
    avg_latency = mean(item.latency_seconds for item in metrics)
    avg_cost_values = [item.estimated_cost_usd for item in metrics if item.estimated_cost_usd is not None]
    avg_quality_values = [item.quality_score for item in metrics if item.quality_score is not None]
    avg_citation_values = [item.citation_coverage for item in metrics if item.citation_coverage is not None]
    avg_error_values = [item.error_rate for item in metrics if item.error_rate is not None]
    average_cost = mean(avg_cost_values) if avg_cost_values else None
    average_quality = mean(avg_quality_values) if avg_quality_values else None
    average_citation = mean(avg_citation_values) if avg_citation_values else None
    average_error = mean(avg_error_values) if avg_error_values else None
    average_tokens = round((average_cost or 0.0) / 0.0000025) if average_cost is not None else None
    source_count = _extract_source_count(metrics)
    notes_parts = [f"queries={len(metrics)}"]
    if source_count is not None:
        notes_parts.append(f"sources={source_count}")
    if average_tokens is not None:
        notes_parts.append(f"tokens≈{average_tokens}")
    return BenchmarkMetrics(
        run_name="baseline",
        latency_seconds=avg_latency,
        estimated_cost_usd=average_cost,
        quality_score=average_quality,
        citation_coverage=average_citation,
        error_rate=average_error,
        notes="; ".join(notes_parts),
    )


def _extract_source_count(metrics: list[BenchmarkMetrics]) -> int | None:
    for item in metrics:
        match = re.search(r"sources=(\d+)", item.notes)
        if match:
            return int(match.group(1))
    return None


def _load_benchmark_queries(config_path: Path) -> list[str]:
    if not config_path.exists():
        raise typer.BadParameter(f"Config file not found: {config_path}")
    config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    benchmark_section = config.get("benchmark", {})
    queries = benchmark_section.get("queries", []) if isinstance(benchmark_section, dict) else []
    if not isinstance(queries, list) or not all(isinstance(query, str) and query.strip() for query in queries):
        raise typer.BadParameter("benchmark.queries must be a non-empty list of strings")
    return [query.strip() for query in queries]


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "query"


if __name__ == "__main__":
    app()
