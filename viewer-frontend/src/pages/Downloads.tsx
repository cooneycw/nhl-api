import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Checkbox } from '@/components/ui/checkbox'
import { Progress } from '@/components/ui/progress'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog'
import {
  useDownloadOptions,
  useActiveDownloads,
  useStartDownload,
  useCancelDownload,
  useDeleteSeason,
  type SourceGroup,
  type DeleteSeasonResponse,
} from '@/hooks/useDownloads'
import {
  useSyncStatus,
  usePriorSeasons,
  useQuickPreseason,
  useQuickRegular,
  useQuickPlayoffs,
  useQuickExternal,
  useQuickPriorSeason,
} from '@/hooks/useQuickDownloads'
import {
  Download,
  X,
  Loader2,
  Play,
  AlertCircle,
  Trash2,
  ChevronDown,
  ChevronRight,
  Calendar,
  Trophy,
  Snowflake,
  RefreshCw,
  History,
  Clock,
  CheckCircle,
  AlertTriangle,
} from 'lucide-react'

// Source types to auto-select by default (NHL API sources)
const DEFAULT_SELECTED_SOURCE_TYPES = ['nhl_json', 'html_report', 'shift_chart']

// Game types with labels
const GAME_TYPES = [
  { id: 1, label: 'Pre-season', description: 'Exhibition games before regular season' },
  { id: 2, label: 'Regular Season', description: 'Standard 82-game season' },
  { id: 3, label: 'Playoffs', description: 'Stanley Cup playoffs' },
]

