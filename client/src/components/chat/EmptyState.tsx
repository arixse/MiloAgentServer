import { useThreads } from '../../hooks/useThreads';
import { Button } from '../ui/Button';
import { MessageSquare, Plus } from 'lucide-react';

export function EmptyState() {
  const { createThread } = useThreads();

  return (
    <div className="flex-1 flex items-center justify-center px-4">
      <div className="text-center max-w-sm">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gray-100 mb-4">
          <MessageSquare className="w-8 h-8 text-gray-400" />
        </div>
        <h3 className="text-lg font-semibold text-gray-700 mb-2">开始对话</h3>
        <p className="text-sm text-gray-500 mb-6">
          选择一个已有的会话，或创建一个新会话开始与 AI 助手交流。
        </p>
        <Button onClick={createThread} size="lg">
          <Plus className="w-4 h-4 mr-2" />
          新建会话
        </Button>
      </div>
    </div>
  );
}
