"""Supervisor / router implementation."""

from __future__ import annotations

import logging

from multi_agent_research_lab.agents.base import BaseAgent
from multi_agent_research_lab.core.config import get_settings
from multi_agent_research_lab.core.schemas import AgentName
from multi_agent_research_lab.core.state import ResearchState


logger = logging.getLogger(__name__)


class SupervisorAgent(BaseAgent):
    """Decides which worker should run next and when to stop."""

    name = "supervisor"

    def __init__(self) -> None:
        self.settings = get_settings()

    def run(self, state: ResearchState) -> ResearchState:
        """Update `state.route_history` with the next route."""

        route = self._choose_route(state)
        state.record_route(route)
        state.add_trace_event(
            "supervisor.route",
            {
                "next": route,
                "iteration": state.iteration,
                "has_sources": bool(state.sources),
                "has_analysis": bool(state.analysis_notes),
                "has_final_answer": bool(state.final_answer),
                "errors": len(state.errors),
            },
        )
        logger.info("Supervisor selected route: %s", route)
        return state

    def _choose_route(self, state: ResearchState) -> str:
        if state.iteration >= self.settings.max_iterations:
            return "done"
        if not state.sources:
            return AgentName.RESEARCHER.value
        if not state.research_notes:
            return AgentName.RESEARCHER.value
        if not state.analysis_notes:
            return AgentName.ANALYST.value
        if not state.final_answer:
            return AgentName.WRITER.value
        last_route = self._last_worker_route(state)
        if state.errors and last_route == AgentName.WRITER.value:
            return AgentName.CRITIC.value
        if state.errors and last_route == AgentName.CRITIC.value:
            return AgentName.WRITER.value
        if not any(result.agent == AgentName.CRITIC for result in state.agent_results):
            return AgentName.CRITIC.value
        return "done"

    def _last_worker_route(self, state: ResearchState) -> str | None:
        for route in reversed(state.route_history):
            if route != "done":
                return route
        return None
