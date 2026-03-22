"""Schemas for adaptive mock interview."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


class InterviewOption(BaseModel):
    """Single multiple-choice option."""

    option_id: str
    text: str


class PublicInterviewQuestion(BaseModel):
    """Question payload safe to send before the user answers."""

    question_id: str
    topic: str
    difficulty: int = Field(ge=1, le=5)
    stem: str
    options: list[InterviewOption]
    source_requirement: str | None = None


class InterviewStats(BaseModel):
    """Aggregate stats for the current interview session."""

    total_answered: int = 0
    correct_answers: int = 0
    accuracy: float = 0.0
    average_response_time_ms: float = 0.0
    mastery_score: float = 0.0
    forgetting_score: float = 0.0
    current_difficulty: int = Field(ge=1, le=5)
    questions_remaining: int = 0
    predictor_confidence: float | None = None
    predictor_source: str | None = None


class InterviewHistoryItem(BaseModel):
    """Completed answer history entry."""

    question_id: str
    topic: str
    difficulty: int = Field(ge=1, le=5)
    correct: bool
    response_time_ms: int = Field(ge=0)
    answered_at: str


class MockInterviewSessionCreateRequest(BaseModel):
    """Request to start a mock interview session."""

    resume_id: str
    job_id: str | None = None
    language: str = Field(default="en", min_length=2, max_length=16)
    question_count: int = Field(default=5, ge=1, le=15)


class MockInterviewSessionCreateResponse(BaseModel):
    """Response returned when a session starts."""

    session_id: str
    opening_message: str
    context: dict[str, Any]
    stats: InterviewStats
    current_question: PublicInterviewQuestion


class MockInterviewAnswerRequest(BaseModel):
    """Answer submission payload."""

    question_id: str
    selected_option_id: str = Field(min_length=1, max_length=8)
    response_time_ms: int = Field(ge=0, le=600000)

    @field_validator("selected_option_id")
    @classmethod
    def normalize_option_id(cls, value: str) -> str:
        return value.strip().upper()


class MockInterviewAnswerResponse(BaseModel):
    """Response after evaluating one answer."""

    session_id: str
    question_id: str
    correct: bool
    correct_option_id: str
    explanation: str
    answer_summary: str
    completed: bool
    stats: InterviewStats
    next_question: PublicInterviewQuestion | None = None


class MockInterviewSessionResponse(BaseModel):
    """Session status payload for refresh and recovery."""

    session_id: str
    opening_message: str | None = None
    context: dict[str, Any]
    stats: InterviewStats
    current_question: PublicInterviewQuestion | None = None
    history: list[InterviewHistoryItem] = Field(default_factory=list)
