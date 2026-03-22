"""Service orchestration for adaptive mock interview sessions."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from fastapi import HTTPException

from app.adaptive_mock_interview.context import build_interview_context
from app.adaptive_mock_interview.database import SQLiteInterviewStore
from app.adaptive_mock_interview.llm_engine import MockInterviewLLMEngine
from app.adaptive_mock_interview.predictor import DifficultyPredictor
from app.config import settings
from app.database import db
from app.services.improver import extract_job_keywords


class AdaptiveMockInterviewService:
    """Coordinates context extraction, question generation, and adaptation."""

    def __init__(
        self,
        *,
        store: SQLiteInterviewStore | None = None,
        engine: MockInterviewLLMEngine | None = None,
        predictor: DifficultyPredictor | None = None,
    ) -> None:
        self.store = store or SQLiteInterviewStore(settings.mock_interview_db_path)
        self.engine = engine or MockInterviewLLMEngine()
        self.predictor = predictor or DifficultyPredictor(settings.mock_interview_decay_hours)

    def _resolve_job_for_resume(self, resume_id: str, explicit_job_id: str | None) -> dict[str, Any]:
        if explicit_job_id:
            job = db.get_job(explicit_job_id)
            if not job:
                raise HTTPException(status_code=404, detail="Job not found")
            return job

        resume = db.get_resume(resume_id)
        if not resume:
            raise HTTPException(status_code=404, detail="Resume not found")

        if resume.get("parent_id"):
            improvement = db.get_improvement_by_tailored_resume(resume_id)
            if improvement:
                job = db.get_job(improvement["job_id"])
                if job:
                    return job

        raise HTTPException(
            status_code=400,
            detail="Mock interview requires a job context. Please tailor the resume first or provide a job_id.",
        )

    @staticmethod
    def _initial_difficulty(context: dict[str, Any]) -> int:
        match_ratio = float(context.get("match_ratio", 0.0))
        missing_count = len(context.get("missing_skills", []))
        if match_ratio >= 0.7 and missing_count <= 2:
            return 3
        if match_ratio >= 0.4:
            return 2
        return 1

    @staticmethod
    def _public_question(question: dict[str, Any]) -> dict[str, Any]:
        return {
            "question_id": question["question_id"],
            "topic": question["topic"],
            "difficulty": question["difficulty"],
            "stem": question["stem"],
            "options": question["options"],
            "source_requirement": question.get("source_requirement"),
        }

    def _build_stats(self, session: dict[str, Any], attempts: list[dict[str, Any]]) -> dict[str, Any]:
        total_answered = len(attempts)
        correct_answers = sum(int(attempt.get("correct", 0)) for attempt in attempts)
        accuracy = round((correct_answers / total_answered) if total_answered else 0.0, 4)
        average_response_time_ms = round(
            sum(int(attempt.get("response_time_ms", 0)) for attempt in attempts) / total_answered,
            2,
        ) if total_answered else 0.0
        latest_attempt = attempts[0] if attempts else None
        mastery_score = round(
            self.predictor.calculate_mastery_score(attempts, topic=latest_attempt.get("topic") if latest_attempt else None),
            4,
        ) if attempts else 0.5
        forgetting_score = round(
            self.predictor.calculate_forgetting_score(latest_attempt),
            4,
        ) if attempts else 0.95
        return {
            "total_answered": total_answered,
            "correct_answers": correct_answers,
            "accuracy": accuracy,
            "average_response_time_ms": average_response_time_ms,
            "mastery_score": mastery_score,
            "forgetting_score": forgetting_score,
            "current_difficulty": int(session.get("current_difficulty", 2)),
            "questions_remaining": max(
                int(session.get("target_question_count", 0)) - total_answered,
                0,
            ),
        }

    async def start_session(
        self,
        *,
        resume_id: str,
        job_id: str | None,
        language: str,
        question_count: int,
    ) -> dict[str, Any]:
        resume = db.get_resume(resume_id)
        if not resume:
            raise HTTPException(status_code=404, detail="Resume not found")
        resume_data = resume.get("processed_data")
        if not resume_data:
            raise HTTPException(
                status_code=400,
                detail="Resume has no processed data. Please upload or tailor the resume first.",
            )

        job = self._resolve_job_for_resume(resume_id, job_id)
        job_keywords = await extract_job_keywords(job["content"])
        context = build_interview_context(
            resume_id=resume_id,
            job_id=job["job_id"],
            job_content=job["content"],
            resume_data=resume_data,
            job_keywords=job_keywords,
        )
        current_difficulty = self._initial_difficulty(context)
        session_id = str(uuid4())
        opening_message = (
            "I will act as your interviewer. Questions will adapt to your response speed, accuracy, "
            "and the JD skills your resume covers less confidently."
        )

        session = self.store.create_session(
            session_id=session_id,
            resume_id=resume_id,
            job_id=job["job_id"],
            language=language,
            target_question_count=question_count,
            current_difficulty=current_difficulty,
            opening_message=opening_message,
            context=context,
        )

        question = await self.engine.generate_question(
            context=context,
            attempts=[],
            difficulty=current_difficulty,
            language=language,
        )
        self.store.save_question(
            session_id=session_id,
            question_id=question["question_id"],
            topic=question["topic"],
            difficulty=question["difficulty"],
            question=question,
        )
        session = self.store.update_session(
            session_id,
            {
                "current_question_id": question["question_id"],
                "questions_asked": 1,
                "latest_topic": question["topic"],
            },
        ) or session

        attempts = self.store.list_attempts(session_id=session_id)
        return {
            "session_id": session_id,
            "opening_message": opening_message,
            "context": context,
            "stats": self._build_stats(session, attempts),
            "current_question": self._public_question(question),
        }

    async def answer_question(
        self,
        *,
        session_id: str,
        question_id: str,
        selected_option_id: str,
        response_time_ms: int,
    ) -> dict[str, Any]:
        session = self.store.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Interview session not found")
        if session.get("status") == "completed":
            raise HTTPException(status_code=400, detail="Interview session is already completed")

        question_record = self.store.get_question(session_id, question_id)
        if not question_record:
            raise HTTPException(status_code=404, detail="Question not found")

        question = question_record["question"]
        correct = selected_option_id == question["correct_option_id"]

        previous_attempts = self.store.list_attempts(resume_id=session["resume_id"])
        topic_attempts = [
            attempt for attempt in previous_attempts if attempt.get("topic") == question["topic"]
        ]

        recommendation = self.predictor.recommend_next_difficulty(
            topic=question["topic"],
            resume_attempts=previous_attempts,
            topic_attempts=topic_attempts,
            current_difficulty=int(question["difficulty"]),
            response_time_ms=response_time_ms,
            correct=correct,
        )
        rolling_accuracy = self.predictor.rolling_accuracy(previous_attempts, question["topic"])

        self.store.create_attempt(
            session_id=session_id,
            resume_id=session["resume_id"],
            job_id=session["job_id"],
            question_id=question_id,
            topic=question["topic"],
            difficulty=int(question["difficulty"]),
            selected_option_id=selected_option_id,
            correct=correct,
            response_time_ms=response_time_ms,
            rolling_accuracy=rolling_accuracy,
            mastery_score=recommendation.mastery_score,
            forgetting_score=recommendation.forgetting_score,
            recommended_next_difficulty=recommendation.recommended_difficulty,
        )

        session_attempts = self.store.list_attempts(session_id=session_id)
        total_answered = len(session_attempts)
        target_question_count = int(session.get("target_question_count", 5))
        completed = total_answered >= target_question_count

        update_payload: dict[str, Any] = {
            "questions_answered": total_answered,
            "current_difficulty": recommendation.recommended_difficulty,
            "latest_topic": question["topic"],
            "status": "completed" if completed else "active",
        }
        next_question_public = None

        if not completed:
            next_question = await self.engine.generate_question(
                context=session["context"],
                attempts=session_attempts,
                difficulty=recommendation.recommended_difficulty,
                language=session["language"],
            )
            self.store.save_question(
                session_id=session_id,
                question_id=next_question["question_id"],
                topic=next_question["topic"],
                difficulty=next_question["difficulty"],
                question=next_question,
            )
            update_payload["current_question_id"] = next_question["question_id"]
            update_payload["questions_asked"] = int(session.get("questions_asked", 1)) + 1
            next_question_public = self._public_question(next_question)

        session = self.store.update_session(session_id, update_payload) or session
        stats = self._build_stats(session, session_attempts)

        return {
            "session_id": session_id,
            "question_id": question_id,
            "correct": correct,
            "correct_option_id": question["correct_option_id"],
            "explanation": question["explanation"],
            "answer_summary": question["answer_summary"],
            "completed": completed,
            "stats": {
                **stats,
                "current_difficulty": recommendation.recommended_difficulty,
                "mastery_score": round(recommendation.mastery_score, 4),
                "forgetting_score": round(recommendation.forgetting_score, 4),
                "predictor_confidence": round(recommendation.confidence, 4),
                "predictor_source": recommendation.model_source,
            },
            "next_question": next_question_public,
        }

    def get_session(self, session_id: str) -> dict[str, Any]:
        session = self.store.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Interview session not found")
        attempts = self.store.list_attempts(session_id=session_id)
        current_question = None
        current_question_id = session.get("current_question_id")
        if current_question_id:
            question_record = self.store.get_question(session_id, current_question_id)
            if question_record:
                current_question = self._public_question(question_record["question"])

        return {
            "session_id": session_id,
            "opening_message": session.get("opening_message"),
            "context": session["context"],
            "stats": self._build_stats(session, attempts),
            "current_question": current_question,
            "history": [
                {
                    "question_id": attempt["question_id"],
                    "topic": attempt["topic"],
                    "difficulty": attempt["difficulty"],
                    "correct": bool(attempt["correct"]),
                    "response_time_ms": attempt["response_time_ms"],
                    "answered_at": attempt["answered_at"],
                }
                for attempt in reversed(attempts)
            ],
        }
