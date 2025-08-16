import React, { useState } from 'react';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ScrollArea } from '@/components/ui/scroll-area';
import { ChevronDown, ChevronRight, Clock, CheckCircle2, AlertCircle, Play } from 'lucide-react';
import { cn } from '@/lib/utils';

interface NodeExecution {
  node_name: string;
  start_time: string;
  end_time?: string;
  duration_ms?: number;
  input_data: any;
  output_data: any;
  errors: string[];
  status: 'pending' | 'running' | 'success' | 'error';
}

interface ExecutionFlowProps {
  nodeExecutions: NodeExecution[];
}

const NodeCard: React.FC<{ node: NodeExecution; index: number }> = ({ node, index }) => {
  const [isOpen, setIsOpen] = useState(false);

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'success': return <CheckCircle2 className="h-4 w-4 text-green-600" />;
      case 'error': return <AlertCircle className="h-4 w-4 text-red-600" />;
      case 'running': return <Play className="h-4 w-4 text-blue-600" />;
      default: return <Clock className="h-4 w-4 text-gray-400" />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'success': return 'default';
      case 'error': return 'destructive';
      case 'running': return 'secondary';
      default: return 'outline';
    }
  };

  const formatDuration = (ms?: number) => {
    if (!ms) return 'N/A';
    return ms < 1000 ? `${ms.toFixed(1)}ms` : `${(ms / 1000).toFixed(2)}s`;
  };

  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <CollapsibleTrigger asChild>
        <Card className={cn(
          "cursor-pointer transition-colors hover:bg-accent/50",
          node.status === 'error' && "border-red-200 bg-red-50/50",
          node.status === 'success' && "border-green-200 bg-green-50/50"
        )}>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="flex items-center gap-2">
                  <span className="text-sm text-muted-foreground font-mono">
                    {(index + 1).toString().padStart(2, '0')}
                  </span>
                  {isOpen ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                </div>
                {getStatusIcon(node.status)}
                <span className="font-semibold">{node.node_name}</span>
                <Badge variant={getStatusColor(node.status)}>
                  {node.status}
                </Badge>
              </div>
              <div className="flex items-center gap-2">
                <Badge variant="outline" className="font-mono text-xs">
                  {formatDuration(node.duration_ms)}
                </Badge>
                <span className="text-xs text-muted-foreground">
                  {new Date(node.start_time).toLocaleTimeString()}
                </span>
              </div>
            </div>
            
            {node.errors.length > 0 && (
              <div className="mt-2">
                <Badge variant="destructive" className="text-xs">
                  {node.errors.length} error{node.errors.length !== 1 ? 's' : ''}
                </Badge>
              </div>
            )}
          </CardHeader>
        </Card>
      </CollapsibleTrigger>
      
      <CollapsibleContent>
        <Card className="mt-2 border-l-4 border-l-blue-200">
          <CardContent className="pt-4">
            <Tabs defaultValue="output" className="w-full">
              <TabsList className="grid w-full grid-cols-4">
                <TabsTrigger value="output">Output</TabsTrigger>
                <TabsTrigger value="input">Input</TabsTrigger>
                <TabsTrigger value="timing">Timing</TabsTrigger>
                {node.errors.length > 0 && <TabsTrigger value="errors">Errors</TabsTrigger>}
              </TabsList>
              
              <TabsContent value="output" className="mt-4">
                <ScrollArea className="h-60 w-full rounded-md border p-4">
                  <pre className="text-xs">
                    {JSON.stringify(node.output_data, null, 2)}
                  </pre>
                </ScrollArea>
              </TabsContent>
              
              <TabsContent value="input" className="mt-4">
                <ScrollArea className="h-60 w-full rounded-md border p-4">
                  <pre className="text-xs">
                    {JSON.stringify(node.input_data, null, 2)}
                  </pre>
                </ScrollArea>
              </TabsContent>
              
              <TabsContent value="timing" className="mt-4">
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span>Start Time:</span>
                    <span className="font-mono">{new Date(node.start_time).toLocaleString()}</span>
                  </div>
                  {node.end_time && (
                    <div className="flex justify-between">
                      <span>End Time:</span>
                      <span className="font-mono">{new Date(node.end_time).toLocaleString()}</span>
                    </div>
                  )}
                  <div className="flex justify-between">
                    <span>Duration:</span>
                    <span className="font-mono">{formatDuration(node.duration_ms)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Status:</span>
                    <Badge variant={getStatusColor(node.status)}>{node.status}</Badge>
                  </div>
                </div>
              </TabsContent>
              
              {node.errors.length > 0 && (
                <TabsContent value="errors" className="mt-4">
                  <div className="space-y-2">
                    {node.errors.map((error, idx) => (
                      <div key={idx} className="p-3 bg-red-50 border border-red-200 rounded-md">
                        <p className="text-sm text-red-800 font-mono">{error}</p>
                      </div>
                    ))}
                  </div>
                </TabsContent>
              )}
            </Tabs>
          </CardContent>
        </Card>
      </CollapsibleContent>
    </Collapsible>
  );
};

export const ExecutionFlow: React.FC<ExecutionFlowProps> = ({ nodeExecutions }) => {
  if (!nodeExecutions || nodeExecutions.length === 0) {
    return (
      <div className="text-center py-8 text-muted-foreground">
        <Clock className="h-12 w-12 mx-auto mb-4 opacity-50" />
        <p>No node executions recorded</p>
      </div>
    );
  }

  const totalDuration = nodeExecutions.reduce((sum, node) => sum + (node.duration_ms || 0), 0);
  const successCount = nodeExecutions.filter(node => node.status === 'success').length;
  const errorCount = nodeExecutions.filter(node => node.status === 'error').length;

  return (
    <div className="space-y-6">
      {/* Summary Stats */}
      <div className="grid grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-6">
            <div className="text-2xl font-bold">{nodeExecutions.length}</div>
            <p className="text-xs text-muted-foreground">Total Nodes</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="text-2xl font-bold text-green-600">{successCount}</div>
            <p className="text-xs text-muted-foreground">Successful</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="text-2xl font-bold text-red-600">{errorCount}</div>
            <p className="text-xs text-muted-foreground">Errors</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="text-2xl font-bold">
              {totalDuration < 1000 
                ? `${totalDuration.toFixed(0)}ms` 
                : `${(totalDuration / 1000).toFixed(1)}s`
              }
            </div>
            <p className="text-xs text-muted-foreground">Total Time</p>
          </CardContent>
        </Card>
      </div>

      {/* Node Execution Timeline */}
      <div className="space-y-3">
        {nodeExecutions.map((node, index) => (
          <NodeCard key={`${node.node_name}-${index}`} node={node} index={index} />
        ))}
      </div>
    </div>
  );
};