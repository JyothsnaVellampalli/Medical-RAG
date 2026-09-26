import { NavLink } from 'react-router-dom'
import './Navbar.css'

const NAV_ITEMS = [
  { to: '/', label: 'Home', end: true },
  { to: '/chunk', label: 'Chunk' },
  { to: '/retrieve', label: 'Retrieve' },
  { to: '/ask', label: 'Ask' },
  { to: '/evaluate', label: 'Evals' },
]

function Navbar() {
  return (
    <nav className="navbar" aria-label="Main navigation">
      <span className="navbar__brand">Med RAG Lab</span>
      <ul className="navbar__list">
        {NAV_ITEMS.map((item) => (
          <li key={item.to}>
            <NavLink
              to={item.to}
              end={item.end}
              className={({ isActive }) => 'navbar__link' + (isActive ? ' navbar__link--active' : '')}
            >
              {item.label}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  )
}

export default Navbar
