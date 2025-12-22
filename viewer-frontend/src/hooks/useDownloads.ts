import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'

// Types

interface SeasonOption {
  season_id: number
  start_year: number
  end_year: number
  is_current: boolean
  label: string
}

interface SourceOption {
  source_id: number
  name: string
  source_type: string
  description: string | null
  display_name: string
  is_active: boolean
}

interface SourceGroup {
  source_type: string
  display_name: string
  sources: SourceOption[]
}

interface DownloadOptionsResponse {
  seasons: SeasonOption[]
  source_groups: SourceGroup[]
}

interface ActiveDownload {
  batch_id: number
  source_id: number
  source_name: string
  source_type: string
  season_id: number
  season_label: string
  started_at: string
  items_total: number | null
  items_completed: number
  items_failed: number
  progress_percent: number | null
}

interface ActiveDownloadsResponse {
  downloads: ActiveDownload[]
  count: number
}

interface StartDownloadRequest {
  season_ids: number[]
  source_names: string[]
  force?: boolean
}

interface BatchCreated {
  batch_id: number
  source_name: string
  season_id: number
}

interface StartDownloadResponse {
  batches: BatchCreated[]
  message: string
}

interface CancelDownloadResponse {
  batch_id: number
  cancelled: boolean
  message: string
}

interface DeleteSeasonResponse {
  season_id: number
  dry_run: boolean
  deleted_counts: Record<string, number>
  total_records_deleted: number
  execution_time_ms: number
  message: string
}

// Hooks

export function useDownloadOptions() {
  return useQuery({
    queryKey: ['downloads', 'options'],
    queryFn: () => api.get<DownloadOptionsResponse>('/downloads/options'),
    staleTime: 5 * 60 * 1000, // 5 minutes - options don't change often
  })
}

export function useActiveDownloads() {
  return useQuery({
    queryKey: ['downloads', 'active'],
    queryFn: () => api.get<ActiveDownloadsResponse>('/downloads/active'),
    refetchInterval: 2000, // Poll every 2 seconds for progress updates
  })
}

export function useStartDownload() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (request: StartDownloadRequest) =>
      api.post<StartDownloadResponse>('/downloads/start', request),
    onSuccess: () => {
      // Immediately refetch active downloads
      queryClient.invalidateQueries({ queryKey: ['downloads', 'active'] })
      // Also refresh monitoring dashboard
      queryClient.invalidateQueries({ queryKey: ['monitoring'] })
    },
  })
}

export function useCancelDownload() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (batchId: number) =>
      api.post<CancelDownloadResponse>(`/downloads/${batchId}/cancel`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['downloads', 'active'] })
      queryClient.invalidateQueries({ queryKey: ['monitoring'] })
    },
  })
}

export function useDeleteSeason() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ seasonId, dryRun = false }: { seasonId: number; dryRun?: boolean }) =>
      api.delete<DeleteSeasonResponse>(
        `/monitoring/seasons/${seasonId}/data`,
        { dry_run: dryRun.toString() }
      ),
    onSuccess: (data) => {
      // If it was a real delete (not dry run), invalidate all queries
      if (!data.dry_run) {
        queryClient.invalidateQueries({ queryKey: ['players'] })
        queryClient.invalidateQueries({ queryKey: ['games'] })
        queryClient.invalidateQueries({ queryKey: ['teams'] })
        queryClient.invalidateQueries({ queryKey: ['monitoring'] })
        queryClient.invalidateQueries({ queryKey: ['downloads'] })
        queryClient.invalidateQueries({ queryKey: ['validation'] })
      }
    },
  })
}

// Export types for use in components
export type {
  SeasonOption,
  SourceOption,
  SourceGroup,
  DownloadOptionsResponse,
  ActiveDownload,
  ActiveDownloadsResponse,
  StartDownloadRequest,
  DeleteSeasonResponse,
}
