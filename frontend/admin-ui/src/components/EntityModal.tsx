import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from './ui/dialog';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/tabs';
import { Skeleton } from './ui/skeleton';
import { RefreshCw, Lightbulb, Thermometer, Zap, Wifi, Camera, Home, Gauge, Power, Info, Wrench, Bug, Settings } from 'lucide-react';
import { adminApi, type PromptFormat } from '../lib/api';

interface EntityModalProps {
  entity: any;
  isOpen: boolean;
  onClose: () => void;
}

// Domain-specific styling helper (imported from Entities.tsx)
function getDomainInfo(domain: string, deviceClass?: string) {
  const domainConfigs = {
    light: { icon: Lightbulb, color: 'text-yellow-600', bgColor: 'bg-yellow-50 border-yellow-200' },
    sensor: { icon: Thermometer, color: 'text-blue-600', bgColor: 'bg-blue-50 border-blue-200' },
    switch: { icon: Zap, color: 'text-green-600', bgColor: 'bg-green-50 border-green-200' },
    binary_sensor: { icon: Wifi, color: 'text-purple-600', bgColor: 'bg-purple-50 border-purple-200' },
    camera: { icon: Camera, color: 'text-red-600', bgColor: 'bg-red-50 border-red-200' },
    climate: { icon: Home, color: 'text-orange-600', bgColor: 'bg-orange-50 border-orange-200' },
    cover: { icon: Home, color: 'text-gray-600', bgColor: 'bg-gray-50 border-gray-200' },
    default: { icon: Gauge, color: 'text-gray-600', bgColor: 'bg-gray-50 border-gray-200' }
  };

  // Special handling for power/energy sensors
  if (domain === 'sensor' && (deviceClass?.includes('power') || deviceClass?.includes('energy'))) {
    return { icon: Power, color: 'text-green-600', bgColor: 'bg-green-50 border-green-200' };
  }

  return domainConfigs[domain as keyof typeof domainConfigs] || domainConfigs.default;
}

// Friendly name quality analyzer (imported from Entities.tsx)
function analyzeFriendlyNameQuality(friendlyName: string, entityId: string, deviceName?: string) {
  const issues = [];
  const suggestions = [];
  let score = 100;

  // Check if it's too generic
  const genericTerms = ['power', 'sensor', 'switch', 'light', 'entity', 'device'];
  if (genericTerms.some(term => friendlyName.toLowerCase().includes(term))) {
    issues.push('🔴 Túl általános név');
    score -= 30;
    if (deviceName) {
      suggestions.push(`Próbáld: "${deviceName} - ${friendlyName}"`);
    }
  }

  // Check if it's just the entity ID
  const entityName = entityId.split('.')[1]?.replace(/_/g, ' ');
  if (friendlyName.toLowerCase() === entityName?.toLowerCase()) {
    issues.push('🟡 Csak entity ID alapú');
    score -= 20;
  }

  // Check length
  if (friendlyName.length < 5) {
    issues.push('🟠 Túl rövid');
    score -= 15;
  }

  // Check if it contains area info
  const commonAreas = ['nappali', 'konyha', 'hálószoba', 'fürdő'];
  const hasAreaInfo = commonAreas.some(area => 
    friendlyName.toLowerCase().includes(area) || entityId.toLowerCase().includes(area)
  );
  
  if (!hasAreaInfo) {
    issues.push('🟡 Nincs terület info');
    score -= 10;
  }

  return {
    score: Math.max(0, score),
    issues,
    suggestions,
    quality: score >= 80 ? 'good' : score >= 60 ? 'medium' : 'poor'
  };
}

