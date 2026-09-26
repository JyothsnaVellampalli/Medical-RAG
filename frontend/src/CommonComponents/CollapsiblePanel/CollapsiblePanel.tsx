import { useState, type ReactNode } from 'react'
import './CollapsiblePanel.css'

interface CollapsiblePanelProps {
  title: string
  children: ReactNode
  defaultOpen?: boolean
  onToggle?: (open: boolean) => void
}

function CollapsiblePanel({ title, children, defaultOpen = true, onToggle }: CollapsiblePanelProps) {
  const [open, setOpen] = useState(defaultOpen)

  function handleClick() {
    setOpen((prev) => {
      const next = !prev
      onToggle?.(next)
      return next
    })
  }

  return (
    <div className="collapsible-panel">
      <button
        className="collapsible-panel__toggle"
        onClick={handleClick}
        aria-expanded={open}
      >
        <span className={`collapsible-panel__chevron${open ? ' collapsible-panel__chevron--open' : ''}`}>
          &#9656;
        </span>
        {title}
      </button>
      {open && <div className="collapsible-panel__content">{children}</div>}
    </div>
  )
}

export default CollapsiblePanel
