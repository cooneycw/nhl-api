import { Link } from 'react-router-dom'
import { cn } from '@/lib/utils'

interface GasTankGaugeProps {
  label: string
  actual: number
  expected: number
  percentage: number | null
  linkPath: string
  compact?: boolean
}

function getGaugeColor(percentage: number | null): string {
  if (percentage === null) return 'bg-gray-400'
  if (percentage >= 95) return 'bg-green-500'
  if (percentage >= 75) return 'bg-emerald-400'
  if (percentage >= 50) return 'bg-yellow-400'
  if (percentage >= 25) return 'bg-orange-400'
  return 'bg-red-400'
}

function getGaugeTextColor(percentage: number | null): string {
  if (percentage === null) return 'text-gray-600'
  if (percentage >= 95) return 'text-green-700'
  if (percentage >= 75) return 'text-emerald-700'
  if (percentage >= 50) return 'text-yellow-700'
  if (percentage >= 25) return 'text-orange-700'
  return 'text-red-700'
}

export function GasTankGauge({
  label,
  actual,
  expected,
  percentage,
  linkPath,
  compact = false,
}: GasTankGaugeProps) {
  const displayPercentage = percentage !== null ? percentage : 0
  const gaugeColor = getGaugeColor(percentage)
  const textColor = getGaugeTextColor(percentage)

  return (
    <Link
      to={linkPath}
      className={cn(
        'block rounded-lg border bg-card p-3 transition-all hover:shadow-md hover:border-primary/50',
        compact ? 'p-2' : 'p-3'
      )}
    >
      <div className="flex items-center justify-between mb-2">
        <span className={cn('font-medium', compact ? 'text-xs' : 'text-sm')}>
          {label}
        </span>
        <span className={cn('font-bold', textColor, compact ? 'text-xs' : 'text-sm')}>
          {percentage !== null ? `${percentage.toFixed(1)}%` : 'N/A'}
        </span>
      </div>

      {/* Progress bar container */}
      <div className="relative h-3 w-full rounded-full bg-muted overflow-hidden">
        {/* Fill */}
        <div
          className={cn('h-full rounded-full transition-all duration-500', gaugeColor)}
          style={{ width: `${Math.min(displayPercentage, 100)}%` }}
        />
      </div>

      {/* Count display */}
      <div className={cn('mt-1 text-muted-foreground', compact ? 'text-xs' : 'text-xs')}>
        {actual.toLocaleString()} / {expected.toLocaleString()}
      </div>
    </Link>
  )
}

// Compact version for use in tables or smaller spaces
export function GasTankGaugeInline({
  percentage,
}: Pick<GasTankGaugeProps, 'percentage'>) {
  const displayPercentage = percentage !== null ? percentage : 0
  const gaugeColor = getGaugeColor(percentage)
  const textColor = getGaugeTextColor(percentage)

  return (
    <div className="flex items-center gap-2 min-w-[120px]">
      <div className="relative h-2 flex-1 rounded-full bg-muted overflow-hidden">
        <div
          className={cn('h-full rounded-full', gaugeColor)}
          style={{ width: `${Math.min(displayPercentage, 100)}%` }}
        />
      </div>
      <span className={cn('text-xs font-medium tabular-nums', textColor)}>
        {percentage !== null ? `${percentage.toFixed(0)}%` : '-'}
      </span>
    </div>
  )
}
