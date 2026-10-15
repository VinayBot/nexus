/**
 * Tiny WebAudio synth for UI sounds (muted unless the user turns sound on).
 * Nothing is downloaded: a soft confirm thump, a chime and an alarm tone.
 */
let ctx: AudioContext | null = null;

function audio(): AudioContext | null {
  if (typeof window === "undefined") return null;
  ctx ??= new AudioContext();
  return ctx;
}

function tone(freq: number, dur: number, type: OscillatorType, gain: number, delay = 0, decayTo = 0.0001) {
  const a = audio();
  if (!a) return;
  const t = a.currentTime + delay;
  const osc = a.createOscillator();
  const g = a.createGain();
  osc.type = type;
  osc.frequency.setValueAtTime(freq, t);
  g.gain.setValueAtTime(gain, t);
  g.gain.exponentialRampToValueAtTime(decayTo, t + dur);
  osc.connect(g).connect(a.destination);
  osc.start(t);
  osc.stop(t + dur);
}

export const sounds = {
  /** Approval stamp. */
  confirm: () => {
    tone(80, 0.35, "sine", 0.5);
    tone(55, 0.5, "sine", 0.3, 0.02);
  },
  /** Something needs attention. */
  chime: () => [1568, 2093, 2637].forEach((f, i) => tone(f, 0.9, "sine", 0.06, i * 0.09)),
  /** Chaos switch armed. */
  alarm: () => {
    tone(392, 2.2, "triangle", 0.12);
    tone(784, 1.4, "sine", 0.05, 0.01);
  },
  /** Mission succeeded. */
  success: () => [523, 659, 784, 1047].forEach((f, i) => tone(f, 0.5, "sine", 0.07, i * 0.08)),
};
