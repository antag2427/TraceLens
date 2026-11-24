
import { useRef, useState } from 'react'
import { AudioLines, Database, FileUp, FlaskConical, Plus, Save, Trash2, UploadCloud } from 'lucide-react'
import { request, upload, useApi, writeJson } from './api'
import type { Dataset, ImportResult, Run, Settings } from './api'
import { Empty, Heading, Metric, Notice, Panel, Pending, number, timestamp } from './ui'

type ViewProps = { revision: number; refresh: () => void }

function ImportHistory({ revision }: { revision: number }) {
  const { data, error } = useApi<Dataset[]>('/datasets', revision)
  if (!data) return <Pending error={error} />
  if (!data.length) return <Empty>No datasets have been imported.</Empty>
  return <div className="table-scroll"><table>
    <thead><tr><th>Dataset</th><th>Imported (UTC)</th><th>Parsed</th><th>Rejected</th><th>Duplicates</th></tr></thead>
    <tbody>{data.map((item) => <tr key={item.id}><td>{item.source_file}</td><td className="mono">{timestamp(item.created_at)}</td>
      <td>{number(item.result.parsed)}</td><td>{number(item.result.rejected)}</td><td>{number(item.result.duplicates)}</td></tr>)}</tbody>
  </table></div>
}

export function DataUpload({ revision, refresh }: ViewProps) {
  const input = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File>()
  const [progress, setProgress] = useState(0)
  const [operation, setOperation] = useState<'upload' | 'demo' | 'analysis'>()
  const [result, setResult] = useState<ImportResult>()
  const [run, setRun] = useState<Run>()
  const [error, setError] = useState('')
  const [dragging, setDragging] = useState(false)
  async function submit(kind: 'upload' | 'demo' | 'analysis') {
    if (kind === 'upload' && !file) return
    setOperation(kind)
    setError('')
    setProgress(0)
    if (kind !== 'analysis') setResult(undefined)
    setRun(undefined)
    try {
      if (kind === 'upload' && file) setResult(await upload(file, setProgress))
      else if (kind === 'demo') setResult(await request<ImportResult>('/logs/demo', { method: 'POST' }))
      if (kind !== 'upload') setRun(await request<Run>('/analysis/run', { method: 'POST' }))
    } catch (error) {
      setError((error as Error).message)
    } finally {
      refresh()
      setOperation(undefined)
    }
  }
  return <>
    <Heading title="Data Upload" description="Import application logs or load the bundled dataset to explore an incident." />
    <div className="split-grid">
      <Panel title="Import a log file" caption="Supported formats include CSV, JSON, JSONL and plain-text logs.">
        <div className="detail-body">
          <div className={`dropzone ${dragging ? 'dropzone-active' : ''}`}
            onDragOver={(event) => { event.preventDefault(); if (!operation) setDragging(true) }}
            onDragLeave={() => setDragging(false)}
            onDrop={(event) => {
              event.preventDefault()
              setDragging(false)
              if (!operation) setFile(event.dataTransfer.files[0])
            }}>
            <UploadCloud size={30} /><strong>{file?.name ?? 'Drag a log file here'}</strong>
            <input type="file" ref={input} accept=".csv,.json,.jsonl,.log,.txt,.ndjson" hidden
              onChange={(event) => { setFile(event.target.files?.[0]); event.target.value = '' }} />
            <button className="button" type="button" disabled={!!operation} onClick={() => input.current?.click()}>Choose file</button>
          </div>
          <button className="button button-primary" disabled={!file || !!operation} onClick={() => submit('upload')}>
            <FileUp size={17} /> {operation === 'upload' ? 'Importing…' : 'Import selected file'}
          </button>
          {operation === 'upload' && <div className="form-stack" role="status">
            <label htmlFor="upload-progress">{progress < 100 ? `Uploading · ${progress}%` : 'Parsing and storing records…'}</label>
            <progress id="upload-progress" max={100} value={progress < 100 ? progress : undefined} />
          </div>}
        </div>
      </Panel>
      <Panel title="Demonstration dataset" caption="Bundled synthetic microservice logs">
        <div className="detail-body">
          <p>Load and analyze a sample containing healthy baseline traffic, operational failures and recovery signals.</p>
          <button className="button button-primary" disabled={!!operation} onClick={() => submit('demo')}>
            <FlaskConical size={17} /> {operation === 'demo' ? 'Loading and analyzing…' : 'Load demo & analyze'}
          </button>
        </div>
      </Panel>
    </div>
    {error && <Notice error>{error}</Notice>}
    {result && <Panel title="Ingestion results" caption={`Processed in ${number(Math.round(result.duration_ms))} ms`}
      action={<button className="button" disabled={!!operation} onClick={() => submit('analysis')}><AudioLines size={16} />{operation === 'analysis' ? 'Analyzing…' : 'Run analysis'}</button>}>
      <div className="detail-body">
        <div className="metrics-grid metrics-four">
          <Metric label="Processed" value={result.processed} icon={Database} />
          <Metric label="Parsed" value={result.parsed} icon={Database} tone="green" />
          <Metric label="Rejected" value={result.rejected} icon={Database} tone="red" />
          <Metric label="Duplicates" value={result.duplicates} icon={Database} tone="amber" />
        </div>
        <h3>Detected services</h3>
        {result.services.length ? <div className="tags">{result.services.map((item) => <span className="tag" key={item}>{item}</span>)}</div> : <p className="muted">No services detected in this import.</p>}
        {result.errors.length > 0 && <details className="disclosure">
          <summary>Parsing errors ({number(result.errors.length)} shown)</summary>
          <ol className="detail-body">{result.errors.map((item, index) => <li key={index}>Record {item.record} · {item.message}</li>)}</ol>
        </details>}
      </div>
    </Panel>}
    {run && <Notice><div>Analysis complete. {number(run.event_count)} events · {number(run.anomaly_count)} anomalies · {number(run.cluster_count)} patterns · {number(run.incident_count)} incidents. <a className="subtle-link" href="#/incidents">Review incidents</a></div></Notice>}
    <Panel title="Import history"><ImportHistory revision={revision} /></Panel>
  </>
}

