/**
 * Message skeleton placeholders shown while loading chat history.
 * Simulates alternating user (right-aligned) and assistant (left-aligned) messages.
 */
export function MessageSkeleton() {
  // Simulate a few alternating messages at different widths for realism
  const items = [
    { side: 'right', width: 'w-2/3' },
    { side: 'left', width: 'w-4/5' },
    { side: 'right', width: 'w-1/2' },
    { side: 'left', width: 'w-3/4' },
  ];

  return (
    <div className="space-y-6 animate-fade-in">
      {items.map((item, i) => (
        <div
          key={i}
          className={`flex ${item.side === 'right' ? 'justify-end' : 'gap-3'}`}
        >
          {/* Avatar for left-side messages */}
          {item.side === 'left' && (
            <div className="w-7 h-7 rounded-lg bg-gray-200 animate-pulse shrink-0 mt-0.5" />
          )}
          <div
            className={`
              rounded-2xl px-4 py-3 animate-pulse
              ${item.side === 'right'
                ? 'bg-gray-200 rounded-br-md max-w-[80%]'
                : 'flex-1 max-w-[80%]'
              }
            `}
          >
            {/* Simulated text lines */}
            <div className={`space-y-2 ${item.side === 'right' ? item.width : ''}`}>
              {item.side === 'left' ? (
                <>
                  <div className={`h-3 bg-gray-200 rounded ${item.width}`} />
                  <div className="h-3 bg-gray-200 rounded w-5/6" />
                  <div className="h-3 bg-gray-200 rounded w-2/3" />
                </>
              ) : (
                <div className={`h-3 bg-gray-200 rounded ${item.width}`} />
              )}
            </div>
            {/* Subtle shimmer on right-side bubbles */}
            {item.side === 'right' && (
              <div className="h-3 bg-gray-300/40 rounded w-1/3 mt-2" />
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
