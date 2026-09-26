import type { SelectHTMLAttributes } from 'react'
import './Dropdown.css'

export interface DropdownOption {
  label: string
  value: string
}

interface DropdownProps extends Omit<SelectHTMLAttributes<HTMLSelectElement>, 'children'> {
  options: DropdownOption[]
}

function Dropdown({ options, className, ...rest }: DropdownProps) {
  const classes = ['dropdown', className].filter(Boolean).join(' ')
  return (
    <select className={classes} {...rest}>
      {options.map((option) => (
        <option key={option.value} value={option.value}>
          {option.label}
        </option>
      ))}
    </select>
  )
}

export default Dropdown
