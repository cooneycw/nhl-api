import { Link } from 'react-router-dom'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { useTeams } from '@/hooks/useTeams'

export function Teams() {
  const { data, isLoading, error } = useTeams({ active_only: true })

  if (isLoading) {
    return (
      <div className="space-y-6">
        <h1 className="text-3xl font-bold">Teams</h1>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <Card key={i}>
              <CardHeader>
                <Skeleton className="h-6 w-32" />
              </CardHeader>
              <CardContent>
                <Skeleton className="h-4 w-24" />
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="space-y-6">
        <h1 className="text-3xl font-bold">Teams</h1>
        <Card className="border-destructive">
          <CardContent className="pt-6">
            <p className="text-destructive">Error loading teams: {error.message}</p>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Teams</h1>
        <span className="text-muted-foreground">{data?.total_teams} teams</span>
      </div>

      {data?.divisions.map((division) => (
        <div key={division.division_id} className="space-y-4">
          <h2 className="text-xl font-semibold">
            {division.division_name}
            {division.conference_name && (
              <span className="text-muted-foreground ml-2 text-base font-normal">
                ({division.conference_name})
              </span>
            )}
          </h2>

          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            {division.teams.map((team) => (
              <Link key={team.team_id} to={`/teams/${team.team_id}`}>
                <Card className="hover:bg-accent transition-colors cursor-pointer">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-lg flex items-center gap-2">
                      <span className="font-mono text-muted-foreground">
                        {team.abbreviation}
                      </span>
                      {team.location_name}
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-sm text-muted-foreground">{team.team_name}</p>
                  </CardContent>
                </Card>
              </Link>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}
