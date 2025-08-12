import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { AlertTriangle, Database, HardDrive, Cpu } from 'lucide-react';
import { adminApi } from '../lib/api';

export function Dashboard() {
  const { data: overview, isLoading, error } = useQuery({
    queryKey: ['overview'],
    queryFn: adminApi.getOverview,
  });

  if (isLoading) {
    return (
      <div className="space-y-6">
        <h1 className="text-3xl font-bold">Dashboard</h1>
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Card key={i}>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-medium">
                  <div className="h-4 bg-muted animate-pulse rounded" />
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="h-8 bg-muted animate-pulse rounded mb-2" />
                <div className="h-4 bg-muted animate-pulse rounded w-2/3" />
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6">
        <h1 className="text-3xl font-bold">Dashboard</h1>
        <Card className="border-destructive">
          <CardContent className="pt-6">
            <div className="flex items-center space-x-2 text-destructive">
              <AlertTriangle className="h-5 w-5" />
              <p>Failed to load system overview</p>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  const needsSchemaUpdate = overview?.schema?.current !== overview?.schema?.latest;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Dashboard</h1>
        {needsSchemaUpdate && (
          <Button variant="outline" className="border-amber-500 text-amber-600">
            <AlertTriangle className="h-4 w-4 mr-2" />
            Schema Update Available
          </Button>
        )}
      </div>

      {needsSchemaUpdate && (
        <Card className="border-amber-200 bg-amber-50 dark:border-amber-800 dark:bg-amber-950">
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-3">
                <AlertTriangle className="h-5 w-5 text-amber-600" />
                <div>
                  <p className="font-medium text-amber-800 dark:text-amber-200">
                    Schema update needed
                  </p>
                  <p className="text-sm text-amber-700 dark:text-amber-300">
                    Current: {overview?.schema?.current} → Latest: {overview?.schema?.latest}
                  </p>
                </div>
              </div>
              <Button size="sm" className="bg-amber-600 hover:bg-amber-700">
                Update Now
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
        {/* Database Status */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-3">
            <CardTitle className="text-sm font-medium">Database</CardTitle>
            <Database className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-2xl font-bold">{overview?.database?.name}</p>
                <p className="text-xs text-muted-foreground mt-1">
                  {overview?.database?.status === 'ok' ? 'Connected' : 'Error'}
                </p>
              </div>
              <Badge variant={overview?.database?.status === 'ok' ? 'default' : 'destructive'}>
                {overview?.database?.status}
              </Badge>
            </div>
          </CardContent>
        </Card>

        {/* Schema Version */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-3">
            <CardTitle className="text-sm font-medium">Schema</CardTitle>
            <HardDrive className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-2xl font-bold">
                  {overview?.schema?.current}/{overview?.schema?.latest}
                </p>
                <p className="text-xs text-muted-foreground mt-1">
                  {needsSchemaUpdate ? 'Update available' : 'Up to date'}
                </p>
              </div>
              <Badge variant={needsSchemaUpdate ? 'secondary' : 'default'}>
                {needsSchemaUpdate ? 'pending' : 'current'}
              </Badge>
            </div>
          </CardContent>
        </Card>

        {/* Vector Dimension */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-3">
            <CardTitle className="text-sm font-medium">Vector Index</CardTitle>
            <Cpu className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-2xl font-bold">{overview?.vector?.dimension}</p>
                <p className="text-xs text-muted-foreground mt-1">Dimensions</p>
              </div>
              <Badge variant={overview?.vector?.status === 'ok' ? 'default' : 'destructive'}>
                {overview?.vector?.status}
              </Badge>
            </div>
          </CardContent>
        </Card>

        {/* System Status */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-3">
            <CardTitle className="text-sm font-medium">System</CardTitle>
            <div className={`h-3 w-3 rounded-full ${
              overview?.system?.status === 'ok' ? 'bg-green-500' :
              overview?.system?.status === 'degraded' ? 'bg-yellow-500' :
              'bg-red-500'
            }`} />
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-2xl font-bold capitalize">
                  {overview?.system?.status}
                </p>
                <p className="text-xs text-muted-foreground mt-1">Overall health</p>
              </div>
              <Badge 
                variant={
                  overview?.system?.status === 'ok' ? 'default' :
                  overview?.system?.status === 'degraded' ? 'secondary' :
                  'destructive'
                }
              >
                {overview?.system?.status}
              </Badge>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* System Information */}
      <Card>
        <CardHeader>
          <CardTitle>System Information</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 md:grid-cols-3">
            <div>
              <p className="text-sm font-medium text-muted-foreground">Database Name</p>
              <p className="text-lg font-semibold">{overview?.database?.name}</p>
            </div>
            <div>
              <p className="text-sm font-medium text-muted-foreground">Vector Dimensions</p>
              <p className="text-lg font-semibold">{overview?.vector?.dimension}</p>
            </div>
            <div>
              <p className="text-sm font-medium text-muted-foreground">Schema Version</p>
              <p className="text-lg font-semibold">
                {overview?.schema?.current} / {overview?.schema?.latest}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}