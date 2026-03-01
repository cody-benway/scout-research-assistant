import { useEffect, useRef } from 'react'
import type { AgentStep, ResearchStatus, StepType } from '../types'

interface ProgressPanelProps {
  steps: AgentStep[]
  status: ResearchStatus
}

const STEP_CONFIG: Record<StepType, { label: string; color: string; icon: React.ReactNode }> = {
  planning: {
    label: 'Planning',
    color: 'text-purple-400',
    icon: <BrainIcon />,
  },
  searching: {
    label: 'Searching',
    color: 'text-blue-400',
    icon: <SearchIcon />,
  },
  extracting: {
    label: 'Reading',
    color: 'text-cyan-400',
    icon: <DocumentIcon />,
  },
  synthesizing: {
    label: 'Synthesizing',
    color: 'text-emerald-400',
    icon: <SparklesIcon />,
  },
  reflecting: {
    label: 'Reflecting',
    color: 'text-amber-400',
    icon: <ReflectIcon />,
  },
  warning: {
    label: 'Warning',
    color: 'text-orange-400',
    icon: <WarningIcon />,
  },
}

export function ProgressPanel({ steps, status }: ProgressPanelProps) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [steps.length])

  if (steps.length === 0 && status === 'idle') {
    return (
      <div className="h-full flex flex-col items-center justify-center text-center p-8">
        <div className="w-16 h-16 rounded-2xl bg-gray-800 flex items-center justify-center mb-4">
          <AgentIcon />
        </div>
        <h3 className="text-gray-400 font-medium mb-2">Agent steps will appear here</h3>
        <p className="text-gray-600 text-sm max-w-xs">
          Scout will show you its reasoning process in real time as it researches your topic.
        </p>
      </div>
    )
  }

  return (
    <div className="h-full overflow-y-auto px-4 py-4 space-y-2">
      {steps.map(step => (
        <StepCard key={step.id} step={step} />
      ))}

      {status === 'running' && (
        <div className="flex items-center gap-3 px-3 py-2.5 animate-pulse-slow">
          <div className="flex gap-1">
            <span className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
            <span className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
            <span className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
          </div>
          <span className="text-xs text-gray-500">Working...</span>
        </div>
      )}

      {status === 'complete' && (
        <div className="flex items-center gap-2 px-3 py-2.5 text-emerald-400 animate-fade-in">
          <CheckIcon />
          <span className="text-xs font-medium">Research complete</span>
        </div>
      )}

      {status === 'error' && (
        <div className="flex items-center gap-2 px-3 py-2.5 text-red-400 animate-fade-in">
          <ErrorIcon />
          <span className="text-xs font-medium">Research stopped with an error</span>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  )
}

function StepCard({ step }: { step: AgentStep }) {
  const config = STEP_CONFIG[step.type] ?? STEP_CONFIG.planning

  return (
    <div className="flex gap-3 group animate-slide-in">
      <div className={`mt-0.5 shrink-0 ${config.color}`}>{config.icon}</div>
      <div className="flex-1 min-w-0">
        <div className="flex items-baseline gap-2">
          <span className={`text-xs font-semibold uppercase tracking-wide ${config.color}`}>
            {config.label}
          </span>
          {step.iteration !== undefined && (
            <span className="text-xs text-gray-600">iter {step.iteration}</span>
          )}
          <span className="text-xs text-gray-700 ml-auto shrink-0">
            {step.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
          </span>
        </div>
        <p className="text-sm text-gray-300 mt-0.5 leading-snug">{step.message}</p>

        {step.queries && step.queries.length > 0 && (
          <ul className="mt-1.5 space-y-1">
            {step.queries.map((q, i) => (
              <li key={i} className="flex items-start gap-1.5 text-xs text-gray-500">
                <span className="text-gray-700 shrink-0 mt-0.5">→</span>
                <span>{q}</span>
              </li>
            ))}
          </ul>
        )}

        {step.gaps && step.gaps.length > 0 && (
          <ul className="mt-1.5 space-y-1">
            {step.gaps.map((g, i) => (
              <li key={i} className="flex items-start gap-1.5 text-xs text-amber-600">
                <span className="shrink-0 mt-0.5">⚠</span>
                <span>{g}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}

// --- Icons ---

function BrainIcon() {
  return (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 0 0-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 0 0 3.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 0 0 3.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 0 0-3.09 3.09ZM18.259 8.715 18 9.75l-.259-1.035a3.375 3.375 0 0 0-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 0 0 2.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 0 0 2.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 0 0-2.456 2.456ZM16.894 20.567 16.5 21.75l-.394-1.183a2.25 2.25 0 0 0-1.423-1.423L13.5 18.75l1.183-.394a2.25 2.25 0 0 0 1.423-1.423l.394-1.183.394 1.183a2.25 2.25 0 0 0 1.423 1.423l1.183.394-1.183.394a2.25 2.25 0 0 0-1.423 1.423Z" />
    </svg>
  )
}

function SearchIcon() {
  return (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="m21 21-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.607 10.607Z" />
    </svg>
  )
}

function DocumentIcon() {
  return (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z" />
    </svg>
  )
}

function SparklesIcon() {
  return (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 0 0-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 0 0 3.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 0 0 3.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 0 0-3.09 3.09Z" />
    </svg>
  )
}

function ReflectIcon() {
  return (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0 3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182m0-4.991v4.99" />
    </svg>
  )
}

function WarningIcon() {
  return (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
    </svg>
  )
}

function AgentIcon() {
  return (
    <svg className="w-8 h-8 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 3v1.5M4.5 8.25H3m18 0h-1.5M4.5 12H3m18 0h-1.5m-15 3.75H3m18 0h-1.5M8.25 19.5V21M12 3v1.5m0 15V21m3.75-18v1.5m0 15V21m-9-1.5h10.5a2.25 2.25 0 0 0 2.25-2.25V6.75a2.25 2.25 0 0 0-2.25-2.25H6.75A2.25 2.25 0 0 0 4.5 6.75v10.5a2.25 2.25 0 0 0 2.25 2.25Zm.75-12h9v9h-9v-9Z" />
    </svg>
  )
}

function CheckIcon() {
  return (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="m4.5 12.75 6 6 9-13.5" />
    </svg>
  )
}

function ErrorIcon() {
  return (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
    </svg>
  )
}
