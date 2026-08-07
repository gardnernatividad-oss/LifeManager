export type DailyFormAnswerType = "boolean" | "text" | "number";

export interface DailyFormQuestion {
  id: string;
  order: number;
  title: string;
  description: string | null;
  answer_type: DailyFormAnswerType;
}

export interface DailyFormDefinition {
  id: string;
  workspace_id: string;
  questions: DailyFormQuestion[];
  created_at: string;
  updated_at: string;
}

export interface DailyFormAnswer {
  question_id: string;
  question_title: string;
  question_order: number;
  answer_type: DailyFormAnswerType;
  value: boolean | string | number;
}

export interface DailyFormSubmission {
  id: string;
  workspace_id: string;
  user_id: string;
  definition_id: string;
  submission_date: string;
  answers: DailyFormAnswer[];
  created_at: string;
  updated_at: string;
}

export interface DailyFormSubmissionPayload {
  answers: Array<{ question_id: string; value: boolean | string | number }>;
}
