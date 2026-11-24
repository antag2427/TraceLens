
import { useId } from 'react'
import type { ReactNode } from 'react'
import { AlertCircle, Inbox, LoaderCircle, ChevronLeft, ChevronRight } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

const dateFormat = new Intl.DateTimeFormat('en', {
  month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit',
  second: '2-digit', hourCycle: 'h23', timeZone: 'UTC',
})
const numbers = new Intl.NumberFormat('en')
export const number = (value: number) => numbers.format(value)
export const timestamp = (value: string) => dateFormat.format(new Date(value))
export const titleCase = (value: string) => value ? value[0].toUpperCase() + value.slice(1).toLowerCase() : 'Unknown'
export const pathToIncident = (id: string) => '#/incidents/' + encodeURIComponent(id)
export const pathToLog = (id: number | string) => '#/logs/' + encodeURIComponent(id)

export function Heading({ title, description, children }: { title: string; description: string; children?: ReactNode }) {
  return <div className="page-heading"><div><h1>{title}</h1><p>{description}</p></div>
    {children && <div className="actions">{children}</div>}</div>
}

export function Panel({ title, caption, action, children, className = '' }: {
  title: string; caption?: string; action?: ReactNode; children: ReactNode; className?: string
}) {
  return <section className={`panel ${className}`}>
    <div className="panel-header"><div><h2>{title}</h2>{caption && <p>{caption}</p>}</div>{action}</div>
    {children}
  </section>
}

export function Status({ value }: { value: string }) {
  const style = value.toLowerCase()
  return <span className={`status status-${style}`}><span aria-hidden="true" />{titleCase(value)}</span>
}

export function Metric({ label, value, icon: Icon, tone = 'accent' }: {
  label: string; value: string | number; icon: LucideIcon; tone?: string
}) {
  return <div className="metric">
    <div className={`metric-icon ${tone}`}><Icon size={17} aria-hidden="true" /></div>
    <div className="metric-label">{label}</div>
    <strong>{typeof value === 'number' ? number(value) : value}</strong>
  </div>
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="empty"><Inbox size={23} aria-hidden="true" /><p>{children}</p></div>
}

export function Notice({ error, children }: { error?: boolean; children: ReactNode }) {
  return <div className={`notice ${error ? 'notice-error' : ''}`} role={error ? 'alert' : 'status'}>
    {error && <AlertCircle size={18} aria-hidden="true" />}{children}
  </div>
}

export function Pending({ error }: { error?: string }) {
  return error ? <Notice error>{error}</Notice> : <div className="pending" role="status">
    <LoaderCircle className="spin" size={19} aria-hidden="true" /> Loading…
  </div>
}

export function Select({ label, value, onChange, options, all }: {
  label: string; value: string; onChange: (value: string) => void; options: string[]; all?: string
}) {
  const id = useId()
  return <div className="field"><label htmlFor={id}>{label}</label><select id={id} value={value} onChange={(event) => onChange(event.target.value)}>
    {all && <option value="">{all}</option>}
    {options.map((option) => <option key={option} value={option}>{option.includes('-') || /[a-z].*[A-Z]/.test(option) ? option : titleCase(option)}</option>)}
  </select></div>
}

export function Pagination({ total, page, size, onChange }: {
  total: number; page: number; size: number; onChange: (value: number) => void
}) {
  const pages = Math.max(1, Math.ceil(total / size))
  return <div className="pagination">
    <span>{total ? `${number(page * size + 1)}–${number(Math.min((page + 1) * size, total))} of ${number(total)}` : '0 results'}</span>
    <span>Page {page + 1} of {pages}</span>
    <div className="actions">
      <button className="button icon-button" type="button" aria-label="Previous page" disabled={page === 0} onClick={() => onChange(page - 1)}><ChevronLeft size={17} /></button>
      <button className="button icon-button" type="button" aria-label="Next page" disabled={page + 1 >= pages} onClick={() => onChange(page + 1)}><ChevronRight size={17} /></button>
    </div>
  </div>
}
