
import { useState } from 'react'
import { Activity, AlertTriangle, AudioLines, CircleAlert, Database, GitBranch, Network, Play, UploadCloud } from 'lucide-react'
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { query, request, severities, useApi } from './api'
import type { Anomaly, Edge, Page, Run, Service, Summary } from './api'
import { Empty, Heading, Metric, Notice, Pagination, Panel, Pending, Select, Status, number, pathToIncident, timestamp, titleCase } from './ui'

type Series = { key: string; name: string; color: string }
const timeTick = (value: string) => new Date(value).toISOString().slice(5, 16).replace('T', ' ')
const tooltipStyle = { background: '#202735', border: '1px solid #354055', borderRadius: 8, color: '#edf2fc' }

function TimelineChart({ points, series, label }: {
  points: object[]; series: Series[]; label: string
}) {
  if (!points.length) return <Empty>No activity in this view.</Empty>
  return <div className="chart-region" role="region" aria-label={label}>
    <ResponsiveContainer width="100%" height={238} minWidth={0}>
      <AreaChart data={points} margin={{ top: 12, right: 15, bottom: 2, left: 0 }}>
        <CartesianGrid vertical={false} stroke="#293241" strokeDasharray="3 4" />
        <XAxis dataKey="timestamp" stroke="#a0abc0" tickFormatter={timeTick} minTickGap={24} axisLine={false} tickLine={false} tickMargin={12} tick={{ fontSize: 11 }} />
        <YAxis stroke="#a0abc0" width={42} axisLine={false} tickLine={false} tickMargin={8} tick={{ fontSize: 11 }} />
        <Tooltip contentStyle={tooltipStyle} labelFormatter={(label) => timestamp(String(label)) + ' UTC'} />
        {series.map(({ key, name, color }) => <Area key={key} dataKey={key} name={name}
          type="linear" stroke={color} fill={color} fillOpacity={0.10} strokeWidth={2} connectNulls={false}
          isAnimationActive={false} />)}
      </AreaChart>
    </ResponsiveContainer>
  </div>
}

function AnalyzeButton({ refresh }: { refresh: () => void }) {
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<{ text: string; error?: boolean }>()
  async function analyze() {
    setBusy(true)
    setMessage(undefined)
    try {
      const run = await request<Run>('/analysis/run', { method: 'POST' })
      setMessage({ text: `Analysis complete. ${number(run.event_count)} events processed, ${number(run.incident_count)} incidents identified.` })
      refresh()
    } catch (error) {
      setMessage({ text: (error as Error).message, error: true })
    } finally {
      setBusy(false)
    }
  }
  return <>
    <button className="button button-primary" onClick={analyze} disabled={busy}><Play size={15} />{busy ? 'Analyzing…' : 'Run analysis'}</button>
    {message && <div className="analysis-feedback"><Notice error={message.error}>{message.text}</Notice></div>}
  </>
}

export function Overview({ revision, refresh }: { revision: number; refresh: () => void }) {
  const { data, error } = useApi<Summary>('/analytics/summary', revision)
  const severityTotal = data ? Object.values(data.severity_distribution).reduce((a, b) => a + b, 0) : 0
  return <>
    <Heading title="Overview" description="Monitor service health and investigate unusual activity across your logs.">
      <a className="button" href="#/upload"><UploadCloud size={16} /> Upload logs</a>
      <AnalyzeButton refresh={refresh} />
    </Heading>
    {!data ? <Pending error={error} /> : <>
      {data.total_events === 0 && <div className="empty-banner"><Database size={24} />
        <div><strong>Start with your first dataset</strong><p>Load the included demo or import your own logs to begin investigating.</p></div>
        <a className="button button-primary" href="#/upload">Open data upload</a></div>}
      <div className="metrics-grid">
        <Metric label="Total log events" value={data.total_events} icon={Database} />
        <Metric label="Active incidents" value={data.active_incidents} icon={CircleAlert} tone="amber" />
        <Metric label="Critical incidents" value={data.critical_incidents} icon={AlertTriangle} tone="red" />
        <Metric label="Detected anomalies" value={data.anomalies} icon={AudioLines} tone="purple" />
        <Metric label="Monitored services" value={data.services} icon={Network} tone="green" />
        <Metric label="Error rate" value={(data.error_rate * 100).toFixed(2) + '%'} icon={Activity} tone="red" />
      </div>
      <div className="split-grid">
        <Panel title="Log volume over time" caption="Total events and errors by window · UTC"
          action={<div className="legend"><span className="legend-accent">Total events</span><span className="legend-red">Errors</span></div>}>
          <TimelineChart points={data.volume} label="Total events and errors over time"
            series={[{ key: 'total', name: 'Total events', color: '#74a9ff' }, { key: 'errors', name: 'Errors', color: '#fa7e91' }]} />
        </Panel>
        <Panel title="Severity distribution" caption="Breakdown of ingested records">
          {severityTotal === 0 ? <Empty>No log records.</Empty> : <div className="distribution">
            {[...severities].reverse().map((severity) => {
              const count = data.severity_distribution[severity] ?? 0
              return <div className="distribution-row" key={severity}><Status value={severity} /><span>{number(count)}</span>
                <span className="track"><span className={`fill severity-${severity.toLowerCase()}`} style={{ width: (count / severityTotal) * 100 + '%' }} /></span></div>
            })}
          </div>}
        </Panel>
      </div>
      <div className="split-grid">
        <Panel title="Recent incidents" action={<a className="subtle-link" href="#/incidents">View all</a>}>
          {data.recent_incidents.length ? <div className="activity-list">{data.recent_incidents.map((incident) => <a
            className="activity-item" href={pathToIncident(incident.id)} key={incident.id}>
            <Status value={incident.severity} /><div><strong>{incident.title}</strong><small>{incident.services.join(', ')}</small></div>
            <Status value={incident.status} />
          </a>)}</div> : <Empty>No incidents detected.</Empty>}
        </Panel>
        <Panel title="Service health" action={<a className="subtle-link" href="#/services">Service map</a>}>
          {data.service_health.length ? <div className="activity-list">{data.service_health.map((service) => <a
            className="activity-item" key={service.id} href={'#/services?' + new URLSearchParams({ service: service.name })}>
            <span className="service-list-icon"><GitBranch size={15} /></span>
            <div><strong>{service.name}</strong><small>{number(service.event_count)} events · {number(service.error_count)} errors</small></div>
            <Status value={service.health} />
          </a>)}</div> : <Empty>No services yet.</Empty>}
        </Panel>
      </div>
    </>}
  </>
}