export function EntityModal({ entity, isOpen, onClose }: EntityModalProps) {
  const [activeTab, setActiveTab] = useState('overview');

  // Query for prompt format
  const { data: promptFormat, isLoading: promptLoading, refetch: refetchPrompt } = useQuery<PromptFormat>({
    queryKey: ['entity-prompt-format', entity?.id],
    queryFn: () => adminApi.getEntityPromptFormat(entity!.id),
    enabled: isOpen && !!entity?.id,
    staleTime: 30000, // Cache for 30 seconds
  });

  if (!entity) return null;

  // Smart friendly name fallback
  const displayName = entity.friendly_name || 
    (entity.id ? entity.id.split('.')[1]?.replace(/_/g, ' ') : 'Unknown Entity');

  // Get domain styling
  const domainInfo = getDomainInfo(entity.domain, entity.device_class);
  const DomainIcon = domainInfo.icon;
  
  // Analyze friendly name quality
  const qualityAnalysis = analyzeFriendlyNameQuality(
    displayName, 
    entity.id, 
    entity.device_name
  );

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-hidden flex flex-col">
        <DialogHeader className="flex-shrink-0">
          <div className="flex items-center gap-3">
            <div className={`p-3 rounded-full bg-white ${domainInfo.color} border-2`}>
              <DomainIcon size={24} />
            </div>
            <div>
              <DialogTitle className="text-xl">{displayName}</DialogTitle>
              <DialogDescription className="flex items-center gap-2 mt-1">
                <span>{entity.domain} · {entity.area_name || entity.area || 'Unknown Area'}</span>
                {entity.state && (
                  <Badge variant="outline" className="text-xs">
                    {entity.state}
                  </Badge>
                )}
                <Badge 
                  variant="outline" 
                  className={`text-xs ${
                    qualityAnalysis.quality === 'good' ? 'bg-green-100 text-green-700 border-green-300' :
                    qualityAnalysis.quality === 'medium' ? 'bg-yellow-100 text-yellow-700 border-yellow-300' :
                    'bg-red-100 text-red-700 border-red-300'
                  }`}
                >
                  {qualityAnalysis.score}% 
                  {qualityAnalysis.quality === 'good' ? ' ✅' : 
                   qualityAnalysis.quality === 'medium' ? ' ⚠️' : ' ❌'}
                </Badge>
              </DialogDescription>
            </div>
          </div>

          {/* Entity badges */}
          <div className="flex gap-2 flex-wrap">
            <Badge variant="secondary" className={`${domainInfo.color} bg-white/50`}>
              {entity.domain}
            </Badge>
            {entity.device_class && (
              <Badge variant="outline" className="text-xs bg-white/50">
                {entity.device_class}
              </Badge>
            )}
            {entity.unit_of_measurement && (
              <Badge variant="outline" className="text-xs bg-white/70 font-mono">
                {entity.unit_of_measurement}
              </Badge>
            )}
            {entity.tags?.map((tag: string) => (
              <Badge key={tag} variant="outline" className="text-xs bg-white/50">
                {tag}
              </Badge>
            ))}
          </div>
        </DialogHeader>

        <Tabs value={activeTab} onValueChange={setActiveTab} className="flex-1 flex flex-col overflow-hidden">
          <TabsList className="grid w-full grid-cols-4 flex-shrink-0">
            <TabsTrigger value="overview" className="flex items-center gap-2">
              <Info className="w-4 h-4" />
              Overview
            </TabsTrigger>
            <TabsTrigger value="technical" className="flex items-center gap-2">
              <Wrench className="w-4 h-4" />
              Technical
            </TabsTrigger>
            <TabsTrigger value="debug" className="flex items-center gap-2">
              <Bug className="w-4 h-4" />
              Debug
            </TabsTrigger>
            <TabsTrigger value="attributes" className="flex items-center gap-2">
              <Settings className="w-4 h-4" />
              Attributes
            </TabsTrigger>
          </TabsList>

          <div className="flex-1 overflow-auto">
            <TabsContent value="overview" className="space-y-6 p-1">
              {/* Device Information */}
              {(entity.device_name || entity.manufacturer || entity.model) && (
                <div className="bg-gray-50 rounded-lg p-4">
                  <h3 className="font-medium text-lg mb-3 text-primary flex items-center gap-2">
                    <Home className="w-5 h-5" />
                    Device Information
                  </h3>
                  <div className="grid md:grid-cols-2 gap-4 text-sm">
                    {entity.device_name && (
                      <div>
                        <span className="font-medium text-gray-600">Name:</span>
                        <p className="text-gray-900">{entity.device_name}</p>
                      </div>
                    )}
                    {entity.manufacturer && (
                      <div>
                        <span className="font-medium text-gray-600">Manufacturer:</span>
                        <p className="text-gray-900">{entity.manufacturer}</p>
                      </div>
                    )}
                    {entity.model && (
                      <div>
                        <span className="font-medium text-gray-600">Model:</span>
                        <p className="text-gray-900">{entity.model}</p>
                      </div>
                    )}
                    {entity.device_id && (
                      <div>
                        <span className="font-medium text-gray-600">Device ID:</span>
                        <p className="text-gray-900 font-mono text-xs">{entity.device_id}</p>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Location Information */}
              <div className="bg-blue-50 rounded-lg p-4">
                <h3 className="font-medium text-lg mb-3 text-primary flex items-center gap-2">
                  <Home className="w-5 h-5" />
                  Location
                </h3>
                <div className="grid md:grid-cols-2 gap-4 text-sm">
                  <div>
                    <span className="font-medium text-gray-600">Area:</span>
                    <p className="text-gray-900">{entity.area_name || entity.area || 'Unknown'}</p>
                  </div>
                  {entity.area_id && (
                    <div>
                      <span className="font-medium text-gray-600">Area ID:</span>
                      <p className="text-gray-900 font-mono text-xs">{entity.area_id}</p>
                    </div>
                  )}
                </div>
              </div>

              {/* Current State */}
              {(entity.state || entity.unit_of_measurement) && (
                <div className="bg-green-50 rounded-lg p-4">
                  <h3 className="font-medium text-lg mb-3 text-primary flex items-center gap-2">
                    <Gauge className="w-5 h-5" />
                    Current State
                  </h3>
                  <div className="text-sm space-y-2">
                    {entity.state && (
                      <div>
                        <span className="font-medium text-gray-600">Value:</span>
                        <p className="text-2xl font-bold text-gray-900 mt-1">
                          {entity.state}
                          {entity.unit_of_measurement && (
                            <span className="text-lg text-gray-600 ml-1">
                              {entity.unit_of_measurement}
                            </span>
                          )}
                        </p>
                      </div>
                    )}
                    {entity.last_updated && (
                      <div>
                        <span className="font-medium text-gray-600">Last Updated:</span>
                        <p className="text-gray-900">{new Date(entity.last_updated).toLocaleString()}</p>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </TabsContent>

            <TabsContent value="technical" className="space-y-6 p-1">
              {/* Technical Details */}
              <div className="bg-gray-50 rounded-lg p-4">
                <h3 className="font-medium text-lg mb-3 text-primary">Entity Configuration</h3>
                <div className="grid md:grid-cols-2 gap-4 text-sm">
                  <div>
                    <span className="font-medium text-gray-600">Entity ID:</span>
                    <p className="text-gray-900 font-mono text-xs">{entity.id}</p>
                  </div>
                  <div>
                    <span className="font-medium text-gray-600">Domain:</span>
                    <p className="text-gray-900">{entity.domain}</p>
                  </div>
                  {entity.device_class && (
                    <div>
                      <span className="font-medium text-gray-600">Device Class:</span>
                      <p className="text-gray-900">{entity.device_class}</p>
                    </div>
                  )}
                  {entity.entity_category && (
                    <div>
                      <span className="font-medium text-gray-600">Category:</span>
                      <p className="text-gray-900">{entity.entity_category}</p>
                    </div>
                  )}
                  {entity.icon && (
                    <div>
                      <span className="font-medium text-gray-600">Icon:</span>
                      <p className="text-gray-900">{entity.icon}</p>
                    </div>
                  )}
                  {entity.unit_of_measurement && (
                    <div>
                      <span className="font-medium text-gray-600">Unit:</span>
                      <p className="text-gray-900">{entity.unit_of_measurement}</p>
                    </div>
                  )}
                </div>
              </div>
            </TabsContent>

            <TabsContent value="debug" className="space-y-6 p-1">
              {/* Friendly Name Quality Analysis */}
              <div className={`rounded-lg p-4 ${
                qualityAnalysis.quality === 'good' ? 'bg-green-50 border border-green-200' :
                qualityAnalysis.quality === 'medium' ? 'bg-yellow-50 border border-yellow-200' :
                'bg-red-50 border border-red-200'
              }`}>
                <h3 className={`font-medium text-lg mb-3 flex items-center gap-2 ${
                  qualityAnalysis.quality === 'good' ? 'text-green-800' :
                  qualityAnalysis.quality === 'medium' ? 'text-yellow-800' :
                  'text-red-800'
                }`}>
                  📝 Friendly Name Quality ({qualityAnalysis.score}%)
                </h3>
                <div className="text-sm space-y-3">
                  <div>
                    <span className="font-medium">Current Name:</span>
                    <p className="mt-1 p-2 bg-white rounded border font-mono text-xs">
                      {displayName}
                    </p>
                  </div>
                  
                  {qualityAnalysis.issues.length > 0 && (
                    <div>
                      <span className="font-medium">Issues:</span>
                      <ul className="mt-1 space-y-1">
                        {qualityAnalysis.issues.map((issue, idx) => (
                          <li key={idx} className="text-xs">{issue}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  
                  {qualityAnalysis.suggestions.length > 0 && (
                    <div>
                      <span className="font-medium">Suggestions:</span>
                      <ul className="mt-1 space-y-1">
                        {qualityAnalysis.suggestions.map((suggestion, idx) => (
                          <li key={idx} className="text-xs bg-white p-2 rounded border font-mono">
                            {suggestion}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              </div>

              {/* Embedded Text */}
              {entity.text && (
                <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
                  <h3 className="font-medium text-lg mb-3 text-amber-800 flex items-center gap-2">
                    🔍 Embedded Text (Search Quality Debug)
                  </h3>
                  <div className="text-sm space-y-2">
                    <div>
                      <span className="font-medium text-amber-700">Embedded Text (Multilingual):</span>
                      <pre className="mt-1 p-3 bg-white rounded border text-xs font-mono leading-relaxed whitespace-pre-wrap">
                        {entity.text}
                      </pre>
                    </div>
                    <div className="text-xs text-amber-600 italic">
                      💡 Ez a szöveg alapján történik a szemantikus keresés. Ha túl általános vagy nem kifejező, 
                      javítani kell a friendly name-et vagy az embedding logikát.
                    </div>
                  </div>
                </div>
              )}

              {/* Prompt Format */}
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                <div className="flex items-center justify-between mb-3">
                  <h3 className="font-medium text-lg text-blue-800 flex items-center gap-2">
                    🤖 LLM Prompt Format (Real-time)
                  </h3>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => refetchPrompt()}
                    disabled={promptLoading}
                    className="text-xs"
                  >
                    <RefreshCw className={`h-3 w-3 ${promptLoading ? 'animate-spin' : ''}`} />
                    Refresh
                  </Button>
                </div>
                {promptLoading ? (
                  <div className="space-y-3">
                    <div className="flex items-center gap-2 text-sm text-blue-600">
                      <RefreshCw className="h-4 w-4 animate-spin" />
                      Loading fresh data...
                    </div>
                    <div className="space-y-2">
                      <Skeleton className="h-4 w-full" />
                      <Skeleton className="h-4 w-3/4" />
                      <Skeleton className="h-8 w-1/2" />
                    </div>
                  </div>
                ) : promptFormat ? (
                  <div className="text-sm space-y-3">
                    {/* Current Value Section */}
                    <div className="bg-white rounded border p-3">
                      <div className="font-medium text-blue-700 mb-2">Current State:</div>
                      <div className="text-xs space-y-1">
                        <div><span className="font-medium">Clean Name:</span> {promptFormat.clean_name}</div>
                        <div><span className="font-medium">Area:</span> {promptFormat.area}</div>
                        {promptFormat.current_value !== null && (
                          <div>
                            <span className="font-medium">Current Value:</span> 
                            <span className="ml-1 font-mono bg-green-100 px-1 rounded">
                              {promptFormat.current_value}
                              {promptFormat.unit && ` ${promptFormat.unit}`}
                            </span>
                          </div>
                        )}
                        <div className="text-xs text-gray-500">
                          Last updated: {new Date(promptFormat.last_updated).toLocaleTimeString()}
                        </div>
                      </div>
                    </div>

                    {/* Prompt Format Examples */}
                    <div>
                      <div className="font-medium text-blue-700 mb-2">LLM Prompt Formats:</div>
                      <div className="space-y-2">
                        {Object.entries(promptFormat.prompt_formats).map(([formatType, formatText]) => (
                          <div key={formatType} className="bg-white rounded border p-2">
                            <div className="text-xs font-medium text-gray-600 mb-1 capitalize">
                              {formatType.replace('_', ' ')}:
                            </div>
                            <code className="text-xs bg-gray-100 p-2 rounded font-mono block whitespace-pre-wrap">
                              {formatText}
                            </code>
                          </div>
                        ))}
                      </div>
                    </div>

                    <div className="text-xs text-blue-600 italic">
                      💡 Ez pontosan így jelenik meg az LLM prompt-jában. A current value valós időben frissül.
                    </div>
                  </div>
                ) : (
                  <div className="text-sm text-red-600">
                    Failed to load prompt format
                  </div>
                )}
              </div>
            </TabsContent>

            <TabsContent value="attributes" className="p-1">
              <div className="bg-gray-50 rounded-lg p-4">
                <h3 className="font-medium text-lg mb-3 text-primary">Entity Attributes</h3>
                {entity.attributes && typeof entity.attributes === 'object' && Object.keys(entity.attributes).length > 0 ? (
                  <pre className="text-xs bg-white p-4 rounded border overflow-x-auto font-mono">
                    {JSON.stringify(entity.attributes, null, 2)}
                  </pre>
                ) : (
                  <p className="text-sm text-muted-foreground italic">No additional attributes</p>
                )}
              </div>
            </TabsContent>
          </div>
        </Tabs>
      </DialogContent>
    </Dialog>
  );
}