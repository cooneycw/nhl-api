const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1'

export class ApiError extends Error {
  status: number
  statusText: string

  constructor(status: number, statusText: string, message?: string) {
    super(message || `${status} ${statusText}`)
    this.name = 'ApiError'
    this.status = status
    this.statusText = statusText
  }
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const message = await response.text().catch(() => undefined)
    throw new ApiError(response.status, response.statusText, message)
  }
  return response.json()
}

export const api = {
  get: async <T>(endpoint: string, params?: Record<string, string>): Promise<T> => {
    const url = new URL(`${API_BASE_URL}${endpoint}`, window.location.origin)
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          url.searchParams.append(key, value)
        }
      })
    }
    const response = await fetch(url.toString())
    return handleResponse<T>(response)
  },

  post: async <T>(endpoint: string, data?: unknown): Promise<T> => {
    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: data ? JSON.stringify(data) : undefined,
    })
    return handleResponse<T>(response)
  },
}

// API response types
export interface HealthResponse {
  status: string
  database: string
  timestamp: string
}

export interface DashboardStats {
  active_batches: number
  completed_today: number
  failed_today: number
  success_rate_24h: number | null
  total_items_24h: number
  sources_healthy: number
  sources_degraded: number
  sources_error: number
}

export interface RecentFailure {
  progress_id: number
  source_name: string
  item_key: string
  error_message: string | null
  last_attempt_at: string | null
}

export interface DashboardResponse {
  stats: DashboardStats
  recent_failures: RecentFailure[]
  timestamp: string
}

export interface BatchSummary {
  id: string
  source: string
  season: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  progress: number
  total: number
  started_at: string
  completed_at?: string
}

export interface SourceHealth {
  source_id: number
  source_name: string
  source_type: string
  is_active: boolean
  rate_limit_ms: number | null
  max_concurrent: number | null
  latest_batch_id: number | null
  latest_status: string | null
  latest_started_at: string | null
  latest_completed_at: string | null
  batches_last_24h: number
  items_last_24h: number
  success_last_24h: number
  failed_last_24h: number
  success_rate_24h: number | null
  total_batches: number
  total_items_all_time: number
  success_items_all_time: number
  health_status: 'healthy' | 'degraded' | 'error' | 'running' | 'inactive' | 'unknown'
  refreshed_at: string | null
}

export interface SourceListResponse {
  sources: SourceHealth[]
  total: number
}

export interface PlayerSummary {
  id: number
  name: string
  team: string
  position: string
  games_played: number
  goals: number
  assists: number
  points: number
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  per_page: number
  pages: number
}

// Failure types
export interface FailedDownload {
  progress_id: number
  batch_id: number | null
  source_id: number
  source_name: string
  source_type: string
  season_id: number | null
  item_key: string
  status: string
  attempts: number
  last_attempt_at: string | null
  error_message: string | null
}

export interface FailureListResponse {
  total: number
  page: number
  page_size: number
  pages: number
  failures: FailedDownload[]
}

export interface RetryResponse {
  progress_id: number
  status: string
  message: string
}
