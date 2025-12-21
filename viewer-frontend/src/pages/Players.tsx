import { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Button } from '@/components/ui/button'
import { Search, ChevronLeft, ChevronRight } from 'lucide-react'
import { usePlayers, type PlayerFilters } from '@/hooks/usePlayers'
import { PlayerLink, TeamLink } from '@/components/EntityLinks'

type PositionFilter = PlayerFilters['position'] | 'all'

const POSITION_OPTIONS: { value: PositionFilter; label: string }[] = [
  { value: 'all', label: 'All Positions' },
  { value: 'C', label: 'Center' },
  { value: 'LW', label: 'Left Wing' },
  { value: 'RW', label: 'Right Wing' },
  { value: 'D', label: 'Defenseman' },
  { value: 'G', label: 'Goalie' },
]

export function Players() {
  const [search, setSearch] = useState('')
  const [position, setPosition] = useState<PositionFilter>('all')
  const [page, setPage] = useState(1)
  const perPage = 25

  const { data, isLoading, error } = usePlayers({
    search: search || undefined,
    position: position !== 'all' ? position : undefined,
    page,
    per_page: perPage,
  })

  const handleSearch = (value: string) => {
    setSearch(value)
    setPage(1) // Reset to first page on new search
  }

  const handlePositionChange = (value: PositionFilter) => {
    setPosition(value)
    setPage(1) // Reset to first page on filter change
  }

  if (error) {
    return (
      <div className="space-y-6">
        <h1 className="text-3xl font-bold">Players</h1>
        <Card className="border-destructive">
          <CardContent className="pt-6">
            <p className="text-destructive">Error loading players: {error.message}</p>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Players</h1>
          <p className="text-muted-foreground">Browse and search NHL players</p>
        </div>
        {data && (
          <span className="text-muted-foreground">
            {data.pagination.total_items.toLocaleString()} players
          </span>
        )}
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Search & Filter</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col gap-4 md:flex-row">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search by name..."
                value={search}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => handleSearch(e.target.value)}
                className="pl-9"
              />
            </div>
            <Select value={position} onValueChange={(value) => handlePositionChange(value as PositionFilter)}>
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="Position" />
              </SelectTrigger>
              <SelectContent>
                {POSITION_OPTIONS.map((opt) => (
                  <SelectItem key={opt.value ?? 'all'} value={opt.value ?? 'all'}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="pt-6">
          {isLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 10 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : data?.players.length === 0 ? (
            <p className="text-center text-muted-foreground py-8">
              No players found matching your criteria
            </p>
          ) : (
            <>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Player</TableHead>
                    <TableHead>Position</TableHead>
                    <TableHead>Team</TableHead>
                    <TableHead className="text-right">Age</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data?.players.map((player) => (
                    <TableRow key={player.player_id}>
                      <TableCell>
                        <div className="flex items-center gap-3">
                          {player.headshot_url && (
                            <img
                              src={player.headshot_url}
                              alt={player.full_name}
                              className="h-10 w-10 rounded-full object-cover"
                            />
                          )}
                          <div>
                            <PlayerLink
                              playerId={player.player_id}
                              playerName={player.full_name}
                            />
                            {player.sweater_number && (
                              <span className="ml-2 text-sm text-muted-foreground font-mono">
                                #{player.sweater_number}
                              </span>
                            )}
                          </div>
                        </div>
                      </TableCell>
                      <TableCell>{player.primary_position}</TableCell>
                      <TableCell>
                        {player.team_name && player.current_team_id ? (
                          <TeamLink teamId={player.current_team_id} teamName={player.team_name} />
                        ) : (
                          <span className="text-muted-foreground">-</span>
                        )}
                      </TableCell>
                      <TableCell className="text-right">{player.age || '-'}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>

              {/* Pagination */}
              {data && data.pagination.total_pages > 1 && (
                <div className="flex items-center justify-between mt-4 pt-4 border-t">
                  <span className="text-sm text-muted-foreground">
                    Page {data.pagination.page} of {data.pagination.total_pages}
                  </span>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setPage((p) => Math.max(1, p - 1))}
                      disabled={page <= 1}
                    >
                      <ChevronLeft className="h-4 w-4" />
                      Previous
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setPage((p) => Math.min(data.pagination.total_pages, p + 1))}
                      disabled={page >= data.pagination.total_pages}
                    >
                      Next
                      <ChevronRight className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
