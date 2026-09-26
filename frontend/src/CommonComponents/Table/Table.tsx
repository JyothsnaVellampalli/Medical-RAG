import './Table.css'

export interface TableColumn<T> {
  key: keyof T
  header: string
  render?: (row: T) => React.ReactNode
}

interface TableProps<T> {
  columns: TableColumn<T>[]
  rows: T[]
  getRowKey: (row: T) => string
  emptyMessage?: string
}

function Table<T>({ columns, rows, getRowKey, emptyMessage = 'No data to show.' }: TableProps<T>) {
  if (rows.length === 0) {
    return <p className="table__empty">{emptyMessage}</p>
  }

  return (
    <table className="table">
      <thead>
        <tr>
          {columns.map((col) => (
            <th key={String(col.key)}>{col.header}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={getRowKey(row)}>
            {columns.map((col) => (
              <td key={String(col.key)}>{col.render ? col.render(row) : String(row[col.key])}</td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  )
}

export default Table
