import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

export function Players() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Players</h1>
        <p className="text-muted-foreground">
          Browse and search NHL players
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Player Explorer</CardTitle>
          <CardDescription>
            Search and filter players by name, team, or position
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex h-[400px] items-center justify-center text-muted-foreground">
            <p>Waiting for Entity API (#44) and Data Explorer (#48)</p>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
