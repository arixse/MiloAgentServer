import { useThreads } from '../../hooks/useThreads';
import { Button } from '../ui/Button';
import { Spinner } from '../ui/Spinner';
import { ThreadItem } from './ThreadItem';
import { Plus } from 'lucide-react';

export function ThreadHistory() {
  const { threads, activeThreadId, isLoading, createThread, selectThread, deleteThread } = useThreads();

  return (
    <aside className="w-64 border-r border-gray-200 bg-gray-50/50 flex flex-col shrink-0">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-3 border-b border-gray-100">
        <h2 className="text-sm font-semibold text-gray-700">会话列表</h2>
        <Button
          variant="ghost"
          size="sm"
          onClick={createThread}
          title="新建会话"
          className="p-1 h-auto"
        >
          <Plus className="w-4 h-4" />
        </Button>
      </div>

      {/* Thread list */}
      <div className="flex-1 overflow-y-auto p-2 space-y-0.5">
        {isLoading && threads.length === 0 ? (
          <div className="flex items-center justify-center py-8">
            <Spinner size="sm" />
          </div>
        ) : threads.length === 0 ? (
          <div className="text-center py-8">
            <p className="text-sm text-gray-400 mb-2">暂无会话</p>
            <Button variant="secondary" size="sm" onClick={createThread}>
              <Plus className="w-3.5 h-3.5 mr-1" />
              新建会话
            </Button>
          </div>
        ) : (
          threads.map((t) => (
            <ThreadItem
              key={t.thread_id}
              thread={t}
              isActive={t.thread_id === activeThreadId}
              onSelect={selectThread}
              onDelete={deleteThread}
            />
          ))
        )}
      </div>
    </aside>
  );
}
