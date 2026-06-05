import { createContext, useCallback, useReducer, useRef, type ReactNode } from 'react';
import { toast } from 'sonner';
import type { ChatMessage, ContentBlock, ToolCallBlock } from '../lib/types';
import { getMessageText } from '../lib/types';
import * as runsApi from '../api/runs';
import * as threadsApi from '../api/threads';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
let _msgCounter = 0;
function nextMsgId(): string {
  return `msg_${Date.now()}_${++_msgCounter}`;
}

const LANGGRAPH_TYPE_MAP: Record<string, ChatMessage['role']> = {
  human: 'user',
  user: 'user',
  ai: 'assistant',
  assistant: 'assistant',
  tool: 'system',
  system: 'system',
};

function mapStateMessages(rawMessages: unknown[]): ChatMessage[] {
  const result: ChatMessage[] = [];

  for (const m of rawMessages) {
    const msg = m as Record<string, unknown>;
    const msgType = (msg.type as string) || (msg.role as string) || '';
    const mappedRole = LANGGRAPH_TYPE_MAP[msgType];
    if (!mappedRole) continue;

    const content = typeof msg.content === 'string' ? msg.content
      : msg.content ? JSON.stringify(msg.content)
      : '';

    const blocks: ContentBlock[] = [];

    // Add text block if there's content
    if (content) {
      blocks.push({ type: 'text', content });
    }

    // Add tool call blocks from AI messages (history = already completed)
    if (msg.tool_calls && Array.isArray(msg.tool_calls)) {
      for (const tc of msg.tool_calls as Array<Record<string, unknown>>) {
        blocks.push({
          type: 'tool_call',
          toolCall: {
            id: (tc.id as string) || (tc.name as string),
            name: tc.name as string,
            args: (tc.args as Record<string, unknown>) || {},
            status: 'completed',
          },
        });
      }
    }

    // Skip empty messages
    if (blocks.length === 0) continue;

    result.push({
      id: nextMsgId(),
      role: mappedRole,
      blocks,
      createdAt: (msg.created_at as string) || new Date().toISOString(),
    });
  }

  return result;
}

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
interface StreamState {
  messages: ChatMessage[];
  isLoading: boolean;
  threadId: string | null;
}

type StreamAction =
  | { type: 'LOAD_MESSAGES'; payload: ChatMessage[] }
  | { type: 'ADD_USER_MESSAGE'; payload: ChatMessage }
  | { type: 'START_STREAMING'; payload: string }
  | { type: 'APPEND_CONTENT'; payload: string }
  | { type: 'APPEND_TOOL_CHUNK'; payload: { id: string; name: string; chunkContent: string } }
  | { type: 'UPSERT_TOOL_CALL'; payload: { id: string; name: string; args: Record<string, unknown> } }
  | { type: 'UPDATE_TOOL_CALL'; payload: { toolCallId: string; name: string; result: string } }
  | { type: 'FINISH_STREAMING' }
  | { type: 'STREAM_ERROR'; payload: string }
  | { type: 'CLEAR_MESSAGES' };

