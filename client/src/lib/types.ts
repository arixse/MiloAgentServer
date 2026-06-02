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
  id?: string;
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
  | { type: "message"; content?: string; tool_calls?: RawToolCall[]; tool_call_chunks?: RawToolCallChunk[] }
  | { type: "tool_result"; tool_call_id: string; name: string; content: string }
  | { type: "done"; thread_id: string }
  | { type: "error"; detail: string };

/** Raw tool call from backend SSE (not yet merged with result) */
export interface RawToolCall {
  id?: string;
  name: string;
  args?: Record<string, unknown>;
}

export interface RawToolCallChunk {
  id?: string;
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
