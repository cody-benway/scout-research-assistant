import { useState, type FormEvent, type KeyboardEvent } from 'react'

interface QueryInputProps {
  onSubmit: (query: string, maxIterations: number) => void
  isRunning: boolean
  onStop: () => void
}

const EXAMPLE_QUERIES = [
  'What are the latest developments in quantum computing?',
  'How does the US Federal Reserve control inflation?',
  'What are the environmental impacts of lithium mining?',
  'Explain the current state of fusion energy research',
]

export function QueryInput({ onSubmit, isRunning, onStop }: QueryInputProps) {
  const [query, setQuery] = useState('')
  const [maxIterations, setMaxIterations] = useState(3)
  const [showSettings, setShowSettings] = useState(false)

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!query.trim() || isRunning) return
    onSubmit(query.trim(), maxIterations)
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      e.preventDefault()
      if (!query.trim() || isRunning) return
      onSubmit(query.trim(), maxIterations)
    }
  }

  return (
    <div className="w-full max-w-3xl mx-auto">
      <form onSubmit={handleSubmit} className="space-y-3">
        <div className="relative">
          <textarea
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask Scout to research any topic..."
            disabled={isRunning}
            rows={3}
            className="w-full bg-gray-900 border border-gray-700 rounded-xl px-4 py-3 pr-28 text-gray-100 placeholder-gray-500 resize-none focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all disabled:opacity-60 disabled:cursor-not-allowed text-sm leading-relaxed"
          />
          <div className="absolute bottom-3 right-3 flex items-center gap-2">
            {isRunning ? (
              <button
                type="button"
                onClick={onStop}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-red-600 hover:bg-red-500 text-white rounded-lg text-xs font-medium transition-colors"
              >
                <StopIcon />
                Stop
              </button>
            ) : (
              <button
                type="submit"
                disabled={!query.trim()}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:cursor-not-allowed text-white rounded-lg text-xs font-medium transition-colors"
              >
                <SearchIcon />
                Research
              </button>
            )}
          </div>
        </div>

        <div className="flex items-center justify-between">
          <div className="flex flex-wrap gap-2">
            {EXAMPLE_QUERIES.map(q => (
              <button
                key={q}
                type="button"
                disabled={isRunning}
                onClick={() => setQuery(q)}
                className="text-xs text-gray-500 hover:text-gray-300 bg-gray-900 hover:bg-gray-800 border border-gray-800 hover:border-gray-700 rounded-full px-3 py-1 transition-all disabled:opacity-40 disabled:cursor-not-allowed truncate max-w-[200px]"
              >
                {q}
              </button>
            ))}
          </div>

          <button
            type="button"
            onClick={() => setShowSettings(s => !s)}
            className="text-xs text-gray-500 hover:text-gray-300 flex items-center gap-1 transition-colors shrink-0 ml-2"
          >
            <SettingsIcon />
            Settings
          </button>
        </div>

        {showSettings && (
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 space-y-3 animate-fade-in">
            <div className="flex items-center justify-between">
              <div>
                <label className="text-sm font-medium text-gray-300">Research depth</label>
                <p className="text-xs text-gray-500 mt-0.5">
                  Number of search-and-reflect iterations (more = deeper, slower)
                </p>
              </div>
              <div className="flex items-center gap-2">
                {[1, 2, 3].map(n => (
                  <button
                    key={n}
                    type="button"
                    onClick={() => setMaxIterations(n)}
                    className={`w-8 h-8 rounded-lg text-sm font-medium transition-colors ${
                      maxIterations === n
                        ? 'bg-blue-600 text-white'
                        : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
                    }`}
                  >
                    {n}
                  </button>
                ))}
              </div>
            </div>
            <p className="text-xs text-gray-600">
              Tip: Press <kbd className="bg-gray-800 text-gray-400 px-1.5 py-0.5 rounded text-xs">⌘ Enter</kbd> to submit
            </p>
          </div>
        )}
      </form>
    </div>
  )
}

function SearchIcon() {
  return (
    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="m21 21-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.607 10.607Z" />
    </svg>
  )
}

function StopIcon() {
  return (
    <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 24 24">
      <rect x="6" y="6" width="12" height="12" rx="2" />
    </svg>
  )
}

function SettingsIcon() {
  return (
    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M10.343 3.94c.09-.542.56-.94 1.11-.94h1.093c.55 0 1.02.398 1.11.94l.149.894c.07.424.384.764.78.93.398.164.855.142 1.205-.108l.737-.527a1.125 1.125 0 0 1 1.45.12l.773.774c.39.389.44 1.002.12 1.45l-.527.737c-.25.35-.272.806-.107 1.204.165.397.505.71.93.78l.893.15c.543.09.94.559.94 1.109v1.094c0 .55-.397 1.02-.94 1.11l-.894.149c-.424.07-.764.383-.929.78-.165.398-.143.854.107 1.204l.527.738c.32.447.269 1.06-.12 1.45l-.774.773a1.125 1.125 0 0 1-1.449.12l-.738-.527c-.35-.25-.806-.272-1.203-.107-.398.165-.71.505-.781.929l-.149.894c-.09.542-.56.94-1.11.94h-1.094c-.55 0-1.019-.398-1.11-.94l-.148-.894c-.071-.424-.384-.764-.781-.93-.398-.164-.854-.142-1.204.108l-.738.527c-.447.32-1.06.269-1.45-.12l-.773-.774a1.125 1.125 0 0 1-.12-1.45l.527-.737c.25-.35.272-.806.108-1.204-.165-.397-.506-.71-.93-.78l-.894-.15c-.542-.09-.94-.56-.94-1.109v-1.094c0-.55.398-1.02.94-1.11l.894-.149c.424-.07.765-.383.93-.78.165-.398.143-.854-.108-1.204l-.526-.738a1.125 1.125 0 0 1 .12-1.45l.773-.773a1.125 1.125 0 0 1 1.45-.12l.737.527c.35.25.807.272 1.204.107.397-.165.71-.505.78-.929l.15-.894Z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" />
    </svg>
  )
}
