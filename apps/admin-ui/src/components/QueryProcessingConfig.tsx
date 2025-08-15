import { useTranslation } from 'react-i18next';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { Alert, AlertDescription } from './ui/alert';
import { 
  Collapsible, 
  CollapsibleContent, 
  CollapsibleTrigger 
} from './ui/collapsible';
import { InfoIcon, Zap, Brain, Clock, ChevronDown, ChevronUp } from 'lucide-react';
import { ConfigField } from './ConfigField';

interface QueryProcessingConfigProps {
  config: Record<string, any>;
  modifiedFields: Set<string>;
  onValueChange: (category: string, field: string, value: any) => void;
  currentLang: string;
  isExpanded?: boolean;
  onToggle?: () => void;
}

export function QueryProcessingConfig({
  config,
  modifiedFields,
  onValueChange,
  currentLang,
  isExpanded = true,
  onToggle
}: QueryProcessingConfigProps) {
  const { t } = useTranslation();

  const queryProcessingFields = config?.query_processing || {};
  const categoryHasChanges = Array.from(modifiedFields).some(field => 
    field.startsWith('query_processing.')
  );

  return (
    <Card>
      <Collapsible open={isExpanded} onOpenChange={onToggle}>
        <CollapsibleTrigger asChild>
          <CardHeader className="cursor-pointer hover:bg-muted/50 transition-colors pb-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Brain className="h-5 w-5 text-blue-500" />
                <CardTitle className="flex items-center gap-2">
                  {t('configCategories.query_processing')}
                  {categoryHasChanges && (
                    <Badge variant="secondary">
                      {Array.from(modifiedFields).filter(f => 
                        f.startsWith('query_processing.')
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
          <CardContent className="pt-0 space-y-6">
        {/* Overview Information */}
        <Alert>
          <InfoIcon className="h-4 w-4" />
          <AlertDescription>
            <div className="space-y-2">
              <strong>{t('Query Processing Configuration')}</strong>
              <p className="text-sm">
                {currentLang === 'hu' 
                  ? 'LLM-alapú többfordulós beszélgetés kezelése coreference resolution és intent inheritance funkcióval.'
                  : 'LLM-based multi-turn conversation handling with coreference resolution and intent inheritance.'}
              </p>
              <div className="flex flex-wrap gap-2 mt-2">
                <Badge variant="outline" className="text-xs">
                  <Zap className="h-3 w-3 mr-1" />
                  {currentLang === 'hu' ? 'Gyors átírás' : 'Fast rewriting'}
                </Badge>
                <Badge variant="outline" className="text-xs">
                  <Brain className="h-3 w-3 mr-1" />
                  {currentLang === 'hu' ? 'Kontextus feloldás' : 'Context resolution'}
                </Badge>
                <Badge variant="outline" className="text-xs">
                  <Clock className="h-3 w-3 mr-1" />
                  {currentLang === 'hu' ? 'Timeout védelem' : 'Timeout protection'}
                </Badge>
              </div>
            </div>
          </AlertDescription>
        </Alert>

        {/* Configuration Fields */}
        <div className="grid gap-6 md:grid-cols-2">
          {Object.entries(queryProcessingFields).map(([fieldName, fieldData]) => {
            const fieldKey = `query_processing.${fieldName}`;
            const isModified = modifiedFields.has(fieldKey);
            
            return (
              <ConfigField
                key={fieldName}
                category="query_processing"
                fieldName={fieldName}
                fieldData={fieldData as any}
                isModified={isModified}
                currentLang={currentLang}
                onValueChange={onValueChange}
              />
            );
          })}
        </div>

        {/* Usage Examples */}
        <div className="mt-6 p-4 bg-muted/50 rounded-lg">
          <h4 className="font-medium mb-2">
            {currentLang === 'hu' ? 'Használati példák:' : 'Usage Examples:'}
          </h4>
          <div className="space-y-2 text-sm text-muted-foreground">
            <div>
              <strong>{currentLang === 'hu' ? 'Bemenet' : 'Input'}:</strong> 
              <span className="ml-2 font-mono bg-background px-2 py-1 rounded">
                {currentLang === 'hu' 
                  ? '"Hány fok van a nappaliban?" → "És a kertben?"'
                  : '"What is the temperature in the living room?" → "And in the garden?"'}
              </span>
            </div>
            <div>
              <strong>{currentLang === 'hu' ? 'Kimenet' : 'Output'}:</strong> 
              <span className="ml-2 font-mono bg-background px-2 py-1 rounded">
                {currentLang === 'hu' 
                  ? '"Hány fok van a kertben?"'
                  : '"What is the temperature in the garden?"'}
              </span>
            </div>
          </div>
        </div>
          </CardContent>
        </CollapsibleContent>
      </Collapsible>
    </Card>
  );
}