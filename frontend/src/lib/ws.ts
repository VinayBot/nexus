import { withToken } from "./auth";
import { WS_URL } from "./config";
import { isEvent, type NexusEvent, type StreamMessage } from "./events";

export type SocketStatus = "connecting" | "open" | "reconnecting" | "closed";

interface Options {
  /** Mission id, or null for the global channel. */
  missionId: string | null;
  onEvent: (e: NexusEvent) => void;
  onStatus?: (s: SocketStatus) => void;
  /** Called when the server dropped events for a slow client; refetch from `seq`. */
  onGap?: (seq: number) => void;
}

/**
 * WebSocket with exponential-backoff reconnect. Mission sockets resume from the
 * last sequence number they saw (`?after_seq=`), so a reconnect never loses or
 * duplicates events.
 */
export class EventSocket {
  private ws: WebSocket | null = null;
  private lastSeq = 0;
  private attempts = 0;
  private stopped = false;
  private ping: ReturnType<typeof setInterval> | null = null;
  private retry: ReturnType<typeof setTimeout> | null = null;

  constructor(private readonly opts: Options) {}

  start(afterSeq = 0): void {
    this.lastSeq = afterSeq;
    this.stopped = false;
    this.connect();
  }

  stop(): void {
    this.stopped = true;
    if (this.retry) clearTimeout(this.retry);
    if (this.ping) clearInterval(this.ping);
    this.ws?.close();
    this.ws = null;
    this.opts.onStatus?.("closed");
  }

  private url(): string {
    if (!this.opts.missionId) return withToken(`${WS_URL}/ws/global`);
    return withToken(`${WS_URL}/ws/missions/${this.opts.missionId}?after_seq=${this.lastSeq}`);
  }

  private connect(): void {
    this.opts.onStatus?.(this.attempts ? "reconnecting" : "connecting");
    const ws = new WebSocket(this.url());
    this.ws = ws;
    ws.onopen = () => {
      this.attempts = 0;
      this.opts.onStatus?.("open");
      this.ping = setInterval(() => ws.readyState === WebSocket.OPEN && ws.send("ping"), 20_000);
    };
    ws.onmessage = (msg) => {
      let data: StreamMessage;
      try {
        data = JSON.parse(String(msg.data)) as StreamMessage;
      } catch {
        return;
      }
      if (isEvent(data)) {
        if (this.opts.missionId) {
          if (data.seq <= this.lastSeq) return; // duplicate after resume
          this.lastSeq = data.seq;
        }
        this.opts.onEvent(data);
      } else if (data.type === "stream.gap") {
        this.opts.onGap?.(data.seq);
      }
    };
    ws.onclose = () => {
      if (this.ping) clearInterval(this.ping);
      if (this.stopped) return;
      this.attempts += 1;
      const delay = Math.min(10_000, 400 * 2 ** Math.min(this.attempts, 5)) + Math.random() * 300;
      this.opts.onStatus?.("reconnecting");
      this.retry = setTimeout(() => this.connect(), delay);
    };
    ws.onerror = () => ws.close();
  }
}
