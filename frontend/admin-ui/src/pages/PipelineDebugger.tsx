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
import { EnhancedPipeline } from '@/components/pipeline/EnhancedPipeline';
import { axiosApi as api } from '@/lib/api';

interface EnhancedPipelineStage {
  stage_name: string;
  stage_type: 'transform' | 'search' | 'boost' | 'rank' | 'filter';
  input_count: number;
  output_count: number;
  duration_ms: number;
  details?: {
    query_rewrite?: {
      original: string;
      rewritten: string;
      method: string;
      confidence: number;
      coreferences_resolved: string[];
      reasoning?: string;
    };
    conversation_summary?: {
      topic: string;
      current_focus: string;
      intent_pattern: string;
      topic_domains: string[];
      confidence: number;
      reasoning: string;
    };
    cluster_search?: {
      cluster_types: string[];
      cluster_count: number;
      scope: string;
      optimal_k: number;
    };
    vector_search?: {
      backend: string;
      vector_dimension: number;
      total_entities: number;
      k_value: number;
    };
    memory_boost?: {
      memory_entities_count: number;
      boosted_entities: number;
      session_id: string;
    };
    memory_stage?: {
      cache_status: 'hit' | 'miss' | 'pending';
      background_pending: boolean;
      entity_boosts: Record<string, number>;
      processing_source: 'quick_patterns' | 'cached_summary' | 'llm_generated';
      patterns_detected: number;
      quick_patterns?: {
        domains: string[];
        areas: string[];
        processing_time_ms: number;
      };
    };
    reranking?: {
      algorithm: string;
      score_range: {
        min: number;
        max: number;
      };
      primary_count: number;
      related_count: number;
      target_entities: number;
      filtered_entities: number;
      formatter_selected: string;
    };
  };
}

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
  enhanced_pipeline_stages: EnhancedPipelineStage[];
  performance_metrics: any;
  errors: string[];
}

export const PipelineDebugger: React.FC = () => {
  const [traces, setTraces] = useState<WorkflowTrace[]>([]);
  const [selectedTrace, setSelectedTrace] = useState<WorkflowTrace | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isTraceLoading, setIsTraceLoading] = useState(false);
  const [isLive, setIsLive] = useState(false);
  const [activeTab, setActiveTab] = useState('enhanced');
  const [testQuery, setTestQuery] = useState('hány fok van a nappaliban?');

  // Fetch recent traces (simplified list)
  const fetchTraces = async () => {
    try {
      const response = await api.get('/debug/traces');
      const tracesData = response.data;
      setTraces(tracesData);
      
      // Auto-select most recent if none selected
      if (!selectedTrace && tracesData.length > 0) {
        await fetchTraceDetails(tracesData[0].trace_id);
      }
    } catch (error) {
      console.error('Failed to fetch traces:', error);
    } finally {
      setIsLoading(false);
    }
  };

  // Fetch detailed trace data
  const fetchTraceDetails = async (traceId: string) => {
    try {
      setIsTraceLoading(true);
      const response = await api.get(`/debug/trace/${traceId}`);
      setSelectedTrace(response.data);
    } catch (error) {
      console.error('Failed to fetch trace details:', error);
    } finally {
      setIsTraceLoading(false);
    }
  };

  // Start a new test trace
  const startTestTrace = async () => {
    if (!testQuery.trim()) return;

    try {
      setIsLoading(true);
      await api.post('/debug/start-trace', {
        query: testQuery,
        session_id: `test_${Date.now()}`
      });
      
      // Refresh traces to show the new one
      setTimeout(fetchTraces, 1000);
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
              <CardTitle className="text-2xl font-bold">
                Pipeline Debugger 
                <Badge variant="destructive" className="ml-2 text-xs">OBSOLETE</Badge>
              </CardTitle>
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
                fetchTraceDetails(traceId);
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
          
          <Alert className="mt-4">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>
              This Pipeline Debugger is <strong>OBSOLETE</strong>. Please use the new <strong>Hook Debugger</strong> page for monitoring LiteLLM hook calls and entity retrieval debugging.
            </AlertDescription>
          </Alert>
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
              <TabsList className="grid w-full grid-cols-4">
                <TabsTrigger value="enhanced">Enhanced Pipeline</TabsTrigger>
                <TabsTrigger value="execution">Execution Flow</TabsTrigger>
                <TabsTrigger value="entities">Entity Pipeline</TabsTrigger>
                <TabsTrigger value="raw">Raw Data</TabsTrigger>
              </TabsList>
              
              <TabsContent value="enhanced" className="mt-6">
                {isTraceLoading ? (
                  <div className="space-y-4">
                    <Skeleton className="h-8 w-full" />
                    <Skeleton className="h-32 w-full" />
                    <Skeleton className="h-24 w-full" />
                  </div>
                ) : (
                  <EnhancedPipeline 
                    enhancedPipeline={selectedTrace.enhanced_pipeline_stages || []}
                  />
                )}
              </TabsContent>
              
              <TabsContent value="execution" className="mt-6">
                {isTraceLoading ? (
                  <div className="space-y-4">
                    <Skeleton className="h-8 w-full" />
                    <Skeleton className="h-32 w-full" />
                    <Skeleton className="h-24 w-full" />
                  </div>
                ) : (
                  <ScoreEvolution 
                    nodeExecutions={selectedTrace.node_executions || []}
                    entityPipeline={selectedTrace.entity_pipeline || []}
                    enhancedPipeline={selectedTrace.enhanced_pipeline_stages || []}
                  />
                )}
              </TabsContent>
              
              <TabsContent value="entities" className="mt-6">
                {isTraceLoading ? (
                  <div className="space-y-4">
                    <Skeleton className="h-8 w-full" />
                    <Skeleton className="h-32 w-full" />
                    <Skeleton className="h-24 w-full" />
                  </div>
                ) : (
                  <EntityPipeline 
                    entityPipeline={selectedTrace.entity_pipeline || []} 
                    enhancedPipeline={selectedTrace.enhanced_pipeline_stages || []}
                  />
                )}
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