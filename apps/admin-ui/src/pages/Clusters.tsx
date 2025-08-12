import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Plus, Edit, Trash2 } from 'lucide-react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Textarea } from '../components/ui/textarea';
import { toast } from '../hooks/use-toast';
import { adminApi, type Cluster } from '../lib/api';

interface ClusterFormData {
  name: string;
  type: 'micro' | 'macro' | 'overview';
  scope: string;
  tags: string;
  description: string;
}

export function Clusters() {
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [editingCluster, setEditingCluster] = useState<Cluster | null>(null);
  const [formData, setFormData] = useState<ClusterFormData>({
    name: '',
    type: 'micro',
    scope: '',
    tags: '',
    description: '',
  });

  const queryClient = useQueryClient();

  const { data: clusters = [], isLoading } = useQuery({
    queryKey: ['clusters'],
    queryFn: adminApi.getClusters,
  });

  const createMutation = useMutation({
    mutationFn: adminApi.createCluster,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['clusters'] });
      setIsCreateOpen(false);
      resetForm();
      toast({
        title: 'Cluster created',
        description: 'The cluster has been created successfully.',
      });
    },
    onError: () => {
      toast({
        title: 'Error',
        description: 'Failed to create cluster.',
        variant: 'destructive',
      });
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<Cluster> }) =>
      adminApi.updateCluster(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['clusters'] });
      setEditingCluster(null);
      resetForm();
      toast({
        title: 'Cluster updated',
        description: 'The cluster has been updated successfully.',
      });
    },
    onError: () => {
      toast({
        title: 'Error',
        description: 'Failed to update cluster.',
        variant: 'destructive',
      });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: adminApi.deleteCluster,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['clusters'] });
      toast({
        title: 'Cluster deleted',
        description: 'The cluster has been deleted successfully.',
      });
    },
    onError: () => {
      toast({
        title: 'Error',
        description: 'Failed to delete cluster.',
        variant: 'destructive',
      });
    },
  });

  const resetForm = () => {
    setFormData({
      name: '',
      type: 'micro',
      scope: '',
      tags: '',
      description: '',
    });
  };

  const handleEdit = (cluster: Cluster) => {
    setEditingCluster(cluster);
    setFormData({
      name: cluster.name,
      type: cluster.type as 'micro' | 'macro' | 'overview',
      scope: cluster.scope,
      tags: cluster.tags.join(', '),
      description: cluster.description || '',
    });
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    
    const clusterData = {
      name: formData.name,
      type: formData.type,
      scope: formData.scope,
      tags: formData.tags.split(',').map(tag => tag.trim()).filter(Boolean),
      description: formData.description || undefined,
    };

    if (editingCluster) {
      updateMutation.mutate({
        id: editingCluster.id,
        data: clusterData,
      });
    } else {
      createMutation.mutate(clusterData);
    }
  };

  const handleDelete = (id: string) => {
    if (confirm('Are you sure you want to delete this cluster?')) {
      deleteMutation.mutate(id);
    }
  };

  // Calculate KPI stats
  const kpis = {
    total: clusters.length,
    micro: clusters.filter(c => c.type === 'micro').length,
    macro: clusters.filter(c => c.type === 'macro').length,
    overview: clusters.filter(c => c.type === 'overview').length,
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Cluster-ek</h1>
        <Dialog open={isCreateOpen} onOpenChange={setIsCreateOpen}>
          <DialogTrigger asChild>
            <Button>
              <Plus className="h-4 w-4 mr-2" />
              Új Cluster
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Új cluster létrehozása</DialogTitle>
            </DialogHeader>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <Label htmlFor="name">Név</Label>
                <Input
                  id="name"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  required
                />
              </div>
              <div>
                <Label htmlFor="type">Típus</Label>
                <Select
                  value={formData.type}
                  onValueChange={(value: 'micro' | 'macro' | 'overview') =>
                    setFormData({ ...formData, type: value })
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="micro">Micro</SelectItem>
                    <SelectItem value="macro">Macro</SelectItem>
                    <SelectItem value="overview">Overview</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label htmlFor="scope">Hatókör</Label>
                <Input
                  id="scope"
                  value={formData.scope}
                  onChange={(e) => setFormData({ ...formData, scope: e.target.value })}
                  required
                />
              </div>
              <div>
                <Label htmlFor="tags">Címkék (vesszővel elválasztva)</Label>
                <Input
                  id="tags"
                  value={formData.tags}
                  onChange={(e) => setFormData({ ...formData, tags: e.target.value })}
                  placeholder="light, bedroom, main"
                />
              </div>
              <div>
                <Label htmlFor="description">Leírás</Label>
                <Textarea
                  id="description"
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                />
              </div>
              <div className="flex justify-end space-x-2">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => {
                    setIsCreateOpen(false);
                    resetForm();
                  }}
                >
                  Mégse
                </Button>
                <Button type="submit" disabled={createMutation.isPending}>
                  {createMutation.isPending ? 'Létrehozás...' : 'Létrehozás'}
                </Button>
              </div>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      {/* KPI Cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium">Összes</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{kpis.total}</p>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium">Micro</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{kpis.micro}</p>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium">Macro</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{kpis.macro}</p>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium">Overview</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{kpis.overview}</p>
          </CardContent>
        </Card>
      </div>

      {/* Clusters List */}
      <Card>
        <CardHeader>
          <CardTitle>Cluster-ek listája</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-4">
              {Array.from({ length: 3 }).map((_, i) => (
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
          ) : clusters.length === 0 ? (
            <div className="text-center py-8">
              <p className="text-muted-foreground">Még nincsenek cluster-ek definiálva.</p>
              <Button
                className="mt-4"
                onClick={() => setIsCreateOpen(true)}
              >
                <Plus className="h-4 w-4 mr-2" />
                Első cluster létrehozása
              </Button>
            </div>
          ) : (
            <div className="space-y-4">
              {clusters.map((cluster) => (
                <div key={cluster.id} className="border rounded-lg p-4">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <h3 className="font-semibold text-lg">{cluster.name}</h3>
                      <p className="text-sm text-muted-foreground mt-1">
                        {cluster.description}
                      </p>
                      <div className="flex gap-2 mt-3">
                        <Badge 
                          variant={
                            cluster.type === 'micro' ? 'default' :
                            cluster.type === 'macro' ? 'secondary' :
                            'outline'
                          }
                        >
                          {cluster.type}
                        </Badge>
                        <Badge variant="outline">{cluster.scope}</Badge>
                        {cluster.tags.map((tag) => (
                          <Badge key={tag} variant="outline" className="text-xs">
                            {tag}
                          </Badge>
                        ))}
                      </div>
                    </div>
                    <div className="flex gap-2 ml-4">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleEdit(cluster)}
                      >
                        <Edit className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleDelete(cluster.id)}
                        disabled={deleteMutation.isPending}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Edit Modal */}
      <Dialog open={!!editingCluster} onOpenChange={() => setEditingCluster(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Cluster szerkesztése</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <Label htmlFor="edit-name">Név</Label>
              <Input
                id="edit-name"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                required
              />
            </div>
            <div>
              <Label htmlFor="edit-type">Típus</Label>
              <Select
                value={formData.type}
                onValueChange={(value: 'micro' | 'macro' | 'overview') =>
                  setFormData({ ...formData, type: value })
                }
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="micro">Micro</SelectItem>
                  <SelectItem value="macro">Macro</SelectItem>
                  <SelectItem value="overview">Overview</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label htmlFor="edit-scope">Hatókör</Label>
              <Input
                id="edit-scope"
                value={formData.scope}
                onChange={(e) => setFormData({ ...formData, scope: e.target.value })}
                required
              />
            </div>
            <div>
              <Label htmlFor="edit-tags">Címkék (vesszővel elválasztva)</Label>
              <Input
                id="edit-tags"
                value={formData.tags}
                onChange={(e) => setFormData({ ...formData, tags: e.target.value })}
                placeholder="light, bedroom, main"
              />
            </div>
            <div>
              <Label htmlFor="edit-description">Leírás</Label>
              <Textarea
                id="edit-description"
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              />
            </div>
            <div className="flex justify-end space-x-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => {
                  setEditingCluster(null);
                  resetForm();
                }}
              >
                Mégse
              </Button>
              <Button type="submit" disabled={updateMutation.isPending}>
                {updateMutation.isPending ? 'Mentés...' : 'Mentés'}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}