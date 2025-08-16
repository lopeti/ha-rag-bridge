import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Separator } from '@/components/ui/separator';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Skeleton } from '@/components/ui/skeleton';
import { RefreshCw, Play, AlertCircle, CheckCircle2, Clock } from 'lucide-react';
import { EntityPipeline } from '@/components/pipeline/EntityPipeline';
import { ScoreEvolution } from '@/components/pipeline/ScoreEvolution';

interface WorkflowTrace {
  _key: string;
  trace_id: string;
  session_id: string;
  user_query: string;
  start_time: string;
  end_time?: string;
  total_duration_ms?: number;
  status: 'pending' | 'running' | 'success' | 'error';
  node_executions: any[];
  entity_pipeline: any[];
  performance_metrics: any;
  errors: string[];
}

export const PipelineDebugger: React.FC = () => {
  const [traces, setTraces] = useState<WorkflowTrace[]>([]);
  const [selectedTrace, setSelectedTrace] = useState<WorkflowTrace | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isLive, setIsLive] = useState(false);
  const [activeTab, setActiveTab] = useState('execution');
  const [testQuery, setTestQuery] = useState('hány fok van a nappaliban?');

  // Fetch recent traces
  const fetchTraces = async () => {
    try {
      const response = await fetch('/admin/debug/traces');
      if (response.ok) {
        const tracesData = await response.json();
        setTraces(tracesData);
        
        // Auto-select most recent if none selected
        if (!selectedTrace && tracesData.length > 0) {
          setSelectedTrace(tracesData[0]);
        }
      }
    } catch (error) {
      console.error('Failed to fetch traces:', error);
    } finally {
      setIsLoading(false);
    }
  };

  // Start a new test trace
  const startTestTrace = async () => {
    if (!testQuery.trim()) return;

    try {
      setIsLoading(true);
      const response = await fetch('/admin/debug/start-trace', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: testQuery,
          session_id: `test_${Date.now()}`
        })
      });

      if (response.ok) {
        // Refresh traces to show the new one
        setTimeout(fetchTraces, 1000);
      }
    } catch (error) {
      console.error('Failed to start test trace:', error);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchTraces();
    
    // Auto-refresh every 5 seconds when live mode is enabled
    const interval = setInterval(() => {
      if (isLive) {
        fetchTraces();
      }
    }, 5000);

    return () => clearInterval(interval);
  }, [isLive]);

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'success': return 'default';
      case 'error': return 'destructive';
      case 'running': return 'secondary';
      default: return 'outline';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'success': return <CheckCircle2 className="h-4 w-4" />;
      case 'error': return <AlertCircle className="h-4 w-4" />;
      case 'running': return <Clock className="h-4 w-4" />;
      default: return <Clock className="h-4 w-4" />;
    }
  };

  if (isLoading && traces.length === 0) {
    return (
      <div className="space-y-6">
        <div className="flex justify-between items-center">
          <Skeleton className="h-8 w-48" />
          <Skeleton className="h-10 w-24" />
        </div>
        <Card>
          <CardHeader>
            <Skeleton className="h-6 w-32" />
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-20 w-full" />
              <Skeleton className="h-40 w-full" />
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <Card>
        <CardHeader>
          <div className="flex justify-between items-center">
            <div className="flex items-center gap-4">
              <CardTitle className="text-2xl font-bold">Pipeline Debugger</CardTitle>
              <Badge variant={isLive ? "default" : "secondary"}>
                {isLive ? 'Live' : 'Historical'}
              </Badge>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setIsLive(!isLive)}
              >
                <RefreshCw className="h-4 w-4 mr-2" />
                {isLive ? 'Stop Live' : 'Start Live'}
              </Button>
            </div>
          </div>
          
          <div className="flex items-center gap-4">
            <Select
              value={selectedTrace?.trace_id || ''}
              onValueChange={(traceId) => {
                const trace = traces.find(t => t.trace_id === traceId);
                setSelectedTrace(trace || null);
              }}
            >
              <SelectTrigger className="w-80">
                <SelectValue placeholder="Select a trace to debug" />
              </SelectTrigger>
              <SelectContent>
                {traces.map((trace) => (
                  <SelectItem key={trace.trace_id} value={trace.trace_id}>
                    <div className="flex items-center gap-2">
                      {getStatusIcon(trace.status)}
                      <span className="truncate max-w-60">
                        {trace.user_query}
                      </span>
                      <Badge variant={getStatusColor(trace.status)} className="ml-2">
                        {trace.status}
                      </Badge>
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            
            <Separator orientation="vertical" className="h-6" />
            
            <div className="flex items-center gap-2">
              <input
                type="text"
                value={testQuery}
                onChange={(e) => setTestQuery(e.target.value)}
                placeholder="Enter test query..."
                className="px-3 py-2 border rounded-md bg-background text-sm"
                style={{ minWidth: '200px' }}
              />
              <Button
                onClick={startTestTrace}
                disabled={isLoading || !testQuery.trim()}
              >
                <Play className="h-4 w-4 mr-2" />
                Test
              </Button>
            </div>
          </div>
        </CardHeader>
      </Card>

      {/* Main Content */}
      {selectedTrace ? (
        <Card>
          <CardHeader>
            <div className="flex justify-between items-center">
              <div>
                <h3 className="text-lg font-semibold">{selectedTrace.user_query}</h3>
                <p className="text-sm text-muted-foreground">
                  Session: {selectedTrace.session_id} • 
                  Started: {new Date(selectedTrace.start_time).toLocaleString()}
                  {selectedTrace.total_duration_ms && (
                    <> • Duration: {selectedTrace.total_duration_ms.toFixed(1)}ms</>
                  )}
                </p>
              </div>
              <Badge variant={getStatusColor(selectedTrace.status)}>
                {selectedTrace.status.toUpperCase()}
              </Badge>
            </div>
            
            {selectedTrace.errors.length > 0 && (
              <Alert variant="destructive">
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>
                  {selectedTrace.errors.length} error(s) occurred during execution
                </AlertDescription>
              </Alert>
            )}
          </CardHeader>
          
          <CardContent>
            <Tabs value={activeTab} onValueChange={setActiveTab}>
              <TabsList className="grid w-full grid-cols-3">
                <TabsTrigger value="execution">Execution Flow</TabsTrigger>
                <TabsTrigger value="entities">Entity Pipeline</TabsTrigger>
                <TabsTrigger value="raw">Raw Data</TabsTrigger>
              </TabsList>
              
              <TabsContent value="execution" className="mt-6">
                <ScoreEvolution 
                  nodeExecutions={selectedTrace.node_executions || []}
                  entityPipeline={selectedTrace.entity_pipeline || []}
                />
              </TabsContent>
              
              <TabsContent value="entities" className="mt-6">
                <EntityPipeline entityPipeline={selectedTrace.entity_pipeline || []} />
              </TabsContent>
              
              <TabsContent value="raw" className="mt-6">
                <div className="space-y-4">
                  <pre className="bg-muted p-4 rounded-md overflow-auto max-h-96 text-xs">
                    {JSON.stringify(selectedTrace, null, 2)}
                  </pre>
                </div>
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="py-12">
            <div className="text-center text-muted-foreground">
              <AlertCircle className="h-12 w-12 mx-auto mb-4 opacity-50" />
              <h3 className="text-lg font-semibold mb-2">No Trace Selected</h3>
              <p>Select a trace from the dropdown above or start a new test to begin debugging.</p>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
};