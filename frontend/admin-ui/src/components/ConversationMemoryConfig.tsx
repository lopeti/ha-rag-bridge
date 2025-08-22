import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { 
  Collapsible, 
  CollapsibleContent, 
  CollapsibleTrigger 
} from './ui/collapsible';
import { 
  ChevronDown,
  ChevronUp,
  Brain,
  Zap,
  Clock,
  Server
} from 'lucide-react';
import { ConfigField } from './ConfigField';
import type { ConfigData } from '../lib/api';

interface ConversationMemoryConfigProps {
  config: ConfigData;
  modifiedFields: Set<string>;
  onValueChange: (category: string, field: string, value: any) => void;
  currentLang: string;
  isExpanded: boolean;
  onToggle: () => void;
}

export function ConversationMemoryConfig({
  config,
  modifiedFields,
  onValueChange,
  currentLang,
  isExpanded,
  onToggle
}: ConversationMemoryConfigProps) {
  const categoryFields = config.conversation_memory || {};
  
  const categoryHasChanges = Array.from(modifiedFields).some(field => 
    field.startsWith('conversation_memory.')
  );

  // Helper to check if a field is for local models only
  const isLocalModelField = (fieldName: string) => {
    return fieldName.includes('api_base') || fieldName.includes('api_key');
  };

  // Get current model to show/hide local model fields
  const currentModel = categoryFields.conversation_summary_model?.value || 'disabled';
  const isLocalModel = ['home-llama-3b', 'qwen-7b'].includes(currentModel);

  // Group fields by functionality
  const enablementFields = ['conversation_summary_enabled'];
  const modelFields = ['conversation_summary_model', 'conversation_summary_timeout'];
  const localModelFields = ['conversation_summary_api_base', 'conversation_summary_api_key'];
  const memoryFields = ['memory_topic_boost_enabled', 'memory_decay_constant'];

  const renderFieldGroup = (title: string, icon: React.ReactNode, fields: string[], description?: string) => {
    const visibleFields = fields.filter(fieldName => {
      const field = categoryFields[fieldName];
      if (!field) return false;
      
      // Hide local model fields when not using local models
      if (isLocalModelField(fieldName) && !isLocalModel) {
        return false;
      }
      
      return true;
    });

    if (visibleFields.length === 0) return null;

    return (
      <div className="space-y-3">
        <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
          {icon}
          <span>{title}</span>
        </div>
        {description && (
          <p className="text-xs text-muted-foreground pl-6">{description}</p>
        )}
        <div className="space-y-3 pl-6">
          {visibleFields.map(fieldName => {
            const field = categoryFields[fieldName];
            const fieldKey = `conversation_memory.${fieldName}`;
            const hasChanges = modifiedFields.has(fieldKey);

            return (
              <div key={fieldName} className="space-y-2">
                <ConfigField
                  category="conversation_memory"
                  fieldName={fieldName}
                  fieldData={field}
                  onValueChange={onValueChange}
                  isModified={hasChanges}
                  currentLang={currentLang}
                />
                
                {/* Info for local model configuration */}
                {fieldName === 'conversation_summary_api_base' && isLocalModel && (
                  <div className="ml-4 text-xs text-muted-foreground">
                    {currentLang === 'hu' 
                      ? '💡 Ellenőrizd, hogy a lokális LLM szerver fut ezen a címen'
                      : '💡 Ensure the local LLM server is running at this address'
                    }
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    );
  };

  return (
    <Card className="transition-all duration-200 hover:shadow-md">
      <Collapsible open={isExpanded} onOpenChange={onToggle}>
        <CollapsibleTrigger asChild>
          <CardHeader className="cursor-pointer hover:bg-accent/50 transition-colors">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Brain className="h-5 w-5 text-primary" />
                <CardTitle className="text-lg">
                  {currentLang === 'hu' ? 'Beszélgetési Memória & LLM Összefoglaló' : 'Conversation Memory & LLM Summary'}
                </CardTitle>
                {categoryHasChanges && (
                  <Badge variant="outline" className="bg-blue-50 text-blue-700 border-blue-200">
                    {currentLang === 'hu' ? 'Módosítva' : 'Modified'}
                  </Badge>
                )}
              </div>
              <div className="flex items-center gap-2">
                {/* Model indicator */}
                {currentModel !== 'disabled' && (
                  <Badge 
                    variant={isLocalModel ? "default" : "secondary"}
                    className="text-xs"
                  >
                    {currentModel}
                  </Badge>
                )}
                {isExpanded ? (
                  <ChevronUp className="h-4 w-4" />
                ) : (
                  <ChevronDown className="h-4 w-4" />
                )}
              </div>
            </div>
          </CardHeader>
        </CollapsibleTrigger>

        <CollapsibleContent>
          <CardContent className="space-y-6">
            <div className="text-sm text-muted-foreground">
              {currentLang === 'hu' 
                ? 'Többkörös beszélgetések kontextus megjegyzése és LLM-alapú téma követés beállítása.'
                : 'Configure multi-turn conversation context memory and LLM-based topic tracking.'
              }
            </div>

            {/* Enablement Settings */}
            {renderFieldGroup(
              currentLang === 'hu' ? 'Aktiválás' : 'Enablement',
              <Zap className="h-4 w-4" />,
              enablementFields,
              currentLang === 'hu' 
                ? 'Beszélgetési memória és LLM összefoglaló be/kikapcsolása'
                : 'Enable/disable conversation memory and LLM summarization'
            )}

            {/* Model Configuration */}
            {renderFieldGroup(
              currentLang === 'hu' ? 'LLM Modell Beállítások' : 'LLM Model Configuration',
              <Brain className="h-4 w-4" />,
              modelFields,
              currentLang === 'hu' 
                ? 'Összefoglaló generáláshoz használt LLM modell és timeout'
                : 'LLM model and timeout for summary generation'
            )}

            {/* Local Model Settings */}
            {isLocalModel && renderFieldGroup(
              currentLang === 'hu' ? 'Lokális Modell API' : 'Local Model API',
              <Server className="h-4 w-4" />,
              localModelFields,
              currentLang === 'hu' 
                ? 'Lokális LLM szerver kapcsolódási adatok'
                : 'Local LLM server connection details'
            )}

            {/* Memory Enhancement */}
            {renderFieldGroup(
              currentLang === 'hu' ? 'Memória Finomhangolás' : 'Memory Enhancement',
              <Clock className="h-4 w-4" />,
              memoryFields,
              currentLang === 'hu' 
                ? 'Téma-alapú entity boost és memória decay beállítások'
                : 'Topic-based entity boost and memory decay settings'
            )}

            {/* Info Panel */}
            <div className="mt-6 p-4 bg-blue-50 rounded-lg border border-blue-200">
              <h4 className="font-medium text-blue-900 mb-2">
                {currentLang === 'hu' ? '💡 Működési Elv' : '💡 How It Works'}
              </h4>
              <ul className="text-sm text-blue-800 space-y-1">
                <li>
                  {currentLang === 'hu' 
                    ? '• Quick patterns: azonnali (2ms) domain/area felismerés'
                    : '• Quick patterns: immediate (2ms) domain/area detection'
                  }
                </li>
                <li>
                  {currentLang === 'hu' 
                    ? '• LLM summary: háttérben futó kontextus gazdagítás'
                    : '• LLM summary: background context enrichment'
                  }
                </li>
                <li>
                  {currentLang === 'hu' 
                    ? '• Entity memory: 15 perces TTL cache a többkörös beszélgetésekhez'
                    : '• Entity memory: 15-minute TTL cache for multi-turn conversations'
                  }
                </li>
                <li>
                  {currentLang === 'hu' 
                    ? '• Loop prevention: belső LLM hívások automatikus szűrése'
                    : '• Loop prevention: automatic filtering of internal LLM calls'
                  }
                </li>
              </ul>
            </div>
          </CardContent>
        </CollapsibleContent>
      </Collapsible>
    </Card>
  );
}