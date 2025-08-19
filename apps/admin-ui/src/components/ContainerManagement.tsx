import { useState, useRef } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from './ui/dialog';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from './ui/alert-dialog';
import { 
  RefreshCw, 
  Square, 
  RotateCcw, 
  Cpu, 
  HardDrive,
  Activity,
  Settings,
  Hammer,
  Terminal,
  X
} from 'lucide-react';
import { adminApi } from '../lib/api';

interface Container {
  name: string;
  service: string;
  status: string;
  health: string;
  image: string;
  ports: Array<{[key: string]: any}>;
}

interface HealthData {
  container: string;
  cpu_percent: string;
  memory_usage: string;
  network_io: string;
  block_io: string;
}

export function ContainerManagement() {
  const queryClient = useQueryClient();
  
  // Log streaming state
  const [logs, setLogs] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [showLogDialog, setShowLogDialog] = useState(false);
  const [streamTitle, setStreamTitle] = useState('Container Logs');
  const eventSourceRef = useRef<EventSource | null>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  // Get container status
  const { data: containerData, isLoading: statusLoading } = useQuery({
    queryKey: ['containers', 'status'],
    queryFn: adminApi.getContainerStatus,
    refetchInterval: 10000, // Refresh every 10 seconds
  });

  // Get container health
  const { data: healthData } = useQuery({
    queryKey: ['containers', 'health'],
    queryFn: adminApi.getContainerHealth,
    refetchInterval: 15000, // Refresh every 15 seconds
  });

  // Restart service mutation
  const restartMutation = useMutation({
    mutationFn: (service: string) => adminApi.restartContainer(service),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['containers'] });
    },
  });

  // Rebuild service mutation
  const rebuildMutation = useMutation({
    mutationFn: (service: string) => adminApi.rebuildContainer(service),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['containers'] });
    },
  });

  // Restart stack mutation
  const restartStackMutation = useMutation({
    mutationFn: adminApi.restartStack,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['containers'] });
    },
  });

  // Dev mode toggle mutation
  const devModeMutation = useMutation({
    mutationFn: (action: 'enable' | 'disable') => adminApi.toggleDevMode(action),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['containers'] });
    },
  });

  const containers: Container[] = containerData?.containers || [];
  const healthStats: HealthData[] = healthData?.health_data || [];

  const getStatusBadgeVariant = (status: string) => {
    switch (status.toLowerCase()) {
      case 'running': return 'default';
      case 'healthy': return 'default';
      case 'restarting': return 'secondary';
      case 'paused': return 'secondary';
      case 'exited': return 'destructive';
      case 'dead': return 'destructive';
      default: return 'outline';
    }
  };

  const getServiceIcon = (service: string) => {
    switch (service) {
      case 'bridge': return <Activity className="h-4 w-4" />;
      case 'litellm': return <Cpu className="h-4 w-4" />;
      case 'arangodb': return <HardDrive className="h-4 w-4" />;
      case 'ollama': return <HardDrive className="h-4 w-4" />;
      default: return <Settings className="h-4 w-4" />;
    }
  };

  const getHealthStats = (containerName: string) => {
    return healthStats.find(h => h.container.includes(containerName.split('-')[0]));
  };

  const isValidService = (service: string) => {
    const validServices = ['bridge', 'litellm', 'arangodb', 'ollama', 'portainer'];
    return validServices.includes(service);
  };

  const isBuildableService = (service: string) => {
    const buildableServices = ['bridge', 'litellm'];
    return buildableServices.includes(service);
  };

  // Log streaming functions
  const startLogStreaming = (service: string) => {
    if (isStreaming) return;
    
    setIsStreaming(true);
    setLogs(`🔍 Connecting to ${service} logs...\n`);
    setShowLogDialog(true);
    setStreamTitle(`${service} Container Logs`);
    
    // Close any existing connection
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }
    
    const eventSource = new EventSource(`/admin/containers/${service}/logs/stream`);
    eventSourceRef.current = eventSource;
    
    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setLogs(prev => {
        const newLogs = prev + `[${data.timestamp || new Date().toLocaleTimeString()}] ${data.message}\n`;
        // Auto-scroll to bottom after state update
        setTimeout(() => {
          if (scrollContainerRef?.current) {
            scrollContainerRef.current.scrollTop = scrollContainerRef.current.scrollHeight;
          }
        }, 50);
        return newLogs;
      });
      
      if (data.event === 'complete' || data.event === 'error') {
        setIsStreaming(false);
        eventSource.close();
      }
    };
    
    eventSource.onerror = () => {
      setLogs(prev => prev + `❌ Connection error occurred\n`);
      setIsStreaming(false);
      eventSource.close();
    };
  };

  const stopLogStreaming = () => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    setIsStreaming(false);
    setLogs(prev => prev + `⏹️ Log streaming stopped by user\n`);
  };
  
  const closeLogDialog = () => {
    if (isStreaming) {
      stopLogStreaming();
    }
    setShowLogDialog(false);
    setLogs('');
  };

  return (
    <div className="space-y-6">
      {/* Quick Actions */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center">
            <RotateCcw className="h-5 w-5 mr-2" />
            Gyors műveletek
          </CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-4">
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button 
                variant="outline" 
                disabled={restartStackMutation.isPending}
                className="flex items-center gap-2"
              >
                {restartStackMutation.isPending ? (
                  <RefreshCw className="h-4 w-4 animate-spin" />
                ) : (
                  <RefreshCw className="h-4 w-4" />
                )}
                Teljes stack újraindítása
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Stack újraindítása</AlertDialogTitle>
                <AlertDialogDescription>
                  Ez újraindítja az összes konténert. A művelet körülbelül 1-2 percet vesz igénybe.
                  Biztos vagy benne?
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Mégse</AlertDialogCancel>
                <AlertDialogAction onClick={() => restartStackMutation.mutate()}>
                  Újraindítás
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>

          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button 
                variant="outline" 
                disabled={devModeMutation.isPending}
                className="flex items-center gap-2"
              >
                {devModeMutation.isPending ? (
                  <RefreshCw className="h-4 w-4 animate-spin" />
                ) : (
                  <Settings className="h-4 w-4" />
                )}
                Fejlesztői mód
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Fejlesztői mód bekapcsolása</AlertDialogTitle>
                <AlertDialogDescription>
                  Ez aktiválja a debugpy portot, auto-reload funkciót és volume mount-okat.
                  A CPU használat megnőhet. Szeretnéd folytatni?
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Mégse</AlertDialogCancel>
                <AlertDialogAction onClick={() => devModeMutation.mutate('enable')}>
                  Bekapcsolás
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>

          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button 
                variant="outline" 
                disabled={devModeMutation.isPending}
                className="flex items-center gap-2"
              >
                {devModeMutation.isPending ? (
                  <RefreshCw className="h-4 w-4 animate-spin" />
                ) : (
                  <Square className="h-4 w-4" />
                )}
                Produkciós mód
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Produkciós mód bekapcsolása</AlertDialogTitle>
                <AlertDialogDescription>
                  Ez kikapcsolja a debug funkciókat és optimalizálja a CPU használatot.
                  Szeretnéd folytatni?
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Mégse</AlertDialogCancel>
                <AlertDialogAction onClick={() => devModeMutation.mutate('disable')}>
                  Bekapcsolás
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </CardContent>
      </Card>

      {/* Container Status Grid */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {containers.map((container) => {
          const health = getHealthStats(container.name);
          
          return (
            <Card key={container.name}>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-medium flex items-center justify-between">
                  <div className="flex items-center">
                    {getServiceIcon(container.service)}
                    <span className="ml-2">{container.service}</span>
                  </div>
                  <Badge variant={getStatusBadgeVariant(container.status)}>
                    {container.status}
                  </Badge>
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {/* Health Stats */}
                {health && (
                  <div className="text-xs space-y-1">
                    <div className="flex justify-between">
                      <span>CPU:</span>
                      <span>{health.cpu_percent}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Memória:</span>
                      <span>{health.memory_usage}</span>
                    </div>
                  </div>
                )}

                {/* Container Image */}
                <div className="text-xs text-muted-foreground">
                  {container.image}
                </div>

                {/* Action Buttons */}
                <div className="flex gap-2 flex-wrap">
                  {/* Log Console Button */}
                  <Button 
                    size="sm" 
                    variant="outline"
                    disabled={isStreaming}
                    onClick={() => startLogStreaming(container.service)}
                    className="flex items-center gap-1"
                  >
                    <Terminal className="h-3 w-3" />
                    Logok
                  </Button>

                  {isValidService(container.service) && (
                    <AlertDialog>
                      <AlertDialogTrigger asChild>
                        <Button 
                          size="sm" 
                          variant="outline"
                          disabled={restartMutation.isPending}
                        >
                          <RefreshCw className="h-3 w-3 mr-1" />
                          Újraindítás
                        </Button>
                      </AlertDialogTrigger>
                      <AlertDialogContent>
                        <AlertDialogHeader>
                          <AlertDialogTitle>Szolgáltatás újraindítása</AlertDialogTitle>
                          <AlertDialogDescription>
                            Újraindítod a {container.service} szolgáltatást? 
                            Ez körülbelül 10-30 másodpercet vesz igénybe.
                          </AlertDialogDescription>
                        </AlertDialogHeader>
                        <AlertDialogFooter>
                          <AlertDialogCancel>Mégse</AlertDialogCancel>
                          <AlertDialogAction 
                            onClick={() => restartMutation.mutate(container.service)}
                          >
                            Újraindítás
                          </AlertDialogAction>
                        </AlertDialogFooter>
                      </AlertDialogContent>
                    </AlertDialog>
                  )}

                  {isBuildableService(container.service) && (
                    <AlertDialog>
                      <AlertDialogTrigger asChild>
                        <Button 
                          size="sm" 
                          variant="outline"
                          disabled={rebuildMutation.isPending}
                        >
                          <Hammer className="h-3 w-3 mr-1" />
                          Rebuild
                        </Button>
                      </AlertDialogTrigger>
                      <AlertDialogContent>
                        <AlertDialogHeader>
                          <AlertDialogTitle>Szolgáltatás rebuild</AlertDialogTitle>
                          <AlertDialogDescription>
                            Ez újraépíti és újraindítja a {container.service} szolgáltatást.
                            A művelet 2-5 percet vehet igénybe. Szeretnéd folytatni?
                          </AlertDialogDescription>
                        </AlertDialogHeader>
                        <AlertDialogFooter>
                          <AlertDialogCancel>Mégse</AlertDialogCancel>
                          <AlertDialogAction 
                            onClick={() => rebuildMutation.mutate(container.service)}
                          >
                            Rebuild
                          </AlertDialogAction>
                        </AlertDialogFooter>
                      </AlertDialogContent>
                    </AlertDialog>
                  )}
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Loading/Error States */}
      {statusLoading && (
        <div className="text-center py-8">
          <RefreshCw className="h-8 w-8 animate-spin mx-auto mb-2" />
          <p>Konténer állapot betöltése...</p>
        </div>
      )}

      {!statusLoading && containers.length === 0 && (
        <div className="text-center py-8 text-muted-foreground">
          Nincsenek futó konténerek
        </div>
      )}

      {/* Log Stream Dialog */}
      <Dialog open={showLogDialog} onOpenChange={setShowLogDialog}>
        <DialogContent className="max-w-4xl max-h-[80vh]">
          <DialogHeader>
            <DialogTitle className="flex items-center">
              <Terminal className="h-5 w-5 mr-2" />
              {streamTitle}
            </DialogTitle>
            <DialogDescription>
              {isStreaming ? 'Live log streaming in progress...' : 'Container log output'}
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-col space-y-4">
            <div 
              className="h-96 w-full rounded-md border bg-slate-950 text-slate-50 p-4 overflow-auto"
              ref={scrollContainerRef}
            >
              <pre className="text-xs font-mono whitespace-pre-wrap">
                {logs || 'No logs available...'}
              </pre>
            </div>
            <div className="flex justify-between gap-2">
              <Button 
                variant="outline" 
                size="sm" 
                onClick={() => setLogs('')}
                disabled={isStreaming}
              >
                Clear Logs
              </Button>
              <div className="flex gap-2">
                {isStreaming && (
                  <Button 
                    variant="destructive" 
                    size="sm"
                    onClick={stopLogStreaming}
                  >
                    <X className="h-4 w-4 mr-1" />
                    Stop Stream
                  </Button>
                )}
                <Button 
                  variant="outline" 
                  size="sm" 
                  onClick={closeLogDialog}
                >
                  Close
                </Button>
              </div>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}