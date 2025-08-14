import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Badge } from '../components/ui/badge';
import { Skeleton } from '../components/ui/skeleton';
import { Search, Filter, X, Lightbulb, Thermometer, Zap, Wifi, Camera, Home, Gauge, Power, Bug, Eye } from 'lucide-react';
import { adminApi } from '../lib/api';
import { SearchDebugger } from '../components/SearchDebugger';
import { EntityModal } from '../components/EntityModal';

export function Entities() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [searchQuery, setSearchQuery] = useState(searchParams.get('q') || '');
  const [debouncedQuery, setDebouncedQuery] = useState(searchQuery);
  const [activeTab, setActiveTab] = useState<'browse' | 'debug'>('browse');
  const [selectedEntity, setSelectedEntity] = useState<any>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  // Handle modal entity from URL
  const entityIdFromUrl = searchParams.get('entity');
  
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

  // Query for individual entity when accessing via URL
  const { data: urlEntity } = useQuery({
    queryKey: ['entity', entityIdFromUrl],
    queryFn: () => adminApi.getEntities({ q: entityIdFromUrl || '', limit: 1 }),
    enabled: !!entityIdFromUrl && (!entities?.items || !entities.items.find((e: any) => e.id === entityIdFromUrl)),
  });

  // Find entity by ID when URL changes
  useEffect(() => {
    if (entityIdFromUrl) {
      // First try to find in current list
      let entity = entities?.items?.find((e: any) => e.id === entityIdFromUrl);
      
      // If not found, try the URL-specific query result
      if (!entity && urlEntity?.items && urlEntity.items.length > 0) {
        entity = urlEntity.items[0];
      }
      
      if (entity) {
        setSelectedEntity(entity);
        setIsModalOpen(true);
      }
    } else if (!entityIdFromUrl && isModalOpen) {
      setIsModalOpen(false);
      setSelectedEntity(null);
    }
  }, [entityIdFromUrl, entities?.items, urlEntity?.items, isModalOpen]);

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

  const openEntityModal = (entity: any) => {
    if (!entity || !entity.id) {
      console.warn('Cannot open modal for entity without ID:', entity);
      return;
    }
    const params = new URLSearchParams(searchParams);
    params.set('entity', entity.id);
    setSearchParams(params);
    setSelectedEntity(entity);
    setIsModalOpen(true);
  };

  const closeEntityModal = () => {
    const params = new URLSearchParams(searchParams);
    params.delete('entity');
    setSearchParams(params);
    setIsModalOpen(false);
    setSelectedEntity(null);
  };

  const hasFilters = searchQuery || domain || area;

  return (
    <>
      {/* Sticky Header with KPIs and Filters - Outside container */}
      <div className="sticky top-0 z-40 bg-background border-b shadow-lg mb-8">
        <div className="max-w-7xl mx-auto px-6 py-3 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <h1 className="text-3xl font-bold">Entitások</h1>
              {/* Always visible KPI badges when in browse mode */}
              {activeTab === 'browse' && (
                <div className="flex items-center gap-2 text-sm">
                  <Badge variant="outline" className="bg-blue-50 text-blue-700 border-blue-300 px-2 py-1">
                    {entities?.items?.filter(e => e && e.id).length || 0} megjelenített
                  </Badge>
                  <Badge variant="outline" className="bg-green-50 text-green-700 border-green-300 px-2 py-1">
                    {meta?.total || 0} összes
                  </Badge>
                  <Badge variant="outline" className="bg-purple-50 text-purple-700 border-purple-300 px-2 py-1 hidden sm:inline-flex">
                    {meta?.domain_types || 0} domain
                  </Badge>
                  <Badge variant="outline" className="bg-orange-50 text-orange-700 border-orange-300 px-2 py-1 hidden md:inline-flex">
                    {meta?.areas || 0} terület
                  </Badge>
                </div>
              )}
            </div>
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


          {/* Filters - Only visible in browse mode */}
          {activeTab === 'browse' && (
            <div className="bg-muted rounded-lg p-2 border">
              <div className="flex items-center gap-2 mb-2">
                <Filter className="h-4 w-4 text-muted-foreground" />
                <span className="text-sm font-medium text-foreground">Szűrők</span>
              </div>
              <div className="grid gap-2 md:grid-cols-3">
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-muted-foreground h-4 w-4" />
                  <Input
                    placeholder="Keresés..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="pl-10 bg-background"
                  />
                </div>
                
                <Select value={domain || 'all'} onValueChange={(value) => updateFilter('domain', value)}>
                  <SelectTrigger className="bg-background">
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
                  <SelectTrigger className="bg-background">
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
            </div>
          )}
        </div>
      </div>

      {/* Main Content */}
      <div className="min-h-screen bg-background">
        <div className="max-w-7xl mx-auto px-6 py-6">
          {/* Tab Content */}
          {activeTab === 'browse' && (
            <div>
              {/* Entities Grid */}
              {entitiesLoading ? (
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                  {Array.from({ length: 8 }).map((_, i) => (
                    <Card key={i} className="p-4">
                      <div className="space-y-3">
                        <div className="flex items-center gap-3">
                          <Skeleton className="w-10 h-10 rounded-full" />
                          <div className="flex-1 space-y-2">
                            <Skeleton className="h-4 w-3/4" />
                            <Skeleton className="h-3 w-1/2" />
                          </div>
                        </div>
                        <div className="flex gap-2">
                          <Skeleton className="h-5 w-16" />
                          <Skeleton className="h-5 w-12" />
                        </div>
                      </div>
                    </Card>
                  ))}
                </div>
              ) : (
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                  {entities?.items?.filter(entity => entity && entity.id).map((entity) => (
                    <EntityCard
                      key={entity.id}
                      entity={entity}
                      onClick={() => openEntityModal(entity)}
                    />
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Pipeline Debug Tab */}
          {activeTab === 'debug' && (
            <SearchDebugger />
          )}
        </div>

        {/* Entity Modal */}
        <EntityModal
          entity={selectedEntity}
          isOpen={isModalOpen}
          onClose={closeEntityModal}
        />
      </div>
    </>
  );
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

function EntityCard({ entity, onClick }: { entity: any; onClick: () => void }) {
  if (!entity) {
    return null;
  }

  // Smart friendly name fallback
  const displayName = entity.friendly_name || 
    (entity.id ? entity.id.split('.')[1]?.replace(/_/g, ' ') : 'Unknown Entity');

  // Get domain icon only (no colors)
  const domainInfo = getDomainInfo(entity.domain, entity.device_class);
  const DomainIcon = domainInfo.icon;
  
  return (
    <Card 
      className="hover:shadow-md transition-all duration-200 cursor-pointer group hover:border-primary/50"
      onClick={onClick}
    >
      <CardContent className="p-3">
        <div className="space-y-2.5">
          {/* Header */}
          <div className="flex items-start gap-2.5">
            <div className="p-1.5 rounded-md bg-muted group-hover:bg-muted/80 transition-colors">
              <DomainIcon size={16} className="text-muted-foreground" />
            </div>
            <div className="flex-1 min-w-0">
              <h3 className="font-medium text-sm text-foreground truncate leading-tight">
                {displayName}
              </h3>
              <p className="text-xs text-muted-foreground truncate">
                {entity.area_name || entity.area || 'Unknown Area'}
              </p>
            </div>
            <Button
              variant="ghost"
              size="sm"
              className="opacity-0 group-hover:opacity-100 transition-opacity p-1 h-6 w-6"
              onClick={(e) => {
                e.stopPropagation();
                onClick();
              }}
            >
              <Eye className="h-3 w-3" />
            </Button>
          </div>

          {/* Current State */}
          {entity.state && (
            <div className="bg-muted/50 rounded-md px-2 py-1.5">
              <div className="flex items-center justify-between">
                <span className="text-xs text-muted-foreground">State</span>
                <div className="flex items-center gap-1">
                  <span className="font-mono text-sm font-medium text-foreground">
                    {entity.state}
                  </span>
                  {entity.unit_of_measurement && (
                    <span className="text-xs text-muted-foreground">
                      {entity.unit_of_measurement}
                    </span>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Meta Info */}
          <div className="flex items-center justify-between text-xs">
            <span className="text-muted-foreground font-mono">
              {entity.domain}
            </span>
            {entity.device_class && (
              <Badge variant="outline" className="text-xs h-5 px-1.5 text-muted-foreground">
                {entity.device_class}
              </Badge>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}