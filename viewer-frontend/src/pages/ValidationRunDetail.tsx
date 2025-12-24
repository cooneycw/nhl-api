import { useParams, Link } from 'react-router-dom'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { useValidationRun, type ValidationResult } from '@/hooks/useValidation'
import {
  CheckCircle2,
  XCircle,
  AlertTriangle,
  ArrowLeft,
  Clock,
  ListChecks,
} from 'lucide-react'

export function ValidationRunDetail() {
  const { runId } = useParams<{ runId: string }>()
  const { data: run, isLoading, error } = useValidationRun(Number(runId))

  const getStatusBadge = (status: string) => {
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

  const getSeverityBadge = (severity: string | null) => {
    switch (severity) {
      case 'error':
        return <Badge variant="error">Error</Badge>
      case 'warning':
        return <Badge variant="warning">Warning</Badge>
      case 'info':
        return <Badge variant="secondary">Info</Badge>
      default:
        return null
    }
  }

  const getResultIcon = (result: ValidationResult) => {
    if (result.passed) {
      return <CheckCircle2 className="h-4 w-4 text-green-500" />
    }
    if (result.severity === 'warning') {
      return <AlertTriangle className="h-4 w-4 text-yellow-500" />
    }
    return <XCircle className="h-4 w-4 text-red-500" />
  }

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

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-48 w-full" />
        <Skeleton className="h-96 w-full" />
      </div>
    )
  }

  if (error || !run) {
    return (
      <div className="space-y-6">
        <Button variant="ghost" asChild>
          <Link to="/validation" className="gap-2">
            <ArrowLeft className="h-4 w-4" />
            Back to Validation
          </Link>
        </Button>
        <Card className="border-destructive">
          <CardContent className="flex items-center gap-2 pt-6">
            <AlertTriangle className="h-5 w-5 text-destructive" />
            <span className="text-destructive">
              Failed to load validation run. The run may not exist.
            </span>
          </CardContent>
        </Card>
      </div>
    )
  }

  const totalChecks = run.total_passed + run.total_failed
  const passRate = totalChecks > 0 ? (run.total_passed / totalChecks) * 100 : 0
  const failedResults = run.results.filter((r) => !r.passed)
  const passedResults = run.results.filter((r) => r.passed)

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="sm" asChild>
            <Link to="/validation" className="gap-2">
              <ArrowLeft className="h-4 w-4" />
              Back
            </Link>
          </Button>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">
              Validation Run #{run.run_id}
            </h1>
            <p className="text-muted-foreground">
              {run.season_id ? `Season ${run.season_id}` : 'All seasons'}
            </p>
          </div>
        </div>
        {getStatusBadge(run.status)}
      </div>

      {/* Summary Cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
              <Clock className="h-4 w-4" />
              Started
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-lg font-semibold">
              {formatDate(run.started_at)}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Duration
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-lg font-semibold">
              {formatDuration(run.started_at, run.completed_at)}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Rules Checked
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-lg font-semibold">{run.rules_checked}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Pass Rate
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              <div className="text-lg font-semibold">
                {passRate.toFixed(1)}%
              </div>
              <Progress value={passRate} />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Results Summary */}
      <Card className="bg-gradient-to-br from-primary/5 to-primary/10">
        <CardContent className="pt-6">
          <div className="flex items-center justify-around">
            <div className="text-center">
              <div className="flex items-center justify-center gap-2 mb-1">
                <CheckCircle2 className="h-5 w-5 text-green-500" />
                <span className="text-sm font-medium text-muted-foreground">Passed</span>
              </div>
              <div className="text-3xl font-bold text-green-600">{run.total_passed}</div>
            </div>
            <div className="text-center">
              <div className="flex items-center justify-center gap-2 mb-1">
                <XCircle className="h-5 w-5 text-red-500" />
                <span className="text-sm font-medium text-muted-foreground">Failed</span>
              </div>
              <div className="text-3xl font-bold text-red-600">{run.total_failed}</div>
            </div>
            <div className="text-center">
              <div className="flex items-center justify-center gap-2 mb-1">
                <AlertTriangle className="h-5 w-5 text-yellow-500" />
                <span className="text-sm font-medium text-muted-foreground">Warnings</span>
              </div>
              <div className="text-3xl font-bold text-yellow-600">{run.total_warnings}</div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Failed Results */}
      {failedResults.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-red-600">
              <XCircle className="h-5 w-5" />
              Failed Checks ({failedResults.length})
            </CardTitle>
            <CardDescription>
              Validation checks that did not pass
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-8"></TableHead>
                  <TableHead>Rule</TableHead>
                  <TableHead>Game</TableHead>
                  <TableHead>Severity</TableHead>
                  <TableHead>Message</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {failedResults.map((result) => (
                  <TableRow key={result.result_id}>
                    <TableCell>{getResultIcon(result)}</TableCell>
                    <TableCell className="font-medium">
                      {result.rule_name}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {result.game_id ? (
                        <Link
                          to={`/games/${result.game_id}`}
                          className="hover:underline"
                        >
                          #{result.game_id}
                        </Link>
                      ) : (
                        'N/A'
                      )}
                    </TableCell>
                    <TableCell>
                      {getSeverityBadge(result.severity)}
                    </TableCell>
                    <TableCell className="max-w-md truncate">
                      {result.message || 'No message'}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {/* Passed Results */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-green-600">
            <CheckCircle2 className="h-5 w-5" />
            Passed Checks ({passedResults.length})
          </CardTitle>
          <CardDescription>
            Validation checks that passed successfully
          </CardDescription>
        </CardHeader>
        <CardContent>
          {passedResults.length === 0 ? (
            <div className="flex h-24 items-center justify-center text-muted-foreground">
              <div className="text-center">
                <ListChecks className="h-6 w-6 mx-auto mb-2" />
                <p>No passed checks to display</p>
              </div>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-8"></TableHead>
                  <TableHead>Rule</TableHead>
                  <TableHead>Game</TableHead>
                  <TableHead>Message</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {passedResults.slice(0, 20).map((result) => (
                  <TableRow key={result.result_id}>
                    <TableCell>{getResultIcon(result)}</TableCell>
                    <TableCell className="font-medium">
                      {result.rule_name}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {result.game_id ? (
                        <Link
                          to={`/games/${result.game_id}`}
                          className="hover:underline"
                        >
                          #{result.game_id}
                        </Link>
                      ) : (
                        'N/A'
                      )}
                    </TableCell>
                    <TableCell className="max-w-md truncate text-muted-foreground">
                      {result.message || 'Check passed'}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
          {passedResults.length > 20 && (
            <div className="mt-4 text-center text-sm text-muted-foreground">
              Showing 20 of {passedResults.length} passed checks
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
