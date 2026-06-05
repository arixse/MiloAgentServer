import { useEffect, useState } from 'react';
import { useThreads } from '../../hooks/useThreads';
import { useStream } from '../../hooks/useStream';
import { MessagesList } from './MessagesList';
import { ChatInput } from './ChatInput';
import { EmptyState } from './EmptyState';
import { Eye, EyeOff } from 'lucide-react';

export function ChatArea() {
  const { activeThreadId } = useThreads();
  const { isLoading, submit, stop, loadMessages } = useStream();
  const [showToolCalls, setShowToolCalls] = useState(false);

  // Load messages when active thread changes, abort any in-flight stream
  useEffect(() => {
    stop();
    if (activeThreadId) {
      loadMessages(activeThreadId);
    }
  }, [activeThreadId, loadMessages, stop]);

  if (!activeThreadId) {
    return <EmptyState />;
  }

  const handleSubmit = (text: string) => {
    if (activeThreadId) {
      submit(text, activeThreadId);
    }
  };

  return (
    <div className="flex-1 flex flex-col min-h-0">
      {/* Header with toggle */}
      <div className="flex items-center justify-end px-4 py-1.5 border-b border-gray-100">
        <button
          onClick={() => setShowToolCalls(!showToolCalls)}
          className={`
            inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs
            transition-colors cursor-pointer
            ${showToolCalls
              ? 'bg-blue-100 text-blue-700 hover:bg-blue-200'
              : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
            }
          `}
          title={showToolCalls ? '隐藏详情' : '显示详情'}
        >
          {showToolCalls ? <Eye className="w-3 h-3" /> : <EyeOff className="w-3 h-3" />}
          <span>显示详情</span>
        </button>
      </div>
      <MessagesList showToolCalls={showToolCalls} />
      <ChatInput
        onSubmit={handleSubmit}
        onStop={stop}
        isLoading={isLoading}
        disabled={!activeThreadId}
      />
    </div>
  );
}
