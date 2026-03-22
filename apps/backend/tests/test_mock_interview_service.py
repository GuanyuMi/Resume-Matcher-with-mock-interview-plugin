import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from app.adaptive_mock_interview.database import SQLiteInterviewStore
from app.adaptive_mock_interview.predictor import DifficultyPredictor
from app.adaptive_mock_interview.service import AdaptiveMockInterviewService


class TestAdaptiveMockInterviewService(unittest.IsolatedAsyncioTestCase):
    async def test_start_session_and_answer_flow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = SQLiteInterviewStore(Path(tmp_dir) / "mock_interview.sqlite3")
            engine = AsyncMock()
            engine.generate_question = AsyncMock(
                side_effect=[
                    {
                        "question_id": "q1",
                        "topic": "Python",
                        "difficulty": 2,
                        "stem": "Which answer is strongest?",
                        "options": [
                            {"option_id": "A", "text": "Use a concrete Python example."},
                            {"option_id": "B", "text": "Stay generic."},
                            {"option_id": "C", "text": "Discuss an unrelated tool."},
                            {"option_id": "D", "text": "Claim unsupported ownership."},
                        ],
                        "correct_option_id": "A",
                        "explanation": "Concrete, truthful examples are strongest.",
                        "answer_summary": "Explain one Python project with outcomes.",
                        "source_requirement": "Python",
                    },
                    {
                        "question_id": "q2",
                        "topic": "FastAPI",
                        "difficulty": 3,
                        "stem": "How would you discuss API design?",
                        "options": [
                            {"option_id": "A", "text": "Tie FastAPI decisions to measurable outcomes."},
                            {"option_id": "B", "text": "Only list the framework name."},
                            {"option_id": "C", "text": "Avoid system design detail."},
                            {"option_id": "D", "text": "Invent production ownership."},
                        ],
                        "correct_option_id": "A",
                        "explanation": "Best answer explains design choices and impact.",
                        "answer_summary": "Describe API trade-offs, observability, and impact.",
                        "source_requirement": "FastAPI",
                    },
                ]
            )

            service = AdaptiveMockInterviewService(
                store=store,
                engine=engine,
                predictor=DifficultyPredictor(),
            )

            mock_db = MagicMock()
            mock_db.get_resume.return_value = {
                "resume_id": "resume_1",
                "processed_data": {
                    "summary": "Backend engineer focused on Python APIs.",
                    "workExperience": [
                        {
                            "title": "Backend Engineer",
                            "company": "Acme",
                            "years": "2022 - Present",
                            "description": ["Built Python services with FastAPI and PostgreSQL."],
                        }
                    ],
                    "personalProjects": [],
                    "additional": {"technicalSkills": ["Python", "FastAPI", "PostgreSQL"]},
                },
            }
            mock_db.get_job.return_value = {
                "job_id": "job_1",
                "content": "Need Python and FastAPI experience for API platform work.",
            }

            with (
                patch("app.adaptive_mock_interview.service.db", mock_db),
                patch(
                    "app.adaptive_mock_interview.service.extract_job_keywords",
                    AsyncMock(
                        return_value={
                            "required_skills": ["Python", "FastAPI"],
                            "preferred_skills": ["Docker"],
                            "keywords": ["API platform"],
                            "key_responsibilities": ["Build backend services"],
                        }
                    ),
                ),
            ):
                created = await service.start_session(
                    resume_id="resume_1",
                    job_id="job_1",
                    language="en",
                    question_count=2,
                )

                self.assertEqual(created["current_question"]["question_id"], "q1")
                self.assertEqual(created["stats"]["total_answered"], 0)

                answered = await service.answer_question(
                    session_id=created["session_id"],
                    question_id="q1",
                    selected_option_id="A",
                    response_time_ms=30000,
                )

                self.assertTrue(answered["correct"])
                self.assertEqual(answered["next_question"]["question_id"], "q2")
                self.assertGreaterEqual(answered["stats"]["current_difficulty"], 2)
