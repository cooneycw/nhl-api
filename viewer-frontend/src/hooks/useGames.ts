import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'

// Types

interface PaginationMeta {
  page: number
  per_page: number
  total_items: number
  total_pages: number
}

export interface GameSummary {
  game_id: number
  season_id: number
  season_name: string | null
  game_type: string
  game_type_name: string | null
  game_date: string
  game_time: string | null
  venue_name: string | null
  home_team_id: number
  home_team_name: string
  home_team_abbr: string
  home_score: number | null
  away_team_id: number
  away_team_name: string
  away_team_abbr: string
  away_score: number | null
  game_state: string | null
  is_overtime: boolean
  is_shootout: boolean
  winner_abbr: string | null
}

export interface GameDetail extends GameSummary {
  venue_id: number | null
  venue_city: string | null
  final_period: number | null
  game_outcome: string | null
  winner_team_id: number | null
  goal_differential: number | null
  attendance: number | null
  game_duration_minutes: number | null
  updated_at: string | null
}

interface GameListResponse {
  games: GameSummary[]
  pagination: PaginationMeta
}

export interface PlayByPlayEvent {
  event_idx: number
  event_type: string
  period: number
  period_type: string | null
  time_in_period: string | null
  time_remaining: string | null
  description: string | null
  player1_id: number | null
  player1_name: string | null
  player1_role: string | null
  player2_id: number | null
  player2_name: string | null
  player2_role: string | null
  player3_id: number | null
  player3_name: string | null
  player3_role: string | null
  team_id: number | null
  team_abbr: string | null
  home_score: number
  away_score: number
  shot_type: string | null
  zone: string | null
  x_coord: number | null
  y_coord: number | null
}

interface GameEventsResponse {
  game_id: number
  events: PlayByPlayEvent[]
  total_events: number
}

export interface SkaterGameStats {
  player_id: number
  player_name: string
  team_id: number
  team_abbr: string
  position: string | null
  goals: number
  assists: number
  points: number
  plus_minus: number
  pim: number
  shots: number
  hits: number
  blocked_shots: number
  giveaways: number
  takeaways: number
  faceoff_pct: number | null
  toi_seconds: number
  toi_formatted: string
  shifts: number
  power_play_goals: number
  shorthanded_goals: number
}

export interface GoalieGameStats {
  player_id: number
  player_name: string
  team_id: number
  team_abbr: string
  saves: number
  shots_against: number
  goals_against: number
  save_pct: number | null
  toi_seconds: number
  toi_formatted: string
  even_strength_saves: number
  even_strength_shots: number
  power_play_saves: number
  power_play_shots: number
  shorthanded_saves: number
  shorthanded_shots: number
  is_starter: boolean
  decision: string | null
}

export interface GamePlayerStats {
  game_id: number
  home_team_id: number
  home_team_abbr: string
  away_team_id: number
  away_team_abbr: string
  home_skaters: SkaterGameStats[]
  away_skaters: SkaterGameStats[]
  home_goalies: GoalieGameStats[]
  away_goalies: GoalieGameStats[]
}

// Filter types

export interface GameFilters {
  page?: number
  per_page?: number
  season?: string
  team_id?: number
  start_date?: string
  end_date?: string
  game_type?: 'PR' | 'R' | 'P' | 'A'
}

export interface EventFilters {
  period?: number
  event_type?: string
}

// Hooks

export function useGames(filters: GameFilters = {}) {
  const params: Record<string, string> = {}

  if (filters.page) params.page = String(filters.page)
  if (filters.per_page) params.per_page = String(filters.per_page)
  if (filters.season) params.season = filters.season
  if (filters.team_id) params.team_id = String(filters.team_id)
  if (filters.start_date) params.start_date = filters.start_date
  if (filters.end_date) params.end_date = filters.end_date
  if (filters.game_type) params.game_type = filters.game_type

  return useQuery({
    queryKey: ['games', filters],
    queryFn: () => api.get<GameListResponse>('/entities/games', params),
    staleTime: 60 * 1000, // 1 minute
  })
}

export function useGameDetail(gameId: number | null) {
  return useQuery({
    queryKey: ['games', gameId],
    queryFn: () => api.get<GameDetail>(`/entities/games/${gameId}`),
    enabled: gameId !== null,
    staleTime: 5 * 60 * 1000, // 5 minutes
  })
}

export function useGameEvents(gameId: number | null, filters: EventFilters = {}) {
  const params: Record<string, string> = {}

  if (filters.period !== undefined) params.period = String(filters.period)
  if (filters.event_type) params.event_type = filters.event_type

  return useQuery({
    queryKey: ['games', gameId, 'events', filters],
    queryFn: () => api.get<GameEventsResponse>(`/entities/games/${gameId}/events`, params),
    enabled: gameId !== null,
    staleTime: 5 * 60 * 1000, // 5 minutes
  })
}

export function useGameStats(gameId: number | null) {
  return useQuery({
    queryKey: ['games', gameId, 'stats'],
    queryFn: () => api.get<GamePlayerStats>(`/entities/games/${gameId}/stats`),
    enabled: gameId !== null,
    staleTime: 5 * 60 * 1000, // 5 minutes
  })
}

// Shift types

export interface PlayerShiftSummary {
  player_id: number
  player_name: string
  sweater_number: number | null
  position: string | null
  team_id: number
  team_abbr: string
  total_toi_seconds: number
  total_toi_display: string
  total_shifts: number
  avg_shift_seconds: number
  period_1_toi: number
  period_2_toi: number
  period_3_toi: number
  ot_toi: number
}

export interface GameShiftsResponse {
  game_id: number
  home_team_id: number
  home_team_abbr: string
  away_team_id: number
  away_team_abbr: string
  home_players: PlayerShiftSummary[]
  away_players: PlayerShiftSummary[]
}

export function useGameShifts(gameId: number | null) {
  return useQuery({
    queryKey: ['games', gameId, 'shifts'],
    queryFn: () => api.get<GameShiftsResponse>(`/entities/games/${gameId}/shifts`),
    enabled: gameId !== null,
    staleTime: 5 * 60 * 1000, // 5 minutes
  })
}
