"""Researcher agent implementation."""

from __future__ import annotations

import logging
from textwrap import shorten

from multi_agent_research_lab.agents.base import BaseAgent
from multi_agent_research_lab.core.schemas import AgentName, AgentResult
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.services.llm_client import LLMClient
from multi_agent_research_lab.services.search_client import SearchClient


logger = logging.getLogger(__name__)


class ResearcherAgent(BaseAgent):
    """Collects sources and creates concise research notes."""

    name = "researcher"

    def __init__(self, search_client: SearchClient | None = None, llm_client: LLMClient | None = None) -> None:
        self.search_client = search_client or SearchClient()
        self.llm_client = llm_client or LLMClient()

    def run(self, state: ResearchState) -> ResearchState:
        """Populate `state.sources` and `state.research_notes`."""

        query = state.request.query.strip()
        sources = self.search_client.search(query, max_results=state.request.max_sources)
        deduped_sources = self._dedupe_sources(sources, state.request.max_sources)
        state.sources = deduped_sources

        source_block = "\n".join(
            f"- [{index}] {source.title} | {source.url or 'n/a'} | {shorten(source.snippet, width=180, placeholder='...')}"
            for index, source in enumerate(deduped_sources, start=1)
        )
        user_prompt = (
            f"Query: {query}\n"
            f"Audience: {state.request.audience}\n"
            f"Max sources: {state.request.max_sources}\n\n"
            f"Sources:\n{source_block or '- No sources available.'}\n"
        )
        response = self.llm_client.complete(
            "You are the researcher agent. Gather evidence, highlight the strongest claims, and keep notes concise.",
            user_prompt,
        )
        state.research_notes = response.content.strip() or self._fallback_notes(query, deduped_sources)
        state.agent_results.append(
            AgentResult(
                agent=AgentName.RESEARCHER,
                content=state.research_notes,
                metadata={
                    "source_count": len(deduped_sources),
                    "titles": [source.title for source in deduped_sources],
                },
            )
        )
        state.add_trace_event(
            "researcher.run",
            {"query": query, "source_count": len(deduped_sources)},
        )
        logger.info("Researcher collected %s sources", len(deduped_sources))
        return state

    def _dedupe_sources(self, sources: list[object], max_sources: int) -> list[object]:
        deduped: list[object] = []
        seen: set[str] = set()
        for source in sources:
            url = getattr(source, "url", None)
            title = getattr(source, "title", "")
            signature = (url or title).strip().lower()
            if signature in seen:
                continue
            seen.add(signature)
            deduped.append(source)
            if len(deduped) >= max_sources:
                break
        return deduped

    def _fallback_notes(self, query: str, sources: list[object]) -> str:
        lines = [f"Research memo for {query}", "", "Evidence summary:"]
        if not sources:
            lines.append("- No external sources were returned, so the answer must rely on the query context.")
        else:
            for index, source in enumerate(sources, start=1):
                title = getattr(source, "title", f"Source {index}")
                snippet = getattr(source, "snippet", "")
                lines.append(f"- [{index}] {title}: {shorten(snippet, width=150, placeholder='...')}")
        lines.extend(
            [
                "",
                "Working conclusion:",
                "- Prefer claims that are directly supported by the strongest sources.",
                "- Flag ambiguous or weak evidence before the writer stage.",
            ]
        )
        return "\n".join(lines)
