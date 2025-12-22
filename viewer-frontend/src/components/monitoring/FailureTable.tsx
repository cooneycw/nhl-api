import { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Tooltip } from '@/components/ui/tooltip'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { useFailures, useRetryDownload } from '@/hooks/useApi'
import {
  RefreshCw,
  AlertCircle,
  ChevronLeft,
  ChevronRight,
  Loader2,
} from 'lucide-react'
import { type FailedDownload } from '@/lib/api'

function formatSourceType(type: string): string {
  const typeLabels: Record<string, string> = {
    nhl_json: 'NHL JSON',
    html_report: 'HTML Report',
    shift_chart: 'Shift Chart',
    external: 'External',
    dailyfaceoff: 'DailyFaceoff',
  }
  return typeLabels[type] || type
}

function formatTimeAgo(dateString: string | null): string {
  if (!dateString) return 'Never'

  const date = new Date(dateString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMins / 60)
  const diffDays = Math.floor(diffHours / 24)

  if (diffMins < 1) return 'Just now'
  if (diffMins < 60) return `${diffMins}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  if (diffDays < 7) return `${diffDays}d ago`
  return date.toLocaleDateString()
}

function truncateError(error: string | null, maxLength = 40): string {
  if (!error) return '-'
  if (error.length <= maxLength) return error
  return error.slice(0, maxLength) + '...'
}

interface FailureRowProps {
  failure: FailedDownload
  onRetry: (progressId: number) => void
  isRetrying: boolean
}

function FailureRow({ failure, onRetry, isRetrying }: FailureRowProps) {
  const errorTruncated = truncateError(failure.error_message)
  const needsTooltip = failure.error_message && failure.error_message.length > 40

  return (
    <TableRow>
      <TableCell className="font-medium">
        <div className="flex flex-col gap-1">
          <span className="text-sm">{failure.source_name}</span>
          <Badge variant="outline" className="w-fit text-xs">
            {formatSourceType(failure.source_type)}
          </Badge>
        </div>
      </TableCell>
      <TableCell className="font-mono text-xs max-w-[200px] truncate">
        {failure.item_key}
      </TableCell>
      <TableCell>
        {needsTooltip ? (
          <Tooltip content={failure.error_message} side="top">
            <span className="text-sm text-muted-foreground cursor-help">
              {errorTruncated}
            </span>
          </Tooltip>
        ) : (
          <span className="text-sm text-muted-foreground">
            {errorTruncated}
          </span>
        )}
      </TableCell>
      <TableCell className="text-center">
        <Badge variant="secondary">{failure.attempts}</Badge>
      </TableCell>
      <TableCell className="text-sm text-muted-foreground">
        {formatTimeAgo(failure.last_attempt_at)}
      </TableCell>
      <TableCell>
        <Button
          variant="outline"
          size="sm"
          onClick={() => onRetry(failure.progress_id)}
          disabled={isRetrying}
          className="gap-1"
        >
          {isRetrying ? (
            <Loader2 className="h-3 w-3 animate-spin" />
          ) : (
            <RefreshCw className="h-3 w-3" />
          )}
          Retry
        </Button>
      </TableCell>
    </TableRow>
  )
}

function TableSkeleton() {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Source</TableHead>
          <TableHead>Item Key</TableHead>
          <TableHead>Error</TableHead>
          <TableHead className="text-center">Attempts</TableHead>
          <TableHead>Time</TableHead>
          <TableHead>Action</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {Array.from({ length: 5 }).map((_, i) => (
          <TableRow key={i}>
            <TableCell><Skeleton className="h-10 w-24" /></TableCell>
            <TableCell><Skeleton className="h-4 w-32" /></TableCell>
            <TableCell><Skeleton className="h-4 w-40" /></TableCell>
            <TableCell><Skeleton className="h-5 w-8 mx-auto" /></TableCell>
            <TableCell><Skeleton className="h-4 w-16" /></TableCell>
            <TableCell><Skeleton className="h-8 w-16" /></TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}

export function FailureTable() {
  const [page, setPage] = useState(1)
  const pageSize = 10
  const { data, isLoading, error, isFetching } = useFailures(page, pageSize)
  const retryMutation = useRetryDownload()
  const [retryingId, setRetryingId] = useState<number | null>(null)

  const handleRetry = async (progressId: number) => {
    setRetryingId(progressId)
    try {
      await retryMutation.mutateAsync(progressId)
    } finally {
      setRetryingId(null)
    }
  }

  if (error) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <AlertCircle className="h-5 w-5 text-destructive" />
            Recent Failures
            <Badge variant="destructive">Error</Badge>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            Failed to load failure data
          </p>
        </CardContent>
      </Card>
    )
  }

  const failures = data?.failures || []
  const totalPages = data?.pages || 1
  const totalFailures = data?.total || 0

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg flex items-center gap-2">
            <AlertCircle className="h-5 w-5 text-orange-500" />
            Recent Failures
            {totalFailures > 0 && (
              <Badge variant="destructive">{totalFailures}</Badge>
            )}
          </CardTitle>
          {isFetching && !isLoading && (
            <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
          )}
        </div>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <TableSkeleton />
        ) : failures.length === 0 ? (
          <div className="flex h-[200px] items-center justify-center text-muted-foreground">
            <div className="text-center">
              <AlertCircle className="h-8 w-8 mx-auto mb-2 text-green-500" />
              <p>No failures - all downloads successful!</p>
            </div>
          </div>
        ) : (
          <>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Source</TableHead>
                  <TableHead>Item Key</TableHead>
                  <TableHead>Error</TableHead>
                  <TableHead className="text-center">Attempts</TableHead>
                  <TableHead>Time</TableHead>
                  <TableHead>Action</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {failures.map((failure) => (
                  <FailureRow
                    key={failure.progress_id}
                    failure={failure}
                    onRetry={handleRetry}
                    isRetrying={retryingId === failure.progress_id}
                  />
                ))}
              </TableBody>
            </Table>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-between mt-4">
                <p className="text-sm text-muted-foreground">
                  Showing {(page - 1) * pageSize + 1}-{Math.min(page * pageSize, totalFailures)} of {totalFailures}
                </p>
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setPage(p => Math.max(1, p - 1))}
                    disabled={page === 1}
                  >
                    <ChevronLeft className="h-4 w-4" />
                  </Button>
                  <span className="text-sm">
                    Page {page} of {totalPages}
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                    disabled={page === totalPages}
                  >
                    <ChevronRight className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  )
}
