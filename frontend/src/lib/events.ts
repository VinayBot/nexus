import type { NexusEvent } from "./generated/events";

export type { NexusEvent } from "./generated/events";

export type EventType = NexusEvent["type"];
export type EventOf<T extends EventType> = Extract<NexusEvent, { type: T }>;
export type PayloadOf<T extends EventType> = EventOf<T>["payload"];

/** Control messages the WebSocket may send besides events. */
export interface StreamGap {
  type: "stream.gap";
  dropped: number;
  seq: number;
}
export interface Pong {
  type: "pong";
}
export type StreamMessage = NexusEvent | StreamGap | Pong;

export function isEvent(m: StreamMessage): m is NexusEvent {
  return "payload" in m && "seq" in m;
}

/** Narrowing helper: `if (is(e, "council.verdict")) e.payload.winner`. */
export function is<T extends EventType>(e: NexusEvent, type: T): e is EventOf<T> {
  return e.type === type;
}