// Format relative time
function formatRelativeTime(dateStr: string | null): string {
  if (!dateStr) return 'Never'

  const date = new Date(dateStr)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)

  if (diffMins < 1) return 'Just now'
  if (diffMins < 60) return `${diffMins}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  if (diffDays < 7) return `${diffDays}d ago`
  return date.toLocaleDateString()
}

export function Downloads() {
  // Existing hooks
  const { data: options, isLoading: optionsLoading, error: optionsError } = useDownloadOptions()
  const { data: activeDownloads, isLoading: activeLoading } = useActiveDownloads()
  const startDownload = useStartDownload()
  const cancelDownload = useCancelDownload()
  const deleteSeason = useDeleteSeason()

  // Quick download hooks
  const { data: syncStatus, isLoading: syncLoading } = useSyncStatus()
  const { data: priorSeasons, isLoading: seasonsLoading } = usePriorSeasons()
  const quickPreseason = useQuickPreseason()
  const quickRegular = useQuickRegular()
  const quickPlayoffs = useQuickPlayoffs()
  const quickExternal = useQuickExternal()
  const quickPriorSeason = useQuickPriorSeason()

  // State
  const [selectedSeasons, setSelectedSeasons] = useState<number[]>([])
  const [selectedSources, setSelectedSources] = useState<string[]>([])
  const [selectedGameTypes, setSelectedGameTypes] = useState<number[]>([2])
  const [initialized, setInitialized] = useState(false)
  const [deletePreview, setDeletePreview] = useState<DeleteSeasonResponse | null>(null)
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [advancedOpen, setAdvancedOpen] = useState(false)
  const [selectedPriorSeason, setSelectedPriorSeason] = useState<string>('')

  // Set default selections when options load
  useEffect(() => {
    if (options && !initialized) {
      const currentSeason = options.seasons.find((s) => s.is_current)
      if (currentSeason) {
        setSelectedSeasons([currentSeason.season_id])
      }

      const defaultSources = options.source_groups
        .filter((g) => DEFAULT_SELECTED_SOURCE_TYPES.includes(g.source_type))
        .flatMap((g) => g.sources.map((s) => s.name))
      setSelectedSources(defaultSources)

      setInitialized(true)
    }
  }, [options, initialized])

  // Advanced mode handlers
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

  const toggleGameType = (gameTypeId: number) => {
    setSelectedGameTypes((prev) =>
      prev.includes(gameTypeId)
        ? prev.filter((t) => t !== gameTypeId)
        : [...prev, gameTypeId]
    )
  }

  const selectAllInGroup = (group: SourceGroup) => {
    const groupSourceNames = group.sources.map((s) => s.name)
    const allSelected = groupSourceNames.every((name) => selectedSources.includes(name))

    if (allSelected) {
      setSelectedSources((prev) => prev.filter((s) => !groupSourceNames.includes(s)))
    } else {
      setSelectedSources((prev) => [...new Set([...prev, ...groupSourceNames])])
    }
  }

  const handleStartDownload = async () => {
    if (selectedSeasons.length === 0 || selectedSources.length === 0 || selectedGameTypes.length === 0) return

    try {
      await startDownload.mutateAsync({
        season_ids: selectedSeasons,
        source_names: selectedSources,
        game_types: selectedGameTypes,
      })
      setSelectedSeasons([])
      setSelectedSources([])
      setSelectedGameTypes([2])
    } catch (error) {
      console.error('Failed to start download:', error)
    }
  }

  const handleCancelDownload = (batchId: number) => {
    cancelDownload.mutate(batchId)
  }

  const handleDeletePreview = async (seasonId: number) => {
    try {
      const result = await deleteSeason.mutateAsync({ seasonId, dryRun: true })
      setDeletePreview(result)
      setDeleteDialogOpen(true)
    } catch (error) {
      console.error('Failed to get delete preview:', error)
    }
  }

  const handleDeleteConfirm = async () => {
    if (!deletePreview) return

    try {
      await deleteSeason.mutateAsync({ seasonId: deletePreview.season_id, dryRun: false })
      setDeleteDialogOpen(false)
      setDeletePreview(null)
    } catch (error) {
      console.error('Failed to delete season data:', error)
    }
  }

  const handlePriorSeasonDownload = async () => {
    if (!selectedPriorSeason) return
    try {
      await quickPriorSeason.mutateAsync(parseInt(selectedPriorSeason))
      setSelectedPriorSeason('')
    } catch (error) {
      console.error('Failed to start prior season download:', error)
    }
  }

  // Get sync status for a specific game type
  const getSyncStatusForGameType = (gameType: number) => {
    if (!syncStatus) return null
    // Find the most recent sync for this game type across all sources
    const relevantItems = syncStatus.items.filter((item) => item.game_type === gameType)
    if (relevantItems.length === 0) return null

    const synced = relevantItems.filter((item) => item.last_synced_at)
    if (synced.length === 0) return { status: 'never', label: 'Never synced' }

    const anyStale = synced.some((item) => item.is_stale)
    const mostRecent = synced.reduce((latest, item) => {
      if (!latest.last_synced_at) return item
      if (!item.last_synced_at) return latest
      return new Date(item.last_synced_at) > new Date(latest.last_synced_at) ? item : latest
    })

    return {
      status: anyStale ? 'stale' : 'fresh',
      label: formatRelativeTime(mostRecent.last_synced_at),
    }
  }

  const canStartDownload =
    selectedSeasons.length > 0 &&
    selectedSources.length > 0 &&
    selectedGameTypes.length > 0 &&
    !startDownload.isPending

  const isAnyQuickLoading =
    quickPreseason.isPending ||
    quickRegular.isPending ||
    quickPlayoffs.isPending ||
    quickExternal.isPending ||
    quickPriorSeason.isPending

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Downloads</h1>
        <p className="text-muted-foreground">
          {syncStatus ? (
            <>Current season: <span className="font-medium">{syncStatus.season_label}</span></>
          ) : (
            'Quick actions to sync NHL data'
          )}
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

      {/* Quick Download Actions */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Play className="h-5 w-5" />
            Quick Download
          </CardTitle>
          <CardDescription>
            One-click downloads for current season. Uses smart delta sync to only fetch new data.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {/* Pre-season */}
            <Button
              variant="outline"
              className="h-auto flex-col items-start p-4 space-y-2"
              onClick={() => quickPreseason.mutate()}
              disabled={isAnyQuickLoading}
            >
              <div className="flex items-center gap-2 w-full">
                <Snowflake className="h-5 w-5 text-cyan-500" />
                <span className="font-semibold">Pre-season</span>
                {quickPreseason.isPending && <Loader2 className="h-4 w-4 animate-spin ml-auto" />}
              </div>
              <div className="text-xs text-muted-foreground text-left w-full">
                {syncLoading ? (
                  <Skeleton className="h-3 w-16" />
                ) : (
                  <>
                    {(() => {
                      const status = getSyncStatusForGameType(1)
                      if (!status) return 'No data'
                      return (
                        <span className="flex items-center gap-1">
                          {status.status === 'fresh' ? (
                            <CheckCircle className="h-3 w-3 text-green-500" />
                          ) : status.status === 'stale' ? (
                            <AlertTriangle className="h-3 w-3 text-yellow-500" />
                          ) : (
                            <Clock className="h-3 w-3 text-muted-foreground" />
                          )}
                          {status.label}
                        </span>
                      )
                    })()}
                  </>
                )}
              </div>
            </Button>

            {/* Regular Season */}
            <Button
              variant="outline"
              className="h-auto flex-col items-start p-4 space-y-2"
              onClick={() => quickRegular.mutate()}
              disabled={isAnyQuickLoading}
            >
              <div className="flex items-center gap-2 w-full">
                <Calendar className="h-5 w-5 text-blue-500" />
                <span className="font-semibold">Regular Season</span>
                {quickRegular.isPending && <Loader2 className="h-4 w-4 animate-spin ml-auto" />}
              </div>
              <div className="text-xs text-muted-foreground text-left w-full">
                {syncLoading ? (
                  <Skeleton className="h-3 w-16" />
                ) : (
                  <>
                    {(() => {
                      const status = getSyncStatusForGameType(2)
                      if (!status) return 'No data'
                      return (
                        <span className="flex items-center gap-1">
                          {status.status === 'fresh' ? (
                            <CheckCircle className="h-3 w-3 text-green-500" />
                          ) : status.status === 'stale' ? (
                            <AlertTriangle className="h-3 w-3 text-yellow-500" />
                          ) : (
                            <Clock className="h-3 w-3 text-muted-foreground" />
                          )}
                          {status.label}
                        </span>
                      )
                    })()}
                  </>
                )}
              </div>
            </Button>

            {/* Playoffs */}
            <Button
              variant="outline"
              className="h-auto flex-col items-start p-4 space-y-2"
              onClick={() => quickPlayoffs.mutate()}
              disabled={isAnyQuickLoading}
            >
              <div className="flex items-center gap-2 w-full">
                <Trophy className="h-5 w-5 text-yellow-500" />
                <span className="font-semibold">Playoffs</span>
                {quickPlayoffs.isPending && <Loader2 className="h-4 w-4 animate-spin ml-auto" />}
              </div>
              <div className="text-xs text-muted-foreground text-left w-full">
                {syncLoading ? (
                  <Skeleton className="h-3 w-16" />
                ) : (
                  <>
                    {(() => {
                      const status = getSyncStatusForGameType(3)
                      if (!status) return 'No data'
                      return (
                        <span className="flex items-center gap-1">
                          {status.status === 'fresh' ? (
                            <CheckCircle className="h-3 w-3 text-green-500" />
                          ) : status.status === 'stale' ? (
                            <AlertTriangle className="h-3 w-3 text-yellow-500" />
                          ) : (
                            <Clock className="h-3 w-3 text-muted-foreground" />
                          )}
                          {status.label}
                        </span>
                      )
                    })()}
                  </>
                )}
              </div>
            </Button>

            {/* External Sources */}
            <Button
              variant="outline"
              className="h-auto flex-col items-start p-4 space-y-2"
              onClick={() => quickExternal.mutate()}
              disabled={isAnyQuickLoading}
            >
              <div className="flex items-center gap-2 w-full">
                <RefreshCw className="h-5 w-5 text-purple-500" />
                <span className="font-semibold">External</span>
                {quickExternal.isPending && <Loader2 className="h-4 w-4 animate-spin ml-auto" />}
              </div>
              <div className="text-xs text-muted-foreground text-left w-full">
                DailyFaceoff & QuantHockey
              </div>
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Prior Season Download */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <History className="h-5 w-5" />
            Prior Season
          </CardTitle>
          <CardDescription>
            Download complete data for a historical season (all game types)
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex gap-4 items-center">
            <Select
              value={selectedPriorSeason}
              onValueChange={setSelectedPriorSeason}
              disabled={seasonsLoading || quickPriorSeason.isPending}
            >
              <SelectTrigger className="w-48">
                <SelectValue placeholder="Select season..." />
              </SelectTrigger>
              <SelectContent>
                {priorSeasons?.map((season) => (
                  <SelectItem key={season.season_id} value={season.season_id.toString()}>
                    {season.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button
              onClick={handlePriorSeasonDownload}
              disabled={!selectedPriorSeason || quickPriorSeason.isPending}
            >
              {quickPriorSeason.isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Starting...
                </>
              ) : (
                <>
                  <Download className="mr-2 h-4 w-4" />
                  Download Full Season
                </>
              )}
            </Button>
          </div>
        </CardContent>
      </Card>

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

      {/* Advanced Mode - Collapsible */}
      <Collapsible open={advancedOpen} onOpenChange={setAdvancedOpen}>
        <Card>
          <CardHeader>
            <CollapsibleTrigger asChild>
              <Button variant="ghost" className="w-full justify-between p-0 h-auto hover:bg-transparent">
                <CardTitle className="flex items-center gap-2">
                  {advancedOpen ? <ChevronDown className="h-5 w-5" /> : <ChevronRight className="h-5 w-5" />}
                  Advanced Mode
                </CardTitle>
                <Badge variant="outline">Granular Control</Badge>
              </Button>
            </CollapsibleTrigger>
            <CardDescription>
              Select specific seasons, sources, and game types for download
            </CardDescription>
          </CardHeader>

          <CollapsibleContent>
            <CardContent className="space-y-6">
              {/* Game Type Selection */}
              <div className="space-y-3">
                <h4 className="font-medium">Game Types</h4>
                <div className="flex flex-wrap gap-6">
                  {GAME_TYPES.map((gameType) => (
                    <div
                      key={gameType.id}
                      className="flex items-center space-x-3"
                    >
                      <Checkbox
                        id={`gametype-${gameType.id}`}
                        checked={selectedGameTypes.includes(gameType.id)}
                        onCheckedChange={() => toggleGameType(gameType.id)}
                      />
                      <div className="grid gap-1.5 leading-none">
                        <label
                          htmlFor={`gametype-${gameType.id}`}
                          className="text-sm font-medium leading-none cursor-pointer"
                        >
                          {gameType.label}
                          {gameType.id === 2 && (
                            <Badge variant="secondary" className="ml-2">Default</Badge>
                          )}
                        </label>
                        <p className="text-xs text-muted-foreground">{gameType.description}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                {/* Season Selection */}
                <div className="space-y-3">
                  <h4 className="font-medium">Seasons</h4>
                  {optionsLoading ? (
                    <div className="space-y-2">
                      <Skeleton className="h-6 w-32" />
                      <Skeleton className="h-6 w-32" />
                    </div>
                  ) : (
                    <div className="space-y-2">
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
                            className="text-sm leading-none cursor-pointer"
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
                </div>

                {/* Source Selection */}
                <div className="space-y-3">
                  <h4 className="font-medium">Data Sources</h4>
                  {optionsLoading ? (
                    <div className="space-y-2">
                      <Skeleton className="h-6 w-40" />
                      <Skeleton className="h-6 w-36" />
                    </div>
                  ) : (
                    <div className="space-y-4">
                      {options?.source_groups.map((group) => {
                        const groupSourceNames = group.sources.map((s) => s.name)
                        const allSelected = groupSourceNames.every((name) =>
                          selectedSources.includes(name)
                        )
                        const someSelected =
                          !allSelected &&
                          groupSourceNames.some((name) => selectedSources.includes(name))

                        return (
                          <div key={group.source_type} className="space-y-1">
                            <div className="flex items-center space-x-3">
                              <Checkbox
                                id={`group-${group.source_type}`}
                                checked={allSelected}
                                data-state={someSelected ? 'indeterminate' : undefined}
                                onCheckedChange={() => selectAllInGroup(group)}
                              />
                              <label
                                htmlFor={`group-${group.source_type}`}
                                className="text-sm font-medium cursor-pointer"
                              >
                                {group.display_name}
                              </label>
                            </div>
                            <div className="ml-6 space-y-1">
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
                                    className="text-xs leading-none cursor-pointer"
                                  >
                                    {source.display_name}
                                  </label>
                                </div>
                              ))}
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  )}
                </div>
              </div>

              {/* Start Download Button */}
              <div className="flex items-center justify-between pt-4 border-t">
                <div className="text-sm text-muted-foreground">
                  {selectedSeasons.length > 0 && selectedSources.length > 0 && selectedGameTypes.length > 0 ? (
                    <>
                      {selectedSeasons.length} season(s) × {selectedSources.length} source(s) ={' '}
                      <span className="font-medium">
                        {selectedSeasons.length * selectedSources.length} batch(es)
                      </span>
                    </>
                  ) : (
                    'Select at least one season, source, and game type'
                  )}
                </div>
                <Button
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
            </CardContent>
          </CollapsibleContent>
        </Card>
      </Collapsible>

      {/* Delete Season Data */}
      <Card className="border-destructive/50">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-destructive">
            <Trash2 className="h-5 w-5" />
            Delete Season Data
          </CardTitle>
          <CardDescription>
            Permanently remove all data for a specific season. This action cannot be undone.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {optionsLoading ? (
            <div className="space-y-2">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          ) : (
            <div className="space-y-3">
              {options?.seasons.map((season) => (
                <div
                  key={season.season_id}
                  className="flex items-center justify-between rounded-lg border p-4"
                >
                  <div>
                    <div className="font-medium">{season.label}</div>
                    <div className="text-sm text-muted-foreground">
                      Season ID: {season.season_id}
                      {season.is_current && (
                        <Badge variant="secondary" className="ml-2">
                          Current
                        </Badge>
                      )}
                    </div>
                  </div>
                  <AlertDialog open={deleteDialogOpen && deletePreview?.season_id === season.season_id} onOpenChange={setDeleteDialogOpen}>
                    <AlertDialogTrigger asChild>
                      <Button
                        variant="destructive"
                        size="sm"
                        onClick={() => handleDeletePreview(season.season_id)}
                        disabled={deleteSeason.isPending}
                      >
                        {deleteSeason.isPending ? (
                          <>
                            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                            Loading...
                          </>
                        ) : (
                          <>
                            <Trash2 className="mr-2 h-4 w-4" />
                            Delete
                          </>
                        )}
                      </Button>
                    </AlertDialogTrigger>
                    <AlertDialogContent>
                      <AlertDialogHeader>
                        <AlertDialogTitle>Delete {season.label} Data?</AlertDialogTitle>
                        <AlertDialogDescription asChild>
                          <div className="space-y-4">
                            <p className="text-destructive font-medium">
                              This will permanently delete all data for the {season.label} season.
                              This action cannot be undone.
                            </p>

                            {deletePreview && (
                              <div className="rounded-lg bg-muted p-4 space-y-2">
                                <p className="font-semibold">Data to be deleted:</p>
                                <ul className="text-sm space-y-1">
                                  {Object.entries(deletePreview.deleted_counts).map(([table, count]) => (
                                    <li key={table} className="flex justify-between">
                                      <span className="text-muted-foreground">{table}:</span>
                                      <span className="font-medium">{count.toLocaleString()} records</span>
                                    </li>
                                  ))}
                                </ul>
                                <div className="pt-2 border-t mt-2">
                                  <div className="flex justify-between font-semibold">
                                    <span>Total:</span>
                                    <span>{deletePreview.total_records_deleted.toLocaleString()} records</span>
                                  </div>
                                </div>
                              </div>
                            )}
                          </div>
                        </AlertDialogDescription>
                      </AlertDialogHeader>
                      <AlertDialogFooter>
                        <AlertDialogCancel onClick={() => setDeletePreview(null)}>
                          Cancel
                        </AlertDialogCancel>
                        <AlertDialogAction
                          onClick={handleDeleteConfirm}
                          className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                        >
                          {deleteSeason.isPending ? (
                            <>
                              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                              Deleting...
                            </>
                          ) : (
                            'Delete Permanently'
                          )}
                        </AlertDialogAction>
                      </AlertDialogFooter>
                    </AlertDialogContent>
                  </AlertDialog>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