const numericSettings = [
  { key: 'window_minutes', label: 'Analysis window (minutes)', step: 1, min: 1, max: 180 },
  { key: 'sensitivity', label: 'Anomaly sensitivity', step: 0.01, min: 0.01, max: 0.4 },
  { key: 'incident_gap_minutes', label: 'Incident grouping gap (minutes)', step: 1, min: 1, max: 180 },
  { key: 'min_errors', label: 'Minimum errors for incident grouping', step: 1, min: 1, max: 200 },
  { key: 'minimum_training_windows', label: 'Minimum model training windows', step: 1, min: 4, max: 200 },
  { key: 'isolation_estimators', label: 'Isolation Forest tree count', step: 1, min: 20, max: 300 },
  { key: 'cluster_similarity', label: 'Error pattern similarity threshold', step: 0.01, min: 0.1, max: 0.8 },
] as const

function SettingsForm({ initial, refresh }: { initial: Settings; refresh: () => void }) {
  const [values, setValues] = useState(initial)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<{ text: string; error?: boolean }>()
  async function save() {
    setBusy(true)
    setMessage(undefined)
    try {
      const result = await writeJson<Settings>('/settings', 'PUT', {
        ...values,
        dependencies: values.dependencies.map(({ source, target }) => ({ source: source.trim(), target: target.trim() })),
      })
      setValues(result)
      setMessage({ text: 'Settings saved. Run analysis to apply these settings to detection results.' })
    } catch (error) {
      setMessage({ text: (error as Error).message, error: true })
    } finally {
      setBusy(false)
    }
  }
  function updateDependency(index: number, field: 'source' | 'target', value: string) {
    setValues((previous) => ({
      ...previous,
      dependencies: previous.dependencies.map((edge, position) => position === index ? { ...edge, [field]: value } : edge),
    }))
  }
  return <form className="settings-form" onSubmit={(event) => { event.preventDefault(); void save() }}>
    <div className="split-grid split-even">
      <Panel title="Detection configuration" caption="Tune the settings used on the next analysis run."><div className="detail-body form-stack">
        {numericSettings.map((config) => <label className="field" key={config.key}>{config.label}
          <input type="number" min={config.min} step={config.step} max={config.max}
            required value={Number.isNaN(values[config.key]) ? '' : values[config.key]}
            onChange={(event) => setValues({ ...values, [config.key]: event.target.valueAsNumber })} />
        </label>)}
      </div></Panel>
      <Panel title="Configured dependencies" caption="Enter a calling service and the service it depends on."><div className="detail-body">
        {values.dependencies.length === 0 && <p className="muted">No explicit dependency configuration.</p>}
        {values.dependencies.map((edge, index) => <div className="dependency-edit" key={index}>
          <label className="field">Calling service<input required value={edge.source} onChange={(event) => updateDependency(index, 'source', event.target.value)} /></label>
          <label className="field">Dependency<input required value={edge.target} onChange={(event) => updateDependency(index, 'target', event.target.value)} /></label>
          <button className="button icon-button" type="button" aria-label={`Remove dependency ${index + 1}`} onClick={() =>
            setValues({ ...values, dependencies: values.dependencies.filter((_, position) => position !== index) })}><Trash2 size={16} /></button>
        </div>)}
        <button className="button" type="button" onClick={() =>
          setValues({ ...values, dependencies: [...values.dependencies, { source: '', target: '' }] })}><Plus size={16} /> Add dependency</button>
      </div></Panel>
    </div>
    <div className="actions">
      <button className="button button-primary" disabled={busy}><Save size={16} /> {busy ? 'Saving…' : 'Save settings'}</button>
      <button className="button" type="button" disabled={busy} onClick={refresh}>Reload settings</button>
    </div>
    {message && <Notice error={message.error}>{message.text}</Notice>}
  </form>
}

export function SettingsView({ revision, refresh }: ViewProps) {
  const { data, error } = useApi<Settings>('/settings', revision)
  const runs = useApi<Run[]>('/analysis/runs', revision)
  return <>
    <Heading title="Settings" description="Configure local analysis and review datasets and prior runs." />
    {!data ? <Pending error={error} /> : <SettingsForm key={revision} initial={data} refresh={refresh} />}
    <Panel title="Dataset management" caption="Review imported datasets and their ingestion results."
      action={<a className="button" href="#/upload"><UploadCloud size={16} /> Import dataset</a>}>
      <ImportHistory revision={revision} />
    </Panel>
    <Panel title="Analysis runs">
      {!runs.data ? <Pending error={runs.error} /> : runs.data.length ? <div className="table-scroll"><table>
        <thead><tr><th>Run time (UTC)</th><th>Events</th><th>Anomalies</th><th>Clusters</th><th>Incidents</th></tr></thead>
        <tbody>{runs.data.map((run) => <tr key={run.id}><td className="mono">{timestamp(run.created_at)}</td>
          <td>{number(run.event_count)}</td><td>{number(run.anomaly_count)}</td><td>{number(run.cluster_count)}</td><td>{number(run.incident_count)}</td></tr>)}</tbody>
      </table></div> : <Empty>No analysis runs yet.</Empty>}
    </Panel>
  </>
}
