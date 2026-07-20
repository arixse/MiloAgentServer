import { useAutoScroll } from '../../hooks/useAutoScroll';
import { useStream } from '../../hooks/useStream';
import { HumanMessage } from './HumanMessage';
import { AssistantMessage } from './AssistantMessage';
import { MessageSkeleton } from './MessageSkeleton';
import { getMessageText } from '../../lib/types';
import { Wrench } from 'lucide-react';

interface MessagesListProps {
  showToolCalls: boolean;
}

export function MessagesList({ showToolCalls }: MessagesListProps) {
  const { messages, isLoading, isLoadingMessages } = useStream();
  const scrollRef = useAutoScroll(messages);

  return (
    <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-6">
      <div className="max-w-3xl mx-auto space-y-6">
        {/* Skeleton loading while fetching history */}
        {isLoadingMessages && <MessageSkeleton />}

        {/* Empty state — only when truly empty (not loading) */}
        {messages.length === 0 && !isLoading && !isLoadingMessages && (
          <div className="text-center text-sm text-gray-400 py-12">
            发送一条消息开始对话
          </div>
        )}
        {messages.map((msg) => {
          // User messages always visible
          if (msg.role === 'user') {
            return <HumanMessage key={msg.id} message={msg} />;
          }

          // System messages = tool results from history (hidden when tool calls off)
          if (msg.role === 'system') {
            if (!showToolCalls) return null;
            const text = getMessageText(msg);
            if (!text) return null;
            return (
              <div key={msg.id} className="flex gap-3 animate-fade-in">
                <div className="w-7 h-7 rounded-lg bg-gray-100 text-gray-500 flex items-center justify-center shrink-0 mt-0.5 xxxxxx">
                  <Wrench className="w-3.5 h-3.5" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-xs text-gray-400 mb-1 font-medium">工具结果</div>
                  <pre className="text-xs text-gray-500 font-mono whitespace-pre-wrap break-all max-h-48 overflow-y-auto bg-gray-50 rounded-lg p-2.5">
                    {text}
                  </pre>
                </div>
              </div>
            );
          }

          // Assistant messages — always visible, tool calls toggled inside
          return (
            <AssistantMessage
              key={msg.id}
              message={msg}
              isStreaming={isLoading}
              showToolCalls={showToolCalls}
            />
          )
        })}
      </div>
    </div>
  );
}
