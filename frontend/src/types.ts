export type StepType = 'planning' | 'searching' | 'extracting' | 'synthesizing' | 'reflecting' | 'warning'

export interface AgentStep {
  id: string
  type: StepType
  message: string
  timestamp: Date
  queries?: string[]
  gaps?: string[]
  iteration?: number
}

export interface ReportSection {
  heading: string
  content: string
}

export interface ReportCitation {
  index: number
  title: string
  url: string
}

export interface ResearchReport {
  title: string
  summary: string
  key_findings: string[]
  sections: ReportSection[]
  conclusion: string
  citations: ReportCitation[]
}

export type ResearchStatus = 'idle' | 'running' | 'complete' | 'error'

export interface ResearchState {
  status: ResearchStatus
  jobId: string | null
  steps: AgentStep[]
  report: ResearchReport | null
  error: string | null
}

// SSE event shapes from the backend
export interface SSEStepEvent {
  type: 'step' | 'warning'
  step?: StepType
  message: string
  queries?: string[]
  gaps?: string[]
  iteration?: number
}

export interface SSECompleteEvent {
  type: 'complete'
  report: ResearchReport
  degraded?: boolean
  warning?: string | null
}

export interface SSEErrorEvent {
  type: 'error'
  message: string
}

export type SSEEvent = SSEStepEvent | SSECompleteEvent | SSEErrorEvent
