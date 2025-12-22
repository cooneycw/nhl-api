import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Activity, Download, Fuel, Calendar, Shield, Users, CheckCircle, HelpCircle, ExternalLink, Keyboard, Moon, Sun } from 'lucide-react'

interface FeatureCardProps {
  icon: React.ReactNode
  title: string
  description: string
  tips?: string[]
}

function FeatureCard({ icon, title, description, tips }: FeatureCardProps) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center gap-2">
          {icon}
          <CardTitle className="text-lg">{title}</CardTitle>
        </div>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      {tips && tips.length > 0 && (
        <CardContent>
          <ul className="list-disc list-inside text-sm text-muted-foreground space-y-1">
            {tips.map((tip, index) => (
              <li key={index}>{tip}</li>
            ))}
          </ul>
        </CardContent>
      )}
    </Card>
  )
}

export function Help() {
  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold flex items-center gap-2">
          <HelpCircle className="h-8 w-8" />
          Help & Documentation
        </h1>
        <p className="text-muted-foreground mt-2">
          Learn how to use the NHL Data Viewer to explore, download, and validate NHL data.
        </p>
      </div>

      {/* Quick Start */}
      <section>
        <h2 className="text-xl font-semibold mb-4">Quick Start</h2>
        <Card>
          <CardContent className="pt-6">
            <ol className="list-decimal list-inside space-y-2 text-sm">
              <li><strong>Check Coverage</strong> - Visit the Coverage page to see what data is available</li>
              <li><strong>Download Data</strong> - Use the Downloads page to fetch new data from NHL APIs</li>
              <li><strong>Explore</strong> - Browse Players, Teams, and Games once data is downloaded</li>
              <li><strong>Validate</strong> - Use Validation to check data integrity across sources</li>
            </ol>
          </CardContent>
        </Card>
      </section>

      {/* Page Guides */}
      <section>
        <h2 className="text-xl font-semibold mb-4">Page Guide</h2>
        <div className="grid gap-4 md:grid-cols-2">
          <FeatureCard
            icon={<Activity className="h-5 w-5 text-blue-500" />}
            title="Dashboard"
            description="Monitor system health and download activity at a glance."
            tips={[
              'Health cards show database connectivity',
              'Source grid displays status of each data type',
              'Progress chart shows 24-hour activity',
              'Click retry buttons to re-attempt failed downloads'
            ]}
          />
          <FeatureCard
            icon={<Download className="h-5 w-5 text-green-500" />}
            title="Downloads"
            description="Trigger new data downloads from NHL APIs."
            tips={[
              'Select multiple seasons with checkboxes',
              'Choose data sources (Schedule, Boxscore, etc.)',
              'Monitor progress with real-time updates',
              'Cancel active downloads if needed'
            ]}
          />
          <FeatureCard
            icon={<Fuel className="h-5 w-5 text-amber-500" />}
            title="Coverage"
            description="View data completeness with visual gauges."
            tips={[
              'Gas tank gauges show percentage complete',
              'Click categories to drill down',
              'Switch seasons to compare coverage',
              'Red/yellow/green indicates status'
            ]}
          />
          <FeatureCard
            icon={<Calendar className="h-5 w-5 text-purple-500" />}
            title="Games"
            description="Browse all NHL games with filtering options."
            tips={[
              'Filter by season, team, date range',
              'Click game for detailed view',
              'Game detail shows events, stats, shifts',
              'Use tabs to switch between data views'
            ]}
          />
          <FeatureCard
            icon={<Shield className="h-5 w-5 text-red-500" />}
            title="Teams"
            description="Explore teams organized by division."
            tips={[
              'Teams grouped by conference and division',
              'Click team for roster and schedule',
              'Player list shows current roster',
              'Recent games displayed with results'
            ]}
          />
          <FeatureCard
            icon={<Users className="h-5 w-5 text-cyan-500" />}
            title="Players"
            description="Search and browse all NHL players."
            tips={[
              'Search by name (partial matches work)',
              'Filter by position (C, LW, RW, D, G)',
              'Filter by current team',
              'Click player for game log and stats'
            ]}
          />
          <FeatureCard
            icon={<CheckCircle className="h-5 w-5 text-emerald-500" />}
            title="Validation"
            description="Verify data integrity across sources."
            tips={[
              'Compare JSON API vs HTML reports',
              'Identify missing or inconsistent data',
              'Drill down to per-game reconciliation',
              'Field-by-field comparison available'
            ]}
          />
        </div>
      </section>

      {/* Features */}
      <section>
        <h2 className="text-xl font-semibold mb-4">Features</h2>
        <div className="grid gap-4 md:grid-cols-2">
          <Card>
            <CardHeader className="pb-3">
              <div className="flex items-center gap-2">
                <Sun className="h-5 w-5" />
                <Moon className="h-5 w-5" />
                <CardTitle className="text-lg">Dark Mode</CardTitle>
              </div>
              <CardDescription>
                Toggle between light, dark, and system themes using the button in the header.
                Your preference is saved automatically.
              </CardDescription>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader className="pb-3">
              <div className="flex items-center gap-2">
                <Keyboard className="h-5 w-5" />
                <CardTitle className="text-lg">Keyboard Shortcuts</CardTitle>
              </div>
              <CardDescription>
                Press <kbd className="px-1.5 py-0.5 bg-muted rounded text-xs">/</kbd> to focus search on list pages.
                Press <kbd className="px-1.5 py-0.5 bg-muted rounded text-xs">Esc</kbd> to close dialogs.
              </CardDescription>
            </CardHeader>
          </Card>
        </div>
      </section>

      {/* API Documentation */}
      <section>
        <h2 className="text-xl font-semibold mb-4">API Documentation</h2>
        <Card>
          <CardContent className="pt-6">
            <p className="text-sm text-muted-foreground mb-4">
              The backend API provides programmatic access to all NHL data. Interactive documentation is available:
            </p>
            <div className="flex gap-4">
              <a
                href="http://localhost:8000/docs"
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1 text-sm text-blue-500 hover:underline"
              >
                Swagger UI <ExternalLink className="h-3 w-3" />
              </a>
              <a
                href="http://localhost:8000/redoc"
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1 text-sm text-blue-500 hover:underline"
              >
                ReDoc <ExternalLink className="h-3 w-3" />
              </a>
            </div>
          </CardContent>
        </Card>
      </section>

      {/* Troubleshooting */}
      <section>
        <h2 className="text-xl font-semibold mb-4">Troubleshooting</h2>
        <Card>
          <CardContent className="pt-6 space-y-4">
            <div>
              <h3 className="font-medium">Health cards show "Offline"</h3>
              <p className="text-sm text-muted-foreground">
                The database may be unavailable. Check that credentials are configured in <code className="bg-muted px-1 rounded">.env</code> and the database is running.
              </p>
            </div>
            <div>
              <h3 className="font-medium">Empty data on pages</h3>
              <p className="text-sm text-muted-foreground">
                Data must be downloaded first. Go to the Downloads page, select seasons and sources, then start a download.
              </p>
            </div>
            <div>
              <h3 className="font-medium">Downloads stuck or failing</h3>
              <p className="text-sm text-muted-foreground">
                Check the Dashboard for failed downloads and use the retry button. Rate limiting may cause temporary failures.
              </p>
            </div>
          </CardContent>
        </Card>
      </section>
    </div>
  )
}
