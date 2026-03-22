import { apiFetch, apiPost } from './client';

export interface InterviewOption {
  option_id: string;
  text: string;
}

export interface PublicInterviewQuestion {
  question_id: string;
  topic: string;
  difficulty: number;
  stem: string;
  options: InterviewOption[];
  source_requirement?: string | null;
}

export interface InterviewStats {
  total_answered: number;
  correct_answers: number;
  accuracy: number;
  average_response_time_ms: number;
  mastery_score: number;
  forgetting_score: number;
  current_difficulty: number;
  questions_remaining: number;
  predictor_confidence?: number | null;
  predictor_source?: string | null;
}

export interface InterviewHistoryItem {
  question_id: string;
  topic: string;
  difficulty: number;
  correct: boolean;
  response_time_ms: number;
  answered_at: string;
}

export interface MockInterviewSessionPayload {
  session_id: string;
  opening_message?: string | null;
  context: {
    core_requirements?: string[];
    matched_skills?: string[];
    missing_skills?: string[];
    responsibilities?: string[];
    resume_highlights?: string[];
    focus_areas?: string[];
    match_ratio?: number;
  };
  stats: InterviewStats;
  current_question?: PublicInterviewQuestion | null;
  history?: InterviewHistoryItem[];
}

export interface MockInterviewAnswerResponse {
  session_id: string;
  question_id: string;
  correct: boolean;
  correct_option_id: string;
  explanation: string;
  answer_summary: string;
  completed: boolean;
  stats: InterviewStats;
  next_question?: PublicInterviewQuestion | null;
}

export async function createMockInterviewSession(payload: {
  resume_id: string;
  job_id?: string | null;
  language: string;
  question_count: number;
}): Promise<MockInterviewSessionPayload> {
  const res = await apiPost('/mock-interview/sessions', payload);
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(text || `Failed to create mock interview session (status ${res.status}).`);
  }
  return (await res.json()) as MockInterviewSessionPayload;
}

export async function submitMockInterviewAnswer(
  sessionId: string,
  payload: {
    question_id: string;
    selected_option_id: string;
    response_time_ms: number;
  }
): Promise<MockInterviewAnswerResponse> {
  const res = await apiPost(
    `/mock-interview/sessions/${encodeURIComponent(sessionId)}/answers`,
    payload
  );
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(text || `Failed to submit mock interview answer (status ${res.status}).`);
  }
  return (await res.json()) as MockInterviewAnswerResponse;
}

export async function fetchMockInterviewSession(
  sessionId: string
): Promise<MockInterviewSessionPayload> {
  const res = await apiFetch(`/mock-interview/sessions/${encodeURIComponent(sessionId)}`);
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(text || `Failed to load mock interview session (status ${res.status}).`);
  }
  return (await res.json()) as MockInterviewSessionPayload;
}
