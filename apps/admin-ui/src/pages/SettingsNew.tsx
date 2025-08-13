import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useLocation } from 'react-router-dom';
import { adminApi } from '../lib/api';
import { ConfigField } from '../components/ConfigField';
import { ServiceConnectionTest } from '../components/ServiceConnectionTest';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Alert, AlertDescription } from '../components/ui/alert';
import { 
  AlertCircle, 
  AlertTriangle,
  CheckCircle, 
  Save, 
  Download, 
  RotateCcw,
  Database,
  Cpu,
  Zap,
  Network,
  Home,
  Bug,
  Shield,
  Search,
  Target
} from 'lucide-react';
import { cn } from '../lib/utils';
import type { ConfigData, ConfigFieldData } from '../lib/api';

const categoryIcons: Record<string, React.ComponentType<any>> = {
  database: Database,
  embedding: Cpu,
  performance: Zap,
  query_scope: Target,
  similarity: Search,
  network: Network,
  home_assistant: Home,
  debug: Bug,
  security: Shield,
};

export function Settings() {
  const { t, i18n } = useTranslation();
  const currentLang = i18n.language || 'hu';
  const location = useLocation();
  const queryClient = useQueryClient();

  const [configValues, setConfigValues] = useState<ConfigData>({});
  const [modifiedFields, setModifiedFields] = useState<Set<string>>(new Set());
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
      setConfigValues(configData.config);
    }
  }, [configData, configValues]);

  // Configuration update mutation
  const updateConfigMutation = useMutation({
    mutationFn: (config: ConfigData) => adminApi.updateConfig({ config }),
    onSuccess: (response) => {
      setModifiedFields(new Set());
      queryClient.invalidateQueries({ queryKey: ['admin-config'] });
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

  const handleFieldChange = (category: string, field: string, value: any) => {
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
    
    const fieldKey = `${category}.${field}`;
    setModifiedFields(prev => new Set([...prev, fieldKey]));
    setShowValidation(false);
  };

  const handleSave = () => {
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

  const handleValidate = () => {
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

  const handleExport = () => {
    const hasSensitiveFields = Object.values(configValues).some(category =>
      Object.values(category).some((field: ConfigFieldData) => field.metadata.is_sensitive)
    );

    if (hasSensitiveFields) {
      if (window.confirm(t('exportSensitiveConfirm'))) {
        exportConfigMutation.mutate(true);
      } else {
        exportConfigMutation.mutate(false);
      }
    } else {
      exportConfigMutation.mutate(false);
    }
  };

  const handleReset = () => {
    if (window.confirm(t('resetConfirm'))) {
      setModifiedFields(new Set());
      if (configData) {
        setConfigValues(configData.config);
      }
      setShowValidation(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="text-muted-foreground">{t('loading')}...</div>
      </div>
    );
  }

  if (error) {
    return (
      <Alert className="mb-6">
        <AlertCircle className="h-4 w-4" />
        <AlertDescription>
          <strong>{t('error')}:</strong> {error.message}
        </AlertDescription>
      </Alert>
    );
  }

  if (!configData) {
    return null;
  }

  const categoryOrder = [
    'database', 'embedding', 'performance', 'query_scope', 
    'similarity', 'network', 'home_assistant', 'debug', 'security'
  ];

  const categoryEntries = categoryOrder
    .filter(name => configValues[name])
    .map(name => [name, configValues[name]] as [string, Record<string, ConfigFieldData>]);

  // Get current category from hash or default to first
  const currentCategoryName = location.hash.slice(1) || categoryEntries[0]?.[0];
  const currentCategory = categoryEntries.find(([name]) => name === currentCategoryName);

  const hasRestartRequired = modifiedFields.size > 0 && 
    Array.from(modifiedFields).some(fieldKey => {
      const [category, field] = fieldKey.split('.');
      return configValues[category]?.[field]?.metadata?.restart_required;
    });

  return (
    <div className="flex min-h-screen bg-background">
      {/* Sidebar Navigation */}
      <div className="w-80 bg-card border-r border-border sticky top-0 h-screen overflow-y-auto">
        <div className="p-6 border-b border-border">
          <h1 className="text-xl font-bold text-foreground mb-2">
            {t('configurationManagement')}
          </h1>
          <p className="text-sm text-muted-foreground">
            Konfigurálja a HA-RAG Bridge rendszer beállításokat
          </p>
          
          {modifiedFields.size > 0 && (
            <div className="mt-4 p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-200 dark:border-blue-800">
              <div className="text-sm font-medium text-blue-900 dark:text-blue-100">
                {modifiedFields.size} nem mentett változtatás
              </div>
            </div>
          )}
        </div>
        
        <nav className="p-4">
          <ul className="space-y-2">
            {categoryEntries.map(([categoryName, categoryFields]) => {
              const modifiedCount = Object.keys(categoryFields).filter(fieldName =>
                modifiedFields.has(`${categoryName}.${fieldName}`)
              ).length;
              
              const IconComponent = categoryIcons[categoryName] || Database;
              
              return (
                <li key={categoryName}>
                  <a
                    href={`#${categoryName}`}
                    className={cn(
                      "flex items-center justify-between p-3 rounded-lg transition-all duration-200",
                      currentCategoryName === categoryName
                        ? "bg-primary text-primary-foreground shadow-sm"
                        : "hover:bg-muted/50 text-foreground hover:shadow-sm"
                    )}
                    onClick={(e) => {
                      e.preventDefault();
                      window.location.hash = categoryName;
                      document.getElementById(categoryName)?.scrollIntoView({ behavior: 'smooth' });
                    }}
                  >
                    <div className="flex items-center space-x-3">
                      <IconComponent className="h-5 w-5" />
                      <div>
                        <div className="font-medium">
                          {t(`configCategories.${categoryName}`) !== `configCategories.${categoryName}` 
                            ? t(`configCategories.${categoryName}`) 
                            : categoryName.replace('_', ' ')}
                        </div>
                        <div className={cn(
                          "text-xs",
                          currentCategoryName === categoryName 
                            ? "text-primary-foreground/70"
                            : "text-muted-foreground"
                        )}>
                          {Object.keys(categoryFields).length} beállítás
                        </div>
                      </div>
                    </div>
                    {modifiedCount > 0 && (
                      <Badge variant={currentCategoryName === categoryName ? "secondary" : "outline"} className="text-xs">
                        {modifiedCount}
                      </Badge>
                    )}
                  </a>
                </li>
              );
            })}
          </ul>
        </nav>
        
        {/* Actions in Sidebar */}
        <div className="p-4 border-t border-border mt-auto">
          <div className="space-y-2">
            <Button
              onClick={handleSave}
              disabled={modifiedFields.size === 0 || updateConfigMutation.isPending}
              className="w-full"
              size="sm"
            >
              <Save className="h-4 w-4 mr-2" />
              {t('saveChanges')} {modifiedFields.size > 0 && `(${modifiedFields.size})`}
            </Button>
            
            <Button
              onClick={handleValidate}
              variant="outline"
              disabled={modifiedFields.size === 0 || validateConfigMutation.isPending}
              className="w-full"
              size="sm"
            >
              <CheckCircle className="h-4 w-4 mr-2" />
              {t('validateConfig')}
            </Button>
            
            <div className="flex space-x-2">
              <Button
                onClick={handleExport}
                variant="outline"
                className="flex-1"
                size="sm"
                disabled={exportConfigMutation.isPending}
              >
                <Download className="h-4 w-4 mr-1" />
                Export
              </Button>
              
              <Button
                onClick={handleReset}
                variant="outline"
                disabled={modifiedFields.size === 0}
                className="flex-1"
                size="sm"
              >
                <RotateCcw className="h-4 w-4 mr-1" />
                Reset
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-5xl mx-auto p-6">
          {/* Alerts */}
          {hasRestartRequired && (
            <Alert className="border-orange-200 bg-orange-50 dark:bg-orange-900/20 mb-6">
              <AlertTriangle className="h-4 w-4 text-orange-600" />
              <AlertDescription className="text-orange-800 dark:text-orange-200">
                <strong>{t('restartRequired')}:</strong> Néhány módosítás szolgáltatás újraindítást igényel.
              </AlertDescription>
            </Alert>
          )}

          {showValidation && (validationErrors.length > 0 || validationWarnings.length > 0) && (
            <div className="space-y-2 mb-6">
              {validationErrors.length > 0 && (
                <Alert variant="destructive">
                  <AlertTriangle className="h-4 w-4" />
                  <AlertDescription>
                    <div className="font-semibold mb-2">Validációs hibák:</div>
                    <ul className="list-disc list-inside space-y-1">
                      {validationErrors.map((error, idx) => (
                        <li key={idx} className="text-sm">{error}</li>
                      ))}
                    </ul>
                  </AlertDescription>
                </Alert>
              )}
              
              {validationWarnings.length > 0 && (
                <Alert className="border-yellow-200 bg-yellow-50 dark:bg-yellow-900/20">
                  <AlertTriangle className="h-4 w-4 text-yellow-600" />
                  <AlertDescription className="text-yellow-800 dark:text-yellow-200">
                    <div className="font-semibold mb-2">Figyelmeztetések:</div>
                    <ul className="list-disc list-inside space-y-1">
                      {validationWarnings.map((warning, idx) => (
                        <li key={idx} className="text-sm">{warning}</li>
                      ))}
                    </ul>
                  </AlertDescription>
                </Alert>
              )}

              {validationErrors.length === 0 && (
                <Alert className="border-green-200 bg-green-50 dark:bg-green-900/20">
                  <CheckCircle className="h-4 w-4 text-green-600" />
                  <AlertDescription className="text-green-800 dark:text-green-200">
                    A konfiguráció érvényes!
                  </AlertDescription>
                </Alert>
              )}
            </div>
          )}

          {/* Current Category */}
          {currentCategory && (
            <section key={currentCategory[0]} id={currentCategory[0]} className="scroll-mt-6">
              <div className="mb-8">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center space-x-3">
                    {React.createElement(categoryIcons[currentCategory[0]] || Database, { 
                      className: "h-8 w-8 text-primary" 
                    })}
                    <h2 className="text-3xl font-bold text-foreground">
                      {t(`configCategories.${currentCategory[0]}`) !== `configCategories.${currentCategory[0]}` 
                        ? t(`configCategories.${currentCategory[0]}`) 
                        : currentCategory[0].replace('_', ' ')}
                    </h2>
                  </div>
                  
                  {/* Service Connection Test */}
                  <div className="flex items-center gap-2">
                    {currentCategory[0] === 'database' && (
                      <ServiceConnectionTest 
                        service="arango" 
                        serviceName="ArangoDB" 
                        allConfigValues={configValues} 
                      />
                    )}
                    {currentCategory[0] === 'home_assistant' && (
                      <ServiceConnectionTest 
                        service="home_assistant" 
                        serviceName="Home Assistant" 
                        allConfigValues={configValues} 
                      />
                    )}
                    {currentCategory[0] === 'home_assistant' && configValues.home_assistant?.influx_url?.value && (
                      <ServiceConnectionTest 
                        service="influx" 
                        serviceName="InfluxDB" 
                        allConfigValues={configValues} 
                      />
                    )}
                    {currentCategory[0] === 'embedding' && (
                      <>
                        {configValues.embedding?.openai_api_key?.value && (
                          <ServiceConnectionTest 
                            service="openai" 
                            serviceName="OpenAI" 
                            allConfigValues={configValues} 
                          />
                        )}
                        {configValues.embedding?.gemini_api_key?.value && (
                          <ServiceConnectionTest 
                            service="gemini" 
                            serviceName="Gemini" 
                            allConfigValues={configValues} 
                          />
                        )}
                      </>
                    )}
                  </div>
                </div>
                <p className="text-muted-foreground text-lg">
                  {Object.keys(currentCategory[1]).length} konfigurációs beállítás ebben a kategóriában
                </p>
              </div>
              
              <div className="bg-card border border-border rounded-xl p-8 shadow-sm">
                <div className="grid grid-cols-1 xl:grid-cols-2 gap-8">
                  {Object.entries(currentCategory[1]).map(([fieldName, fieldData]) => (
                    <ConfigField
                      key={fieldName}
                      category={currentCategory[0]}
                      fieldName={fieldName}
                      fieldData={fieldData}
                      isModified={modifiedFields.has(`${currentCategory[0]}.${fieldName}`)}
                      currentLang={currentLang}
                      onValueChange={handleFieldChange}
                    />
                  ))}
                </div>
              </div>
            </section>
          )}
        </div>
      </div>
    </div>
  );
}