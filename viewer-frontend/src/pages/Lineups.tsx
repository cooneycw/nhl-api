import { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useTeamLines, useTeamPowerPlay, useTeamPenaltyKill, useLineHistory } from '@/hooks/useDailyFaceoff'
import { useTeams } from '@/hooks/useTeams'
import type { PlayerLineupEntry, PowerPlayPlayerEntry, PenaltyKillPlayerEntry } from '@/lib/api'

// NHL team abbreviations for selector
const NHL_TEAMS = [
  { abbrev: 'ANA', name: 'Anaheim Ducks' },
  { abbrev: 'ARI', name: 'Arizona Coyotes' },
  { abbrev: 'BOS', name: 'Boston Bruins' },
  { abbrev: 'BUF', name: 'Buffalo Sabres' },
  { abbrev: 'CGY', name: 'Calgary Flames' },
  { abbrev: 'CAR', name: 'Carolina Hurricanes' },
  { abbrev: 'CHI', name: 'Chicago Blackhawks' },
  { abbrev: 'COL', name: 'Colorado Avalanche' },
  { abbrev: 'CBJ', name: 'Columbus Blue Jackets' },
  { abbrev: 'DAL', name: 'Dallas Stars' },
  { abbrev: 'DET', name: 'Detroit Red Wings' },
  { abbrev: 'EDM', name: 'Edmonton Oilers' },
  { abbrev: 'FLA', name: 'Florida Panthers' },
  { abbrev: 'LAK', name: 'Los Angeles Kings' },
  { abbrev: 'MIN', name: 'Minnesota Wild' },
  { abbrev: 'MTL', name: 'Montreal Canadiens' },
  { abbrev: 'NSH', name: 'Nashville Predators' },
  { abbrev: 'NJD', name: 'New Jersey Devils' },
  { abbrev: 'NYI', name: 'New York Islanders' },
  { abbrev: 'NYR', name: 'New York Rangers' },
  { abbrev: 'OTT', name: 'Ottawa Senators' },
  { abbrev: 'PHI', name: 'Philadelphia Flyers' },
  { abbrev: 'PIT', name: 'Pittsburgh Penguins' },
  { abbrev: 'SJS', name: 'San Jose Sharks' },
  { abbrev: 'SEA', name: 'Seattle Kraken' },
  { abbrev: 'STL', name: 'St. Louis Blues' },
  { abbrev: 'TBL', name: 'Tampa Bay Lightning' },
  { abbrev: 'TOR', name: 'Toronto Maple Leafs' },
  { abbrev: 'UTA', name: 'Utah Hockey Club' },
  { abbrev: 'VAN', name: 'Vancouver Canucks' },
  { abbrev: 'VGK', name: 'Vegas Golden Knights' },
  { abbrev: 'WSH', name: 'Washington Capitals' },
  { abbrev: 'WPG', name: 'Winnipeg Jets' },
]

