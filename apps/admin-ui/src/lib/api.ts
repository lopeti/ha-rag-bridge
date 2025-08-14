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
  areas_list?: Array<{name: string, id: string}>;
  domains_list?: Array<{name: string, id: string}>;
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

export interface PromptFormat {
  entity_id: string;
  clean_name: string;
  area: string;
  current_value?: any;
  unit?: string;
  prompt_formats: {
    compact: string;
    detailed: string;
    grouped_by_area: string;
    hierarchical: string;
  };
  embedded_text: string;
  last_updated: string;
}

// Search Debug Types
export interface EntityDebugInfo {
  entity_id: string;
  entity_name: string;
  domain: string;
  area: string;
  
  // Stage 1: Cluster search
  cluster_score?: number;
  source_cluster?: string;
  cluster_relevance?: number;
  
  // Stage 2: Vector search  
  vector_score?: number;
  embedding_similarity?: number;
  
  // Stage 3: Reranking
  base_score?: number;
  context_boost?: number;
  final_score?: number;
  ranking_factors?: Record<string, number>;
  
  // Cross-encoder specific debug info
  cross_encoder_raw_score?: number;
  cross_encoder_input_text?: string;
  cross_encoder_cache_hit?: boolean;
  cross_encoder_inference_ms?: number;
  used_fallback_matching?: boolean;
  
  // Stage 4: Selection
  is_active?: boolean;
  is_selected?: boolean;
  selection_rank?: number;
  in_prompt?: boolean;
  
  // Metadata
  pipeline_stage_reached?: 'cluster_search' | 'vector_fallback' | 'reranking' | 'final_selection';
  score_delta?: number; // final_score - vector_score
}

export interface StageResult {
  stage: 'cluster_search' | 'vector_fallback' | 'reranking' | 'final_selection';
  stage_name: string;
  entities_in: number;
  entities_out: number;
  execution_time_ms: number;
  metadata: Record<string, any>;
}

export interface PipelineDebugInfo {
  query: string;
  query_embedding?: number[];
  scope_config: Record<string, any>;
  
  // Stage results
  stage_results: StageResult[];
  entities: EntityDebugInfo[];
  
  // Summary statistics
  total_execution_time_ms: number;
  pipeline_efficiency: Record<string, number>;
  final_entity_count: number;
  similarity_threshold: number;
  
  // Query analysis
  detected_scope?: string;
  areas_mentioned?: string[];
  conversation_context?: Record<string, any>;
  query_analysis?: {
    detected_scope: string;
    areas_mentioned: string[];
    scope_confidence: number;
    cluster_types: string[];
    optimal_k: number;
  };
}

export interface SearchDebugRequest {
  query: string;
  include_debug?: boolean;
  threshold?: number;
  limit?: number;
}

// Configuration Management Types
export interface ConfigFieldMetadata {
  type: string;
  title_hu: string;
  title_en: string;
  description_hu: string;
  description_en: string;
  recommendation_hu?: string;
  recommendation_en?: string;
  is_sensitive: boolean;
  restart_required: boolean;
  example?: string;
  constraints?: {
    min?: number;
    max?: number;
    min_exclusive?: number;
    max_exclusive?: number;
  };
  default?: any;
  env_var?: string;
}

export interface ConfigFieldData {
  value: any;
  metadata: ConfigFieldMetadata;
}

export interface ConfigCategoryData {
  [fieldName: string]: ConfigFieldData;
}

export interface ConfigData {
  [categoryName: string]: ConfigCategoryData;
}

export interface ConfigResponse {
  config: ConfigData;
  metadata: any;
  timestamp: string;
}

export interface ConfigUpdateResponse {
  success: boolean;
  updated_fields: string[];
  restart_required: boolean;
  message: string;
  timestamp: string;
}

export interface ConfigValidationResponse {
  valid: boolean;
  errors: string[];
  warnings: string[];
  timestamp: string;
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

  getEntityPromptFormat: async (entityId: string): Promise<PromptFormat> => {
    const response = await api.get(`/entities/${encodeURIComponent(entityId)}/prompt-format`);
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

  // Search Debug
  searchEntitiesDebug: async (searchRequest: SearchDebugRequest): Promise<PipelineDebugInfo> => {
    const response = await api.post('/entities/search-debug', searchRequest);
    return response.data;
  },

  // Configuration Management
  getConfig: async (): Promise<ConfigResponse> => {
    const response = await api.get('/config');
    return response.data;
  },

  updateConfig: async (configData: { config: any }): Promise<ConfigUpdateResponse> => {
    const response = await api.put('/config', configData);
    return response.data;
  },

  validateConfig: async (configData: { config: any }): Promise<ConfigValidationResponse> => {
    const response = await api.post('/config/validate', configData);
    return response.data;
  },

  reloadConfig: async (): Promise<{ success: boolean; message: string; timestamp: string }> => {
    const response = await api.post('/config/reload');
    return response.data;
  },

  exportConfig: async (includeSensitive = false): Promise<Blob> => {
    const response = await api.get('/config/export', { 
      responseType: 'blob',
      params: { include_sensitive: includeSensitive }
    });
    return response.data;
  },

  revealSensitiveField: async (fieldName: string): Promise<{ field_name: string; value: string }> => {
    const response = await api.get(`/config/reveal/${fieldName}`);
    return response.data;
  },

  // Connection testing
  testConnection: async (service: string, overrides?: any): Promise<{
    service: string;
    status: 'connected' | 'failed' | 'not_configured';
    details?: any;
    error?: string;
    response_time_ms: number;
  }> => {
    const body = overrides ? { overrides } : {};
    const response = await api.post(`/test-connection/${service}`, body);
    return response.data;
  },

  testAllConnections: async (): Promise<{
    summary: {
      total: number;
      connected: number;
      failed: number;
      not_configured: number;
    };
    services: Record<string, any>;
    timestamp: string;
  }> => {
    const response = await api.post('/test-all-connections');
    return response.data;
  }
};

export default adminApi;