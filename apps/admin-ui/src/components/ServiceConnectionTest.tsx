import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useMutation } from '@tanstack/react-query';
import { adminApi } from '../lib/api';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { 
  Loader2,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Wifi
} from 'lucide-react';

interface ServiceConnectionTestProps {
  service: 'arango' | 'home_assistant' | 'influx' | 'openai' | 'gemini';
  serviceName: string;
  allConfigValues: any;
}

export function ServiceConnectionTest({ 
  service, 
  serviceName, 
  allConfigValues 
}: ServiceConnectionTestProps) {
  const { t } = useTranslation();
  const [connectionStatus, setConnectionStatus] = useState<'idle' | 'testing' | 'connected' | 'failed' | 'not_configured'>('idle');
  const [connectionError, setConnectionError] = useState<string>('');
  const [connectionDetails, setConnectionDetails] = useState<any>(null);

  // Mutation for testing connections
  const testConnectionMutation = useMutation({
    mutationFn: ({ service, overrides }: { service: string; overrides?: any }) => 
      adminApi.testConnection(service, overrides),
    onSuccess: (data) => {
      setConnectionStatus(data.status);
      setConnectionError(data.error || '');
      setConnectionDetails(data.details);
      // Auto-hide success after 8 seconds
      if (data.status === 'connected') {
        setTimeout(() => {
          setConnectionStatus('idle');
          setConnectionDetails(null);
        }, 8000);
      }
    },
    onError: (error) => {
      setConnectionStatus('failed');
      setConnectionError(error.message || 'Connection test failed');
      setConnectionDetails(null);
    }
  });

  const buildOverrides = () => {
    const overrides: any = {};
    
    if (service === 'arango') {
      overrides.arango_url = allConfigValues.database?.arango_url?.value;
      overrides.arango_user = allConfigValues.database?.arango_user?.value;
      overrides.arango_pass = allConfigValues.database?.arango_pass?.value;
      overrides.arango_db = allConfigValues.database?.arango_db?.value;
    } else if (service === 'home_assistant') {
      overrides.ha_url = allConfigValues.home_assistant?.ha_url?.value;
      overrides.ha_token = allConfigValues.home_assistant?.ha_token?.value;
    } else if (service === 'influx') {
      overrides.influx_url = allConfigValues.home_assistant?.influx_url?.value;
    } else if (service === 'openai') {
      overrides.openai_api_key = allConfigValues.embedding?.openai_api_key?.value;
    } else if (service === 'gemini') {
      overrides.gemini_api_key = allConfigValues.embedding?.gemini_api_key?.value;
      overrides.gemini_base_url = allConfigValues.embedding?.gemini_base_url?.value;
    }
    
    return overrides;
  };

  const handleTestConnection = () => {
    setConnectionStatus('testing');
    setConnectionError('');
    setConnectionDetails(null);
    
    const overrides = buildOverrides();
    console.log(`Testing ${service} with overrides:`, overrides);
    console.log('All config values:', allConfigValues);
    testConnectionMutation.mutate({ service, overrides });
  };

  const resetStatus = () => {
    setConnectionStatus('idle');
    setConnectionError('');
    setConnectionDetails(null);
  };

  return (
    <div className="flex items-center gap-2">
      {/* Status Badge or Button */}
      {connectionStatus === 'testing' && (
        <Button variant="outline" size="sm" disabled>
          <Loader2 className="h-4 w-4 animate-spin mr-2" />
          {t('testing')}...
        </Button>
      )}
      
      {connectionStatus === 'connected' && (
        <div className="flex items-center gap-2">
          <Badge variant="default" className="bg-green-600 text-white">
            <CheckCircle2 className="h-4 w-4 mr-1" />
            {t('connected')}
          </Badge>
          {connectionDetails?.version && (
            <span className="text-xs text-green-600">v{connectionDetails.version}</span>
          )}
          <Button variant="ghost" size="sm" onClick={resetStatus} className="h-6 w-6 p-0">
            ×
          </Button>
        </div>
      )}
      
      {connectionStatus === 'failed' && (
        <div className="flex items-center gap-2">
          <Badge variant="destructive">
            <XCircle className="h-4 w-4 mr-1" />
            {t('failed')}
          </Badge>
          <Button variant="ghost" size="sm" onClick={resetStatus} className="h-6 w-6 p-0">
            ×
          </Button>
        </div>
      )}
      
      {connectionStatus === 'not_configured' && (
        <div className="flex items-center gap-2">
          <Badge variant="secondary">
            <AlertCircle className="h-4 w-4 mr-1" />
            {t('notConfigured')}
          </Badge>
          <Button variant="ghost" size="sm" onClick={resetStatus} className="h-6 w-6 p-0">
            ×
          </Button>
        </div>
      )}
      
      {connectionStatus === 'idle' && (
        <Button
          variant="outline"
          size="sm"
          onClick={handleTestConnection}
          title={`${t('testConnection')}: ${serviceName}`}
        >
          <Wifi className="h-4 w-4 mr-2" />
          {serviceName}
        </Button>
      )}
      
      {/* Error Message */}
      {connectionError && connectionStatus === 'failed' && (
        <div className="text-xs text-red-600 max-w-xs truncate" title={connectionError}>
          {connectionError}
        </div>
      )}
    </div>
  );
}