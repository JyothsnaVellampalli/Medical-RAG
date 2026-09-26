import { useState } from 'react'
import Button from '../../CommonComponents/Button/Button'
import Loader from '../../CommonComponents/Loader/Loader'
import Table, { type TableColumn } from '../../CommonComponents/Table/Table'
import { getChunks, type ChunkResult } from '../../api/client'
import './Chunk.css'

const COLUMNS: TableColumn<ChunkResult>[] = [
  { key: 'chunk_id', header: 'Chunk ID' },
  { key: 'hf_row_id', header: 'HF Row ID' },
  { key: 'text', header: 'Text' },
  { key: 'chunk_index', header: 'Chunk Index' },
]

function Chunk() {
  const [chunks, setChunks] = useState<ChunkResult[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [hasFetched, setHasFetched] = useState(false)

  async function handleShowChunks() {
    setLoading(true)
    setError(null)
    try {
      const result = await getChunks()
      setChunks(result)
      setHasFetched(true)
    } catch {
      setError('Could not fetch chunks. Is the backend running?')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="chunk-page">
      <h1>Chunks</h1>
      <Button onClick={handleShowChunks} disabled={loading}>
        Show chunks
      </Button>

      {loading && <Loader label="Fetching chunks…" />}
      {error && <p className="chunk-page__error">{error}</p>}
      {!loading && hasFetched && !error && (
        <Table columns={COLUMNS} rows={chunks} getRowKey={(row) => row.chunk_id} />
      )}
    </div>
  )
}

export default Chunk
