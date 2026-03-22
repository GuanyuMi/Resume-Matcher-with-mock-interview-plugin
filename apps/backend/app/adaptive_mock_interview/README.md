# Adaptive Mock Interview Backend Module

This directory contains the backend implementation for the Adaptive Mock Interview extension.

It is intentionally kept inside the existing Resume Matcher backend because the feature depends on:

- resume parsing output already produced by the platform
- JD extraction and keyword analysis already used by resume tailoring
- shared FastAPI routing and configuration

## Files

- `context.py`: builds interview-ready context from resume and JD data
- `llm_engine.py`: LangGraph-based interviewer agent and question generation logic
- `predictor.py`: adaptive difficulty recommendation using mastery and forgetting signals
- `service.py`: orchestration layer for sessions, answers, and progression
- `database/sqlite_store.py`: SQLite persistence for sessions, questions, and attempts

