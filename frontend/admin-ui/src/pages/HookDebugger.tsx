import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { AlertCircle, RefreshCw, Power, PowerOff, Eye } from 'lucide-react';

interface HookResult {
  id: string;
  session_id: string;
  timestamp: string;
  raw_input: string;
  extracted_messages: Array<{role: string; content: string}>;
  strategy_name: string;
  hook_source_info: {
    source: string;
    is_meta_task: boolean;
    meta_task_details?: any;
    extracted_query: string;
  };
  source_label: string;
  strategy_result: {
    strategy_used: string;
    execution_time_ms: number;
    entity_count: number;
    success: boolean;
  };
  entities: any[];
  formatted_content: string;
  completed_at: string;
  pipeline_summary: string;
  processing_info: {
    messages_extracted: number;
    raw_input_length: number;
    formatted_content_length: number;
  };
}

interface DebugStatus {
  debug_enabled: boolean;
  active_sessions: number;
  sessions: Record<string, any>;
  total_results: number;
  recent_hook_calls: number;
  listening_status: string;
  last_activity?: string;
}

export default function HookDebugger() {
  const [debugMode, setDebugMode] = useState(false);
  const [debugStatus, setDebugStatus] = useState<DebugStatus | null>(null);
  const [hookResults, setHookResults] = useState<HookResult[]>([]);
  const [selectedResult, setSelectedResult] = useState<HookResult | null>(null);
  const [loading, setLoading] = useState(false);

  // Fetch debug status
  const fetchDebugStatus = async () => {
    try {
      const debugResponse = await fetch('/admin/debug/status', {
        headers: { 'X-Admin-Token': 'changeme' }
      });
      const status = await debugResponse.json();
      setDebugStatus(status);
      // Check if hook-debugger session is active, not global debug_enabled
      const hookDebuggerActive = status.sessions && status.sessions['hook-debugger'];
      setDebugMode(hookDebuggerActive || false);
      return status;
    } catch (error) {
      console.error('Failed to fetch debug status:', error);
      return null;
    }
  };

  // Fetch hook results
  const fetchHookResults = async () => {
    try {
      const response = await fetch('/admin/debug/results?limit=50', {
        headers: { 'X-Admin-Token': 'changeme' }
      });
      const data = await response.json();
      setHookResults(data.results || []);
      return data;
    } catch (error) {
      console.error('Failed to fetch hook results:', error);
      return null;
    }
  };

  // Toggle debug mode
  const toggleDebugMode = async () => {
    setLoading(true);
    try {
      const response = await fetch('/admin/debug/toggle', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Admin-Token': 'changeme'
        },
        body: JSON.stringify({
          session_id: 'hook-debugger',
          enabled: !debugMode
        })
      });
      
      if (response.ok) {
        const result = await response.json();
        setDebugMode(result.debug_enabled);
        await fetchDebugStatus();
      }
    } catch (error) {
      console.error('Failed to toggle debug mode:', error);
    } finally {
      setLoading(false);
    }
  };

  // Auto-refresh when debug mode is on
  useEffect(() => {
    fetchDebugStatus();
    if (debugMode) {
      fetchHookResults();
    }

    const interval = setInterval(() => {
      if (debugMode) {
        fetchHookResults();
        fetchDebugStatus();
      }
    }, 3000); // Faster refresh for real-time feel

    return () => clearInterval(interval);
  }, [debugMode]);

  const formatTimestamp = (timestamp: string) => {
    return new Date(timestamp).toLocaleTimeString('hu-HU', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    });
  };

  const formatDuration = (ms: number) => {
    return `${ms.toFixed(1)}ms`;
  };

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Hook Debugger</h1>
          <p className="text-muted-foreground">
            Real-time monitoring of LiteLLM hook calls and bridge responses
          </p>
        </div>
        
        <div className="flex items-center gap-4">
          <Button 
            onClick={toggleDebugMode}
            disabled={loading}
            variant={debugMode ? "destructive" : "default"}
            size="lg"
          >
            {loading ? (
              <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
            ) : debugMode ? (
              <PowerOff className="h-4 w-4 mr-2" />
            ) : (
              <Power className="h-4 w-4 mr-2" />
            )}
            {debugMode ? 'Stop Monitoring' : 'Start Monitoring'}
          </Button>
          
          {debugMode && (
            <Badge variant="default" className="animate-pulse">
              🟢 Live
            </Badge>
          )}
        </div>
      </div>

      {/* Status Card */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Eye className="h-5 w-5" />
            Debug Status
          </CardTitle>
        </CardHeader>
        <CardContent>
          {debugStatus ? (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <div className="text-2xl font-bold">{debugStatus.total_results}</div>
                <div className="text-sm text-muted-foreground">Total Captures</div>
              </div>
              <div>
                <div className="text-2xl font-bold">{debugStatus.recent_hook_calls}</div>
                <div className="text-sm text-muted-foreground">Recent Hooks</div>
              </div>
              <div>
                <div className="text-2xl font-bold">{debugStatus.active_sessions}</div>
                <div className="text-sm text-muted-foreground">Active Sessions</div>
              </div>
              <div>
                <Badge variant={debugMode ? "default" : "secondary"}>
                  {debugStatus.listening_status}
                </Badge>
              </div>
            </div>
          ) : (
            <div className="text-center text-muted-foreground">Loading status...</div>
          )}
        </CardContent>
      </Card>

      {/* Hook Results */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Results List */}
        <Card>
          <CardHeader>
            <CardTitle>Hook Calls ({hookResults.length})</CardTitle>
          </CardHeader>
          <CardContent>
            {!debugMode && (
              <Alert>
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>
                  Start monitoring to capture hook calls from LiteLLM
                </AlertDescription>
              </Alert>
            )}
            
            {debugMode && hookResults.length === 0 && (
              <div className="text-center py-8 text-muted-foreground">
                <AlertCircle className="h-12 w-12 mx-auto mb-4 opacity-50" />
                <h3 className="text-lg font-semibold mb-2">Waiting for Hook Calls</h3>
                <p>Send queries through LiteLLM to see results here.</p>
              </div>
            )}

            {hookResults.length > 0 && (
              <div className="space-y-2 max-h-96 overflow-y-auto">
                {hookResults.map((result) => (
                  <Card 
                    key={result.id} 
                    className={`cursor-pointer transition-colors ${
                      selectedResult?.id === result.id ? 'ring-2 ring-primary' : 'hover:bg-muted/50'
                    }`}
                    onClick={() => setSelectedResult(result)}
                  >
                    <CardContent className="p-4">
                      <div className="flex items-start justify-between">
                        <div className="flex-1 min-w-0">
                          <div className="font-medium truncate">
                            {result.hook_source_info.extracted_query}
                          </div>
                          <div className="text-sm text-muted-foreground mt-1">
                            {formatTimestamp(result.timestamp)} • {result.strategy_result.entity_count} entities • {formatDuration(result.strategy_result.execution_time_ms)}
                          </div>
                        </div>
                        <Badge variant="outline" className="ml-2">
                          {result.hook_source_info.source}
                        </Badge>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Selected Result Details */}
        <Card>
          <CardHeader>
            <CardTitle>Hook Details</CardTitle>
          </CardHeader>
          <CardContent>
            {!selectedResult ? (
              <div className="text-center py-8 text-muted-foreground">
                Select a hook call to view details
              </div>
            ) : (
              <Tabs defaultValue="overview" className="w-full">
                <TabsList className="grid w-full grid-cols-3">
                  <TabsTrigger value="overview">Overview</TabsTrigger>
                  <TabsTrigger value="entities">Entities</TabsTrigger>
                  <TabsTrigger value="context">Context</TabsTrigger>
                </TabsList>
                
                <TabsContent value="overview" className="space-y-4">
                  <div>
                    <h4 className="font-semibold">Query</h4>
                    <p className="text-sm">{selectedResult.hook_source_info.extracted_query}</p>
                  </div>
                  
                  <div className="grid grid-cols-3 gap-4">
                    <div>
                      <h4 className="font-semibold">Strategy</h4>
                      <Badge variant="secondary">{selectedResult.strategy_result.strategy_used}</Badge>
                    </div>
                    <div>
                      <h4 className="font-semibold">Execution Time</h4>
                      <span className="text-sm">{formatDuration(selectedResult.strategy_result.execution_time_ms)}</span>
                    </div>
                    <div>
                      <h4 className="font-semibold">Context Injected</h4>
                      <div className="space-y-1">
                        <Badge variant="outline">
                          {selectedResult.processing_info.formatted_content_length} chars
                        </Badge>
                        <div className="text-xs text-muted-foreground">
                          ~{Math.round(selectedResult.processing_info.formatted_content_length / 4)} tokens
                        </div>
                      </div>
                    </div>
                  </div>
                  
                  <div>
                    <h4 className="font-semibold">Processing Info</h4>
                    <div className="text-sm space-y-1">
                      <div>Messages: {selectedResult.processing_info.messages_extracted}</div>
                      <div>Input Length: {selectedResult.processing_info.raw_input_length} chars</div>
                      <div>Context Length: {selectedResult.processing_info.formatted_content_length} chars</div>
                    </div>
                  </div>
                </TabsContent>
                
                <TabsContent value="entities" className="space-y-2">
                  <div className="max-h-64 overflow-y-auto space-y-2">
                    {selectedResult.entities.slice(0, 10).map((entity, idx) => (
                      <Card key={entity.entity_id} className="p-3">
                        <div className="flex items-start justify-between">
                          <div className="flex-1 min-w-0">
                            <div className="font-mono text-sm truncate">{entity.entity_id}</div>
                            <div className="text-xs text-muted-foreground">
                              {entity.area} • {entity.domain} • Score: {entity.score?.toFixed(3)}
                            </div>
                          </div>
                          <Badge variant="outline" className="ml-2 text-xs">
                            #{idx + 1}
                          </Badge>
                        </div>
                      </Card>
                    ))}
                    {selectedResult.entities.length > 10 && (
                      <div className="text-center text-sm text-muted-foreground">
                        ... and {selectedResult.entities.length - 10} more entities
                      </div>
                    )}
                  </div>
                </TabsContent>
                
                <TabsContent value="context" className="space-y-2">
                  <div>
                    <h4 className="font-semibold mb-2">Formatted Context</h4>
                    <div className="bg-muted p-3 rounded-lg text-sm font-mono whitespace-pre-wrap max-h-64 overflow-y-auto">
                      {selectedResult.formatted_content}
                    </div>
                  </div>
                </TabsContent>
              </Tabs>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}