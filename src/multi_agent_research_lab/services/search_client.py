"""Search client abstraction for ResearcherAgent."""

from __future__ import annotations

import json
import logging
import os
from textwrap import shorten
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from multi_agent_research_lab.core.config import get_settings
from multi_agent_research_lab.core.schemas import SourceDocument


logger = logging.getLogger(__name__)


class SearchClient:
    """Provider-agnostic search client skeleton."""

    def search(self, query: str, max_results: int = 5) -> list[SourceDocument]:
        """Search for documents relevant to a query.

        The client prefers Tavily when `TAVILY_API_KEY` is configured and falls back to a
        deterministic local mock so offline tests still have stable source documents.
        """

        query = query.strip()
        if not query:
            raise ValueError("Search query cannot be empty")

        settings = get_settings()
        if self._should_use_remote_services() and settings.tavily_api_key:
            try:
                results = self._search_tavily(settings.tavily_api_key, query, max_results)
                if results:
                    return results
            except (HTTPError, URLError, TimeoutError, OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
                logger.warning("Tavily search failed, falling back locally: %s", exc)

        return self._local_search(query, max_results)

    def _should_use_remote_services(self) -> bool:
        settings = get_settings()
        return "PYTEST_CURRENT_TEST" not in os.environ and settings.app_env.lower() != "local"

    def _search_tavily(self, api_key: str, query: str, max_results: int) -> list[SourceDocument]:
        payload: dict[str, Any] = {
            "api_key": api_key,
            "query": query,
            "max_results": max_results,
            "search_depth": "basic",
            "include_answer": False,
            "include_raw_content": False,
        }
        request = Request(
            "https://api.tavily.com/search",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        settings = get_settings()
        with urlopen(request, timeout=settings.timeout_seconds) as response:
            body = json.loads(response.read().decode("utf-8"))
        results: list[SourceDocument] = []
        for item in body.get("results", [])[:max_results]:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title", query)).strip() or query
            url = str(item.get("url", "")).strip() or None
            snippet = str(item.get("content", item.get("snippet", ""))).strip()
            if not snippet:
                snippet = title
            results.append(SourceDocument(title=title, url=url, snippet=snippet, metadata={"provider": "tavily"}))
        return results

    def _local_search(self, query: str, max_results: int) -> list[SourceDocument]:
        keywords = [word.strip(".,:;()[]{}") for word in query.split() if len(word.strip(".,:;()[]{}")) > 3]
        focus = ", ".join(keywords[:3]) if keywords else query
        templates = [
            (
                f"Overview of {query}",
                f"Background material for {query} with emphasis on {focus} and the main concepts involved.",
            ),
            (
                f"Trade-offs in {query}",
                f"A synthesized comparison of the benefits, constraints, and implementation trade-offs related to {query}.",
            ),
            (
                f"Guardrails for {query}",
                f"Practical guardrails for {query}, including verification, citations, and failure-mode analysis.",
            ),
            (
                f"Current patterns for {query}",
                f"Common patterns, evaluation considerations, and operating notes that help interpret {query} responsibly.",
            ),
        ]
        results: list[SourceDocument] = []
        for index, (title, snippet) in enumerate(templates[:max_results], start=1):
            results.append(
                SourceDocument(
                    title=title,
                    url=None,
                    snippet=shorten(snippet, width=220, placeholder="..."),
                    metadata={"provider": "local", "rank": index},
                )
            )
        return results