function streamReducer(state: StreamState, action: StreamAction): StreamState {
  switch (action.type) {
    case 'LOAD_MESSAGES':
      return { ...state, messages: action.payload };
    case 'ADD_USER_MESSAGE':
      return { ...state, messages: [...state.messages, action.payload] };
    case 'START_STREAMING': {
      const assistantMsg: ChatMessage = {
        id: action.payload,
        role: 'assistant',
        blocks: [],
        createdAt: new Date().toISOString(),
      };
      return { ...state, isLoading: true, messages: [...state.messages, assistantMsg] };
    }
    case 'APPEND_CONTENT': {
      // Append text to the last text block, or create a new one
      const msgs = [...state.messages];
      const last = msgs[msgs.length - 1];
      if (last && last.role === 'assistant') {
        const blocks = [...last.blocks];
        const lastBlock = blocks[blocks.length - 1];
        if (lastBlock && lastBlock.type === 'text') {
          blocks[blocks.length - 1] = { ...lastBlock, content: lastBlock.content + action.payload };
        } else {
          blocks.push({ type: 'text', content: action.payload });
        }
        msgs[msgs.length - 1] = { ...last, blocks };
      }
      return { ...state, messages: msgs };
    }
    case 'APPEND_TOOL_CHUNK': {
      // Accumulate streaming arg deltas into a tool_call block by ID
      const msgs = [...state.messages];
      const last = msgs[msgs.length - 1];
      if (last && last.role === 'assistant') {
        const blocks = [...last.blocks];
        const idx = blocks.findIndex(b => b.type === 'tool_call' && b.toolCall.id === action.payload.id);
        if (idx >= 0) {
          const prev = blocks[idx] as ToolCallBlock;
          const prevStreaming = (prev.toolCall.args?._streaming as string) || '';
          blocks[idx] = {
            type: 'tool_call',
            toolCall: { ...prev.toolCall, args: { _streaming: prevStreaming + action.payload.chunkContent } },
          };
        } else {
          blocks.push({
            type: 'tool_call',
            toolCall: {
              id: action.payload.id,
              name: action.payload.name,
              args: { _streaming: action.payload.chunkContent },
              status: 'running',
            },
          });
        }
        msgs[msgs.length - 1] = { ...last, blocks };
      }
      return { ...state, messages: msgs };
    }
    case 'UPSERT_TOOL_CALL': {
      // Replace chunk placeholder with fully-resolved tool call args
      const msgs = [...state.messages];
      const last = msgs[msgs.length - 1];
      if (last && last.role === 'assistant') {
        const blocks = [...last.blocks];
        const idx = blocks.findIndex(b => b.type === 'tool_call' && b.toolCall.id === action.payload.id);
        if (idx >= 0) {
          const prev = blocks[idx] as ToolCallBlock;
          blocks[idx] = {
            type: 'tool_call',
            toolCall: { ...prev.toolCall, args: action.payload.args, status: 'running' },
          };
        } else {
          blocks.push({
            type: 'tool_call',
            toolCall: {
              id: action.payload.id,
              name: action.payload.name,
              args: action.payload.args,
              status: 'running',
            },
          });
        }
        msgs[msgs.length - 1] = { ...last, blocks };
      }
      return { ...state, messages: msgs };
    }
    case 'UPDATE_TOOL_CALL': {
      // Set the result on a tool_call block by ID (or name+status fallback).
      // Also parse streaming args into real args if the tool_calls event never fired.
      const msgs = [...state.messages];
      const last = msgs[msgs.length - 1];
      if (last && last.role === 'assistant') {
        const blocks = last.blocks.map((b) => {
          if (b.type === 'tool_call') {
            const tc = b.toolCall;
            if (
              (action.payload.toolCallId && tc.id === action.payload.toolCallId) ||
              (tc.name === action.payload.name && tc.status === 'running')
            ) {
              let resolvedArgs = tc.args;
              // If args were never resolved (only _streaming), try to parse them
              if (resolvedArgs && '_streaming' in resolvedArgs && Object.keys(resolvedArgs).length === 1) {
                try {
                  resolvedArgs = JSON.parse(resolvedArgs._streaming as string);
                } catch {
                  // Leave as-is if parsing fails
                }
              }
              return {
                type: 'tool_call' as const,
                toolCall: { ...tc, args: resolvedArgs, status: 'completed' as const, result: action.payload.result },
              };
            }
          }
          return b;
        });
        msgs[msgs.length - 1] = { ...last, blocks };
      }
      return { ...state, messages: msgs };
    }
    case 'FINISH_STREAMING':
      return { ...state, isLoading: false };
    case 'STREAM_ERROR': {
      const msgs = [...state.messages];
      const last = msgs[msgs.length - 1];
      if (last && last.role === 'assistant') {
        const blocks = [...last.blocks];
        // Append error as a new text block if there's existing content,
        // otherwise replace blocks entirely
        if (getMessageText(last)) {
          blocks.push({ type: 'text', content: `\n\n⚠️ 错误: ${action.payload}` });
        } else {
          blocks.push({ type: 'text', content: `⚠️ 错误: ${action.payload}` });
        }
        msgs[msgs.length - 1] = { ...last, blocks };
      }
      return { ...state, isLoading: false };
    }
    case 'CLEAR_MESSAGES':
      return { ...state, messages: [] };
    default:
      return state;
  }
}

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------
interface StreamContextValue {
  messages: ChatMessage[];
  isLoading: boolean;
  loadMessages: (threadId: string) => Promise<void>;
  submit: (text: string, threadId: string) => Promise<void>;
  stop: () => void;
}

