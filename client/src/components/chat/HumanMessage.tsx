import type { ChatMessage } from '../../lib/types';
import { cn } from '../../lib/cn';

interface HumanMessageProps {
  message: ChatMessage;
}

export function HumanMessage({ message }: HumanMessageProps) {
  return (
    <div className="flex justify-end animate-fade-in">
      <div
        className={cn(
          'max-w-[80%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed',
          'bg-black text-white rounded-br-md',
        )}
      >
        <p className="whitespace-pre-wrap break-words">{message.content}</p>
      </div>
    </div>
  );
}
