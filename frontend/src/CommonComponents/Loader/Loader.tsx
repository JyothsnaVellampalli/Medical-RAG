import './Loader.css'

interface LoaderProps {
  label?: string
}

function Loader({ label = 'Loading…' }: LoaderProps) {
  return (
    <div className="loader" role="status" aria-live="polite">
      <span className="loader__spinner" aria-hidden="true" />
      <span>{label}</span>
    </div>
  )
}

export default Loader
