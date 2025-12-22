import { useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { useActiveDownloads, useCancelDownload } from '@/hooks/useDownloads'
import { BatchCard } from './BatchCard'
import { Loader2, Download } from 'lucide-react'

function BatchCardSkeleton() {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <div className="space-y-2">
          <Skeleton className="h-4 w-32" />
          <Skeleton className="h-3 w-24" />
        </div>
        <Skeleton className="h-8 w-8" />
      </CardHeader>
      <CardContent className="space-y-2">
        <Skeleton className="h-2 w-full" />
        <div className="flex justify-between">
          <Skeleton className="h-3 w-24" />
          <Skeleton className="h-3 w-8" />
        </div>
      </CardContent>
    </Card>
  )
}

export function ActiveBatches() {
  const { data, isLoading, error, isFetching } = useActiveDownloads()
  const cancelMutation = useCancelDownload()
  const [cancellingId, setCancellingId] = useState<number | null>(null)

  const handleCancel = async (batchId: number) => {
    setCancellingId(batchId)
    try {
      await cancelMutation.mutateAsync(batchId)
    } finally {
      setCancellingId(null)
    }
  }

  if (error) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Download className="h-5 w-5" />
            Active Downloads
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            Failed to load active downloads
          </p>
        </CardContent>
      </Card>
    )
  }

  const downloads = data?.downloads || []

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="text-lg flex items-center gap-2">
              <Download className="h-5 w-5" />
              Active Downloads
              {downloads.length > 0 && (
                <span className="text-sm font-normal text-muted-foreground">
                  ({downloads.length})
                </span>
              )}
            </CardTitle>
            <CardDescription>
              Real-time download progress with cancel functionality
            </CardDescription>
          </div>
          {isFetching && !isLoading && (
            <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
          )}
        </div>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            <BatchCardSkeleton />
            <BatchCardSkeleton />
          </div>
        ) : downloads.length === 0 ? (
          <div className="flex h-[120px] items-center justify-center text-muted-foreground">
            <div className="text-center">
              <Download className="h-8 w-8 mx-auto mb-2 opacity-50" />
              <p>No active downloads</p>
              <p className="text-xs mt-1">Start a download from the Downloads page</p>
            </div>
          </div>
        ) : (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {downloads.map((batch) => (
              <BatchCard
                key={batch.batch_id}
                batch={batch}
                onCancel={handleCancel}
                isCancelling={cancellingId === batch.batch_id}
              />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
