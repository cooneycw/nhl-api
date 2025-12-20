import { useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Checkbox } from '@/components/ui/checkbox'
import { Progress } from '@/components/ui/progress'
import { Skeleton } from '@/components/ui/skeleton'
import {
  useDownloadOptions,
  useActiveDownloads,
  useStartDownload,
  useCancelDownload,
  type SourceGroup,
} from '@/hooks/useDownloads'
import { Download, X, Loader2, Play, AlertCircle } from 'lucide-react'

export function Downloads() {
  const { data: options, isLoading: optionsLoading, error: optionsError } = useDownloadOptions()
  const { data: activeDownloads, isLoading: activeLoading } = useActiveDownloads()
  const startDownload = useStartDownload()
  const cancelDownload = useCancelDownload()

  const [selectedSeasons, setSelectedSeasons] = useState<number[]>([])
  const [selectedSources, setSelectedSources] = useState<string[]>([])

  const toggleSeason = (seasonId: number) => {
    setSelectedSeasons((prev) =>
      prev.includes(seasonId)
        ? prev.filter((s) => s !== seasonId)
        : [...prev, seasonId]
    )
  }

  const toggleSource = (sourceName: string) => {
    setSelectedSources((prev) =>
      prev.includes(sourceName)
        ? prev.filter((s) => s !== sourceName)
        : [...prev, sourceName]
    )
  }

  const selectAllInGroup = (group: SourceGroup) => {
    const groupSourceNames = group.sources.map((s) => s.name)
    const allSelected = groupSourceNames.every((name) => selectedSources.includes(name))

    if (allSelected) {
      // Deselect all in group
      setSelectedSources((prev) => prev.filter((s) => !groupSourceNames.includes(s)))
    } else {
      // Select all in group
      setSelectedSources((prev) => [...new Set([...prev, ...groupSourceNames])])
    }
  }

  const handleStartDownload = async () => {
    if (selectedSeasons.length === 0 || selectedSources.length === 0) return

    try {
      await startDownload.mutateAsync({
        season_ids: selectedSeasons,
        source_names: selectedSources,
      })
      // Clear selections after successful start
      setSelectedSeasons([])
      setSelectedSources([])
    } catch (error) {
      console.error('Failed to start download:', error)
    }
  }

  const handleCancelDownload = (batchId: number) => {
    cancelDownload.mutate(batchId)
  }

  const canStartDownload =
    selectedSeasons.length > 0 &&
    selectedSources.length > 0 &&
    !startDownload.isPending

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Downloads</h1>
        <p className="text-muted-foreground">
          Select seasons and data sources to download
        </p>
      </div>

      {optionsError && (
        <Card className="border-destructive">
          <CardContent className="flex items-center gap-2 pt-6">
            <AlertCircle className="h-5 w-5 text-destructive" />
            <span className="text-destructive">Failed to load download options</span>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-4 md:grid-cols-2">
        {/* Season Selection */}
        <Card>
          <CardHeader>
            <CardTitle>Seasons</CardTitle>
            <CardDescription>Select one or more seasons to download</CardDescription>
          </CardHeader>
          <CardContent>
            {optionsLoading ? (
              <div className="space-y-2">
                <Skeleton className="h-6 w-32" />
                <Skeleton className="h-6 w-32" />
              </div>
            ) : (
              <div className="space-y-3">
                {options?.seasons.map((season) => (
                  <div
                    key={season.season_id}
                    className="flex items-center space-x-3"
                  >
                    <Checkbox
                      id={`season-${season.season_id}`}
                      checked={selectedSeasons.includes(season.season_id)}
                      onCheckedChange={() => toggleSeason(season.season_id)}
                    />
                    <label
                      htmlFor={`season-${season.season_id}`}
                      className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70 cursor-pointer"
                    >
                      {season.label}
                      {season.is_current && (
                        <Badge variant="secondary" className="ml-2">
                          Current
                        </Badge>
                      )}
                    </label>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Source Selection */}
        <Card>
          <CardHeader>
            <CardTitle>Data Sources</CardTitle>
            <CardDescription>Select data types to download</CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {optionsLoading ? (
              <div className="space-y-2">
                <Skeleton className="h-6 w-40" />
                <Skeleton className="h-6 w-36" />
                <Skeleton className="h-6 w-44" />
              </div>
            ) : (
              options?.source_groups.map((group) => {
                const groupSourceNames = group.sources.map((s) => s.name)
                const allSelected = groupSourceNames.every((name) =>
                  selectedSources.includes(name)
                )
                const someSelected =
                  !allSelected &&
                  groupSourceNames.some((name) => selectedSources.includes(name))

                return (
                  <div key={group.source_type} className="space-y-2">
                    {/* Group header with select all */}
                    <div className="flex items-center space-x-3">
                      <Checkbox
                        id={`group-${group.source_type}`}
                        checked={allSelected}
                        data-state={someSelected ? 'indeterminate' : undefined}
                        onCheckedChange={() => selectAllInGroup(group)}
                      />
                      <label
                        htmlFor={`group-${group.source_type}`}
                        className="text-sm font-semibold cursor-pointer"
                      >
                        {group.display_name}
                      </label>
                    </div>

                    {/* Individual sources */}
                    <div className="ml-6 space-y-2">
                      {group.sources.map((source) => (
                        <div
                          key={source.source_id}
                          className="flex items-center space-x-3"
                        >
                          <Checkbox
                            id={`source-${source.source_id}`}
                            checked={selectedSources.includes(source.name)}
                            onCheckedChange={() => toggleSource(source.name)}
                          />
                          <label
                            htmlFor={`source-${source.source_id}`}
                            className="text-sm leading-none cursor-pointer"
                          >
                            {source.display_name}
                          </label>
                        </div>
                      ))}
                    </div>
                  </div>
                )
              })
            )}
          </CardContent>
        </Card>
      </div>

      {/* Start Download Button */}
      <div className="flex items-center justify-between">
        <div className="text-sm text-muted-foreground">
          {selectedSeasons.length > 0 && selectedSources.length > 0 ? (
            <>
              {selectedSeasons.length} season(s) × {selectedSources.length} source(s) ={' '}
              <span className="font-medium">
                {selectedSeasons.length * selectedSources.length} batch(es)
              </span>
            </>
          ) : (
            'Select at least one season and one source'
          )}
        </div>
        <Button
          size="lg"
          onClick={handleStartDownload}
          disabled={!canStartDownload}
        >
          {startDownload.isPending ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Starting...
            </>
          ) : (
            <>
              <Play className="mr-2 h-4 w-4" />
              Start Download
            </>
          )}
        </Button>
      </div>

      {/* Active Downloads with Progress Bars */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Download className="h-5 w-5" />
            Active Downloads
          </CardTitle>
          <CardDescription>
            Real-time progress of running downloads
          </CardDescription>
        </CardHeader>
        <CardContent>
          {activeLoading ? (
            <div className="space-y-4">
              <Skeleton className="h-16 w-full" />
              <Skeleton className="h-16 w-full" />
            </div>
          ) : !activeDownloads?.downloads.length ? (
            <div className="flex h-24 items-center justify-center text-muted-foreground">
              No active downloads
            </div>
          ) : (
            <div className="space-y-4">
              {activeDownloads.downloads.map((download) => (
                <div
                  key={download.batch_id}
                  className="rounded-lg border p-4 space-y-3"
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="font-medium">
                        {download.source_name.replace('nhl_', '').replace('_', ' ').toUpperCase()}
                      </div>
                      <div className="text-sm text-muted-foreground">
                        {download.season_label} • Batch #{download.batch_id}
                      </div>
                    </div>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => handleCancelDownload(download.batch_id)}
                      disabled={cancelDownload.isPending}
                    >
                      <X className="h-4 w-4" />
                    </Button>
                  </div>

                  {/* Progress Bar */}
                  <div className="space-y-1">
                    <div className="flex justify-between text-sm">
                      <span>
                        {download.items_completed}
                        {download.items_total ? ` / ${download.items_total}` : ''} items
                        {download.items_failed > 0 && (
                          <span className="text-destructive ml-2">
                            ({download.items_failed} failed)
                          </span>
                        )}
                      </span>
                      <span className="font-medium">
                        {download.progress_percent
                          ? `${download.progress_percent.toFixed(1)}%`
                          : 'Starting...'}
                      </span>
                    </div>
                    <Progress value={download.progress_percent ?? 0} />
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
