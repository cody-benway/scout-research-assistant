import { useCallback, useRef, useState } from 'react'
import { fetchEventSource } from '@microsoft/fetch-event-source'
import type {
  AgentStep,
  ResearchReport,
  ResearchStatus,
  SSEEvent,
  StepType,
} from '../types'

interface UseResearchReturn {
  status: ResearchStatus
  steps: AgentStep[]
  report: ResearchReport | null
  error: string | null
  degraded: boolean
  warning: string | null
  startResearch: (query: string, maxIterations?: number) => Promise<void>
  reset: () => void
}

let _stepCounter = 0
function makeStep(type: StepType | 'warning', message: string, extras: Partial<AgentStep> = {}): AgentStep {
  return {
    id: String(++_stepCounter),
    type: type === 'warning' ? 'warning' : type,
    message,
    timestamp: new Date(),
    ...extras,
  }
}

export function useResearch(): UseResearchReturn {
  const [status, setStatus] = useState<ResearchStatus>('idle')
  const [steps, setSteps] = useState<AgentStep[]>([])
  const [report, setReport] = useState<ResearchReport | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [degraded, setDegraded] = useState(false)
  const [warning, setWarning] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  const reset = useCallback(() => {
    abortRef.current?.abort()
    setStatus('idle')
    setSteps([])
    setReport(null)
    setError(null)
    setDegraded(false)
    setWarning(null)
  }, [])

  const addStep = useCallback((step: AgentStep) => {
    setSteps(prev => [...prev, step])
  }, [])

  const startResearch = useCallback(
    async (query: string, maxIterations = 3) => {
      abortRef.current?.abort()
      const controller = new AbortController()
      abortRef.current = controller

      setStatus('running')
      setSteps([])
      setReport(null)
      setError(null)
      setDegraded(false)
      setWarning(null)

      // Step 1: POST /research to create the job
      let jobId: string
      try {
        const res = await fetch('/research', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ query, max_iterations: maxIterations }),
          signal: controller.signal,
        })
        if (!res.ok) {
          const body = await res.json().catch(() => ({}))
          throw new Error(body.detail ?? `HTTP ${res.status}`)
        }
        const data = await res.json()
        jobId = data.job_id
      } catch (err) {
        if ((err as Error).name === 'AbortError') return
        setError((err as Error).message)
        setStatus('error')
        return
      }

      // Step 2: Open SSE stream for progress events
      try {
        await fetchEventSource(`/research/${jobId}/stream`, {
          method: 'GET',
          signal: controller.signal,
          onmessage(msg) {
            if (!msg.data || msg.data.startsWith(':')) return // keepalive comment

            let event: SSEEvent
            try {
              event = JSON.parse(msg.data)
            } catch {
              return
            }

            if (event.type === 'step' || event.type === 'warning') {
              const stepType: StepType =
                event.type === 'warning'
                  ? 'warning'
                  : (event.step ?? 'planning') as StepType
              addStep(
                makeStep(stepType, event.message, {
                  queries: event.queries,
                  gaps: event.gaps,
                  iteration: event.iteration,
                }),
              )
            } else if (event.type === 'complete') {
              setReport(event.report)
              setDegraded(Boolean(event.degraded))
              setWarning(event.warning ?? null)
              if (event.degraded && event.warning) {
                addStep(makeStep('warning', event.warning))
              }
              setStatus('complete')
              controller.abort()
            } else if (event.type === 'error') {
              setError(event.message)
              setStatus('error')
              controller.abort()
            }
          },
          onerror(err) {
            if (controller.signal.aborted) return
            setError((err as Error)?.message ?? 'Stream connection error')
            setStatus('error')
            throw err // stop retrying
          },
          openWhenHidden: true,
        })
      } catch (err) {
        if (controller.signal.aborted) return
        setError((err as Error).message)
        setStatus('error')
      }
    },
    [addStep],
  )

  return { status, steps, report, error, degraded, warning, startResearch, reset }
}
