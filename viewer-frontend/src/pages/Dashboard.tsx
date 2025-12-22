import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { useHealth } from '@/hooks/useApi'
import { Activity, Database, Clock, CheckCircle, XCircle } from 'lucide-react'
import { DashboardStats, SourceHealthGrid } from '@/components/monitoring'

export function Dashboard() {
  const { data: health, isLoading, error } = useHealth()

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
        <p className="text-muted-foreground">
          Monitor download progress and data quality
        </p>
      </div>

      {/* Health Status */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">API Status</CardTitle>
            <Activity className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <Skeleton className="h-8 w-24" />
            ) : error ? (
              <div className="flex items-center space-x-2">
                <XCircle className="h-5 w-5 text-destructive" />
                <span className="text-lg font-bold text-destructive">Offline</span>
              </div>
            ) : (
              <div className="flex items-center space-x-2">
                <CheckCircle className="h-5 w-5 text-green-500" />
                <span className="text-lg font-bold">{health?.status}</span>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Database</CardTitle>
            <Database className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <Skeleton className="h-8 w-24" />
            ) : (
              <div className="flex items-center space-x-2">
                {health?.database === 'connected' ? (
                  <>
                    <CheckCircle className="h-5 w-5 text-green-500" />
                    <span className="text-lg font-bold">Connected</span>
                  </>
                ) : (
                  <>
                    <XCircle className="h-5 w-5 text-destructive" />
                    <span className="text-lg font-bold text-destructive">Disconnected</span>
                  </>
                )}
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Last Update</CardTitle>
            <Clock className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <Skeleton className="h-8 w-32" />
            ) : (
              <div className="text-lg font-bold">
                {health?.timestamp
                  ? new Date(health.timestamp).toLocaleTimeString()
                  : '-'}
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Environment</CardTitle>
          </CardHeader>
          <CardContent>
            <Badge variant="secondary">Development</Badge>
          </CardContent>
        </Card>
      </div>

      {/* Download Stats Summary */}
      <div className="space-y-4">
        <h2 className="text-lg font-semibold">Download Stats</h2>
        <DashboardStats />
      </div>

      {/* Active Downloads placeholder */}
      <Card>
        <CardHeader>
          <CardTitle>Active Downloads</CardTitle>
          <CardDescription>
            Real-time download progress will appear here
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex h-[200px] items-center justify-center text-muted-foreground">
            <p>Coming soon (#167)</p>
          </div>
        </CardContent>
      </Card>

      {/* Source Health Grid */}
      <SourceHealthGrid />
    </div>
  )
}
