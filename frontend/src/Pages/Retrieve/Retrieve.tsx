import { useState, type KeyboardEvent } from 'react'
import Button from '../../CommonComponents/Button/Button'
import Dropdown from '../../CommonComponents/Dropdown/Dropdown'
import Loader from '../../CommonComponents/Loader/Loader'
import Table, { type TableColumn } from '../../CommonComponents/Table/Table'
import { retrieve, type RetrieveResult, type SearchType } from '../../api/client'
import './Retrieve.css'

const STRATEGY_OPTIONS: { label: string; value: SearchType }[] = [
  { label: 'Lexical(BM25)', value: 'bm25' },
  { label: 'Semantic', value: 'semantic' },
  { label: 'Hybrid(RRF)', value: 'hybrid_rrf' },
  { label: 'Hybrid(Weighted)', value: 'hybrid_weighted' },
]

const COLUMNS: TableColumn<RetrieveResult>[] = [
  { key: 'text', header: 'Text' },
  { key: 'chunk_index', header: 'Chunk Index' },
  { key: 'score', header: 'Score', render: (row) => row.score.toFixed(4) },
]

function Retrieve() {
  const [searchType, setSearchType] = useState<SearchType>('bm25')
  const [weight, setWeight] = useState(0.5)
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<RetrieveResult[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [hasSearched, setHasSearched] = useState(false)

  async function handleRetrieve() {
    if (!query.trim()) return
    setLoading(true)
    setError(null)
    try {
      const payload =
        searchType === 'hybrid_weighted'
          ? { search_type: searchType, query, weight }
          : { search_type: searchType, query }
      const result = await retrieve(payload)
      setResults(result)
      setHasSearched(true)
    } catch {
      setError('Retrieval failed. Is the backend running?')
    } finally {
      setLoading(false)
    }
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'Enter') {
      handleRetrieve()
    }
  }

  return (
    <div className="retrieve-page">
      <h1>Retrieve</h1>

      <div className="retrieve-page__controls">
        <Dropdown
          options={STRATEGY_OPTIONS}
          value={searchType}
          onChange={(event) => setSearchType(event.target.value as SearchType)}
          aria-label="Retrieval strategy"
        />

        {searchType === 'hybrid_weighted' && (
          <div className="retrieve-page__weight">
            <label htmlFor="weight-slider">
              Semantic weight: {weight.toFixed(2)} &nbsp;|&nbsp; BM25 weight: {(1 - weight).toFixed(2)}
            </label>
            <input
              id="weight-slider"
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={weight}
              onChange={(event) => setWeight(Number(event.target.value))}
            />
          </div>
        )}
      </div>

      <div className="retrieve-page__search">
        <input
          type="text"
          className="retrieve-page__search-box"
          placeholder="Search the corpus…"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          onKeyDown={handleKeyDown}
        />
        <Button onClick={handleRetrieve} disabled={loading || !query.trim()}>
          Retrieve
        </Button>
      </div>

      {loading && <Loader label="Retrieving…" />}
      {error && <p className="retrieve-page__error">{error}</p>}
      {!loading && hasSearched && !error && (
        <Table columns={COLUMNS} rows={results} getRowKey={(row) => row.chunk_id} emptyMessage="No results found." />
      )}
    </div>
  )
}

export default Retrieve
