import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { useDashboard } from '@/hooks/useApi'
import {
  Loader2,
  CheckCircle,
  AlertTriangle,
  TrendingUp,
} from 'lucide-react'

function getSuccessRateColor(rate: number | null): string {
  if (rate === null) return 'text-gray-400'
  if (rate >= 95) return 'text-green-500'
  if (rate >= 80) return 'text-yellow-500'
  return 'text-red-500'
}

function StatCardSkeleton() {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-4 w-4" />
      </CardHeader>
      <CardContent>
        <Skeleton className="h-8 w-16" />
      </CardContent>
    </Card>
  )
}

export function DashboardStats() {
  const { data, isLoading, isFetching } = useDashboard()
  const stats = data?.stats

  if (isLoading) {
    return (
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <StatCardSkeleton />
        <StatCardSkeleton />
        <StatCardSkeleton />
        <StatCardSkeleton />
      </div>
    )
  }

  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
      {/* Active Batches */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Active Batches</CardTitle>
          <Loader2
            className={`h-4 w-4 text-blue-500 ${
              stats?.active_batches && stats.active_batches > 0 ? 'animate-spin' : ''
            }`}
          />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">
            {stats?.active_batches ?? 0}
          </div>
          <p className="text-xs text-muted-foreground">
            {stats?.active_batches && stats.active_batches > 0
              ? 'Downloads in progress'
              : 'No active downloads'}
          </p>
        </CardContent>
      </Card>

      {/* Completed Today */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Completed Today</CardTitle>
          <CheckCircle className="h-4 w-4 text-green-500" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">
            {stats?.completed_today ?? 0}
          </div>
          <p className="text-xs text-muted-foreground">
            {stats?.total_items_24h?.toLocaleString() ?? 0} items in 24h
          </p>
        </CardContent>
      </Card>

      {/* Failed Today */}
      <Card className={stats?.failed_today && stats.failed_today > 0 ? 'border-red-200 bg-red-50/50' : ''}>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Failed Today</CardTitle>
          <AlertTriangle
            className={`h-4 w-4 ${
              stats?.failed_today && stats.failed_today > 0
                ? 'text-red-500'
                : 'text-muted-foreground'
            }`}
          />
        </CardHeader>
        <CardContent>
          <div
            className={`text-2xl font-bold ${
              stats?.failed_today && stats.failed_today > 0 ? 'text-red-600' : ''
            }`}
          >
            {stats?.failed_today ?? 0}
          </div>
          <p className="text-xs text-muted-foreground">
            {stats?.failed_today && stats.failed_today > 0
              ? 'Batches need attention'
              : 'All batches healthy'}
          </p>
        </CardContent>
      </Card>

      {/* 24h Success Rate */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">24h Success Rate</CardTitle>
          <TrendingUp
            className={`h-4 w-4 ${getSuccessRateColor(stats?.success_rate_24h ?? null)}`}
          />
        </CardHeader>
        <CardContent>
          <div className={`text-2xl font-bold ${getSuccessRateColor(stats?.success_rate_24h ?? null)}`}>
            {stats?.success_rate_24h !== null && stats?.success_rate_24h !== undefined
              ? `${stats.success_rate_24h.toFixed(1)}%`
              : 'N/A'}
          </div>
          <p className="text-xs text-muted-foreground">
            {isFetching ? 'Updating...' : 'Auto-refresh 10s'}
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
