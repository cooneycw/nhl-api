import { useState } from 'react'
import { ChevronLeft, ChevronRight, ExternalLink, AlertCircle } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import {
  useGames,
  type GameSummary,
  type GameFilters,
} from '@/hooks/useGames'
import { TeamLink, GameLink, formatGameDate } from '@/components/EntityLinks'

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
  const [filters, setFilters] = useState<GameFilters>({
    page: 1,
    per_page: 25,
    season: '20242025',
  })

  const { data, isLoading, error } = useGames(filters)

  const games = data?.games || []
  const pagination = data?.pagination

  const handlePageChange = (newPage: number) => {
    setFilters((prev) => ({ ...prev, page: newPage }))
  }

  const handleSeasonChange = (season: string) => {
    setFilters((prev) => ({ ...prev, season, page: 1 }))
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Games</h1>
        <p className="text-muted-foreground">
          Browse NHL games by date and team
        </p>
      </div>

      {/* Filters */}
      <Card>
        <CardHeader>
          <CardTitle>Filters</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-4">
            <div className="space-y-1">
              <label className="text-sm text-muted-foreground">Season</label>
              <div className="flex gap-2">
                {['20242025', '20232024', '20222023'].map((season) => (
                  <Button
                    key={season}
                    variant={filters.season === season ? 'default' : 'outline'}
                    size="sm"
                    onClick={() => handleSeasonChange(season)}
                  >
                    {season.slice(0, 4)}-{season.slice(4)}
                  </Button>
                ))}
              </div>
            </div>
            <div className="space-y-1">
              <label className="text-sm text-muted-foreground">Game Type</label>
              <div className="flex gap-2">
                {[
                  { value: undefined, label: 'All' },
                  { value: 'R' as const, label: 'Regular' },
                  { value: 'P' as const, label: 'Playoff' },
                  { value: 'PR' as const, label: 'Preseason' },
                ].map((type) => (
                  <Button
                    key={type.label}
                    variant={filters.game_type === type.value ? 'default' : 'outline'}
                    size="sm"
                    onClick={() =>
                      setFilters((prev) => ({ ...prev, game_type: type.value, page: 1 }))
                    }
                  >
                    {type.label}
                  </Button>
                ))}
              </div>
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
            <CardTitle>Game Schedule</CardTitle>
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
