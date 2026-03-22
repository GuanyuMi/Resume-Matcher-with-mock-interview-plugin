'use client';

import {
  Brain,
  CheckCircle2,
  Gauge,
  Play,
  RefreshCcw,
  Target,
  TimerReset,
  XCircle,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { useTranslations } from '@/lib/i18n';
import { useLanguage } from '@/lib/context/language-context';
import { cn } from '@/lib/utils';
import { useAdaptiveMockInterview } from '@/hooks/use-adaptive-mock-interview';

interface MockInterviewSharedProps {
  controller: ReturnType<typeof useAdaptiveMockInterview>;
}

function formatPercent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

function formatSeconds(valueMs: number): string {
  return `${Math.max(Math.round(valueMs / 1000), 0)}s`;
}

function useMockInterviewCopy() {
  const { t } = useTranslations();
  const { uiLanguage } = useLanguage();

  const tr = (key: string, english: string, chinese?: string) => {
    const translated = t(key);
    if (translated !== key) {
      return translated;
    }
    if (uiLanguage.startsWith('zh')) {
      return chinese ?? english;
    }
    return english;
  };

  return {
    title: tr('builder.mockInterview.title', 'Adaptive Mock Interview', '自适应模拟面试'),
    description: tr(
      'builder.mockInterview.description',
      'Practice with JD-grounded technical questions that adapt to your mastery and forgetting curve.',
      '基于 JD 与简历内容进行技术问答练习，并根据掌握度与遗忘曲线动态调节难度。'
    ),
    start: tr('builder.mockInterview.start', 'Start Interview', '开始面试'),
    restart: tr('builder.mockInterview.restart', 'Restart Session', '重新开始'),
    submit: tr('builder.mockInterview.submit', 'Submit Answer', '提交答案'),
    disabled: tr(
      'builder.mockInterview.disabled',
      'Mock interview unlocks after a resume is linked to a job description.',
      '简历与 JD 建立关联后即可开启模拟面试。'
    ),
    questionCount: tr('builder.mockInterview.questionCount', 'Question Count', '题目数量'),
    currentQuestion: tr('builder.mockInterview.currentQuestion', 'Current Question', '当前题目'),
    lastFeedback: tr('builder.mockInterview.lastFeedback', 'Latest Feedback', '最近反馈'),
    correct: tr('builder.mockInterview.correct', 'Correct', '回答正确'),
    incorrect: tr('builder.mockInterview.incorrect', 'Needs Work', '仍需加强'),
    matchedSkills: tr('builder.mockInterview.matchedSkills', 'Matched Skills', '已匹配技能'),
    missingSkills: tr('builder.mockInterview.missingSkills', 'Stretch Areas', '待加强方向'),
    focusAreas: tr('builder.mockInterview.focusAreas', 'Focus Areas', '重点主题'),
    history: tr('builder.mockInterview.history', 'Question History', '作答历史'),
    noHistory: tr('builder.mockInterview.noHistory', 'No answers yet.', '还没有作答记录。'),
    completed: tr(
      'builder.mockInterview.completed',
      'Session complete. Review the insights panel, then restart to practice a fresh adaptive sequence.',
      '本轮已完成。先查看右侧分析，再重新开始下一轮自适应练习。'
    ),
    restore: tr('builder.mockInterview.restore', 'Restoring session...', '正在恢复会话...'),
    predictor: tr('builder.mockInterview.predictor', 'Difficulty Engine', '难度引擎'),
    accuracy: tr('builder.mockInterview.accuracy', 'Accuracy', '正确率'),
    averageTime: tr('builder.mockInterview.averageTime', 'Avg Time', '平均耗时'),
    mastery: tr('builder.mockInterview.mastery', 'Mastery', '掌握度'),
    forgetting: tr('builder.mockInterview.forgetting', 'Retention', '记忆保持'),
    nextDifficulty: tr('builder.mockInterview.nextDifficulty', 'Next Difficulty', '下一题难度'),
    idealAnswer: tr('builder.mockInterview.idealAnswer', 'Ideal Answer', '理想答案'),
    explanation: tr('builder.mockInterview.explanation', 'Why It Works', '原因说明'),
    support: tr(
      'builder.mockInterview.support',
      'The interview engine reuses JD extraction and structured resume content from Resume Matcher.',
      '该面试引擎直接复用 Resume Matcher 的 JD 提取结果与结构化简历内容。'
    ),
  };
}

function Pill({
  children,
  tone = 'neutral',
}: {
  children: React.ReactNode;
  tone?: 'neutral' | 'success' | 'warning';
}) {
  return (
    <span
      className={cn(
        'inline-flex items-center border border-black px-2 py-1 text-[11px] font-mono uppercase tracking-wide',
        tone === 'neutral' && 'bg-white text-black',
        tone === 'success' && 'bg-green-100 text-green-900',
        tone === 'warning' && 'bg-amber-100 text-amber-900'
      )}
    >
      {children}
    </span>
  );
}

function StatCard({ label, value, accent }: { label: string; value: string; accent: string }) {
  return (
    <div className="border border-black bg-white p-4">
      <p className="font-mono text-[11px] uppercase tracking-wide text-gray-600">{label}</p>
      <p className={cn('mt-2 font-serif text-3xl leading-none', accent)}>{value}</p>
    </div>
  );
}

export function MockInterviewPanel({ controller }: MockInterviewSharedProps) {
  const copy = useMockInterviewCopy();
  const {
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
    canStart,
  } = controller;

  if (!canStart && !session) {
    return (
      <Card variant="outline" className="border-2 border-dashed border-black bg-white">
        <CardHeader>
          <CardTitle>{copy.title}</CardTitle>
          <CardDescription>{copy.disabled}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3 text-sm text-gray-700">
          <p>{copy.support}</p>
        </CardContent>
      </Card>
    );
  }

  if (isRestoring && !session) {
    return (
      <Card variant="outline" className="border-black bg-white">
        <CardContent className="flex min-h-[220px] items-center justify-center">
          <p className="font-mono text-sm uppercase tracking-wide text-blue-700">{copy.restore}</p>
        </CardContent>
      </Card>
    );
  }

  if (!session) {
    return (
      <div className="space-y-4">
        <Card variant="outline" className="border-black bg-white">
          <CardHeader>
            <CardTitle>{copy.title}</CardTitle>
            <CardDescription>{copy.description}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            <div className="border border-black bg-[#F0F0E8] p-4">
              <p className="font-mono text-[11px] uppercase tracking-wide text-blue-700">
                {copy.questionCount}
              </p>
              <div className="mt-3 flex gap-2">
                {[5, 8, 10].map((count) => (
                  <button
                    key={count}
                    type="button"
                    className={cn(
                      'border border-black px-4 py-2 font-mono text-xs uppercase tracking-wide',
                      questionCount === count
                        ? 'bg-blue-700 text-white'
                        : 'bg-white text-black hover:bg-[#E5E5E0]'
                    )}
                    onClick={() => setQuestionCount(count)}
                  >
                    {count}
                  </button>
                ))}
              </div>
            </div>

            {error && <p className="text-sm text-red-700">{error}</p>}

            <Button onClick={startSession} disabled={isStarting} className="w-full">
              <Play className="w-4 h-4" />
              {isStarting ? `${copy.start}...` : copy.start}
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  const question = session.current_question;

  return (
    <div className="space-y-4">
      <Card variant="outline" className="border-black bg-white">
        <CardHeader>
          <div className="flex items-start justify-between gap-4">
            <div>
              <CardTitle>{copy.title}</CardTitle>
              <CardDescription>{session.opening_message ?? copy.description}</CardDescription>
            </div>
            <Button variant="outline" size="sm" onClick={resetSession}>
              <RefreshCcw className="w-4 h-4" />
              {copy.restart}
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap gap-2">
            {(session.context.focus_areas ?? []).slice(0, 4).map((item) => (
              <Pill key={item} tone="neutral">
                {item}
              </Pill>
            ))}
          </div>

          {question ? (
            <div className="space-y-4">
              <div className="border border-black bg-[#F0F0E8] p-4">
                <div className="flex flex-wrap items-center gap-2">
                  <Pill tone="neutral">{copy.currentQuestion}</Pill>
                  <Pill tone="success">{`${copy.nextDifficulty} ${question.difficulty}`}</Pill>
                  <Pill tone="warning">{question.topic}</Pill>
                </div>
                <p className="mt-4 font-serif text-2xl leading-tight text-black">{question.stem}</p>
                {question.source_requirement && (
                  <p className="mt-3 text-sm text-gray-600">
                    <span className="font-mono uppercase tracking-wide text-blue-700">JD</span>{' '}
                    {question.source_requirement}
                  </p>
                )}
              </div>

              <div className="space-y-3">
                {question.options.map((option) => {
                  const isSelected = selectedOptionId === option.option_id;
                  return (
                    <button
                      key={option.option_id}
                      type="button"
                      onClick={() => setSelectedOptionId(option.option_id)}
                      className={cn(
                        'w-full border border-black p-4 text-left transition-colors',
                        isSelected
                          ? 'bg-blue-700 text-white'
                          : 'bg-white text-black hover:bg-[#E5E5E0]'
                      )}
                    >
                      <div className="flex items-start gap-3">
                        <span className="font-mono text-sm uppercase">{option.option_id}</span>
                        <span className="text-sm leading-relaxed">{option.text}</span>
                      </div>
                    </button>
                  );
                })}
              </div>

              {error && <p className="text-sm text-red-700">{error}</p>}

              <Button
                onClick={submitAnswer}
                disabled={!selectedOptionId || isSubmitting}
                className="w-full"
              >
                {isSubmitting ? `${copy.submit}...` : copy.submit}
              </Button>
            </div>
          ) : (
            <div className="border border-black bg-[#F0F0E8] p-5">
              <p className="text-sm text-gray-700">{copy.completed}</p>
              <Button onClick={startSession} disabled={isStarting} className="mt-4">
                <Play className="w-4 h-4" />
                {copy.start}
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {lastResult && (
        <Card variant="outline" className="border-black bg-white">
          <CardHeader>
            <CardTitle>{copy.lastFeedback}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center gap-2">
              {lastResult.correct ? (
                <>
                  <CheckCircle2 className="w-5 h-5 text-green-700" />
                  <span className="font-mono text-sm uppercase tracking-wide text-green-700">
                    {copy.correct}
                  </span>
                </>
              ) : (
                <>
                  <XCircle className="w-5 h-5 text-red-700" />
                  <span className="font-mono text-sm uppercase tracking-wide text-red-700">
                    {copy.incorrect}
                  </span>
                </>
              )}
            </div>
            <div className="border border-black bg-[#F0F0E8] p-4">
              <p className="font-mono text-[11px] uppercase tracking-wide text-blue-700">
                {copy.explanation}
              </p>
              <p className="mt-2 text-sm leading-relaxed text-gray-700">{lastResult.explanation}</p>
            </div>
            <div className="border border-black bg-white p-4">
              <p className="font-mono text-[11px] uppercase tracking-wide text-blue-700">
                {copy.idealAnswer}
              </p>
              <p className="mt-2 text-sm leading-relaxed text-gray-700">
                {lastResult.answer_summary}
              </p>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

export function MockInterviewInsights({ controller }: MockInterviewSharedProps) {
  const copy = useMockInterviewCopy();
  const { session } = controller;

  if (!session) {
    return (
      <div className="p-6">
        <Card variant="outline" className="border-black bg-white">
          <CardHeader>
            <CardTitle>{copy.title}</CardTitle>
            <CardDescription>{copy.description}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-sm text-gray-700">
            <p>{copy.support}</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  const stats = session.stats;
  const history = session.history ?? [];

  return (
    <div className="p-6 space-y-5">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <StatCard
          label={copy.accuracy}
          value={formatPercent(stats.accuracy)}
          accent="text-blue-700"
        />
        <StatCard
          label={copy.averageTime}
          value={formatSeconds(stats.average_response_time_ms)}
          accent="text-orange-600"
        />
        <StatCard
          label={copy.mastery}
          value={formatPercent(stats.mastery_score)}
          accent="text-green-700"
        />
        <StatCard
          label={copy.forgetting}
          value={formatPercent(stats.forgetting_score)}
          accent="text-red-600"
        />
      </div>

      <Card variant="outline" className="border-black bg-white">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-xl">
            <Gauge className="w-5 h-5" />
            {copy.predictor}
          </CardTitle>
          <CardDescription>
            {`${copy.nextDifficulty}: ${stats.current_difficulty}`}
            {stats.predictor_source ? ` | ${stats.predictor_source}` : ''}
          </CardDescription>
        </CardHeader>
      </Card>

      <Card variant="outline" className="border-black bg-white">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-xl">
            <Target className="w-5 h-5" />
            {copy.focusAreas}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <p className="font-mono text-[11px] uppercase tracking-wide text-blue-700">
              {copy.matchedSkills}
            </p>
            <div className="flex flex-wrap gap-2">
              {(session.context.matched_skills ?? []).slice(0, 8).map((item) => (
                <Pill key={item} tone="success">
                  {item}
                </Pill>
              ))}
            </div>
          </div>
          <div className="space-y-2">
            <p className="font-mono text-[11px] uppercase tracking-wide text-blue-700">
              {copy.missingSkills}
            </p>
            <div className="flex flex-wrap gap-2">
              {(session.context.missing_skills ?? []).slice(0, 8).map((item) => (
                <Pill key={item} tone="warning">
                  {item}
                </Pill>
              ))}
            </div>
          </div>
          <div className="space-y-2">
            <p className="font-mono text-[11px] uppercase tracking-wide text-blue-700">
              {copy.focusAreas}
            </p>
            <div className="flex flex-wrap gap-2">
              {(session.context.focus_areas ?? []).slice(0, 8).map((item) => (
                <Pill key={item}>{item}</Pill>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>

      <Card variant="outline" className="border-black bg-white">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-xl">
            <Brain className="w-5 h-5" />
            {copy.history}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {history.length === 0 ? (
            <p className="text-sm text-gray-600">{copy.noHistory}</p>
          ) : (
            history
              .slice()
              .reverse()
              .map((item) => (
                <div
                  key={`${item.question_id}-${item.answered_at}`}
                  className="border border-black bg-[#F0F0E8] p-4"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <Pill tone={item.correct ? 'success' : 'warning'}>
                      {item.correct ? copy.correct : copy.incorrect}
                    </Pill>
                    <Pill>{item.topic}</Pill>
                    <Pill>{`${copy.nextDifficulty} ${item.difficulty}`}</Pill>
                    <Pill>
                      <TimerReset className="mr-1 w-3 h-3" />
                      {formatSeconds(item.response_time_ms)}
                    </Pill>
                  </div>
                </div>
              ))
          )}
        </CardContent>
      </Card>
    </div>
  );
}
