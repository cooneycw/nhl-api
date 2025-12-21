import { useState } from 'react'
import { ChevronLeft, ChevronRight, Trophy, Clock, MapPin, Users, AlertCircle } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  useGames,
  useGameDetail,
  useGameEvents,
  useGameStats,
  type GameSummary,
  type GameFilters,
} from '@/hooks/useGames'

// Format date for display
function formatDate(dateStr: string): string {
  const date = new Date(dateStr)
  return date.toLocaleDateString('en-US', {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

// Format game type
function formatGameType(type: string): string {
  const types: Record<string, string> = {
    PR: 'Preseason',
    R: 'Regular',
    P: 'Playoff',
    A: 'All-Star',
  }
  return types[type] || type
}

// Get game outcome badge
function GameOutcomeBadge({ game }: { game: GameSummary }) {
  if (game.game_state !== 'Final') {
    return <Badge variant="secondary">{game.game_state || 'Scheduled'}</Badge>
  }

  const badges = []
  if (game.is_shootout) {
    badges.push(<Badge key="so" variant="warning">SO</Badge>)
  } else if (game.is_overtime) {
    badges.push(<Badge key="ot" variant="warning">OT</Badge>)
  }

  return <>{badges}</>
}

// Games List Component
function GamesList({
  games,
  selectedGameId,
  onSelectGame,
  isLoading,
}: {
  games: GameSummary[]
  selectedGameId: number | null
  onSelectGame: (gameId: number) => void
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
          <TableHead>Matchup</TableHead>
          <TableHead className="text-center">Score</TableHead>
          <TableHead className="text-center">Status</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {games.map((game) => (
          <TableRow
            key={game.game_id}
            className={`cursor-pointer ${selectedGameId === game.game_id ? 'bg-muted' : ''}`}
            onClick={() => onSelectGame(game.game_id)}
          >
            <TableCell className="font-medium">{formatDate(game.game_date)}</TableCell>
            <TableCell>
              <span className="font-medium">{game.away_team_abbr}</span>
              <span className="text-muted-foreground"> @ </span>
              <span className="font-medium">{game.home_team_abbr}</span>
            </TableCell>
            <TableCell className="text-center">
              {game.game_state === 'Final' ? (
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
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}

// Game Detail Overview Tab
function OverviewTab({ gameId }: { gameId: number }) {
  const { data: game, isLoading, error } = useGameDetail(gameId)

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-24 w-full" />
      </div>
    )
  }

  if (error || !game) {
    return (
      <div className="flex items-center gap-2 text-destructive">
        <AlertCircle className="h-4 w-4" />
        Failed to load game details
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Score Card */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex items-center justify-center gap-8">
            <div className="text-center">
              <div className="text-2xl font-bold">{game.away_team_abbr}</div>
              <div className="text-sm text-muted-foreground">{game.away_team_name}</div>
              <div className="mt-2 text-4xl font-bold">{game.away_score ?? 0}</div>
            </div>
            <div className="text-center">
              <div className="text-muted-foreground">@</div>
              <div className="text-sm text-muted-foreground mt-1">
                {game.game_outcome || 'Final'}
              </div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold">{game.home_team_abbr}</div>
              <div className="text-sm text-muted-foreground">{game.home_team_name}</div>
              <div className="mt-2 text-4xl font-bold">{game.home_score ?? 0}</div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Game Info */}
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardContent className="flex items-center gap-3 pt-6">
            <Clock className="h-5 w-5 text-muted-foreground" />
            <div>
              <div className="text-sm text-muted-foreground">Date & Time</div>
              <div className="font-medium">{formatDate(game.game_date)}</div>
              {game.game_time && (
                <div className="text-sm text-muted-foreground">{game.game_time}</div>
              )}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="flex items-center gap-3 pt-6">
            <MapPin className="h-5 w-5 text-muted-foreground" />
            <div>
              <div className="text-sm text-muted-foreground">Venue</div>
              <div className="font-medium">{game.venue_name || 'TBD'}</div>
              {game.venue_city && (
                <div className="text-sm text-muted-foreground">{game.venue_city}</div>
              )}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="flex items-center gap-3 pt-6">
            <Users className="h-5 w-5 text-muted-foreground" />
            <div>
              <div className="text-sm text-muted-foreground">Attendance</div>
              <div className="font-medium">
                {game.attendance?.toLocaleString() || 'N/A'}
              </div>
              <div className="text-sm text-muted-foreground">
                {formatGameType(game.game_type)}
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

// Play-by-Play Tab
function PlayByPlayTab({ gameId }: { gameId: number }) {
  const [periodFilter, setPeriodFilter] = useState<number | undefined>(undefined)
  const { data, isLoading, error } = useGameEvents(gameId, { period: periodFilter })

  if (isLoading) {
    return (
      <div className="space-y-2">
        {[...Array(10)].map((_, i) => (
          <Skeleton key={i} className="h-10 w-full" />
        ))}
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="flex items-center gap-2 text-destructive">
        <AlertCircle className="h-4 w-4" />
        Failed to load events
      </div>
    )
  }

  const periods = [...new Set(data.events.map((e) => e.period))].sort()

  return (
    <div className="space-y-4">
      {/* Period Filter */}
      <div className="flex gap-2">
        <Button
          variant={periodFilter === undefined ? 'default' : 'outline'}
          size="sm"
          onClick={() => setPeriodFilter(undefined)}
        >
          All
        </Button>
        {periods.map((p) => (
          <Button
            key={p}
            variant={periodFilter === p ? 'default' : 'outline'}
            size="sm"
            onClick={() => setPeriodFilter(p)}
          >
            {p <= 3 ? `P${p}` : p === 4 ? 'OT' : `OT${p - 3}`}
          </Button>
        ))}
      </div>

      {/* Events Table */}
      <div className="max-h-[400px] overflow-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-[60px]">Period</TableHead>
              <TableHead className="w-[80px]">Time</TableHead>
              <TableHead className="w-[80px]">Type</TableHead>
              <TableHead>Description</TableHead>
              <TableHead className="w-[80px] text-center">Score</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.events.length === 0 ? (
              <TableRow>
                <TableCell colSpan={5} className="text-center text-muted-foreground">
                  No events found
                </TableCell>
              </TableRow>
            ) : (
              data.events.map((event) => (
                <TableRow key={event.event_idx}>
                  <TableCell>{event.period}</TableCell>
                  <TableCell>{event.time_in_period || '—'}</TableCell>
                  <TableCell>
                    <Badge variant={event.event_type === 'goal' ? 'success' : 'secondary'}>
                      {event.event_type}
                    </Badge>
                  </TableCell>
                  <TableCell className="max-w-[300px] truncate">
                    {event.description || `${event.player1_name || ''} ${event.event_type}`}
                  </TableCell>
                  <TableCell className="text-center">
                    {event.away_score} - {event.home_score}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      <div className="text-sm text-muted-foreground">
        Total events: {data.total_events}
      </div>
    </div>
  )
}

// Goals Tab
function GoalsTab({ gameId }: { gameId: number }) {
  const { data, isLoading, error } = useGameEvents(gameId, { event_type: 'goal' })

  if (isLoading) {
    return <Skeleton className="h-[200px] w-full" />
  }

  if (error || !data) {
    return (
      <div className="flex items-center gap-2 text-destructive">
        <AlertCircle className="h-4 w-4" />
        Failed to load goals
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {data.events.length === 0 ? (
        <div className="flex h-[200px] items-center justify-center text-muted-foreground">
          No goals scored
        </div>
      ) : (
        data.events.map((goal) => (
          <Card key={goal.event_idx}>
            <CardContent className="flex items-center gap-4 py-4">
              <Trophy className="h-6 w-6 text-yellow-500" />
              <div className="flex-1">
                <div className="font-medium">
                  {goal.player1_name || 'Unknown'}
                  {goal.player2_name && (
                    <span className="text-muted-foreground"> from {goal.player2_name}</span>
                  )}
                  {goal.player3_name && (
                    <span className="text-muted-foreground"> and {goal.player3_name}</span>
                  )}
                </div>
                <div className="text-sm text-muted-foreground">
                  Period {goal.period} • {goal.time_in_period}
                  {goal.shot_type && ` • ${goal.shot_type}`}
                </div>
              </div>
              <div className="text-right">
                <Badge>{goal.team_abbr}</Badge>
                <div className="mt-1 text-sm text-muted-foreground">
                  {goal.away_score} - {goal.home_score}
                </div>
              </div>
            </CardContent>
          </Card>
        ))
      )}
    </div>
  )
}

// Penalties Tab
function PenaltiesTab({ gameId }: { gameId: number }) {
  const { data, isLoading, error } = useGameEvents(gameId, { event_type: 'penalty' })

  if (isLoading) {
    return <Skeleton className="h-[200px] w-full" />
  }

  if (error || !data) {
    return (
      <div className="flex items-center gap-2 text-destructive">
        <AlertCircle className="h-4 w-4" />
        Failed to load penalties
      </div>
    )
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Period</TableHead>
          <TableHead>Time</TableHead>
          <TableHead>Team</TableHead>
          <TableHead>Player</TableHead>
          <TableHead>Infraction</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {data.events.length === 0 ? (
          <TableRow>
            <TableCell colSpan={5} className="text-center text-muted-foreground">
              No penalties called
            </TableCell>
          </TableRow>
        ) : (
          data.events.map((penalty) => (
            <TableRow key={penalty.event_idx}>
              <TableCell>{penalty.period}</TableCell>
              <TableCell>{penalty.time_in_period || '—'}</TableCell>
              <TableCell>
                <Badge variant="outline">{penalty.team_abbr}</Badge>
              </TableCell>
              <TableCell>{penalty.player1_name || 'Team'}</TableCell>
              <TableCell className="max-w-[200px] truncate">
                {penalty.description || 'Penalty'}
              </TableCell>
            </TableRow>
          ))
        )}
      </TableBody>
    </Table>
  )
}

// Player Stats Tab
function PlayerStatsTab({ gameId }: { gameId: number }) {
  const { data, isLoading, error } = useGameStats(gameId)

  if (isLoading) {
    return <Skeleton className="h-[400px] w-full" />
  }

  if (error || !data) {
    return (
      <div className="flex items-center gap-2 text-destructive">
        <AlertCircle className="h-4 w-4" />
        Failed to load player stats
      </div>
    )
  }

  const renderSkaterTable = (skaters: typeof data.home_skaters, teamAbbr: string) => (
    <div className="space-y-2">
      <h4 className="font-semibold">{teamAbbr} Skaters</h4>
      <div className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Player</TableHead>
              <TableHead className="text-center">G</TableHead>
              <TableHead className="text-center">A</TableHead>
              <TableHead className="text-center">P</TableHead>
              <TableHead className="text-center">+/-</TableHead>
              <TableHead className="text-center">PIM</TableHead>
              <TableHead className="text-center">SOG</TableHead>
              <TableHead className="text-center">TOI</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {skaters.length === 0 ? (
              <TableRow>
                <TableCell colSpan={8} className="text-center text-muted-foreground">
                  No skater data available
                </TableCell>
              </TableRow>
            ) : (
              skaters.map((player) => (
                <TableRow key={player.player_id}>
                  <TableCell className="font-medium">{player.player_name}</TableCell>
                  <TableCell className="text-center">{player.goals}</TableCell>
                  <TableCell className="text-center">{player.assists}</TableCell>
                  <TableCell className="text-center font-semibold">{player.points}</TableCell>
                  <TableCell className="text-center">
                    {player.plus_minus > 0 ? `+${player.plus_minus}` : player.plus_minus}
                  </TableCell>
                  <TableCell className="text-center">{player.pim}</TableCell>
                  <TableCell className="text-center">{player.shots}</TableCell>
                  <TableCell className="text-center">{player.toi_formatted}</TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  )

  const renderGoalieTable = (goalies: typeof data.home_goalies, teamAbbr: string) => (
    <div className="space-y-2">
      <h4 className="font-semibold">{teamAbbr} Goalies</h4>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Player</TableHead>
            <TableHead className="text-center">Dec</TableHead>
            <TableHead className="text-center">SA</TableHead>
            <TableHead className="text-center">SV</TableHead>
            <TableHead className="text-center">SV%</TableHead>
            <TableHead className="text-center">TOI</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {goalies.length === 0 ? (
            <TableRow>
              <TableCell colSpan={6} className="text-center text-muted-foreground">
                No goalie data available
              </TableCell>
            </TableRow>
          ) : (
            goalies.map((goalie) => (
              <TableRow key={goalie.player_id}>
                <TableCell className="font-medium">
                  {goalie.player_name}
                  {goalie.is_starter && (
                    <Badge variant="secondary" className="ml-2">
                      Start
                    </Badge>
                  )}
                </TableCell>
                <TableCell className="text-center">
                  {goalie.decision ? (
                    <Badge
                      variant={goalie.decision === 'W' ? 'success' : 'destructive'}
                    >
                      {goalie.decision}
                    </Badge>
                  ) : (
                    '—'
                  )}
                </TableCell>
                <TableCell className="text-center">{goalie.shots_against}</TableCell>
                <TableCell className="text-center">{goalie.saves}</TableCell>
                <TableCell className="text-center">
                  {goalie.save_pct ? (goalie.save_pct * 100).toFixed(1) + '%' : '—'}
                </TableCell>
                <TableCell className="text-center">{goalie.toi_formatted}</TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
    </div>
  )

  return (
    <div className="space-y-6">
      <div className="grid gap-6 lg:grid-cols-2">
        <div className="space-y-4">
          {renderSkaterTable(data.away_skaters, data.away_team_abbr)}
          {renderGoalieTable(data.away_goalies, data.away_team_abbr)}
        </div>
        <div className="space-y-4">
          {renderSkaterTable(data.home_skaters, data.home_team_abbr)}
          {renderGoalieTable(data.home_goalies, data.home_team_abbr)}
        </div>
      </div>
    </div>
  )
}

// Game Detail Component with Tabs
function GameDetail({
  gameId,
  onPrevious,
  onNext,
  hasPrevious,
  hasNext,
}: {
  gameId: number
  onPrevious: () => void
  onNext: () => void
  hasPrevious: boolean
  hasNext: boolean
}) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <div>
          <CardTitle>Game Details</CardTitle>
          <CardDescription>Game ID: {gameId}</CardDescription>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="icon"
            onClick={onPrevious}
            disabled={!hasPrevious}
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <Button
            variant="outline"
            size="icon"
            onClick={onNext}
            disabled={!hasNext}
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        <Tabs defaultValue="overview">
          <TabsList className="grid w-full grid-cols-5">
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="plays">Play-by-Play</TabsTrigger>
            <TabsTrigger value="goals">Goals</TabsTrigger>
            <TabsTrigger value="penalties">Penalties</TabsTrigger>
            <TabsTrigger value="stats">Stats</TabsTrigger>
          </TabsList>
          <TabsContent value="overview">
            <OverviewTab gameId={gameId} />
          </TabsContent>
          <TabsContent value="plays">
            <PlayByPlayTab gameId={gameId} />
          </TabsContent>
          <TabsContent value="goals">
            <GoalsTab gameId={gameId} />
          </TabsContent>
          <TabsContent value="penalties">
            <PenaltiesTab gameId={gameId} />
          </TabsContent>
          <TabsContent value="stats">
            <PlayerStatsTab gameId={gameId} />
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  )
}

// Main Games Page
export function Games() {
  const [filters, setFilters] = useState<GameFilters>({
    page: 1,
    per_page: 25,
    season: '20242025',
  })
  const [selectedGameId, setSelectedGameId] = useState<number | null>(null)

  const { data, isLoading, error } = useGames(filters)

  const games = data?.games || []
  const pagination = data?.pagination

  // Find selected game index for navigation
  const selectedIndex = games.findIndex((g) => g.game_id === selectedGameId)

  const handlePreviousGame = () => {
    if (selectedIndex > 0) {
      setSelectedGameId(games[selectedIndex - 1].game_id)
    }
  }

  const handleNextGame = () => {
    if (selectedIndex < games.length - 1) {
      setSelectedGameId(games[selectedIndex + 1].game_id)
    }
  }

  const handlePageChange = (newPage: number) => {
    setFilters((prev) => ({ ...prev, page: newPage }))
    setSelectedGameId(null)
  }

  const handleSeasonChange = (season: string) => {
    setFilters((prev) => ({ ...prev, season, page: 1 }))
    setSelectedGameId(null)
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
            <CardTitle>Games</CardTitle>
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
          <GamesList
            games={games}
            selectedGameId={selectedGameId}
            onSelectGame={setSelectedGameId}
            isLoading={isLoading}
          />
        </CardContent>
      </Card>

      {/* Game Detail */}
      {selectedGameId && (
        <GameDetail
          gameId={selectedGameId}
          onPrevious={handlePreviousGame}
          onNext={handleNextGame}
          hasPrevious={selectedIndex > 0}
          hasNext={selectedIndex < games.length - 1}
        />
      )}
    </div>
  )
}
