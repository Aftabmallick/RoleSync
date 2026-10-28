// RoleSync Strongly-Typed Message Bus Protocol
export type MessageAction =
  | 'JD_EXTRACTED'
  | 'TRIGGER_TAILORING'
  | 'TAILORING_PROGRESS'
  | 'TAILORING_COMPLETED'
  | 'EXECUTE_DOM_AUTOFILL'
  | 'AUTOFILL_PROGRESS'
  | 'AUTH_STATE_CHANGED'
  | 'DISPATCH_ERROR';

export interface BaseExtensionMessage<TAction extends MessageAction, TPayload> {
  action: TAction;
  correlationId: string;
  timestamp: number;
  payload: TPayload;
}

export type JDExtractedPayload = {
  atsProvider: 'GREENHOUSE' | 'LEVER' | 'WORKDAY' | 'LINKEDIN' | 'ICIMS' | 'TALEO' | 'GENERIC';
  jobTitle: string;
  companyName: string;
  rawText: string;
  cleanedHtml: string;
  pageUrl: string;
};

export type AutofillProgressPayload = {
  taskId: string;
  fieldsCompleted: number;
  totalFields: number;
  currentFieldSelector: string;
  status: 'IN_PROGRESS' | 'COMPLETED' | 'BLOCKED';
};

export type TailoringProgressPayload = {
  taskId: string;
  stage: 'PARSING' | 'TAILORING' | 'GUARDRAIL_VERIFY' | 'TYPST_COMPILING' | 'COMPLETED';
  progressPercent: number;
  message: string;
};

export type AppExtensionMessage =
  | BaseExtensionMessage<'JD_EXTRACTED', JDExtractedPayload>
  | BaseExtensionMessage<'AUTOFILL_PROGRESS', AutofillProgressPayload>
  | BaseExtensionMessage<'TAILORING_PROGRESS', TailoringProgressPayload>
  | BaseExtensionMessage<'TRIGGER_TAILORING', { jobId?: string; customInstructions?: string }>
  | BaseExtensionMessage<'EXECUTE_DOM_AUTOFILL', { mappings: any[]; resumeDataUri?: string }>;

