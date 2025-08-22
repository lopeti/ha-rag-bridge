import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Alert, AlertDescription } from '../components/ui/alert';
import { 
  Collapsible, 
  CollapsibleContent, 
  CollapsibleTrigger 
} from '../components/ui/collapsible';
import { 
  Save, 
  RotateCcw, 
  Download, 
  CheckCircle, 
  AlertTriangle, 
  ChevronDown,
  ChevronUp
} from 'lucide-react';
import { adminApi } from '../lib/api';
import { ConfigField } from '../components/ConfigField';
import { QueryProcessingConfig } from '../components/QueryProcessingConfig';
import { EmbeddingAdvancedConfig } from '../components/EmbeddingAdvancedConfig';
import { ConversationMemoryConfig } from '../components/ConversationMemoryConfig';
import type { ConfigData } from '../lib/api';


export function Settings() {
  console.log('🚨 CLAUDE DEBUG: Settings component loaded! 🚨');
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const currentLang = i18n.language;
  
  const [expandedCategories, setExpandedCategories] = useState<string[]>([
    'database', 'embedding', 'query_processing', 'embedding_advanced', 
    'conversation_memory', 'performance', 'cross_encoder', 'entity_ranking'
  ]);
  const [modifiedFields, setModifiedFields] = useState<Set<string>>(new Set());
  const [configValues, setConfigValues] = useState<ConfigData>({});
  const [validationErrors, setValidationErrors] = useState<string[]>([]);
  const [validationWarnings, setValidationWarnings] = useState<string[]>([]);
  const [showValidation, setShowValidation] = useState(false);

  // Fetch current configuration
  const { data: configData, isLoading, error } = useQuery({
    queryKey: ['admin-config'],
    queryFn: adminApi.getConfig
  });

  // Initialize config values when data loads
  useEffect(() => {
    if (configData && Object.keys(configValues).length === 0) {
      console.log('Initializing config values:', Object.keys(configData.config));
      setConfigValues(configData.config);
    }
  }, [configData, configValues]);

  // Configuration update mutation
  const updateConfigMutation = useMutation({
    mutationFn: (config: ConfigData) => adminApi.updateConfig({ config }),
    onSuccess: (response) => {
      setModifiedFields(new Set());
      queryClient.invalidateQueries({ queryKey: ['admin-config'] });
      // Show success message or restart warning
      if (response.restart_required) {
        // Show restart warning
      }
    }
  });

  // Configuration validation mutation
  const validateConfigMutation = useMutation({
    mutationFn: (config: ConfigData) => adminApi.validateConfig({ config }),
    onSuccess: (response) => {
      setValidationErrors(response.errors || []);
      setValidationWarnings(response.warnings || []);
      setShowValidation(true);
    }
  });

  // Export configuration
  const exportConfigMutation = useMutation({
    mutationFn: (includeSensitive: boolean = false) => adminApi.exportConfig(includeSensitive),
    onSuccess: (blob) => {
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `ha-rag-bridge-config-${new Date().toISOString().slice(0, 19)}.env`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    }
  });

  const handleExport = () => {
    // Check if there are any sensitive fields
    const hasSensitiveFields = Object.values(configValues).some(category =>
      Object.values(category).some(field => field.metadata.is_sensitive)
    );

    if (hasSensitiveFields) {
      // Show confirmation dialog
      if (window.confirm(t('exportSensitiveConfirm'))) {
        exportConfigMutation.mutate(true); // Include sensitive
      } else {
        exportConfigMutation.mutate(false); // Exclude sensitive
      }
    } else {
      exportConfigMutation.mutate(false);
    }
  };

  const toggleCategory = (category: string) => {
    setExpandedCategories(prev => 
      prev.includes(category) 
        ? prev.filter(c => c !== category)
        : [...prev, category]
    );
  };

  const updateFieldValue = (category: string, field: string, value: any) => {
    const fieldKey = `${category}.${field}`;
    setModifiedFields(prev => new Set([...prev, fieldKey]));
    setConfigValues(prev => ({
      ...prev,
      [category]: {
        ...prev[category],
        [field]: {
          ...prev[category][field],
          value: value
        }
      }
    }));
  };


  const resetToDefaults = () => {
    if (configData) {
      setConfigValues(configData.config);
      setModifiedFields(new Set());
      setValidationErrors([]);
      setValidationWarnings([]);
      setShowValidation(false);
    }
  };

  const saveChanges = () => {
    if (modifiedFields.size > 0) {
      const changedConfig: ConfigData = {};
      modifiedFields.forEach(fieldKey => {
        const [category, field] = fieldKey.split('.');
        if (!changedConfig[category]) {
          changedConfig[category] = {};
        }
        changedConfig[category][field] = configValues[category][field];
      });
      updateConfigMutation.mutate(changedConfig);
    }
  };

  const validateChanges = () => {
    if (modifiedFields.size > 0) {
      const changedConfig: ConfigData = {};
      modifiedFields.forEach(fieldKey => {
        const [category, field] = fieldKey.split('.');
        if (!changedConfig[category]) {
          changedConfig[category] = {};
        }
        changedConfig[category][field] = configValues[category][field];
      });
      validateConfigMutation.mutate(changedConfig);
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-6">
        <h1 className="text-3xl font-bold">{t('settings')}</h1>
        <div className="grid gap-6">
          {Array.from({ length: 3 }).map((_, i) => (
            <Card key={i}>
              <CardHeader className="pb-3">
                <div className="h-6 bg-muted animate-pulse rounded" />
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {Array.from({ length: 4 }).map((_, j) => (
                    <div key={j} className="space-y-2">
                      <div className="h-4 bg-muted animate-pulse rounded w-1/3" />
                      <div className="h-10 bg-muted animate-pulse rounded" />
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6">
        <h1 className="text-3xl font-bold">{t('settings')}</h1>
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription>
            Failed to load configuration: {error.message}
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  const categoryOrder = [
    'database', 'embedding', 'query_processing', 'embedding_advanced',
    'conversation_memory', 'cross_encoder', 'entity_ranking', 'performance', 'query_scope', 
    'similarity', 'network', 'home_assistant', 'debug', 'security'
  ];

  const hasRestartRequired = modifiedFields.size > 0 && 
    Array.from(modifiedFields).some(fieldKey => {
      const [category, field] = fieldKey.split('.');
      return configValues[category]?.[field]?.metadata?.restart_required;
    });

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <h1 className="text-3xl font-bold">Configuration Management</h1>
        
        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={validateChanges}
            disabled={modifiedFields.size === 0 || validateConfigMutation.isPending}
          >
            <CheckCircle className="h-4 w-4 mr-2" />
            {t('validateConfig')}
          </Button>
          
          <Button
            variant="outline"
            size="sm"
            onClick={handleExport}
            disabled={exportConfigMutation.isPending}
          >
            <Download className="h-4 w-4 mr-2" />
            {t('exportConfig')}
          </Button>
          
          <Button
            variant="outline"
            size="sm"
            onClick={resetToDefaults}
            disabled={modifiedFields.size === 0}
          >
            <RotateCcw className="h-4 w-4 mr-2" />
            {t('resetToDefault')}
          </Button>
          
          <Button
            onClick={saveChanges}
            disabled={modifiedFields.size === 0 || updateConfigMutation.isPending}
            size="sm"
          >
            <Save className="h-4 w-4 mr-2" />
            {t('saveChanges')}
            {modifiedFields.size > 0 && (
              <Badge variant="secondary" className="ml-2">
                {modifiedFields.size}
              </Badge>
            )}
          </Button>
        </div>
      </div>

      {/* Restart Required Warning */}
      {hasRestartRequired && (
        <Alert className="border-orange-200 bg-orange-50">
          <AlertTriangle className="h-4 w-4 text-orange-600" />
          <AlertDescription className="text-orange-800">
            <strong>{t('restartRequired')}:</strong> {t('restartWarning')}
          </AlertDescription>
        </Alert>
      )}

      {/* Validation Results */}
      {showValidation && (validationErrors.length > 0 || validationWarnings.length > 0) && (
        <div className="space-y-2">
          {validationErrors.length > 0 && (
            <Alert variant="destructive">
              <AlertTriangle className="h-4 w-4" />
              <AlertDescription>
                <div className="font-semibold mb-2">{t('validationErrors')}:</div>
                <ul className="list-disc list-inside space-y-1">
                  {validationErrors.map((error, idx) => (
                    <li key={idx} className="text-sm">{error}</li>
                  ))}
                </ul>
              </AlertDescription>
            </Alert>
          )}
          
          {validationWarnings.length > 0 && (
            <Alert className="border-yellow-200 bg-yellow-50">
              <AlertTriangle className="h-4 w-4 text-yellow-600" />
              <AlertDescription className="text-yellow-800">
                <div className="font-semibold mb-2">{t('validationWarnings')}:</div>
                <ul className="list-disc list-inside space-y-1">
                  {validationWarnings.map((warning, idx) => (
                    <li key={idx} className="text-sm">{warning}</li>
                  ))}
                </ul>
              </AlertDescription>
            </Alert>
          )}
          
          {validationErrors.length === 0 && (
            <Alert className="border-green-200 bg-green-50">
              <CheckCircle className="h-4 w-4 text-green-600" />
              <AlertDescription className="text-green-800">
                {t('configurationValid')}
              </AlertDescription>
            </Alert>
          )}
        </div>
      )}

      {/* Configuration Categories */}
      <div className="grid gap-4">
        {categoryOrder.map(category => {
          if (!configValues[category]) {
            console.log(`Missing category: ${category}, available:`, Object.keys(configValues));
            return null;
          }
          
          const isExpanded = expandedCategories.includes(category);
          const categoryFields = configValues[category];
          const categoryHasChanges = Array.from(modifiedFields).some(field => 
            field.startsWith(`${category}.`)
          );

          // Use specialized components for new categories
          if (category === 'query_processing') {
            return (
              <QueryProcessingConfig
                key={category}
                config={configValues}
                modifiedFields={modifiedFields}
                onValueChange={updateFieldValue}
                currentLang={currentLang}
                isExpanded={isExpanded}
                onToggle={() => toggleCategory(category)}
              />
            );
          }
          
          if (category === 'embedding_advanced') {
            return (
              <EmbeddingAdvancedConfig
                key={category}
                config={configValues}
                modifiedFields={modifiedFields}
                onValueChange={updateFieldValue}
                currentLang={currentLang}
                isExpanded={isExpanded}
                onToggle={() => toggleCategory(category)}
              />
            );
          }

          if (category === 'conversation_memory') {
            return (
              <ConversationMemoryConfig
                key={category}
                config={configValues}
                modifiedFields={modifiedFields}
                onValueChange={updateFieldValue}
                currentLang={currentLang}
                isExpanded={isExpanded}
                onToggle={() => toggleCategory(category)}
              />
            );
          }

          // Default generic category rendering
          return (
            <Card key={category}>
              <Collapsible open={isExpanded} onOpenChange={() => toggleCategory(category)}>
                <CollapsibleTrigger asChild>
                  <CardHeader className="cursor-pointer hover:bg-muted/50 transition-colors pb-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <CardTitle className="flex items-center gap-2">
                          {t(`configCategories.${category}`)}
                          {categoryHasChanges && (
                            <Badge variant="secondary">
                              {Array.from(modifiedFields).filter(f => 
                                f.startsWith(`${category}.`)
                              ).length} modified
                            </Badge>
                          )}
                        </CardTitle>
                      </div>
                      {isExpanded ? (
                        <ChevronUp className="h-5 w-5" />
                      ) : (
                        <ChevronDown className="h-5 w-5" />
                      )}
                    </div>
                  </CardHeader>
                </CollapsibleTrigger>
                
                <CollapsibleContent>
                  <CardContent className="pt-0">
                    <div className="grid gap-6 md:grid-cols-2">
                      {Object.entries(categoryFields).map(([fieldName, fieldData]) => {
                        const fieldKey = `${category}.${fieldName}`;
                        const isModified = modifiedFields.has(fieldKey);
                        
                        return (
                          <ConfigField
                            key={fieldName}
                            category={category}
                            fieldName={fieldName}
                            fieldData={fieldData}
                            isModified={isModified}
                            currentLang={currentLang}
                            onValueChange={updateFieldValue}
                          />
                        );
                      })}
                    </div>
                  </CardContent>
                </CollapsibleContent>
              </Collapsible>
            </Card>
          );
        })}
      </div>
    </div>
  );
}