export function AnomalyDetails({ anomaly }: { anomaly: Anomaly }) {
  return <details className="disclosure">
    <summary><Status value={anomaly.anomalous ? anomaly.severity : 'normal'} /><strong>{anomaly.service}</strong>
      <span className="mono">{anomaly.score.toFixed(3)}</span><time>{timestamp(anomaly.timestamp)} UTC</time></summary>
    <div className="detail-body"><p>{anomaly.explanation}</p>
      <p className="muted">Method {anomaly.method} · Window ends {timestamp(anomaly.end)} UTC</p>
      <dl className="key-values">{Object.entries(anomaly.features).map(([key, value]) => <div key={key}>
        <dt>{key.replaceAll('_', ' ')}</dt><dd>{Number.isInteger(value) ? number(value) : value.toFixed(4)}</dd>
      </div>)}</dl>
    </div>
  </details>
}

export function Anomalies({ revision }: { revision: number }) {
  const [service, setService] = useState('')
  const [classification, setClassification] = useState('')
  const [page, setPage] = useState(0)
  const services = useApi<Service[]>('/services', revision)
  const counts = useApi<Page<Anomaly>>('/anomalies?anomalous=true&limit=1', revision)
  const windows = useApi<Page<Anomaly>>('/anomalies' + query({ limit: 200, service }), revision)
  const list = useApi<Page<Anomaly>>('/anomalies' + query({ service, anomalous: classification, limit: 20, offset: page * 20 }), revision)
  const chartPoints = Object.values((windows.data?.items ?? []).reduce<Record<string, { timestamp: string; normal: number; abnormal: number }>>((points, item) => {
    const point = points[item.timestamp] ??= { timestamp: item.timestamp, normal: 0, abnormal: 0 }
    if (item.anomalous) point.abnormal++
    else point.normal++
    return points
  }, {})).sort((a, b) => a.timestamp.localeCompare(b.timestamp))
  return <>
    <Heading title="Anomalies" description="Inspect unusual service behavior, model scores and the features behind each detection." />
    <div className="filter-panel">
      <Select label="Service" value={service} options={services.data?.map((item) => item.name) ?? []} all="All services" onChange={(value) => { setService(value); setPage(0) }} />
      <label className="field">Classification<select value={classification} onChange={(event) => { setClassification(event.target.value); setPage(0) }}>
        <option value="">All windows</option><option value="true">Anomalous</option><option value="false">Normal</option>
      </select></label>
    </div>
    <div className="metrics-grid metrics-narrow">
      <Metric label="Detected anomalies" value={counts.data?.total ?? '–'} icon={AudioLines} tone="purple" />
      <Metric label="Windows in current filter" value={list.data?.total ?? '–'} icon={Activity} />
      <Metric label="Services with anomalies" value={services.data?.filter((item) => item.anomaly_status).length ?? '–'} icon={Network} tone="green" />
    </div>
    <Panel title="Detection activity" caption="Normal and abnormal service windows · latest 200 windows · UTC"
      action={<div className="legend"><span className="legend-accent">Normal</span><span className="legend-red">Abnormal</span></div>}>
      {!windows.data ? <Pending error={windows.error} /> : <TimelineChart points={chartPoints} label="Normal and abnormal service windows over time"
        series={[{ key: 'normal', name: 'Normal', color: '#74a9ff' }, { key: 'abnormal', name: 'Abnormal', color: '#fa7e91' }]} />}
    </Panel>
    <Panel title="Detection windows" caption="Expand a row to inspect its evidence and input features.">
      {!list.data ? <Pending error={list.error} /> : <>
        {list.data.items.length ? list.data.items.map((item) => <AnomalyDetails key={item.id} anomaly={item} />) : <Empty>No windows match your filters. Run analysis after importing logs.</Empty>}
        <Pagination total={list.data.total} page={page} size={20} onChange={setPage} />
      </>}
    </Panel>
  </>
}

