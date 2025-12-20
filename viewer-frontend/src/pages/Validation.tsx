import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

export function Validation() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Validation</h1>
        <p className="text-muted-foreground">
          View data quality scores and discrepancies
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Validation Results</CardTitle>
          <CardDescription>
            Quality scores and cross-source data validation
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex h-[400px] items-center justify-center text-muted-foreground">
            <p>Waiting for Validation API (#45) and Validation Viewer (#49)</p>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
