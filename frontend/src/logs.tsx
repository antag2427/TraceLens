
import { useState } from 'react'
import { ArrowLeft, ArrowUpRight, Search } from 'lucide-react'
import { dateQuery, query, severities, useApi } from './api'
import type { Event, Page, Service } from './api'
import { Empty, Heading, Pagination, Panel, Pending, Select, Status, pathToIncident, pathToLog, timestamp } from './ui'

const blank = { q: '', severity: '', service: '', start: '', end: '', trace_id: '', request_id: '', sort: 'desc' }
const size = 25

export function LogExplorer({ revision }: { revision: number }) {
  const [filters, setFilters] = useState(() => ({
    ...blank,
    service: new URLSearchParams(window.location.hash.split('?')[1]).get('service') ?? '',
  }))
  const [page, setPage] = useState(0)
  const [keyword, setKeyword] = useState(filters.q)
  const services = useApi<Service[]>('/services', revision)
  const { data, error } = useApi<Page<Event>>('/logs' + query({
    ...filters, start: dateQuery(filters.start), end: dateQuery(filters.end), offset: page * size, limit: size,
  }), revision)
  function change(key: keyof typeof blank, value: string) {
    setPage(0)
    setFilters((previous) => ({ ...previous, [key]: value }))
  }
  return <>
    <Heading title="Log Explorer" description="Search structured log events and follow the evidence into an investigation." />
    <div className="filter-panel">
      <form className="search-form" onSubmit={(event) => { event.preventDefault(); change('q', keyword.trim()) }}>
        <label className="field">Search log messages<div className="search-input"><Search size={17} /><input type="search"
          placeholder="Search messages…" maxLength={250} value={keyword} onChange={(event) => setKeyword(event.target.value)} /></div></label>
        <button className="button button-primary" type="submit">Search</button>
      </form>
      <Select label="Severity" value={filters.severity} options={severities} all="All severities" onChange={(value) => change('severity', value)} />
      <Select label="Service" value={filters.service} options={services.data?.map((item) => item.name) ?? []} all="All services" onChange={(value) => change('service', value)} />
      <label className="field">Sort by timestamp<select value={filters.sort} onChange={(event) => change('sort', event.target.value)}>
        <option value="desc">Newest first</option><option value="asc">Oldest first</option>
      </select></label>
      <label className="field">Start time (local)<input type="datetime-local" value={filters.start} onChange={(event) => change('start', event.target.value)} /></label>
      <label className="field">End time (local)<input type="datetime-local" value={filters.end} onChange={(event) => change('end', event.target.value)} /></label>
      <label className="field">Trace ID<input value={filters.trace_id} onChange={(event) => change('trace_id', event.target.value)} placeholder="Filter by trace ID" /></label>
      <label className="field">Request ID<input value={filters.request_id} onChange={(event) => change('request_id', event.target.value)} placeholder="Filter by request ID" /></label>
      <button className="button" type="button" onClick={() => { setFilters(blank); setKeyword(''); setPage(0) }}>Reset filters</button>
    </div>
    <Panel title="Log events" caption="Timestamps are displayed in UTC. Open a message to inspect its fields.">
      {!data ? <Pending error={error} /> : <>
        {data.items.length ? <div className="table-scroll"><table>
          <thead><tr><th>Timestamp (UTC)</th><th>Severity</th><th>Service</th><th>Message</th><th>Incident</th></tr></thead>
          <tbody>{data.items.map((event) => <tr key={event.id}>
            <td className="mono nowrap">{timestamp(event.timestamp)}</td>
            <td><Status value={event.severity} /></td><td>{event.service}</td>
            <td><a className="row-link log-message" href={pathToLog(event.id)}>{event.message}</a></td>
            <td>{event.incident_id ? <a className="subtle-link" href={pathToIncident(event.incident_id)}>Open <ArrowUpRight size={13} /></a> : '–'}</td>
          </tr>)}</tbody>
        </table></div> : <Empty>No log events match your filters.</Empty>}
        <Pagination total={data.total} page={page} size={size} onChange={setPage} />
      </>}
    </Panel>
  </>
}

export function LogDetails({ revision, id }: { revision: number; id: string }) {
  const { data, error } = useApi<Event>('/logs/' + id, revision)
  return <>
    <a className="back-link" href="#/logs"><ArrowLeft size={15} /> Log Explorer</a>
    <Heading title="Log event" description={data ? timestamp(data.timestamp) + ' UTC' : 'Inspect normalized fields and source metadata.'}>
      {data?.incident_id && <a className="button button-primary" href={pathToIncident(data.incident_id)}><ArrowUpRight size={17} /> Open incident</a>}
    </Heading>
    {!data ? <Pending error={error} /> : <div className="split-grid">
      <Panel title="Event message" action={<Status value={data.severity} />}><div className="detail-body">
        <pre>{data.message}</pre><h3>Normalized message</h3><pre>{data.normalized_message}</pre>
        <h3>Additional metadata</h3><pre>{JSON.stringify(data.metadata, null, 2)}</pre>
      </div></Panel>
      <Panel title="Event fields"><div className="detail-body"><dl className="key-values">
        {Object.entries({
          'Event ID': data.id, Service: data.service, 'Source file': data.source_file, Host: data.host,
          'Trace ID': data.trace_id, 'Request ID': data.request_id, Fingerprint: data.fingerprint,
        }).map(([label, value]) => <div key={label}><dt>{label}</dt><dd className="mono">{value ?? '–'}</dd></div>)}
      </dl></div></Panel>
    </div>}
  </>
}
