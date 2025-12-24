import { useEffect, useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import { ChevronLeft, ChevronRight, ExternalLink, AlertCircle, X } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { Input } from '@/components/ui/input'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  useGames,
  type GameSummary,
  type GameFilters,
} from '@/hooks/useGames'
import { useTeams } from '@/hooks/useTeams'
import { useSeason } from '@/contexts/SeasonContext'
import { TeamLink, GameLink, formatGameDate } from '@/components/EntityLinks'

// Game type options
const GAME_TYPES = [
  { value: 'all', label: 'All Types' },
  { value: 'R', label: 'Regular Season' },
  { value: 'P', label: 'Playoffs' },
  { value: 'PR', label: 'Preseason' },
] as const

// Get game outcome badge
function GameOutcomeBadge({ game }: { game: GameSummary }) {
  const isFinal = game.game_state === 'Final' || game.game_state === 'OFF'

  if (!isFinal) {
    return <Badge variant="secondary">{game.game_state || 'Scheduled'}</Badge>
  }

  if (game.is_shootout) {
    return <Badge variant="outline">SO</Badge>
  } else if (game.is_overtime) {
    return <Badge variant="outline">OT</Badge>
  }

  return <Badge variant="default">Final</Badge>
}

// Games List Component
function GamesList({
  games,
  isLoading,
}: {
  games: GameSummary[]
  isLoading: boolean
}) {
  if (isLoading) {
    return (
      <div className="space-y-2">
        {[...Array(10)].map((_, i) => (
          <Skeleton key={i} className="h-12 w-full" />
        ))}
      </div>
    )
  }

  if (games.length === 0) {
    return (
      <div className="flex h-[200px] items-center justify-center text-muted-foreground">
        No games found for the selected filters
      </div>
    )
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Date</TableHead>
          <TableHead>Away</TableHead>
          <TableHead>Home</TableHead>
          <TableHead className="text-center">Score</TableHead>
          <TableHead className="text-center">Status</TableHead>
          <TableHead></TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {games.map((game) => (
          <TableRow key={game.game_id} className="hover:bg-muted/50">
            <TableCell className="font-medium">{formatGameDate(game.game_date)}</TableCell>
            <TableCell>
              {game.away_team_id ? (
                <TeamLink teamId={game.away_team_id} teamName={game.away_team_abbr} />
              ) : (
                <span className="font-medium">{game.away_team_abbr}</span>
              )}
            </TableCell>
            <TableCell>
              {game.home_team_id ? (
                <TeamLink teamId={game.home_team_id} teamName={game.home_team_abbr} />
              ) : (
                <span className="font-medium">{game.home_team_abbr}</span>
              )}
            </TableCell>
            <TableCell className="text-center">
              {game.game_state === 'Final' || game.game_state === 'OFF' ? (
                <span>
                  <span className={game.winner_abbr === game.away_team_abbr ? 'font-bold' : ''}>
                    {game.away_score}
                  </span>
                  <span className="text-muted-foreground"> - </span>
                  <span className={game.winner_abbr === game.home_team_abbr ? 'font-bold' : ''}>
                    {game.home_score}
                  </span>
                </span>
              ) : (
                <span className="text-muted-foreground">—</span>
              )}
            </TableCell>
            <TableCell className="text-center">
              <GameOutcomeBadge game={game} />
            </TableCell>
            <TableCell>
              <GameLink gameId={game.game_id} className="inline-flex items-center gap-1">
                Details <ExternalLink className="h-3 w-3" />
              </GameLink>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}

// Main Games Page
export function Games() {
  const [searchParams, setSearchParams] = useSearchParams()
  const { seasons, isLoading: seasonsLoading } = useSeason()
  const { data: teamsData, isLoading: teamsLoading } = useTeams({ active_only: true })

  // Flatten teams for the dropdown
  const allTeams = useMemo(() => {
    if (!teamsData?.divisions) return []
    return teamsData.divisions
      .flatMap((d) => d.teams)
      .sort((a, b) => a.name.localeCompare(b.name))
  }, [teamsData])

  // Parse filters from URL
  const filters: GameFilters = useMemo(() => {
    const defaultSeason = seasons.find((s) => s.is_current)?.season_id?.toString() || '20242025'
    return {
      page: parseInt(searchParams.get('page') || '1', 10),
      per_page: 25,
      season: searchParams.get('season') || defaultSeason,
      team_id: searchParams.get('team') ? parseInt(searchParams.get('team')!, 10) : undefined,
      game_type: (searchParams.get('type') as GameFilters['game_type']) || undefined,
      start_date: searchParams.get('from') || undefined,
      end_date: searchParams.get('to') || undefined,
    }
  }, [searchParams, seasons])

  // Sync default season to URL on first load
  useEffect(() => {
    if (!searchParams.has('season') && seasons.length > 0) {
      const defaultSeason = seasons.find((s) => s.is_current)?.season_id?.toString() || '20242025'
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev)
        next.set('season', defaultSeason)
        return next
      }, { replace: true })
    }
  }, [seasons, searchParams, setSearchParams])

  const { data, isLoading, error } = useGames(filters)

  const games = data?.games || []
  const pagination = data?.pagination

  // Update URL params helper
  const updateFilters = (updates: Partial<Record<string, string | undefined>>) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      Object.entries(updates).forEach(([key, value]) => {
        if (value === undefined || value === '' || value === 'all') {
          next.delete(key)
        } else {
          next.set(key, value)
        }
      })
      // Reset to page 1 when filters change (except for page itself)
      if (!('page' in updates)) {
        next.set('page', '1')
      }
      return next
    })
  }

  const handlePageChange = (newPage: number) => {
    updateFilters({ page: String(newPage) })
  }

  const clearFilters = () => {
    const defaultSeason = seasons.find((s) => s.is_current)?.season_id?.toString() || '20242025'
    setSearchParams({ season: defaultSeason })
  }

  const hasActiveFilters = filters.team_id || filters.game_type || filters.start_date || filters.end_date

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Games</h1>
        <p className="text-muted-foreground">
          Browse NHL games by season, team, and date
        </p>
      </div>

      {/* Filters */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle>Filters</CardTitle>
            {hasActiveFilters && (
              <Button variant="ghost" size="sm" onClick={clearFilters} className="h-8 px-2">
                <X className="mr-1 h-4 w-4" />
                Clear filters
              </Button>
            )}
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
            {/* Season Select */}
            <div className="space-y-2">
              <label htmlFor="season-select" className="text-sm font-medium">
                Season
              </label>
              <Select
                value={filters.season || ''}
                onValueChange={(value) => updateFilters({ season: value })}
                disabled={seasonsLoading}
              >
                <SelectTrigger id="season-select">
                  <SelectValue placeholder="Select season" />
                </SelectTrigger>
                <SelectContent>
                  {seasons.map((season) => (
                    <SelectItem key={season.season_id} value={String(season.season_id)}>
                      {season.label}
                      {season.is_current && ' (Current)'}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Game Type Select */}
            <div className="space-y-2">
              <label htmlFor="type-select" className="text-sm font-medium">
                Game Type
              </label>
              <Select
                value={filters.game_type || 'all'}
                onValueChange={(value) => updateFilters({ type: value === 'all' ? undefined : value })}
              >
                <SelectTrigger id="type-select">
                  <SelectValue placeholder="All types" />
                </SelectTrigger>
                <SelectContent>
                  {GAME_TYPES.map((type) => (
                    <SelectItem key={type.value} value={type.value}>
                      {type.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Team Select */}
            <div className="space-y-2">
              <label htmlFor="team-select" className="text-sm font-medium">
                Team
              </label>
              <Select
                value={filters.team_id ? String(filters.team_id) : 'all'}
                onValueChange={(value) => updateFilters({ team: value === 'all' ? undefined : value })}
                disabled={teamsLoading}
              >
                <SelectTrigger id="team-select">
                  <SelectValue placeholder="All teams" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Teams</SelectItem>
                  {allTeams.map((team) => (
                    <SelectItem key={team.team_id} value={String(team.team_id)}>
                      {team.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Date Range - From */}
            <div className="space-y-2">
              <label htmlFor="date-from" className="text-sm font-medium">
                From Date
              </label>
              <Input
                id="date-from"
                type="date"
                value={filters.start_date || ''}
                onChange={(e) => updateFilters({ from: e.target.value || undefined })}
                className="w-full"
              />
            </div>

            {/* Date Range - To */}
            <div className="space-y-2">
              <label htmlFor="date-to" className="text-sm font-medium">
                To Date
              </label>
              <Input
                id="date-to"
                type="date"
                value={filters.end_date || ''}
                onChange={(e) => updateFilters({ to: e.target.value || undefined })}
                className="w-full"
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Error State */}
      {error && (
        <Card>
          <CardContent className="flex items-center gap-2 py-6 text-destructive">
            <AlertCircle className="h-5 w-5" />
            <span>Failed to load games. Please try again.</span>
          </CardContent>
        </Card>
      )}

      {/* Games List */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle>Game Results</CardTitle>
            <CardDescription>
              {pagination
                ? `Showing ${(pagination.page - 1) * pagination.per_page + 1}-${Math.min(
                    pagination.page * pagination.per_page,
                    pagination.total_items
                  )} of ${pagination.total_items} games`
                : 'Loading...'}
            </CardDescription>
          </div>
          {pagination && pagination.total_pages > 1 && (
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => handlePageChange(pagination.page - 1)}
                disabled={pagination.page <= 1}
              >
                <ChevronLeft className="h-4 w-4" />
                Previous
              </Button>
              <span className="text-sm text-muted-foreground">
                Page {pagination.page} of {pagination.total_pages}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => handlePageChange(pagination.page + 1)}
                disabled={pagination.page >= pagination.total_pages}
              >
                Next
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          )}
        </CardHeader>
        <CardContent>
          <GamesList games={games} isLoading={isLoading} />
        </CardContent>
      </Card>
    </div>
  )
}
