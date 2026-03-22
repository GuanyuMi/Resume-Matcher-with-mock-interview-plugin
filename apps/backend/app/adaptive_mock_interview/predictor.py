"""Difficulty prediction for adaptive mock interviews."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

try:
    from sklearn.ensemble import RandomForestRegressor
except Exception:  # pragma: no cover - optional dependency fallback
    RandomForestRegressor = None  # type: ignore[assignment]


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _clamp_difficulty(value: float | int) -> int:
    return max(1, min(5, int(round(value))))


@dataclass
class DifficultyRecommendation:
    """Recommended next-question difficulty and associated diagnostics."""

    recommended_difficulty: int
    mastery_score: float
    forgetting_score: float
    confidence: float
    model_source: str


class DifficultyPredictor:
    """Predicts next interview difficulty from user performance history."""

    def __init__(self, decay_hours: float = 72.0) -> None:
        self.decay_hours = decay_hours

    def calculate_forgetting_score(
        self,
        previous_attempt: dict[str, Any] | None,
        *,
        now: datetime | None = None,
    ) -> float:
        """Approximate retention using an exponential forgetting curve."""
        if previous_attempt is None:
            return 0.95

        last_seen = _parse_iso(previous_attempt.get("answered_at"))
        if last_seen is None:
            return 0.8

        reference = now or datetime.now(timezone.utc)
        elapsed_hours = max((reference - last_seen).total_seconds() / 3600.0, 0.0)
        return max(0.05, min(1.0, math.exp(-elapsed_hours / self.decay_hours)))

    def calculate_mastery_score(
        self,
        attempts: list[dict[str, Any]],
        *,
        topic: str | None = None,
    ) -> float:
        """Blend accuracy, speed, and recency into a 0-1 mastery estimate."""
        relevant = [attempt for attempt in attempts if not topic or attempt.get("topic") == topic]
        if not relevant:
            return 0.5

        recent = relevant[:6]
        correctness = sum(float(attempt.get("correct", 0)) for attempt in recent) / len(recent)
        avg_time_ms = sum(int(attempt.get("response_time_ms", 0)) for attempt in recent) / len(recent)
        speed_score = max(0.15, min(1.0, 1.0 - (avg_time_ms / 180000.0)))
        forgetting_score = self.calculate_forgetting_score(recent[0])
        return max(0.1, min(0.98, correctness * 0.6 + speed_score * 0.2 + forgetting_score * 0.2))

    @staticmethod
    def rolling_accuracy(attempts: list[dict[str, Any]], topic: str) -> float:
        relevant = [attempt for attempt in attempts if attempt.get("topic") == topic][:5]
        if not relevant:
            return 0.5
        return sum(float(attempt.get("correct", 0)) for attempt in relevant) / len(relevant)

    def _build_feature_vector(
        self,
        *,
        topic: str,
        topic_attempts: list[dict[str, Any]],
        all_attempts: list[dict[str, Any]],
        current_difficulty: int,
        response_time_ms: int | None = None,
        correctness: bool | None = None,
    ) -> list[float]:
        latest_topic_attempt = topic_attempts[0] if topic_attempts else None
        forgetting_score = self.calculate_forgetting_score(latest_topic_attempt)
        mastery_score = self.calculate_mastery_score(all_attempts, topic=topic)
        rolling_accuracy = self.rolling_accuracy(all_attempts, topic)
        avg_time_ms = (
            sum(int(attempt.get("response_time_ms", 0)) for attempt in topic_attempts[:5]) / max(len(topic_attempts[:5]), 1)
            if topic_attempts
            else 90000.0
        )
        return [
            float(current_difficulty),
            float(correctness if correctness is not None else latest_topic_attempt.get("correct", 1) if latest_topic_attempt else 1),
            float(response_time_ms if response_time_ms is not None else avg_time_ms),
            float(rolling_accuracy),
            float(mastery_score),
            float(forgetting_score),
            float(len(topic_attempts)),
            float(len(all_attempts)),
        ]

    @staticmethod
    def _heuristic_target(
        *,
        current_difficulty: int,
        correct: bool,
        response_time_ms: int,
        rolling_accuracy: float,
        forgetting_score: float,
    ) -> int:
        delta = 0
        if correct:
            if response_time_ms <= 45000:
                delta += 1
            if rolling_accuracy >= 0.8:
                delta += 1
        else:
            delta -= 1
            if response_time_ms >= 90000:
                delta -= 1

        if forgetting_score <= 0.35:
            delta -= 1

        return _clamp_difficulty(current_difficulty + delta)

    def _build_training_data(
        self,
        attempts: list[dict[str, Any]],
    ) -> tuple[list[list[float]], list[int]]:
        rows = sorted(
            attempts,
            key=lambda attempt: attempt.get("answered_at", ""),
            reverse=True,
        )
        feature_rows: list[list[float]] = []
        targets: list[int] = []

        for index, attempt in enumerate(rows):
            topic = str(attempt.get("topic", "")).strip()
            later_attempts = rows[index + 1 :]
            topic_attempts = [item for item in later_attempts if item.get("topic") == topic]
            current_difficulty = int(attempt.get("difficulty", 2))
            response_time_ms = int(attempt.get("response_time_ms", 60000))
            correct = bool(attempt.get("correct"))
            rolling_accuracy = float(attempt.get("rolling_accuracy", self.rolling_accuracy(later_attempts, topic)))
            forgetting_score = float(
                attempt.get(
                    "forgetting_score",
                    self.calculate_forgetting_score(topic_attempts[0] if topic_attempts else None),
                )
            )

            feature_rows.append(
                self._build_feature_vector(
                    topic=topic,
                    topic_attempts=topic_attempts,
                    all_attempts=later_attempts,
                    current_difficulty=current_difficulty,
                    response_time_ms=response_time_ms,
                    correctness=correct,
                )
            )
            targets.append(
                _clamp_difficulty(
                    attempt.get(
                        "recommended_next_difficulty",
                        self._heuristic_target(
                            current_difficulty=current_difficulty,
                            correct=correct,
                            response_time_ms=response_time_ms,
                            rolling_accuracy=rolling_accuracy,
                            forgetting_score=forgetting_score,
                        ),
                    )
                )
            )

        return feature_rows, targets

    def recommend_next_difficulty(
        self,
        *,
        topic: str,
        resume_attempts: list[dict[str, Any]],
        topic_attempts: list[dict[str, Any]],
        current_difficulty: int,
        response_time_ms: int,
        correct: bool,
    ) -> DifficultyRecommendation:
        """Recommend next difficulty using sklearn when enough history exists."""
        rolling_accuracy = self.rolling_accuracy(resume_attempts, topic)
        forgetting_score = self.calculate_forgetting_score(topic_attempts[0] if topic_attempts else None)
        mastery_score = self.calculate_mastery_score(resume_attempts, topic=topic)

        if len(resume_attempts) < 6 or RandomForestRegressor is None:
            return DifficultyRecommendation(
                recommended_difficulty=self._heuristic_target(
                    current_difficulty=current_difficulty,
                    correct=correct,
                    response_time_ms=response_time_ms,
                    rolling_accuracy=rolling_accuracy,
                    forgetting_score=forgetting_score,
                ),
                mastery_score=mastery_score,
                forgetting_score=forgetting_score,
                confidence=0.45,
                model_source="heuristic",
            )

        features, targets = self._build_training_data(resume_attempts)
        if len(features) < 6:
            return DifficultyRecommendation(
                recommended_difficulty=self._heuristic_target(
                    current_difficulty=current_difficulty,
                    correct=correct,
                    response_time_ms=response_time_ms,
                    rolling_accuracy=rolling_accuracy,
                    forgetting_score=forgetting_score,
                ),
                mastery_score=mastery_score,
                forgetting_score=forgetting_score,
                confidence=0.5,
                model_source="heuristic",
            )

        model = RandomForestRegressor(
            n_estimators=64,
            max_depth=6,
            min_samples_leaf=1,
            random_state=42,
        )
        model.fit(features, targets)
        prediction = model.predict(
            [
                self._build_feature_vector(
                    topic=topic,
                    topic_attempts=topic_attempts,
                    all_attempts=resume_attempts,
                    current_difficulty=current_difficulty,
                    response_time_ms=response_time_ms,
                    correctness=correct,
                )
            ]
        )[0]

        confidence = min(0.9, 0.55 + len(features) / 50.0)
        return DifficultyRecommendation(
            recommended_difficulty=_clamp_difficulty(prediction),
            mastery_score=mastery_score,
            forgetting_score=forgetting_score,
            confidence=confidence,
            model_source="sklearn_random_forest",
        )
