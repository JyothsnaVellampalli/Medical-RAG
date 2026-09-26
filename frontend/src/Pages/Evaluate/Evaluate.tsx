import { useEffect, useState, useCallback } from 'react'
import Button from '../../CommonComponents/Button/Button'
import Modal from '../../CommonComponents/Modal/Modal'
import Loader from '../../CommonComponents/Loader/Loader'
import Table, { type TableColumn } from '../../CommonComponents/Table/Table'
import Dropdown from '../../CommonComponents/Dropdown/Dropdown'
import {
  startEvaluation,
  getEvals,
  getEvalResults,
  type SearchType,
  type EvalJob,
  type MechanismMetrics,
  type EvalResultDetail,
} from '../../api/client'
import './Evaluate.css'

const MECHANISM_OPTIONS: { label: string; value: SearchType }[] = [
  { label: 'Lexical(BM25)', value: 'bm25' },
  { label: 'Semantic', value: 'semantic' },
  { label: 'Hybrid(RRF)', value: 'hybrid_rrf' },
  { label: 'Hybrid(Weighted)', value: 'hybrid_weighted' },
]

const MECHANISM_FILTER_OPTIONS = [{ label: 'All mechanisms', value: '' }, ...MECHANISM_OPTIONS]

const POLL_INTERVAL_MS = 15000

function formatScore(value: number | null): string {
  return value === null ? '—' : value.toFixed(3)
}

const METRICS_COLUMNS: TableColumn<MechanismMetrics>[] = [
  { key: 'retrieval_mechanism', header: 'Mechanism' },
  { key: 'num_questions', header: 'Questions' },
  { key: 'avg_precision_at_k', header: 'Precision@k', render: (r) => formatScore(r.avg_precision_at_k) },
  { key: 'avg_recall_at_k', header: 'Recall@k', render: (r) => formatScore(r.avg_recall_at_k) },
  { key: 'avg_mrr', header: 'MRR', render: (r) => formatScore(r.avg_mrr) },
  { key: 'avg_ndcg_at_k', header: 'nDCG@k', render: (r) => formatScore(r.avg_ndcg_at_k) },
  { key: 'avg_faithfulness', header: 'Faithfulness', render: (r) => formatScore(r.avg_faithfulness) },
  { key: 'avg_answer_relevancy', header: 'Relevancy', render: (r) => formatScore(r.avg_answer_relevancy) },
  { key: 'avg_answer_correctness', header: 'Correctness', render: (r) => formatScore(r.avg_answer_correctness) },
  {
    key: 'avg_latency_seconds',
    header: 'Avg latency',
    render: (r) => (r.avg_latency_seconds === null ? '—' : `${r.avg_latency_seconds.toFixed(1)}s`),
  },
  { key: 'error_count', header: 'Errors' },
]

const RESULT_COLUMNS: TableColumn<EvalResultDetail>[] = [
  { key: 'hf_qa_id', header: 'HF QA ID' },
  { key: 'retrieval_mechanism', header: 'Mechanism' },
  { key: 'question', header: 'Question' },
  { key: 'precision_at_k', header: 'Precision@k', render: (r) => formatScore(r.precision_at_k) },
  { key: 'recall_at_k', header: 'Recall@k', render: (r) => formatScore(r.recall_at_k) },
  { key: 'mrr', header: 'MRR', render: (r) => formatScore(r.mrr) },
  { key: 'ndcg_at_k', header: 'nDCG@k', render: (r) => formatScore(r.ndcg_at_k) },
  { key: 'faithfulness', header: 'Faithfulness', render: (r) => formatScore(r.faithfulness) },
  { key: 'answer_relevancy', header: 'Relevancy', render: (r) => formatScore(r.answer_relevancy) },
  { key: 'answer_correctness', header: 'Correctness', render: (r) => formatScore(r.answer_correctness) },
  {
    key: 'latency_seconds',
    header: 'Latency',
    render: (r) => (r.latency_seconds === null ? '—' : `${r.latency_seconds.toFixed(1)}s`),
  },
  {
    key: 'error',
    header: 'Error',
    render: (r) => (r.error ? <span className="evaluate-page__result-error">{r.error}</span> : '—'),
  },
]

