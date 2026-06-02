import { useState } from 'react';
import type { ToolCall } from '../../lib/types';
import { cn } from '../../lib/cn';
import { Wrench, ChevronDown } from 'lucide-react';

interface ToolCallDisplayProps {
  toolCall: ToolCall;
}

export function ToolCallDisplay({ toolCall }: ToolCallDisplayProps) {
  const [expanded, setExpanded] = useState(false);
  const hasArgs = toolCall.args && Object.keys(toolCall.args).length > 0;

  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden text-xs">
      {/* Header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-3 py-2 bg-gray-50 hover:bg-gray-100 transition-colors cursor-pointer text-left"
      >
        <Wrench className="w-3.5 h-3.5 text-gray-500 shrink-0" />
        <span className="font-medium text-gray-700 truncate">
          {toolCall.name}
        </span>
        {toolCall.status && (
          <span className={cn(
            'ml-auto text-xs px-1.5 py-0.5 rounded-full',
            toolCall.status === 'completed' && 'bg-green-100 text-green-700',
            toolCall.status === 'running' && 'bg-blue-100 text-blue-700',
            toolCall.status === 'error' && 'bg-red-100 text-red-700',
            toolCall.status === 'pending' && 'bg-gray-100 text-gray-500',
          )}>
            {toolCall.status === 'completed' ? '完成' : toolCall.status === 'running' ? '运行中' : toolCall.status === 'error' ? '错误' : '等待中'}
          </span>
        )}
        {hasArgs && (
          <ChevronDown className={cn('w-3.5 h-3.5 text-gray-400 transition-transform', expanded && 'rotate-180')} />
        )}
      </button>

      {/* Args (expandable) */}
      {hasArgs && expanded && (
        <div className="px-3 py-2 border-t border-gray-100 bg-white">
          <pre className="text-xs text-gray-600 font-mono whitespace-pre-wrap break-all">
            {JSON.stringify(toolCall.args, null, 2)}
          </pre>
        </div>
      )}

      {/* Result */}
      {toolCall.result && (
        <div className="px-3 py-2 border-t border-gray-100 bg-white text-gray-600">
          {toolCall.result}
        </div>
      )}
    </div>
  );
}
