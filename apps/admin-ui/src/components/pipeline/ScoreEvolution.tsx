import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';

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

interface ScoreEvolutionProps {
  nodeExecutions: NodeExecution[];
  entityPipeline: EntityStageInfo[];
  enhancedPipeline?: EnhancedPipelineStage[];
}

export const ScoreEvolution: React.FC<ScoreEvolutionProps> = ({ nodeExecutions, entityPipeline, enhancedPipeline }) => {
  // Create a mapping of entity pipeline stages to their scores
  const entityScoreMap = new Map();
  if (entityPipeline && entityPipeline.length > 0) {
    entityPipeline.forEach(stage => {
      const scores = stage.entities
        .filter(entity => entity._score !== undefined)
        .map(entity => entity._score);
      
      entityScoreMap.set(stage.stage, {
        avgScore: scores.length > 0 ? scores.reduce((sum, score) => sum + score, 0) / scores.length : 0,
        maxScore: scores.length > 0 ? Math.max(...scores) : 0,
        minScore: scores.length > 0 ? Math.min(...scores) : 0,
        scores: scores
      });
    });
  }
  
  // Prefer enhanced pipeline data if available, with score injection
  const pipelineToUse = enhancedPipeline && enhancedPipeline.length > 0 ? enhancedPipeline : null;
  
  // Extract score evolution from enhanced pipeline with entity score injection
  const scoreEvolution = pipelineToUse 
    ? pipelineToUse.map(stage => {
        // Try to match enhanced stage to entity stage for score data
        const matchingEntityStage = entityScoreMap.get('vector_search') || entityScoreMap.get('final_selection');
        const hasScoreData = stage.stage_name === 'vector_search' || stage.stage_name === 'final_selection';
        const scoreData = hasScoreData && matchingEntityStage ? matchingEntityStage : {
          avgScore: 0,
          maxScore: 0,
          minScore: 0,
          scores: []
        };
        
        return {
          stage: stage.stage_name,
          entityCount: stage.output_count,
          avgScore: scoreData.avgScore,
          maxScore: scoreData.maxScore,
          minScore: scoreData.minScore,
          scores: scoreData.scores,
          duration: stage.duration_ms,
          stageType: stage.stage_type,
          hasRealScores: hasScoreData && scoreData.scores.length > 0
        };
      })
    : entityPipeline.map(stage => {
        const scores = stage.entities
          .filter(entity => entity._score !== undefined)
          .map(entity => entity._score);
        
        return {
          stage: stage.stage,
          entityCount: stage.entity_count,
          avgScore: scores.length > 0 ? scores.reduce((sum, score) => sum + score, 0) / scores.length : 0,
          maxScore: scores.length > 0 ? Math.max(...scores) : 0,
          minScore: scores.length > 0 ? Math.min(...scores) : 0,
          scores: scores,
          duration: 0,
          stageType: 'search',
          hasRealScores: scores.length > 0
        };
      });

  // Extract timing data from node executions
  const timingData = nodeExecutions
    .filter(node => node.duration_ms !== undefined)
    .map(node => ({
      nodeName: node.node_name,
      duration: node.duration_ms!,
      status: node.status
    }));

  const maxDuration = Math.max(...timingData.map(t => t.duration), 1);

  // Calculate score trends
  const getScoreTrend = (currentAvg: number, previousAvg: number) => {
    if (previousAvg === 0) return { icon: Minus, color: 'text-gray-500', change: 0 };
    
    const change = ((currentAvg - previousAvg) / previousAvg) * 100;
    
    if (change > 5) return { icon: TrendingUp, color: 'text-green-600', change };
    if (change < -5) return { icon: TrendingDown, color: 'text-red-600', change };
    return { icon: Minus, color: 'text-gray-500', change };
  };

  if (scoreEvolution.length === 0 && timingData.length === 0) {
    return (
      <div className="text-center py-8 text-muted-foreground">
        <TrendingUp className="h-12 w-12 mx-auto mb-4 opacity-50" />
        <p>No score evolution data available</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Score Evolution Timeline */}
      {scoreEvolution.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Entity Score Evolution</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {scoreEvolution.map((stage, stageIndex) => {
                const prevStage = stageIndex > 0 ? scoreEvolution[stageIndex - 1] : null;
                const trend = prevStage ? getScoreTrend(stage.avgScore, prevStage.avgScore) : null;
                
                return (
                  <div key={stage.stage} className="space-y-2">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="font-medium">{stage.stage.replace('_', ' ').toUpperCase()}</span>
                        {trend && (
                          <div className={`flex items-center gap-1 ${trend.color}`}>
                            <trend.icon className="h-4 w-4" />
                            <span className="text-sm">
                              {trend.change > 0 ? '+' : ''}{trend.change.toFixed(1)}%
                            </span>
                          </div>
                        )}
                      </div>
                      <div className="flex items-center gap-4">
                        <Badge variant="outline" className="font-mono text-xs">
                          {stage.entityCount} entities
                        </Badge>
                        <Badge 
                          variant={stage.hasRealScores ? "secondary" : "outline"} 
                          className="font-mono text-xs"
                        >
                          Avg: {stage.hasRealScores ? stage.avgScore.toFixed(3) : 'N/A'}
                        </Badge>
                        {!stage.hasRealScores && (
                          <Badge variant="outline" className="text-xs">
                            No scores
                          </Badge>
                        )}
                      </div>
                    </div>
                    
                    {stage.hasRealScores ? (
                      <div className="space-y-2">
                        <div className="flex justify-between text-xs text-muted-foreground">
                          <span>Min: {stage.minScore.toFixed(3)}</span>
                          <span>Max: {stage.maxScore.toFixed(3)}</span>
                        </div>
                        <Progress 
                          value={stage.avgScore * 100} 
                          className="h-2"
                        />
                        
                        {/* Score distribution */}
                        {stage.scores.length > 0 && (
                          <div className="text-xs text-muted-foreground">
                            <span>Score range: </span>
                            <span className="font-mono">
                              [{stage.minScore.toFixed(3)} - {stage.maxScore.toFixed(3)}]
                            </span>
                            <span className="ml-2">
                              (σ = {Math.sqrt(stage.scores.reduce((sum: number, score: number) => sum + Math.pow(score - stage.avgScore, 2), 0) / stage.scores.length).toFixed(3)})
                            </span>
                          </div>
                        )}
                      </div>
                    ) : (
                      <div className="py-2 text-xs text-muted-foreground italic">
                        This stage ({stage.stageType}) does not generate entity similarity scores
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Node Execution Performance */}
      {timingData.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Node Execution Performance</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {timingData.map((timing, index) => (
                <div key={index} className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="font-medium">{timing.nodeName}</span>
                    <div className="flex items-center gap-2">
                      <Badge 
                        variant={timing.status === 'success' ? 'default' : timing.status === 'error' ? 'destructive' : 'secondary'}
                      >
                        {timing.status}
                      </Badge>
                      <Badge variant="outline" className="font-mono text-xs">
                        {timing.duration < 1000 
                          ? `${timing.duration.toFixed(1)}ms` 
                          : `${(timing.duration / 1000).toFixed(2)}s`
                        }
                      </Badge>
                    </div>
                  </div>
                  <Progress 
                    value={(timing.duration / maxDuration) * 100} 
                    className="h-2"
                  />
                </div>
              ))}
            </div>
            
            <div className="mt-4 pt-4 border-t">
              <div className="grid grid-cols-3 gap-4 text-center">
                <div>
                  <div className="text-lg font-bold">
                    {timingData.reduce((sum, t) => sum + t.duration, 0).toFixed(1)}ms
                  </div>
                  <p className="text-xs text-muted-foreground">Total Time</p>
                </div>
                <div>
                  <div className="text-lg font-bold">
                    {(timingData.reduce((sum, t) => sum + t.duration, 0) / timingData.length).toFixed(1)}ms
                  </div>
                  <p className="text-xs text-muted-foreground">Average</p>
                </div>
                <div>
                  <div className="text-lg font-bold">
                    {Math.max(...timingData.map(t => t.duration)).toFixed(1)}ms
                  </div>
                  <p className="text-xs text-muted-foreground">Slowest</p>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Score Distribution Chart (simplified) */}
      {scoreEvolution.length > 1 && (
        <Card>
          <CardHeader>
            <CardTitle>Score Distribution Comparison</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {scoreEvolution.map((stage) => (
                <div key={stage.stage} className="flex items-center gap-4">
                  <div className="w-32 text-sm font-medium">
                    {stage.stage.replace('_', ' ')}
                  </div>
                  <div className="flex-1">
                    {stage.hasRealScores ? (
                      <div className="h-8 bg-gradient-to-r from-red-200 via-yellow-200 to-green-200 rounded relative overflow-hidden">
                        {/* Average score marker */}
                        <div 
                          className="absolute top-0 bottom-0 w-1 bg-blue-600"
                          style={{ left: `${stage.avgScore * 100}%` }}
                        />
                        {/* Score range */}
                        <div 
                          className="absolute top-1 bottom-1 bg-blue-500 opacity-30 rounded"
                          style={{ 
                            left: `${stage.minScore * 100}%`,
                            width: `${(stage.maxScore - stage.minScore) * 100}%`
                          }}
                        />
                      </div>
                    ) : (
                      <div className="h-8 bg-gray-100 rounded flex items-center justify-center text-xs text-muted-foreground">
                        No scores available
                      </div>
                    )}
                  </div>
                  <div className="w-20 text-xs text-right font-mono">
                    {stage.hasRealScores ? stage.avgScore.toFixed(3) : 'N/A'}
                  </div>
                </div>
              ))}
            </div>
            <div className="mt-4 text-xs text-muted-foreground">
              <div className="flex items-center gap-4">
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 bg-blue-600 rounded" />
                  <span>Average Score</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 bg-blue-500 opacity-30 rounded" />
                  <span>Score Range</span>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
};