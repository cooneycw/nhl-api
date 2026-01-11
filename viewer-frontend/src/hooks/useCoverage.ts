import { useQuery } from '@tanstack/react-query'
import { api, type CoverageResponse } from '@/lib/api'

interface UseCoverageOptions {
  seasonIds?: number[]
  includeAll?: boolean
  gameType?: number | null  // 1=Preseason, 2=Regular, 3=Playoffs, 4=All-Star
}

export function useCoverage(options: UseCoverageOptions = {}) {
  const { seasonIds, includeAll = false, gameType } = options

  return useQuery({
    queryKey: ['coverage', seasonIds, includeAll, gameType],
    queryFn: async () => {
      const params: Record<string, string> = {}

      if (seasonIds && seasonIds.length > 0) {
        // Pass season_ids as comma-separated for query string
        params.season_ids = seasonIds.join(',')
      }

      if (includeAll) {
        params.include_all = 'true'
      }

      if (gameType !== undefined && gameType !== null) {
        params.game_type = gameType.toString()
      }

      return api.get<CoverageResponse>('/coverage/summary', params)
    },
    refetchInterval: 60000, // Refresh every 60 seconds
  })
}
