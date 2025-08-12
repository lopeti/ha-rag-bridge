import { useState, useEffect, useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Badge } from '../components/ui/badge';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '../components/ui/collapsible';
import { Search, Filter, ChevronDown, X } from 'lucide-react';
import { adminApi } from '../lib/api';
// import { useVirtualizer } from '@tanstack/react-virtual';

export function Entities() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [searchQuery, setSearchQuery] = useState(searchParams.get('q') || '');
  const [debouncedQuery, setDebouncedQuery] = useState(searchQuery);
  const parentRef = useRef<HTMLDivElement>(null);

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

  // Temporary disable virtualizer to fix ref error
  // const rowVirtualizer = useVirtualizer({
  //   count: entities?.items.length || 0,
  //   getScrollElement: () => parentRef.current,
  //   estimateSize: () => 120,
  // });
  const rowVirtualizer = {
    getVirtualItems: () => (entities?.items || []).map((_, index) => ({ index, start: index * 120, size: 120, key: index })),
    getTotalSize: () => (entities?.items.length || 0) * 120
  };

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
        {hasFilters && (
          <Button variant="outline" onClick={clearFilters}>
            <X className="h-4 w-4 mr-2" />
            Szűrők törlése
          </Button>
        )}
      </div>

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
                <SelectItem value="light">Light</SelectItem>
                <SelectItem value="sensor">Sensor</SelectItem>
                <SelectItem value="climate">Climate</SelectItem>
                <SelectItem value="switch">Switch</SelectItem>
              </SelectContent>
            </Select>
            
            <Select value={area || 'all'} onValueChange={(value) => updateFilter('area', value)}>
              <SelectTrigger>
                <SelectValue placeholder="Terület kiválasztása" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Minden terület</SelectItem>
                <SelectItem value="nappali">Nappali</SelectItem>
                <SelectItem value="konyha">Konyha</SelectItem>
                <SelectItem value="haloszoba">Hálószoba</SelectItem>
                <SelectItem value="furdoszoba">Fürdőszoba</SelectItem>
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
            <div
              ref={parentRef}
              className="h-[600px] overflow-auto"
            >
              <div
                style={{
                  height: `${rowVirtualizer.getTotalSize()}px`,
                  width: '100%',
                  position: 'relative',
                }}
              >
                {rowVirtualizer.getVirtualItems().map((virtualItem) => {
                  const entity = entities?.items[virtualItem.index];
                  if (!entity) return null;

                  return (
                    <EntityItem
                      key={virtualItem.key}
                      entity={entity}
                      style={{
                        position: 'absolute',
                        top: 0,
                        left: 0,
                        width: '100%',
                        height: `${virtualItem.size}px`,
                        transform: `translateY(${virtualItem.start}px)`,
                      }}
                    />
                  );
                })}
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function EntityItem({ entity, style }: { entity: any; style: React.CSSProperties }) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div style={style} className="px-1">
      <Collapsible open={isOpen} onOpenChange={setIsOpen}>
        <div className="border rounded-lg p-4 bg-card">
          <CollapsibleTrigger className="w-full text-left">
            <div className="flex items-center justify-between">
              <div className="flex-1 min-w-0">
                <p className="font-semibold text-foreground truncate">
                  {entity.friendly_name}
                </p>
                <p className="text-sm text-muted-foreground truncate">
                  {entity.domain} · {entity.area} · {entity.id}
                </p>
                <div className="flex gap-2 mt-2">
                  <Badge variant="secondary">{entity.domain}</Badge>
                  <Badge variant="outline">{entity.area}</Badge>
                  {entity.tags.map((tag: string) => (
                    <Badge key={tag} variant="outline" className="text-xs">
                      {tag}
                    </Badge>
                  ))}
                </div>
              </div>
              <ChevronDown 
                className={`h-4 w-4 transition-transform ${isOpen ? 'rotate-180' : ''}`}
              />
            </div>
          </CollapsibleTrigger>
          
          <CollapsibleContent className="mt-4 pt-4 border-t">
            <div className="space-y-2">
              <h4 className="font-medium text-sm">Attribútumok:</h4>
              <pre className="text-xs bg-muted p-3 rounded overflow-x-auto">
                {JSON.stringify(entity.attributes, null, 2)}
              </pre>
            </div>
          </CollapsibleContent>
        </div>
      </Collapsible>
    </div>
  );
}