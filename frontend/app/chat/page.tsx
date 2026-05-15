"use client";

import { useEffect, useRef, useState } from "react";
import { sourcesApi, Source, streamChat } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { Loader2, MessageSquare, Send, User, Bot, RefreshCw } from "lucide-react";
import { cn } from "@/lib/utils";

interface Message {
  role: "user" | "assistant";
  content: string;
  streaming?: boolean;
}

export default function ChatPage() {
  const [sources, setSources] = useState<Source[]>([]);
  const [selectedSources, setSelectedSources] = useState<string[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [streaming, setStreaming] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    sourcesApi.list().then((list) => {
      setSources(list.filter((s) => s.is_enabled));
    });
  }, []);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const toggleSource = (id: string) => {
    setSelectedSources((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  };

  const handleSend = () => {
    if (!input.trim() || streaming) return;
    const question = input.trim();
    setInput("");
    setMessages((m) => [...m, { role: "user", content: question }]);
    setMessages((m) => [...m, { role: "assistant", content: "", streaming: true }]);
    setStreaming(true);

    const history = messages.map((m) => ({ role: m.role, content: m.content }));

    abortRef.current = streamChat(
      question,
      sessionId,
      selectedSources,
      (token) => {
        setMessages((m) => {
          const last = m[m.length - 1];
          if (last.role !== "assistant") return m;
          return [...m.slice(0, -1), { ...last, content: last.content + token }];
        });
      },
      (id) => setSessionId(id),
      () => {
        setMessages((m) => {
          const last = m[m.length - 1];
          return [...m.slice(0, -1), { ...last, streaming: false }];
        });
        setStreaming(false);
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

  const handleClear = () => {
    if (abortRef.current) abortRef.current.abort();
    setMessages([]);
    setSessionId(null);
    setStreaming(false);
  };

  return (
    <div className="flex flex-col h-full space-y-4 max-h-[calc(100vh-3rem)]">
      <div className="flex items-center gap-3 shrink-0">
        <MessageSquare className="h-5 w-5 text-primary" />
        <h1 className="text-xl font-bold">RAG 对话</h1>
        <Button size="sm" variant="ghost" className="ml-auto text-muted-foreground" onClick={handleClear}>
          <RefreshCw className="h-3 w-3 mr-1" />
          清空对话
        </Button>
      </div>

      {/* Source selector */}
      <div className="shrink-0">
        <p className="text-xs text-muted-foreground mb-2">
          选择检索范围（不选则检索全部）
        </p>
        <div className="flex flex-wrap gap-2">
          {sources.map((s) => (
            <Badge
              key={s.id}
              variant={selectedSources.includes(s.id) ? "default" : "outline"}
              className="cursor-pointer text-xs"
              onClick={() => toggleSource(s.id)}
            >
              {s.name}
            </Badge>
          ))}
          {sources.length === 0 && (
            <span className="text-xs text-muted-foreground">暂无数据源，请先在「数据源配置」中添加</span>
          )}
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 border border-border rounded-lg overflow-hidden flex flex-col min-h-0">
        <ScrollArea className="flex-1">
          <div ref={scrollRef} className="p-4 space-y-4">
            {messages.length === 0 && (
              <div className="text-center py-16 text-muted-foreground">
                <Bot className="h-10 w-10 mx-auto mb-3 opacity-30" />
                <p className="text-sm">向 FOMO 投研助手提问</p>
                <p className="text-xs mt-1 opacity-60">基于博主推文和公众号文章的 RAG 问答</p>
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
                  {msg.content || (msg.streaming ? <Loader2 className="h-4 w-4 animate-spin" /> : "")}
                  {msg.streaming && msg.content && (
                    <span className="inline-block w-1 h-4 bg-primary ml-0.5 animate-pulse" />
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
  );
}
