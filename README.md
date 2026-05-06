# Multi-Agent Research Lab

This project demonstrates a research assistant built from multiple agents: a supervisor routes work to a researcher, analyst, writer, and optional critic, while the CLI writes trace JSON and benchmark reports to disk.

## Agent Architecture

```text
User Query
   |
   v
Supervisor / Router
   |------> Researcher Agent  -> research_notes + sources
   |------> Analyst Agent     -> analysis_notes
   |------> Writer Agent      -> final_answer
   |------> Critic Agent      -> review / issue flags
   |
   v
JSON Trace + Benchmark Report
```

### Roles

- Supervisor: decides the next step and stops the loop when the answer is ready.
- Researcher: gathers sources and produces research notes.
- Analyst: extracts claims, compares viewpoints, and highlights weak evidence.
- Writer: synthesizes the final answer with citations or source references.
- Critic: checks citation coverage and obvious hallucination risks.

## What Gets Generated

When you run the CLI, the project writes artifacts under `reports/`:

- `reports/traces/*.json` for simple JSON traces.
- `reports/benchmark_report.md` for the latest benchmark ledger.
- `reports/benchmark/*.md` for per-run copies of the report.

The benchmark ledger is updated after each query run. It keeps rows for the baseline summary, each baseline query, and each multi-agent query.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -e "[dev]"
```

Add your API keys to `.env` if you want remote model or search calls.

```bash
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-2.5-flash
TAVILY_API_KEY=...
APP_ENV=local
```

`APP_ENV=local` uses deterministic local fallbacks, which is useful for offline runs and tests.

## Run The App

### Single query baseline

```bash
python -m multi_agent_research_lab.cli baseline \
  --query "Research GraphRAG state-of-the-art and write a 500-word summary"
```

This runs a single-agent baseline, prints the answer, and writes a trace JSON plus benchmark entry.

### Multi-agent workflow

```bash
python -m multi_agent_research_lab.cli multi-agent \
  --query "Research GraphRAG state-of-the-art and write a 500-word summary"
```

This runs the full supervisor-managed workflow and writes a JSON trace plus benchmark entry.

### Benchmark all lab queries

```bash
python -m multi_agent_research_lab.cli benchmark --config configs/lab_default.yaml
```

This reads the query list from `configs/lab_default.yaml`, runs the baseline and multi-agent workflow for each query, and updates `reports/benchmark_report.md` after every run.

## How To Check Outputs

After a run, inspect the following:

- Open the JSON trace file in `reports/traces/` to see route history, notes, sources, and final output.
- Open `reports/benchmark_report.md` to see the current benchmark ledger.
- Compare the `baseline` row with the `multi-agent q*` rows to judge latency, cost, quality, citation coverage, and error rate.

## Benchmark Report Format

The report uses a table like this:

| Run | Latency (s) | Cost (USD) | Quality | Citation Cov. | Error Rate | Notes |
|---|---:|---:|---:|---:|---:|---|
| baseline | 0.00 | 0.0002 | 5.5 | 0.25 | 0.00 | queries=3; sources=4; tokens≈80 |
| baseline q1 | 0.00 | 0.0002 | 5.5 | 0.25 | 0.00 | sources=4; tokens≈87 |
| baseline q2 | 0.00 | 0.0002 | 5.5 | 0.25 | 0.00 | sources=4; tokens≈90 |
| baseline q3 | 0.00 | 0.0002 | 5.5 | 0.25 | 0.00 | sources=4; tokens≈84 |
| multi-agent q1 | 0.01 | 0.0008 | 10.0 | 1.00 | 0.00 | sources=4; tokens≈314 |
| multi-agent q2 | 0.01 | 0.0008 | 10.0 | 1.00 | 0.00 | sources=4; tokens≈319 |
| multi-agent q3 | 0.01 | 0.0007 | 10.0 | 1.00 | 0.00 | sources=4; tokens≈288 |

## Failure Mode

A common failure mode is that the workflow stops too early or loops between writer and critic when evidence is thin or citations are incomplete. The fix is to keep the max-iterations guard, require explicit source-backed citations before finalizing, and fall back to the deterministic local writer/critic path whenever a provider call is unavailable or fails.

## Project Structure

```text
.
├── src/multi_agent_research_lab/
│   ├── agents/              # Supervisor, researcher, analyst, writer, critic
│   ├── core/                # Config, state, schemas, errors
│   ├── graph/               # Workflow orchestration
│   ├── services/            # LLM, search, storage clients
│   ├── evaluation/          # Benchmark and report helpers
│   ├── observability/       # Tracing and logging helpers
│   └── cli.py               # CLI entrypoint
├── configs/                 # YAML config files for runs
├── reports/                 # JSON traces and markdown benchmark reports
├── tests/                   # Unit tests
└── pyproject.toml           # Project config
```

## References

- Anthropic: Building effective agents — https://www.anthropic.com/engineering/building-effective-agents
- OpenAI Agents SDK orchestration/handoffs — https://developers.openai.com/api/docs/guides/agents/orchestration
- LangGraph concepts — https://langchain-ai.github.io/langgraph/concepts/
