import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { PlayerSummary } from './usePlayers'
import type { GameSummary } from './useGames'

// Types

interface PaginationMeta {
  page: number
  per_page: number
  total_items: number
  total_pages: number
}

export interface TeamSummary {
  team_id: number
  name: string
  abbreviation: string
  team_name: string | null
  location_name: string | null
  division_id: number | null
  division_name: string | null
  conference_id: number | null
  conference_name: string | null
  active: boolean
}

export interface TeamDetail {
  team_id: number
  franchise_id: number | null
  name: string
  abbreviation: string
  team_name: string | null
  location_name: string | null
  division_id: number | null
  division_name: string | null
  conference_id: number | null
  conference_name: string | null
  venue_id: number | null
  venue_name: string | null
  first_year_of_play: number | null
  official_site_url: string | null
  active: boolean
  updated_at: string | null
}

export interface DivisionTeams {
  division_id: number
  division_name: string
  conference_name: string | null
  teams: TeamSummary[]
}

interface TeamListResponse {
  divisions: DivisionTeams[]
  total_teams: number
}

interface TeamWithRoster {
  team: TeamDetail
  roster: PlayerSummary[]
}

interface TeamRecentGamesResponse {
  team_id: number
  team_name: string
  team_abbr: string
  games: GameSummary[]
  pagination: PaginationMeta
}

// Filter types

export interface TeamFilters {
  active_only?: boolean
}

export interface TeamGameFilters {
  page?: number
  per_page?: number
  season?: string
}

// Hooks

export function useTeams(filters: TeamFilters = {}) {
  const params: Record<string, string> = {}

  if (filters.active_only !== undefined) params.active_only = String(filters.active_only)

  return useQuery({
    queryKey: ['teams', filters],
    queryFn: () => api.get<TeamListResponse>('/entities/teams', params),
    staleTime: 5 * 60 * 1000,
  })
}

export function useTeamDetail(teamId: number | null) {
  return useQuery({
    queryKey: ['teams', teamId],
    queryFn: () => api.get<TeamWithRoster>(`/entities/teams/${teamId}`),
    enabled: teamId !== null,
    staleTime: 5 * 60 * 1000,
  })
}

export function useTeamGames(teamId: number | null, filters: TeamGameFilters = {}) {
  const params: Record<string, string> = {}

  if (filters.page) params.page = String(filters.page)
  if (filters.per_page) params.per_page = String(filters.per_page)
  if (filters.season) params.season = filters.season

  return useQuery({
    queryKey: ['teams', teamId, 'games', filters],
    queryFn: () => api.get<TeamRecentGamesResponse>(`/entities/teams/${teamId}/games`, params),
    enabled: teamId !== null,
    staleTime: 5 * 60 * 1000,
  })
}
