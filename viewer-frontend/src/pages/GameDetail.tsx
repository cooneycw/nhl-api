import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { ArrowLeft, ChevronLeft, ChevronRight } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { useGameDetail, useGameEvents, useGameStats, useGameShifts } from '@/hooks/useGames'
import { PlayerLink, TeamLink, formatGameDate, formatTOI } from '@/components/EntityLinks'

export function GameDetail() {
  const { gameId } = useParams<{ gameId: string }>()
  const parsedGameId = gameId ? parseInt(gameId, 10) : null

  const { data: game, isLoading, error } = useGameDetail(parsedGameId)
  const { data: eventsData, isLoading: eventsLoading } = useGameEvents(parsedGameId)
  const { data: statsData, isLoading: statsLoading } = useGameStats(parsedGameId)
  const { data: shiftsData, isLoading: shiftsLoading } = useGameShifts(parsedGameId)

  const [eventsPerPage, setEventsPerPage] = useState(50)
  const [eventsPage, setEventsPage] = useState(1)

  if (isLoading) {
    return <div className="space-y-6"><Skeleton className="h-8 w-64" /><Skeleton className="h-32 w-full" /><Skeleton className="h-64 w-full" /></div>
  }

  if (error || !game) {
    return (
      <div className="space-y-6">
        <Link to="/games" className="flex items-center gap-2 text-muted-foreground hover:text-foreground"><ArrowLeft className="h-4 w-4" />Back to Games</Link>
        <Card className="border-destructive"><CardContent className="pt-6"><p className="text-destructive">{error ? `Error: ${error.message}` : 'Game not found'}</p></CardContent></Card>
      </div>
    )
  }

  const goals = eventsData?.events.filter((e) => e.event_type.toLowerCase() === 'goal') || []
  const penalties = eventsData?.events.filter((e) => e.event_type.toLowerCase() === 'penalty') || []
  const allEvents = eventsData?.events || []
  const paginatedEvents = allEvents.slice((eventsPage - 1) * eventsPerPage, eventsPage * eventsPerPage)
  const totalEventPages = Math.ceil(allEvents.length / eventsPerPage)

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Link to="/games" className="text-muted-foreground hover:text-foreground"><ArrowLeft className="h-5 w-5" /></Link>
        <div className="flex-1">
          <p className="text-sm text-muted-foreground">{formatGameDate(game.game_date)}</p>
          <h1 className="text-2xl font-bold">
            <TeamLink teamId={game.away_team_id} teamName={game.away_team_name} />
            <span className="mx-2">@</span>
            <TeamLink teamId={game.home_team_id} teamName={game.home_team_name} />
          </h1>
        </div>
      </div>

      <Card>
        <CardContent className="pt-6">
          <div className="flex items-center justify-center gap-8">
            <div className="text-center">
              <TeamLink teamId={game.away_team_id} teamName={game.away_team_abbr} className="text-2xl font-bold" />
              <p className="text-4xl font-bold mt-2">{game.away_score ?? '-'}</p>
              <p className="text-sm text-muted-foreground">{game.away_team_name}</p>
            </div>
            <div className="text-center">
              <Badge variant={game.game_state === 'OFF' ? 'default' : 'secondary'}>
                {game.game_state === 'OFF' ? 'Final' : game.game_state}{game.is_overtime && ' (OT)'}{game.is_shootout && ' (SO)'}
              </Badge>
              <p className="text-sm text-muted-foreground mt-2">{game.venue_name}</p>
              {game.attendance && <p className="text-sm text-muted-foreground">Attendance: {game.attendance.toLocaleString()}</p>}
            </div>
            <div className="text-center">
              <TeamLink teamId={game.home_team_id} teamName={game.home_team_abbr} className="text-2xl font-bold" />
              <p className="text-4xl font-bold mt-2">{game.home_score ?? '-'}</p>
              <p className="text-sm text-muted-foreground">{game.home_team_name}</p>
            </div>
          </div>
        </CardContent>
      </Card>

      <Tabs defaultValue="overview">
        <TabsList className="flex flex-wrap">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="playbyplay">Play-by-Play</TabsTrigger>
          <TabsTrigger value="goals">Goals ({goals.length})</TabsTrigger>
          <TabsTrigger value="penalties">Penalties ({penalties.length})</TabsTrigger>
          <TabsTrigger value="boxscore">Box Score</TabsTrigger>
          <TabsTrigger value="shifts">Shifts</TabsTrigger>
          <TabsTrigger value="raw">Raw Data</TabsTrigger>
        </TabsList>

        <TabsContent value="overview">
          <div className="grid gap-4 md:grid-cols-2">
            <Card>
              <CardHeader><CardTitle className="text-lg">Game Info</CardTitle></CardHeader>
              <CardContent className="space-y-2">
                <div className="flex justify-between"><span className="text-muted-foreground">Season</span><span>{game.season_name}</span></div>
                <div className="flex justify-between"><span className="text-muted-foreground">Game Type</span><span>{game.game_type_name || game.game_type}</span></div>
                <div className="flex justify-between"><span className="text-muted-foreground">Venue</span><span>{game.venue_name}</span></div>
                <div className="flex justify-between"><span className="text-muted-foreground">Outcome</span><span>{game.game_outcome || 'N/A'}</span></div>
                {game.game_duration_minutes && <div className="flex justify-between"><span className="text-muted-foreground">Duration</span><span>{game.game_duration_minutes} min</span></div>}
              </CardContent>
            </Card>
            <Card>
              <CardHeader><CardTitle className="text-lg">Summary</CardTitle></CardHeader>
              <CardContent className="space-y-2">
                <div className="flex justify-between"><span className="text-muted-foreground">Total Events</span><span>{eventsData?.total_events || 0}</span></div>
                <div className="flex justify-between"><span className="text-muted-foreground">Goals</span><span>{goals.length}</span></div>
                <div className="flex justify-between"><span className="text-muted-foreground">Penalties</span><span>{penalties.length}</span></div>
                <div className="flex justify-between"><span className="text-muted-foreground">Final Period</span><span>{game.final_period || 3}</span></div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="playbyplay">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="text-lg">Play-by-Play Events</CardTitle>
                <div className="flex items-center gap-2">
                  <span className="text-sm text-muted-foreground">Per page:</span>
                  <select value={eventsPerPage} onChange={(e) => { setEventsPerPage(Number(e.target.value)); setEventsPage(1) }} className="text-sm border rounded px-2 py-1">
                    <option value={25}>25</option><option value={50}>50</option><option value={100}>100</option>
                  </select>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              {eventsLoading ? <Skeleton className="h-64 w-full" /> : paginatedEvents.length === 0 ? <p className="text-muted-foreground text-center py-8">No events found</p> : (
                <>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="w-16">Period</TableHead>
                        <TableHead className="w-20">Time</TableHead>
                        <TableHead className="w-24">Type</TableHead>
                        <TableHead>Description</TableHead>
                        <TableHead className="w-16">Score</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {paginatedEvents.map((event) => (
                        <TableRow key={event.event_idx}>
                          <TableCell>P{event.period}</TableCell>
                          <TableCell className="font-mono">{event.time_in_period}</TableCell>
                          <TableCell><Badge variant="outline" className="text-xs">{event.event_type}</Badge></TableCell>
                          <TableCell>
                            <div className="flex items-center gap-2">
                              {event.team_abbr && <span className="text-muted-foreground text-sm">[{event.team_abbr}]</span>}
                              {event.player1_id ? <PlayerLink playerId={event.player1_id} playerName={event.player1_name || 'Unknown'} /> : <span>{event.description || event.player1_name}</span>}
                            </div>
                          </TableCell>
                          <TableCell className="font-mono text-sm">{event.away_score}-{event.home_score}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                  {totalEventPages > 1 && (
                    <div className="flex items-center justify-between mt-4 pt-4 border-t">
                      <span className="text-sm text-muted-foreground">Showing {(eventsPage - 1) * eventsPerPage + 1}-{Math.min(eventsPage * eventsPerPage, allEvents.length)} of {allEvents.length}</span>
                      <div className="flex gap-2">
                        <Button variant="outline" size="sm" onClick={() => setEventsPage((p) => p - 1)} disabled={eventsPage === 1}><ChevronLeft className="h-4 w-4" /></Button>
                        <span className="flex items-center px-2">{eventsPage} / {totalEventPages}</span>
                        <Button variant="outline" size="sm" onClick={() => setEventsPage((p) => p + 1)} disabled={eventsPage >= totalEventPages}><ChevronRight className="h-4 w-4" /></Button>
                      </div>
                    </div>
                  )}
                </>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="goals">
          <Card>
            <CardHeader><CardTitle className="text-lg">Goals</CardTitle></CardHeader>
            <CardContent>
              {eventsLoading ? <Skeleton className="h-48 w-full" /> : goals.length === 0 ? <p className="text-muted-foreground text-center py-8">No goals scored</p> : (
                <div className="space-y-4">
                  {goals.map((goal) => (
                    <div key={goal.event_idx} className="flex items-start gap-4 p-4 rounded-lg border">
                      <div className="text-center min-w-[60px]">
                        <span className="text-sm text-muted-foreground">P{goal.period}</span>
                        <p className="font-mono">{goal.time_in_period}</p>
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <Badge variant="outline">{goal.team_abbr}</Badge>
                          {goal.player1_id ? <PlayerLink playerId={goal.player1_id} playerName={goal.player1_name || 'Unknown'} className="font-semibold" /> : <span className="font-semibold">{goal.player1_name || 'Unknown'}</span>}
                        </div>
                        {(goal.player2_id || goal.player3_id) && (
                          <p className="text-sm text-muted-foreground mt-1">
                            Assists: {goal.player2_id && <PlayerLink playerId={goal.player2_id} playerName={goal.player2_name || 'Unknown'} />}
                            {goal.player2_id && goal.player3_id && ', '}
                            {goal.player3_id && <PlayerLink playerId={goal.player3_id} playerName={goal.player3_name || 'Unknown'} />}
                          </p>
                        )}
                        {goal.shot_type && <p className="text-sm text-muted-foreground">{goal.shot_type}</p>}
                      </div>
                      <div className="text-right"><span className="font-mono">{goal.away_score}-{goal.home_score}</span></div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="penalties">
          <Card>
            <CardHeader><CardTitle className="text-lg">Penalties</CardTitle></CardHeader>
            <CardContent>
              {eventsLoading ? <Skeleton className="h-48 w-full" /> : penalties.length === 0 ? <p className="text-muted-foreground text-center py-8">No penalties</p> : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-16">Period</TableHead>
                      <TableHead className="w-20">Time</TableHead>
                      <TableHead className="w-16">Team</TableHead>
                      <TableHead>Player</TableHead>
                      <TableHead>Description</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {penalties.map((penalty) => (
                      <TableRow key={penalty.event_idx}>
                        <TableCell>P{penalty.period}</TableCell>
                        <TableCell className="font-mono">{penalty.time_in_period}</TableCell>
                        <TableCell><Badge variant="outline">{penalty.team_abbr}</Badge></TableCell>
                        <TableCell>{penalty.player1_id ? <PlayerLink playerId={penalty.player1_id} playerName={penalty.player1_name || 'Unknown'} /> : penalty.player1_name || 'Team'}</TableCell>
                        <TableCell>{penalty.description}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="boxscore">
          {statsLoading ? <Skeleton className="h-64 w-full" /> : !statsData ? <Card><CardContent className="pt-6"><p className="text-muted-foreground text-center">No stats available</p></CardContent></Card> : (
            <div className="space-y-6">
              <Card>
                <CardHeader><CardTitle className="text-lg">{game.away_team_name} Skaters</CardTitle></CardHeader>
                <CardContent><SkaterTable skaters={statsData.away_skaters} /></CardContent>
              </Card>
              <Card>
                <CardHeader><CardTitle className="text-lg">{game.home_team_name} Skaters</CardTitle></CardHeader>
                <CardContent><SkaterTable skaters={statsData.home_skaters} /></CardContent>
              </Card>
              <Card>
                <CardHeader><CardTitle className="text-lg">Goalies</CardTitle></CardHeader>
                <CardContent><GoalieTable awayGoalies={statsData.away_goalies} homeGoalies={statsData.home_goalies} awayTeam={game.away_team_abbr} homeTeam={game.home_team_abbr} /></CardContent>
              </Card>
            </div>
          )}
        </TabsContent>

        <TabsContent value="shifts">
          {shiftsLoading ? <Skeleton className="h-64 w-full" /> : !shiftsData ? <Card><CardContent className="pt-6"><p className="text-muted-foreground text-center">No shift data available</p></CardContent></Card> : (
            <div className="space-y-6">
              <Card>
                <CardHeader><CardTitle className="text-lg">{game.away_team_name} Time on Ice</CardTitle></CardHeader>
                <CardContent><ShiftsTable players={shiftsData.away_players} /></CardContent>
              </Card>
              <Card>
                <CardHeader><CardTitle className="text-lg">{game.home_team_name} Time on Ice</CardTitle></CardHeader>
                <CardContent><ShiftsTable players={shiftsData.home_players} /></CardContent>
              </Card>
            </div>
          )}
        </TabsContent>

        <TabsContent value="raw">
          <Card>
            <CardHeader><CardTitle className="text-lg">Raw Game Data</CardTitle></CardHeader>
            <CardContent><pre className="bg-muted p-4 rounded-lg overflow-auto max-h-[600px] text-xs">{JSON.stringify(game, null, 2)}</pre></CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}

function SkaterTable({ skaters }: { skaters: Array<{ player_id: number; player_name: string; position: string | null; goals: number; assists: number; points: number; plus_minus: number; pim: number; shots: number; hits: number; blocked_shots: number; toi_formatted: string; shifts: number }> }) {
  if (skaters.length === 0) return <p className="text-muted-foreground">No skater data</p>
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Player</TableHead><TableHead className="w-12">Pos</TableHead><TableHead className="text-right w-12">G</TableHead><TableHead className="text-right w-12">A</TableHead><TableHead className="text-right w-12">P</TableHead><TableHead className="text-right w-12">+/-</TableHead><TableHead className="text-right w-12">PIM</TableHead><TableHead className="text-right w-12">SOG</TableHead><TableHead className="text-right w-12">HIT</TableHead><TableHead className="text-right w-12">BLK</TableHead><TableHead className="text-right w-16">TOI</TableHead><TableHead className="text-right w-12">SH</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {skaters.map((s) => (
          <TableRow key={s.player_id}>
            <TableCell><PlayerLink playerId={s.player_id} playerName={s.player_name} /></TableCell>
            <TableCell>{s.position}</TableCell><TableCell className="text-right">{s.goals}</TableCell><TableCell className="text-right">{s.assists}</TableCell><TableCell className="text-right font-semibold">{s.points}</TableCell><TableCell className="text-right">{s.plus_minus > 0 ? '+' : ''}{s.plus_minus}</TableCell><TableCell className="text-right">{s.pim}</TableCell><TableCell className="text-right">{s.shots}</TableCell><TableCell className="text-right">{s.hits}</TableCell><TableCell className="text-right">{s.blocked_shots}</TableCell><TableCell className="text-right font-mono text-sm">{s.toi_formatted}</TableCell><TableCell className="text-right">{s.shifts}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}

function GoalieTable({ awayGoalies, homeGoalies, awayTeam, homeTeam }: { awayGoalies: Array<{ player_id: number; player_name: string; saves: number; shots_against: number; goals_against: number; save_pct: number | null; toi_formatted: string; decision: string | null }>; homeGoalies: Array<{ player_id: number; player_name: string; saves: number; shots_against: number; goals_against: number; save_pct: number | null; toi_formatted: string; decision: string | null }>; awayTeam: string; homeTeam: string }) {
  const allGoalies = [...awayGoalies.map((g) => ({ ...g, team: awayTeam })), ...homeGoalies.map((g) => ({ ...g, team: homeTeam }))]
  if (allGoalies.length === 0) return <p className="text-muted-foreground">No goalie data</p>
  return (
    <Table>
      <TableHeader><TableRow><TableHead>Goalie</TableHead><TableHead className="w-12">Team</TableHead><TableHead className="text-right w-12">SV</TableHead><TableHead className="text-right w-12">SA</TableHead><TableHead className="text-right w-12">GA</TableHead><TableHead className="text-right w-16">SV%</TableHead><TableHead className="text-right w-16">TOI</TableHead><TableHead className="w-12">Dec</TableHead></TableRow></TableHeader>
      <TableBody>
        {allGoalies.map((g) => (
          <TableRow key={`${g.team}-${g.player_id}`}>
            <TableCell><PlayerLink playerId={g.player_id} playerName={g.player_name} /></TableCell>
            <TableCell>{g.team}</TableCell><TableCell className="text-right">{g.saves}</TableCell><TableCell className="text-right">{g.shots_against}</TableCell><TableCell className="text-right">{g.goals_against}</TableCell><TableCell className="text-right font-mono">{g.save_pct?.toFixed(3) || '-'}</TableCell><TableCell className="text-right font-mono text-sm">{g.toi_formatted}</TableCell>
            <TableCell>{g.decision && <Badge variant={g.decision === 'W' ? 'default' : 'secondary'}>{g.decision}</Badge>}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}

function ShiftsTable({ players }: { players: Array<{ player_id: number; player_name: string; sweater_number: number | null; position: string | null; total_toi_display: string; total_shifts: number; avg_shift_seconds: number; period_1_toi: number; period_2_toi: number; period_3_toi: number; ot_toi: number }> }) {
  if (players.length === 0) return <p className="text-muted-foreground">No shift data</p>
  return (
    <Table>
      <TableHeader><TableRow><TableHead className="w-12">#</TableHead><TableHead>Player</TableHead><TableHead className="w-12">Pos</TableHead><TableHead className="text-right w-16">TOI</TableHead><TableHead className="text-right w-12">SH</TableHead><TableHead className="text-right w-16">AVG</TableHead><TableHead className="text-right w-16">P1</TableHead><TableHead className="text-right w-16">P2</TableHead><TableHead className="text-right w-16">P3</TableHead><TableHead className="text-right w-16">OT</TableHead></TableRow></TableHeader>
      <TableBody>
        {players.map((p) => (
          <TableRow key={p.player_id}>
            <TableCell className="font-mono">{p.sweater_number}</TableCell>
            <TableCell><PlayerLink playerId={p.player_id} playerName={p.player_name} /></TableCell>
            <TableCell>{p.position}</TableCell><TableCell className="text-right font-mono">{p.total_toi_display}</TableCell><TableCell className="text-right">{p.total_shifts}</TableCell><TableCell className="text-right font-mono text-sm">{Math.floor(p.avg_shift_seconds)}s</TableCell><TableCell className="text-right font-mono text-sm">{formatTOI(p.period_1_toi)}</TableCell><TableCell className="text-right font-mono text-sm">{formatTOI(p.period_2_toi)}</TableCell><TableCell className="text-right font-mono text-sm">{formatTOI(p.period_3_toi)}</TableCell><TableCell className="text-right font-mono text-sm">{p.ot_toi > 0 ? formatTOI(p.ot_toi) : '-'}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
