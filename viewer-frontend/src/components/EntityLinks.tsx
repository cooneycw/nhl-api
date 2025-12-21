/**
 * Reusable clickable link components for navigating between entities.
 *
 * These components provide consistent styling and navigation for:
 * - Players: Navigate to player detail page
 * - Teams: Navigate to team detail page
 * - Games: Navigate to game detail page
 */

import { Link } from 'react-router-dom'
import { cn } from '@/lib/utils'

interface PlayerLinkProps {
  playerId: number
  playerName: string
  /** Optional team abbreviation to display */
  teamAbbr?: string
  /** Optional sweater number to display */
  sweaterNumber?: number
  /** Optional CSS class */
  className?: string
  /** Show as compact (name only) or full (with team/number) */
  compact?: boolean
}

/**
 * Clickable player name that navigates to player detail page.
 *
 * @example
 * <PlayerLink playerId={8478402} playerName="Nathan MacKinnon" />
 * <PlayerLink playerId={8478402} playerName="Nathan MacKinnon" sweaterNumber={29} teamAbbr="COL" />
 */
export function PlayerLink({
  playerId,
  playerName,
  teamAbbr,
  sweaterNumber,
  className,
  compact = true,
}: PlayerLinkProps) {
  const displayText = compact
    ? playerName
    : sweaterNumber
      ? `#${sweaterNumber} ${playerName}${teamAbbr ? ` (${teamAbbr})` : ''}`
      : `${playerName}${teamAbbr ? ` (${teamAbbr})` : ''}`

  return (
    <Link
      to={`/players/${playerId}`}
      className={cn(
        'text-primary hover:text-primary/80 hover:underline font-medium transition-colors',
        className
      )}
    >
      {displayText}
    </Link>
  )
}

interface TeamLinkProps {
  teamId: number
  /** Team name or abbreviation to display */
  teamName: string
  /** Optional abbreviation (if teamName is full name) */
  abbreviation?: string
  /** Optional CSS class */
  className?: string
  /** Display mode: 'name' | 'abbr' | 'full' (name + abbr) */
  display?: 'name' | 'abbr' | 'full'
}

/**
 * Clickable team name that navigates to team detail page.
 *
 * @example
 * <TeamLink teamId={21} teamName="Colorado Avalanche" />
 * <TeamLink teamId={21} teamName="COL" display="abbr" />
 */
export function TeamLink({
  teamId,
  teamName,
  abbreviation,
  className,
  display = 'name',
}: TeamLinkProps) {
  const displayText =
    display === 'abbr'
      ? abbreviation || teamName
      : display === 'full' && abbreviation
        ? `${teamName} (${abbreviation})`
        : teamName

  return (
    <Link
      to={`/teams/${teamId}`}
      className={cn(
        'text-primary hover:text-primary/80 hover:underline font-medium transition-colors',
        className
      )}
    >
      {displayText}
    </Link>
  )
}

interface GameLinkProps {
  gameId: number
  /** What to display for the game link */
  children: React.ReactNode
  /** Optional CSS class */
  className?: string
}

/**
 * Clickable game reference that navigates to game detail page.
 *
 * @example
 * <GameLink gameId={2024020500}>COL @ VAN - Dec 15</GameLink>
 * <GameLink gameId={2024020500}>View Game</GameLink>
 */
export function GameLink({ gameId, children, className }: GameLinkProps) {
  return (
    <Link
      to={`/games/${gameId}`}
      className={cn(
        'text-primary hover:text-primary/80 hover:underline font-medium transition-colors',
        className
      )}
    >
      {children}
    </Link>
  )
}

interface GameScoreLinkProps {
  gameId: number
  homeTeamId: number
  homeTeamAbbr: string
  homeScore: number | null
  awayTeamId: number
  awayTeamAbbr: string
  awayScore: number | null
  /** Optional CSS class for container */
  className?: string
  /** Show final indicator for completed games */
  isFinal?: boolean
}

/**
 * Combined game score display with clickable team names.
 * Shows: "COL 4 @ VAN 2" with both team names clickable.
 *
 * @example
 * <GameScoreLink
 *   gameId={2024020500}
 *   homeTeamId={23}
 *   homeTeamAbbr="VAN"
 *   homeScore={2}
 *   awayTeamId={21}
 *   awayTeamAbbr="COL"
 *   awayScore={4}
 * />
 */
export function GameScoreLink({
  gameId,
  homeTeamId,
  homeTeamAbbr,
  homeScore,
  awayTeamId,
  awayTeamAbbr,
  awayScore,
  className,
  isFinal = false,
}: GameScoreLinkProps) {
  return (
    <div className={cn('flex items-center gap-2 text-sm', className)}>
      <TeamLink teamId={awayTeamId} teamName={awayTeamAbbr} display="abbr" />
      <span className="font-mono">
        {awayScore ?? '-'} @ {homeScore ?? '-'}
      </span>
      <TeamLink teamId={homeTeamId} teamName={homeTeamAbbr} display="abbr" />
      {isFinal && <span className="text-muted-foreground text-xs">(Final)</span>}
      <GameLink gameId={gameId} className="ml-2 text-xs">
        Details →
      </GameLink>
    </div>
  )
}

/**
 * Format a date for display in game context.
 */
export function formatGameDate(date: string | Date): string {
  const d = typeof date === 'string' ? new Date(date) : date
  return d.toLocaleDateString('en-US', {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
  })
}

/**
 * Format time on ice from seconds to MM:SS display.
 */
export function formatTOI(seconds: number): string {
  const mins = Math.floor(seconds / 60)
  const secs = seconds % 60
  return `${mins}:${secs.toString().padStart(2, '0')}`
}
