import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { Loader2, X, Clock } from 'lucide-react'
import { type ActiveDownload } from '@/hooks/useDownloads'

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

function formatTimeAgo(dateString: string): string {
  const date = new Date(dateString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMins / 60)

  if (diffMins < 1) return 'Just started'
  if (diffMins < 60) return `${diffMins}m ago`
  return `${diffHours}h ${diffMins % 60}m ago`
}

interface BatchCardProps {
  batch: ActiveDownload
  onCancel: (batchId: number) => void
  isCancelling: boolean
}

export function BatchCard({ batch, onCancel, isCancelling }: BatchCardProps) {
  const progressPercent = batch.progress_percent ?? 0
  const hasTotal = batch.items_total !== null && batch.items_total > 0

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <div className="space-y-1">
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            {batch.source_name}
            <Badge variant="outline" className="text-xs">
              {formatSourceType(batch.source_type)}
            </Badge>
          </CardTitle>
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <span>{batch.season_label}</span>
            <span>•</span>
            <Clock className="h-3 w-3" />
            <span>{formatTimeAgo(batch.started_at)}</span>
          </div>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => onCancel(batch.batch_id)}
          disabled={isCancelling}
          className="h-8 w-8 p-0 text-muted-foreground hover:text-destructive"
        >
          {isCancelling ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <X className="h-4 w-4" />
          )}
        </Button>
      </CardHeader>
      <CardContent className="space-y-2">
        <Progress value={progressPercent} className="h-2" />
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>
            {hasTotal ? (
              <>
                {batch.items_completed.toLocaleString()} / {batch.items_total?.toLocaleString()} items
              </>
            ) : (
              <>{batch.items_completed.toLocaleString()} items processed</>
            )}
          </span>
          <span className="font-mono font-medium">
            {progressPercent.toFixed(0)}%
          </span>
        </div>
        {batch.items_failed > 0 && (
          <div className="text-xs text-destructive">
            {batch.items_failed} failed
          </div>
        )}
      </CardContent>
    </Card>
  )
}
