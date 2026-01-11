import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'

// =============================================================================
// Types - Based on backend Pydantic schemas
// =============================================================================

interface ValidationRule {
  rule_id: number
  name: string
  description: string | null
  category: string
  severity: string
  is_active: boolean
  config: Record<string, unknown> | null
}

interface ValidationRulesResponse {
  rules: ValidationRule[]
  total: number
}

interface ValidationResult {
  result_id: number
  rule_id: number
  rule_name: string
  game_id: number | null
  passed: boolean
  severity: string | null
  message: string | null
  details: Record<string, unknown> | null
  source_values: Record<string, unknown> | null
  created_at: string
}

interface ValidationRunSummary {
  run_id: number
  season_id: number | null
  started_at: string
  completed_at: string | null
  status: 'running' | 'completed' | 'failed'
  rules_checked: number
  total_passed: number
  total_failed: number
  total_warnings: number
}

interface ValidationRunDetail extends ValidationRunSummary {
  results: ValidationResult[]
  metadata: Record<string, unknown> | null
}

interface ValidationRunsResponse {
  runs: ValidationRunSummary[]
  total: number
  page: number
  page_size: number
  pages: number
}

interface QualityScore {
  score_id: number
  season_id: number
  game_id: number | null
  entity_type: 'season' | 'game'
  entity_id: string
  completeness_score: number | null
  accuracy_score: number | null
  consistency_score: number | null
  timeliness_score: number | null
  overall_score: number | null
  total_checks: number
  passed_checks: number
  failed_checks: number
  warning_checks: number
  calculated_at: string
}

interface QualityScoresResponse {
  scores: QualityScore[]
  total: number
  page: number
  page_size: number
  pages: number
}

interface DiscrepancySummary {
  discrepancy_id: number
  rule_id: number
  rule_name: string
  game_id: number | null
  season_id: number | null
  entity_type: string | null
  entity_id: string | null
  field_name: string | null
  source_a: string | null
  source_b: string | null
  resolution_status: 'open' | 'resolved' | 'ignored'
  created_at: string
}

interface DiscrepancyDetail extends DiscrepancySummary {
  source_a_value: string | null
  source_b_value: string | null
  resolution_notes: string | null
  resolved_at: string | null
  result_id: number | null
}

interface DiscrepanciesResponse {
  discrepancies: DiscrepancySummary[]
  total: number
  page: number
  page_size: number
  pages: number
}

interface ValidationRunRequest {
  season_id?: number
  game_id?: number
  validator_types?: string[]
}

interface ValidationRunResponse {
  run_id: number
  status: string
  message: string
}

interface SourceAccuracy {
  source: string
  total_games: number
  accuracy_percentage: number
  total_discrepancies: number
}

interface SeasonSummary {
  season_id: number
  season_display: string
  total_games: number
  reconciled_games: number
  failed_games: number
  reconciliation_percentage: number
  total_goals: number
  games_with_discrepancies: number
  source_accuracy: SourceAccuracy[]
  common_discrepancies: Record<string, number>
}

// =============================================================================
// Hooks
// =============================================================================

/**
 * Fetch validation rules list.
 */
export function useValidationRules(options?: {
  category?: string
  isActive?: boolean
}) {
  const { category, isActive } = options ?? {}

  return useQuery({
    queryKey: ['validation', 'rules', category, isActive],
    queryFn: () => {
      const params: Record<string, string> = {}
      if (category) params.category = category
      if (isActive !== undefined) params.is_active = String(isActive)
      return api.get<ValidationRulesResponse>('/validation/rules', params)
    },
    staleTime: 60000, // Rules change rarely
  })
}

/**
 * Fetch paginated list of validation runs.
 */
export function useValidationRuns(options?: {
  seasonId?: number
  page?: number
  pageSize?: number
}) {
  const { seasonId, page = 1, pageSize = 20 } = options ?? {}

  return useQuery({
    queryKey: ['validation', 'runs', seasonId, page, pageSize],
    queryFn: () => {
      const params: Record<string, string> = {
        page: String(page),
        page_size: String(pageSize),
      }
      if (seasonId) params.season_id = String(seasonId)
      return api.get<ValidationRunsResponse>('/validation/runs', params)
    },
    staleTime: 10000, // Refresh more often for live status
    refetchInterval: 30000, // Auto-refetch for running validations
  })
}

