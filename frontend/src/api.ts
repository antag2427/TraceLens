
import { useEffect, useState } from 'react'

export const apiBase = '/api/v1'
export const severities = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
export const incidentSeverities = ['critical', 'high', 'medium', 'low']
export const statuses = ['open', 'investigating', 'resolved', 'closed']

export interface Page<T> { items: T[]; total: number; limit: number; offset: number }
export interface Service {
  id: string
  name: string
  event_count: number
  error_count: number
  anomaly_status: boolean
  incident_count: number
  health: string
  connected_services: string[]
}
export interface Edge { source: string; target: string; kind: string; evidence: string }
export interface Event {
  id: string | number
  timestamp: string
  severity: string
  service: string
  message: string
  normalized_message: string
  fingerprint: string
  trace_id: string | null
  request_id: string | null
  host: string | null
  source_file: string | null
  metadata: Record<string, unknown>
  incident_id: string | null
}
export interface Anomaly {
  id: string | number
  timestamp: string
  end: string
  service: string
  score: number
  anomalous: boolean
  severity: string
  features: Record<string, number>
  explanation: string
  method: string
}
export interface Cluster {
  id: string | number
  title: string
  count: number
  description: string
  messages: string[]
  keywords: string[]
  severity_distribution: Record<string, number>
  first_seen: string
  last_seen: string
  services: string[]
}
export interface TimelineEvent {
  timestamp: string
  service: string
  severity: string
  message: string
  event_id: number | null
  trace_id: string | null
  request_id: string | null
  kind: string
}
export interface Hypothesis {
  service: string
  pattern: string
  confidence: number
  supporting_evidence: string[]
  contradicting_evidence: string[]
  temporal_relationship: string
  explanation: string
}
export interface IncidentSummary {
  id: string
  title: string
  description: string
  severity: string
  first_seen: string
  last_seen: string
  services: string[]
  event_count: number
  status: string
  notes: string | null
}
export interface Incident extends IncidentSummary {
  anomalies: Anomaly[]
  clusters: Cluster[]
  timeline: TimelineEvent[]
  hypotheses: Hypothesis[]
  dependencies: Edge[]
}
export interface Summary {
  total_events: number
  active_incidents: number
  critical_incidents: number
  anomalies: number
  services: number
  error_rate: number
  recent_incidents: IncidentSummary[]
  volume: { timestamp: string; total: number; errors: number }[]
  severity_distribution: Record<string, number>
  service_health: Service[]
}
export interface ImportResult {
  processed: number
  parsed: number
  rejected: number
  duplicates: number
  services: string[]
  duration_ms: number
  errors: { record: number; message: string }[]
}
export interface Dataset {
  id: string | number
  source_file: string
  created_at: string
  result: ImportResult
}
export interface Run {
  id: string | number
  event_count: number
  anomaly_count: number
  cluster_count: number
  incident_count: number
  created_at: string
}
export interface Settings {
  window_minutes: number
  sensitivity: number
  incident_gap_minutes: number
  min_errors: number
  minimum_training_windows: number
  isolation_estimators: number
  cluster_similarity: number
  dependencies: { source: string; target: string }[]
  root_cause_weights: Record<string, number>
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(apiBase + path, init)
  const payload = await response.json().catch(() => null)
  if (!response.ok) {
    const detail: unknown = payload?.detail
    const message = Array.isArray(detail)
      ? detail.map((item) => [item.loc?.at(-1), item.msg].filter(Boolean).join(' · ')).join('; ')
      : detail
    throw new Error(typeof message === 'string' ? message : `Request failed (${response.status})`)
  }
  return payload as T
}

export function writeJson<T>(path: string, method: string, body: unknown) {
  return request<T>(path, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

export function useApi<T>(path: string, revision = 0) {
  const [state, setState] = useState<{ path: string; revision: number; data?: T; error?: string }>()
  useEffect(() => {
    const controller = new AbortController()
    request<T>(path, { signal: controller.signal }).then(
      (data) => setState({ path, revision, data }),
      (error: Error) => {
        if (!controller.signal.aborted) setState({ path, revision, error: error.message })
      },
    )
    return () => controller.abort()
  }, [path, revision])
  const current = state?.path === path && state.revision === revision ? state : undefined
  return { data: current?.data, error: current?.error, loading: !current }
}

export function query(values: Record<string, string | number>) {
  const params = new URLSearchParams()
  Object.entries(values).forEach(([key, value]) => {
    if (value !== '') params.set(key, String(value))
  })
  return '?' + params
}

export function dateQuery(value: string) {
  return value ? new Date(value).toISOString() : ''
}

export function upload(file: File, onProgress: (percent: number) => void): Promise<ImportResult> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', apiBase + '/logs/upload')
    xhr.responseType = 'json'
    xhr.upload.onprogress = ({ loaded, total, lengthComputable }) => {
      if (lengthComputable) onProgress(Math.round(loaded / total * 100))
    }
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) resolve(xhr.response)
      else reject(new Error(xhr.response?.detail || `Upload failed (${xhr.status})`))
    }
    xhr.onerror = () => reject(new Error('Could not reach the upload API.'))
    const form = new FormData()
    form.append('file', file)
    xhr.send(form)
  })
}
