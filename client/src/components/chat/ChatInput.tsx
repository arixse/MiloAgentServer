import { useState, useRef, useCallback, type KeyboardEvent } from 'react';
import { Button } from '../ui/Button';
import { Send, Square } from 'lucide-react';
import { cn } from '../../lib/cn';

interface ChatInputProps {
  onSubmit: (text: string) => void;
  onStop: () => void;
  isLoading: boolean;
  disabled?: boolean;
}

export function ChatInput({ onSubmit, onStop, isLoading, disabled }: ChatInputProps) {
  const [text, setText] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSubmit = useCallback(() => {
    const trimmed = text.trim();
    if (!trimmed || isLoading || disabled) return;
    onSubmit(trimmed);
    setText('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  }, [text, isLoading, disabled, onSubmit]);

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleInput = () => {
    const el = textareaRef.current;
    if (el) {
      el.style.height = 'auto';
      el.style.height = Math.min(el.scrollHeight, 200) + 'px';
    }
  };

  return (
    <div className="border-t border-gray-200 bg-white px-4 py-3">
      <div className="max-w-3xl mx-auto flex items-end gap-2">
        <div className="flex-1 relative">
          <textarea
            ref={textareaRef}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={handleKeyDown}
            onInput={handleInput}
            placeholder={
              disabled ? '请先选择一个会话'
              : isLoading ? 'AI 正在回复中...'
              : '输入消息... (Enter 发送, Shift+Enter 换行)'
            }
            disabled={isLoading || disabled}
            rows={1}
            className={cn(
              'w-full resize-none rounded-xl border border-gray-200 px-4 py-2.5 pr-10 text-sm',
              'placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-black/10 focus:border-gray-300',
              'disabled:bg-gray-50 disabled:cursor-not-allowed',
            )}
          />
        </div>

        {isLoading ? (
          <Button variant="danger" size="sm" onClick={onStop} className="shrink-0 px-3">
            <Square className="w-3.5 h-3.5" />
          </Button>
        ) : (
          <Button
            onClick={handleSubmit}
            disabled={!text.trim() || disabled}
            size="sm"
            className="shrink-0 px-3"
          >
            <Send className="w-3.5 h-3.5" />
          </Button>
        )}
      </div>
    </div>
  );
}
