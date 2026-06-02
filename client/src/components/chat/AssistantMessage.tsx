import { useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeHighlight from 'rehype-highlight';
import type { ChatMessage } from '../../lib/types';
import { getMessageText } from '../../lib/types';
import { ToolCallDisplay } from './ToolCallDisplay';

interface AssistantMessageProps {
  message: ChatMessage;
  isStreaming?: boolean;
  showIntermediate: boolean;
}

export function AssistantMessage({ message, isStreaming, showIntermediate }: AssistantMessageProps) {
  const text = getMessageText(message);

  // In "简洁" mode, find the last tool_call block to distinguish intermediate
  // text (before the last tool call) from final answer (after the last tool call)
  const lastToolCallIdx = useMemo(() => {
    for (let i = message.blocks.length - 1; i >= 0; i--) {
      if (message.blocks[i].type === 'tool_call') return i;
    }
    return -1;
  }, [message.blocks]);

  // Determine which blocks are visible in the current mode
  const visibleBlockCount = message.blocks.filter((block, i) => {
    if (block.type === 'tool_call') return showIntermediate;
    // text block: hidden if it's intermediate (before last tool call in 简洁 mode)
    if (!showIntermediate && lastToolCallIdx >= 0 && i < lastToolCallIdx) return false;
    return true;
  }).length;

  // If nothing is visible and we're not streaming, don't render an empty bubble
  if (visibleBlockCount === 0 && !isStreaming) {
    return null;
  }

  return (
    <div className="flex gap-3 animate-fade-in">
      {/* AI Avatar */}
      <div className="w-7 h-7 rounded-lg bg-black text-white flex items-center justify-center shrink-0 mt-0.5">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
        </svg>
      </div>

      <div className="flex-1 min-w-0 space-y-2">
        {/* Render blocks in chronological order */}
        {message.blocks.map((block, i) => {
          if (block.type === 'tool_call') {
            if (!showIntermediate) return null;
            return (
              <ToolCallDisplay
                key={block.toolCall.id || `${block.toolCall.name}-${i}`}
                toolCall={block.toolCall}
              />
            );
          }
          // text block — hide if intermediate (before last tool call in 简洁 mode)
          if (!showIntermediate && lastToolCallIdx >= 0 && i < lastToolCallIdx) {
            return null;
          }
          return (
            <div
              key={`text-${i}`}
              className="markdown-content text-sm leading-relaxed text-gray-800"
            >
              <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}>
                {block.content || (isStreaming && i === message.blocks.length - 1 ? '...' : '')}
              </ReactMarkdown>
            </div>
          );
        })}

        {/* Show pulse when streaming but nothing visible yet (all blocks hidden or no blocks) */}
        {isStreaming && visibleBlockCount === 0 && (
          <div className="markdown-content text-sm leading-relaxed text-gray-400 animate-pulse">
            ...
          </div>
        )}

        {/* Show text-only fallback when blocks is empty but streaming ended */}
        {!isStreaming && text && message.blocks.length === 0 && (
          <div className="markdown-content text-sm leading-relaxed text-gray-800">
            <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}>
              {text}
            </ReactMarkdown>
          </div>
        )}
      </div>
    </div>
  );
}
