import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Copy, Download, Eye, Code } from 'lucide-react';
import { useToast } from '@/hooks/use-toast';

interface WorkflowTrace {
  _key: string;
  trace_id: string;
  session_id: string;
  user_query: string;
  start_time: string;
  end_time?: string;
  total_duration_ms?: number;
  status: 'pending' | 'running' | 'success' | 'error';
  openwebui_request: any;
  litellm_request: any;
  node_executions: any[];
  workflow_state: any;
  final_result: any;
  entity_pipeline: any[];
  performance_metrics: any;
  errors: string[];
}

interface RawDataViewerProps {
  trace: WorkflowTrace;
}

export const RawDataViewer: React.FC<RawDataViewerProps> = ({ trace }) => {
  const [viewMode, setViewMode] = useState<'formatted' | 'compact'>('formatted');
  const { toast } = useToast();

  const copyToClipboard = (data: any, label: string) => {
    const jsonString = JSON.stringify(data, null, viewMode === 'formatted' ? 2 : 0);
    navigator.clipboard.writeText(jsonString).then(() => {
      toast({
        title: "Copied to clipboard",
        description: `${label} data copied successfully`,
      });
    });
  };

  const downloadJson = (data: any, filename: string) => {
    const jsonString = JSON.stringify(data, null, 2);
    const blob = new Blob([jsonString], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    
    const link = document.createElement('a');
    link.href = url;
    link.download = `${filename}_${trace.trace_id.slice(0, 8)}.json`;
    link.click();
    
    URL.revokeObjectURL(url);
  };

  const formatJson = (data: any) => {
    return JSON.stringify(data, null, viewMode === 'formatted' ? 2 : 0);
  };

  const getDataSize = (data: any) => {
    const jsonString = JSON.stringify(data);
    const sizeInBytes = new Blob([jsonString]).size;
    
    if (sizeInBytes < 1024) return `${sizeInBytes} bytes`;
    if (sizeInBytes < 1024 * 1024) return `${(sizeInBytes / 1024).toFixed(1)} KB`;
    return `${(sizeInBytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const DataSection: React.FC<{
    title: string;
    data: any;
    filename: string;
    description?: string;
  }> = ({ title, data, filename, description }) => (
    <Card>
      <CardHeader>
        <div className="flex justify-between items-center">
          <div>
            <CardTitle className="text-base">{title}</CardTitle>
            {description && (
              <p className="text-sm text-muted-foreground mt-1">{description}</p>
            )}
          </div>
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="text-xs">
              {getDataSize(data)}
            </Badge>
            <Button
              variant="outline"
              size="sm"
              onClick={() => copyToClipboard(data, title)}
            >
              <Copy className="h-3 w-3" />
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => downloadJson(data, filename)}
            >
              <Download className="h-3 w-3" />
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <ScrollArea className="h-80 w-full rounded-md border">
          <pre className="p-4 text-xs font-mono">
            {formatJson(data)}
          </pre>
        </ScrollArea>
      </CardContent>
    </Card>
  );

  return (
    <div className="space-y-6">
      {/* Controls */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex justify-between items-center">
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium">View Mode:</span>
                <Button
                  variant={viewMode === 'formatted' ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setViewMode('formatted')}
                >
                  <Eye className="h-3 w-3 mr-1" />
                  Formatted
                </Button>
                <Button
                  variant={viewMode === 'compact' ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setViewMode('compact')}
                >
                  <Code className="h-3 w-3 mr-1" />
                  Compact
                </Button>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                onClick={() => copyToClipboard(trace, 'Complete trace')}
              >
                <Copy className="h-4 w-4 mr-2" />
                Copy All
              </Button>
              <Button
                variant="outline"
                onClick={() => downloadJson(trace, 'complete_trace')}
              >
                <Download className="h-4 w-4 mr-2" />
                Download All
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Data Sections */}
      <Tabs defaultValue="trace_info" className="w-full">
        <TabsList className="grid w-full grid-cols-7">
          <TabsTrigger value="trace_info">Trace Info</TabsTrigger>
          <TabsTrigger value="requests">Requests</TabsTrigger>
          <TabsTrigger value="nodes">Node Executions</TabsTrigger>
          <TabsTrigger value="entities">Entity Pipeline</TabsTrigger>
          <TabsTrigger value="workflow">Workflow State</TabsTrigger>
          <TabsTrigger value="result">Final Result</TabsTrigger>
          <TabsTrigger value="metrics">Metrics</TabsTrigger>
        </TabsList>

        <TabsContent value="trace_info" className="mt-6">
          <DataSection
            title="Trace Information"
            data={{
              trace_id: trace.trace_id,
              session_id: trace.session_id,
              user_query: trace.user_query,
              start_time: trace.start_time,
              end_time: trace.end_time,
              total_duration_ms: trace.total_duration_ms,
              status: trace.status,
              errors: trace.errors
            }}
            filename="trace_info"
            description="Basic trace metadata and timing information"
          />
        </TabsContent>

        <TabsContent value="requests" className="mt-6">
          <div className="space-y-4">
            <DataSection
              title="OpenWebUI Request"
              data={trace.openwebui_request}
              filename="openwebui_request"
              description="Original request from OpenWebUI interface"
            />
            <DataSection
              title="LiteLLM Request"
              data={trace.litellm_request}
              filename="litellm_request"
              description="Processed request sent to LiteLLM"
            />
          </div>
        </TabsContent>

        <TabsContent value="nodes" className="mt-6">
          <DataSection
            title="Node Executions"
            data={trace.node_executions}
            filename="node_executions"
            description="Complete workflow node execution timeline with inputs/outputs"
          />
        </TabsContent>

        <TabsContent value="entities" className="mt-6">
          <DataSection
            title="Entity Pipeline"
            data={trace.entity_pipeline}
            filename="entity_pipeline"
            description="Entity retrieval, scoring, and filtering pipeline stages"
          />
        </TabsContent>

        <TabsContent value="workflow" className="mt-6">
          <DataSection
            title="Workflow State"
            data={trace.workflow_state}
            filename="workflow_state"
            description="Internal workflow state and variables"
          />
        </TabsContent>

        <TabsContent value="result" className="mt-6">
          <DataSection
            title="Final Result"
            data={trace.final_result}
            filename="final_result"
            description="Complete workflow output returned to client"
          />
        </TabsContent>

        <TabsContent value="metrics" className="mt-6">
          <DataSection
            title="Performance Metrics"
            data={trace.performance_metrics}
            filename="performance_metrics"
            description="Timing, counts, and performance analysis data"
          />
        </TabsContent>
      </Tabs>

      {/* Quick Stats */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Raw Data Summary</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-4 gap-4 text-sm">
            <div>
              <div className="font-medium">{trace.node_executions.length}</div>
              <div className="text-muted-foreground">Node Executions</div>
            </div>
            <div>
              <div className="font-medium">{trace.entity_pipeline.length}</div>
              <div className="text-muted-foreground">Pipeline Stages</div>
            </div>
            <div>
              <div className="font-medium">{trace.errors.length}</div>
              <div className="text-muted-foreground">Errors</div>
            </div>
            <div>
              <div className="font-medium">{getDataSize(trace)}</div>
              <div className="text-muted-foreground">Total Size</div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};