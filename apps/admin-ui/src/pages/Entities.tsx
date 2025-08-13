import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Badge } from '../components/ui/badge';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '../components/ui/collapsible';
import { Search, Filter, ChevronDown, X, Lightbulb, Thermometer, Zap, Wifi, Camera, Home, Gauge, Power, RefreshCw, Bug } from 'lucide-react';
import { adminApi, type PromptFormat } from '../lib/api';
import { SearchDebugger } from '../components/SearchDebugger';

export function Entities() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [searchQuery, setSearchQuery] = useState(searchParams.get('q') || '');
  const [debouncedQuery, setDebouncedQuery] = useState(searchQuery);
  const [activeTab, setActiveTab] = useState<'browse' | 'debug'>('browse');

  // Debounce search
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedQuery(searchQuery);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  // Update URL params
  useEffect(() => {
    const params = new URLSearchParams(searchParams);
    if (debouncedQuery) {
      params.set('q', debouncedQuery);
    } else {
      params.delete('q');
    }
    setSearchParams(params, { replace: true });
  }, [debouncedQuery, setSearchParams, searchParams]);

  const domain = searchParams.get('domain') || '';
  const area = searchParams.get('area') || '';

  const { data: entities, isLoading: entitiesLoading } = useQuery({
    queryKey: ['entities', { q: debouncedQuery, domain, area, limit: 50 }],
    queryFn: () => adminApi.getEntities({
      q: debouncedQuery || undefined,
      domain: domain || undefined,
      area: area || undefined,
      limit: 50,
    }),
  });

  const { data: meta } = useQuery({
    queryKey: ['entities-meta'],
    queryFn: adminApi.getEntitiesMeta,
  });


  const updateFilter = (key: string, value: string) => {
    const params = new URLSearchParams(searchParams);
    if (value && value !== 'all') {
      params.set(key, value);
    } else {
      params.delete(key);
    }
    setSearchParams(params);
  };

  const clearFilters = () => {
    setSearchParams({});
    setSearchQuery('');
    setDebouncedQuery('');
  };

  const hasFilters = searchQuery || domain || area;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Entitások</h1>
        {hasFilters && activeTab === 'browse' && (
          <Button variant="outline" onClick={clearFilters}>
            <X className="h-4 w-4 mr-2" />
            Szűrők törlése
          </Button>
        )}
      </div>

      {/* Tab Navigation */}
      <div className="border-b">
        <nav className="-mb-px flex space-x-8" aria-label="Tabs">
          <button
            onClick={() => setActiveTab('browse')}
            className={`${
              activeTab === 'browse'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            } whitespace-nowrap py-2 px-1 border-b-2 font-medium text-sm flex items-center gap-2`}
          >
            <Search className="w-4 h-4" />
            Entity böngésző
          </button>
          <button
            onClick={() => setActiveTab('debug')}
            className={`${
              activeTab === 'debug'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            } whitespace-nowrap py-2 px-1 border-b-2 font-medium text-sm flex items-center gap-2`}
          >
            <Bug className="w-4 h-4" />
            Pipeline Debug
          </button>
        </nav>
      </div>

      {/* Tab Content */}
      {activeTab === 'browse' && (
        <>
          {/* KPI Cards */}
          <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium">Megjelenített</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{entities?.items.length || 0}</p>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium">Összes</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{meta?.total || 0}</p>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium">Domain típusok</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{meta?.domain_types || 0}</p>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium">Területek</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{meta?.areas || 0}</p>
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center">
            <Filter className="h-5 w-5 mr-2" />
            Szűrők
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 md:grid-cols-3">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-muted-foreground h-4 w-4" />
              <Input
                placeholder="Keresés..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-10"
              />
            </div>
            
            <Select value={domain || 'all'} onValueChange={(value) => updateFilter('domain', value)}>
              <SelectTrigger>
                <SelectValue placeholder="Domain kiválasztása" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Minden domain</SelectItem>
                {meta?.domains_list?.map((d: any) => (
                  <SelectItem key={d.id} value={d.id}>{d.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            
            <Select value={area || 'all'} onValueChange={(value) => updateFilter('area', value)}>
              <SelectTrigger>
                <SelectValue placeholder="Terület kiválasztása" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Minden terület</SelectItem>
                {meta?.areas_list?.map((a: any) => (
                  <SelectItem key={a.id} value={a.id}>{a.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {/* Entities List */}
      <Card>
        <CardHeader>
          <CardTitle>Entitások listája</CardTitle>
        </CardHeader>
        <CardContent>
          {entitiesLoading ? (
            <div className="space-y-4">
              {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="border rounded-lg p-4">
                  <div className="space-y-2">
                    <div className="h-5 bg-muted animate-pulse rounded w-1/3" />
                    <div className="h-4 bg-muted animate-pulse rounded w-2/3" />
                    <div className="flex gap-2">
                      <div className="h-6 bg-muted animate-pulse rounded w-16" />
                      <div className="h-6 bg-muted animate-pulse rounded w-20" />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="space-y-3 max-h-[600px] overflow-auto">
              {entities?.items.map((entity) => (
                <EntityItem
                  key={entity.id}
                  entity={entity}
                />
              ))}
            </div>
          )}
        </CardContent>
      </Card>
        </>
      )}

      {/* Pipeline Debug Tab */}
      {activeTab === 'debug' && (
        <SearchDebugger />
      )}
    </div>
  );
}

// Friendly name quality analyzer
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

// Domain-specific styling helper
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

function EntityItem({ entity }: { entity: any }) {
  const [isOpen, setIsOpen] = useState(false);
  const [showPromptFormat, setShowPromptFormat] = useState(false);

  // Query for prompt format when needed
  const { data: promptFormat, isLoading: promptLoading, refetch: refetchPrompt } = useQuery<PromptFormat>({
    queryKey: ['entity-prompt-format', entity.id],
    queryFn: () => adminApi.getEntityPromptFormat(entity.id),
    enabled: isOpen && showPromptFormat,
    staleTime: 30000, // Cache for 30 seconds
  });

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
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <div className={`border rounded-lg p-4 ${domainInfo.bgColor} hover:opacity-90 transition-all duration-200 shadow-sm hover:shadow-md`}>
        <CollapsibleTrigger className="w-full text-left">
          <div className="flex items-center justify-between">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-3 mb-1">
                <div className={`p-2 rounded-full bg-white ${domainInfo.color} border`}>
                  <DomainIcon size={16} />
                </div>
                <p className="font-semibold text-foreground truncate text-base">
                  {displayName}
                </p>
                {entity.state && (
                  <Badge variant="outline" className="text-xs">
                    {entity.state}
                  </Badge>
                )}
                {/* Friendly name quality indicator */}
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
              </div>
              
              <div className="text-sm text-muted-foreground space-y-1">
                <p className="truncate">
                  {entity.domain} · {entity.area_name || entity.area || 'Unknown Area'}
                </p>
                {entity.device_name && (
                  <p className="truncate text-xs">
                    Device: {entity.device_name}
                  </p>
                )}
                <p className="truncate text-xs">
                  ID: {entity.id}
                </p>
              </div>
              
              <div className="flex gap-2 mt-2 flex-wrap">
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
            </div>
            <ChevronDown 
              className={`h-4 w-4 transition-transform ${isOpen ? 'rotate-180' : ''} flex-shrink-0`}
            />
          </div>
        </CollapsibleTrigger>
        
        <CollapsibleContent className="space-y-0 data-[state=open]:mt-4">
          <div className="pt-4 border-t space-y-4">
            {/* Toggle between Embedded Text and Prompt Format */}
            <div className="flex gap-2 mb-4">
              <Button
                variant={!showPromptFormat ? "default" : "outline"}
                size="sm"
                onClick={() => setShowPromptFormat(false)}
                className="text-xs"
              >
                🔍 Embedded Text
              </Button>
              <Button
                variant={showPromptFormat ? "default" : "outline"}
                size="sm"
                onClick={() => setShowPromptFormat(true)}
                className="text-xs"
              >
                🤖 LLM Prompt Format
              </Button>
              {showPromptFormat && promptFormat && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => refetchPrompt()}
                  disabled={promptLoading}
                  className="text-xs"
                >
                  <RefreshCw className={`h-3 w-3 ${promptLoading ? 'animate-spin' : ''}`} />
                </Button>
              )}
            </div>

            {/* Embedded Text Panel */}
            {!showPromptFormat && entity.text && (
              <div className="bg-amber-50 border border-amber-200 rounded-lg p-3">
                <h4 className="font-medium text-sm mb-2 text-amber-800 flex items-center gap-2">
                  🔍 Embedded Text (Search Quality Debug)
                </h4>
                <div className="text-sm space-y-2">
                  <div>
                    <span className="font-medium text-amber-700">Embedded Text (Multilingual):</span>
                    <p className="mt-1 p-2 bg-white rounded border text-xs font-mono leading-relaxed">
                      {entity.text}
                    </p>
                  </div>
                  <div className="text-xs text-amber-600 italic">
                    💡 Ez a szöveg alapján történik a szemantikus keresés. Ha túl általános vagy nem kifejező, 
                    javítani kell a friendly name-et vagy az embedding logikát.
                  </div>
                </div>
              </div>
            )}

            {/* Prompt Format Panel */}
            {showPromptFormat && (
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
                <h4 className="font-medium text-sm mb-2 text-blue-800 flex items-center gap-2">
                  🤖 LLM Prompt Format (Real-time)
                </h4>
                {promptLoading ? (
                  <div className="flex items-center gap-2 text-sm text-blue-600">
                    <RefreshCw className="h-4 w-4 animate-spin" />
                    Loading fresh data...
                  </div>
                ) : promptFormat ? (
                  <div className="text-sm space-y-3">
                    {/* Current Value Section */}
                    <div className="bg-white rounded border p-2">
                      <div className="font-medium text-blue-700 mb-1">Current State:</div>
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
                            <code className="text-xs bg-gray-100 p-1 rounded font-mono block">
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
            )}

            {/* Friendly Name Quality Analysis */}
            <div className={`rounded-lg p-3 ${
              qualityAnalysis.quality === 'good' ? 'bg-green-50 border border-green-200' :
              qualityAnalysis.quality === 'medium' ? 'bg-yellow-50 border border-yellow-200' :
              'bg-red-50 border border-red-200'
            }`}>
              <h4 className={`font-medium text-sm mb-2 flex items-center gap-2 ${
                qualityAnalysis.quality === 'good' ? 'text-green-800' :
                qualityAnalysis.quality === 'medium' ? 'text-yellow-800' :
                'text-red-800'
              }`}>
                📝 Friendly Name Quality ({qualityAnalysis.score}%)
              </h4>
              <div className="text-sm space-y-2">
                <div>
                  <span className="font-medium">Current Name:</span>
                  <span className="ml-2 font-mono bg-white px-2 py-1 rounded border text-xs">
                    {displayName}
                  </span>
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
                        <li key={idx} className="text-xs bg-white p-1 rounded border font-mono">
                          {suggestion}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </div>

            {/* Device Information */}
            {(entity.device_name || entity.manufacturer || entity.model) && (
              <div>
                <h4 className="font-medium text-sm mb-2 text-primary">Device Info</h4>
                <div className="text-sm space-y-1">
                  {entity.device_name && <p><span className="font-medium">Name:</span> {entity.device_name}</p>}
                  {entity.manufacturer && <p><span className="font-medium">Manufacturer:</span> {entity.manufacturer}</p>}
                  {entity.model && <p><span className="font-medium">Model:</span> {entity.model}</p>}
                  {entity.device_id && <p><span className="font-medium">ID:</span> {entity.device_id}</p>}
                </div>
              </div>
            )}

            {/* Area Information */}
            <div>
              <h4 className="font-medium text-sm mb-2 text-primary">Location</h4>
              <div className="text-sm space-y-1">
                <p><span className="font-medium">Area:</span> {entity.area_name || entity.area || 'Unknown'}</p>
                {entity.area_id && <p><span className="font-medium">Area ID:</span> {entity.area_id}</p>}
              </div>
            </div>

            {/* Technical Details */}
            <div>
              <h4 className="font-medium text-sm mb-2 text-primary">Technical Details</h4>
              <div className="text-sm space-y-1">
                <p><span className="font-medium">Domain:</span> {entity.domain}</p>
                {entity.device_class && <p><span className="font-medium">Device Class:</span> {entity.device_class}</p>}
                {entity.entity_category && <p><span className="font-medium">Category:</span> {entity.entity_category}</p>}
                {entity.icon && <p><span className="font-medium">Icon:</span> {entity.icon}</p>}
                {entity.last_updated && <p><span className="font-medium">Last Updated:</span> {new Date(entity.last_updated).toLocaleString()}</p>}
              </div>
            </div>

            {/* Attributes */}
            <div>
              <h4 className="font-medium text-sm mb-2 text-primary">Attributes</h4>
              {entity.attributes && Object.keys(entity.attributes).length > 0 ? (
                <pre className="text-xs bg-muted p-3 rounded overflow-x-auto border">
                  {JSON.stringify(entity.attributes, null, 2)}
                </pre>
              ) : (
                <p className="text-sm text-muted-foreground italic">No additional attributes</p>
              )}
            </div>
          </div>
        </CollapsibleContent>
      </div>
    </Collapsible>
  );
}