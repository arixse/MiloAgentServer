import { useState } from 'react';
import type { ToolCall } from '../../lib/types';
import { cn } from '../../lib/cn';
import { Wrench, ChevronDown, CheckCircle, Loader2, XCircle } from 'lucide-react';

interface ToolCallDisplayProps {
  toolCall: ToolCall;
}

export function ToolCallDisplay({ toolCall }: ToolCallDisplayProps) {
  const [expanded, setExpanded] = useState(false);
  // Only show streaming animation while still running; completed tools may have
  // residual _streaming args if tool_calls event never fired to replace them
  const isStreamingArgs = toolCall.status === 'running'
    && toolCall.args && Object.keys(toolCall.args).length === 1 && '_streaming' in toolCall.args;
  const hasArgs = toolCall.args && Object.keys(toolCall.args).filter(k => k !== '_streaming').length > 0;
  // Completed tool with residual streaming args — show the raw arg string as regular text
  const hasFallbackArgs = toolCall.status !== 'running'
    && toolCall.args && '_streaming' in toolCall.args;

  const statusIcon = toolCall.status === 'completed' ? (
    <CheckCircle className="w-3.5 h-3.5 text-green-500 shrink-0" />
  ) : toolCall.status === 'running' ? (
    <Loader2 className="w-3.5 h-3.5 text-blue-500 shrink-0 animate-spin" />
  ) : toolCall.status === 'error' ? (
    <XCircle className="w-3.5 h-3.5 text-red-500 shrink-0" />
  ) : (
    <Wrench className="w-3.5 h-3.5 text-gray-400 shrink-0" />
  );

  const statusLabel = toolCall.status === 'completed' ? '完成'
    : toolCall.status === 'running' ? '运行中'
    : toolCall.status === 'error' ? '错误'
    : null;

  return (
    <div className={cn(
      'border rounded-lg overflow-hidden text-xs',
      toolCall.status === 'completed' ? 'border-green-200' :
      toolCall.status === 'error' ? 'border-red-200' :
      'border-gray-200',
    )}>
      {/* Header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-3 py-2 bg-gray-50 hover:bg-gray-100 transition-colors cursor-pointer text-left"
      >
        {statusIcon}
        <span className="font-medium text-gray-700 truncate flex-1">
          {toolCall.name}
        </span>
        {statusLabel && (
          <span className={cn(
            'text-xs px-1.5 py-0.5 rounded-full font-medium',
            toolCall.status === 'completed' && 'bg-green-100 text-green-700',
            toolCall.status === 'running' && 'bg-blue-100 text-blue-700',
            toolCall.status === 'error' && 'bg-red-100 text-red-700',
          )}>
            {statusLabel}
          </span>
        )}
        {(hasArgs || isStreamingArgs || hasFallbackArgs || toolCall.result != null) && (
          <ChevronDown className={cn('w-3.5 h-3.5 text-gray-400 transition-transform', expanded && 'rotate-180')} />
        )}
      </button>

      {/* Expandable details */}
      {expanded && (
        <div className="divide-y divide-gray-100">
          {isStreamingArgs && (
            <div className="px-3 py-2 bg-white">
              <p className="text-xs text-gray-400 mb-1 font-medium">参数</p>
              <pre className="text-xs text-blue-600 font-mono whitespace-pre-wrap break-all max-h-32 overflow-y-auto animate-pulse">
                {toolCall.args?._streaming as string}
              </pre>
            </div>
          )}
          {hasFallbackArgs && (
            <div className="px-3 py-2 bg-white">
              <p className="text-xs text-gray-400 mb-1 font-medium">参数</p>
              <pre className="text-xs text-gray-600 font-mono whitespace-pre-wrap break-all max-h-32 overflow-y-auto">
                {toolCall.args?._streaming as string}
              </pre>
            </div>
          )}
          {hasArgs && (
            <div className="px-3 py-2 bg-white">
              <p className="text-xs text-gray-400 mb-1 font-medium">参数</p>
              <pre className="text-xs text-gray-600 font-mono whitespace-pre-wrap break-all max-h-32 overflow-y-auto">
                {JSON.stringify(toolCall.args, null, 2)}
              </pre>
            </div>
          )}
          {toolCall.result != null && (
            <div className="px-3 py-2 bg-white">
              <p className="text-xs text-gray-400 mb-1 font-medium">结果</p>
              <pre className="text-xs text-gray-600 font-mono whitespace-pre-wrap break-all max-h-48 overflow-y-auto">
                {toolCall.result}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
