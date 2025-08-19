import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Badge } from './ui/badge';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from './ui/collapsible';
import { 
  Search, 
  ChevronDown, 
  ChevronRight,
  Zap, 
  Target, 
  TrendingUp, 
  CheckCircle,
  Clock,
  BarChart3,
  Activity,
  ArrowRight,
  Brain,
  Info
} from 'lucide-react';
import { adminApi, type EntityDebugInfo, type StageResult } from '../lib/api';

// Helper functions
const formatScore = (score?: number): string => {
  if (score === undefined) return '-';
  return (score * 100).toFixed(1) + '%';
};

const formatRawScore = (score?: number): string => {
  if (score === undefined) return '-';
  return score.toFixed(3);
};

const getScoreColor = (score?: number): string => {
  if (!score) return 'text-gray-500';
  if (score >= 0.85) return 'text-green-600';
  if (score >= 0.75) return 'text-blue-600';  
  if (score >= 0.60) return 'text-yellow-600';
  return 'text-red-600';
};

const getScoreBadgeVariant = (score?: number) => {
  if (!score) return 'secondary';
  if (score >= 0.85) return 'default'; // green
  if (score >= 0.75) return 'secondary'; // blue
  if (score >= 0.60) return 'outline'; // yellow
  return 'destructive'; // red
};

// Stage icon mapping
const getStageIcon = (stage: string) => {
  switch (stage) {
    case 'cluster_search':
      return <Target className="w-4 h-4" />;
    case 'vector_fallback':
      return <Zap className="w-4 h-4" />;
    case 'reranking':
      return <TrendingUp className="w-4 h-4" />;
    case 'final_selection':
      return <CheckCircle className="w-4 h-4" />;
    default:
      return <Activity className="w-4 h-4" />;
  }
};

// Stage component
interface StageCardProps {
  stage: StageResult;
  isActive: boolean;
}

const StageCard: React.FC<StageCardProps> = ({ stage, isActive }) => (
  <Card className={`transition-all ${isActive ? 'ring-2 ring-blue-500 bg-blue-50' : ''}`}>
    <CardHeader className="pb-3">
      <CardTitle className="flex items-center justify-between text-sm">
        <div className="flex items-center gap-2">
          {getStageIcon(stage.stage)}
          <span>{stage.stage_name}</span>
        </div>
        <Badge variant="outline" className="text-xs">
          <Clock className="w-3 h-3 mr-1" />
          {stage.execution_time_ms.toFixed(1)}ms
        </Badge>
      </CardTitle>
    </CardHeader>
    <CardContent className="pt-0">
      <div className="flex items-center justify-between text-sm">
        <div className="flex items-center gap-4">
          <span className="text-muted-foreground">
            {stage.entities_in} → {stage.entities_out} entities
          </span>
        </div>
        {stage.entities_out !== stage.entities_in && (
          <Badge variant="secondary" className="text-xs">
            {stage.entities_out > stage.entities_in ? '+' : ''}{stage.entities_out - stage.entities_in}
          </Badge>
        )}
      </div>
      
      {/* Stage-specific metadata */}
      {stage.metadata && typeof stage.metadata === 'object' && Object.keys(stage.metadata).length > 0 && (
        <div className="mt-2 space-y-1">
          {Object.entries(stage.metadata).map(([key, value]) => (
            <div key={key} className="text-xs text-muted-foreground">
              <span className="font-medium">{key.replace(/_/g, ' ')}:</span> {
                Array.isArray(value) ? value.join(', ') : String(value)
              }
            </div>
          ))}
        </div>
      )}
    </CardContent>
  </Card>
);

// Entity score evolution component
interface EntityCardProps {
  entity: EntityDebugInfo;
}

