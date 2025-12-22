import { useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { GasTankGauge, GasTankGaugeInline } from '@/components/GasTankGauge'
import { useCoverage } from '@/hooks/useCoverage'
import { Fuel, RefreshCw, AlertCircle } from 'lucide-react'
import type { SeasonCoverage } from '@/lib/api'

export function Coverage() {
  const [includeAll, setIncludeAll] = useState(false)
  const { data, isLoading, error, refetch, isFetching } = useCoverage({ includeAll })

  // Calculate totals across all seasons for the table view
  const calculateTotals = (seasons: SeasonCoverage[]): Record<string, { actual: number; expected: number }> => {
    const totals: Record<string, { actual: number; expected: number }> = {}

    for (const season of seasons) {
      for (const cat of season.categories) {
        if (!totals[cat.name]) {
          totals[cat.name] = { actual: 0, expected: 0 }
        }
        totals[cat.name].actual += cat.actual
        totals[cat.name].expected += cat.expected
      }
    }

    return totals
  }

  const formatRefreshTime = (timestamp: string | null) => {
    if (!timestamp) return 'Never'
    const date = new Date(timestamp)
    return date.toLocaleString()
  }

  if (error) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
            <Fuel className="h-8 w-8" />
            Data Coverage
          </h1>
          <p className="text-muted-foreground">
            Visual overview of data completeness per season
          </p>
        </div>

        <Card className="border-destructive">
          <CardContent className="flex items-center gap-4 py-6">
            <AlertCircle className="h-8 w-8 text-destructive" />
            <div>
              <p className="font-medium text-destructive">Failed to load coverage data</p>
              <p className="text-sm text-muted-foreground">{String(error)}</p>
            </div>
            <Button variant="outline" onClick={() => refetch()} className="ml-auto">
              Retry
            </Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
            <Fuel className="h-8 w-8" />
            Data Coverage
          </h1>
          <p className="text-muted-foreground">
            Visual overview of data completeness per season
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant={includeAll ? 'default' : 'outline'}
            size="sm"
            onClick={() => setIncludeAll(!includeAll)}
          >
            {includeAll ? 'Show Recent' : 'Show All Seasons'}
          </Button>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => refetch()}
            disabled={isFetching}
          >
            <RefreshCw className={`h-4 w-4 ${isFetching ? 'animate-spin' : ''}`} />
          </Button>
        </div>
      </div>

      {/* Tabs for Gauges / Raw Counts */}
      <Tabs defaultValue="gauges" className="space-y-4">
        <TabsList>
          <TabsTrigger value="gauges">Gauges</TabsTrigger>
          <TabsTrigger value="table">Raw Counts</TabsTrigger>
        </TabsList>

        {/* Gauges View */}
        <TabsContent value="gauges" className="space-y-4">
          {isLoading ? (
            <div className="space-y-4">
              {[1, 2, 3].map((i) => (
                <Card key={i}>
                  <CardHeader>
                    <Skeleton className="h-6 w-32" />
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
                      {[1, 2, 3, 4, 5, 6].map((j) => (
                        <Skeleton key={j} className="h-20" />
                      ))}
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          ) : data?.seasons.length === 0 ? (
            <Card>
              <CardContent className="py-12 text-center text-muted-foreground">
                No coverage data available. Run some downloads first.
              </CardContent>
            </Card>
          ) : (
            data?.seasons.map((season) => (
              <SeasonCard key={season.season_id} season={season} />
            ))
          )}
        </TabsContent>

        {/* Table View */}
        <TabsContent value="table">
          <Card>
            <CardHeader>
              <CardTitle>Raw Coverage Counts</CardTitle>
              <CardDescription>
                Detailed breakdown of downloaded vs expected items
              </CardDescription>
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <div className="space-y-2">
                  {[1, 2, 3, 4].map((i) => (
                    <Skeleton key={i} className="h-12 w-full" />
                  ))}
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Season</TableHead>
                      <TableHead>Games</TableHead>
                      <TableHead>Boxscore</TableHead>
                      <TableHead>Play-by-Play</TableHead>
                      <TableHead>Shifts</TableHead>
                      <TableHead>Players</TableHead>
                      <TableHead>HTML</TableHead>
                      <TableHead>Game Logs</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {data?.seasons.map((season) => (
                      <TableRow key={season.season_id}>
                        <TableCell className="font-medium">
                          <div className="flex items-center gap-2">
                            {season.season_label}
                            {season.is_current && (
                              <Badge variant="secondary" className="text-xs">
                                Current
                              </Badge>
                            )}
                          </div>
                        </TableCell>
                        {season.categories.map((cat) => (
                          <TableCell key={cat.name}>
                            <div className="space-y-1">
                              <GasTankGaugeInline percentage={cat.percentage} />
                              <div className="text-xs text-muted-foreground">
                                {cat.actual.toLocaleString()} / {cat.expected.toLocaleString()}
                              </div>
                            </div>
                          </TableCell>
                        ))}
                        <TableCell>
                          <div className="text-sm">
                            {season.game_logs_total.toLocaleString()}
                            <div className="text-xs text-muted-foreground">
                              {season.players_with_game_logs.toLocaleString()} players
                            </div>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}

                    {/* Totals row */}
                    {data && data.seasons.length > 1 && (
                      <TableRow className="bg-muted/50 font-medium">
                        <TableCell>Total</TableCell>
                        {(() => {
                          const totals = calculateTotals(data.seasons)
                          const categoryOrder = ['games', 'boxscore', 'pbp', 'shifts', 'players', 'html']
                          return categoryOrder.map((name) => {
                            const t = totals[name] || { actual: 0, expected: 0 }
                            const pct = t.expected > 0 ? (t.actual / t.expected) * 100 : null
                            return (
                              <TableCell key={name}>
                                <div className="space-y-1">
                                  <GasTankGaugeInline percentage={pct} />
                                  <div className="text-xs text-muted-foreground">
                                    {t.actual.toLocaleString()} / {t.expected.toLocaleString()}
                                  </div>
                                </div>
                              </TableCell>
                            )
                          })
                        })()}
                        <TableCell>
                          {data.seasons.reduce((sum, s) => sum + s.game_logs_total, 0).toLocaleString()}
                        </TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Last refreshed footer */}
      {data && (
        <div className="text-center text-sm text-muted-foreground">
          Last refreshed: {formatRefreshTime(data.refreshed_at)}
        </div>
      )}
    </div>
  )
}

// Season card component with gauges
function SeasonCard({ season }: { season: SeasonCoverage }) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg flex items-center gap-2">
            {season.season_label}
            {season.is_current && (
              <Badge variant="default" className="text-xs">
                Current
              </Badge>
            )}
          </CardTitle>
          <div className="text-sm text-muted-foreground">
            {season.game_logs_total.toLocaleString()} game logs &bull;{' '}
            {season.players_with_game_logs.toLocaleString()} players
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
          {season.categories.map((cat) => (
            <GasTankGauge
              key={cat.name}
              label={cat.display_name}
              actual={cat.actual}
              expected={cat.expected}
              percentage={cat.percentage}
              linkPath={cat.link_path}
            />
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
