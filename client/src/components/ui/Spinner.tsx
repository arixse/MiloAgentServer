import { cn } from '../../lib/cn';

interface SpinnerProps {
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

const sizes = { sm: 'w-4 h-4', md: 'w-6 h-6', lg: 'w-8 h-8' };

export function Spinner({ size = 'md', className }: SpinnerProps) {
  return (
    <div
      className={cn('animate-spin rounded-full border-2 border-gray-300 border-t-black', sizes[size], className)}
      role="status"
      aria-label="加载中"
    />
  );
}
