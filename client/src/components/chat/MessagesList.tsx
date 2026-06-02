import { useAutoScroll } from '../../hooks/useAutoScroll';
import { useStream } from '../../hooks/useStream';
import { HumanMessage } from './HumanMessage';
import { AssistantMessage } from './AssistantMessage';

export function MessagesList() {
  const { messages, isLoading } = useStream();
  const scrollRef = useAutoScroll(messages);

  return (
    <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-6">
      <div className="max-w-3xl mx-auto space-y-6">
        {messages.length === 0 && !isLoading && (
          <div className="text-center text-sm text-gray-400 py-12">
            发送一条消息开始对话
          </div>
        )}
        {messages.map((msg) =>
          msg.role === 'user' ? (
            <HumanMessage key={msg.id} message={msg} />
          ) : (
            <AssistantMessage key={msg.id} message={msg} isStreaming={isLoading} />
          ),
        )}
        {isLoading && messages.length > 0 && messages[messages.length - 1]?.role !== 'assistant' && (
          <div className="flex items-center gap-2 text-sm text-gray-400">
            <div className="flex gap-1">
              <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
              <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
              <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
