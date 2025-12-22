import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  useReconciliationDashboard,
  useGameReconciliations,
  useTriggerReconciliation,
  useExportReconciliation,
  type DiscrepancyType,
} from '@/hooks/useReconciliation'
import {
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Play,
  Download,
  Loader2,
  Target,
  TrendingUp,
  Clock,
  FileWarning,
} from 'lucide-react'

// Available seasons - could be fetched from API in future
const SEASONS = [
  { id: 20242025, label: '2024-25' },
  { id: 20232024, label: '2023-24' },
  { id: 20222023, label: '2022-23' },
]

export function Validation() {
  const [seasonId, setSeasonId] = useState(20242025)
  const [discrepancyFilter, setDiscrepancyFilter] = useState<DiscrepancyType | 'all'>('all')
  const [page, setPage] = useState(1)

  const { data: dashboard, isLoading: dashboardLoading, error: dashboardError } = useReconciliationDashboard(seasonId)
  const { data: games, isLoading: gamesLoading } = useGameReconciliations(seasonId, {
    discrepancyType: discrepancyFilter === 'all' ? undefined : discrepancyFilter,
    page,
    pageSize: 10,
  })
  const triggerReconciliation = useTriggerReconciliation()
  const exportReconciliation = useExportReconciliation()

  const handleRunReconciliation = async () => {
    try {
      await triggerReconciliation.mutateAsync({ season_id: seasonId })
    } catch (error) {
      console.error('Failed to trigger reconciliation:', error)
    }
  }

  const handleExport = async (format: 'csv' | 'json') => {
    try {
      await exportReconciliation.mutateAsync({
        runId: 1, // placeholder - could be from dashboard.last_run
        seasonId,
        format,
      })
    } catch (error) {
      console.error('Failed to export:', error)
    }
  }

  const getStatusBadge = (passRate: number) => {
    if (passRate >= 0.95) {
      return <Badge className="bg-green-500/10 text-green-600 hover:bg-green-500/20">Excellent</Badge>
    } else if (passRate >= 0.80) {
      return <Badge className="bg-yellow-500/10 text-yellow-600 hover:bg-yellow-500/20">Good</Badge>
    } else {
      return <Badge className="bg-red-500/10 text-red-600 hover:bg-red-500/20">Needs Review</Badge>
    }
  }

  const formatPercent = (value: number) => `${(value * 100).toFixed(1)}%`

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Data Validation</h1>
          <p className="text-muted-foreground">
            Cross-source reconciliation and data quality metrics
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Select value={String(seasonId)} onValueChange={(v) => setSeasonId(Number(v))}>
            <SelectTrigger className="w-32">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {SEASONS.map((s) => (
                <SelectItem key={s.id} value={String(s.id)}>
                  {s.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button
            onClick={handleRunReconciliation}
            disabled={triggerReconciliation.isPending}
          >
            {triggerReconciliation.isPending ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Running...
              </>
            ) : (
              <>
                <Play className="mr-2 h-4 w-4" />
                Run Reconciliation
              </>
            )}
          </Button>
        </div>
      </div>

      {dashboardError && (
        <Card className="border-destructive">
          <CardContent className="flex items-center gap-2 pt-6">
            <AlertTriangle className="h-5 w-5 text-destructive" />
            <span className="text-destructive">
              Failed to load reconciliation data. Make sure the database has game data.
            </span>
          </CardContent>
        </Card>
      )}

      {/* Quality Score Card */}
      <Card className="bg-gradient-to-br from-primary/5 to-primary/10">
        <CardContent className="pt-6">
          {dashboardLoading ? (
            <div className="flex items-center justify-center h-24">
              <Skeleton className="h-16 w-32" />
            </div>
          ) : dashboard ? (
            <div className="flex items-center justify-between">
              <div>
                <div className="text-sm font-medium text-muted-foreground mb-1">
                  Data Quality Score
                </div>
                <div className="flex items-baseline gap-3">
                  <span className="text-5xl font-bold">
                    {dashboard.quality_score.toFixed(1)}%
                  </span>
                  {getStatusBadge(dashboard.quality_score / 100)}
                </div>
                <div className="text-sm text-muted-foreground mt-2">
                  {dashboard.summary.total_games} games analyzed
                  {dashboard.last_run && (
                    <> • Last run: {new Date(dashboard.last_run).toLocaleString()}</>
                  )}
                </div>
              </div>
              <Target className="h-16 w-16 text-primary/20" />
            </div>
          ) : null}
        </CardContent>
      </Card>

      {/* Category Cards Grid */}
      <div className="grid gap-4 md:grid-cols-3">
        {/* Goal Reconciliation */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-muted-foreground" />
              Goal Reconciliation
            </CardTitle>
          </CardHeader>
          <CardContent>
            {dashboardLoading ? (
              <Skeleton className="h-8 w-full" />
            ) : dashboard ? (
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-2xl font-bold">
                    {formatPercent(dashboard.summary.goal_reconciliation_rate)}
                  </span>
                  {dashboard.summary.goal_reconciliation_rate >= 0.95 ? (
                    <CheckCircle2 className="h-5 w-5 text-green-500" />
                  ) : (
                    <XCircle className="h-5 w-5 text-yellow-500" />
                  )}
                </div>
                <Progress value={dashboard.summary.goal_reconciliation_rate * 100} />
              </div>
            ) : null}
          </CardContent>
        </Card>

        {/* Penalty Reconciliation */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <Clock className="h-4 w-4 text-muted-foreground" />
              Penalty Reconciliation
            </CardTitle>
          </CardHeader>
          <CardContent>
            {dashboardLoading ? (
              <Skeleton className="h-8 w-full" />
            ) : dashboard ? (
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-2xl font-bold">
                    {formatPercent(dashboard.summary.penalty_reconciliation_rate)}
                  </span>
                  {dashboard.summary.penalty_reconciliation_rate >= 0.95 ? (
                    <CheckCircle2 className="h-5 w-5 text-green-500" />
                  ) : (
                    <XCircle className="h-5 w-5 text-yellow-500" />
                  )}
                </div>
                <Progress value={dashboard.summary.penalty_reconciliation_rate * 100} />
              </div>
            ) : null}
          </CardContent>
        </Card>

        {/* TOI Reconciliation */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <FileWarning className="h-4 w-4 text-muted-foreground" />
              TOI Reconciliation
            </CardTitle>
          </CardHeader>
          <CardContent>
            {dashboardLoading ? (
              <Skeleton className="h-8 w-full" />
            ) : dashboard ? (
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-2xl font-bold">
                    {formatPercent(dashboard.summary.toi_reconciliation_rate)}
                  </span>
                  {dashboard.summary.toi_reconciliation_rate >= 0.95 ? (
                    <CheckCircle2 className="h-5 w-5 text-green-500" />
                  ) : (
                    <XCircle className="h-5 w-5 text-yellow-500" />
                  )}
                </div>
                <Progress value={dashboard.summary.toi_reconciliation_rate * 100} />
              </div>
            ) : null}
          </CardContent>
        </Card>
      </div>

      {/* Problem Games Table */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Games with Discrepancies</CardTitle>
              <CardDescription>
                Games where data sources don't match
              </CardDescription>
            </div>
            <div className="flex items-center gap-2">
              <Select
                value={discrepancyFilter}
                onValueChange={(v) => {
                  setDiscrepancyFilter(v as DiscrepancyType | 'all')
                  setPage(1)
                }}
              >
                <SelectTrigger className="w-36">
                  <SelectValue placeholder="Filter by type" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Types</SelectItem>
                  <SelectItem value="goal">Goals</SelectItem>
                  <SelectItem value="penalty">Penalties</SelectItem>
                  <SelectItem value="toi">TOI</SelectItem>
                  <SelectItem value="shot">Shots</SelectItem>
                </SelectContent>
              </Select>
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleExport('csv')}
                disabled={exportReconciliation.isPending}
              >
                <Download className="mr-2 h-4 w-4" />
                Export CSV
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {gamesLoading ? (
            <div className="space-y-2">
              <Skeleton className="h-12 w-full" />
              <Skeleton className="h-12 w-full" />
              <Skeleton className="h-12 w-full" />
            </div>
          ) : !games?.games.length ? (
            <div className="flex h-32 items-center justify-center text-muted-foreground">
              <div className="text-center">
                <CheckCircle2 className="h-8 w-8 mx-auto mb-2 text-green-500" />
                <p>No discrepancies found</p>
              </div>
            </div>
          ) : (
            <>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Game</TableHead>
                    <TableHead>Date</TableHead>
                    <TableHead className="text-center">Passed</TableHead>
                    <TableHead className="text-center">Failed</TableHead>
                    <TableHead>Discrepancies</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {games.games.map((game) => (
                    <TableRow key={game.game_id}>
                      <TableCell className="font-medium">
                        {game.away_team} @ {game.home_team}
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {new Date(game.game_date).toLocaleDateString()}
                      </TableCell>
                      <TableCell className="text-center">
                        <Badge variant="outline" className="text-green-600">
                          {game.checks_passed}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-center">
                        <Badge variant="outline" className="text-red-600">
                          {game.checks_failed}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <div className="flex flex-wrap gap-1">
                          {game.discrepancies.slice(0, 3).map((d, i) => (
                            <Badge key={i} variant="secondary" className="text-xs">
                              {d.rule_name}
                            </Badge>
                          ))}
                          {game.discrepancies.length > 3 && (
                            <Badge variant="secondary" className="text-xs">
                              +{game.discrepancies.length - 3} more
                            </Badge>
                          )}
                        </div>
                      </TableCell>
                      <TableCell className="text-right">
                        <Button variant="ghost" size="sm" asChild>
                          <Link to={`/validation/game/${game.game_id}`}>
                            View Details
                          </Link>
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>

              {/* Pagination */}
              {games.pages > 1 && (
                <div className="flex items-center justify-between mt-4">
                  <div className="text-sm text-muted-foreground">
                    Page {games.page} of {games.pages} ({games.total} games)
                  </div>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setPage((p) => Math.max(1, p - 1))}
                      disabled={page === 1}
                    >
                      Previous
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setPage((p) => Math.min(games.pages, p + 1))}
                      disabled={page === games.pages}
                    >
                      Next
                    </Button>
                  </div>
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