/**
 * Fetch detailed validation run with results.
 */
export function useValidationRun(runId: number) {
  return useQuery({
    queryKey: ['validation', 'run', runId],
    queryFn: () => api.get<ValidationRunDetail>(`/validation/runs/${runId}`),
    staleTime: 30000,
    enabled: !!runId,
  })
}

/**
 * Fetch paginated quality scores.
 */
export function useQualityScores(options?: {
  seasonId?: number
  entityType?: 'season' | 'game'
  page?: number
  pageSize?: number
}) {
  const { seasonId, entityType, page = 1, pageSize = 20 } = options ?? {}

  return useQuery({
    queryKey: ['validation', 'scores', seasonId, entityType, page, pageSize],
    queryFn: () => {
      const params: Record<string, string> = {
        page: String(page),
        page_size: String(pageSize),
      }
      if (seasonId) params.season_id = String(seasonId)
      if (entityType) params.entity_type = entityType
      return api.get<QualityScoresResponse>('/validation/scores', params)
    },
    staleTime: 30000,
  })
}

/**
 * Fetch quality score for a specific entity.
 */
export function useEntityQualityScore(
  entityType: 'season' | 'game',
  entityId: string
) {
  return useQuery({
    queryKey: ['validation', 'score', entityType, entityId],
    queryFn: () =>
      api.get<QualityScore>(`/validation/scores/${entityType}/${entityId}`),
    staleTime: 60000,
    enabled: !!entityType && !!entityId,
  })
}

/**
 * Fetch paginated discrepancies list.
 */
export function useDiscrepancies(options?: {
  seasonId?: number
  status?: 'open' | 'resolved' | 'ignored'
  entityType?: string
  page?: number
  pageSize?: number
}) {
  const { seasonId, status, entityType, page = 1, pageSize = 20 } = options ?? {}

  return useQuery({
    queryKey: ['validation', 'discrepancies', seasonId, status, entityType, page, pageSize],
    queryFn: () => {
      const params: Record<string, string> = {
        page: String(page),
        page_size: String(pageSize),
      }
      if (seasonId) params.season_id = String(seasonId)
      if (status) params.status = status
      if (entityType) params.entity_type = entityType
      return api.get<DiscrepanciesResponse>('/validation/discrepancies', params)
    },
    staleTime: 30000,
  })
}

/**
 * Fetch detailed discrepancy with source values.
 */
export function useDiscrepancy(discrepancyId: number) {
  return useQuery({
    queryKey: ['validation', 'discrepancy', discrepancyId],
    queryFn: () =>
      api.get<DiscrepancyDetail>(`/validation/discrepancies/${discrepancyId}`),
    staleTime: 60000,
    enabled: !!discrepancyId,
  })
}

/**
 * Trigger a validation run for a season or game.
 * Invalidates relevant queries on success.
 */
export function useTriggerValidation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (request: ValidationRunRequest) =>
      api.post<ValidationRunResponse>('/validation/run', request),
    onSuccess: (_data, variables) => {
      // Invalidate relevant queries to trigger refetch
      if (variables.season_id) {
        queryClient.invalidateQueries({
          queryKey: ['validation', 'runs', variables.season_id],
        })
        queryClient.invalidateQueries({
          queryKey: ['validation', 'summary', variables.season_id],
        })
        queryClient.invalidateQueries({
          queryKey: ['validation', 'discrepancies', variables.season_id],
        })
      }
    },
  })
}

/**
 * Fetch season validation summary.
 */
export function useSeasonSummary(seasonId: number) {
  return useQuery({
    queryKey: ['validation', 'summary', seasonId],
    queryFn: () =>
      api.get<SeasonSummary>(`/validation/summary/${seasonId}`),
    staleTime: 30000,
    enabled: !!seasonId,
  })
}

// =============================================================================
// Export Types
// =============================================================================

export type {
  ValidationRule,
  ValidationRulesResponse,
  ValidationRunRequest,
  ValidationRunResponse,
  SeasonSummary,
  SourceAccuracy,
  ValidationResult,
  ValidationRunSummary,
  ValidationRunDetail,
  ValidationRunsResponse,
  QualityScore,
  QualityScoresResponse,
  DiscrepancySummary,
  DiscrepancyDetail,
  DiscrepanciesResponse,
}
