export type LiveFrame = {
  event: string;
  data: Record<string, unknown>;
  id?: string;
};
// Same-origin fetch keeps expected-user/lodge headers and an HttpOnly session.
// Resume tokens remain in memory; no private API response is stored on disk.
export async function readLiveFrames(
  response: Response,
  signal: AbortSignal,
  receive: (frame: LiveFrame) => void,
) {
  if (
    !response.headers.get("content-type")?.includes("text/event-stream") ||
    !response.body
  )
    throw new Error("stream unavailable");
  const reader = response.body.getReader(),
    decoder = new TextDecoder();
  let buffer = "";
  try {
    while (!signal.aborted) {
      const { value, done } = await reader.read();
      if (done) return;
      buffer = (buffer + decoder.decode(value, { stream: true })).replace(
        /\r\n/g,
        "\n",
      );
      if (buffer.length > 65536) throw new Error("stream frame too large");
      let end: number;
      while ((end = buffer.indexOf("\n\n")) >= 0) {
        const block = buffer.slice(0, end);
        buffer = buffer.slice(end + 2);
        let event = "message",
          id: string | undefined;
        const data: string[] = [];
        for (const line of block.split("\n")) {
          if (line.startsWith("event:")) event = line.slice(6).trim();
          else if (line.startsWith("id:") && !line.includes("\0"))
            id = line.slice(3).trim();
          else if (line.startsWith("data:"))
            data.push(line.slice(5).trimStart());
        }
        if (!data.length) continue;
        const parsed: unknown = JSON.parse(data.join("\n"));
        if (!parsed || typeof parsed !== "object" || Array.isArray(parsed))
          throw new Error("invalid stream frame");
        if (!signal.aborted)
          receive({ event, data: parsed as Record<string, unknown>, id });
      }
    }
  } finally {
    await reader.cancel().catch(() => {});
    reader.releaseLock();
  }
}
