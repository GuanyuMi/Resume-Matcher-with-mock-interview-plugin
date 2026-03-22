'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  createMockInterviewSession,
  fetchMockInterviewSession,
  submitMockInterviewAnswer,
  type InterviewHistoryItem,
  type MockInterviewAnswerResponse,
  type MockInterviewSessionPayload,
} from '@/lib/api/mock-interview';

interface UseAdaptiveMockInterviewOptions {
  resumeId: string | null;
  hasJobContext: boolean;
  language: string;
}

function getStorageKey(resumeId: string | null): string | null {
  return resumeId ? `mock_interview_session_${resumeId}` : null;
}

export function useAdaptiveMockInterview({
  resumeId,
  hasJobContext,
  language,
}: UseAdaptiveMockInterviewOptions) {
  const [session, setSession] = useState<MockInterviewSessionPayload | null>(null);
  const [lastResult, setLastResult] = useState<MockInterviewAnswerResponse | null>(null);
  const [selectedOptionId, setSelectedOptionId] = useState<string | null>(null);
  const [questionCount, setQuestionCount] = useState(5);
  const [isStarting, setIsStarting] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isRestoring, setIsRestoring] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const questionShownAtRef = useRef<number | null>(null);

  const storageKey = useMemo(() => getStorageKey(resumeId), [resumeId]);

  const resetSession = useCallback(() => {
    setSession(null);
    setLastResult(null);
    setSelectedOptionId(null);
    setError(null);
    questionShownAtRef.current = null;
    if (storageKey && typeof window !== 'undefined') {
      window.sessionStorage.removeItem(storageKey);
    }
  }, [storageKey]);

  useEffect(() => {
    if (!storageKey || typeof window === 'undefined') {
      setSession(null);
      setLastResult(null);
      setSelectedOptionId(null);
      return;
    }

    const sessionId = window.sessionStorage.getItem(storageKey);
    if (!sessionId) {
      setSession(null);
      setLastResult(null);
      setSelectedOptionId(null);
      return;
    }

    let active = true;
    setIsRestoring(true);

    void fetchMockInterviewSession(sessionId)
      .then((payload) => {
        if (!active) return;
        setSession(payload);
        setSelectedOptionId(null);
        questionShownAtRef.current = payload.current_question ? Date.now() : null;
      })
      .catch(() => {
        if (!active) return;
        window.sessionStorage.removeItem(storageKey);
        setSession(null);
      })
      .finally(() => {
        if (!active) return;
        setIsRestoring(false);
      });

    return () => {
      active = false;
    };
  }, [storageKey]);

  const startSession = useCallback(async () => {
    if (!resumeId) {
      setError('Resume ID is required.');
      return;
    }
    if (!hasJobContext) {
      setError('Mock interview requires a tailored resume or a linked job description.');
      return;
    }

    try {
      setIsStarting(true);
      setError(null);
      setLastResult(null);
      setSelectedOptionId(null);
      const payload = await createMockInterviewSession({
        resume_id: resumeId,
        language,
        question_count: questionCount,
      });
      setSession({ ...payload, history: payload.history ?? [] });
      questionShownAtRef.current = payload.current_question ? Date.now() : null;
      if (storageKey && typeof window !== 'undefined') {
        window.sessionStorage.setItem(storageKey, payload.session_id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start mock interview.');
    } finally {
      setIsStarting(false);
    }
  }, [hasJobContext, language, questionCount, resumeId, storageKey]);

  const submitAnswer = useCallback(async () => {
    if (!session?.current_question || !selectedOptionId) {
      return;
    }

    const startedAt = questionShownAtRef.current ?? Date.now();
    const responseTimeMs = Math.max(Date.now() - startedAt, 0);

    try {
      setIsSubmitting(true);
      setError(null);
      const response = await submitMockInterviewAnswer(session.session_id, {
        question_id: session.current_question.question_id,
        selected_option_id: selectedOptionId,
        response_time_ms: responseTimeMs,
      });

      setLastResult(response);
      setSession((current) => {
        if (!current?.current_question) {
          return current;
        }
        const historyItem: InterviewHistoryItem = {
          question_id: current.current_question.question_id,
          topic: current.current_question.topic,
          difficulty: current.current_question.difficulty,
          correct: response.correct,
          response_time_ms: responseTimeMs,
          answered_at: new Date().toISOString(),
        };
        return {
          ...current,
          stats: response.stats,
          current_question: response.next_question ?? null,
          history: [...(current.history ?? []), historyItem],
        };
      });
      setSelectedOptionId(null);

      if (response.completed) {
        questionShownAtRef.current = null;
        if (storageKey && typeof window !== 'undefined') {
          window.sessionStorage.removeItem(storageKey);
        }
      } else {
        questionShownAtRef.current = Date.now();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to submit answer.');
    } finally {
      setIsSubmitting(false);
    }
  }, [selectedOptionId, session, storageKey]);

  return {
    session,
    lastResult,
    selectedOptionId,
    setSelectedOptionId,
    questionCount,
    setQuestionCount,
    isStarting,
    isSubmitting,
    isRestoring,
    error,
    startSession,
    submitAnswer,
    resetSession,
    canStart: Boolean(resumeId && hasJobContext),
    hasActiveQuestion: Boolean(session?.current_question),
  };
}
