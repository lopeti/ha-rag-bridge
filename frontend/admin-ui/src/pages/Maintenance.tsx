
import { useState, useRef, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useMutation, useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '../components/ui/dialog';
// import { ScrollArea } from '../components/ui/scroll-area';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from '../components/ui/alert-dialog';
import { Database, Trash2, RefreshCw, Activity, HardDrive, Cpu, X, Terminal, Download, Container } from 'lucide-react';
import { adminApi } from '../lib/api';
import { ContainerManagement } from '../components/ContainerManagement';

export function Maintenance() {
  const { t } = useTranslation();
  const [logs, setLogs] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [showStreamDialog, setShowStreamDialog] = useState(false);
  const [streamTitle, setStreamTitle] = useState('Művelet');
  const eventSourceRef = useRef<EventSource | null>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  
  // Cleanup EventSource connections when component unmounts
  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
    };
  }, []);
  
  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn: adminApi.getHealth,
    refetchInterval: 30000, // Refresh every 30 seconds
  });

  const { data: stats } = useQuery({
    queryKey: ['stats'],
    queryFn: adminApi.getSystemStats,
    refetchInterval: 10000, // Refresh every 10 seconds
  });

  // Bootstrap now uses streaming instead of mutation

  const clearCacheMutation = useMutation({
    mutationFn: adminApi.clearCache,
    onSuccess: () => {
      setLogs('✅ Cache sikeresen törölve');
      setShowStreamDialog(true);
      setStreamTitle(t('cacheCleanResult'));
    },
    onError: (error: any) => {
      setLogs(`❌ Hiba: ${error.message}`);
      setShowStreamDialog(true);
      setStreamTitle(t('cacheCleanError'));
    },
  });

  const startStreamingIngest = () => {
    if (isStreaming) return;
    
    setIsStreaming(true);
    setLogs('📥 Kapcsolódás az ingesztálás szolgáltatáshoz...\n');
    setShowStreamDialog(true);
    setStreamTitle(t('entityIngestion'));
    
    // Close any existing connection
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }
    
    const eventSource = new EventSource('/admin/maintenance/ingest/stream?token=changeme');
    eventSourceRef.current = eventSource;
    
    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setLogs(prev => {
        const newLogs = prev + `[${data.event}] ${data.message}\n`;
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
      setLogs(prev => prev + `❌ Kapcsolódási hiba történt\n`);
      setIsStreaming(false);
      eventSource.close();
    };
  };

  const startStreamingBootstrap = () => {
    if (isStreaming) return;
    
    setIsStreaming(true);
    setLogs('🚀 Kapcsolódás a bootstrap szolgáltatáshoz...\n');
    setShowStreamDialog(true);
    setStreamTitle('Adatbázis bootstrap');
    
    // Close any existing connection
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }
    
    const eventSource = new EventSource('/admin/maintenance/bootstrap/stream?token=changeme');
    eventSourceRef.current = eventSource;
    
    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setLogs(prev => {
        const newLogs = prev + `[${data.event}] ${data.message}\n`;
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
      setLogs(prev => prev + `❌ Kapcsolódási hiba történt\n`);
      setIsStreaming(false);
      eventSource.close();
    };
  };

  // Remove reindexMutation since we'll use streaming by default

  const startStreamingReindex = () => {
    if (isStreaming) return;
    
    setIsStreaming(true);
    setLogs('🔄 Kapcsolódás a vektor újraindexelés szolgáltatáshoz...\n');
    setShowStreamDialog(true);
    setStreamTitle(t('vectorReindexing'));
    
    // Close any existing connection
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }
    
    const eventSource = new EventSource('/admin/maintenance/reindex-vectors/stream?token=changeme');
    eventSourceRef.current = eventSource;
    
    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setLogs(prev => {
        const newLogs = prev + `[${data.event}] ${data.message}\n`;
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
      setLogs(prev => prev + `❌ Kapcsolódási hiba történt\n`);
      setIsStreaming(false);
      eventSource.close();
    };
  };

  // Test streaming function using our working test endpoint
  const startTestStreaming = () => {
    if (isStreaming) return;
    
    setIsStreaming(true);
    setLogs('🧪 Kapcsolódás a teszt szolgáltatáshoz...\n');
    setShowStreamDialog(true);
    setStreamTitle(t('streamingTest'));
    
    // Close any existing connection
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }
    
    const eventSource = new EventSource('/admin/test-streaming?token=changeme');
    eventSourceRef.current = eventSource;
    
    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setLogs(prev => {
        let newLogs = prev;
        if (data.message) {
          newLogs = prev + `${data.message}\n`;
        }
        
        // Auto-scroll to bottom after state update
        setTimeout(() => {
          if (scrollContainerRef?.current) {
            scrollContainerRef.current.scrollTop = scrollContainerRef.current.scrollHeight;
          }
        }, 50);
        return newLogs;
      });
      
      if (data.completed) {
        setIsStreaming(false);
        eventSource.close();
      }
    };
    
    eventSource.onerror = () => {
      setLogs(prev => prev + `❌ Kapcsolódási hiba történt\n`);
      setIsStreaming(false);
      eventSource.close();
    };
  };

  const stopStreaming = () => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    setIsStreaming(false);
    setLogs(prev => prev + `⏹️ Felhasználó által leállítva\n`);
  };
  
  const closeStreamDialog = () => {
    if (isStreaming) {
      stopStreaming();
    }
    setShowStreamDialog(false);
    setLogs('');
  };

  const getHealthBadgeVariant = (status: string) => {
    switch (status) {
      case 'healthy': return 'default';
      case 'warning': return 'secondary';
      case 'error': return 'destructive';
      default: return 'outline';
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Karbantartás</h1>
        <Badge variant={getHealthBadgeVariant(health?.status || 'unknown')}>
          {health?.status === 'healthy' ? 'Rendben' : 
           health?.status === 'warning' ? 'Figyelmeztetés' : 
           health?.status === 'error' ? 'Hiba' : 'Ismeretlen'}
        </Badge>
      </div>

      {/* System Status */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium flex items-center">
              <Database className="h-4 w-4 mr-2" />
              Adatbázis
            </CardTitle>
          </CardHeader>
          <CardContent>
            <Badge variant={health?.database ? 'default' : 'destructive'}>
              {health?.database ? t('available') : t('notAvailable')}
            </Badge>
            <p className="text-xs text-muted-foreground mt-1">
              {health?.database_version || 'N/A'}
            </p>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium flex items-center">
              <Activity className="h-4 w-4 mr-2" />
              Home Assistant
            </CardTitle>
          </CardHeader>
          <CardContent>
            <Badge variant={health?.home_assistant ? 'default' : 'destructive'}>
              {health?.home_assistant ? t('available') : t('notAvailable')}
            </Badge>
            <p className="text-xs text-muted-foreground mt-1">
              {health?.ha_version || 'N/A'}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium flex items-center">
              <Cpu className="h-4 w-4 mr-2" />
              CPU
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{stats?.cpu_usage || 0}%</p>
            <p className="text-xs text-muted-foreground">{t('usage')}</p>
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
            <p className="text-2xl font-bold">{stats?.memory_usage || 0}%</p>
            <p className="text-xs text-muted-foreground">{t('usage')}</p>
          </CardContent>
        </Card>
      </div>

      {/* Container Management */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center">
            <Container className="h-5 w-5 mr-2" />
            Konténer kezelés
          </CardTitle>
        </CardHeader>
        <CardContent>
          <ContainerManagement />
        </CardContent>
      </Card>

      {/* Maintenance Actions */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-5">
        {/* Bootstrap Database */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center">
              <Database className="h-5 w-5 mr-2" />
              {t('databaseInit')}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">
              {t('databaseInitDescription')}
            </p>
            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button 
                  variant="outline" 
                  disabled={isStreaming}
                  className="w-full"
                >
                  {isStreaming ? (
                    <>
                      <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                      {t('running')}
                    </>
                  ) : (
                    t('runBootstrap')
                  )}
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>{t('runBootstrap')}</AlertDialogTitle>
                  <AlertDialogDescription>
                    Ez újra létrehozza az adatbázis kollekciók és indexeket. Ez eltarthat néhány percig.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>{t('cancel')}</AlertDialogCancel>
                  <AlertDialogAction onClick={startStreamingBootstrap}>
                    Indítás
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          </CardContent>
        </Card>

        {/* Clear Cache */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center">
              <Trash2 className="h-5 w-5 mr-2" />
              {t('cacheClear')}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">
              {t('cacheClearDescription')}
            </p>
            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button 
                  variant="outline" 
                  disabled={clearCacheMutation.isPending}
                  className="w-full"
                >
                  {clearCacheMutation.isPending ? (
                    <>
                      <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                      {t('deleting')}
                    </>
                  ) : (
                    t('cacheDeletion')
                  )}
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>{t('cacheDeletion')}</AlertDialogTitle>
                  <AlertDialogDescription>
                    {t('cacheDeleteDescription')}
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>{t('cancel')}</AlertDialogCancel>
                  <AlertDialogAction onClick={() => clearCacheMutation.mutate()}>
                    Törlés
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          </CardContent>
        </Card>

        {/* Ingest Entities */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center">
              <Download className="h-5 w-5 mr-2" />
              {t('entityIngestion')}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Home Assistant entitások szinkronizálása az adatbázisba élő naplózással.
            </p>
            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button 
                  variant="outline" 
                  disabled={isStreaming}
                  className="w-full"
                >
                  {isStreaming ? (
                    <>
                      <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                      {t('ingesting')}
                    </>
                  ) : (
                    t('ingestEntities')
                  )}
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>{t('entityIngestion')}</AlertDialogTitle>
                  <AlertDialogDescription>
                    {t('entityIngestionDescription')}
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>{t('cancel')}</AlertDialogCancel>
                  <AlertDialogAction onClick={startStreamingIngest}>
                    Indítás
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          </CardContent>
        </Card>

        {/* Vector Reindex */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center">
              <RefreshCw className="h-5 w-5 mr-2" />
              Vektor újraindexelés
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Összes entitás embedding újraszámítása élő naplózással.
            </p>
            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button 
                  variant="outline" 
                  disabled={isStreaming}
                  className="w-full"
                >
                  {isStreaming ? (
                    <>
                      <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                      {t('indexingInProgress')}
                    </>
                  ) : (
                    'Vektor újraindexelés'
                  )}
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>{t('vectorReindexing')}</AlertDialogTitle>
                  <AlertDialogDescription>
                    {t('vectorReindexDescription')}
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>{t('cancel')}</AlertDialogCancel>
                  <AlertDialogAction onClick={startStreamingReindex}>
                    Indítás
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          </CardContent>
        </Card>

        {/* Test Streaming */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center">
              <Terminal className="h-5 w-5 mr-2" />
              {t('streamingTest')}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">
              {t('testFunctionality')}
            </p>
            <Button 
              variant="outline" 
              disabled={isStreaming}
              className="w-full"
              onClick={startTestStreaming}
            >
              {isStreaming ? (
                <>
                  <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                  {t('testing')}
                </>
              ) : (
                t('startTest')
              )}
            </Button>
          </CardContent>
        </Card>
      </div>

      {/* System Information */}
      <Card>
        <CardHeader>
          <CardTitle>{t('systemInformation')}</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <h4 className="font-medium mb-2">{t('serviceInfo')}</h4>
              <div className="space-y-1 text-sm">
                <div className="flex justify-between">
                  <span>{t('embeddingBackend')}</span>
                  <span>{health?.embedding_backend || 'N/A'}</span>
                </div>
                <div className="flex justify-between">
                  <span>{t('embeddingDimensions')}</span>
                  <span>{health?.embedding_dimensions || 'N/A'}</span>
                </div>
                <div className="flex justify-between">
                  <span>{t('lastBootstrap')}</span>
                  <span>{health?.last_bootstrap || 'N/A'}</span>
                </div>
                <div className="flex justify-between">
                  <span>{t('uptime')}</span>
                  <span>{stats?.uptime || 'N/A'}</span>
                </div>
              </div>
            </div>
            <div>
              <h4 className="font-medium mb-2">{t('databaseStats')}</h4>
              <div className="space-y-1 text-sm">
                <div className="flex justify-between">
                  <span>{t('entities')}</span>
                  <span>{stats?.total_entities || 0}</span>
                </div>
                <div className="flex justify-between">
                  <span>{t('clusters')}</span>
                  <span>{stats?.total_clusters || 0}</span>
                </div>
                <div className="flex justify-between">
                  <span>{t('documents')}</span>
                  <span>{stats?.total_documents || 0}</span>
                </div>
                <div className="flex justify-between">
                  <span>{t('databaseSize')}</span>
                  <span>{stats?.database_size || 'N/A'}</span>
                </div>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Stream Dialog */}
      <Dialog open={showStreamDialog} onOpenChange={setShowStreamDialog}>
        <DialogContent className="max-w-4xl max-h-[80vh]">
          <DialogHeader>
            <DialogTitle className="flex items-center">
              <Terminal className="h-5 w-5 mr-2" />
              {streamTitle}
            </DialogTitle>
            <DialogDescription>
              {isStreaming ? t('operationInProgress') : t('operationResult')}
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-col space-y-4">
            <div 
              className="h-96 w-full rounded-md border bg-slate-950 text-slate-50 p-4 overflow-auto"
              ref={scrollContainerRef}
            >
              <pre className="text-xs font-mono whitespace-pre-wrap">
                {logs || 'Nincsenek logok...'}
              </pre>
            </div>
            <div className="flex justify-between gap-2">
              <Button 
                variant="outline" 
                size="sm" 
                onClick={() => setLogs('')}
                disabled={isStreaming}
              >
                Logok törlése
              </Button>
              <div className="flex gap-2">
                {isStreaming && (
                  <Button 
                    variant="destructive" 
                    size="sm"
                    onClick={stopStreaming}
                  >
                    <X className="h-4 w-4 mr-1" />
                    Leállítás
                  </Button>
                )}
                <Button 
                  variant="outline" 
                  size="sm" 
                  onClick={closeStreamDialog}
                >
                  Bezárás
                </Button>
              </div>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}