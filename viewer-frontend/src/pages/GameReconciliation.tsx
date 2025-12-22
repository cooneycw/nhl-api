import { useParams, Link } from 'react-router-dom'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { useGameReconciliation } from '@/hooks/useReconciliation'
import {
  ArrowLeft,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Database,
  FileText,
} from 'lucide-react'

export function GameReconciliation() {
  const { gameId } = useParams<{ gameId: string }>()
  const { data: game, isLoading, error } = useGameReconciliation(Number(gameId))

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    )
  }

  if (error || !game) {
    return (
      <div className="space-y-6">
        <Button variant="ghost" asChild>
          <Link to="/validation">
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Validation
          </Link>
        </Button>
        <Card className="border-destructive">
          <CardContent className="flex items-center gap-2 pt-6">
            <AlertTriangle className="h-5 w-5 text-destructive" />
            <span className="text-destructive">
              Failed to load game reconciliation data. Game ID: {gameId}
            </span>
          </CardContent>
        </Card>
      </div>
    )
  }

  const passedChecks = game.all_checks.filter((c) => c.passed)
  const failedChecks = game.all_checks.filter((c) => !c.passed)

  // Group checks by type
  const checksByType = game.all_checks.reduce(
    (acc, check) => {
      const type = check.rule_name.split('_')[0] || 'other'
      if (!acc[type]) acc[type] = []
      acc[type].push(check)
      return acc
    },
    {} as Record<string, typeof game.all_checks>
  )

  const formatValue = (value: unknown): string => {
    if (value === null || value === undefined) return '-'
    if (typeof value === 'number') return value.toLocaleString()
    if (typeof value === 'object') return JSON.stringify(value)
    return String(value)
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="sm" asChild>
            <Link to="/validation">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back
            </Link>
          </Button>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">
              {game.away_team} @ {game.home_team}
            </h1>
            <p className="text-muted-foreground">
              {new Date(game.game_date).toLocaleDateString('en-US', {
                weekday: 'long',
                year: 'numeric',
                month: 'long',
                day: 'numeric',
              })}
              {' • '}Game ID: {game.game_id}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="outline" className="text-green-600 text-lg px-3 py-1">
            <CheckCircle2 className="mr-1 h-4 w-4" />
            {game.checks_passed} passed
          </Badge>
          <Badge variant="outline" className="text-red-600 text-lg px-3 py-1">
            <XCircle className="mr-1 h-4 w-4" />
            {game.checks_failed} failed
          </Badge>
        </div>
      </div>

      {/* Data Sources */}
      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <Database className="h-4 w-4 text-green-500" />
              Available Sources
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {game.sources_available.map((source) => (
                <Badge key={source} variant="secondary">
                  {source}
                </Badge>
              ))}
              {game.sources_available.length === 0 && (
                <span className="text-muted-foreground text-sm">No sources available</span>
              )}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <FileText className="h-4 w-4 text-yellow-500" />
              Missing Sources
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {game.sources_missing.map((source) => (
                <Badge key={source} variant="outline" className="text-yellow-600">
                  {source}
                </Badge>
              ))}
              {game.sources_missing.length === 0 && (
                <span className="text-green-600 text-sm">All sources available</span>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Checks Tabs */}
      <Tabs defaultValue="failed" className="space-y-4">
        <TabsList>
          <TabsTrigger value="failed" className="gap-2">
            <XCircle className="h-4 w-4" />
            Failed Checks ({failedChecks.length})
          </TabsTrigger>
          <TabsTrigger value="passed" className="gap-2">
            <CheckCircle2 className="h-4 w-4" />
            Passed Checks ({passedChecks.length})
          </TabsTrigger>
          <TabsTrigger value="all" className="gap-2">
            All Checks ({game.all_checks.length})
          </TabsTrigger>
        </TabsList>

        <TabsContent value="failed">
          <Card>
            <CardHeader>
              <CardTitle>Failed Reconciliation Checks</CardTitle>
              <CardDescription>
                These checks found discrepancies between data sources
              </CardDescription>
            </CardHeader>
            <CardContent>
              {failedChecks.length === 0 ? (
                <div className="flex h-24 items-center justify-center text-muted-foreground">
                  <div className="text-center">
                    <CheckCircle2 className="h-8 w-8 mx-auto mb-2 text-green-500" />
                    <p>All checks passed!</p>
                  </div>
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Check</TableHead>
                      <TableHead>Entity</TableHead>
                      <TableHead>Source A</TableHead>
                      <TableHead>Value A</TableHead>
                      <TableHead>Source B</TableHead>
                      <TableHead>Value B</TableHead>
                      <TableHead className="text-right">Difference</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {failedChecks.map((check, i) => (
                      <TableRow key={i}>
                        <TableCell className="font-medium">
                          <Badge variant="destructive" className="font-normal">
                            {check.rule_name}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-muted-foreground">
                          {check.entity_type}: {check.entity_id}
                        </TableCell>
                        <TableCell>{check.source_a}</TableCell>
                        <TableCell className="font-mono">
                          {formatValue(check.source_a_value)}
                        </TableCell>
                        <TableCell>{check.source_b}</TableCell>
                        <TableCell className="font-mono">
                          {formatValue(check.source_b_value)}
                        </TableCell>
                        <TableCell className="text-right font-mono text-red-600">
                          {check.difference !== null ? check.difference : '-'}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="passed">
          <Card>
            <CardHeader>
              <CardTitle>Passed Reconciliation Checks</CardTitle>
              <CardDescription>
                These checks found matching data across sources
              </CardDescription>
            </CardHeader>
            <CardContent>
              {passedChecks.length === 0 ? (
                <div className="flex h-24 items-center justify-center text-muted-foreground">
                  No passed checks
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Check</TableHead>
                      <TableHead>Entity</TableHead>
                      <TableHead>Source A</TableHead>
                      <TableHead>Value A</TableHead>
                      <TableHead>Source B</TableHead>
                      <TableHead>Value B</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {passedChecks.map((check, i) => (
                      <TableRow key={i}>
                        <TableCell className="font-medium">
                          <Badge variant="outline" className="text-green-600 font-normal">
                            {check.rule_name}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-muted-foreground">
                          {check.entity_type}: {check.entity_id}
                        </TableCell>
                        <TableCell>{check.source_a}</TableCell>
                        <TableCell className="font-mono">
                          {formatValue(check.source_a_value)}
                        </TableCell>
                        <TableCell>{check.source_b}</TableCell>
                        <TableCell className="font-mono">
                          {formatValue(check.source_b_value)}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="all">
          <Card>
            <CardHeader>
              <CardTitle>All Reconciliation Checks</CardTitle>
              <CardDescription>
                Complete list of all validation checks for this game
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Status</TableHead>
                    <TableHead>Check</TableHead>
                    <TableHead>Entity</TableHead>
                    <TableHead>Source A</TableHead>
                    <TableHead>Value A</TableHead>
                    <TableHead>Source B</TableHead>
                    <TableHead>Value B</TableHead>
                    <TableHead className="text-right">Difference</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {game.all_checks.map((check, i) => (
                    <TableRow key={i}>
                      <TableCell>
                        {check.passed ? (
                          <CheckCircle2 className="h-4 w-4 text-green-500" />
                        ) : (
                          <XCircle className="h-4 w-4 text-red-500" />
                        )}
                      </TableCell>
                      <TableCell className="font-medium">
                        {check.rule_name}
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {check.entity_type}: {check.entity_id}
                      </TableCell>
                      <TableCell>{check.source_a}</TableCell>
                      <TableCell className="font-mono">
                        {formatValue(check.source_a_value)}
                      </TableCell>
                      <TableCell>{check.source_b}</TableCell>
                      <TableCell className="font-mono">
                        {formatValue(check.source_b_value)}
                      </TableCell>
                      <TableCell className="text-right font-mono">
                        {check.difference !== null ? (
                          <span className={check.passed ? '' : 'text-red-600'}>
                            {check.difference}
                          </span>
                        ) : (
                          '-'
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
