import { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useLeagueInjuries, useTodaysStarters } from '@/hooks/useDailyFaceoff'
import type { InjuryEntry, StartingGoalieEntry } from '@/lib/api'

function getStatusColor(status: string): 'destructive' | 'secondary' | 'outline' | 'default' {
  switch (status.toLowerCase()) {
    case 'ir':
      return 'destructive'
    case 'out':
      return 'destructive'
    case 'day-to-day':
      return 'secondary'
    case 'questionable':
      return 'secondary'
    case 'game-time-decision':
      return 'outline'
    default:
      return 'default'
  }
}

function getConfirmationColor(status: string): 'default' | 'secondary' | 'outline' {
  switch (status.toLowerCase()) {
    case 'confirmed':
      return 'default'
    case 'likely':
      return 'secondary'
    default:
      return 'outline'
  }
}

function InjuryCard({ injury }: { injury: InjuryEntry }) {
  return (
    <div className="flex items-center justify-between p-3 border rounded-lg">
      <div>
        <div className="font-medium">{injury.player_name}</div>
        <div className="text-sm text-muted-foreground">
          {injury.injury_type || 'Unspecified injury'}
          {injury.expected_return && (
            <span className="ml-2">- {injury.expected_return}</span>
          )}
        </div>
        {injury.injury_details && (
          <div className="text-xs text-muted-foreground mt-1">
            {injury.injury_details}
          </div>
        )}
      </div>
      <Badge variant={getStatusColor(injury.injury_status)}>
        {injury.injury_status.toUpperCase()}
      </Badge>
    </div>
  )
}

function GoalieStartCard({ goalie }: { goalie: StartingGoalieEntry }) {
  return (
    <div className="flex items-center justify-between p-4 border rounded-lg">
      <div className="flex items-center gap-4">
        <div className="text-center">
          <div className="font-mono text-lg font-bold">{goalie.team_abbrev}</div>
          <div className="text-xs text-muted-foreground">
            {goalie.is_home ? 'HOME' : 'AWAY'}
          </div>
        </div>
        <div>
          <div className="font-medium">{goalie.goalie_name}</div>
          <div className="text-sm text-muted-foreground">
            vs {goalie.opponent_abbrev}
          </div>
        </div>
      </div>
      <div className="flex items-center gap-4">
        <div className="text-right text-sm">
          {goalie.wins !== null && goalie.losses !== null && (
            <div>
              {goalie.wins}-{goalie.losses}
              {goalie.otl !== null && `-${goalie.otl}`}
            </div>
          )}
          {goalie.save_pct !== null && (
            <div className="text-muted-foreground">
              {(goalie.save_pct * 100).toFixed(1)}% SV | {goalie.gaa?.toFixed(2)} GAA
            </div>
          )}
        </div>
        <Badge variant={getConfirmationColor(goalie.confirmation_status)}>
          {goalie.confirmation_status.toUpperCase()}
        </Badge>
      </div>
    </div>
  )
}

