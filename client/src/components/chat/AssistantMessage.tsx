import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeHighlight from 'rehype-highlight';
import type { ChatMessage } from '../../lib/types';
import { getMessageText } from '../../lib/types';
import { ToolCallDisplay } from './ToolCallDisplay';

interface AssistantMessageProps {
  message: ChatMessage;
  isStreaming?: boolean;
  showToolCalls: boolean;
}

export function AssistantMessage({ message, isStreaming, showToolCalls }: AssistantMessageProps) {
  const text = getMessageText(message);

  // Skip rendering if nothing visible and not streaming (prevents empty avatar)
  const hasVisibleToolCalls = showToolCalls && message.blocks.some(b => b.type === 'tool_call');
  if (!isStreaming && text.length === 0 && !hasVisibleToolCalls) {
    return null;
  }

  return (
    <div className="flex gap-3 animate-fade-in">
      {/* AI Avatar */}
      <div className="w-7 h-7 rounded-lg bg-black text-white flex items-center justify-center shrink-0 mt-0.5 yyyyyyy">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
        </svg>
      </div>

      <div className="flex-1 min-w-0 space-y-2">
        {/* Render blocks in chronological order */}
        {message.blocks.map((block, i) => {
          if (block.type === 'tool_call') {
            if (!showToolCalls) return null;
            return (
              <ToolCallDisplay
                key={block.toolCall.id || `${block.toolCall.name}-${i}`}
                toolCall={block.toolCall}
              />
            );
          }
          // text block — always visible
          return (
            <div key={`text-${i}`} className="markdown-content text-sm leading-relaxed text-gray-800">
              <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}>
                {block.content || (isStreaming && i === message.blocks.length - 1 ? '...' : '')}
              </ReactMarkdown>
            </div>
          );
        })}

        {/* Empty state while waiting for first token */}
        {message.blocks.length === 0 && isStreaming && (
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