function PlayerCard({ player, label }: { player: PlayerLineupEntry | null; label: string }) {
  if (!player) {
    return (
      <div className="p-2 text-center text-muted-foreground text-sm">
        <div className="text-xs uppercase tracking-wide mb-1">{label}</div>
        <div>-</div>
      </div>
    )
  }

  return (
    <div className="p-2 text-center">
      <div className="text-xs uppercase tracking-wide text-muted-foreground mb-1">{label}</div>
      <div className="font-medium">
        {player.jersey_number && <span className="text-muted-foreground mr-1">#{player.jersey_number}</span>}
        {player.player_name}
      </div>
      {player.injury_status && (
        <Badge variant="destructive" className="mt-1 text-xs">
          {player.injury_status}
        </Badge>
      )}
    </div>
  )
}

function PPPlayerCard({ player }: { player: PowerPlayPlayerEntry }) {
  return (
    <div className="p-2 border rounded text-center">
      <div className="font-medium text-sm">
        {player.jersey_number && <span className="text-muted-foreground mr-1">#{player.jersey_number}</span>}
        {player.player_name}
      </div>
      <div className="text-xs text-muted-foreground mt-1">
        {player.season_points !== null && <span>{player.season_points} pts</span>}
        {player.df_rating !== null && <span className="ml-2">({player.df_rating.toFixed(0)})</span>}
      </div>
    </div>
  )
}

function PKPlayerCard({ player }: { player: PenaltyKillPlayerEntry }) {
  return (
    <div className="p-2 border rounded text-center">
      <div className="font-medium text-sm">
        {player.jersey_number && <span className="text-muted-foreground mr-1">#{player.jersey_number}</span>}
        {player.player_name}
      </div>
      <div className="text-xs text-muted-foreground mt-1 capitalize">
        {player.position_type}
      </div>
    </div>
  )
}

export function Lineups() {
  const [selectedTeam, setSelectedTeam] = useState<string>('')
  const [selectedDate, setSelectedDate] = useState<string>('')

  const { data: linesData, isLoading: linesLoading, error: linesError } = useTeamLines(
    selectedTeam,
    selectedDate || undefined
  )
  const { data: ppData, isLoading: ppLoading } = useTeamPowerPlay(
    selectedTeam,
    selectedDate || undefined
  )
  const { data: pkData, isLoading: pkLoading } = useTeamPenaltyKill(
    selectedTeam,
    selectedDate || undefined
  )
  const { data: historyDates } = useLineHistory(selectedTeam)

  const isLoading = linesLoading || ppLoading || pkLoading

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <h1 className="text-3xl font-bold">Team Lineups</h1>
        <div className="flex gap-2">
          <Select value={selectedTeam} onValueChange={setSelectedTeam}>
            <SelectTrigger className="w-[220px]">
              <SelectValue placeholder="Select a team" />
            </SelectTrigger>
            <SelectContent>
              {NHL_TEAMS.map((team) => (
                <SelectItem key={team.abbrev} value={team.abbrev}>
                  {team.abbrev} - {team.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          {historyDates && historyDates.length > 0 && (
            <Select value={selectedDate} onValueChange={setSelectedDate}>
              <SelectTrigger className="w-[160px]">
                <SelectValue placeholder="Latest" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="">Latest</SelectItem>
                {historyDates.map((date) => (
                  <SelectItem key={date} value={date}>
                    {new Date(date).toLocaleDateString()}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
        </div>
      </div>

      {!selectedTeam && (
        <Card>
          <CardContent className="pt-6">
            <p className="text-muted-foreground text-center">
              Select a team to view their line combinations, power play, and penalty kill units.
            </p>
          </CardContent>
        </Card>
      )}

      {selectedTeam && isLoading && (
        <div className="grid gap-4 md:grid-cols-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <Card key={i}>
              <CardHeader>
                <Skeleton className="h-6 w-32" />
              </CardHeader>
              <CardContent>
                <Skeleton className="h-20" />
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {linesError && (
        <Card className="border-destructive">
          <CardContent className="pt-6">
            <p className="text-destructive">
              No lineup data available for {selectedTeam}. Run a DailyFaceoff download first.
            </p>
          </CardContent>
        </Card>
      )}

      {linesData && (
        <Tabs defaultValue="lines" className="space-y-4">
          <TabsList>
            <TabsTrigger value="lines">Even Strength</TabsTrigger>
            <TabsTrigger value="powerplay">Power Play</TabsTrigger>
            <TabsTrigger value="penaltykill">Penalty Kill</TabsTrigger>
          </TabsList>

          <TabsContent value="lines" className="space-y-4">
            <div className="text-sm text-muted-foreground">
              Data from {new Date(linesData.snapshot_date).toLocaleDateString()}
            </div>

            {/* Forward Lines */}
            <Card>
              <CardHeader>
                <CardTitle>Forward Lines</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {linesData.forward_lines.map((line) => (
                    <div key={line.line_number} className="grid grid-cols-4 gap-2 items-center">
                      <div className="font-semibold text-muted-foreground">
                        Line {line.line_number}
                      </div>
                      <PlayerCard player={line.lw} label="LW" />
                      <PlayerCard player={line.c} label="C" />
                      <PlayerCard player={line.rw} label="RW" />
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            {/* Defense Pairs */}
            <Card>
              <CardHeader>
                <CardTitle>Defense Pairs</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {linesData.defense_pairs.map((pair) => (
                    <div key={pair.pair_number} className="grid grid-cols-3 gap-2 items-center">
                      <div className="font-semibold text-muted-foreground">
                        Pair {pair.pair_number}
                      </div>
                      <PlayerCard player={pair.ld} label="LD" />
                      <PlayerCard player={pair.rd} label="RD" />
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            {/* Goalies */}
            <Card>
              <CardHeader>
                <CardTitle>Goaltenders</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 gap-4">
                  <PlayerCard player={linesData.goalies.starter} label="Starter" />
                  <PlayerCard player={linesData.goalies.backup} label="Backup" />
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="powerplay" className="space-y-4">
            {ppData ? (
              <div className="text-sm text-muted-foreground">
                Data from {new Date(ppData.snapshot_date).toLocaleDateString()}
              </div>
            ) : null}

            <div className="grid gap-4 md:grid-cols-2">
              {/* PP1 */}
              <Card>
                <CardHeader>
                  <CardTitle>Power Play 1</CardTitle>
                </CardHeader>
                <CardContent>
                  {ppData?.pp1 ? (
                    <div className="grid grid-cols-3 gap-2">
                      {ppData.pp1.players.map((player, i) => (
                        <PPPlayerCard key={i} player={player} />
                      ))}
                    </div>
                  ) : (
                    <p className="text-muted-foreground text-center">No data</p>
                  )}
                </CardContent>
              </Card>

              {/* PP2 */}
              <Card>
                <CardHeader>
                  <CardTitle>Power Play 2</CardTitle>
                </CardHeader>
                <CardContent>
                  {ppData?.pp2 ? (
                    <div className="grid grid-cols-3 gap-2">
                      {ppData.pp2.players.map((player, i) => (
                        <PPPlayerCard key={i} player={player} />
                      ))}
                    </div>
                  ) : (
                    <p className="text-muted-foreground text-center">No data</p>
                  )}
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          <TabsContent value="penaltykill" className="space-y-4">
            {pkData ? (
              <div className="text-sm text-muted-foreground">
                Data from {new Date(pkData.snapshot_date).toLocaleDateString()}
              </div>
            ) : null}

            <div className="grid gap-4 md:grid-cols-2">
              {/* PK1 */}
              <Card>
                <CardHeader>
                  <CardTitle>Penalty Kill 1</CardTitle>
                </CardHeader>
                <CardContent>
                  {pkData?.pk1 ? (
                    <div className="space-y-2">
                      <div className="text-sm text-muted-foreground">Forwards</div>
                      <div className="grid grid-cols-2 gap-2">
                        {pkData.pk1.forwards.map((player, i) => (
                          <PKPlayerCard key={i} player={player} />
                        ))}
                      </div>
                      <div className="text-sm text-muted-foreground mt-4">Defensemen</div>
                      <div className="grid grid-cols-2 gap-2">
                        {pkData.pk1.defensemen.map((player, i) => (
                          <PKPlayerCard key={i} player={player} />
                        ))}
                      </div>
                    </div>
                  ) : (
                    <p className="text-muted-foreground text-center">No data</p>
                  )}
                </CardContent>
              </Card>

              {/* PK2 */}
              <Card>
                <CardHeader>
                  <CardTitle>Penalty Kill 2</CardTitle>
                </CardHeader>
                <CardContent>
                  {pkData?.pk2 ? (
                    <div className="space-y-2">
                      <div className="text-sm text-muted-foreground">Forwards</div>
                      <div className="grid grid-cols-2 gap-2">
                        {pkData.pk2.forwards.map((player, i) => (
                          <PKPlayerCard key={i} player={player} />
                        ))}
                      </div>
                      <div className="text-sm text-muted-foreground mt-4">Defensemen</div>
                      <div className="grid grid-cols-2 gap-2">
                        {pkData.pk2.defensemen.map((player, i) => (
                          <PKPlayerCard key={i} player={player} />
                        ))}
                      </div>
                    </div>
                  ) : (
                    <p className="text-muted-foreground text-center">No data</p>
                  )}
                </CardContent>
              </Card>
            </div>
          </TabsContent>
        </Tabs>
      )}
    </div>
  )
}
