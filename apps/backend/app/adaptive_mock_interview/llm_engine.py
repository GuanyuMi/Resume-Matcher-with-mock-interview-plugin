"""LangGraph-based interview question generation engine."""

from __future__ import annotations

from typing import Any, TypedDict
from uuid import uuid4

from app.llm import complete_json

try:
    from langgraph.graph import END, StateGraph
except Exception:  # pragma: no cover - optional dependency fallback
    END = "__end__"
    StateGraph = None  # type: ignore[assignment]


class InterviewGraphState(TypedDict, total=False):
    context: dict[str, Any]
    attempts: list[dict[str, Any]]
    topic: str
    difficulty: int
    prompt_payload: dict[str, Any]
    question_payload: dict[str, Any]


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = value.strip()
        if not cleaned:
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(cleaned)
    return result


class MockInterviewLLMEngine:
    """Generates adaptive interview questions grounded in JD and resume context."""

    async def generate_question(
        self,
        *,
        context: dict[str, Any],
        attempts: list[dict[str, Any]],
        difficulty: int,
        language: str,
    ) -> dict[str, Any]:
        """Generate a multiple-choice question using LangGraph when available."""
        if StateGraph is None:
            state = {
                "context": context,
                "attempts": attempts,
                "difficulty": difficulty,
                "topic": self._select_topic(context, attempts),
            }
            drafted = await self._draft_question_payload(state, language=language)
            return self._normalize_question(
                drafted.get("question_payload", {}),
                context=context,
                difficulty=difficulty,
            )

        graph = StateGraph(InterviewGraphState)
        graph.add_node("prepare", self._prepare_state)
        graph.add_node("draft", lambda state: self._draft_question_payload(state, language=language))
        graph.add_node("validate", self._validate_state)
        graph.set_entry_point("prepare")
        graph.add_edge("prepare", "draft")
        graph.add_edge("draft", "validate")
        graph.add_edge("validate", END)

        compiled = graph.compile()
        result = await compiled.ainvoke(
            {
                "context": context,
                "attempts": attempts,
                "difficulty": difficulty,
            }
        )
        payload = result.get("question_payload", {})
        return self._normalize_question(payload, context=context, difficulty=difficulty)

    def _select_topic(self, context: dict[str, Any], attempts: list[dict[str, Any]]) -> str:
        focus_areas = list(context.get("focus_areas", []))
        if not focus_areas:
            focus_areas = list(context.get("core_requirements", []))
        if not focus_areas:
            focus_areas = ["role alignment"]

        scores: dict[str, tuple[int, int]] = {}
        for index, topic in enumerate(focus_areas):
            scores[topic] = (0, -index)

        for attempt in attempts:
            topic = str(attempt.get("topic", "")).strip()
            if topic not in scores:
                continue
            score, original_index = scores[topic]
            delta = -2 if attempt.get("correct") else 3
            scores[topic] = (score + delta, original_index)

        ranked = sorted(scores.items(), key=lambda item: (-item[1][0], item[1][1]))
        return ranked[0][0]

    def _prepare_state(self, state: InterviewGraphState) -> InterviewGraphState:
        topic = self._select_topic(state["context"], state.get("attempts", []))
        return {
            **state,
            "topic": topic,
            "prompt_payload": {
                "topic": topic,
                "difficulty": state["difficulty"],
                "core_requirements": state["context"].get("core_requirements", []),
                "matched_skills": state["context"].get("matched_skills", []),
                "missing_skills": state["context"].get("missing_skills", []),
                "resume_highlights": state["context"].get("resume_highlights", []),
                "responsibilities": state["context"].get("responsibilities", []),
            },
        }

    async def _draft_question_payload(
        self,
        state: InterviewGraphState,
        *,
        language: str,
    ) -> InterviewGraphState:
        prompt_payload = state.get("prompt_payload") or {
            "topic": state.get("topic") or self._select_topic(state["context"], state.get("attempts", [])),
            "difficulty": state["difficulty"],
            "core_requirements": state["context"].get("core_requirements", []),
            "matched_skills": state["context"].get("matched_skills", []),
            "missing_skills": state["context"].get("missing_skills", []),
            "resume_highlights": state["context"].get("resume_highlights", []),
            "responsibilities": state["context"].get("responsibilities", []),
        }

        prompt = f"""
Generate one multiple-choice interview question as strict JSON for a mock interview.

Output language: {language}
Target topic: {prompt_payload["topic"]}
Target difficulty: {prompt_payload["difficulty"]} (1=easy, 5=hard)
Core JD requirements: {prompt_payload["core_requirements"]}
JD responsibilities: {prompt_payload["responsibilities"]}
Matched skills from resume: {prompt_payload["matched_skills"]}
Missing or weak skills from resume: {prompt_payload["missing_skills"]}
Resume highlights: {prompt_payload["resume_highlights"]}

Rules:
- Ask a technical interview question tightly grounded in the JD and the candidate's resume.
- Make the correct answer objectively best among exactly 4 options.
- Keep distractors plausible but clearly weaker, irrelevant, or risky.
- Avoid asking about technologies not present in the JD context unless needed as a distractor.
- The explanation should mention why the correct option is strongest in this hiring context.
- answer_summary should be a short recruiter-friendly ideal answer.

Return JSON with:
{{
  "topic": "string",
  "difficulty": 1,
  "stem": "string",
  "options": [
    {{"option_id": "A", "text": "string"}},
    {{"option_id": "B", "text": "string"}},
    {{"option_id": "C", "text": "string"}},
    {{"option_id": "D", "text": "string"}}
  ],
  "correct_option_id": "A|B|C|D",
  "explanation": "string",
  "answer_summary": "string",
  "source_requirement": "string"
}}
"""

        try:
            payload = await complete_json(
                prompt=prompt,
                system_prompt="You are a precise technical interviewer. Output only valid JSON.",
                max_tokens=1400,
            )
        except Exception:
            payload = self._fallback_question(
                context=state["context"],
                topic=str(prompt_payload["topic"]),
                difficulty=int(prompt_payload["difficulty"]),
            )

        return {**state, "question_payload": payload}

    def _validate_state(self, state: InterviewGraphState) -> InterviewGraphState:
        payload = state.get("question_payload") or {}
        normalized = self._normalize_question(payload, context=state["context"], difficulty=state["difficulty"])
        return {**state, "question_payload": normalized}

    def _normalize_question(
        self,
        payload: dict[str, Any],
        *,
        context: dict[str, Any],
        difficulty: int,
    ) -> dict[str, Any]:
        options = payload.get("options", [])
        normalized_options: list[dict[str, str]] = []
        for fallback_id, option in zip(("A", "B", "C", "D"), options[:4], strict=False):
            if isinstance(option, dict):
                option_id = str(option.get("option_id") or fallback_id).strip() or fallback_id
                text = str(option.get("text") or "").strip()
            else:
                option_id = fallback_id
                text = str(option).strip()
            if text:
                normalized_options.append({"option_id": option_id, "text": text})

        if len(normalized_options) < 4:
            fallback = self._fallback_question(
                context=context,
                topic=str(payload.get("topic") or self._select_topic(context, [])),
                difficulty=difficulty,
            )
            normalized_options = fallback["options"]
            payload = {**fallback, **payload}

        option_ids = [option["option_id"] for option in normalized_options]
        correct_option_id = str(payload.get("correct_option_id") or option_ids[0]).strip()
        if correct_option_id not in option_ids:
            correct_option_id = option_ids[0]

        return {
            "question_id": str(payload.get("question_id") or uuid4()),
            "topic": str(payload.get("topic") or self._select_topic(context, [])).strip(),
            "difficulty": max(1, min(5, int(payload.get("difficulty", difficulty)))),
            "stem": str(payload.get("stem") or "Which option best answers this interview prompt?").strip(),
            "options": normalized_options[:4],
            "correct_option_id": correct_option_id,
            "explanation": str(payload.get("explanation") or "This option best matches the JD and resume evidence.").strip(),
            "answer_summary": str(payload.get("answer_summary") or "Connect the requirement to a concrete result from the resume.").strip(),
            "source_requirement": str(
                payload.get("source_requirement")
                or (context.get("core_requirements", [payload.get("topic", "")]) or [""])[0]
            ).strip(),
        }

    def _fallback_question(
        self,
        *,
        context: dict[str, Any],
        topic: str,
        difficulty: int,
    ) -> dict[str, Any]:
        topic_name = topic or "role alignment"
        source_requirement = (
            context.get("missing_skills", [])
            or context.get("core_requirements", [])
            or [topic_name]
        )[0]
        highlights = _dedupe([str(item) for item in context.get("resume_highlights", [])])
        best_highlight = highlights[0] if highlights else "a concrete project or work example from the resume"
        return {
            "question_id": str(uuid4()),
            "topic": topic_name,
            "difficulty": max(1, min(5, difficulty)),
            "stem": f"For the JD requirement '{source_requirement}', which answer would be strongest in a mock interview?",
            "options": [
                {
                    "option_id": "A",
                    "text": f"Explain how {best_highlight} demonstrates {topic_name}, including architecture decisions and measurable outcomes.",
                },
                {
                    "option_id": "B",
                    "text": f"State that you are generally familiar with {topic_name} but avoid giving a concrete example.",
                },
                {
                    "option_id": "C",
                    "text": "Shift the answer to a loosely related tool that is not central to the JD requirement.",
                },
                {
                    "option_id": "D",
                    "text": "Claim production ownership of a system that is not supported by the resume evidence.",
                },
            ],
            "correct_option_id": "A",
            "explanation": "The strongest answer anchors the requirement in a truthful, specific example and shows measurable impact.",
            "answer_summary": f"Connect {topic_name} to {best_highlight}, then explain decisions, trade-offs, and outcomes.",
            "source_requirement": source_requirement,
        }
