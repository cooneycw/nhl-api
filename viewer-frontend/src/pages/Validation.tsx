import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
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
  useValidationRuns,
  useDiscrepancies,
  useSeasonSummary,
  useTriggerValidation,
  type ValidationRunSummary,
} from '@/hooks/useValidation'
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
  ClipboardCheck,
  ListChecks,
  LineChart as LineChartIcon,
} from 'lucide-react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts'

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
  const [runsPage, setRunsPage] = useState(1)

  // Reconciliation hooks
  const { data: dashboard, isLoading: dashboardLoading, error: dashboardError } = useReconciliationDashboard(seasonId)
  const { data: games, isLoading: gamesLoading } = useGameReconciliations(seasonId, {
    discrepancyType: discrepancyFilter === 'all' ? undefined : discrepancyFilter,
    page,
    pageSize: 10,
  })
  const triggerReconciliation = useTriggerReconciliation()
  const exportReconciliation = useExportReconciliation()

  // Validation runs hooks
  const { data: validationRuns, isLoading: runsLoading } = useValidationRuns({
    seasonId,
    page: runsPage,
    pageSize: 10,
  })
  const { data: discrepancies, isLoading: discrepanciesLoading } = useDiscrepancies({
    seasonId,
    status: 'open',
    page: 1,
    pageSize: 5,
  })

  // Season summary for source accuracy
  const { data: seasonSummary, isLoading: summaryLoading } = useSeasonSummary(seasonId)
  const triggerValidation = useTriggerValidation()

  const handleRunReconciliation = async () => {
    try {
      await triggerReconciliation.mutateAsync({ season_id: seasonId })
    } catch (error) {
      console.error('Failed to trigger reconciliation:', error)
    }
  }

  const handleRunValidation = async () => {
    try {
      await triggerValidation.mutateAsync({ season_id: seasonId })
    } catch (error) {
      console.error('Failed to trigger validation:', error)
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
      return <Badge variant="success">Excellent</Badge>
    } else if (passRate >= 0.80) {
      return <Badge variant="warning">Good</Badge>
    } else {
      return <Badge variant="error">Needs Review</Badge>
    }
  }

  const getRunStatusBadge = (status: ValidationRunSummary['status']) => {
    switch (status) {
      case 'completed':
        return <Badge variant="success">Completed</Badge>
      case 'running':
        return <Badge variant="warning">Running</Badge>
      case 'failed':
        return <Badge variant="error">Failed</Badge>
      default:
        return <Badge variant="secondary">{status}</Badge>
    }
  }

  const formatPercent = (value: number) => `${(value * 100).toFixed(1)}%`

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr)
    return date.toLocaleString()
  }

  const formatDuration = (startedAt: string, completedAt: string | null) => {
    if (!completedAt) return 'In progress...'
    const start = new Date(startedAt).getTime()
    const end = new Date(completedAt).getTime()
    const durationMs = end - start
    if (durationMs < 1000) return `${durationMs}ms`
    if (durationMs < 60000) return `${(durationMs / 1000).toFixed(1)}s`
    return `${(durationMs / 60000).toFixed(1)}m`
  }

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

      {/* Tabs */}
      <Tabs defaultValue="reconciliation" className="space-y-4">
        <TabsList>
          <TabsTrigger value="reconciliation" className="gap-2">
            <ClipboardCheck className="h-4 w-4" />
            Reconciliation
          </TabsTrigger>
          <TabsTrigger value="validation-runs" className="gap-2">
            <ListChecks className="h-4 w-4" />
            Validation Runs
          </TabsTrigger>
        </TabsList>

        {/* Reconciliation Tab */}
        <TabsContent value="reconciliation" className="space-y-6">
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
        </TabsContent>

        {/* Validation Runs Tab */}
        <TabsContent value="validation-runs" className="space-y-6">
          {/* Summary Cards */}
          <div className="grid gap-4 md:grid-cols-4">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  Total Runs
                </CardTitle>
              </CardHeader>
              <CardContent>
                {runsLoading ? (
                  <Skeleton className="h-8 w-20" />
                ) : (
                  <div className="text-2xl font-bold">
                    {validationRuns?.total ?? 0}
                  </div>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  Open Discrepancies
                </CardTitle>
              </CardHeader>
              <CardContent>
                {discrepanciesLoading ? (
                  <Skeleton className="h-8 w-20" />
                ) : (
                  <div className="text-2xl font-bold text-yellow-600">
                    {discrepancies?.total ?? 0}
                  </div>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  Last Run Status
                </CardTitle>
              </CardHeader>
              <CardContent>
                {runsLoading ? (
                  <Skeleton className="h-8 w-24" />
                ) : validationRuns?.runs[0] ? (
                  getRunStatusBadge(validationRuns.runs[0].status)
                ) : (
                  <span className="text-muted-foreground">No runs yet</span>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  Last Run Pass Rate
                </CardTitle>
              </CardHeader>
              <CardContent>
                {runsLoading ? (
                  <Skeleton className="h-8 w-20" />
                ) : validationRuns?.runs[0] ? (
                  <div className="text-2xl font-bold">
                    {validationRuns.runs[0].total_passed + validationRuns.runs[0].total_failed > 0
                      ? `${((validationRuns.runs[0].total_passed / (validationRuns.runs[0].total_passed + validationRuns.runs[0].total_failed)) * 100).toFixed(1)}%`
                      : 'N/A'}
                  </div>
                ) : (
                  <span className="text-muted-foreground">N/A</span>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Validation Runs Table */}
          <Card>
            <CardHeader>
              <CardTitle>Validation Run History</CardTitle>
              <CardDescription>
                Recent validation runs with pass/fail counts
              </CardDescription>
            </CardHeader>
            <CardContent>
              {runsLoading ? (
                <div className="space-y-2">
                  <Skeleton className="h-12 w-full" />
                  <Skeleton className="h-12 w-full" />
                  <Skeleton className="h-12 w-full" />
                </div>
              ) : !validationRuns?.runs.length ? (
                <div className="flex h-32 items-center justify-center text-muted-foreground">
                  <div className="text-center">
                    <ListChecks className="h-8 w-8 mx-auto mb-2" />
                    <p>No validation runs yet</p>
                    <p className="text-sm">Run a validation to see results here</p>
                  </div>
                </div>
              ) : (
                <>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Run ID</TableHead>
                        <TableHead>Started</TableHead>
                        <TableHead>Duration</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead className="text-center">Passed</TableHead>
                        <TableHead className="text-center">Failed</TableHead>
                        <TableHead className="text-center">Warnings</TableHead>
                        <TableHead className="text-right">Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {validationRuns.runs.map((run) => (
                        <TableRow key={run.run_id}>
                          <TableCell className="font-medium">
                            #{run.run_id}
                          </TableCell>
                          <TableCell className="text-muted-foreground">
                            {formatDate(run.started_at)}
                          </TableCell>
                          <TableCell className="text-muted-foreground">
                            {formatDuration(run.started_at, run.completed_at)}
                          </TableCell>
                          <TableCell>
                            {getRunStatusBadge(run.status)}
                          </TableCell>
                          <TableCell className="text-center">
                            <Badge variant="outline" className="text-green-600">
                              {run.total_passed}
                            </Badge>
                          </TableCell>
                          <TableCell className="text-center">
                            <Badge variant="outline" className="text-red-600">
                              {run.total_failed}
                            </Badge>
                          </TableCell>
                          <TableCell className="text-center">
                            <Badge variant="outline" className="text-yellow-600">
                              {run.total_warnings}
                            </Badge>
                          </TableCell>
                          <TableCell className="text-right">
                            <Button variant="ghost" size="sm" asChild>
                              <Link to={`/validation/run/${run.run_id}`}>
                                View Details
                              </Link>
                            </Button>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>

                  {/* Pagination */}
                  {validationRuns.pages > 1 && (
                    <div className="flex items-center justify-between mt-4">
                      <div className="text-sm text-muted-foreground">
                        Page {validationRuns.page} of {validationRuns.pages} ({validationRuns.total} runs)
                      </div>
                      <div className="flex gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setRunsPage((p) => Math.max(1, p - 1))}
                          disabled={runsPage === 1}
                        >
                          Previous
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setRunsPage((p) => Math.min(validationRuns.pages, p + 1))}
                          disabled={runsPage === validationRuns.pages}
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

          {/* Source Accuracy Matrix */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Source Accuracy</CardTitle>
                  <CardDescription>
                    Data quality by source for {seasonSummary?.season_display || 'current season'}
                  </CardDescription>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleRunValidation}
                  disabled={triggerValidation.isPending}
                >
                  {triggerValidation.isPending ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Running...
                    </>
                  ) : (
                    <>
                      <Play className="mr-2 h-4 w-4" />
                      Run Validation
                    </>
                  )}
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {summaryLoading ? (
                <div className="space-y-2">
                  <Skeleton className="h-12 w-full" />
                  <Skeleton className="h-12 w-full" />
                  <Skeleton className="h-12 w-full" />
                </div>
              ) : !seasonSummary?.source_accuracy.length ? (
                <div className="flex h-24 items-center justify-center text-muted-foreground">
                  <div className="text-center">
                    <AlertTriangle className="h-6 w-6 mx-auto mb-2" />
                    <p>No validation data available</p>
                    <p className="text-sm">Run validation to see source accuracy</p>
                  </div>
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Source</TableHead>
                      <TableHead className="text-center">Games</TableHead>
                      <TableHead className="text-center">Accuracy</TableHead>
                      <TableHead className="text-center">Discrepancies</TableHead>
                      <TableHead>Status</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {seasonSummary.source_accuracy.map((source) => (
                      <TableRow key={source.source}>
                        <TableCell className="font-medium">
                          {source.source}
                        </TableCell>
                        <TableCell className="text-center text-muted-foreground">
                          {source.total_games}
                        </TableCell>
                        <TableCell className="text-center">
                          <div className="flex items-center justify-center gap-2">
                            <Progress
                              value={source.accuracy_percentage}
                              className="w-16 h-2"
                            />
                            <span className="text-sm font-medium">
                              {source.accuracy_percentage.toFixed(1)}%
                            </span>
                          </div>
                        </TableCell>
                        <TableCell className="text-center">
                          {source.total_discrepancies > 0 ? (
                            <Badge variant="outline" className="text-yellow-600">
                              {source.total_discrepancies}
                            </Badge>
                          ) : (
                            <Badge variant="outline" className="text-green-600">
                              0
                            </Badge>
                          )}
                        </TableCell>
                        <TableCell>
                          {source.accuracy_percentage >= 95 ? (
                            <CheckCircle2 className="h-5 w-5 text-green-500" />
                          ) : source.accuracy_percentage >= 80 ? (
                            <AlertTriangle className="h-5 w-5 text-yellow-500" />
                          ) : (
                            <XCircle className="h-5 w-5 text-red-500" />
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>

          {/* Validation Trend Chart */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <LineChartIcon className="h-5 w-5" />
                Validation Trends
              </CardTitle>
              <CardDescription>
                Pass rate and validation counts over time
              </CardDescription>
            </CardHeader>
            <CardContent>
              {runsLoading ? (
                <Skeleton className="h-64 w-full" />
              ) : !validationRuns?.runs.length ? (
                <div className="flex h-64 items-center justify-center text-muted-foreground">
                  <div className="text-center">
                    <LineChartIcon className="h-8 w-8 mx-auto mb-2" />
                    <p>No validation history</p>
                    <p className="text-sm">Run validations to see trends</p>
                  </div>
                </div>
              ) : (
                <ResponsiveContainer width="100%" height={280}>
                  <LineChart
                    data={validationRuns.runs
                      .slice()
                      .reverse()
                      .map((run) => ({
                        date: new Date(run.started_at).toLocaleDateString(),
                        runId: run.run_id,
                        passRate:
                          run.total_passed + run.total_failed > 0
                            ? Math.round(
                                (run.total_passed /
                                  (run.total_passed + run.total_failed)) *
                                  100
                              )
                            : 0,
                        passed: run.total_passed,
                        failed: run.total_failed,
                        warnings: run.total_warnings,
                      }))}
                    margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" className="opacity-30" />
                    <XAxis
                      dataKey="date"
                      fontSize={12}
                      tickLine={false}
                      axisLine={false}
                    />
                    <YAxis
                      yAxisId="left"
                      fontSize={12}
                      tickLine={false}
                      axisLine={false}
                      domain={[0, 100]}
                      tickFormatter={(value) => `${value}%`}
                    />
                    <YAxis
                      yAxisId="right"
                      orientation="right"
                      fontSize={12}
                      tickLine={false}
                      axisLine={false}
                    />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: 'hsl(var(--card))',
                        border: '1px solid hsl(var(--border))',
                        borderRadius: '6px',
                      }}
                      labelStyle={{ fontWeight: 'bold' }}
                    />
                    <Legend />
                    <Line
                      yAxisId="left"
                      type="monotone"
                      dataKey="passRate"
                      name="Pass Rate %"
                      stroke="hsl(var(--primary))"
                      strokeWidth={2}
                      dot={{ r: 4 }}
                      activeDot={{ r: 6 }}
                    />
                    <Line
                      yAxisId="right"
                      type="monotone"
                      dataKey="passed"
                      name="Passed"
                      stroke="#22c55e"
                      strokeWidth={2}
                      dot={{ r: 3 }}
                    />
                    <Line
                      yAxisId="right"
                      type="monotone"
                      dataKey="failed"
                      name="Failed"
                      stroke="#ef4444"
                      strokeWidth={2}
                      dot={{ r: 3 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </CardContent>
          </Card>

          {/* Recent Discrepancies */}
          <Card>
            <CardHeader>
              <CardTitle>Recent Open Discrepancies</CardTitle>
              <CardDescription>
                Data mismatches that need attention
              </CardDescription>
            </CardHeader>
            <CardContent>
              {discrepanciesLoading ? (
                <div className="space-y-2">
                  <Skeleton className="h-12 w-full" />
                  <Skeleton className="h-12 w-full" />
                </div>
              ) : !discrepancies?.discrepancies.length ? (
                <div className="flex h-24 items-center justify-center text-muted-foreground">
                  <div className="text-center">
                    <CheckCircle2 className="h-6 w-6 mx-auto mb-2 text-green-500" />
                    <p>No open discrepancies</p>
                  </div>
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Rule</TableHead>
                      <TableHead>Entity</TableHead>
                      <TableHead>Field</TableHead>
                      <TableHead>Sources</TableHead>
                      <TableHead>Found</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {discrepancies.discrepancies.map((d) => (
                      <TableRow key={d.discrepancy_id}>
                        <TableCell className="font-medium">
                          {d.rule_name}
                        </TableCell>
                        <TableCell className="text-muted-foreground">
                          {d.entity_type}: {d.entity_id}
                        </TableCell>
                        <TableCell>
                          <Badge variant="secondary">{d.field_name}</Badge>
                        </TableCell>
                        <TableCell className="text-muted-foreground">
                          {d.source_a} vs {d.source_b}
                        </TableCell>
                        <TableCell className="text-muted-foreground">
                          {new Date(d.created_at).toLocaleDateString()}
                        </TableCell>
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
