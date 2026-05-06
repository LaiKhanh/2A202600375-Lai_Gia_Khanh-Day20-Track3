"""LLM client abstraction.

Production note: agents should depend on this interface instead of importing an SDK directly.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from textwrap import shorten
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from multi_agent_research_lab.core.config import get_settings
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LLMResponse:
    content: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None


class LLMClient:
    """Provider-agnostic LLM client skeleton."""

    def complete(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        """Return a model completion.

        The client prefers Gemini when `GEMINI_API_KEY` is set, falls back to OpenAI
        when `OPENAI_API_KEY` is set, and otherwise returns a deterministic local
        synthesis so the rest of the workflow remains testable offline.
        """

        settings = get_settings()
        if self._should_use_remote_services() and settings.gemini_api_key:
            try:
                return self._complete_gemini(
                    settings.gemini_api_key,
                    settings.gemini_model,
                    system_prompt,
                    user_prompt,
                    settings.timeout_seconds,
                )
            except (HTTPError, URLError, TimeoutError, OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
                logger.warning("Gemini completion failed, falling back locally: %s", exc)
        if self._should_use_remote_services() and settings.openai_api_key:
            try:
                return self._complete_openai(
                    settings.openai_api_key,
                    settings.openai_model,
                    system_prompt,
                    user_prompt,
                    settings.timeout_seconds,
                )
            except (HTTPError, URLError, TimeoutError, OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
                logger.warning("OpenAI completion failed, falling back locally: %s", exc)
        return self._local_completion(system_prompt, user_prompt)

    def _complete_gemini(
        self,
        api_key: str,
        model: str,
        system_prompt: str,
        user_prompt: str,
        timeout_seconds: int,
    ) -> LLMResponse:
        payload: dict[str, Any] = {
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 1024},
        }
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        request = Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=timeout_seconds) as response:
            body = json.loads(response.read().decode("utf-8"))
        content = self._extract_gemini_content(body)
        usage = body.get("usageMetadata", {}) if isinstance(body, dict) else {}
        return LLMResponse(
            content=content,
            input_tokens=usage.get("promptTokenCount"),
            output_tokens=usage.get("candidatesTokenCount"),
        )

    def _complete_openai(
        self,
        api_key: str,
        model: str,
        system_prompt: str,
        user_prompt: str,
        timeout_seconds: int,
    ) -> LLMResponse:
        payload: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
        }
        request = Request(
            "https://api.openai.com/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
            method="POST",
        )
        with urlopen(request, timeout=timeout_seconds) as response:
            body = json.loads(response.read().decode("utf-8"))
        choices = body.get("choices", []) if isinstance(body, dict) else []
        message = choices[0].get("message", {}) if choices else {}
        content = str(message.get("content", "")).strip()
        usage = body.get("usage", {}) if isinstance(body, dict) else {}
        return LLMResponse(
            content=content,
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
        )

    def _local_completion(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        role = system_prompt.lower()
        query = self._extract_field(user_prompt, ["Query", "Research query", "Question"]) or "the request"
        source_lines = self._extract_block(user_prompt, "Sources")
        research_notes = self._extract_block(user_prompt, "Research notes")
        analysis_notes = self._extract_block(user_prompt, "Analysis notes")
        final_answer = self._extract_block(user_prompt, "Final answer")

        if "researcher" in role:
            content = self._fallback_researcher(query, source_lines)
        elif "analyst" in role:
            content = self._fallback_analyst(query, research_notes, source_lines)
        elif "writer" in role:
            content = self._fallback_writer(query, analysis_notes or research_notes, source_lines)
        elif "critic" in role:
            content = self._fallback_critic(query, final_answer, source_lines)
        else:
            content = self._fallback_general(query, user_prompt)
        return LLMResponse(content=content)

    def _should_use_remote_services(self) -> bool:
        settings = get_settings()
        return "PYTEST_CURRENT_TEST" not in os.environ and settings.app_env.lower() != "local"

    def _extract_gemini_content(self, body: dict[str, Any]) -> str:
        candidates = body.get("candidates", []) if isinstance(body, dict) else []
        if not candidates:
            return ""
        content = candidates[0].get("content", {}) if isinstance(candidates[0], dict) else {}
        parts = content.get("parts", []) if isinstance(content, dict) else []
        texts = [str(part.get("text", "")).strip() for part in parts if isinstance(part, dict) and part.get("text")]
        return "\n".join(texts).strip()

    def _extract_field(self, prompt: str, labels: list[str]) -> str:
        lowered_labels = [f"{label.lower()}:" for label in labels]
        for line in prompt.splitlines():
            stripped = line.strip()
            lowered = stripped.lower()
            for label in lowered_labels:
                if lowered.startswith(label):
                    return stripped.split(":", 1)[1].strip()
        return ""

    def _extract_block(self, prompt: str, label: str) -> list[str]:
        lines = prompt.splitlines()
        collecting = False
        block: list[str] = []
        target = f"{label.lower()}:"
        for raw_line in lines:
            stripped = raw_line.strip()
            lowered = stripped.lower()
            if collecting:
                if not stripped:
                    break
                if lowered.endswith(":") and not lowered.startswith("["):
                    break
                block.append(stripped)
            elif lowered.startswith(target):
                collecting = True
                remainder = stripped.split(":", 1)[1].strip()
                if remainder:
                    block.append(remainder)
        return block

    def _split_source_line(self, line: str) -> tuple[str, str]:
        parts = [part.strip() for part in line.split("|")]
        title = parts[0] if parts else line
        snippet = parts[-1] if len(parts) > 1 else line
        return title.lstrip("-1234567890. "), snippet

    def _fallback_researcher(self, query: str, source_lines: list[str]) -> str:
        lines = [f"Research memo for: {query}", "", "Key sources:"]
        if source_lines:
            for index, source_line in enumerate(source_lines[:5], start=1):
                title, snippet = self._split_source_line(source_line)
                lines.append(f"- [{index}] {title}: {shorten(snippet, width=140, placeholder='...')}")
        else:
            lines.append("- No external sources were available, so this memo is synthesized from the query.")
        lines.extend([
            "",
            "Synthesis:",
            f"- The request focuses on {query} and benefits from evidence-backed comparison.",
            "- Prioritize direct sources, clear claims, and any trade-offs or guardrails mentioned in the evidence.",
        ])
        return "\n".join(lines)

    def _fallback_analyst(self, query: str, research_notes: list[str], source_lines: list[str]) -> str:
        lines = [f"Analysis for: {query}", "", "Key claims:"]
        if research_notes:
            for note in research_notes[:4]:
                lines.append(f"- {shorten(note, width=140, placeholder='...')}")
        else:
            lines.append("- Research notes are empty, so the analysis is limited to the source summary.")
        lines.extend([
            "",
            "Viewpoints:",
            f"- The evidence suggests {query} should be evaluated by usefulness, reliability, and implementation cost.",
            "- Stronger sources are those that name concrete mechanisms, constraints, and measurable outcomes.",
            "",
            "Evidence gaps:",
        ])
        if source_lines:
            for source_line in source_lines[:3]:
                title, snippet = self._split_source_line(source_line)
                lines.append(f"- {title}: {shorten(snippet, width=120, placeholder='...')}")
        else:
            lines.append("- No source list was provided, so the analysis cannot verify coverage.")
        return "\n".join(lines)

    def _fallback_writer(self, query: str, analysis_notes: list[str], source_lines: list[str]) -> str:
        lines = [f"Answer to: {query}", ""]
        if analysis_notes:
            lines.append(shorten(" ".join(analysis_notes[:3]), width=280, placeholder="..."))
        else:
            lines.append(f"A concise response to {query} should combine evidence, trade-offs, and practical guidance.")
        if source_lines:
            lines.extend(["", "References:"])
            for index, source_line in enumerate(source_lines[:5], start=1):
                title, _snippet = self._split_source_line(source_line)
                lines.append(f"- [{index}] {title}")
        return "\n".join(lines)

    def _fallback_critic(self, query: str, final_answer: list[str], source_lines: list[str]) -> str:
        if not final_answer:
            return f"Critic review for {query}: final answer is missing, so the workflow should keep iterating."
        answer_text = " ".join(final_answer)
        has_citation = "[" in answer_text and "]" in answer_text
        source_count = len(source_lines)
        lines = [f"Critic review for: {query}", ""]
        if has_citation or not source_count:
            lines.append("- No major issues detected in the current answer.")
        else:
            lines.append("- The answer should cite the gathered sources more explicitly.")
        lines.append("- Check for unsupported claims and keep the conclusion aligned with the evidence set.")
        return "\n".join(lines)

    def _fallback_general(self, query: str, user_prompt: str) -> str:
        return f"Summary for {query}: {shorten(user_prompt.replace(chr(10), ' '), width=280, placeholder='...')}"
