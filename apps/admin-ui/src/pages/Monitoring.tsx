
import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { ScrollArea } from '../components/ui/scroll-area';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, AreaChart, Area } from 'recharts';
import { Activity, Cpu, HardDrive, Database, Zap, Clock, RefreshCw } from 'lucide-react';
import { adminApi } from '../lib/api';

export function Monitoring() {
  const [logLevel, setLogLevel] = useState('all');
  const [metricsHistory, setMetricsHistory] = useState<any[]>([]);

  const { data: metrics } = useQuery({
    queryKey: ['metrics'],
    queryFn: adminApi.getMetrics,
    refetchInterval: 5000, // Refresh every 5 seconds
  });

  const { data: logs, isLoading: logsLoading } = useQuery({
    queryKey: ['logs', logLevel],
    queryFn: () => adminApi.getLogs({ level: logLevel === 'all' ? undefined : logLevel }),
    refetchInterval: 10000, // Refresh every 10 seconds
  });

  // Collect metrics history for charts
  useEffect(() => {
    if (metrics) {
      const timestamp = new Date().toLocaleTimeString();
      setMetricsHistory(prev => {
        const newHistory = [...prev, { ...metrics, timestamp }].slice(-20); // Keep last 20 data points
        return newHistory;
      });
    }
  }, [metrics]);

  const getLogLevelBadge = (level: string) => {
    switch (level) {
      case 'error': return <Badge variant="destructive">Hiba</Badge>;
      case 'warning': return <Badge variant="secondary">Figyelmeztetés</Badge>;
      case 'info': return <Badge variant="default">Info</Badge>;
      case 'debug': return <Badge variant="outline">Debug</Badge>;
      default: return <Badge variant="outline">{level}</Badge>;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'ok': return 'text-green-600';
      case 'error': return 'text-red-600';
      default: return 'text-yellow-600';
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Monitoring</h1>
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <RefreshCw className="h-4 w-4" />
          Automatikus frissítés: 5s
        </div>
      </div>

      {/* Real-time Metrics */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium flex items-center">
              <Cpu className="h-4 w-4 mr-2" />
              CPU
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{metrics?.cpu || 0}%</div>
            <p className="text-xs text-muted-foreground">használat</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium flex items-center">
              <HardDrive className="h-4 w-4 mr-2" />
              Memória
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{metrics?.memory || 0}%</div>
            <p className="text-xs text-muted-foreground">használat</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium flex items-center">
              <Clock className="h-4 w-4 mr-2" />
              Válaszidő
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{metrics?.latency_ms || 0}ms</div>
            <p className="text-xs text-muted-foreground">átlag</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium flex items-center">
              <Zap className="h-4 w-4 mr-2" />
              QPS
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{metrics?.rag?.qps || 0}</div>
            <p className="text-xs text-muted-foreground">lekérdezés/s</p>
          </CardContent>
        </Card>
      </div>

      {/* Service Status */}
      <Card>
        <CardHeader>
          <CardTitle>Szolgáltatás állapot</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 md:grid-cols-3">
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium flex items-center">
                  <Database className="h-4 w-4 mr-2" />
                  Adatbázis
                </span>
                <span className={`text-sm ${getStatusColor(metrics?.db?.status || 'error')}`}>
                  {metrics?.db?.status === 'ok' ? 'OK' : 'Hiba'}
                </span>
              </div>
              <div className="text-xs text-muted-foreground">
                {metrics?.info?.db_name || 'N/A'}
              </div>
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium flex items-center">
                  <Activity className="h-4 w-4 mr-2" />
                  Vektor keresés
                </span>
                <span className={`text-sm ${getStatusColor(metrics?.vector?.status || 'error')}`}>
                  {metrics?.vector?.status === 'ok' ? 'OK' : 'Hiba'}
                </span>
              </div>
              <div className="text-xs text-muted-foreground">
                {metrics?.rag?.vector_ms || 0}ms átlag
              </div>
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium">Vektor dimenzió</span>
                <span className="text-sm">{metrics?.info?.vector_dim || 0}</span>
              </div>
              <div className="text-xs text-muted-foreground">
                Schema: {metrics?.info?.schema?.current || 0}/{metrics?.info?.schema?.latest || 0}
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Performance Charts */}
      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>CPU & Memória használat</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-80">
              {metricsHistory.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={metricsHistory}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="timestamp" />
                    <YAxis domain={[0, 100]} />
                    <Tooltip />
                    <Line 
                      type="monotone" 
                      dataKey="cpu" 
                      stroke="#8884d8" 
                      strokeWidth={2}
                      name="CPU %"
                    />
                    <Line 
                      type="monotone" 
                      dataKey="memory" 
                      stroke="#82ca9d" 
                      strokeWidth={2}
                      name="Memória %"
                    />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex items-center justify-center h-full text-muted-foreground">
                  Adatgyűjtés folyamatban...
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Válaszidő</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-80">
              {metricsHistory.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={metricsHistory}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="timestamp" />
                    <YAxis />
                    <Tooltip />
                    <Area 
                      type="monotone" 
                      dataKey="latency_ms" 
                      stroke="#8884d8" 
                      fill="#8884d8" 
                      fillOpacity={0.6}
                      name="Válaszidő (ms)"
                    />
                  </AreaChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex items-center justify-center h-full text-muted-foreground">
                  Adatgyűjtés folyamatban...
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* System Logs */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <span>Rendszer logok</span>
            <div className="flex items-center gap-2">
              <Select value={logLevel} onValueChange={setLogLevel}>
                <SelectTrigger className="w-40">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Összes szint</SelectItem>
                  <SelectItem value="error">Csak hibák</SelectItem>
                  <SelectItem value="warning">Figyelmeztetések</SelectItem>
                  <SelectItem value="info">Információk</SelectItem>
                  <SelectItem value="debug">Debug</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <ScrollArea className="h-96">
            {logsLoading ? (
              <div className="flex items-center justify-center h-32">
                <RefreshCw className="h-6 w-6 animate-spin" />
              </div>
            ) : logs?.items && logs.items.length > 0 ? (
              <div className="space-y-2">
                {logs.items.map((log, index) => (
                  <div key={index} className="border-b pb-2">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        {getLogLevelBadge(log.level)}
                        <span className="text-xs text-muted-foreground font-mono">
                          {log.ts}
                        </span>
                      </div>
                    </div>
                    <p className="text-sm mt-1 font-mono">{log.msg}</p>
                  </div>
                ))}
              </div>
            ) : (
              <div className="flex items-center justify-center h-32 text-muted-foreground">
                Nincsenek logok
              </div>
            )}
          </ScrollArea>
        </CardContent>
      </Card>
    </div>
  );
}