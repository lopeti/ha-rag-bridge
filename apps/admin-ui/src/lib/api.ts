import axios from 'axios';

// API Types
export interface SystemOverview {
  database: {
    name: string;
    status: 'ok' | 'error';
  };
  schema: {
    current: number;
    latest: number;
  };
  vector: {
    dimension: number;
    status: 'ok' | 'mismatch';
  };
  system: {
    status: 'ok' | 'degraded' | 'error';
  };
}

export interface Entity {
  id: string;
  friendly_name: string;
  domain: string;
  area: string;
  tags: string[];
  attributes: Record<string, any>;
}

export interface EntitiesResponse {
  total: number;
  items: Entity[];
}

export interface EntitiesMeta {
  total: number;
  shown: number;
  domain_types: number;
  areas: number;
}

export interface Cluster {
  id: string;
  name: string;
  type: 'micro' | 'macro' | 'overview';
  scope: string;
  tags: string[];
  description?: string;
}

export interface MonitoringMetrics {
  cpu: number;
  memory: number;
  disk: number;
  latency_ms: number;
  rag: {
    qps: number;
    vector_ms: number;
  };
  db: {
    status: 'ok' | 'error';
  };
  vector: {
    status: 'ok' | 'error';
  };
  info: {
    db_name: string;
    vector_dim: number;
    schema: {
      current: number;
      latest: number;
    };
  };
}

export interface LogEntry {
  ts: string;
  level: 'debug' | 'info' | 'warning' | 'error';
  msg: string;
  container?: string;
}

export interface LogsResponse {
  items: LogEntry[];
  nextCursor?: string;
}

export interface HealthStatus {
  status: 'healthy' | 'warning' | 'error';
  database: boolean;
  database_version?: string;
  home_assistant: boolean;
  ha_version?: string;
  embedding_backend?: string;
  embedding_dimensions?: number;
  last_bootstrap?: string;
}

export interface SystemStats {
  cpu_usage: number;
  memory_usage: number;
  uptime: string;
  total_entities: number;
  total_clusters: number;
  total_documents: number;
  database_size?: string;
}

// Create axios instance
const api = axios.create({
  baseURL: '/admin',
  timeout: 30000,
});

// Add request interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('API Error:', error);
    return Promise.reject(error);
  }
);

// API functions
export const adminApi = {
  // Overview
  getOverview: async (): Promise<SystemOverview> => {
    const response = await api.get('/overview');
    return response.data;
  },

  // Entities
  getEntities: async (params?: {
    q?: string;
    domain?: string;
    area?: string;
    offset?: number;
    limit?: number;
  }): Promise<EntitiesResponse> => {
    const response = await api.get('/entities', { params });
    return response.data;
  },

  getEntitiesMeta: async (): Promise<EntitiesMeta> => {
    const response = await api.get('/entities/meta');
    return response.data;
  },

  // Clusters
  getClusters: async (): Promise<Cluster[]> => {
    const response = await api.get('/clusters');
    return response.data;
  },

  createCluster: async (cluster: Omit<Cluster, 'id'>): Promise<Cluster> => {
    const response = await api.post('/clusters', cluster);
    return response.data;
  },

  updateCluster: async (id: string, cluster: Partial<Cluster>): Promise<Cluster> => {
    const response = await api.put(`/clusters/${id}`, cluster);
    return response.data;
  },

  deleteCluster: async (id: string): Promise<void> => {
    await api.delete(`/clusters/${id}`);
  },

  // Maintenance
  migrate: async (): Promise<void> => {
    await api.post('/maintenance/migrate');
  },

  reindex: async (params?: { collection?: string; force?: boolean }): Promise<{
    collection: string;
    dropped: number;
    created: number;
    dimensions: number;
    took_ms: number;
  }> => {
    const response = await api.post('/maintenance/reindex', params);
    return response.data;
  },

  ingest: async (): Promise<void> => {
    await api.post('/maintenance/ingest');
  },

  bootstrapClusters: async (): Promise<void> => {
    await api.post('/maintenance/bootstrap-clusters');
  },

  cleanup: async (params: { vacuum_days: number }): Promise<{
    deleted_events: number;
    deleted_sensors: number;
  }> => {
    const response = await api.post('/maintenance/cleanup', params);
    return response.data;
  },

  exportData: async (): Promise<{ url: string }> => {
    const response = await api.post('/maintenance/export');
    return response.data;
  },

  // Monitoring
  getMetrics: async (): Promise<MonitoringMetrics> => {
    const response = await api.get('/monitoring/metrics');
    return response.data;
  },

  getLogs: async (params?: { level?: string; cursor?: string; container?: string }): Promise<LogsResponse> => {
    const response = await api.get('/monitoring/logs', { params });
    return response.data;
  },

  // Health and Stats
  getHealth: async (): Promise<HealthStatus> => {
    const response = await api.get('/health');
    return response.data;
  },

  getSystemStats: async (): Promise<SystemStats> => {
    const response = await api.get('/stats');
    return response.data;
  },

  // Maintenance operations
  bootstrap: async (): Promise<{ output?: string }> => {
    const response = await api.post('/maintenance/bootstrap');
    return response.data;
  },

  clearCache: async (): Promise<void> => {
    await api.post('/maintenance/clear-cache');
  },

  reindexVectors: async (): Promise<void> => {
    await api.post('/maintenance/reindex-vectors');
  },
};

export default adminApi;