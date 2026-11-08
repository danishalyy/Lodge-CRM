"use client";
import { useEffect, useRef } from "react";
import { ArrowUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Form } from "@/components/ui/form";
import { aiCopy as copy } from "@/lib/strings/ai";

export default function ChatComposer({
  question,
  setQuestion,
  busy,
  onSubmit,
}: {
  question: string;
  setQuestion: (value: string) => void;
  busy: boolean;
  onSubmit: (e: React.FormEvent<HTMLFormElement>) => Promise<void>;
}) {
  const input = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    if (!input.current) return;
    input.current.style.height = "auto";
    input.current.style.height =
      Math.min(input.current.scrollHeight, 180) + "px";
  }, [question]);
  return (
    <div className="aiComposerDock">
      <Form className="aiComposer" onSubmit={onSubmit}>
        <Field label={<span className="sr-only">{copy.question}</span>}>
          <textarea
            ref={input}
            name="content"
            className="textarea"
            placeholder={copy.placeholder}
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            required
            maxLength={3000}
            rows={1}
            aria-describedby="ai-composer-hint"
            onKeyDown={(e) => {
              if (
                e.key === "Enter" &&
                !e.shiftKey &&
                !e.nativeEvent.isComposing
              ) {
                e.preventDefault();
                if (!busy) e.currentTarget.form?.requestSubmit();
              }
            }}
          />
        </Field>
        <Button
          type="submit"
          size="icon"
          className="aiSendButton"
          disabled={busy || !question.trim()}
          aria-label={copy.send}
          title={copy.send}
        >
          <ArrowUp size={20} />
        </Button>
      </Form>
      <p className="aiComposerHint" id="ai-composer-hint">
        <span>{copy.keyboardHint}</span>
        <span className="aiHintDivider" aria-hidden="true">
          {" "}
          ·{" "}
        </span>
        <span>{copy.reviewHint}</span>
      </p>
    </div>
  );
}