function DependencyGraph({ services, edges, current, select }: {
  services: Service[]; edges: Edge[]; current: string; select: (service: string) => void
}) {
  const columns = Math.max(2, Math.ceil(Math.sqrt(services.length)))
  const width = columns * 235
  const height = Math.ceil(services.length / columns) * 125 + 50
  const positions = new Map(services.map((service, index) => [
    service.name, { x: (index % columns) * 235 + 117, y: Math.floor(index / columns) * 125 + 82 },
  ]))
  return <div className="graph-scroll"><div className="dependency-graph" style={{ width, height }}>
    <svg width={width} height={height} aria-hidden="true">
      <defs><marker id="arrow" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="7" markerHeight="7" orient="auto">
        <path d="M 0 0 L 10 5 L 0 10 z" fill="#8795ad" />
      </marker></defs>
      {edges.map((edge) => {
        const start = positions.get(edge.source)
        const end = positions.get(edge.target)
        if (!start || !end || start === end) return null
        const explicit = ['configured', 'explicit', 'confirmed'].includes(edge.kind)
        const horizontal = start.y === end.y
        const inset = (horizontal ? 77 : 27) * Math.sign(horizontal ? end.x - start.x : end.y - start.y)
        const x1 = start.x + (horizontal ? inset : 0)
        const x2 = end.x - (horizontal ? inset : 0)
        const y1 = start.y + (horizontal ? 0 : inset)
        const y2 = end.y - (horizontal ? 0 : inset)
        return <line key={edge.source + '/' + edge.target + '/' + edge.kind} x1={x1} x2={x2}
          y1={y1} y2={y2} stroke={explicit ? '#899ab9' : '#65738d'}
          strokeDasharray={explicit ? undefined : '5 5'} markerEnd="url(#arrow)" />
      })}
    </svg>
    {services.map((item) => {
      const position = positions.get(item.name)!
      return <button type="button" key={item.id} className={`graph-node ${current === item.name ? 'graph-selected' : ''}`}
        style={{ left: position.x, top: position.y }} aria-pressed={current === item.name} onClick={() => select(item.name)}>
        <GitBranch size={17} /><span><strong>{item.name}</strong><Status value={item.health} /></span>
      </button>
    })}
  </div></div>
}

export function Services({ revision }: { revision: number }) {
  const services = useApi<Service[]>('/services', revision)
  const edges = useApi<Edge[]>('/services/dependencies', revision)
  const [selected, setSelected] = useState(() => new URLSearchParams(window.location.hash.split('?')[1]).get('service') ?? '')
  const current = services.data?.find((item) => item.name === selected) ?? services.data?.[0]
  return <>
    <Heading title="Service Map" description="Inspect monitored services and the evidence connecting them." />
    <div className="split-grid">
      <Panel title="Dependency graph" caption="Solid connections are configured. Dashed connections are inferred.">
        {!services.data || !edges.data ? <Pending error={services.error || edges.error} /> : services.data.length
          ? <DependencyGraph services={services.data} edges={edges.data} current={current?.name ?? ''} select={setSelected} />
          : <Empty>Import logs to populate the service map.</Empty>}
      </Panel>
      <Panel title="Service activity" caption={current?.name}>
        {!current ? <Empty>Select a service to inspect its activity.</Empty> : <div className="detail-body">
          <Status value={current.health} />
          <dl className="key-values">
            <div><dt>Log events</dt><dd>{number(current.event_count)}</dd></div>
            <div><dt>Errors</dt><dd>{number(current.error_count)}</dd></div>
            <div><dt>Incidents</dt><dd>{number(current.incident_count)}</dd></div>
            <div><dt>Anomalous</dt><dd>{current.anomaly_status ? 'Yes' : 'No'}</dd></div>
          </dl>
          <a className="subtle-link" href={'#/logs?' + new URLSearchParams({ service: current.name })}>View service logs</a>
          <h3>Connected services</h3>
          {current.connected_services.length ? <div className="tags">{current.connected_services.map((name) => <button className="tag" type="button" key={name} onClick={() => setSelected(name)}>{name}</button>)}</div> : <p className="muted">No connections recorded.</p>}
        </div>}
      </Panel>
    </div>
    <Panel title="Relationship evidence">
      {!edges.data ? <Pending error={edges.error} /> : edges.data.length ? <div className="activity-list">{edges.data.map((edge) => <div
        className="activity-item" key={edge.source + '/' + edge.target + '/' + edge.kind}>
        <span className="service-list-icon"><Network size={16} /></span>
        <div><strong>{edge.source} → {edge.target}</strong><small>{edge.evidence}</small></div>
        <Status value={titleCase(edge.kind.replaceAll('_', ' '))} />
      </div>)}</div> : <Empty>No service relationships recorded.</Empty>}
    </Panel>
  </>
}