export const StreamContext = createContext<StreamContextValue | null>(null);

export function StreamProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(streamReducer, {
    messages: [],
    isLoading: false,
    threadId: null,
  });
  const abortRef = useRef<AbortController | null>(null);

  const loadMessages = useCallback(async (threadId: string) => {
    // Clear immediately to prevent flash of old thread's messages
    dispatch({ type: 'CLEAR_MESSAGES' });
    try {
      const threadState = await threadsApi.getThreadState(threadId);
      const rawMessages = (threadState.values?.messages as unknown[]) || [];
      if (rawMessages.length > 0) {
        dispatch({ type: 'LOAD_MESSAGES', payload: mapStateMessages(rawMessages) });
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '未知错误';
      toast.error('加载消息失败', { description: msg });
    }
  }, []);

  const submit = useCallback(async (text: string, threadId: string) => {
    // Abort any in-flight stream before starting a new one
    abortRef.current?.abort();

    // Add user message
    const userMsg: ChatMessage = {
      id: nextMsgId(),
      role: 'user',
      blocks: [{ type: 'text', content: text }],
      createdAt: new Date().toISOString(),
    };
    dispatch({ type: 'ADD_USER_MESSAGE', payload: userMsg });

    // Start streaming
    const assistantId = nextMsgId();
    dispatch({ type: 'START_STREAMING', payload: assistantId });

    const controller = new AbortController();
    abortRef.current = controller;

    let receivedDone = false;

    try {
      const stream = runsApi.streamAgentResponse(
        threadId,
        [{ role: 'user', content: text }],
        controller.signal,
      );

      for await (const event of stream) {
        switch (event.type) {
          case 'message': {
            if (event.content) {
              dispatch({ type: 'APPEND_CONTENT', payload: event.content });
            }
            if (event.tool_call_chunks) {
              for (const tc of event.tool_call_chunks) {
                const dedupId = tc.id || tc.name;
                dispatch({ type: 'APPEND_TOOL_CHUNK', payload: { id: dedupId, name: tc.name, chunkContent: tc.content } });
              }
            }
            if (event.tool_calls) {
              for (const tc of event.tool_calls) {
                const dedupId = tc.id || tc.name;
                dispatch({ type: 'UPSERT_TOOL_CALL', payload: { id: dedupId, name: tc.name, args: (tc.args || {}) as Record<string, unknown> } });
              }
            }
            break;
          }
          case 'tool_result': {
            dispatch({
              type: 'UPDATE_TOOL_CALL',
              payload: {
                toolCallId: event.tool_call_id,
                name: event.name,
                result: typeof event.content === 'string' ? event.content : JSON.stringify(event.content),
              },
            });
            break;
          }
          case 'done':
            receivedDone = true;
            dispatch({ type: 'FINISH_STREAMING' });
            break;
          case 'error':
            toast.error('Agent 运行出错', { description: event.detail });
            dispatch({ type: 'STREAM_ERROR', payload: event.detail });
            break;
        }
      }
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === 'AbortError') {
        // User cancelled — no toast needed
      } else {
        const msg = err instanceof Error ? err.message : '未知错误';
        toast.error('请求失败', { description: msg });
        dispatch({ type: 'STREAM_ERROR', payload: msg });
      }
    } finally {
      if (!receivedDone) {
        dispatch({ type: 'FINISH_STREAMING' });
      }
      abortRef.current = null;
    }
  }, []);

  const stop = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  return (
    <StreamContext.Provider value={{ messages: state.messages, isLoading: state.isLoading, loadMessages, submit, stop }}>
      {children}
    </StreamContext.Provider>
  );
}
