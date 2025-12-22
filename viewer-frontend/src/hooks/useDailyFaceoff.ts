import { useQuery } from '@tanstack/react-query'
import { api, type TeamLineCombinationsResponse, type TeamPowerPlayResponse, type TeamPenaltyKillResponse, type TeamInjuriesResponse, type LeagueInjuriesResponse, type TodaysStartersResponse } from '@/lib/api'

// Team line combinations
export function useTeamLines(teamAbbrev: string, snapshotDate?: string) {
  return useQuery({
    queryKey: ['dailyfaceoff', 'lines', teamAbbrev, snapshotDate],
    queryFn: () => api.get<TeamLineCombinationsResponse>(
      `/dailyfaceoff/lines/${teamAbbrev}`,
      snapshotDate ? { snapshot_date: snapshotDate } : undefined
    ),
    enabled: !!teamAbbrev,
  })
}

// Line history dates
export function useLineHistory(teamAbbrev: string, limit: number = 30) {
  return useQuery({
    queryKey: ['dailyfaceoff', 'lines', teamAbbrev, 'history', limit],
    queryFn: () => api.get<string[]>(
      `/dailyfaceoff/lines/${teamAbbrev}/history`,
      { limit: String(limit) }
    ),
    enabled: !!teamAbbrev,
  })
}

// Team power play units
export function useTeamPowerPlay(teamAbbrev: string, snapshotDate?: string) {
  return useQuery({
    queryKey: ['dailyfaceoff', 'power-play', teamAbbrev, snapshotDate],
    queryFn: () => api.get<TeamPowerPlayResponse>(
      `/dailyfaceoff/power-play/${teamAbbrev}`,
      snapshotDate ? { snapshot_date: snapshotDate } : undefined
    ),
    enabled: !!teamAbbrev,
  })
}

// Team penalty kill units
export function useTeamPenaltyKill(teamAbbrev: string, snapshotDate?: string) {
  return useQuery({
    queryKey: ['dailyfaceoff', 'penalty-kill', teamAbbrev, snapshotDate],
    queryFn: () => api.get<TeamPenaltyKillResponse>(
      `/dailyfaceoff/penalty-kill/${teamAbbrev}`,
      snapshotDate ? { snapshot_date: snapshotDate } : undefined
    ),
    enabled: !!teamAbbrev,
  })
}

// Team injuries
export function useTeamInjuries(teamAbbrev: string, snapshotDate?: string) {
  return useQuery({
    queryKey: ['dailyfaceoff', 'injuries', teamAbbrev, snapshotDate],
    queryFn: () => api.get<TeamInjuriesResponse>(
      `/dailyfaceoff/injuries/${teamAbbrev}`,
      snapshotDate ? { snapshot_date: snapshotDate } : undefined
    ),
    enabled: !!teamAbbrev,
  })
}

// League-wide injuries
export function useLeagueInjuries(snapshotDate?: string, statusFilter?: string) {
  return useQuery({
    queryKey: ['dailyfaceoff', 'injuries', 'league', snapshotDate, statusFilter],
    queryFn: () => {
      const params: Record<string, string> = {}
      if (snapshotDate) params.snapshot_date = snapshotDate
      if (statusFilter) params.status_filter = statusFilter
      return api.get<LeagueInjuriesResponse>('/dailyfaceoff/injuries', params)
    },
    refetchInterval: 300000, // 5 minutes
  })
}

// Today's starting goalies
export function useTodaysStarters(gameDate?: string) {
  return useQuery({
    queryKey: ['dailyfaceoff', 'starting-goalies', gameDate],
    queryFn: () => api.get<TodaysStartersResponse>(
      '/dailyfaceoff/starting-goalies',
      gameDate ? { game_date: gameDate } : undefined
    ),
    refetchInterval: 60000, // 1 minute (starting goalies can change)
  })
}
