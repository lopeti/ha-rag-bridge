import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { ScrollArea } from '@/components/ui/scroll-area';
import { ChevronDown, ChevronRight, Database, Filter, TrendingUp } from 'lucide-react';
import { cn } from '@/lib/utils';

interface EntityStageInfo {
  stage: string;
  entity_count: number;
  entities: any[];
  scores: any;
  filters_applied: string[];
  metadata: any;
}

interface EnhancedPipelineStage {
  stage_name: string;
  stage_type: 'transform' | 'search' | 'boost' | 'rank' | 'filter';
  input_count: number;
  output_count: number;
  duration_ms: number;
  details?: any;
}

interface EntityPipelineProps {
  entityPipeline: EntityStageInfo[];
  enhancedPipeline?: EnhancedPipelineStage[];
}

const EntityStageCard: React.FC<{ stage: EntityStageInfo; index: number }> = ({ stage, index }) => {
  const [isOpen, setIsOpen] = useState(index === 0); // First stage open by default

  const getStageIcon = (stageName: string) => {
    switch (stageName.toLowerCase()) {
      case 'cluster_search': return <Database className="h-4 w-4 text-blue-600" />;
      case 'vector_fallback': return <TrendingUp className="h-4 w-4 text-purple-600" />;
      case 'reranking': return <Filter className="h-4 w-4 text-green-600" />;
      case 'final_selection': return <TrendingUp className="h-4 w-4 text-orange-600" />;
      default: return <Database className="h-4 w-4 text-gray-600" />;
    }
  };

  const getStageColor = (stageName: string) => {
    switch (stageName.toLowerCase()) {
      case 'cluster_search': return 'bg-blue-50 border-blue-200';
      case 'vector_fallback': return 'bg-purple-50 border-purple-200';
      case 'reranking': return 'bg-green-50 border-green-200';
      case 'final_selection': return 'bg-orange-50 border-orange-200';
      default: return 'bg-gray-50 border-gray-200';
    }
  };

  const formatScore = (score: number) => {
    return typeof score === 'number' ? score.toFixed(3) : 'N/A';
  };

  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <CollapsibleTrigger asChild>
        <Card className={cn(
          "cursor-pointer transition-colors hover:bg-accent/50",
          getStageColor(stage.stage)
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
                {getStageIcon(stage.stage)}
                <CardTitle className="text-base">{stage.stage.replace('_', ' ').toUpperCase()}</CardTitle>
              </div>
              <div className="flex items-center gap-2">
                <Badge variant="secondary" className="font-mono">
                  {stage.entity_count} entities
                </Badge>
                {stage.filters_applied.length > 0 && (
                  <Badge variant="outline" className="font-mono text-xs">
                    {stage.filters_applied.length} filters
                  </Badge>
                )}
              </div>
            </div>
          </CardHeader>
        </Card>
      </CollapsibleTrigger>

      <CollapsibleContent>
        <Card className="mt-2 border-l-4 border-l-blue-200">
          <CardContent className="pt-4">
            {/* Filters Applied */}
            {stage.filters_applied.length > 0 && (
              <div className="mb-4">
                <h4 className="text-sm font-semibold mb-2">Filters Applied:</h4>
                <div className="flex flex-wrap gap-2">
                  {stage.filters_applied.map((filter, idx) => (
                    <Badge key={idx} variant="outline" className="text-xs">
                      {filter}
                    </Badge>
                  ))}
                </div>
              </div>
            )}

            {/* Entities Table */}
            {stage.entities.length > 0 && (
              <div className="space-y-2">
                <h4 className="text-sm font-semibold">Entities ({stage.entity_count}):</h4>
                <ScrollArea className="h-80 w-full rounded-md border">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="w-12">#</TableHead>
                        <TableHead>Entity ID</TableHead>
                        <TableHead>Domain</TableHead>
                        <TableHead>Area</TableHead>
                        <TableHead className="text-right">Score</TableHead>
                        <TableHead>State</TableHead>
                        <TableHead>Flags</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {stage.entities.map((entity, idx) => (
                        <TableRow key={idx} className="text-xs">
                          <TableCell className="font-mono">{idx + 1}</TableCell>
                          <TableCell className="font-mono text-xs">
                            {entity.entity_id || 'N/A'}
                          </TableCell>
                          <TableCell>
                            <Badge variant="outline" className="text-xs">
                              {entity.domain || 'unknown'}
                            </Badge>
                          </TableCell>
                          <TableCell className="text-xs">
                            {entity.area || entity.area_name || 'No area'}
                          </TableCell>
                          <TableCell className="text-right font-mono">
                            {formatScore(entity._score)}
                          </TableCell>
                          <TableCell className="text-xs">
                            {entity.state || 'unknown'}
                          </TableCell>
                          <TableCell>
                            <div className="flex gap-1">
                              {entity._memory_boosted && (
                                <Badge variant="secondary" className="text-xs">MEM</Badge>
                              )}
                              {entity._cluster_context && (
                                <Badge variant="secondary" className="text-xs">CLUSTER</Badge>
                              )}
                              {entity._ranking_factors?.has_active_value > 0 && (
                                <Badge variant="default" className="text-xs">ACTIVE</Badge>
                              )}
                            </div>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </ScrollArea>
              </div>
            )}

            {/* Stage Metadata */}
            {stage.metadata && typeof stage.metadata === 'object' && Object.keys(stage.metadata).length > 0 && (
              <div className="mt-4">
                <h4 className="text-sm font-semibold mb-2">Stage Metadata:</h4>
                <ScrollArea className="h-32 w-full rounded-md border p-3">
                  <pre className="text-xs">
                    {JSON.stringify(stage.metadata, null, 2)}
                  </pre>
                </ScrollArea>
              </div>
            )}

            {/* Scores */}
            {stage.scores && typeof stage.scores === 'object' && Object.keys(stage.scores).length > 0 && (
              <div className="mt-4">
                <h4 className="text-sm font-semibold mb-2">Scores:</h4>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  {Object.entries(stage.scores).map(([key, value]) => (
                    <div key={key} className="flex justify-between p-2 bg-muted rounded">
                      <span>{key}:</span>
                      <span className="font-mono">{formatScore(value as number)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </CollapsibleContent>
    </Collapsible>
  );
};

export const EntityPipeline: React.FC<EntityPipelineProps> = ({ entityPipeline, enhancedPipeline }) => {
  // Show enhanced pipeline info if available, fallback to entity pipeline
  const hasEnhancedData = enhancedPipeline && enhancedPipeline.length > 0;
  const hasEntityData = entityPipeline && entityPipeline.length > 0;
  
  if (!hasEnhancedData && !hasEntityData) {
    return (
      <div className="text-center py-8 text-muted-foreground">
        <Database className="h-12 w-12 mx-auto mb-4 opacity-50" />
        <p>No entity pipeline data recorded</p>
      </div>
    );
  }

  // Calculate pipeline metrics
  const totalEntities = entityPipeline.reduce((sum, stage) => sum + stage.entity_count, 0);
  const finalEntities = entityPipeline.length > 0 ? entityPipeline[entityPipeline.length - 1].entity_count : 0;
  const reductionRate = totalEntities > 0 ? ((totalEntities - finalEntities) / totalEntities * 100) : 0;

  return (
    <div className="space-y-6">
      {/* Enhanced Pipeline Summary */}
      {hasEnhancedData && (
        <Card className="bg-blue-50 border-blue-200">
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Database className="h-4 w-4 text-blue-600" />
              Enhanced Pipeline Overview ({enhancedPipeline!.length} stages)
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-5 gap-4 text-sm">
              {enhancedPipeline!.map((stage, index) => (
                <div key={index} className="text-center">
                  <div className="font-semibold text-xs">{stage.stage_name.replace(/_/g, ' ')}</div>
                  <div className="text-xs text-muted-foreground">{stage.stage_type}</div>
                  <div className="text-xs">
                    {stage.input_count} → {stage.output_count}
                  </div>
                  <div className="text-xs">{stage.duration_ms.toFixed(0)}ms</div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
      
      {/* Entity Pipeline Summary */}
      {hasEntityData && (
        <div className="grid grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-6">
            <div className="text-2xl font-bold">{entityPipeline.length}</div>
            <p className="text-xs text-muted-foreground">Pipeline Stages</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="text-2xl font-bold">{totalEntities}</div>
            <p className="text-xs text-muted-foreground">Total Processed</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="text-2xl font-bold">{finalEntities}</div>
            <p className="text-xs text-muted-foreground">Final Output</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="text-2xl font-bold">{reductionRate.toFixed(1)}%</div>
            <p className="text-xs text-muted-foreground">Reduction Rate</p>
          </CardContent>
        </Card>
        </div>
      )}

      {/* Pipeline Stages */}
      {hasEntityData && (
        <div className="space-y-3">
          {entityPipeline.map((stage, index) => (
            <EntityStageCard key={`${stage.stage}-${index}`} stage={stage} index={index} />
          ))}
        </div>
      )}

      {/* Pipeline Flow Visualization */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Entity Flow</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between">
            {entityPipeline.map((stage, index) => (
              <React.Fragment key={stage.stage}>
                <div className="text-center">
                  <div className="w-16 h-16 rounded-full bg-gradient-to-r from-blue-500 to-purple-600 flex items-center justify-center text-white font-bold">
                    {stage.entity_count}
                  </div>
                  <p className="text-xs mt-2 max-w-20 text-center">{stage.stage.replace('_', ' ')}</p>
                </div>
                {index < entityPipeline.length - 1 && (
                  <div className="flex-1 h-1 bg-gradient-to-r from-blue-300 to-purple-300 mx-2" />
                )}
              </React.Fragment>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
};