/** Backend base URL. Override with NEXT_PUBLIC_API_URL. */
export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");

/** WebSocket base derived from the API URL (http→ws, https→wss). */
export const WS_URL = API_URL.replace(/^http/, "ws");
