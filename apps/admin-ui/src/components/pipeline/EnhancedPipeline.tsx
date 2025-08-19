import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { 
  ChevronDown, 
  ChevronRight, 
  MessageSquare, 
  Search, 
  TrendingUp, 
  Brain, 
  Filter, 
  Clock,
  ArrowRight,
  Zap,
  Database
} from 'lucide-react';
import { cn } from '@/lib/utils';

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

interface EnhancedPipelineProps {
  enhancedPipeline: EnhancedPipelineStage[];
}

const EnhancedStageCard: React.FC<{ stage: EnhancedPipelineStage; index: number }> = ({ stage, index }) => {
  const [isOpen, setIsOpen] = useState(index === 0); // First stage open by default

  const getStageIcon = (stageName: string, stageType: string) => {
    switch (stageName.toLowerCase()) {
      case 'query_rewriting': return <MessageSquare className="h-4 w-4 text-blue-600" />;
      case 'conversation_summary': return <Brain className="h-4 w-4 text-purple-600" />;
      case 'async_memory_processing': return <Database className="h-4 w-4 text-cyan-600" />;
      case 'cluster_search': return <Search className="h-4 w-4 text-green-600" />;
      case 'vector_search': return <Search className="h-4 w-4 text-indigo-600" />;
      case 'memory_boost': return <Zap className="h-4 w-4 text-yellow-600" />;
      case 'reranking': return <TrendingUp className="h-4 w-4 text-orange-600" />;
      case 'final_selection': return <Filter className="h-4 w-4 text-red-600" />;
      default: {
        switch (stageType) {
          case 'transform': return <MessageSquare className="h-4 w-4 text-blue-600" />;
          case 'search': return <Search className="h-4 w-4 text-green-600" />;
          case 'boost': return <Zap className="h-4 w-4 text-yellow-600" />;
          case 'rank': return <TrendingUp className="h-4 w-4 text-orange-600" />;
          case 'filter': return <Filter className="h-4 w-4 text-red-600" />;
          default: return <Clock className="h-4 w-4 text-gray-600" />;
        }
      }
    }
  };

  const getStageColor = (stageName: string, stageType: string) => {
    switch (stageName.toLowerCase()) {
      case 'query_rewriting': return 'bg-blue-50 border-blue-200';
      case 'conversation_summary': return 'bg-purple-50 border-purple-200';
      case 'async_memory_processing': return 'bg-cyan-50 border-cyan-200';
      case 'cluster_search': return 'bg-green-50 border-green-200';
      case 'vector_search': return 'bg-indigo-50 border-indigo-200';
      case 'memory_boost': return 'bg-yellow-50 border-yellow-200';
      case 'reranking': return 'bg-orange-50 border-orange-200';
      case 'final_selection': return 'bg-red-50 border-red-200';
      default: {
        switch (stageType) {
          case 'transform': return 'bg-blue-50 border-blue-200';
          case 'search': return 'bg-green-50 border-green-200';
          case 'boost': return 'bg-yellow-50 border-yellow-200';
          case 'rank': return 'bg-orange-50 border-orange-200';
          case 'filter': return 'bg-red-50 border-red-200';
          default: return 'bg-gray-50 border-gray-200';
        }
      }
    }
  };

  const getStageTypeColor = (stageType: string) => {
    switch (stageType) {
      case 'transform': return 'bg-blue-100 text-blue-800';
      case 'search': return 'bg-green-100 text-green-800';
      case 'boost': return 'bg-yellow-100 text-yellow-800';
      case 'rank': return 'bg-orange-100 text-orange-800';
      case 'filter': return 'bg-red-100 text-red-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };


  const renderStageDetails = () => {
    if (!stage.details) return null;

    return (
      <div className="space-y-4">
        {/* Query Rewriting Details */}
        {stage.details.query_rewrite && (
          <div className="p-4 bg-blue-50 rounded-lg border border-blue-200">
            <h5 className="font-semibold text-sm mb-2 flex items-center gap-2">
              <MessageSquare className="h-4 w-4 text-blue-600" />
              Query Rewriting
            </h5>
            <div className="space-y-2 text-sm">
              <div className="flex items-center gap-2">
                <span className="font-medium">Original:</span>
                <span className="font-mono bg-white px-2 py-1 rounded border">
                  {stage.details.query_rewrite.original}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span className="font-medium">Rewritten:</span>
                <span className="font-mono bg-white px-2 py-1 rounded border">
                  {stage.details.query_rewrite.rewritten}
                </span>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <span className="font-medium">Method:</span>
                  <Badge variant="outline" className="ml-2">
                    {stage.details.query_rewrite.method}
                  </Badge>
                </div>
                <div>
                  <span className="font-medium">Confidence:</span>
                  <Badge variant="secondary" className="ml-2">
                    {(stage.details.query_rewrite.confidence * 100).toFixed(0)}%
                  </Badge>
                </div>
              </div>
              {stage.details.query_rewrite.coreferences_resolved?.length > 0 && (
                <div>
                  <span className="font-medium">Resolved:</span>
                  <div className="flex gap-1 mt-1">
                    {stage.details.query_rewrite.coreferences_resolved?.map((ref, idx) => (
                      <Badge key={idx} variant="outline" className="text-xs">
                        {ref}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
              {stage.details.query_rewrite.reasoning && (
                <div>
                  <span className="font-medium">Reasoning:</span>
                  <p className="text-xs text-muted-foreground mt-1">
                    {stage.details.query_rewrite.reasoning}
                  </p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Conversation Summary Details */}
        {stage.details.conversation_summary && (
          <div className="p-4 bg-purple-50 rounded-lg border border-purple-200">
            <h5 className="font-semibold text-sm mb-2 flex items-center gap-2">
              <Brain className="h-4 w-4 text-purple-600" />
              Conversation Summary
            </h5>
            <div className="space-y-2 text-sm">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <span className="font-medium">Topic:</span>
                  <Badge variant="secondary" className="ml-2">
                    {stage.details.conversation_summary.topic}
                  </Badge>
                </div>
                <div>
                  <span className="font-medium">Focus:</span>
                  <Badge variant="outline" className="ml-2">
                    {stage.details.conversation_summary.current_focus || 'none'}
                  </Badge>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <span className="font-medium">Intent:</span>
                  <Badge variant="outline" className="ml-2">
                    {stage.details.conversation_summary.intent_pattern}
                  </Badge>
                </div>
                <div>
                  <span className="font-medium">Confidence:</span>
                  <Badge variant="secondary" className="ml-2">
                    {(stage.details.conversation_summary.confidence * 100).toFixed(0)}%
                  </Badge>
                </div>
              </div>
              {stage.details.conversation_summary.topic_domains?.length > 0 && (
                <div>
                  <span className="font-medium">Domains:</span>
                  <div className="flex gap-1 mt-1">
                    {stage.details.conversation_summary.topic_domains?.map((domain, idx) => (
                      <Badge key={idx} variant="outline" className="text-xs">
                        {domain}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
              <div>
                <span className="font-medium">Reasoning:</span>
                <p className="text-xs text-muted-foreground mt-1">
                  {stage.details.conversation_summary.reasoning}
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Memory Stage Details */}
        {stage.details.memory_stage && (
          <div className="p-4 bg-cyan-50 rounded-lg border border-cyan-200">
            <h5 className="font-semibold text-sm mb-2 flex items-center gap-2">
              <Database className="h-4 w-4 text-cyan-600" />
              Async Memory Processing
            </h5>
            <div className="space-y-3 text-sm">
              {/* Cache Status and Processing Source */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <span className="font-medium">Cache:</span>
                  <Badge 
                    variant={stage.details.memory_stage.cache_status === 'hit' ? 'default' : 'secondary'} 
                    className={cn(
                      "ml-2",
                      stage.details.memory_stage.cache_status === 'hit' ? 'bg-green-100 text-green-800' : 
                      stage.details.memory_stage.cache_status === 'miss' ? 'bg-orange-100 text-orange-800' : 
                      'bg-yellow-100 text-yellow-800'
                    )}
                  >
                    {stage.details.memory_stage.cache_status}
                  </Badge>
                </div>
                <div>
                  <span className="font-medium">Source:</span>
                  <Badge variant="outline" className="ml-2">
                    {stage.details.memory_stage.processing_source}
                  </Badge>
                </div>
              </div>

              {/* Background Processing Status */}
              {stage.details.memory_stage.background_pending && (
                <div className="flex items-center gap-2 p-2 bg-yellow-50 rounded border border-yellow-200">
                  <Clock className="h-4 w-4 text-yellow-600" />
                  <span className="text-yellow-800 text-xs">Background LLM summary in progress</span>
                </div>
              )}

              {/* Entity Boosts */}
              {Object.keys(stage.details.memory_stage.entity_boosts).length > 0 && (
                <div>
                  <span className="font-medium">Entity Boosts:</span>
                  <div className="grid grid-cols-1 gap-1 mt-1 max-h-32 overflow-y-auto">
                    {Object.entries(stage.details.memory_stage.entity_boosts).map(([entityId, boost], idx) => (
                      <div key={idx} className="flex justify-between items-center text-xs bg-white p-2 rounded border">
                        <span className="font-mono truncate flex-1 pr-2">{entityId}</span>
                        <Badge 
                          variant="secondary" 
                          className={cn(
                            "text-xs",
                            boost > 1.5 ? 'bg-green-100 text-green-800' :
                            boost > 1.2 ? 'bg-blue-100 text-blue-800' :
                            'bg-gray-100 text-gray-800'
                          )}
                        >
                          {boost.toFixed(2)}x
                        </Badge>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Quick Patterns */}
              {stage.details.memory_stage.quick_patterns && (
                <div>
                  <span className="font-medium">Quick Patterns:</span>
                  <div className="grid grid-cols-3 gap-4 mt-2">
                    <div>
                      <span className="text-xs text-muted-foreground">Domains:</span>
                      <div className="flex gap-1 mt-1">
                        {(stage.details.memory_stage.quick_patterns.domains || []).map((domain, idx) => (
                          <Badge key={idx} variant="outline" className="text-xs">
                            {domain}
                          </Badge>
                        ))}
                        {(!stage.details.memory_stage.quick_patterns.domains || stage.details.memory_stage.quick_patterns.domains.length === 0) && (
                          <span className="text-xs text-muted-foreground">None detected</span>
                        )}
                      </div>
                    </div>
                    <div>
                      <span className="text-xs text-muted-foreground">Areas:</span>
                      <div className="flex gap-1 mt-1">
                        {(stage.details.memory_stage.quick_patterns.areas || []).map((area, idx) => (
                          <Badge key={idx} variant="outline" className="text-xs">
                            {area}
                          </Badge>
                        ))}
                        {(!stage.details.memory_stage.quick_patterns.areas || stage.details.memory_stage.quick_patterns.areas.length === 0) && (
                          <span className="text-xs text-muted-foreground">None detected</span>
                        )}
                      </div>
                    </div>
                    <div>
                      <span className="text-xs text-muted-foreground">Processing:</span>
                      <Badge variant="secondary" className="ml-1 text-xs">
                        {stage.details.memory_stage.quick_patterns.processing_time_ms || 0}ms
                      </Badge>
                    </div>
                  </div>
                </div>
              )}

              {/* Pattern Detection Count */}
              <div>
                <span className="font-medium">Patterns Detected:</span>
                <Badge variant="secondary" className="ml-2">
                  {stage.details.memory_stage.patterns_detected}
                </Badge>
              </div>
            </div>
          </div>
        )}

        {/* Vector Search Details */}
        {stage.details.vector_search && (
          <div className="p-4 bg-indigo-50 rounded-lg border border-indigo-200">
            <h5 className="font-semibold text-sm mb-2 flex items-center gap-2">
              <Search className="h-4 w-4 text-indigo-600" />
              Vector Search
            </h5>
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <span className="font-medium">Backend:</span>
                <Badge variant="outline" className="ml-2">
                  {stage.details.vector_search.backend}
                </Badge>
              </div>
              <div>
                <span className="font-medium">Dimensions:</span>
                <Badge variant="secondary" className="ml-2">
                  {stage.details.vector_search.vector_dimension}
                </Badge>
              </div>
              <div>
                <span className="font-medium">K-value:</span>
                <Badge variant="outline" className="ml-2">
                  {stage.details.vector_search.k_value}
                </Badge>
              </div>
              <div>
                <span className="font-medium">Retrieved:</span>
                <Badge variant="secondary" className="ml-2">
                  {stage.details.vector_search.total_entities}
                </Badge>
              </div>
            </div>
          </div>
        )}

        {/* Cluster Search Details */}
        {stage.details.cluster_search && (
          <div className="p-4 bg-green-50 rounded-lg border border-green-200">
            <h5 className="font-semibold text-sm mb-2 flex items-center gap-2">
              <Search className="h-4 w-4 text-green-600" />
              Cluster Search
            </h5>
            <div className="space-y-2 text-sm">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <span className="font-medium">Scope:</span>
                  <Badge variant="outline" className="ml-2">
                    {stage.details.cluster_search.scope}
                  </Badge>
                </div>
                <div>
                  <span className="font-medium">K-value:</span>
                  <Badge variant="secondary" className="ml-2">
                    {stage.details.cluster_search.optimal_k}
                  </Badge>
                </div>
              </div>
              <div>
                <span className="font-medium">Cluster Types:</span>
                <div className="flex gap-1 mt-1">
                  {stage.details.cluster_search.cluster_types?.map((type, idx) => (
                    <Badge key={idx} variant="outline" className="text-xs">
                      {type}
                    </Badge>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Memory Boost Details */}
        {stage.details.memory_boost && (
          <div className="p-4 bg-yellow-50 rounded-lg border border-yellow-200">
            <h5 className="font-semibold text-sm mb-2 flex items-center gap-2">
              <Zap className="h-4 w-4 text-yellow-600" />
              Memory Boost
            </h5>
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <span className="font-medium">Memory Entities:</span>
                <Badge variant="secondary" className="ml-2">
                  {stage.details.memory_boost.memory_entities_count}
                </Badge>
              </div>
              <div>
                <span className="font-medium">Boosted:</span>
                <Badge variant="outline" className="ml-2">
                  {stage.details.memory_boost.boosted_entities}
                </Badge>
              </div>
            </div>
          </div>
        )}

        {/* Reranking Details */}
        {stage.details.reranking && (
          <div className="p-4 bg-orange-50 rounded-lg border border-orange-200">
            <h5 className="font-semibold text-sm mb-2 flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-orange-600" />
              Reranking
            </h5>
            <div className="space-y-2 text-sm">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <span className="font-medium">Algorithm:</span>
                  <Badge variant="outline" className="ml-2">
                    {stage.details.reranking.algorithm}
                  </Badge>
                </div>
                <div>
                  <span className="font-medium">Formatter:</span>
                  <Badge variant="secondary" className="ml-2">
                    {stage.details.reranking.formatter_selected}
                  </Badge>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <span className="font-medium">Score Range:</span>
                  <span className="font-mono text-xs ml-2">
                    {stage.details.reranking.score_range?.min?.toFixed(1) || '0.0'} - {stage.details.reranking.score_range?.max?.toFixed(1) || '0.0'}
                  </span>
                </div>
                <div>
                  <span className="font-medium">Target:</span>
                  <Badge variant="outline" className="ml-2">
                    {stage.details.reranking.target_entities}
                  </Badge>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <span className="font-medium">Primary:</span>
                  <Badge variant="secondary" className="ml-2">
                    {stage.details.reranking.primary_count}
                  </Badge>
                </div>
                <div>
                  <span className="font-medium">Related:</span>
                  <Badge variant="outline" className="ml-2">
                    {stage.details.reranking.related_count}
                  </Badge>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    );
  };

  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <CollapsibleTrigger asChild>
        <Card className={cn(
          "cursor-pointer transition-colors hover:bg-accent/50",
          getStageColor(stage.stage_name, stage.stage_type)
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
                {getStageIcon(stage.stage_name, stage.stage_type)}
                <CardTitle className="text-base">
                  {stage.stage_name.replace(/_/g, ' ').toUpperCase()}
                </CardTitle>
              </div>
              <div className="flex items-center gap-2">
                <Badge variant="secondary" className={cn("font-mono text-xs", getStageTypeColor(stage.stage_type))}>
                  {stage.stage_type}
                </Badge>
                <Badge variant="outline" className="font-mono text-xs">
                  <Clock className="h-3 w-3 mr-1" />
                  {formatDuration(stage.duration_ms)}
                </Badge>
                <div className="flex items-center gap-1 text-sm font-mono">
                  <span>{stage.input_count}</span>
                  <ArrowRight className="h-3 w-3 text-muted-foreground" />
                  <span>{stage.output_count}</span>
                </div>
              </div>
            </div>
          </CardHeader>
        </Card>
      </CollapsibleTrigger>

      <CollapsibleContent>
        <Card className="mt-2 border-l-4 border-l-blue-200">
          <CardContent className="pt-4">
            {renderStageDetails()}
          </CardContent>
        </Card>
      </CollapsibleContent>
    </Collapsible>
  );
};

const formatDuration = (ms: number): string => {
  if (ms < 1000) return `${ms.toFixed(0)}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
};

export const EnhancedPipeline: React.FC<EnhancedPipelineProps> = ({ enhancedPipeline }) => {
  if (!enhancedPipeline || enhancedPipeline.length === 0) {
    return (
      <div className="text-center py-8 text-muted-foreground">
        <Brain className="h-12 w-12 mx-auto mb-4 opacity-50" />
        <p>No enhanced pipeline data recorded</p>
      </div>
    );
  }

  // Calculate pipeline metrics
  const totalDuration = enhancedPipeline.reduce((sum, stage) => sum + stage.duration_ms, 0);
  const initialEntities = enhancedPipeline.length > 0 ? enhancedPipeline[0].input_count : 0;
  const finalEntities = enhancedPipeline.length > 0 ? enhancedPipeline[enhancedPipeline.length - 1].output_count : 0;
  const efficiencyRate = initialEntities > 0 ? (finalEntities / initialEntities * 100) : 0;

  return (
    <div className="space-y-6">
      {/* Pipeline Summary */}
      <div className="grid grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-6">
            <div className="text-2xl font-bold">{enhancedPipeline.length}</div>
            <p className="text-xs text-muted-foreground">Pipeline Stages</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="text-2xl font-bold">{formatDuration(totalDuration)}</div>
            <p className="text-xs text-muted-foreground">Total Duration</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="text-2xl font-bold">{initialEntities} → {finalEntities}</div>
            <p className="text-xs text-muted-foreground">Entity Flow</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="text-2xl font-bold">{efficiencyRate.toFixed(1)}%</div>
            <p className="text-xs text-muted-foreground">Selection Rate</p>
          </CardContent>
        </Card>
      </div>

      {/* Pipeline Stages */}
      <div className="space-y-3">
        {enhancedPipeline.map((stage, index) => (
          <EnhancedStageCard key={`${stage.stage_name}-${index}`} stage={stage} index={index} />
        ))}
      </div>

      {/* Pipeline Flow Visualization */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Enhanced Pipeline Flow</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between">
            {enhancedPipeline.map((stage, index) => (
              <React.Fragment key={stage.stage_name}>
                <div className="text-center">
                  <div className="w-20 h-20 rounded-full bg-gradient-to-r from-blue-500 to-purple-600 flex flex-col items-center justify-center text-white font-bold text-xs">
                    <div className="text-lg">{stage.output_count}</div>
                    <div className="text-xs opacity-75">{formatDuration(stage.duration_ms)}</div>
                  </div>
                  <p className="text-xs mt-2 max-w-24 text-center">
                    {stage.stage_name.replace(/_/g, ' ')}
                  </p>
                  <Badge variant="outline" className="text-xs mt-1">
                    {stage.stage_type}
                  </Badge>
                </div>
                {index < enhancedPipeline.length - 1 && (
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