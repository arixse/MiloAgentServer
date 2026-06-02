import { createContext, useCallback, useReducer, useRef, type ReactNode } from 'react';
import { toast } from 'sonner';
import type { ChatMessage, ToolCall } from '../lib/types';
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
  return rawMessages
    .filter((m: unknown) => {
      const msg = m as Record<string, unknown>;
      const msgType = (msg.type as string) || (msg.role as string);
      return msgType && msg.content;
    })
    .map((m: unknown) => {
      const msg = m as Record<string, unknown>;
      const msgType = (msg.type as string) || (msg.role as string) || '';
      const mappedRole = LANGGRAPH_TYPE_MAP[msgType] || 'user';
      return {
        id: nextMsgId(),
        role: mappedRole,
        content: typeof msg.content === 'string' ? msg.content : JSON.stringify(msg.content),
        createdAt: (msg.created_at as string) || new Date().toISOString(),
      };
    });
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
  | { type: 'APPEND_TOOL_CALL'; payload: ToolCall }
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
        content: '',
        createdAt: new Date().toISOString(),
      };
      return { ...state, isLoading: true, messages: [...state.messages, assistantMsg] };
    }
    case 'APPEND_CONTENT': {
      const msgs = [...state.messages];
      const last = msgs[msgs.length - 1];
      if (last && last.role === 'assistant') {
        msgs[msgs.length - 1] = { ...last, content: last.content + action.payload };
      }
      return { ...state, messages: msgs };
    }
    case 'APPEND_TOOL_CALL': {
      const msgs = [...state.messages];
      const last = msgs[msgs.length - 1];
      if (last && last.role === 'assistant') {
        const existing = last.toolCalls || [];
        msgs[msgs.length - 1] = { ...last, toolCalls: [...existing, action.payload] };
      }
      return { ...state, messages: msgs };
    }
    case 'FINISH_STREAMING':
      return { ...state, isLoading: false };
    case 'STREAM_ERROR': {
      const msgs = [...state.messages];
      const last = msgs[msgs.length - 1];
      if (last && last.role === 'assistant' && !last.content) {
        msgs[msgs.length - 1] = { ...last, content: `⚠️ 错误: ${action.payload}` };
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
    try {
      const threadState = await threadsApi.getThreadState(threadId);
      const rawMessages = (threadState.values?.messages as unknown[]) || [];
      if (rawMessages.length > 0) {
        dispatch({ type: 'LOAD_MESSAGES', payload: mapStateMessages(rawMessages) });
      } else {
        dispatch({ type: 'CLEAR_MESSAGES' });
      }
    } catch {
      dispatch({ type: 'CLEAR_MESSAGES' });
    }
  }, []);

  const submit = useCallback(async (text: string, threadId: string) => {
    // Add user message
    const userMsg: ChatMessage = {
      id: nextMsgId(),
      role: 'user',
      content: text,
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
            if (event.tool_calls) {
              for (const tc of event.tool_calls) {
                dispatch({ type: 'APPEND_TOOL_CALL', payload: tc });
              }
            }
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