export function Injuries() {
  const [statusFilter, setStatusFilter] = useState<string>('all')

  // Convert 'all' to undefined for API calls
  const statusParam = statusFilter === 'all' ? undefined : statusFilter

  const { data: injuriesData, isLoading: injuriesLoading, error: injuriesError } = useLeagueInjuries(
    undefined,
    statusParam
  )
  const { data: startersData, isLoading: startersLoading, error: startersError } = useTodaysStarters()

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <h1 className="text-3xl font-bold">Injuries & Starting Goalies</h1>
      </div>

      <Tabs defaultValue="injuries" className="space-y-4">
        <TabsList>
          <TabsTrigger value="injuries">Injuries</TabsTrigger>
          <TabsTrigger value="goalies">Starting Goalies</TabsTrigger>
        </TabsList>

        <TabsContent value="injuries" className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="text-sm text-muted-foreground">
              {injuriesData && (
                <>
                  {injuriesData.total_injuries} injured players as of{' '}
                  {new Date(injuriesData.snapshot_date).toLocaleDateString()}
                </>
              )}
            </div>
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="All Statuses" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Statuses</SelectItem>
                <SelectItem value="ir">IR</SelectItem>
                <SelectItem value="out">Out</SelectItem>
                <SelectItem value="day-to-day">Day-to-Day</SelectItem>
                <SelectItem value="questionable">Questionable</SelectItem>
                <SelectItem value="game-time-decision">Game-Time Decision</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {injuriesLoading && (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {Array.from({ length: 6 }).map((_, i) => (
                <Card key={i}>
                  <CardHeader>
                    <Skeleton className="h-6 w-24" />
                  </CardHeader>
                  <CardContent>
                    <Skeleton className="h-16" />
                  </CardContent>
                </Card>
              ))}
            </div>
          )}

          {injuriesError && (
            <Card className="border-destructive">
              <CardContent className="pt-6">
                <p className="text-destructive">
                  No injury data available. Run a DailyFaceoff Injuries download first.
                </p>
              </CardContent>
            </Card>
          )}

          {injuriesData && (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {Object.entries(injuriesData.teams)
                .sort(([a], [b]) => a.localeCompare(b))
                .map(([teamAbbrev, injuries]) => (
                  <Card key={teamAbbrev}>
                    <CardHeader className="pb-2">
                      <CardTitle className="flex items-center justify-between">
                        <span>{teamAbbrev}</span>
                        <Badge variant="outline">{injuries.length}</Badge>
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-2">
                      {injuries.map((injury, i) => (
                        <InjuryCard key={i} injury={injury} />
                      ))}
                    </CardContent>
                  </Card>
                ))}
            </div>
          )}

          {injuriesData && Object.keys(injuriesData.teams).length === 0 && (
            <Card>
              <CardContent className="pt-6">
                <p className="text-muted-foreground text-center">
                  No injuries found matching the current filter.
                </p>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="goalies" className="space-y-4">
          <div className="text-sm text-muted-foreground">
            {startersData && (
              <>
                {startersData.game_count} games scheduled for{' '}
                {new Date(startersData.game_date).toLocaleDateString()}
              </>
            )}
          </div>

          {startersLoading && (
            <div className="space-y-4">
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-24" />
              ))}
            </div>
          )}

          {startersError && (
            <Card className="border-destructive">
              <CardContent className="pt-6">
                <p className="text-destructive">
                  No starting goalie data available. Run a DailyFaceoff Starting Goalies download first.
                </p>
              </CardContent>
            </Card>
          )}

          {startersData && startersData.starters.length > 0 && (
            <div className="space-y-3">
              {/* Group by game (pairs of home/away) */}
              {startersData.starters
                .filter(g => g.is_home)
                .map((homeGoalie) => {
                  const awayGoalie = startersData.starters.find(
                    g => !g.is_home && g.opponent_abbrev === homeGoalie.team_abbrev
                  )
                  return (
                    <Card key={`${homeGoalie.team_abbrev}-${homeGoalie.opponent_abbrev}`}>
                      <CardContent className="pt-4 space-y-3">
                        <div className="text-center text-sm text-muted-foreground mb-2">
                          {homeGoalie.opponent_abbrev} @ {homeGoalie.team_abbrev}
                        </div>
                        {awayGoalie && <GoalieStartCard goalie={awayGoalie} />}
                        <GoalieStartCard goalie={homeGoalie} />
                      </CardContent>
                    </Card>
                  )
                })}
            </div>
          )}

          {startersData && startersData.starters.length === 0 && (
            <Card>
              <CardContent className="pt-6">
                <p className="text-muted-foreground text-center">
                  No games scheduled for today, or starting goalies not yet announced.
                </p>
              </CardContent>
            </Card>
          )}
        </TabsContent>
      </Tabs>
    </div>
  )
}
