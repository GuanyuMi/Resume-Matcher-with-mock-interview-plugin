"""SQLite-backed persistence for interview sessions and attempts."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SQLiteInterviewStore:
    """Persistence layer dedicated to adaptive mock interview data."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS interview_sessions (
                    session_id TEXT PRIMARY KEY,
                    resume_id TEXT NOT NULL,
                    job_id TEXT NOT NULL,
                    language TEXT NOT NULL,
                    status TEXT NOT NULL,
                    target_question_count INTEGER NOT NULL,
                    questions_asked INTEGER NOT NULL DEFAULT 0,
                    questions_answered INTEGER NOT NULL DEFAULT 0,
                    current_difficulty INTEGER NOT NULL DEFAULT 2,
                    current_question_id TEXT,
                    latest_topic TEXT,
                    opening_message TEXT,
                    context_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS interview_questions (
                    question_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    difficulty INTEGER NOT NULL,
                    question_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS interview_attempts (
                    attempt_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    resume_id TEXT NOT NULL,
                    job_id TEXT NOT NULL,
                    question_id TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    difficulty INTEGER NOT NULL,
                    selected_option_id TEXT NOT NULL,
                    correct INTEGER NOT NULL,
                    response_time_ms INTEGER NOT NULL,
                    rolling_accuracy REAL NOT NULL,
                    mastery_score REAL NOT NULL,
                    forgetting_score REAL NOT NULL,
                    recommended_next_difficulty INTEGER NOT NULL,
                    answered_at TEXT NOT NULL
                );
                """
            )

    @staticmethod
    def _decode_row(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        return {key: row[key] for key in row.keys()}

    def create_session(
        self,
        *,
        session_id: str,
        resume_id: str,
        job_id: str,
        language: str,
        target_question_count: int,
        current_difficulty: int,
        opening_message: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        now = _utc_now()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO interview_sessions (
                    session_id,
                    resume_id,
                    job_id,
                    language,
                    status,
                    target_question_count,
                    current_difficulty,
                    opening_message,
                    context_json,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    resume_id,
                    job_id,
                    language,
                    "active",
                    target_question_count,
                    current_difficulty,
                    opening_message,
                    json.dumps(context, ensure_ascii=False),
                    now,
                    now,
                ),
            )
        return self.get_session(session_id) or {}

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM interview_sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        result = self._decode_row(row)
        if not result:
            return None
        result["context"] = json.loads(result.pop("context_json"))
        return result

    def update_session(
        self,
        session_id: str,
        updates: dict[str, Any],
    ) -> dict[str, Any] | None:
        if not updates:
            return self.get_session(session_id)

        payload = dict(updates)
        if "context" in payload:
            payload["context_json"] = json.dumps(payload.pop("context"), ensure_ascii=False)
        payload["updated_at"] = _utc_now()

        assignments = ", ".join(f"{column} = ?" for column in payload)
        values = list(payload.values()) + [session_id]

        with self._connect() as connection:
            connection.execute(
                f"UPDATE interview_sessions SET {assignments} WHERE session_id = ?",
                values,
            )
        return self.get_session(session_id)

    def save_question(
        self,
        *,
        session_id: str,
        question_id: str,
        topic: str,
        difficulty: int,
        question: dict[str, Any],
    ) -> dict[str, Any]:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO interview_questions (
                    question_id, session_id, topic, difficulty, question_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    question_id,
                    session_id,
                    topic,
                    difficulty,
                    json.dumps(question, ensure_ascii=False),
                    _utc_now(),
                ),
            )
        return self.get_question(session_id, question_id) or {}

    def get_question(self, session_id: str, question_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM interview_questions
                WHERE session_id = ? AND question_id = ?
                """,
                (session_id, question_id),
            ).fetchone()
        result = self._decode_row(row)
        if not result:
            return None
        result["question"] = json.loads(result.pop("question_json"))
        return result

    def list_attempts(
        self,
        *,
        session_id: str | None = None,
        resume_id: str | None = None,
        topic: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM interview_attempts"
        filters: list[str] = []
        values: list[Any] = []

        if session_id:
            filters.append("session_id = ?")
            values.append(session_id)
        if resume_id:
            filters.append("resume_id = ?")
            values.append(resume_id)
        if topic:
            filters.append("topic = ?")
            values.append(topic)

        if filters:
            query += " WHERE " + " AND ".join(filters)

        query += " ORDER BY answered_at DESC"
        if limit is not None:
            query += " LIMIT ?"
            values.append(limit)

        with self._connect() as connection:
            rows = connection.execute(query, values).fetchall()
        return [self._decode_row(row) or {} for row in rows]

    def create_attempt(
        self,
        *,
        session_id: str,
        resume_id: str,
        job_id: str,
        question_id: str,
        topic: str,
        difficulty: int,
        selected_option_id: str,
        correct: bool,
        response_time_ms: int,
        rolling_accuracy: float,
        mastery_score: float,
        forgetting_score: float,
        recommended_next_difficulty: int,
    ) -> dict[str, Any]:
        answered_at = _utc_now()
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO interview_attempts (
                    session_id,
                    resume_id,
                    job_id,
                    question_id,
                    topic,
                    difficulty,
                    selected_option_id,
                    correct,
                    response_time_ms,
                    rolling_accuracy,
                    mastery_score,
                    forgetting_score,
                    recommended_next_difficulty,
                    answered_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    resume_id,
                    job_id,
                    question_id,
                    topic,
                    difficulty,
                    selected_option_id,
                    1 if correct else 0,
                    response_time_ms,
                    rolling_accuracy,
                    mastery_score,
                    forgetting_score,
                    recommended_next_difficulty,
                    answered_at,
                ),
            )
            attempt_id = cursor.lastrowid
        return {
            "attempt_id": attempt_id,
            "session_id": session_id,
            "resume_id": resume_id,
            "job_id": job_id,
            "question_id": question_id,
            "topic": topic,
            "difficulty": difficulty,
            "selected_option_id": selected_option_id,
            "correct": int(correct),
            "response_time_ms": response_time_ms,
            "rolling_accuracy": rolling_accuracy,
            "mastery_score": mastery_score,
            "forgetting_score": forgetting_score,
            "recommended_next_difficulty": recommended_next_difficulty,
            "answered_at": answered_at,
        }
