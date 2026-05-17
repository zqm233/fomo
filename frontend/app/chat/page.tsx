"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { sourcesApi, streamChat, chatApi, ChatSession, ChatMessage } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Loader2, MessageSquare, Send, User, Bot, Plus, Trash2 } from "lucide-react";
import { cn } from "@/lib/utils";
import ReactMarkdown from "react-markdown";

interface Message {
  role: "user" | "assistant";
  content: string;
  streaming?: boolean;
}

function fmtDate(iso: string) {
  const d = new Date(iso);
  const today = new Date();
  const isToday =
    d.getFullYear() === today.getFullYear() &&
    d.getMonth() === today.getMonth() &&
    d.getDate() === today.getDate();
  if (isToday) return d.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
  return d.toLocaleDateString("zh-CN", { month: "numeric", day: "numeric" });
}

export default function ChatPage() {
  const [allSourceIds, setAllSourceIds] = useState<string[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [streaming, setStreaming] = useState(false);
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const abortRef = useRef<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  const loadSessions = useCallback(() => {
    chatApi.listSessions().then(setSessions).catch(() => {});
  }, []);

  useEffect(() => {
    sourcesApi.list().then((list) => {
      setAllSourceIds(list.filter((s) => s.is_enabled).map((s) => s.id));
    });
    loadSessions();
  }, [loadSessions]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const loadSession = async (sid: string) => {
    if (streaming) return;
    try {
      const history = await chatApi.getHistory(sid);
      setSessionId(sid);
      setMessages(
        history.map((m: ChatMessage) => ({ role: m.role as "user" | "assistant", content: m.content }))
      );
    } catch { /* ignore */ }
  };

  const handleNew = () => {
    if (abortRef.current) abortRef.current.abort();
    setMessages([]);
    setSessionId(null);
    setStreaming(false);
  };

  const handleDelete = async (sid: string, e: React.MouseEvent) => {
    e.stopPropagation();
    await chatApi.deleteSession(sid);
    setSessions((prev) => prev.filter((s) => s.session_id !== sid));
    if (sessionId === sid) handleNew();
  };

  const handleSend = () => {
    if (!input.trim() || streaming) return;
    const question = input.trim();
    setInput("");
    setMessages((m) => [...m, { role: "user", content: question }]);
    setMessages((m) => [...m, { role: "assistant", content: "", streaming: true }]);
    setStreaming(true);

    abortRef.current = streamChat(
      question,
      sessionId,
      allSourceIds,
      (token) => {
        setMessages((m) => {
          const last = m[m.length - 1];
          if (last.role !== "assistant") return m;
          return [...m.slice(0, -1), { ...last, content: last.content + token }];
        });
      },
      (id) => {
        setSessionId(id);
      },
      () => {
        setMessages((m) => {
          const last = m[m.length - 1];
          return [...m.slice(0, -1), { ...last, streaming: false }];
        });
        setStreaming(false);
        loadSessions();
      },
      (err) => {
        setMessages((m) => {
          const last = m[m.length - 1];
          return [...m.slice(0, -1), { ...last, content: `错误：${err.message}`, streaming: false }];
        });
        setStreaming(false);
      }
    );
  };

  return (
    <div className="flex h-[calc(100vh-3rem)] gap-4">
      {/* Sessions sidebar */}
      <div className="w-52 shrink-0 flex flex-col border border-border rounded-xl overflow-hidden bg-card">
        <div className="flex items-center justify-between px-3 py-2.5 border-b border-border bg-muted/30 shrink-0">
          <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">历史对话</span>
          <Button size="sm" variant="ghost" className="h-6 w-6 p-0" onClick={handleNew} title="新对话">
            <Plus className="h-3.5 w-3.5" />
          </Button>
        </div>
        <ScrollArea className="flex-1">
          {sessions.length === 0 ? (
            <p className="text-xs text-muted-foreground text-center py-8 px-3">暂无历史记录</p>
          ) : (
            <div className="py-1">
              {sessions.map((s) => (
                <button
                  key={s.session_id}
                  onClick={() => loadSession(s.session_id)}
                  className={cn(
                    "group w-full text-left px-3 py-2 hover:bg-muted/50 transition-colors",
                    sessionId === s.session_id && "bg-primary/10"
                  )}
                >
                  <div className="flex items-start justify-between gap-1">
                    <p className={cn(
                      "text-xs truncate flex-1 leading-snug",
                      sessionId === s.session_id ? "text-primary font-medium" : "text-foreground"
                    )}>
                      {s.title}
                    </p>
                    <div
                      role="button"
                      onClick={(e) => handleDelete(s.session_id, e)}
                      className="opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-red-500 transition-all shrink-0 mt-0.5 cursor-pointer"
                    >
                      <Trash2 className="h-3 w-3" />
                    </div>
                  </div>
                  <p className="text-xs text-muted-foreground/60 mt-0.5">{fmtDate(s.last_at)}</p>
                </button>
              ))}
            </div>
          )}
        </ScrollArea>
      </div>

      {/* Main chat area */}
      <div className="flex-1 flex flex-col space-y-3 min-w-0">
        <div className="flex items-center gap-3 shrink-0">
          <MessageSquare className="h-5 w-5 text-primary" />
          <h1 className="text-xl font-bold">RAG 对话</h1>
        </div>

        {/* Messages */}
        <div className="flex-1 border border-border rounded-lg overflow-hidden flex flex-col min-h-0">
          <ScrollArea className="flex-1">
            <div ref={scrollRef} className="p-4 space-y-4">
              {messages.length === 0 && (
                <div className="text-center py-16 text-muted-foreground">
                  <Bot className="h-10 w-10 mx-auto mb-3 opacity-30" />
                  <p className="text-sm">向 FOMO 投研助手提问</p>
                  <p className="text-xs mt-1 opacity-60">基于公众号文章的 RAG 问答</p>
                </div>
              )}
              {messages.map((msg, i) => (
                <div
                  key={i}
                  className={cn("flex gap-3", msg.role === "user" ? "flex-row-reverse" : "flex-row")}
                >
                  <div
                    className={cn(
                      "h-7 w-7 rounded-full flex items-center justify-center shrink-0 mt-0.5",
                      msg.role === "user" ? "bg-primary/20" : "bg-muted"
                    )}
                  >
                    {msg.role === "user" ? (
                      <User className="h-4 w-4 text-primary" />
                    ) : (
                      <Bot className="h-4 w-4 text-muted-foreground" />
                    )}
                  </div>
                  <div
                    className={cn(
                      "max-w-[75%] px-3 py-2 rounded-lg text-sm leading-relaxed",
                      msg.role === "user"
                        ? "bg-primary/10 text-foreground"
                        : "bg-muted text-foreground"
                    )}
                  >
                    {msg.role === "assistant" ? (
                      <>
                        <div className="prose prose-sm max-w-none dark:prose-invert prose-p:my-1 prose-ul:my-1 prose-ol:my-1 prose-li:my-0 prose-headings:my-2">
                          <ReactMarkdown>{msg.content}</ReactMarkdown>
                        </div>
                        {msg.streaming && msg.content && (
                          <span className="inline-block w-1 h-4 bg-primary ml-0.5 animate-pulse" />
                        )}
                        {msg.streaming && !msg.content && <Loader2 className="h-4 w-4 animate-spin" />}
                      </>
                    ) : (
                      msg.content || ""
                    )}
                  </div>
                </div>
              ))}
            </div>
          </ScrollArea>

          {/* Input */}
          <div className="border-t border-border p-3 flex gap-2 shrink-0">
            <Input
              className="flex-1 bg-background"
              placeholder="输入你的问题…"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleSend();
                }
              }}
              disabled={streaming}
            />
            <Button size="sm" onClick={handleSend} disabled={streaming || !input.trim()}>
              {streaming ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
