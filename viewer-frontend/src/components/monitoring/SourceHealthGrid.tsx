import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { useSourceHealth } from '@/hooks/useApi'
import {
  CheckCircle,
  AlertTriangle,
  XCircle,
  Loader2,
  CircleOff,
  HelpCircle,
  Database,
  Clock
} from 'lucide-react'
import { type SourceHealth } from '@/lib/api'

type HealthStatus = SourceHealth['health_status']

const statusConfig: Record<HealthStatus, {
  icon: React.ComponentType<{ className?: string }>
  color: string
  bgColor: string
  label: string
}> = {
  healthy: {
    icon: CheckCircle,
    color: 'text-green-600',
    bgColor: 'bg-green-50 border-green-200',
    label: 'Healthy'
  },
  degraded: {
    icon: AlertTriangle,
    color: 'text-yellow-600',
    bgColor: 'bg-yellow-50 border-yellow-200',
    label: 'Degraded'
  },
  error: {
    icon: XCircle,
    color: 'text-red-600',
    bgColor: 'bg-red-50 border-red-200',
    label: 'Error'
  },
  running: {
    icon: Loader2,
    color: 'text-blue-600',
    bgColor: 'bg-blue-50 border-blue-200',
    label: 'Running'
  },
  inactive: {
    icon: CircleOff,
    color: 'text-gray-400',
    bgColor: 'bg-gray-50 border-gray-200',
    label: 'Inactive'
  },
  unknown: {
    icon: HelpCircle,
    color: 'text-gray-500',
    bgColor: 'bg-gray-50 border-gray-200',
    label: 'Unknown'
  },
}

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

function getSuccessRateVariant(rate: number | null): 'secondary' | 'success' | 'warning' | 'error' {
  if (rate === null) return 'secondary'
  if (rate >= 95) return 'success'
  if (rate >= 80) return 'warning'
  return 'error'
}

interface SourceCardProps {
  source: SourceHealth
}

function SourceCard({ source }: SourceCardProps) {
  const config = statusConfig[source.health_status]
  const StatusIcon = config.icon

  return (
    <Card className={`border ${config.bgColor}`}>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-medium truncate">
            {source.source_name}
          </CardTitle>
          <StatusIcon
            className={`h-5 w-5 ${config.color} ${source.health_status === 'running' ? 'animate-spin' : ''}`}
          />
        </div>
        <Badge variant="outline" className="w-fit text-xs">
          {formatSourceType(source.source_type)}
        </Badge>
      </CardHeader>
      <CardContent className="space-y-2">
        {/* Success Rate */}
        {source.success_rate_24h !== null && (
          <div className="flex items-center justify-between">
            <span className="text-xs text-muted-foreground">24h Success</span>
            <Badge variant={getSuccessRateVariant(source.success_rate_24h)}>
              {source.success_rate_24h.toFixed(1)}%
            </Badge>
          </div>
        )}

        {/* Last Activity */}
        <div className="flex items-center justify-between">
          <span className="text-xs text-muted-foreground flex items-center gap-1">
            <Clock className="h-3 w-3" />
            Last Success
          </span>
          <span className="text-xs font-medium">
            {formatTimeAgo(source.latest_completed_at)}
          </span>
        </div>

        {/* 24h Stats */}
        <div className="flex items-center justify-between text-xs">
          <span className="text-muted-foreground flex items-center gap-1">
            <Database className="h-3 w-3" />
            24h Items
          </span>
          <span className="font-medium">
            {source.items_last_24h.toLocaleString()}
            {source.failed_last_24h > 0 && (
              <span className="text-red-500 ml-1">
                ({source.failed_last_24h} failed)
              </span>
            )}
          </span>
        </div>
      </CardContent>
    </Card>
  )
}

function SourceCardSkeleton() {
  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-5 w-5 rounded-full" />
        </div>
        <Skeleton className="h-5 w-16" />
      </CardHeader>
      <CardContent className="space-y-2">
        <div className="flex items-center justify-between">
          <Skeleton className="h-3 w-16" />
          <Skeleton className="h-5 w-12" />
        </div>
        <div className="flex items-center justify-between">
          <Skeleton className="h-3 w-20" />
          <Skeleton className="h-3 w-16" />
        </div>
        <div className="flex items-center justify-between">
          <Skeleton className="h-3 w-14" />
          <Skeleton className="h-3 w-10" />
        </div>
      </CardContent>
    </Card>
  )
}

export function SourceHealthGrid() {
  const { data: sources, isLoading, error, isFetching } = useSourceHealth()

  if (error) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            Source Health
            <Badge variant="destructive">Error</Badge>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            Failed to load source health data
          </p>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Source Health</h2>
        {isFetching && !isLoading && (
          <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
        )}
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {isLoading ? (
          // Show skeleton cards while loading
          Array.from({ length: 6 }).map((_, i) => (
            <SourceCardSkeleton key={i} />
          ))
        ) : sources && sources.length > 0 ? (
          // Sort: active first, then by health status priority
          [...sources]
            .sort((a, b) => {
              // Active sources first
              if (a.is_active !== b.is_active) return a.is_active ? -1 : 1
              // Then by health status priority
              const statusPriority: Record<HealthStatus, number> = {
                error: 0,
                degraded: 1,
                running: 2,
                healthy: 3,
                inactive: 4,
                unknown: 5,
              }
              return statusPriority[a.health_status] - statusPriority[b.health_status]
            })
            .map((source) => (
              <SourceCard key={source.source_id} source={source} />
            ))
        ) : (
          <Card className="col-span-full">
            <CardContent className="flex h-[100px] items-center justify-center text-muted-foreground">
              No sources configured
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  )
}