const EntityCard: React.FC<EntityCardProps> = ({ entity }) => {
  const [isOpen, setIsOpen] = useState(false);
  
  return (
    <Card className="mb-3">
      <Collapsible open={isOpen} onOpenChange={setIsOpen}>
        <CollapsibleTrigger asChild>
          <CardHeader className="cursor-pointer hover:bg-gray-50 pb-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                {isOpen ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                <div>
                  <div className="font-medium text-sm">{entity.entity_name}</div>
                  <div className="text-xs text-muted-foreground">{entity.domain} • {entity.area}</div>
                </div>
              </div>
              
              <div className="flex items-center gap-2">
                {/* Score progression badges */}
                {entity.vector_score !== undefined && (
                  <Badge variant="outline" className="text-xs">
                    Vector: {formatScore(entity.vector_score)}
                  </Badge>
                )}
                
                {entity.final_score !== undefined && (
                  <Badge variant={getScoreBadgeVariant(entity.final_score)} className="text-xs">
                    Final: {formatScore(entity.final_score)}
                  </Badge>
                )}
                
                {entity.score_delta !== undefined && entity.score_delta !== 0 && (
                  <Badge variant={entity.score_delta > 0 ? 'default' : 'destructive'} className="text-xs">
                    {entity.score_delta > 0 ? '+' : ''}{(entity.score_delta * 100).toFixed(1)}%
                  </Badge>
                )}
                
                {entity.in_prompt !== undefined && (
                  <Badge variant={entity.in_prompt ? 'default' : 'secondary'} className="text-xs">
                    {entity.in_prompt ? 'In Prompt' : 'Filtered'}
                  </Badge>
                )}
              </div>
            </div>
          </CardHeader>
        </CollapsibleTrigger>
        
        <CollapsibleContent>
          <CardContent className="pt-0">
            {/* Score Evolution Timeline */}
            <div className="space-y-3">
              <h4 className="text-sm font-medium">Score Evolution</h4>
              
              {/* Pipeline stages */}
              <div className="space-y-2">
                {entity.cluster_score !== undefined && (
                  <div className="flex items-center justify-between py-1 px-2 rounded bg-gray-50">
                    <div className="flex items-center gap-2 text-sm">
                      <Target className="w-3 h-3 text-blue-500" />
                      <span>Cluster Search</span>
                      {entity.source_cluster && (
                        <Badge variant="outline" className="text-xs">{entity.source_cluster}</Badge>
                      )}
                    </div>
                    <span className={`text-sm font-mono ${getScoreColor(entity.cluster_score)}`}>
                      {formatScore(entity.cluster_score)}
                    </span>
                  </div>
                )}
                
                {entity.vector_score !== undefined && (
                  <div className="flex items-center justify-between py-1 px-2 rounded bg-gray-50">
                    <div className="flex items-center gap-2 text-sm">
                      <Zap className="w-3 h-3 text-purple-500" />
                      <span>Vector Search</span>
                    </div>
                    <span className={`text-sm font-mono ${getScoreColor(entity.vector_score)}`}>
                      {formatScore(entity.vector_score)}
                    </span>
                  </div>
                )}

                {/* Cross-encoder AI semantic analysis */}
                {entity.base_score !== undefined && (
                  <div className="flex flex-col gap-1 py-2 px-2 rounded bg-blue-50/50 border border-blue-200/50">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2 text-sm">
                        <Brain className="w-3 h-3 text-blue-600" />
                        <span className="font-medium">Cross-encoder AI</span>
                        {entity.cross_encoder_cache_hit && (
                          <Badge variant="outline" className="text-xs text-green-600 border-green-200">
                            Cache Hit
                          </Badge>
                        )}
                        {entity.used_fallback_matching && (
                          <Badge variant="outline" className="text-xs text-orange-600 border-orange-200">
                            Text Fallback
                          </Badge>
                        )}
                      </div>
                      <span className={`text-sm font-mono ${getScoreColor(entity.base_score)}`}>
                        {formatScore(entity.base_score)}
                      </span>
                    </div>
                    
                    {/* Cross-encoder details */}
                    <div className="flex items-center justify-between text-xs text-muted-foreground">
                      <span>Raw Score:</span>
                      <span className="font-mono">
                        {entity.cross_encoder_raw_score !== undefined ? 
                          formatRawScore(entity.cross_encoder_raw_score) : '-'
                        }
                      </span>
                    </div>
                    
                    {entity.cross_encoder_inference_ms !== undefined && entity.cross_encoder_inference_ms > 0 && (
                      <div className="flex items-center justify-between text-xs text-muted-foreground">
                        <span>Inference Time:</span>
                        <span className="font-mono">{entity.cross_encoder_inference_ms.toFixed(1)}ms</span>
                      </div>
                    )}
                    
                    {/* Cross-encoder input preview tooltip */}
                    {entity.cross_encoder_input_text && (
                      <div className="flex items-center gap-1 text-xs">
                        <Info className="w-3 h-3 text-blue-500" />
                        <span 
                          className="text-blue-600 cursor-help truncate max-w-[200px]"
                          title={`Cross-encoder input: ${entity.cross_encoder_input_text}`}
                        >
                          Input: {entity.cross_encoder_input_text.substring(0, 30)}...
                        </span>
                      </div>
                    )}
                  </div>
                )}
                
                {entity.final_score !== undefined && (
                  <div className="flex items-center justify-between py-1 px-2 rounded bg-gray-50">
                    <div className="flex items-center gap-2 text-sm">
                      <TrendingUp className="w-3 h-3 text-green-500" />
                      <span>Reranked</span>
                      {entity.context_boost !== undefined && entity.context_boost !== 0 && (
                        <Badge variant="outline" className="text-xs">
                          {entity.context_boost > 0 ? '+' : ''}{(entity.context_boost * 100).toFixed(1)}%
                        </Badge>
                      )}
                    </div>
                    <span className={`text-sm font-mono ${getScoreColor(entity.final_score)}`}>
                      {formatScore(entity.final_score)}
                    </span>
                  </div>
                )}
              </div>
              
              {/* Ranking factors breakdown */}
              {entity.ranking_factors && typeof entity.ranking_factors === 'object' && Object.keys(entity.ranking_factors).length > 0 && (
                <div className="mt-4">
                  <h5 className="text-xs font-medium text-muted-foreground mb-2">Ranking Factors</h5>
                  <div className="grid grid-cols-2 gap-2">
                    {Object.entries(entity.ranking_factors).map(([factor, value]) => (
                      <div key={factor} className="flex justify-between text-xs">
                        <span className="text-muted-foreground">{factor.replace(/_/g, ' ')}</span>
                        <span className={value > 0 ? 'text-green-600' : value < 0 ? 'text-red-600' : 'text-gray-500'}>
                          {value > 0 ? '+' : ''}{(value * 100).toFixed(1)}%
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              
              {/* Selection info */}
              <div className="mt-4 pt-3 border-t">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-muted-foreground">Status:</span>
                  <div className="flex items-center gap-2">
                    {entity.is_active !== undefined && (
                      <Badge variant={entity.is_active ? 'default' : 'secondary'} className="text-xs">
                        {entity.is_active ? 'Active' : 'Inactive'}
                      </Badge>
                    )}
                    {entity.selection_rank !== undefined && (
                      <Badge variant="outline" className="text-xs">
                        Rank #{entity.selection_rank}
                      </Badge>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </CardContent>
        </CollapsibleContent>
      </Collapsible>
    </Card>
  );
};

// Main SearchDebugger component
export const SearchDebugger: React.FC = () => {
  const { t } = useTranslation();
  const [query, setQuery] = useState('');
  const [threshold, setThreshold] = useState(0.7);
  const [limit, setLimit] = useState(20);
  const [selectedStage] = useState<string | null>(null);
  
  const { data: debugInfo, isLoading, refetch } = useQuery({
    queryKey: ['search-debug', { query, threshold, limit }],
    queryFn: () => adminApi.searchEntitiesDebug({
      query,
      include_debug: true,
      threshold,
      limit
    }),
    enabled: false, // Only run when manually triggered via refetch()
    staleTime: 0 // Always refetch for debug purposes
  });
  
  const handleSearch = () => {
    if (query.trim()) {
      refetch();
    }
  };
  
  return (
    <div className="space-y-6">
      {/* Search Controls */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Search className="w-5 h-5" />
            {t('searchPipelineDebugger')}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex gap-4">
            <div className="flex-1">
              <Input
                placeholder="Enter search query (e.g., 'hány fok van a nappaliban?')"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              />
            </div>
            <Button onClick={handleSearch} disabled={!query.trim() || isLoading}>
              {isLoading ? t('searchingText') : t('debugSearchButton')}
            </Button>
          </div>
          
          <div className="flex gap-4 items-center">
            <div className="flex items-center gap-2">
              <label className="text-sm text-muted-foreground">Threshold:</label>
              <Input
                type="number"
                min="0"
                max="1"
                step="0.05"
                value={threshold}
                onChange={(e) => setThreshold(parseFloat(e.target.value))}
                className="w-20"
              />
            </div>
            <div className="flex items-center gap-2">
              <label className="text-sm text-muted-foreground">Limit:</label>
              <Input
                type="number"
                min="5"
                max="50"
                value={limit}
                onChange={(e) => setLimit(parseInt(e.target.value))}
                className="w-20"
              />
            </div>
          </div>
        </CardContent>
      </Card>
      
      {/* Pipeline Results */}
      {debugInfo && (
        <div className="space-y-6">
          {/* Query Analysis */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Query Analysis</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                <div>
                  <span className="text-muted-foreground">Detected Scope:</span>
                  <div className="font-medium">{debugInfo.query_analysis?.detected_scope || 'Unknown'}</div>
                </div>
                <div>
                  <span className="text-muted-foreground">Confidence:</span>
                  <div className="font-medium">{((debugInfo.query_analysis?.scope_confidence || 0) * 100).toFixed(1)}%</div>
                </div>
                <div>
                  <span className="text-muted-foreground">Optimal K:</span>
                  <div className="font-medium">{debugInfo.query_analysis?.optimal_k || 'N/A'}</div>
                </div>
                <div>
                  <span className="text-muted-foreground">Total Time:</span>
                  <div className="font-medium">{debugInfo.total_execution_time_ms.toFixed(1)}ms</div>
                </div>
              </div>
              
              {debugInfo.query_analysis?.areas_mentioned && debugInfo.query_analysis.areas_mentioned.length > 0 && (
                <div className="mt-3">
                  <span className="text-muted-foreground text-sm">Areas Mentioned:</span>
                  <div className="flex gap-1 mt-1">
                    {debugInfo.query_analysis.areas_mentioned.map((area, idx) => (
                      <Badge key={idx} variant="outline" className="text-xs">{area}</Badge>
                    ))}
                  </div>
                </div>
              )}
              
              {debugInfo.query_analysis?.cluster_types && debugInfo.query_analysis.cluster_types.length > 0 && (
                <div className="mt-3">
                  <span className="text-muted-foreground text-sm">Cluster Types:</span>
                  <div className="flex gap-1 mt-1">
                    {debugInfo.query_analysis.cluster_types.map((type, idx) => (
                      <Badge key={idx} variant="secondary" className="text-xs">{type}</Badge>
                    ))}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
          
          {/* Pipeline Stages */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <BarChart3 className="w-5 h-5" />
                Pipeline Stages
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                {debugInfo.stage_results.map((stage, idx) => (
                  <div key={stage.stage} className="flex flex-col">
                    <StageCard 
                      stage={stage} 
                      isActive={selectedStage === stage.stage}
                    />
                    {idx < debugInfo.stage_results.length - 1 && (
                      <div className="flex justify-center py-2">
                        <ArrowRight className="w-4 h-4 text-muted-foreground" />
                      </div>
                    )}
                  </div>
                ))}
              </div>
              
              {/* Pipeline Efficiency Metrics */}
              {debugInfo.pipeline_efficiency && typeof debugInfo.pipeline_efficiency === 'object' && Object.keys(debugInfo.pipeline_efficiency).length > 0 && (
                <div className="mt-6 pt-4 border-t">
                  <h4 className="text-sm font-medium mb-3">Pipeline Efficiency</h4>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                    {Object.entries(debugInfo.pipeline_efficiency).map(([metric, value]) => (
                      <div key={metric}>
                        <span className="text-muted-foreground">{metric.replace(/_/g, ' ')}:</span>
                        <div className="font-medium">
                          {typeof value === 'number' ? (value * 100).toFixed(1) + '%' : String(value)}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
          
          {/* Entity Results */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Activity className="w-5 h-5" />
                  Entity Results
                </div>
                <Badge variant="outline">{debugInfo.entities.length} entities</Badge>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {debugInfo.entities
                  .sort((a, b) => (b.final_score || 0) - (a.final_score || 0))
                  .map((entity) => (
                    <EntityCard
                      key={entity.entity_id}
                      entity={entity}
                    />
                  ))}
              </div>
            </CardContent>
          </Card>
        </div>
      )}
      
      {/* Loading State */}
      {isLoading && (
        <Card>
          <CardContent className="py-8">
            <div className="flex items-center justify-center space-x-2">
              <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600"></div>
              <span>{t('runningPipelineDebug')}</span>
            </div>
          </CardContent>
        </Card>
      )}
      
      {/* Empty State */}
      {!debugInfo && !isLoading && (
        <Card>
          <CardContent className="py-8 text-center">
            <Search className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
            <h3 className="text-lg font-medium mb-2">{t('searchPipelineDebugger')}</h3>
            <p className="text-muted-foreground mb-4">
              {t('enterSearchQuery')}
            </p>
            <div className="text-sm text-muted-foreground space-y-1">
              <div>• See cluster vs vector search performance</div>
              <div>• Analyze reranking factor impact</div>
              <div>• Compare before/after similarity scores</div>
              <div>• Understand active/inactive entity selection</div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
};

export default SearchDebugger;