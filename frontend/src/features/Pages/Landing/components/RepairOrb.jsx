"use client";

import { useCallback, useLayoutEffect, useRef } from "react";
import { ThinkingOrb, MODE_FRAMES, resolvePreset } from "thinking-orbs";

// Keep one canvas and blend its geometry instead of replacing whole orbs.
export default function RepairOrb({ state, reduced, label }) {
  const transition = useRef({ target: resolvePreset(state, 64), from: null, started: 0 });
  const lastFrame = useRef(null);

  useLayoutEffect(() => {
    transition.current = {
      target: resolvePreset(state, 64),
      from: lastFrame.current,
      started: performance.now(),
    };
  }, [state]);

  const frame = useCallback((size) => {
    const { target, from, started } = transition.current;
    const now = performance.now();
    const next = MODE_FRAMES[target.mode](size, reduced ? 0.6 : now / 1000 * target.speed, target.opts);
    const progress = reduced ? 1 : Math.min(1, (now - started) / 300);
    if (!from || progress >= 1) {
      lastFrame.current = next;
      return next;
    }
    const blend = progress * progress * (3 - 2 * progress);
    const dots = Array.from({ length: Math.max(from.dots.length, next.dots.length) }, (_, index) => {
      const source = from.dots[index] ?? { ...from.dots[index % from.dots.length], r: 0, a: 0 };
      const destination = next.dots[index] ?? { ...next.dots[index % next.dots.length], r: 0, a: 0 };
      const mix = (key, fallback = 0) => (source[key] ?? fallback) + ((destination[key] ?? fallback) - (source[key] ?? fallback)) * blend;
      return { x: mix("x"), y: mix("y"), z: mix("z"), r: mix("r"), white: mix("white"), a: mix("a", 1) };
    });
    const result = {
      dots: dots.sort((a, b) => a.z - b.z),
      lines: [
        ...from.lines.map((line) => ({ ...line, a: (line.a ?? 1) * (1 - blend) })),
        ...next.lines.map((line) => ({ ...line, a: (line.a ?? 1) * blend })),
      ],
    };
    lastFrame.current = result;
    return result;
  }, [reduced, state]);

  return <ThinkingOrb size={64} theme="dark" frame={frame} paused={reduced} aria-label={label} />;
}
