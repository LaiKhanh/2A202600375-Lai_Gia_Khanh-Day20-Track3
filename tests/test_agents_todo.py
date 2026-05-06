from multi_agent_research_lab.agents import SupervisorAgent, WriterAgent
from multi_agent_research_lab.core.schemas import SourceDocument
from multi_agent_research_lab.graph.workflow import MultiAgentWorkflow
from multi_agent_research_lab.core.schemas import ResearchQuery
from multi_agent_research_lab.core.state import ResearchState


def test_supervisor_routes_to_researcher_first() -> None:
    state = ResearchState(request=ResearchQuery(query="Explain multi-agent systems"))
    updated = SupervisorAgent().run(state)
    assert updated.route_history[-1] == "researcher"


def test_writer_adds_references_when_sources_exist() -> None:
    state = ResearchState(request=ResearchQuery(query="Explain multi-agent systems"))
    state.sources = [SourceDocument(title="Example source", url="https://example.com", snippet="Example evidence")]
    state.research_notes = "Research memo"
    state.analysis_notes = "Analysis memo"
    updated = WriterAgent().run(state)
    assert updated.final_answer is not None
    assert "References:" in updated.final_answer


def test_workflow_completes_with_local_fallback() -> None:
    state = ResearchState(request=ResearchQuery(query="Explain multi-agent systems"))
    result = MultiAgentWorkflow().run(state)
    assert result.final_answer is not None
    assert result.route_history
