"""Writer agent implementation."""

from __future__ import annotations

import logging
import re

from multi_agent_research_lab.agents.base import BaseAgent
from multi_agent_research_lab.core.schemas import AgentName, AgentResult
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.services.llm_client import LLMClient


logger = logging.getLogger(__name__)


class WriterAgent(BaseAgent):
    """Produces final answer from research and analysis notes."""

    name = "writer"

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.llm_client = llm_client or LLMClient()

    def run(self, state: ResearchState) -> ResearchState:
        """Populate `state.final_answer`."""

        query = state.request.query.strip()
        source_block = self._format_sources(state)
        user_prompt = (
            f"Query: {query}\n"
            f"Audience: {state.request.audience}\n\n"
            f"Research notes:\n{state.research_notes or 'No research notes available.'}\n\n"
            f"Analysis notes:\n{state.analysis_notes or 'No analysis notes available.'}\n\n"
            f"Sources:\n{source_block or '- No sources available.'}\n\n"
            "Write a clear, direct answer with inline citations like [1], [2] and a short references section if sources exist."
        )
        response = self.llm_client.complete(
            "You are the writer agent. Synthesize a crisp final answer with citations and source references.",
            user_prompt,
        )
        answer = response.content.strip() or self._fallback_answer(state)
        if state.sources and ("References:" not in answer or not self._has_inline_citation(answer)):
            answer = f"{answer}\n\nReferences:\n{self._reference_block(state)}"
        state.final_answer = answer
        state.agent_results.append(
            AgentResult(
                agent=AgentName.WRITER,
                content=state.final_answer,
                metadata={"source_count": len(state.sources)},
            )
        )
        state.add_trace_event("writer.run", {"query": query, "source_count": len(state.sources)})
        logger.info("Writer produced final answer")
        return state

    def _format_sources(self, state: ResearchState) -> str:
        lines = []
        for index, source in enumerate(state.sources, start=1):
            lines.append(f"- [{index}] {source.title} | {source.url or 'n/a'} | {source.snippet}")
        return "\n".join(lines)

    def _reference_block(self, state: ResearchState) -> str:
        lines = []
        for index, source in enumerate(state.sources, start=1):
            label = source.url or source.title
            lines.append(f"[{index}] {label}")
        return "\n".join(lines)

    def _has_inline_citation(self, text: str) -> bool:
        return bool(re.search(r"\[\d+\]", text))

    def _fallback_answer(self, state: ResearchState) -> str:
        lines = [f"Answer to {state.request.query}", ""]
        if state.analysis_notes:
            lines.append(state.analysis_notes.splitlines()[0])
        else:
            lines.append("The answer is based on the available research summary.")
        if state.sources:
            lines.extend(["", "References:", self._reference_block(state)])
        return "\n".join(lines)
