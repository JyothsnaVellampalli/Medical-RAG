import { useState, type KeyboardEvent } from 'react'
import Button from '../../CommonComponents/Button/Button'
import Dropdown from '../../CommonComponents/Dropdown/Dropdown'
import Loader from '../../CommonComponents/Loader/Loader'
import CollapsiblePanel from '../../CommonComponents/CollapsiblePanel/CollapsiblePanel'
import {
  askQuery,
  getQueryEvaluation,
  type QueryEvaluationStatus,
  type RetrieveResult,
  type SearchType,
} from '../../api/client'
import './Ask.css'

const LLM_MODEL = (import.meta.env.VITE_LLM_MODEL as string | undefined) ?? 'not configured'

const STRATEGY_OPTIONS: { label: string; value: SearchType }[] = [
  { label: 'Lexical(BM25)', value: 'bm25' },
  { label: 'Semantic', value: 'semantic' },
  { label: 'Hybrid(RRF)', value: 'hybrid_rrf' },
  { label: 'Hybrid(Weighted)', value: 'hybrid_weighted' },
]

function Ask() {
  const [searchType, setSearchType] = useState<SearchType>('hybrid_rrf')
  const [weight, setWeight] = useState(0.5)
  const [evaluationEnabled, setEvaluationEnabled] = useState(false)
  const [query, setQuery] = useState('')
  const [answer, setAnswer] = useState<string | null>(null)
  const [citations, setCitations] = useState<RetrieveResult[]>([])
  const [latencySeconds, setLatencySeconds] = useState<number | null>(null)
  const [evaluationId, setEvaluationId] = useState<string | null>(null)
  const [evaluationStatus, setEvaluationStatus] = useState<QueryEvaluationStatus | null>(null)
  const [evaluationFetching, setEvaluationFetching] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit() {
    if (!query.trim()) return
    setLoading(true)
    setError(null)
    setEvaluationId(null)
    setEvaluationStatus(null)
    try {
      const payload =
        searchType === 'hybrid_weighted'
          ? { search_type: searchType, query, weight, evaluation: evaluationEnabled }
          : { search_type: searchType, query, evaluation: evaluationEnabled }
      const result = await askQuery(payload)
      setAnswer(result.response)
      setCitations(result.citations)
      setLatencySeconds(result.latency_seconds)
      setEvaluationId(result.evaluation_id)
    } catch {
      setError('Could not get an answer. Is the backend (and Ollama) running?')
    } finally {
      setLoading(false)
    }
  }

  async function fetchEvaluation(id: string) {
    setEvaluationFetching(true)
    try {
      const status = await getQueryEvaluation(id)
      setEvaluationStatus(status)
    } catch {
      // transient fetch failure -- leave previous status, user can retry via the refresh button
    } finally {
      setEvaluationFetching(false)
    }
  }

  function handleEvaluationToggle(open: boolean) {
    if (open && evaluationId && evaluationStatus?.state !== 'Done') {
      void fetchEvaluation(evaluationId)
    }
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'Enter') {
      handleSubmit()
    }
  }

  return (
    <div className="ask-page">
      <h1>Ask your query</h1>
      <p className="ask-page__subheading">LLM: {LLM_MODEL}</p>

      <div className="ask-page__config">
        <div className="ask-page__config-row">
          <Dropdown
            options={STRATEGY_OPTIONS}
            value={searchType}
            onChange={(event) => setSearchType(event.target.value as SearchType)}
            aria-label="Retrieval strategy"
          />

          {searchType === 'hybrid_weighted' && (
            <div className="ask-page__weight">
              <label htmlFor="ask-weight-slider">
                Semantic weight: {weight.toFixed(2)} &nbsp;|&nbsp; BM25 weight: {(1 - weight).toFixed(2)}
              </label>
              <input
                id="ask-weight-slider"
                type="range"
                min={0}
                max={1}
                step={0.05}
                value={weight}
                onChange={(event) => setWeight(Number(event.target.value))}
              />
            </div>
          )}

          <label className="ask-page__eval-toggle">
            <input
              type="checkbox"
              checked={evaluationEnabled}
              onChange={(event) => setEvaluationEnabled(event.target.checked)}
            />
            Evaluate this response
          </label>
        </div>

        <div className="ask-page__search">
          <input
            type="text"
            className="ask-page__search-box"
            placeholder="Ask a question about the corpus…"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={handleKeyDown}
          />
          <Button onClick={handleSubmit} disabled={loading || !query.trim()}>
            Submit
          </Button>
        </div>
      </div>

      {loading && <Loader label="Generating answer…" />}
      {error && <p className="ask-page__notice">{error}</p>}

      {!loading && answer && (
        <div className="ask-page__response">
          <div className="ask-page__answer">{answer}</div>
          {latencySeconds !== null && (
            <p className="ask-page__latency">Answered in {latencySeconds.toFixed(2)}s</p>
          )}

          <div className="ask-page__panels">
            <CollapsiblePanel title={`Citations (${citations.length})`}>
              <ul className="ask-page__citation-list">
                {citations.map((c) => (
                  <li key={c.chunk_id}>
                    <strong>{c.chunk_id}</strong>
                    <p>{c.text}</p>
                  </li>
                ))}
              </ul>
            </CollapsiblePanel>

            {evaluationId && (
              <CollapsiblePanel title="Evaluation" defaultOpen={false} onToggle={handleEvaluationToggle}>
                {evaluationStatus?.state === 'Done' ? (
                  <ul className="ask-page__eval-list">
                    <li>
                      <strong>Faithfulness</strong>
                      <span>{evaluationStatus.faithfulness?.toFixed(4)}</span>
                    </li>
                    <li>
                      <strong>Answer relevancy</strong>
                      <span>{evaluationStatus.answer_relevancy?.toFixed(4)}</span>
                    </li>
                  </ul>
                ) : (
                  <div className="ask-page__eval-pending">
                    <span>
                      {evaluationStatus?.state === 'Error'
                        ? `Evaluation failed: ${evaluationStatus.error ?? 'unknown error'}`
                        : 'Evaluating…'}
                    </span>
                    <button
                      type="button"
                      className="ask-page__eval-refresh"
                      aria-label="Refresh evaluation status"
                      title="Refresh evaluation status"
                      onClick={() => void fetchEvaluation(evaluationId)}
                      disabled={evaluationFetching}
                    >
                      ⟳
                    </button>
                  </div>
                )}
              </CollapsiblePanel>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export default Ask
