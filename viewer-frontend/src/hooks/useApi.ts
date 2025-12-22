import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api, type HealthResponse, type DashboardResponse, type BatchSummary, type SourceListResponse, type FailureListResponse, type RetryResponse } from '@/lib/api'

// Health check
export function useHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: () => api.get<HealthResponse>('/health'),
    refetchInterval: 30000, // 30 seconds
  })
}

// Dashboard stats
export function useDashboard() {
  return useQuery({
    queryKey: ['monitoring', 'dashboard'],
    queryFn: () => api.get<DashboardResponse>('/monitoring/dashboard'),
    refetchInterval: 10000, // 10 seconds for real-time updates
  })
}

// Batch list
export function useBatches(status?: string) {
  return useQuery({
    queryKey: ['monitoring', 'batches', status],
    queryFn: () => api.get<BatchSummary[]>('/monitoring/batches', status ? { status } : undefined),
    refetchInterval: 10000,
  })
}

// Source health
export function useSourceHealth() {
  return useQuery({
    queryKey: ['monitoring', 'sources'],
    queryFn: async () => {
      const response = await api.get<SourceListResponse>('/monitoring/sources')
      return response.sources
    },
    refetchInterval: 30000,
  })
}

// Failed downloads list
export function useFailures(page = 1, pageSize = 20) {
  return useQuery({
    queryKey: ['monitoring', 'failures', page, pageSize],
    queryFn: () => api.get<FailureListResponse>('/monitoring/failures', {
      page: String(page),
      page_size: String(pageSize),
    }),
    refetchInterval: 30000, // 30 seconds
  })
}

// Retry failed download
export function useRetryDownload() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (progressId: number) =>
      api.post<RetryResponse>(`/monitoring/failures/${progressId}/retry`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['monitoring'] })
    },
  })
}
