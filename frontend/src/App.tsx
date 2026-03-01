import { useResearch } from './hooks/useResearch'
import { QueryInput } from './components/QueryInput'
import { ProgressPanel } from './components/ProgressPanel'
import { ReportPanel } from './components/ReportPanel'

export default function App() {
  const { status, steps, report, error, degraded, warning, startResearch, reset } = useResearch()

  const isRunning = status === 'running'
  const hasActivity = steps.length > 0 || report !== null || status === 'error'

  return (
    <div className="min-h-screen bg-gray-950 flex flex-col">
      {/* Header */}
      <header className="border-b border-gray-800 px-6 py-4 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center">
            <ScoutLogo />
          </div>
          <div>
            <h1 className="text-sm font-semibold text-white">Scout</h1>
            <p className="text-xs text-gray-500">AI Research Assistant</p>
          </div>
        </div>

        {hasActivity && !isRunning && (
          <button
            onClick={reset}
            className="text-xs text-gray-500 hover:text-gray-300 flex items-center gap-1.5 transition-colors"
          >
            <NewIcon />
            New research
          </button>
        )}
      </header>

      {/* Query input */}
      <div className="px-6 py-5 border-b border-gray-800 shrink-0">
        <QueryInput onSubmit={startResearch} isRunning={isRunning} onStop={reset} />
      </div>

      {/* Main content: split panel */}
      <div className="flex-1 flex overflow-hidden min-h-0">
        {/* Left: Agent progress */}
        <div className="w-80 shrink-0 border-r border-gray-800 flex flex-col">
          <div className="px-4 py-3 border-b border-gray-800 flex items-center justify-between">
            <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-wide">Agent Steps</h2>
            {steps.length > 0 && (
              <span className="text-xs text-gray-600">{steps.length} steps</span>
            )}
          </div>
          <div className="flex-1 overflow-hidden">
            <ProgressPanel steps={steps} status={status} />
          </div>
        </div>

        {/* Right: Report */}
        <div className="flex-1 flex flex-col overflow-hidden">
          <div className="px-6 py-3 border-b border-gray-800 flex items-center justify-between">
            <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-wide">Research Report</h2>
            {status === 'complete' && degraded && (
              <span className="flex items-center gap-1.5 text-xs text-amber-400" title={warning ?? undefined}>
                <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
                Complete with warnings
              </span>
            )}
            {status === 'complete' && !degraded && (
              <span className="flex items-center gap-1.5 text-xs text-emerald-400">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                Complete
              </span>
            )}
            {isRunning && (
              <span className="flex items-center gap-1.5 text-xs text-blue-400">
                <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse" />
                Running
              </span>
            )}
          </div>
          <div className="flex-1 overflow-hidden">
            <ReportPanel report={report} status={status} error={error} />
          </div>
        </div>
      </div>
    </div>
  )
}

function ScoutLogo() {
  return (
    <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="m21 21-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.607 10.607Z" />
    </svg>
  )
}

function NewIcon() {
  return (
    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
    </svg>
  )
}
