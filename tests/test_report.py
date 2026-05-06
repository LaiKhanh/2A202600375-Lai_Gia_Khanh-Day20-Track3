from multi_agent_research_lab.core.schemas import BenchmarkMetrics
from multi_agent_research_lab.evaluation.report import render_benchmark_comparison_report, render_benchmark_report, render_markdown_report


def test_report_renders_markdown() -> None:
    report = render_markdown_report([BenchmarkMetrics(run_name="baseline", latency_seconds=1.23)])
    assert "Benchmark Report" in report
    assert "baseline" in report


def test_comparison_report_renders_both_modes() -> None:
    single = BenchmarkMetrics(run_name="single-agent", latency_seconds=1.0, quality_score=5.0)
    multi = BenchmarkMetrics(run_name="multi-agent", latency_seconds=1.5, quality_score=7.0)
    report = render_benchmark_comparison_report([("Example query", single, multi)])
    assert "Benchmark Comparison Report" in report
    assert "Example query" in report
    assert "Average single-agent latency" in report
    assert "Average multi-agent latency" in report


def test_benchmark_ledger_renders_placeholders() -> None:
    report = render_benchmark_report(
        ["baseline", "baseline q1", "baseline q2"],
        {"baseline": BenchmarkMetrics(run_name="baseline", latency_seconds=0.5, notes="sources=4; tokens≈90")},
    )
    assert "| baseline | 0.50 |" in report
    assert "| baseline q1 |  |  |  |  |  |  |" in report
    assert "## Failure Mode" in report
    assert "writer and critic" in report
