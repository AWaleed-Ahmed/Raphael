"use client";

import { useLayoutEffect, useRef } from "react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

export function useRepairScroll({ root, reduced, ready, introComplete, setActive, count }) {
  const animation = useRef(null);
  const positions = useRef([]);

  useLayoutEffect(() => {
    if (!ready || !introComplete || reduced || !root.current) return;
    const track = root.current.parentElement;
    if (!track?.hasAttribute("data-repair-track")) return;
    gsap.registerPlugin(ScrollTrigger);
    let observer;
    const context = gsap.context(() => {
      const distance = () => Math.max(180, window.innerHeight * 0.3) * (count - 1);
      // Native sticky never switches positioning modes at the scroll boundary.
      // Reserve the entire travel distance before any section is measured.
      const measure = () => gsap.set(track, { height: root.current.offsetHeight + distance() });
      gsap.set(root.current, { position: "sticky", top: 104 });
      measure();
      const scenes = [...root.current.querySelectorAll("[data-repair-scene]")];
      const line = root.current.querySelector("[data-repair-line-reveal]");
      const state = { stage: 0 };
      let current = 0;
      setActive(0);
      gsap.set(line, { attr: { width: 0 } });
      const timeline = gsap.timeline({
        scrollTrigger: {
          trigger: track,
          start: "top 104px",
          end: () => `+=${distance()}`,
          onRefreshInit: measure,
          scrub: true,
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
      // Re-measure on late font loading and responsive content changes.
      observer = new ResizeObserver(() => {
        if (Math.abs(track.offsetHeight - root.current.offsetHeight - distance()) > 1) {
          ScrollTrigger.refresh();
        }
      });
      observer.observe(root.current);
      ScrollTrigger.refresh();
    }, root);
    return () => {
      observer?.disconnect();
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
      // Explicit selection should land immediately, without sweeping other stages.
      behavior: "instant",
    });
    ScrollTrigger.update();
    return true;
  };
}
