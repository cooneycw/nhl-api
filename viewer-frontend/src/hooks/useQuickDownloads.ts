import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'

// Types

interface SyncStatusItem {
  source_name: string
  source_display_name: string
  game_type: number
  game_type_label: string
  last_synced_at: string | null
  items_synced_count: number
  is_stale: boolean
}

interface SyncStatusResponse {
  season_id: number
  season_label: string
  items: SyncStatusItem[]
}

interface QuickDownloadResponse {
  action: string
  season_id: number
  season_label: string
  batches_started: number
  message: string
  batch_ids: number[]
}

interface PriorSeasonOption {
  season_id: number
  start_year: number
  end_year: number
  label: string
}

// Hooks

/**
 * Get sync status for current season.
 * Shows last sync time per source to help users understand what needs updating.
 */
export function useSyncStatus() {
  return useQuery({
    queryKey: ['downloads', 'quick', 'sync-status'],
    queryFn: () => api.get<SyncStatusResponse>('/downloads/quick/sync-status'),
    staleTime: 30 * 1000, // 30 seconds - sync status changes after downloads
  })
}

/**
 * Get list of prior seasons available for download.
 */
export function usePriorSeasons() {
  return useQuery({
    queryKey: ['downloads', 'quick', 'seasons'],
    queryFn: () => api.get<PriorSeasonOption[]>('/downloads/quick/seasons'),
    staleTime: 5 * 60 * 1000, // 5 minutes - seasons rarely change
  })
}

/**
 * Download current season pre-season games.
 */
export function useQuickPreseason() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: () => api.post<QuickDownloadResponse>('/downloads/quick/preseason'),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['downloads', 'active'] })
      queryClient.invalidateQueries({ queryKey: ['downloads', 'quick', 'sync-status'] })
      queryClient.invalidateQueries({ queryKey: ['monitoring'] })
    },
  })
}

/**
 * Download current season regular season games.
 */
export function useQuickRegular() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: () => api.post<QuickDownloadResponse>('/downloads/quick/regular'),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['downloads', 'active'] })
      queryClient.invalidateQueries({ queryKey: ['downloads', 'quick', 'sync-status'] })
      queryClient.invalidateQueries({ queryKey: ['monitoring'] })
    },
  })
}

/**
 * Download current season playoff games.
 */
export function useQuickPlayoffs() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: () => api.post<QuickDownloadResponse>('/downloads/quick/playoffs'),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['downloads', 'active'] })
      queryClient.invalidateQueries({ queryKey: ['downloads', 'quick', 'sync-status'] })
      queryClient.invalidateQueries({ queryKey: ['monitoring'] })
    },
  })
}

/**
 * Refresh external sources (DailyFaceoff, QuantHockey).
 */
export function useQuickExternal() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: () => api.post<QuickDownloadResponse>('/downloads/quick/external'),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['downloads', 'active'] })
      queryClient.invalidateQueries({ queryKey: ['downloads', 'quick', 'sync-status'] })
      queryClient.invalidateQueries({ queryKey: ['monitoring'] })
    },
  })
}

/**
 * Download a full prior season.
 */
export function useQuickPriorSeason() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (seasonId: number) =>
      api.post<QuickDownloadResponse>(`/downloads/quick/prior-season/${seasonId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['downloads', 'active'] })
      queryClient.invalidateQueries({ queryKey: ['downloads', 'quick', 'sync-status'] })
      queryClient.invalidateQueries({ queryKey: ['monitoring'] })
    },
  })
}

// Export types
export type {
  SyncStatusItem,
  SyncStatusResponse,
  QuickDownloadResponse,
  PriorSeasonOption,
}
