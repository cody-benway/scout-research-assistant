import ReactMarkdown from 'react-markdown'
import type { ResearchReport, ResearchStatus } from '../types'

interface ReportPanelProps {
  report: ResearchReport | null
  status: ResearchStatus
  error: string | null
}

export function ReportPanel({ report, status, error }: ReportPanelProps) {
  if (error && status === 'error') {
    return (
      <div className="h-full flex flex-col items-center justify-center p-8 text-center">
        <div className="w-12 h-12 rounded-xl bg-red-950 border border-red-900 flex items-center justify-center mb-4">
          <ErrorIcon />
        </div>
        <h3 className="text-red-400 font-medium mb-2">Research failed</h3>
        <p className="text-gray-500 text-sm max-w-sm">{error}</p>
      </div>
    )
  }

  if (!report) {
    return (
      <div className="h-full flex flex-col items-center justify-center p-8 text-center">
        <div className="w-16 h-16 rounded-2xl bg-gray-800 flex items-center justify-center mb-4">
          {status === 'running' ? <SpinnerIcon /> : <ReportIcon />}
        </div>
        <h3 className="text-gray-400 font-medium mb-2">
          {status === 'running' ? 'Generating report...' : 'Report will appear here'}
        </h3>
        <p className="text-gray-600 text-sm max-w-xs">
          {status === 'running'
            ? 'Scout is synthesizing its findings into a structured report.'
            : 'The final research report with citations will be displayed here when complete.'}
        </p>
      </div>
    )
  }

  function handleExport() {
    const md = buildMarkdown(report!)
    const blob = new Blob([md], { type: 'text/markdown' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `scout-report-${Date.now()}.md`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="h-full overflow-y-auto">
      <div className="px-6 py-5 space-y-6 animate-fade-in">
        {/* Header */}
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-xl font-semibold text-white leading-snug">{report.title}</h1>
          </div>
          <button
            onClick={handleExport}
            className="shrink-0 flex items-center gap-1.5 px-3 py-1.5 bg-gray-800 hover:bg-gray-700 border border-gray-700 text-gray-300 hover:text-white rounded-lg text-xs font-medium transition-all"
          >
            <DownloadIcon />
            Export
          </button>
        </div>

        {/* Summary */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
          <p className="text-sm text-gray-300 leading-relaxed">{report.summary}</p>
        </div>

        {/* Key findings */}
        {report.key_findings.length > 0 && (
          <div>
            <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-3">
              Key Findings
            </h2>
            <ul className="space-y-2">
              {report.key_findings.map((finding, i) => (
                <li key={i} className="flex items-start gap-3">
                  <span className="shrink-0 w-5 h-5 rounded-full bg-blue-950 border border-blue-800 text-blue-400 text-xs flex items-center justify-center font-semibold mt-0.5">
                    {i + 1}
                  </span>
                  <span className="text-sm text-gray-300 leading-relaxed">{finding}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Sections */}
        {report.sections.map((section, i) => (
          <div key={i}>
            <h2 className="text-base font-semibold text-white mb-3 pb-2 border-b border-gray-800">
              {section.heading}
            </h2>
            <div className="prose-report text-sm">
              <ReactMarkdown>{section.content}</ReactMarkdown>
            </div>
          </div>
        ))}

        {/* Conclusion */}
        {report.conclusion && (
          <div>
            <h2 className="text-base font-semibold text-white mb-3 pb-2 border-b border-gray-800">
              Conclusion
            </h2>
            <p className="text-sm text-gray-300 leading-relaxed">{report.conclusion}</p>
          </div>
        )}

        {/* Citations */}
        {report.citations.length > 0 && (
          <div>
            <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-3">
              Sources
            </h2>
            <ol className="space-y-2">
              {report.citations.map(citation => (
                <li key={citation.index} className="flex items-start gap-3 group">
                  <span className="shrink-0 text-xs text-gray-600 font-mono mt-0.5 w-5 text-right">
                    [{citation.index}]
                  </span>
                  <a
                    href={citation.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm text-blue-400 hover:text-blue-300 underline underline-offset-2 leading-snug break-all transition-colors"
                  >
                    {citation.title || citation.url}
                  </a>
                </li>
              ))}
            </ol>
          </div>
        )}
      </div>
    </div>
  )
}

function buildMarkdown(report: ResearchReport): string {
  const lines: string[] = []
  lines.push(`# ${report.title}`, '')
  lines.push(`## Summary`, '', report.summary, '')

  if (report.key_findings.length > 0) {
    lines.push(`## Key Findings`, '')
    report.key_findings.forEach((f, i) => lines.push(`${i + 1}. ${f}`))
    lines.push('')
  }

  report.sections.forEach(s => {
    lines.push(`## ${s.heading}`, '', s.content, '')
  })

  if (report.conclusion) {
    lines.push(`## Conclusion`, '', report.conclusion, '')
  }

  if (report.citations.length > 0) {
    lines.push(`## Sources`, '')
    report.citations.forEach(c => lines.push(`[${c.index}] [${c.title || c.url}](${c.url})`))
  }

  return lines.join('\n')
}

// --- Icons ---

function ReportIcon() {
  return (
    <svg className="w-8 h-8 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z" />
    </svg>
  )
}

function SpinnerIcon() {
  return (
    <svg className="w-8 h-8 text-blue-500 animate-spin" fill="none" viewBox="0 0 24 24">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 0 1 8-8V0C5.373 0 0 5.373 0 12h4z" />
    </svg>
  )
}

function ErrorIcon() {
  return (
    <svg className="w-6 h-6 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-9 3.75h.008v.008H12v-.008Z" />
    </svg>
  )
}

function DownloadIcon() {
  return (
    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5M16.5 12 12 16.5m0 0L7.5 12m4.5 4.5V3" />
    </svg>
  )
}