function Evaluate() {
  const [modalOpen, setModalOpen] = useState(false)
  const [testDataSize, setTestDataSize] = useState(30)
  const [selectedMechanisms, setSelectedMechanisms] = useState<SearchType[]>(['bm25', 'semantic'])
  const [jobs, setJobs] = useState<EvalJob[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [expandedJobId, setExpandedJobId] = useState<string | null>(null)
  const [resultsByJob, setResultsByJob] = useState<Record<string, EvalResultDetail[]>>({})
  const [resultsLoading, setResultsLoading] = useState<string | null>(null)
  const [resultsError, setResultsError] = useState<string | null>(null)
  const [mechanismFilter, setMechanismFilter] = useState<SearchType | ''>('')
  const [hfQaIdFilter, setHfQaIdFilter] = useState('')

  const loadJobs = useCallback(async () => {
    try {
      const result = await getEvals()
      setJobs(result)
      setError(null)
    } catch {
      setError('Could not load evaluations. Is the backend running?')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    // Standard fetch-on-mount: loadJobs awaits before setting state, so this
    // isn't actually synchronous -- the lint rule can't see past the await.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadJobs()
  }, [loadJobs])

  useEffect(() => {
    const hasRunningJob = jobs.some((j) => j.state === 'Progress')
    if (!hasRunningJob) return
    const interval = setInterval(loadJobs, POLL_INTERVAL_MS)
    return () => clearInterval(interval)
  }, [jobs, loadJobs])

  function toggleMechanism(value: SearchType) {
    setSelectedMechanisms((prev) =>
      prev.includes(value) ? prev.filter((m) => m !== value) : [...prev, value],
    )
  }

  async function handleStartEvaluation() {
    setModalOpen(false)
    try {
      const result = await startEvaluation({ mechanisms: selectedMechanisms, test_size: testDataSize })
      setNotice(
        `Evaluation started (job ${result.job_id.slice(0, 8)}…). This runs in the background and ` +
          `can take a while — this page refreshes automatically while it's running.`,
      )
      loadJobs()
    } catch {
      setNotice('Could not start evaluation. Is the backend running?')
    }
  }

  async function handleToggleExpand(jobId: string) {
    if (expandedJobId === jobId) {
      setExpandedJobId(null)
      return
    }
    setExpandedJobId(jobId)
    setMechanismFilter('')
    setHfQaIdFilter('')
    if (resultsByJob[jobId]) return
    setResultsLoading(jobId)
    setResultsError(null)
    try {
      const results = await getEvalResults(jobId)
      setResultsByJob((prev) => ({ ...prev, [jobId]: results }))
    } catch {
      setResultsError('Could not load per-question results. Is the backend running?')
    } finally {
      setResultsLoading(null)
    }
  }

  function filterResults(results: EvalResultDetail[]): EvalResultDetail[] {
    return results.filter((r) => {
      if (mechanismFilter && r.retrieval_mechanism !== mechanismFilter) return false
      if (hfQaIdFilter.trim() && String(r.hf_qa_id) !== hfQaIdFilter.trim()) return false
      return true
    })
  }

  return (
    <div className="evaluate-page">
      <div className="evaluate-page__header">
        <h1>Evaluate</h1>
        <Button onClick={() => setModalOpen(true)}>Evaluate</Button>
      </div>

      {notice && <p className="evaluate-page__notice">{notice}</p>}
      {error && <p className="evaluate-page__notice">{error}</p>}
      {loading && <Loader label="Loading evaluations…" />}

      {!loading && !error && jobs.length === 0 && (
        <p className="evaluate-page__empty">
          No evaluations run yet. Click Evaluate to configure and run one — results will compare
          retrieval mechanisms so you can identify the best one for this dataset.
        </p>
      )}

      {!loading &&
        jobs.map((job) => (
          <div key={job.job_id} className="evaluate-page__job">
            <div className="evaluate-page__job-header">
              <span className="evaluate-page__job-id">{job.job_id.slice(0, 8)}…</span>
              <span className={`evaluate-page__job-state evaluate-page__job-state--${job.state.toLowerCase()}`}>
                {job.state}
              </span>
              <span className="evaluate-page__job-meta">
                {job.test_size} questions × {job.mechanisms.length} mechanism(s) — started{' '}
                {new Date(job.started_at).toLocaleString()}
              </span>
            </div>
            {job.metrics.length > 0 ? (
              <>
                <Table
                  columns={METRICS_COLUMNS}
                  rows={job.metrics}
                  getRowKey={(r) => r.retrieval_mechanism}
                />
                <button
                  className="evaluate-page__expand-toggle"
                  onClick={() => handleToggleExpand(job.job_id)}
                >
                  {expandedJobId === job.job_id ? '▲ Hide' : '▼ Show'} per-question details
                </button>
                {expandedJobId === job.job_id && (
                  <div className="evaluate-page__question-details">
                    {resultsLoading === job.job_id && <Loader label="Loading per-question results…" />}
                    {resultsError && <p className="evaluate-page__notice">{resultsError}</p>}
                    {resultsByJob[job.job_id] && (
                      <>
                        <div className="evaluate-page__filters">
                          <label className="evaluate-page__filter">
                            <span>Mechanism</span>
                            <Dropdown
                              options={MECHANISM_FILTER_OPTIONS}
                              value={mechanismFilter}
                              onChange={(event) => setMechanismFilter(event.target.value as SearchType | '')}
                            />
                          </label>
                          <label className="evaluate-page__filter">
                            <span>HF QA ID</span>
                            <input
                              type="number"
                              placeholder="e.g. 204"
                              value={hfQaIdFilter}
                              onChange={(event) => setHfQaIdFilter(event.target.value)}
                            />
                          </label>
                          {(mechanismFilter || hfQaIdFilter) && (
                            <button
                              className="evaluate-page__filter-clear"
                              onClick={() => {
                                setMechanismFilter('')
                                setHfQaIdFilter('')
                              }}
                            >
                              Clear filters
                            </button>
                          )}
                        </div>
                        <Table
                          columns={RESULT_COLUMNS}
                          rows={filterResults(resultsByJob[job.job_id])}
                          getRowKey={(r) => `${r.hf_qa_id}-${r.retrieval_mechanism}`}
                          emptyMessage="No results match these filters."
                        />
                      </>
                    )}
                  </div>
                )}
              </>
            ) : (
              <p className="evaluate-page__job-pending">No results scored yet…</p>
            )}
          </div>
        ))}

      {modalOpen && (
        <Modal title="Configure evaluation" onClose={() => setModalOpen(false)}>
          <div className="evaluate-form">
            <label htmlFor="test-data-size">Test data size</label>
            <input
              id="test-data-size"
              type="number"
              min={1}
              max={4720}
              value={testDataSize}
              onChange={(event) => setTestDataSize(Number(event.target.value))}
            />

            <span>Retrieval mechanisms</span>
            <div className="evaluate-form__mechanisms">
              {MECHANISM_OPTIONS.map((option) => (
                <label key={option.value} className="evaluate-form__checkbox">
                  <input
                    type="checkbox"
                    checked={selectedMechanisms.includes(option.value)}
                    onChange={() => toggleMechanism(option.value)}
                  />
                  {option.label}
                </label>
              ))}
            </div>

            <Button onClick={handleStartEvaluation} disabled={selectedMechanisms.length === 0}>
              Start evaluation
            </Button>
          </div>
        </Modal>
      )}
    </div>
  )
}

export default Evaluate
