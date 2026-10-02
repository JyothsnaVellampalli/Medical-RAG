const API_BASE_URL = import.meta.env.VITE_API_BASE_URL as string

export interface HealthResponse {
  status: string
}

export interface ChunkResult {
  chunk_id: string
  hf_row_id: number
  text: string
  chunk_index: number
}

export interface RetrieveResult {
  chunk_id: string
  hf_row_id: number
  text: string
  chunk_index: number
  score: number
}

export type SearchType = 'bm25' | 'semantic' | 'hybrid_weighted' | 'hybrid_rrf'
export type GenerationProvider = 'ollama' | 'openrouter'

export interface RetrieveRequest {
  search_type: SearchType
  query: string
  weight?: number
}

export interface QueryRequest {
  search_type: SearchType
  query: string
  weight?: number
  evaluation: boolean
  provider: GenerationProvider
  rerank: boolean
}

export interface QueryResponse {
  response: string
  citations: RetrieveResult[]
  latency_seconds: number
  evaluation_id: string | null
}

export interface QueryEvaluationStatus {
  state: 'Progress' | 'Done' | 'Error'
  faithfulness: number | null
  answer_relevancy: number | null
  error: string | null
  judge_state: 'Progress' | 'Done' | 'Error'
  judge_faithfulness: number | null
  judge_answer_relevancy: number | null
  judge_error: string | null
}

export interface EvaluateRequest {
  mechanisms: SearchType[]
  test_size: number
}

export interface EvaluateResponse {
  job_id: string
  state: string
}

export interface MechanismMetrics {
  retrieval_mechanism: SearchType
  num_questions: number
  avg_precision_at_k: number | null
  avg_recall_at_k: number | null
  avg_mrr: number | null
  avg_ndcg_at_k: number | null
  avg_faithfulness: number | null
  avg_answer_relevancy: number | null
  avg_answer_correctness: number | null
  avg_latency_seconds: number | null
  error_count: number
}

export interface EvalJob {
  job_id: string
  mechanisms: SearchType[]
  test_size: number
  state: 'Progress' | 'Done' | 'Stopped'
  started_at: string
  completed_at: string | null
  metrics: MechanismMetrics[]
}

export interface EvalResultDetail {
  hf_qa_id: number
  retrieval_mechanism: SearchType
  question: string
  precision_at_k: number | null
  recall_at_k: number | null
  mrr: number | null
  ndcg_at_k: number | null
  faithfulness: number | null
  answer_relevancy: number | null
  answer_correctness: number | null
  latency_seconds: number | null
  error: string | null
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, init)
  if (!response.ok) {
    throw new Error(`Request to ${path} failed with status ${response.status}`)
  }
  return response.json() as Promise<T>
}

export function checkHealth(): Promise<HealthResponse> {
  return request<HealthResponse>('/health')
}

export function getChunks(): Promise<ChunkResult[]> {
  return request<ChunkResult[]>('/get_chunks')
}

export function retrieve(payload: RetrieveRequest): Promise<RetrieveResult[]> {
  return request<RetrieveResult[]>('/retrieve', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function askQuery(payload: QueryRequest): Promise<QueryResponse> {
  return request<QueryResponse>('/query', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function startEvaluation(payload: EvaluateRequest): Promise<EvaluateResponse> {
  return request<EvaluateResponse>('/evaluate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function getEvals(): Promise<EvalJob[]> {
  return request<EvalJob[]>('/get_evals')
}

export function getEvalResults(jobId: string): Promise<EvalResultDetail[]> {
  return request<EvalResultDetail[]>(`/get_evals/${jobId}/results`)
}

export function getQueryEvaluation(evaluationId: string): Promise<QueryEvaluationStatus> {
  return request<QueryEvaluationStatus>(`/get_query_evaluation/${evaluationId}`)
}
