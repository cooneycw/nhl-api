import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

export function Games() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Games</h1>
        <p className="text-muted-foreground">
          Browse NHL games by date and team
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Game Explorer</CardTitle>
          <CardDescription>
            Filter games by date range, team, or season
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
