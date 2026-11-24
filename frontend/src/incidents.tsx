
import { useState } from 'react'
import { ArrowLeft, ChevronRight, Download, GitBranch } from 'lucide-react'
import { apiBase, dateQuery, incidentSeverities, query, severities, statuses, useApi, writeJson } from './api'
import type { Incident, IncidentSummary, Page, Service } from './api'
import { AnomalyDetails } from './monitoring'
import {
  Empty, Heading, Notice, Pagination, Panel, Pending, Select, Status, number, pathToIncident, pathToLog, timestamp,
} from './ui'

const blank = { severity: '', status: '', service: '', start: '', end: '' }
const size = 20

export function Incidents({ revision }: { revision: number }) {
  const [filters, setFilters] = useState(blank)
  const [page, setPage] = useState(0)
  const services = useApi<Service[]>('/services', revision)
  const { data, error } = useApi<Page<IncidentSummary>>('/incidents' + query({
    ...filters, start: dateQuery(filters.start), end: dateQuery(filters.end), limit: size, offset: page * size,
  }), revision)
  function change(key: keyof typeof blank, value: string) {
    setPage(0)
    setFilters((previous) => ({ ...previous, [key]: value }))
  }
  return <>
    <Heading title="Incidents" description="Review correlated failures and track each investigation through resolution." />
    <div className="filter-panel">
      <Select label="Severity" value={filters.severity} options={incidentSeverities} all="All severities" onChange={(value) => change('severity', value)} />
      <Select label="Status" value={filters.status} options={statuses} all="All statuses" onChange={(value) => change('status', value)} />
      <Select label="Service" value={filters.service} options={services.data?.map((service) => service.name) ?? []} all="All services" onChange={(value) => change('service', value)} />
      <label className="field">Start time (local)<input type="datetime-local" value={filters.start} onChange={(event) => change('start', event.target.value)} /></label>
      <label className="field">End time (local)<input type="datetime-local" value={filters.end} onChange={(event) => change('end', event.target.value)} /></label>
      <button className="button" type="button" onClick={() => { setFilters(blank); setPage(0) }}>Reset filters</button>
    </div>
    <Panel title="Detected incidents">
      {!data ? <Pending error={error} /> : <>
        {data.items.length ? <div className="table-scroll"><table>
          <thead><tr><th>Severity</th><th>Incident</th><th>Services</th><th>Events</th><th>First seen (UTC)</th><th>Last seen (UTC)</th><th>Status</th></tr></thead>
          <tbody>{data.items.map((incident) => <tr key={incident.id}>
            <td><Status value={incident.severity} /></td>
            <td><a className="row-link" href={pathToIncident(incident.id)}>{incident.title} <ChevronRight size={14} /></a></td>
            <td>{incident.services.join(', ')}</td>
            <td>{number(incident.event_count)}</td>
            <td className="mono nowrap">{timestamp(incident.first_seen)}</td><td className="mono nowrap">{timestamp(incident.last_seen)}</td>
            <td><Status value={incident.status} /></td>
          </tr>)}</tbody>
        </table></div> : <Empty>No incidents match your filters.</Empty>}
        <Pagination total={data.total} page={page} size={size} onChange={setPage} />
      </>}
    </Panel>
  </>
}

function Lifecycle({ incident, updated }: { incident: Incident; updated: (incident: Incident) => void }) {
  const [status, setStatus] = useState(incident.status)
  const [notes, setNotes] = useState(incident.notes ?? '')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [saved, setSaved] = useState(false)
  async function save() {
    setBusy(true)
    setError('')
    setSaved(false)
    try {
      const result = await writeJson<Incident>('/incidents/' + encodeURIComponent(incident.id) + '/status', 'PATCH', { status, notes })
      setSaved(true)
      updated(result)
    } catch (error) {
      setError((error as Error).message)
    } finally {
      setBusy(false)
    }
  }
  return <form className="detail-body form-stack" onSubmit={(event) => { event.preventDefault(); void save() }}>
    <Select label="Status" value={status} options={statuses} onChange={(value) => { setStatus(value); setSaved(false) }} />
    <label className="field">Resolution notes<textarea value={notes} rows={4} maxLength={4000} placeholder="Record findings or resolution steps…" onChange={(event) => { setNotes(event.target.value); setSaved(false) }} /></label>
    <button className="button button-primary" disabled={busy || (status === incident.status && notes === (incident.notes ?? ''))}>
      {busy ? 'Saving…' : 'Save status and notes'}
    </button>
    {error && <Notice error>{error}</Notice>}
    {saved && <Notice>Incident updated.</Notice>}
  </form>
}

function Timeline({ incident }: { incident: Incident }) {
  const [service, setService] = useState('')
  const [severity, setSeverity] = useState('')
  const events = incident.timeline.filter((event) =>
    (!service || service === event.service) && (!severity || severity === event.severity.toUpperCase()),
  ).sort((a, b) => Date.parse(a.timestamp) - Date.parse(b.timestamp))
  return <Panel title="Incident timeline" caption="Chronological observations and detection signals · UTC">
    <div className="filter-panel compact">
      <Select label="Service" value={service} options={[...new Set(incident.timeline.map((event) => event.service))]} all="All services" onChange={setService} />
      <Select label="Severity" value={severity} options={severities} all="All severities" onChange={setSeverity} />
    </div>
    {events.length ? <ol className="timeline-list">{events.map((event, index) => <li key={event.timestamp + '/' + event.event_id + '/' + index}>
      <div className="timeline-marker" />
      <div className="timeline-meta"><time className="mono">{timestamp(event.timestamp)}</time><Status value={event.severity} /><span>{event.service}</span>
        <span className="type-label">{event.kind.replaceAll('_', ' ')}</span></div>
      {event.event_id != null ? <a className="row-link" href={pathToLog(event.event_id)}>{event.message}</a> : <p>{event.message}</p>}
      {(event.trace_id || event.request_id) && <p className="muted mono">
        {[event.trace_id && 'Trace ' + event.trace_id, event.request_id && 'Request ' + event.request_id].filter(Boolean).join(' · ')}
      </p>}
    </li>)}</ol> : <Empty>No timeline events match your filters.</Empty>}
  </Panel>
}

