"use client";

import { useLayoutEffect, useRef } from "react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

export function useRepairScroll({ root, reduced, ready, introComplete, setActive, count }) {
  const animation = useRef(null);
  const positions = useRef([]);

  useLayoutEffect(() => {
    if (!ready || !introComplete || reduced || !root.current) return;
    gsap.registerPlugin(ScrollTrigger);
    const context = gsap.context(() => {
      const scenes = [...root.current.querySelectorAll("[data-repair-scene]")];
      const line = root.current.querySelector("[data-repair-line-reveal]");
      const state = { stage: 0 };
      let current = 0;
      setActive(0);
      gsap.set(line, { attr: { width: 0 } });
      const timeline = gsap.timeline({
        scrollTrigger: {
          trigger: root.current,
          start: "top 104px",
          end: () => `+=${Math.max(480, window.innerHeight * 0.75) * count}`,
          pin: true,
          // The workflow has no isolating ancestor: a fixed pin stays steady
          // during native scrolling without a JS transform chasing each frame.
          pinType: "fixed",
          scrub: true,
          anticipatePin: 1,
          invalidateOnRefresh: true,
          refreshPriority: 1,
        },
        onUpdate: () => {
          const next = Math.round(state.stage);
          if (next !== current) {
            current = next;
            setActive(next);
          }
        },
      });
      positions.current = [0];
      timeline.to({}, { duration: 0.6 });
      scenes.slice(1).forEach((_, index) => {
        timeline
          .to(line, { attr: { width: 480 }, duration: 0.7, ease: "none" })
          .to(state, { stage: index + 1, duration: 0.01, ease: "none" })
          // Both columns blend together in CSS, independent of scroll speed.
          .to({}, { duration: 0.6 })
          .set(line, { attr: { width: 0 } });
        positions.current.push(timeline.duration());
        timeline.to({}, { duration: 0.65 });
      });
      timeline.to(line, { attr: { width: 480 }, duration: 0.7, ease: "none" });
      animation.current = timeline;
      // Establish the spacer before sibling sections measure or observe visibility.
      ScrollTrigger.refresh();
    }, root);
    return () => {
      animation.current = null;
      context.revert();
    };
  }, [root, reduced, ready, introComplete, setActive, count]);

  return function jumpTo(index) {
    const timeline = animation.current;
    const trigger = timeline?.scrollTrigger;
    if (!trigger) return false;
    const progress = positions.current[index] / timeline.duration();
    window.scrollTo({
      top: trigger.start + (trigger.end - trigger.start) * progress,
      behavior: "smooth",
    });
    return true;
  };
}
