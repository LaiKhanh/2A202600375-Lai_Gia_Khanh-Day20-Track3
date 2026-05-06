"""Workflow orchestration for the multi-agent research lab."""

from __future__ import annotations

import logging

from multi_agent_research_lab.agents.analyst import AnalystAgent
from multi_agent_research_lab.agents.critic import CriticAgent
from multi_agent_research_lab.agents.researcher import ResearcherAgent
from multi_agent_research_lab.agents.supervisor import SupervisorAgent
from multi_agent_research_lab.agents.writer import WriterAgent
from multi_agent_research_lab.core.config import get_settings
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.observability.tracing import trace_span


logger = logging.getLogger(__name__)


class MultiAgentWorkflow:
    """Builds and runs the multi-agent graph.

    Keep orchestration here; keep agent internals in `agents/`.
    """

    def __init__(self) -> None:
        self.supervisor = SupervisorAgent()
        self.researcher = ResearcherAgent()
        self.analyst = AnalystAgent()
        self.writer = WriterAgent()
        self.critic = CriticAgent()
        self._plan: dict[str, object] | None = None

    def build(self) -> object:
        """Create a simple routing plan for the workflow."""

        self._plan = {
            "nodes": ["supervisor", "researcher", "analyst", "writer", "critic"],
            "edges": {
                "supervisor": ["researcher", "analyst", "writer", "critic", "done"],
                "researcher": ["supervisor"],
                "analyst": ["supervisor"],
                "writer": ["supervisor"],
                "critic": ["supervisor"],
            },
            "stop_condition": "supervisor returns done or max_iterations is reached",
        }
        return self._plan

    def run(self, state: ResearchState) -> ResearchState:
        """Execute the workflow and return the final state."""

        self.build()
        settings = get_settings()
        while True:
            if state.iteration >= settings.max_iterations:
                state.errors.append("Stopped because the workflow reached the iteration limit.")
                break
            with trace_span("workflow.supervisor", {"iteration": state.iteration}) as span:
                state = self.supervisor.run(state)
            state.add_trace_event("workflow.supervisor", dict(span))
            route = state.route_history[-1]
            if route == "done":
                break
            with trace_span("workflow.agent", {"route": route}) as span:
                state = self._dispatch(route, state)
            state.add_trace_event("workflow.agent", dict(span))
        return state

    def _dispatch(self, route: str, state: ResearchState) -> ResearchState:
        if route == "researcher":
            return self.researcher.run(state)
        if route == "analyst":
            return self.analyst.run(state)
        if route == "writer":
            return self.writer.run(state)
        if route == "critic":
            return self.critic.run(state)
        raise ValueError(f"Unknown workflow route: {route}")
