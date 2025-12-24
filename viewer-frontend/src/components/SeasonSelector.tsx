import { CalendarDays, ChevronDown } from 'lucide-react'
import { useSeason } from '@/contexts/SeasonContext'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'

export function SeasonSelector() {
  const { seasons, selectedSeason, setSelectedSeason, isLoading } = useSeason()

  if (isLoading) {
    return <Skeleton className="h-9 w-32" />
  }

  if (!selectedSeason) {
    return null
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" size="sm" className="gap-2">
          <CalendarDays className="h-4 w-4" />
          {selectedSeason.label}
          <ChevronDown className="h-4 w-4 opacity-50" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        {seasons.map((season) => (
          <DropdownMenuItem
            key={season.season_id}
            onClick={() => setSelectedSeason(season)}
            className={selectedSeason.season_id === season.season_id ? 'bg-accent' : ''}
          >
            {season.label}
            {season.is_current && (
              <span className="ml-2 text-xs text-muted-foreground">(current)</span>
            )}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
