import { useTranslation } from 'react-i18next';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { Alert, AlertDescription } from './ui/alert';
import { 
  Collapsible, 
  CollapsibleContent, 
  CollapsibleTrigger 
} from './ui/collapsible';
import { InfoIcon, Layers, Search, Languages, Settings, ChevronDown, ChevronUp } from 'lucide-react';
import { ConfigField } from './ConfigField';

interface EmbeddingAdvancedConfigProps {
  config: Record<string, any>;
  modifiedFields: Set<string>;
  onValueChange: (category: string, field: string, value: any) => void;
  currentLang: string;
  isExpanded?: boolean;
  onToggle?: () => void;
}

export function EmbeddingAdvancedConfig({
  config,
  modifiedFields,
  onValueChange,
  currentLang,
  isExpanded = true,
  onToggle
}: EmbeddingAdvancedConfigProps) {
  const { t } = useTranslation();

  const embeddingAdvancedFields = config?.embedding_advanced || {};
  const categoryHasChanges = Array.from(modifiedFields).some(field => 
    field.startsWith('embedding_advanced.')
  );

  // Group fields by functionality
  const instructionFields = ['use_instruction_templates', 'query_prefix_template', 'document_prefix_template'];
  const formatFields = ['embedding_text_format'];
  const expansionFields = ['query_expansion_enabled', 'max_query_variants', 'include_query_translations', 'include_query_synonyms'];

  const renderFieldGroup = (title: string, fields: string[], icon: React.ReactNode) => (
    <div className="space-y-4">
      <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
        {icon}
        {title}
      </div>
      <div className="grid gap-4 md:grid-cols-2 pl-6 border-l-2 border-muted">
        {fields.map(fieldName => {
          if (!embeddingAdvancedFields[fieldName]) return null;
          
          const fieldKey = `embedding_advanced.${fieldName}`;
          const isModified = modifiedFields.has(fieldKey);
          
          return (
            <ConfigField
              key={fieldName}
              category="embedding_advanced"
              fieldName={fieldName}
              fieldData={embeddingAdvancedFields[fieldName] as any}
              isModified={isModified}
              currentLang={currentLang}
              onValueChange={onValueChange}
            />
          );
        })}
      </div>
    </div>
  );

  return (
    <Card>
      <Collapsible open={isExpanded} onOpenChange={onToggle}>
        <CollapsibleTrigger asChild>
          <CardHeader className="cursor-pointer hover:bg-muted/50 transition-colors pb-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Layers className="h-5 w-5 text-purple-500" />
                <CardTitle className="flex items-center gap-2">
                  {t('configCategories.embedding_advanced')}
                  {categoryHasChanges && (
                    <Badge variant="secondary">
                      {Array.from(modifiedFields).filter(f => 
                        f.startsWith('embedding_advanced.')
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
          <CardContent className="pt-0 space-y-8">
        {/* Overview Information */}
        <Alert>
          <InfoIcon className="h-4 w-4" />
          <AlertDescription>
            <div className="space-y-2">
              <strong>{t('Advanced Embedding Configuration')}</strong>
              <p className="text-sm">
                {currentLang === 'hu' 
                  ? 'Haladó embedding beállítások: instruction template-ek, query expansion és semantic search optimalizáció.'
                  : 'Advanced embedding settings: instruction templates, query expansion and semantic search optimization.'}
              </p>
              <div className="flex flex-wrap gap-2 mt-2">
                <Badge variant="outline" className="text-xs">
                  <Search className="h-3 w-3 mr-1" />
                  {currentLang === 'hu' ? 'Query/Document Split' : 'Query/Document Split'}
                </Badge>
                <Badge variant="outline" className="text-xs">
                  <Languages className="h-3 w-3 mr-1" />
                  {currentLang === 'hu' ? 'Multilingual Expansion' : 'Multilingual Expansion'}
                </Badge>
                <Badge variant="outline" className="text-xs">
                  <Settings className="h-3 w-3 mr-1" />
                  {currentLang === 'hu' ? 'Instruction Templates' : 'Instruction Templates'}
                </Badge>
              </div>
            </div>
          </AlertDescription>
        </Alert>

        {/* Instruction Templates */}
        {renderFieldGroup(
          currentLang === 'hu' ? 'Instruction Template-ek' : 'Instruction Templates',
          instructionFields,
          <Settings className="h-4 w-4" />
        )}

        {/* Text Format */}
        {renderFieldGroup(
          currentLang === 'hu' ? 'Szöveg formátum' : 'Text Format',
          formatFields,
          <Layers className="h-4 w-4" />
        )}

        {/* Query Expansion */}
        {renderFieldGroup(
          currentLang === 'hu' ? 'Query Bővítés' : 'Query Expansion',
          expansionFields,
          <Search className="h-4 w-4" />
        )}

        {/* Technical Details */}
        <div className="mt-6 p-4 bg-muted/50 rounded-lg">
          <h4 className="font-medium mb-2">
            {currentLang === 'hu' ? 'Technikai részletek:' : 'Technical Details:'}
          </h4>
          <div className="space-y-2 text-sm text-muted-foreground">
            <div>
              <strong>{currentLang === 'hu' ? 'Query prefix' : 'Query prefix'}:</strong> 
              <span className="ml-2 font-mono bg-background px-2 py-1 rounded">
                query: {currentLang === 'hu' ? 'hány fok van a nappaliban' : 'what is the temperature'}
              </span>
            </div>
            <div>
              <strong>{currentLang === 'hu' ? 'Document prefix' : 'Document prefix'}:</strong> 
              <span className="ml-2 font-mono bg-background px-2 py-1 rounded">
                passage: {currentLang === 'hu' ? 'nappali | hőmérséklet szenzor' : 'living room | temperature sensor'}
              </span>
            </div>
            <div>
              <strong>{currentLang === 'hu' ? 'Expansion példa' : 'Expansion example'}:</strong> 
              <span className="ml-2 font-mono bg-background px-2 py-1 rounded">
                {currentLang === 'hu' 
                  ? '"hőmérséklet" → ["fok", "meleg", "temperature"]'
                  : '"temperature" → ["temp", "degrees", "hőmérséklet"]'}
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