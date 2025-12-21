import { useParams, Link } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { useTeamDetail, useTeamGames } from '@/hooks/useTeams'
import { PlayerLink, GameLink, formatGameDate } from '@/components/EntityLinks'

export function TeamDetail() {
  const { teamId } = useParams<{ teamId: string }>()
  const parsedTeamId = teamId ? parseInt(teamId, 10) : null

  const { data, isLoading, error } = useTeamDetail(parsedTeamId)
  const { data: gamesData, isLoading: gamesLoading } = useTeamGames(parsedTeamId, { per_page: 10 })

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

  if (error || !data) {
    return (
      <div className="space-y-6">
        <Link to="/teams" className="flex items-center gap-2 text-muted-foreground hover:text-foreground">
          <ArrowLeft className="h-4 w-4" />
          Back to Teams
        </Link>
        <Card className="border-destructive">
          <CardContent className="pt-6">
            <p className="text-destructive">
              {error ? `Error: ${error.message}` : 'Team not found'}
            </p>
          </CardContent>
        </Card>
      </div>
    )
  }

  const { team, roster } = data
  const forwards = roster.filter((p) => p.position_type === 'F')
  const defensemen = roster.filter((p) => p.position_type === 'D')
  const goalies = roster.filter((p) => p.position_type === 'G')

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Link to="/teams" className="text-muted-foreground hover:text-foreground">
          <ArrowLeft className="h-5 w-5" />
        </Link>
        <div>
          <h1 className="text-3xl font-bold">{team.name}</h1>
          <p className="text-muted-foreground">
            {team.division_name} &middot; {team.conference_name}
          </p>
        </div>
      </div>

      <Card>
        <CardContent className="pt-6">
          <div className="grid gap-4 md:grid-cols-4">
            <div>
              <p className="text-sm text-muted-foreground">Abbreviation</p>
              <p className="text-lg font-semibold">{team.abbreviation}</p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Location</p>
              <p className="text-lg font-semibold">{team.location_name}</p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Venue</p>
              <p className="text-lg font-semibold">{team.venue_name || 'N/A'}</p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">First Year</p>
              <p className="text-lg font-semibold">{team.first_year_of_play || 'N/A'}</p>
            </div>
          </div>
        </CardContent>
      </Card>

      <Tabs defaultValue="roster">
        <TabsList>
          <TabsTrigger value="roster">Roster ({roster.length})</TabsTrigger>
          <TabsTrigger value="games">Recent Games</TabsTrigger>
        </TabsList>

        <TabsContent value="roster" className="space-y-6">
          {forwards.length > 0 && (
            <Card>
              <CardHeader><CardTitle className="text-lg">Forwards ({forwards.length})</CardTitle></CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-16">#</TableHead>
                      <TableHead>Player</TableHead>
                      <TableHead>Position</TableHead>
                      <TableHead>Age</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {forwards.map((p) => (
                      <TableRow key={p.player_id}>
                        <TableCell className="font-mono">{p.sweater_number}</TableCell>
                        <TableCell><PlayerLink playerId={p.player_id} playerName={p.full_name} /></TableCell>
                        <TableCell>{p.primary_position}</TableCell>
                        <TableCell>{p.age}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          )}

          {defensemen.length > 0 && (
            <Card>
              <CardHeader><CardTitle className="text-lg">Defensemen ({defensemen.length})</CardTitle></CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-16">#</TableHead>
                      <TableHead>Player</TableHead>
                      <TableHead>Position</TableHead>
                      <TableHead>Age</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {defensemen.map((p) => (
                      <TableRow key={p.player_id}>
                        <TableCell className="font-mono">{p.sweater_number}</TableCell>
                        <TableCell><PlayerLink playerId={p.player_id} playerName={p.full_name} /></TableCell>
                        <TableCell>{p.primary_position}</TableCell>
                        <TableCell>{p.age}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          )}

          {goalies.length > 0 && (
            <Card>
              <CardHeader><CardTitle className="text-lg">Goalies ({goalies.length})</CardTitle></CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-16">#</TableHead>
                      <TableHead>Player</TableHead>
                      <TableHead>Age</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {goalies.map((p) => (
                      <TableRow key={p.player_id}>
                        <TableCell className="font-mono">{p.sweater_number}</TableCell>
                        <TableCell><PlayerLink playerId={p.player_id} playerName={p.full_name} /></TableCell>
                        <TableCell>{p.age}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          )}
        </TabsContent>

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
                      <TableHead>Matchup</TableHead>
                      <TableHead>Result</TableHead>
                      <TableHead></TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {gamesData?.games.map((game) => {
                      const isHome = game.home_team_id === parsedTeamId
                      const teamScore = isHome ? game.home_score : game.away_score
                      const oppScore = isHome ? game.away_score : game.home_score
                      const result = teamScore !== null && oppScore !== null
                        ? teamScore > oppScore ? 'W' : teamScore < oppScore ? 'L' : 'T'
                        : '-'

                      return (
                        <TableRow key={game.game_id}>
                          <TableCell>{formatGameDate(game.game_date)}</TableCell>
                          <TableCell>{isHome ? 'vs' : '@'} {isHome ? game.away_team_name : game.home_team_name}</TableCell>
                          <TableCell>
                            <span className={result === 'W' ? 'text-green-600' : result === 'L' ? 'text-red-600' : ''}>
                              {result} {teamScore}-{oppScore}{game.is_overtime && ' (OT)'}{game.is_shootout && ' (SO)'}
                            </span>
                          </TableCell>
                          <TableCell><GameLink gameId={game.game_id}>Details</GameLink></TableCell>
                        </TableRow>
                      )
                    })}
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
