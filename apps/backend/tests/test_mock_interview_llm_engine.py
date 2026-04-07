import unittest
from unittest.mock import AsyncMock, patch

from app.adaptive_mock_interview.llm_engine import MockInterviewLLMEngine


class TestMockInterviewLLMEngine(unittest.IsolatedAsyncioTestCase):
    async def test_generate_question_with_langgraph_returns_normalized_payload(self) -> None:
        engine = MockInterviewLLMEngine()
        context = {
            "core_requirements": ["Python", "FastAPI"],
            "matched_skills": ["Python"],
            "missing_skills": ["FastAPI"],
            "resume_highlights": ["Built Python APIs for internal tools."],
            "responsibilities": ["Build backend services"],
            "focus_areas": ["FastAPI"],
        }

        with patch(
            "app.adaptive_mock_interview.llm_engine.complete_json",
            AsyncMock(
                return_value={
                    "topic": "FastAPI",
                    "difficulty": 3,
                    "stem": "How would you describe your FastAPI experience?",
                    "options": [
                        {"option_id": "A", "text": "Tie FastAPI work to shipped outcomes."},
                        {"option_id": "B", "text": "Say you used APIs in general."},
                        {"option_id": "C", "text": "Discuss a different stack entirely."},
                        {"option_id": "D", "text": "Claim production work not on the resume."},
                    ],
                    "correct_option_id": "A",
                    "explanation": "Specific examples are strongest.",
                    "answer_summary": "Explain one FastAPI project with impact.",
                    "source_requirement": "FastAPI",
                }
            ),
        ):
            question = await engine.generate_question(
                context=context,
                attempts=[],
                difficulty=3,
                language="en",
            )

        self.assertEqual(question["topic"], "FastAPI")
        self.assertEqual(question["correct_option_id"], "A")
        self.assertEqual(len(question["options"]), 4)
        self.assertTrue(question["question_id"])
