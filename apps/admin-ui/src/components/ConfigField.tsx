import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useMutation } from '@tanstack/react-query';
import { adminApi } from '../lib/api';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { 
  Select, 
  SelectContent, 
  SelectItem, 
  SelectTrigger, 
  SelectValue 
} from './ui/select';
import { 
  AlertCircle, 
  Eye, 
  EyeOff, 
  Info
} from 'lucide-react';
import { Textarea } from './ui/textarea';
import { Switch } from './ui/switch';
import { Slider } from './ui/slider';
import { cn } from '../lib/utils';

interface ConfigFieldProps {
  category: string;
  fieldName: string;
  fieldData: {
    value: any;
    metadata: {
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
    };
  };
  isModified: boolean;
  currentLang: string;
  onValueChange: (category: string, field: string, value: any) => void;
}

export function ConfigField({
  category,
  fieldName,
  fieldData,
  isModified,
  currentLang,
  onValueChange,
}: ConfigFieldProps) {
  const { t } = useTranslation();
  const [validationError, setValidationError] = useState<string>('');
  const [showDetails, setShowDetails] = useState(false);
  const [revealedValue, setRevealedValue] = useState<string | null>(null);

  // Mutation for revealing sensitive fields
  const revealMutation = useMutation({
    mutationFn: (fieldName: string) => adminApi.revealSensitiveField(fieldName),
    onSuccess: (data) => {
      setRevealedValue(data.value);
    },
    onError: (error) => {
      console.error('Failed to reveal sensitive field:', error);
    }
  });


  const { value, metadata } = fieldData;
  const {
    type,
    title_hu,
    title_en,
    description_hu,
    description_en,
    recommendation_hu,
    recommendation_en,
    is_sensitive,
    restart_required,
    example,
    constraints,
    default: defaultValue,
    env_var
  } = metadata;

  const title = currentLang === 'hu' ? title_hu : title_en;
  const description = currentLang === 'hu' ? description_hu : description_en;
  const recommendation = currentLang === 'hu' ? recommendation_hu : recommendation_en;


  const validateValue = (newValue: any): string => {
    if (!newValue && newValue !== 0 && newValue !== false) {
      return '';
    }

    // Type-specific validation
    if (type.includes('int') || type.includes('float')) {
      const numValue = Number(newValue);
      if (isNaN(numValue)) {
        return t('invalidValue');
      }
      
      if (constraints) {
        if (constraints.min !== undefined && numValue < constraints.min) {
          return `${t('valueOutOfRange')}: min ${constraints.min}`;
        }
        if (constraints.max !== undefined && numValue > constraints.max) {
          return `${t('valueOutOfRange')}: max ${constraints.max}`;
        }
        if (constraints.min_exclusive !== undefined && numValue <= constraints.min_exclusive) {
          return `${t('valueOutOfRange')}: > ${constraints.min_exclusive}`;
        }
        if (constraints.max_exclusive !== undefined && numValue >= constraints.max_exclusive) {
          return `${t('valueOutOfRange')}: < ${constraints.max_exclusive}`;
        }
      }
    }

    // URL validation
    if (type.includes('str') && (fieldName.includes('url') || fieldName.includes('URL'))) {
      try {
        new URL(newValue);
      } catch {
        return t('invalidValue') + ' (URL format required)';
      }
    }

    return '';
  };

  const handleValueChange = (newValue: any) => {
    const error = validateValue(newValue);
    setValidationError(error);
    
    if (!error) {
      onValueChange(category, fieldName, newValue);
    }
  };

  const getFieldType = (): string => {
    if (type.includes('bool')) return 'boolean';
    if (type.includes('int')) return 'number';
    if (type.includes('float')) return 'number';
    if (type.includes('Literal')) return 'select';
    if (is_sensitive) return 'password';
    if (fieldName.includes('url') || fieldName.includes('URL')) return 'url';
    return 'string';
  };

  const getSelectOptions = (): string[] => {
    // Extract options from Literal type annotation
    const literalMatch = type.match(/Literal\[(.*?)\]/);
    if (literalMatch) {
      return literalMatch[1].split(',').map(opt => opt.trim().replace(/['"]/g, ''));
    }

    // Hardcoded options for known fields
    if (fieldName === 'backend') {
      return ['local', 'openai', 'gemini'];
    }
    if (fieldName === 'log_level' || fieldName === 'ha_rag_log_level') {
      return ['DEBUG', 'INFO', 'WARNING', 'ERROR'];
    }

    return [];
  };

  const getCurrentValue = () => {
    if (is_sensitive && value === '***MASKED***') {
      return revealedValue ?? '***MASKED***';
    }
    return value ?? '';
  };

  const isCurrentlyMasked = () => {
    return is_sensitive && value === '***MASKED***' && revealedValue === null;
  };

  const handleToggleMask = () => {
    if (isCurrentlyMasked()) {
      // Reveal the field
      revealMutation.mutate(fieldName);
    } else {
      // Hide the field
      setRevealedValue(null);
    }
  };

  const renderField = () => {
    const fieldType = getFieldType();
    const currentValue = getCurrentValue();
    const inputProps = {
      value: currentValue,
      onChange: (e: React.ChangeEvent<HTMLInputElement>) => handleValueChange(e.target.value),
      disabled: false, // Always allow editing when revealed
      className: `${isModified ? 'border-modified bg-modified' : ''} ${validationError ? 'border-destructive bg-destructive/10' : ''}`,
    };

    switch (fieldType) {
      case 'boolean':
        return (
          <div className="flex items-center space-x-3">
            <Switch
              checked={value === true || value === 'true'}
              onCheckedChange={handleValueChange}
            />
            <span className={cn(
              "text-sm font-medium",
              (value === true || value === 'true') 
                ? "text-primary" 
                : "text-muted-foreground"
            )}>
              {(value === true || value === 'true') ? t('enabled') : t('disabled')}
            </span>
          </div>
        );
        
      case 'number':
        // Use slider only for cross_encoder and entity_ranking categories
        const useSlider = (category === 'cross_encoder' || category === 'entity_ranking') && type.includes('float');
        
        if (useSlider) {
          const numValue = typeof currentValue === 'string' ? parseFloat(currentValue) || 0 : currentValue || 0;
          
          // Define sensible ranges based on field type
          let minVal = 0;
          let maxVal = 5;
          let step = 0.1;
          
          if (fieldName.includes('scale_factor')) {
            minVal = 0.5; maxVal = 5.0; // Cross-encoder scale factor
          } else if (fieldName.includes('offset')) {
            minVal = 0.0; maxVal = 3.0; // Cross-encoder offset
          } else if (fieldName.includes('boost') && !fieldName.includes('penalty')) {
            minVal = 0.0; maxVal = 5.0; // Various boosts
          } else if (fieldName.includes('multiplier')) {
            minVal = 0.5; maxVal = 3.0; // Multipliers
          } else if (fieldName.includes('penalty')) {
            minVal = -2.0; maxVal = 0.0; // Penalties (negative values)
          }
          
          // Override with actual constraints if provided
          if (constraints?.min !== undefined) minVal = constraints.min;
          if (constraints?.max !== undefined) maxVal = constraints.max;
          
          return (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-primary">
                  {numValue.toFixed(1)}
                </span>
                <div className="text-xs text-muted-foreground">
                  {minVal} — {maxVal}
                </div>
              </div>
              <Slider
                value={[numValue]}
                onValueChange={(values) => {
                  const newValue = Math.round(values[0] * 10) / 10; // Round to 1 decimal
                  handleValueChange(newValue);
                }}
                min={minVal}
                max={maxVal}
                step={step}
                className="w-full"
              />
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>{minVal}</span>
                <span>{maxVal}</span>
              </div>
            </div>
          );
        } else {
          // Use regular Input for other categories
          return (
            <div className="flex items-center gap-2">
              <Input
                type="number"
                {...inputProps}
                min={constraints?.min}
                max={constraints?.max}
                step={type.includes('float') ? 'any' : '1'}
              />
              {constraints && (
                <div className="text-xs text-muted-foreground whitespace-nowrap">
                  {constraints.min !== undefined && constraints.max !== undefined
                    ? `${constraints.min}-${constraints.max}`
                    : constraints.min !== undefined
                    ? `≥${constraints.min}`
                    : constraints.max !== undefined
                    ? `≤${constraints.max}`
                    : ''}
                </div>
              )}
            </div>
          );
        }
        
      case 'select':
        const options = getSelectOptions();
        return (
          <Select 
            value={value} 
            onValueChange={handleValueChange}
          >
            <SelectTrigger className={isModified ? 'border-modified bg-modified' : ''}>
              <SelectValue placeholder={`Select ${fieldName}`} />
            </SelectTrigger>
            <SelectContent>
              {options.map(option => (
                <SelectItem key={option} value={option}>
                  {option}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        );
        
      case 'password':
        const masked = isCurrentlyMasked();
        return (
          <div className="flex items-center gap-2">
            <Input
              type={masked ? "password" : "text"}
              {...inputProps}
              placeholder={masked ? "***MASKED***" : "Enter password"}
            />
            {is_sensitive && (
              <Button
                variant="outline"
                size="sm"
                onClick={handleToggleMask}
                disabled={revealMutation.isPending}
              >
                {masked ? <Eye className="h-4 w-4" /> : <EyeOff className="h-4 w-4" />}
              </Button>
            )}
          </div>
        );
        
      default:
        if (description.length > 100 || value?.toString().length > 50) {
          return (
            <Textarea
              {...inputProps}
              rows={3}
              onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => handleValueChange(e.target.value)}
            />
          );
        }
        return <Input {...inputProps} />;
    }
  };

  return (
    <div className="space-y-3">
      {/* Field Header */}
      <div className="flex items-center justify-between">
        <Label htmlFor={fieldName} className="text-base font-medium flex items-center gap-2">
          {title}
          {restart_required && (
            <Badge variant="outline" className="text-xs">
              {t('restartRequired')}
            </Badge>
          )}
          {isModified && (
            <Badge variant="secondary" className="text-xs">
              Modified
            </Badge>
          )}
        </Label>
        
        <div className="flex items-center gap-1">
          {env_var && (
            <Badge variant="outline" className="text-xs font-mono">
              {env_var}
            </Badge>
          )}
          
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowDetails(!showDetails)}
          >
            <Info className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Field Description */}
      {description && (
        <p className="text-sm text-muted-foreground">{description}</p>
      )}

      {/* Input Field */}
      <div className="space-y-2">
        {renderField()}
        
        {/* Validation Error */}
        {validationError && (
          <div className="flex items-center gap-2 text-sm text-red-600">
            <AlertCircle className="h-4 w-4" />
            {validationError}
          </div>
        )}
      </div>

      {/* Detailed Information */}
      {showDetails && (
        <div className="mt-3 p-3 bg-muted/50 rounded-lg space-y-2 text-sm">
          {defaultValue !== undefined && (
            <div>
              <strong>{t('defaultValue')}:</strong> {String(defaultValue)}
            </div>
          )}
          
          {example && (
            <div>
              <strong>{t('example')}:</strong> {example}
            </div>
          )}
          
          {recommendation && (
            <div className="text-info">
              <strong>{t('recommendation')}:</strong> {recommendation}
            </div>
          )}
          
          {constraints && Object.keys(constraints).length > 0 && (
            <div>
              <strong>Constraints:</strong>{' '}
              {Object.entries(constraints).map(([key, val]) => `${key}: ${val}`).join(', ')}
            </div>
          )}
          
          <div className="text-xs text-muted-foreground">
            <strong>Type:</strong> {type}
          </div>
        </div>
      )}
    </div>
  );
}