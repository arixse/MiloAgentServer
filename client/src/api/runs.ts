import { STORAGE_KEYS } from '../lib/constants';
import type { SSEEvent } from '../lib/types';

/**
 * Send a message to the agent and stream the response via SSE.
 * Uses native fetch (not axios) because axios doesn't support ReadableStream.
 */
export async function* streamAgentResponse(
  threadId: string,
  messages: { role: string; content: string }[],
  signal?: AbortSignal,
): AsyncGenerator<SSEEvent> {
  const token = localStorage.getItem(STORAGE_KEYS.AUTH_TOKEN);

  const response = await fetch(`/api/threads/${threadId}/runs/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      messages,
      stream: true,
    }),
    signal,
  });

  if (!response.ok) {
    const errorText = await response.text().catch(() => 'Unknown error');
    throw new Error(`HTTP ${response.status}: ${errorText}`);
  }

  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        const trimmed = line.trim();
        if (trimmed.startsWith('data: ')) {
          try {
            const json = JSON.parse(trimmed.slice(6));
            yield json as SSEEvent;
          } catch {
            // Skip malformed events
          }
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}
