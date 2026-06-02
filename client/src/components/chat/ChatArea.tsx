import { useEffect } from 'react';
import { useThreads } from '../../hooks/useThreads';
import { useStream } from '../../hooks/useStream';
import { MessagesList } from './MessagesList';
import { ChatInput } from './ChatInput';
import { EmptyState } from './EmptyState';

export function ChatArea() {
  const { activeThreadId } = useThreads();
  const { isLoading, submit, stop, loadMessages } = useStream();

  // Load messages when active thread changes
  useEffect(() => {
    if (activeThreadId) {
      loadMessages(activeThreadId);
    }
  }, [activeThreadId, loadMessages]);

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
      <MessagesList />
      <ChatInput
        onSubmit={handleSubmit}
        onStop={stop}
        isLoading={isLoading}
        disabled={!activeThreadId}
      />
    </div>
  );
}
