import { useState, type KeyboardEvent } from 'react'
import Button from '../../CommonComponents/Button/Button'
import Dropdown from '../../CommonComponents/Dropdown/Dropdown'
import Loader from '../../CommonComponents/Loader/Loader'
import CollapsiblePanel from '../../CommonComponents/CollapsiblePanel/CollapsiblePanel'
import {
  askQuery,
  getQueryEvaluation,
  type GenerationProvider,
  type QueryEvaluationStatus,
  type RetrieveResult,
  type SearchType,
} from '../../api/client'
import './Ask.css'

// const LLM_MODEL = (import.meta.env.VITE_LLM_MODEL as string | undefined) ?? 'not configured'

const STRATEGY_OPTIONS: { label: string; value: SearchType }[] = [
  { label: 'Lexical(BM25)', value: 'bm25' },
  { label: 'Semantic', value: 'semantic' },
  { label: 'Hybrid(RRF)', value: 'hybrid_rrf' },
  { label: 'Hybrid(Weighted)', value: 'hybrid_weighted' },
]

const PROVIDER_OPTIONS: { label: string; value: GenerationProvider }[] = [
  { label: 'Local (Ollama)', value: 'ollama' },
  { label: 'OpenRouter', value: 'openrouter' },
]

function EvalSection({
  title,
  state,
  error,
  metrics,
}: {
  title: string
  state: QueryEvaluationStatus['state']
  error: string | null
  metrics: { label: string; value: number | null }[]
}) {
  return (
    <div className="ask-page__eval-section">
      <p className="ask-page__eval-section-title">{title}</p>
      {state === 'Done' ? (
        <ul className="ask-page__eval-list">
          {metrics.map((m) => (
            <li key={m.label}>
              <strong>{m.label}</strong>
              <span>{m.value?.toFixed(4)}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="ask-page__eval-pending-text">
          {state === 'Error' ? `Failed: ${error ?? 'unknown error'}` : 'Evaluating…'}
        </p>
      )}
    </div>
  )
}

function Ask() {
  const [searchType, setSearchType] = useState<SearchType>('hybrid_rrf')
  const [weight, setWeight] = useState(0.5)
  const [provider, setProvider] = useState<GenerationProvider>('ollama')
  const [evaluationEnabled, setEvaluationEnabled] = useState(false)
  const [rerankEnabled, setRerankEnabled] = useState(false)
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
          ? {
              search_type: searchType,
              query,
              weight,
              evaluation: evaluationEnabled,
              provider,
              rerank: rerankEnabled,
            }
          : {
              search_type: searchType,
              query,
              evaluation: evaluationEnabled,
              provider,
              rerank: rerankEnabled,
            }
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
    const stillPending =
      !evaluationStatus ||
      evaluationStatus.state === 'Progress' ||
      evaluationStatus.judge_state === 'Progress'
    if (open && evaluationId && stillPending) {
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
      {/* <p className="ask-page__subheading">LLM: {LLM_MODEL}</p> */}

      <div className="ask-page__config">
        <div className="ask-page__config-row">
          <Dropdown
            options={STRATEGY_OPTIONS}
            value={searchType}
            onChange={(event) => setSearchType(event.target.value as SearchType)}
            aria-label="Retrieval strategy"
          />

          <Dropdown
            options={PROVIDER_OPTIONS}
            value={provider}
            onChange={(event) => setProvider(event.target.value as GenerationProvider)}
            aria-label="Generation provider"
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

          <label className="ask-page__eval-toggle">
            <input
              type="checkbox"
              checked={rerankEnabled}
              onChange={(event) => setRerankEnabled(event.target.checked)}
            />
            Rerank with Jev
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
                <div className="ask-page__eval-header">
                  {(evaluationStatus?.state === 'Progress' || evaluationStatus?.judge_state === 'Progress') && (
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
                  )}
                </div>

                <EvalSection
                  title="Semantic (embedding-based)"
                  state={evaluationStatus?.state ?? 'Progress'}
                  error={evaluationStatus?.error ?? null}
                  metrics={[
                    { label: 'Faithfulness', value: evaluationStatus?.faithfulness ?? null },
                    { label: 'Answer relevancy', value: evaluationStatus?.answer_relevancy ?? null },
                  ]}
                />

                <EvalSection
                  title="Jev Judge (typesafe/jev-1.13)"
                  state={evaluationStatus?.judge_state ?? 'Progress'}
                  error={evaluationStatus?.judge_error ?? null}
                  metrics={[
                    { label: 'Faithfulness', value: evaluationStatus?.judge_faithfulness ?? null },
                    { label: 'Answer relevancy', value: evaluationStatus?.judge_answer_relevancy ?? null },
                  ]}
                />
              </CollapsiblePanel>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export default Ask
