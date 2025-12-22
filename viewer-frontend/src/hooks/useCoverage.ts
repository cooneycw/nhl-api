import { useQuery } from '@tanstack/react-query'
import { api, type CoverageResponse } from '@/lib/api'

interface UseCoverageOptions {
  seasonIds?: number[]
  includeAll?: boolean
}

export function useCoverage(options: UseCoverageOptions = {}) {
  const { seasonIds, includeAll = false } = options

  return useQuery({
    queryKey: ['coverage', seasonIds, includeAll],
    queryFn: async () => {
      const params: Record<string, string> = {}

      if (seasonIds && seasonIds.length > 0) {
        // Pass season_ids as comma-separated for query string
        params.season_ids = seasonIds.join(',')
      }

      if (includeAll) {
        params.include_all = 'true'
      }

      return api.get<CoverageResponse>('/coverage/summary', params)
    },
    refetchInterval: 60000, // Refresh every 60 seconds
  })
}
