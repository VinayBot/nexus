/**
 * The in-app background: a calm slate base with two very soft indigo glows that drift
 * slowly (transform-only animation, so it costs almost nothing). The full sunset
 * scenery is kept for the landing page and the robots' mission floor.
 */
export function StudioBackdrop() {
  return (
    <div aria-hidden className="pointer-events-none fixed inset-0 -z-10 overflow-hidden bg-[var(--bg)]">
      <div
        className="absolute -top-[35vh] -left-[15vw] h-[80vh] w-[70vw] rounded-full [animation:aurora-a_48s_ease-in-out_infinite]"
        style={{ background: "radial-gradient(closest-side, rgb(99 102 241 / 0.12), transparent)" }}
      />
      <div
        className="absolute -right-[20vw] -bottom-[30vh] h-[75vh] w-[65vw] rounded-full [animation:aurora-b_60s_ease-in-out_infinite]"
        style={{ background: "radial-gradient(closest-side, rgb(56 189 248 / 0.06), transparent)" }}
      />
    </div>
  );
}
