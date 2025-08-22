import React from 'react';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

interface LiveIndicatorProps {
  isLive: boolean;
}

export const LiveIndicator: React.FC<LiveIndicatorProps> = ({ isLive }) => {
  return (
    <Badge 
      variant={isLive ? "default" : "secondary"}
      className={cn(
        "relative",
        isLive && "bg-green-600 hover:bg-green-700"
      )}
    >
      {isLive && (
        <span className="absolute -top-1 -left-1 h-3 w-3">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
          <span className="relative inline-flex rounded-full h-3 w-3 bg-green-500"></span>
        </span>
      )}
      <span className="ml-2">
        {isLive ? "Live" : "Historical"}
      </span>
    </Badge>
  );
};