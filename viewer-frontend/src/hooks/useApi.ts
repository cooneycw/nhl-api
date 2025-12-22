import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api, type HealthResponse, type DashboardResponse, type BatchSummary, type SourceListResponse } from '@/lib/api'

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

// Retry failed download
export function useRetryDownload() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (downloadId: string) =>
      api.post(`/monitoring/failures/${downloadId}/retry`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['monitoring'] })
    },
  })
}
