import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeHighlight from 'rehype-highlight';
import type { ChatMessage } from '../../lib/types';
import { ToolCallDisplay } from './ToolCallDisplay';

interface AssistantMessageProps {
  message: ChatMessage;
  isStreaming?: boolean;
}

export function AssistantMessage({ message, isStreaming }: AssistantMessageProps) {
  return (
    <div className="flex gap-3 animate-fade-in">
      {/* AI Avatar */}
      <div className="w-7 h-7 rounded-lg bg-black text-white flex items-center justify-center shrink-0 mt-0.5">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
        </svg>
      </div>

      <div className="flex-1 min-w-0">
        {/* Tool calls */}
        {message.toolCalls && message.toolCalls.length > 0 && (
          <div className="mb-2 space-y-1">
            {message.toolCalls.map((tc, i) => (
              <ToolCallDisplay key={`${tc.name}-${i}`} toolCall={tc} />
            ))}
          </div>
        )}

        {/* Message content */}
        <div className="markdown-content text-sm leading-relaxed text-gray-800">
          <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}>
            {message.content || (isStreaming ? '...' : '')}
          </ReactMarkdown>
        </div>
      </div>
    </div>
  );
}
