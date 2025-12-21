import { useParams, Link } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { usePlayerDetail, usePlayerGames } from '@/hooks/usePlayers'
import { TeamLink, GameLink, formatGameDate } from '@/components/EntityLinks'

export function PlayerDetail() {
  const { playerId } = useParams<{ playerId: string }>()
  const parsedPlayerId = playerId ? parseInt(playerId, 10) : null

  const { data: player, isLoading, error } = usePlayerDetail(parsedPlayerId)
  const { data: gamesData, isLoading: gamesLoading } = usePlayerGames(parsedPlayerId, { per_page: 20 })

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <Skeleton className="h-8 w-8" />
          <Skeleton className="h-8 w-48" />
        </div>
        <Skeleton className="h-64 w-full" />
      </div>
    )
  }

  if (error || !player) {
    return (
      <div className="space-y-6">
        <Link to="/players" className="flex items-center gap-2 text-muted-foreground hover:text-foreground">
          <ArrowLeft className="h-4 w-4" />
          Back to Players
        </Link>
        <Card className="border-destructive">
          <CardContent className="pt-6">
            <p className="text-destructive">{error ? `Error: ${error.message}` : 'Player not found'}</p>
          </CardContent>
        </Card>
      </div>
    )
  }

  const isGoalie = player.position_type === 'G'

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Link to="/players" className="text-muted-foreground hover:text-foreground">
          <ArrowLeft className="h-5 w-5" />
        </Link>
        <div className="flex items-center gap-4">
          {player.headshot_url && (
            <img src={player.headshot_url} alt={player.full_name} className="h-16 w-16 rounded-full object-cover" />
          )}
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-3xl font-bold">{player.full_name}</h1>
              {player.sweater_number && <span className="text-2xl text-muted-foreground font-mono">#{player.sweater_number}</span>}
              {player.captain && <Badge>C</Badge>}
              {player.alternate_captain && <Badge variant="secondary">A</Badge>}
              {player.rookie && <Badge variant="outline">Rookie</Badge>}
            </div>
            <p className="text-muted-foreground">
              {player.primary_position}
              {player.team_name && player.current_team_id && (
                <> &middot; <TeamLink teamId={player.current_team_id} teamName={player.team_name} /></>
              )}
            </p>
          </div>
        </div>
      </div>

      <Card>
        <CardContent className="pt-6">
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            <div><p className="text-sm text-muted-foreground">Age</p><p className="text-lg font-semibold">{player.age || 'N/A'}</p></div>
            <div><p className="text-sm text-muted-foreground">Birth Date</p><p className="text-lg font-semibold">{player.birth_date ? new Date(player.birth_date).toLocaleDateString() : 'N/A'}</p></div>
            <div><p className="text-sm text-muted-foreground">Nationality</p><p className="text-lg font-semibold">{player.nationality || player.birth_country || 'N/A'}</p></div>
            <div><p className="text-sm text-muted-foreground">Height / Weight</p><p className="text-lg font-semibold">{player.height_display || 'N/A'} / {player.weight_lbs ? `${player.weight_lbs} lbs` : 'N/A'}</p></div>
            <div><p className="text-sm text-muted-foreground">Shoots/Catches</p><p className="text-lg font-semibold">{player.shoots_catches || 'N/A'}</p></div>
            <div><p className="text-sm text-muted-foreground">NHL Experience</p><p className="text-lg font-semibold">{player.nhl_experience ? `${player.nhl_experience} years` : 'N/A'}</p></div>
            <div><p className="text-sm text-muted-foreground">Division</p><p className="text-lg font-semibold">{player.division_name || 'N/A'}</p></div>
            <div><p className="text-sm text-muted-foreground">Conference</p><p className="text-lg font-semibold">{player.conference_name || 'N/A'}</p></div>
          </div>
        </CardContent>
      </Card>

      <Tabs defaultValue="games">
        <TabsList><TabsTrigger value="games">Game Log</TabsTrigger></TabsList>

        <TabsContent value="games">
          <Card>
            <CardHeader><CardTitle className="text-lg">Recent Games</CardTitle></CardHeader>
            <CardContent>
              {gamesLoading ? (
                <div className="space-y-2">{Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-12 w-full" />)}</div>
              ) : gamesData?.games.length === 0 ? (
                <p className="text-muted-foreground">No games found</p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Date</TableHead>
                      <TableHead>Opponent</TableHead>
                      <TableHead>Result</TableHead>
                      {isGoalie ? (
                        <><TableHead className="text-right">SV</TableHead><TableHead className="text-right">SA</TableHead><TableHead className="text-right">SV%</TableHead><TableHead>Dec</TableHead></>
                      ) : (
                        <><TableHead className="text-right">G</TableHead><TableHead className="text-right">A</TableHead><TableHead className="text-right">P</TableHead><TableHead className="text-right">+/-</TableHead><TableHead className="text-right">TOI</TableHead></>
                      )}
                      <TableHead></TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {gamesData?.games.map((game) => (
                      <TableRow key={game.game_id}>
                        <TableCell>{formatGameDate(game.game_date)}</TableCell>
                        <TableCell>{game.is_home ? 'vs' : '@'} {game.opponent_abbr}</TableCell>
                        <TableCell>
                          <span className={game.result === 'W' ? 'text-green-600' : game.result === 'L' ? 'text-red-600' : ''}>
                            {game.result} {game.player_team_score}-{game.opponent_score}
                          </span>
                        </TableCell>
                        {isGoalie ? (
                          <>
                            <TableCell className="text-right">{game.saves}</TableCell>
                            <TableCell className="text-right">{game.shots_against}</TableCell>
                            <TableCell className="text-right">{game.save_pct?.toFixed(3)}</TableCell>
                            <TableCell>{game.decision}</TableCell>
                          </>
                        ) : (
                          <>
                            <TableCell className="text-right">{game.goals}</TableCell>
                            <TableCell className="text-right">{game.assists}</TableCell>
                            <TableCell className="text-right font-semibold">{game.points}</TableCell>
                            <TableCell className="text-right">{game.plus_minus !== null && game.plus_minus > 0 ? '+' : ''}{game.plus_minus}</TableCell>
                            <TableCell className="text-right font-mono text-sm">{game.toi_display}</TableCell>
                          </>
                        )}
                        <TableCell><GameLink gameId={game.game_id}>View</GameLink></TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