export function Investigation({ id, revision }: { id: string; revision: number }) {
  const { data, error } = useApi<Incident>('/incidents/' + id, revision)
  const [updated, setUpdated] = useState<Incident>()
  const incident = updated ?? data
  return <>
    <a className="back-link" href="#/incidents"><ArrowLeft size={15} /> Incidents</a>
    <Heading title={incident?.title ?? 'Incident investigation'} description={incident?.description ?? 'Review the timeline, hypothesis rankings and observed evidence.'}>
      <a className="button" href={apiBase + '/reports/' + id + '/markdown'} download><Download size={16} /> Markdown</a>
      <a className="button" href={apiBase + '/reports/' + id + '/json'} download><Download size={16} /> JSON</a>
    </Heading>
    {!incident ? <Pending error={error} /> : <>
      <div className="split-grid">
        <Panel title="Incident summary" action={<div className="actions"><Status value={incident.severity} /><Status value={incident.status} /></div>}>
          <div className="detail-body"><dl className="key-values">
            <div><dt>Related log events</dt><dd>{number(incident.event_count)}</dd></div>
            <div><dt>Associated anomalies</dt><dd>{number(incident.anomalies.length)}</dd></div>
            <div><dt>First detected</dt><dd>{timestamp(incident.first_seen)} UTC</dd></div>
            <div><dt>Last detected</dt><dd>{timestamp(incident.last_seen)} UTC</dd></div>
          </dl><h3>Affected services</h3><div className="tags">{incident.services.map((service) =>
            <a className="tag" key={service} href={'#/services?' + new URLSearchParams({ service })}>{service}</a>,
          )}</div></div>
        </Panel>
        <Panel title="Incident lifecycle"><Lifecycle incident={incident} updated={setUpdated} /></Panel>
      </div>
      <Panel title="Why TraceLens suspects this cause" caption="Confidence reflects the relative strength of the evidence available. Each entry is a hypothesis.">
        {incident.hypotheses.length ? <div className="hypotheses">{incident.hypotheses.map((item, index) => <article className="hypothesis" key={item.service + '/' + item.pattern}>
          <div className="hypothesis-head"><span className="rank">{index + 1}</span><div><h3>{item.service}</h3><p>{item.pattern}</p></div>
            <span className="confidence">{Math.round(item.confidence * 100)}% confidence</span></div>
          <p>{item.explanation}</p>
          <p className="muted">{item.temporal_relationship}</p>
          <h4>Supporting evidence</h4>
          <ul>{item.supporting_evidence.map((evidence, index) => <li key={index}>{evidence}</li>)}</ul>
          {item.contradicting_evidence.length > 0 && <><h4>Contradicting evidence and caveats</h4>
            <ul>{item.contradicting_evidence.map((evidence, index) => <li key={index}>{evidence}</li>)}</ul></>}
        </article>)}</div> : <Empty>No root-cause hypotheses available.</Empty>}
      </Panel>
      <Timeline incident={incident} />
      <div className="split-grid split-even">
        <Panel title="Error patterns">
          {incident.clusters.length ? incident.clusters.map((cluster) => <details className="disclosure" key={cluster.id}>
            <summary><strong>{cluster.title}</strong><span>{number(cluster.count)} events</span></summary>
            <div className="detail-body"><p>{cluster.description}</p><p>{cluster.services.join(', ')}</p><p>Keywords · {cluster.keywords.join(', ')}</p>
              <p>{timestamp(cluster.first_seen)} – {timestamp(cluster.last_seen)} UTC</p>
              <div className="tags">{Object.entries(cluster.severity_distribution).map(([level, count]) => <span className="tag" key={level}>{level} · {number(count)}</span>)}</div>
              <ul>{cluster.messages.map((message) => <li key={message}>{message}</li>)}</ul>
            </div>
          </details>) : <Empty>No related error patterns.</Empty>}
        </Panel>
        <Panel title="Related anomalies">{incident.anomalies.length
          ? incident.anomalies.map((anomaly) => <AnomalyDetails key={anomaly.id} anomaly={anomaly} />)
          : <Empty>No related anomalies.</Empty>}</Panel>
      </div>
      <Panel title="Service relationships">
        {incident.dependencies.length ? <div className="activity-list">{incident.dependencies.map((edge) => <div className="activity-item" key={edge.source + '/' + edge.target + '/' + edge.kind}>
          <span className="service-list-icon"><GitBranch size={17} /></span><div><strong>{edge.source} → {edge.target}</strong><small>{edge.evidence}</small></div><Status value={edge.kind} />
        </div>)}</div> : <Empty>No relationships recorded for these services.</Empty>}
      </Panel>
    </>}
  </>
}
