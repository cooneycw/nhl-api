import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'

// =============================================================================
// Types - Based on backend Pydantic schemas
// =============================================================================

interface ReconciliationCheck {
  rule_name: string
  passed: boolean
  source_a: string
  source_a_value: unknown
  source_b: string
  source_b_value: unknown
  difference: number | null
  entity_type: 'game' | 'player' | 'team' | 'event'
  entity_id: string
}

interface GameReconciliation {
  game_id: number
  game_date: string // ISO date string
  home_team: string
  away_team: string
  checks_passed: number
  checks_failed: number
  discrepancies: ReconciliationCheck[]
}

interface GameReconciliationDetail extends GameReconciliation {
  all_checks: ReconciliationCheck[]
  sources_available: string[]
  sources_missing: string[]
}

interface ReconciliationSummary {
  season_id: number
  total_games: number
  games_with_discrepancies: number
  total_checks: number
  passed_checks: number
  failed_checks: number
  pass_rate: number
  goal_reconciliation_rate: number
  penalty_reconciliation_rate: number
  toi_reconciliation_rate: number
  problem_games: GameReconciliation[]
}

interface ReconciliationDashboardResponse {
  summary: ReconciliationSummary
  last_run: string | null
  quality_score: number
  timestamp: string
}

interface ReconciliationGamesResponse {
  games: GameReconciliation[]
  total: number
  page: number
  page_size: number
  pages: number
}

interface BatchReconciliationRequest {
  season_id: number
  force?: boolean
}

interface BatchReconciliationResponse {
  run_id: number
  status: 'started' | 'queued' | 'already_running'
  message: string
}

type DiscrepancyType = 'goal' | 'toi' | 'penalty' | 'shot'
type ExportFormat = 'csv' | 'json'

// =============================================================================
// Hooks
// =============================================================================

/**
 * Fetch reconciliation dashboard summary for a season.
 * Auto-refetches every 30 seconds for live updates.
 */
export function useReconciliationDashboard(seasonId: number) {
  return useQuery({
    queryKey: ['reconciliation', 'dashboard', seasonId],
    queryFn: () =>
      api.get<ReconciliationDashboardResponse>('/reconciliation/dashboard', {
        season_id: String(seasonId),
      }),
    refetchInterval: 30000, // 30 seconds
    staleTime: 10000, // Consider data stale after 10 seconds
    enabled: !!seasonId,
  })
}

/**
 * Fetch paginated list of games with reconciliation status.
 * Optionally filter by discrepancy type.
 */
export function useGameReconciliations(
  seasonId: number,
  options?: {
    discrepancyType?: DiscrepancyType
    page?: number
    pageSize?: number
  }
) {
  const { discrepancyType, page = 1, pageSize = 20 } = options ?? {}

  return useQuery({
    queryKey: ['reconciliation', 'games', seasonId, discrepancyType, page, pageSize],
    queryFn: () => {
      const params: Record<string, string> = {
        season_id: String(seasonId),
        page: String(page),
        page_size: String(pageSize),
      }
      if (discrepancyType) {
        params.discrepancy_type = discrepancyType
      }
      return api.get<ReconciliationGamesResponse>('/reconciliation/games', params)
    },
    staleTime: 30000, // 30 seconds
    enabled: !!seasonId,
  })
}

/**
 * Fetch detailed reconciliation data for a single game.
 */
export function useGameReconciliation(gameId: number) {
  return useQuery({
    queryKey: ['reconciliation', 'game', gameId],
    queryFn: () =>
      api.get<GameReconciliationDetail>(`/reconciliation/games/${gameId}`),
    staleTime: 60000, // 1 minute - game data changes less frequently
    enabled: !!gameId,
  })
}

/**
 * Trigger batch reconciliation for a season.
 * Invalidates dashboard and games queries on success.
 */
export function useTriggerReconciliation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (request: BatchReconciliationRequest) =>
      api.post<BatchReconciliationResponse>('/reconciliation/run', request),
    onSuccess: (_data, variables) => {
      // Invalidate relevant queries to trigger refetch
      queryClient.invalidateQueries({
        queryKey: ['reconciliation', 'dashboard', variables.season_id],
      })
      queryClient.invalidateQueries({
        queryKey: ['reconciliation', 'games', variables.season_id],
      })
    },
  })
}

/**
 * Export reconciliation results as CSV or JSON.
 * Returns the file URL for download.
 */
export function useExportReconciliation() {
  return useMutation({
    mutationFn: async ({
      runId,
      seasonId,
      format = 'json',
    }: {
      runId: number
      seasonId: number
      format?: ExportFormat
    }) => {
      // Build the export URL
      const baseUrl = import.meta.env.VITE_API_URL || '/api/v1'
      const url = new URL(
        `${baseUrl}/reconciliation/export/${runId}`,
        window.location.origin
      )
      url.searchParams.set('season_id', String(seasonId))
      url.searchParams.set('format', format)

      // Fetch the file
      const response = await fetch(url.toString())
      if (!response.ok) {
        throw new Error(`Export failed: ${response.statusText}`)
      }

      // Get the blob for download
      const blob = await response.blob()
      const contentDisposition = response.headers.get('Content-Disposition')
      const filename =
        contentDisposition?.match(/filename=(.+)/)?.[1] ||
        `reconciliation_${seasonId}_${runId}.${format}`

      // Create download link
      const downloadUrl = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = downloadUrl
      link.download = filename
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      window.URL.revokeObjectURL(downloadUrl)

      return { success: true, filename }
    },
  })
}

// =============================================================================
// Export Types
// =============================================================================

export type {
  ReconciliationCheck,
  GameReconciliation,
  GameReconciliationDetail,
  ReconciliationSummary,
  ReconciliationDashboardResponse,
  ReconciliationGamesResponse,
  BatchReconciliationRequest,
  BatchReconciliationResponse,
  DiscrepancyType,
  ExportFormat,
}
