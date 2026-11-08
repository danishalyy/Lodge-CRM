"use client";
import { useEffect, useState } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Check, Compass, Copy } from "lucide-react";
import { Button } from "@/components/ui/button";
import { aiCopy as copy } from "@/lib/strings/ai";
import MessageSources from "./MessageSources";
import ActionProposal, { Proposal } from "./ActionProposal";

export type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: any[];
  pending?: boolean;
  actions?: Proposal[];
};
export default function ChatMessage({
  message,
  conversationId,
  onDenied,
}: {
  message: Message;
  conversationId: string;
  onDenied: (message: string) => void;
}) {
  const [copied, setCopied] = useState(false),
    [copyError, setCopyError] = useState(false);
  useEffect(() => {
    if (!copied) return;
    const timer = setTimeout(() => setCopied(false), 2500);
    return () => clearTimeout(timer);
  }, [copied]);
  const assistant = message.role === "assistant";
  async function copyAnswer() {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);
      setCopyError(false);
    } catch {
      setCopyError(true);
    }
  }
  return (
    <article
      className={`aiMessage ${assistant ? "aiAssistantMessage" : "aiUserMessage"}`}
      aria-label={assistant ? copy.assistant : copy.you}
    >
      {assistant && (
        <div className="aiAssistantIdentity">
          <span className="aiAvatar" aria-hidden="true">
            <Compass size={18} />
          </span>
          <span>{copy.assistant}</span>
        </div>
      )}
      {assistant ? (
        <div className="aiMarkdown">
          <Markdown
            remarkPlugins={[remarkGfm]}
            skipHtml
            components={{
              // Model-authored URLs and images are plain text. Only server sources have authority.
              a: ({ children }) => <span>{children}</span>,
              img: ({ alt }) => <span>{alt || ""}</span>,
              h1: ({ children }) => <h3>{children}</h3>,
              h2: ({ children }) => <h3>{children}</h3>,
              table: ({ children }) => (
                <div
                  className="aiTableWrap"
                  role="region"
                  aria-label={copy.table}
                  tabIndex={0}
                >
                  <table>{children}</table>
                </div>
              ),
            }}
          >
            {message.content}
          </Markdown>
        </div>
      ) : (
        <div className="aiUserBubble">
          <span className="sr-only">{copy.you}</span>
          <p>{message.content}</p>
        </div>
      )}
      {assistant &&
        message.actions?.map((action) => (
          <ActionProposal
            key={action.id}
            proposal={action}
            conversationId={conversationId}
            onDenied={onDenied}
          />
        ))}
      {assistant && (
        <div className="aiMessageActions">
          <MessageSources sources={message.sources} />
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="aiCopyButton"
            aria-label={copied ? copy.copied : copy.copyResponse}
            title={copied ? copy.copied : copy.copyResponse}
            onClick={copyAnswer}
          >
            {copied ? <Check size={16} /> : <Copy size={16} />}
          </Button>
          <span className="aiCopyStatus" role="status">
            {copied ? copy.copied : copyError ? copy.copyFailed : ""}
          </span>
        </div>
      )}
    </article>
  );
}
