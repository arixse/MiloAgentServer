import { cn } from '../../lib/cn';

interface AvatarProps {
  name: string;
  size?: 'sm' | 'md';
  className?: string;
}

export function Avatar({ name, size = 'md', className }: AvatarProps) {
  const initials = name.slice(0, 2).toUpperCase();
  const sizeClass = size === 'sm' ? 'w-7 h-7 text-xs' : 'w-9 h-9 text-sm';

  return (
    <div
      className={cn(
        'rounded-full flex items-center justify-center font-semibold text-white shrink-0',
        sizeClass,
        className,
      )}
      style={{ backgroundColor: stringToColor(name) }}
      title={name}
    >
      {initials}
    </div>
  );
}

function stringToColor(str: string): string {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    hash = str.charCodeAt(i) + ((hash << 5) - hash);
  }
  const colors = [
    '#2563eb', '#7c3aed', '#db2777', '#dc2626', '#ea580c',
    '#65a30d', '#0891b2', '#4f46e5', '#9333ea', '#c026d3',
  ];
  return colors[Math.abs(hash) % colors.length];
}
