"""Adaptive mock interview endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from app.adaptive_mock_interview import AdaptiveMockInterviewService
from app.schemas import (
    MockInterviewAnswerRequest,
    MockInterviewAnswerResponse,
    MockInterviewSessionCreateRequest,
    MockInterviewSessionCreateResponse,
    MockInterviewSessionResponse,
)

router = APIRouter(prefix="/mock-interview", tags=["Mock Interview"])

service = AdaptiveMockInterviewService()


@router.post("/sessions", response_model=MockInterviewSessionCreateResponse)
async def create_mock_interview_session(
    request: MockInterviewSessionCreateRequest,
) -> MockInterviewSessionCreateResponse:
    payload = await service.start_session(
        resume_id=request.resume_id,
        job_id=request.job_id,
        language=request.language,
        question_count=request.question_count,
    )
    return MockInterviewSessionCreateResponse.model_validate(payload)


@router.post("/sessions/{session_id}/answers", response_model=MockInterviewAnswerResponse)
async def answer_mock_interview_question(
    session_id: str,
    request: MockInterviewAnswerRequest,
) -> MockInterviewAnswerResponse:
    payload = await service.answer_question(
        session_id=session_id,
        question_id=request.question_id,
        selected_option_id=request.selected_option_id,
        response_time_ms=request.response_time_ms,
    )
    return MockInterviewAnswerResponse.model_validate(payload)


@router.get("/sessions/{session_id}", response_model=MockInterviewSessionResponse)
async def get_mock_interview_session(session_id: str) -> MockInterviewSessionResponse:
    payload = service.get_session(session_id)
    return MockInterviewSessionResponse.model_validate(payload)
