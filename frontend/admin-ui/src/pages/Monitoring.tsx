
import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { ScrollArea } from '../components/ui/scroll-area';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, AreaChart, Area } from 'recharts';
import { Activity, Cpu, HardDrive, Database, Zap, Clock, RefreshCw } from 'lucide-react';
import { adminApi } from '../lib/api';

export function Monitoring() {
  const { t } = useTranslation();
  const [logLevel, setLogLevel] = useState('all');
  const [selectedContainer, setSelectedContainer] = useState('bridge');
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamLogs, setStreamLogs] = useState<any[]>([]);
  const [metricsHistory, setMetricsHistory] = useState<any[]>([]);
  const [currentEventSource, setCurrentEventSource] = useState<EventSource | null>(null);

  const { data: metrics } = useQuery({
    queryKey: ['metrics'],
    queryFn: adminApi.getMetrics,
    refetchInterval: 5000, // Refresh every 5 seconds
  });

  const { data: logs, isLoading: logsLoading } = useQuery({
    queryKey: ['logs', logLevel, selectedContainer],
    queryFn: () => adminApi.getLogs({ level: logLevel === 'all' ? undefined : logLevel, container: selectedContainer }),
    refetchInterval: isStreaming ? false : 10000, // Disable polling when streaming
    enabled: !isStreaming, // Don't fetch when streaming
  });

  // Container options with emojis
  const containerOptions = [
    { value: 'bridge', label: '🌉 HA-RAG Bridge', description: 'Main application server' },
    { value: 'litellm', label: '🤖 LiteLLM Proxy', description: 'LLM API gateway' },
    { value: 'homeassistant', label: '🏠 Home Assistant', description: 'Smart home platform' },
    { value: 'arangodb', label: '🗄️ ArangoDB', description: 'Graph database' }
  ];

  // Close current stream
  const closeCurrentStream = () => {
    if (currentEventSource) {
      currentEventSource.close();
      setCurrentEventSource(null);
    }
  };

  // Start/stop log streaming
  const toggleStreaming = () => {
    if (isStreaming) {
      setIsStreaming(false);
      setStreamLogs([]);
      closeCurrentStream();
    } else {
      setIsStreaming(true);
      startLogStreaming();
    }
  };

  const startLogStreaming = () => {
    // Close any existing stream
    closeCurrentStream();

    const levelParam = logLevel === 'all' ? 'all' : logLevel;
    const eventSource = new EventSource(
      `/admin/monitoring/logs/stream?container=${selectedContainer}&level=${levelParam}&token=changeme`
    );

    setCurrentEventSource(eventSource);

    eventSource.onmessage = (event) => {
      try {
        const logEntry = JSON.parse(event.data);
        setStreamLogs(prev => [logEntry, ...prev.slice(0, 99)]); // Keep last 100 entries
      } catch (error) {
        console.error('Error parsing log stream:', error);
      }
    };

    eventSource.onerror = (error) => {
      console.error('Log streaming error:', error);
      setIsStreaming(false);
      closeCurrentStream();
    };
  };

  // Restart streaming when container or level changes
  useEffect(() => {
    if (isStreaming) {
      console.log(`Restarting stream due to parameter change: container=${selectedContainer}, level=${logLevel}`);
      setStreamLogs([]); // Clear previous logs
      startLogStreaming();
    }
  }, [selectedContainer, logLevel]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      closeCurrentStream();
    };
  }, []);

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
              {t('memoryUsage')}
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
              {t('responseTime')}
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
                  {t('database')}
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
                  {t('vectorSearch')}
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
                <span className="text-sm font-medium">{t('vectorDimension')}</span>
                <span className="text-sm">{metrics?.info?.vector_dim || 0}</span>
              </div>
              <div className="text-xs text-muted-foreground">
                {t('schema')}: {metrics?.info?.schema?.current || 0}/{metrics?.info?.schema?.latest || 0}
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Performance Charts */}
      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>{t('cpuMemoryUsage')}</CardTitle>
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
                      name={t('memoryPercent')}
                    />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex items-center justify-center h-full text-muted-foreground">
                  {t('dataCollection')}...
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>{t('responseTime')}</CardTitle>
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
                      name={t('responseTimeMs')}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex items-center justify-center h-full text-muted-foreground">
                  {t('dataCollection')}...
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
              <Select value={selectedContainer} onValueChange={setSelectedContainer}>
                <SelectTrigger className="w-48">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {containerOptions.map(container => (
                    <SelectItem key={container.value} value={container.value}>
                      <div className="flex flex-col">
                        <span>{container.label}</span>
                        <span className="text-xs text-muted-foreground">{container.description}</span>
                      </div>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              
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
              
              <button
                onClick={toggleStreaming}
                className={`px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                  isStreaming 
                    ? 'bg-red-100 text-red-700 hover:bg-red-200' 
                    : 'bg-green-100 text-green-700 hover:bg-green-200'
                }`}
              >
                {isStreaming ? 'Stop Stream' : 'Start Stream'}
              </button>
            </div>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <ScrollArea className="h-96">
            {isStreaming ? (
              // Show streaming logs
              <div className="space-y-2">
                {streamLogs.length === 0 ? (
                  <div className="flex items-center justify-center h-32 text-muted-foreground">
                    <RefreshCw className="h-4 w-4 animate-spin mr-2" />
                    Várakozás streaming logokra...
                  </div>
                ) : (
                  streamLogs.map((log, index) => (
                    <div key={index} className="border-b pb-2">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          {getLogLevelBadge(log.level)}
                          <span className="text-xs text-muted-foreground font-mono">
                            {log.timestamp}
                          </span>
                          <Badge variant="outline" className="text-xs">
                            {log.container}
                          </Badge>
                        </div>
                      </div>
                      <p className="text-sm mt-1 font-mono">{log.message}</p>
                    </div>
                  ))
                )}
              </div>
            ) : (
              // Show static logs
              <>
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
                            {log.container && (
                              <Badge variant="outline" className="text-xs">
                                {log.container}
                              </Badge>
                            )}
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
              </>
            )}
          </ScrollArea>
        </CardContent>
      </Card>
    </div>
  );
}