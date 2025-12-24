import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'

// Types

interface PaginationMeta {
  page: number
  per_page: number
  total_items: number
  total_pages: number
}

export interface PlayerSummary {
  player_id: number
  first_name: string
  last_name: string
  full_name: string
  age: number | null
  primary_position: string | null
  position_type: 'F' | 'D' | 'G' | null
  current_team_id: number | null
  team_name: string | null
  team_abbreviation: string | null
  sweater_number: number | null
  headshot_url: string | null
  active: boolean
}

export interface PlayerDetail {
  player_id: number
  first_name: string
  last_name: string
  full_name: string
  birth_date: string | null
  age: number | null
  birth_country: string | null
  nationality: string | null
  height_inches: number | null
  height_display: string | null
  weight_lbs: number | null
  shoots_catches: string | null
  primary_position: string | null
  position_type: 'F' | 'D' | 'G' | null
  roster_status: string | null
  current_team_id: number | null
  team_name: string | null
  team_abbreviation: string | null
  division_name: string | null
  conference_name: string | null
  captain: boolean
  alternate_captain: boolean
  rookie: boolean
  nhl_experience: number | null
  sweater_number: number | null
  headshot_url: string | null
  active: boolean
  updated_at: string | null
}

interface PlayerListResponse {
  players: PlayerSummary[]
  pagination: PaginationMeta
}

export interface PlayerGameEntry {
  game_id: number
  game_date: string
  season_id: number
  opponent_team_id: number
  opponent_abbr: string
  opponent_name: string
  is_home: boolean
  result: string | null
  player_team_score: number | null
  opponent_score: number | null
  goals: number | null
  assists: number | null
  points: number | null
  plus_minus: number | null
  pim: number | null
  shots: number | null
  toi_display: string | null
  saves: number | null
  shots_against: number | null
  save_pct: number | null
  decision: string | null
}

interface PlayerGameLogResponse {
  player_id: number
  player_name: string
  position_type: string | null
  games: PlayerGameEntry[]
  pagination: PaginationMeta
}

// Filter types

export interface PlayerFilters {
  page?: number
  per_page?: number
  search?: string
  position?: 'C' | 'LW' | 'RW' | 'D' | 'G'
  team_id?: number
  active_only?: boolean
}

export interface PlayerGameFilters {
  page?: number
  per_page?: number
  season?: string
}

// Hooks

export function usePlayers(filters: PlayerFilters = {}) {
  const params: Record<string, string> = {}

  if (filters.page) params.page = String(filters.page)
  if (filters.per_page) params.per_page = String(filters.per_page)
  if (filters.search) params.search = filters.search
  if (filters.position) params.position = filters.position
  if (filters.team_id) params.team_id = String(filters.team_id)
  if (filters.active_only !== undefined) params.active_only = String(filters.active_only)

  return useQuery({
    queryKey: ['players', filters],
    queryFn: () => api.get<PlayerListResponse>('/players', params),
    staleTime: 60 * 1000,
  })
}

export function usePlayerDetail(playerId: number | null) {
  return useQuery({
    queryKey: ['players', playerId],
    queryFn: () => api.get<PlayerDetail>(`/players/${playerId}`),
    enabled: playerId !== null,
    staleTime: 5 * 60 * 1000,
  })
}

export function usePlayerGames(playerId: number | null, filters: PlayerGameFilters = {}) {
  const params: Record<string, string> = {}

  if (filters.page) params.page = String(filters.page)
  if (filters.per_page) params.per_page = String(filters.per_page)
  if (filters.season) params.season = filters.season

  return useQuery({
    queryKey: ['players', playerId, 'games', filters],
    queryFn: () => api.get<PlayerGameLogResponse>(`/players/${playerId}/games`, params),
    enabled: playerId !== null,
    staleTime: 5 * 60 * 1000,
  })
}
