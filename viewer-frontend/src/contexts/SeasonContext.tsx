import { createContext, useContext, useState, useEffect, type ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'

export interface Season {
  season_id: number
  start_year: number
  end_year: number
  is_current: boolean
  label: string
}

interface SeasonsResponse {
  seasons: Season[]
  source_groups: unknown[]
}

interface SeasonContextType {
  seasons: Season[]
  selectedSeason: Season | null
  setSelectedSeason: (season: Season) => void
  isLoading: boolean
}

const SeasonContext = createContext<SeasonContextType | undefined>(undefined)

export function SeasonProvider({ children }: { children: ReactNode }) {
  const [selectedSeason, setSelectedSeasonState] = useState<Season | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['seasons'],
    queryFn: () => api.get<SeasonsResponse>('/downloads/options'),
    staleTime: 10 * 60 * 1000, // 10 minutes
  })

  const seasons = data?.seasons ?? []

  // Initialize with current season or most recent
  useEffect(() => {
    if (seasons.length > 0 && !selectedSeason) {
      const current = seasons.find(s => s.is_current) ?? seasons[0]
      setSelectedSeasonState(current)
    }
  }, [seasons, selectedSeason])

  const setSelectedSeason = (season: Season) => {
    setSelectedSeasonState(season)
    // Persist to localStorage for page refreshes
    localStorage.setItem('nhl-selected-season', String(season.season_id))
  }

  // Restore from localStorage on mount
  useEffect(() => {
    const saved = localStorage.getItem('nhl-selected-season')
    if (saved && seasons.length > 0) {
      const found = seasons.find(s => s.season_id === Number(saved))
      if (found) {
        setSelectedSeasonState(found)
      }
    }
  }, [seasons])

  return (
    <SeasonContext.Provider value={{ seasons, selectedSeason, setSelectedSeason, isLoading }}>
      {children}
    </SeasonContext.Provider>
  )
}

export function useSeason() {
  const context = useContext(SeasonContext)
  if (context === undefined) {
    throw new Error('useSeason must be used within a SeasonProvider')
  }
  return context
}
