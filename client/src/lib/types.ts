/** Chat message types */
export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  toolCalls?: ToolCall[];
  createdAt: string;
}

/** Tool call info (from SSE events or API response) */
export interface ToolCall {
  name: string;
  args?: Record<string, unknown>;
  result?: string;
  status?: "pending" | "running" | "completed" | "error";
}

/** Thread info from API */
export interface ThreadInfo {
  thread_id: string;
  user_id: string;
  created_at: string;
  metadata?: Record<string, unknown> | null;
}

/** SSE event from the streaming endpoint */
export type SSEEvent =
  | { type: "message"; content?: string; tool_calls?: ToolCall[]; tool_call_chunks?: ToolCallChunk[] }
  | { type: "done"; thread_id: string }
  | { type: "error"; detail: string };

export interface ToolCallChunk {
  name: string;
  content: string;
}

/** Auth types */
export interface UserInfo {
  user_id: string;
  username: string;
}

export interface TokenData {
  access_token: string;
  token_type: string;
  user_id: string;
  username: string;
}
