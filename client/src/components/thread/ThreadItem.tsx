import type { ThreadInfo } from '../../lib/types';
import { cn } from '../../lib/cn';
import { MessageSquare, Trash2 } from 'lucide-react';
import { Button } from '../ui/Button';

interface ThreadItemProps {
  thread: ThreadInfo;
  isActive: boolean;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
}

export function ThreadItem({ thread, isActive, onSelect, onDelete }: ThreadItemProps) {
  const createdDate = new Date(thread.created_at);

  return (
    <div
      onClick={() => onSelect(thread.thread_id)}
      className={cn(
        'group flex items-center gap-2.5 px-3 py-2.5 rounded-lg cursor-pointer transition-colors',
        isActive
          ? 'bg-gray-100 text-gray-900'
          : 'text-gray-600 hover:bg-gray-50 hover:text-gray-800',
      )}
    >
      <MessageSquare className="w-4 h-4 shrink-0" />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium truncate">
          {thread.metadata?.title as string || `会话 ${thread.thread_id.slice(0, 8)}`}
        </p>
        <p className="text-xs text-gray-400 mt-0.5">
          {createdDate.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
        </p>
      </div>
      <Button
        variant="ghost"
        size="sm"
        className="opacity-0 group-hover:opacity-100 transition-opacity shrink-0 p-1 h-auto"
        onClick={(e) => {
          e.stopPropagation();
          onDelete(thread.thread_id);
        }}
        title="删除会话"
      >
        <Trash2 className="w-3.5 h-3.5 text-gray-400 hover:text-red-500" />
      </Button>
    </div>
  );
}
