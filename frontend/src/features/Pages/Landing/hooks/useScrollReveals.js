"use client";

import { useLayoutEffect } from "react";
import gsap from "gsap";

// Explicitly marked content reveals once when visible. The intro controls
// the header's docking reveal; diagrams and stage morphs have their own controllers.
const groups = [
  // Explicit opt-in remains available for individual future components.
  ["[data-reveal]", null],
];

export function useScrollReveals({ enabled }) {
  useLayoutEffect(() => {
    if (!enabled) return;
    const reveals = new Map();
    const claimed = new Set();
    // Observe painted positions rather than cached scroll offsets. The workflow's
    // pin spacer adds several screens of scroll distance before the later sections.
    const observer = new IntersectionObserver((entries) => {
      // Complete all layout reads before starting any animation writes.
      const visible = entries.filter((entry) => {
        if (!entry.isIntersecting) return false;
        const element = entry.target;
        const bounds = element.getBoundingClientRect();
        // Recheck in case a queued entry predates a pin refresh or layout change.
        return bounds.top < window.innerHeight && bounds.bottom > 0;
      });
      visible.forEach((entry, index) => {
        const element = entry.target;
        const tween = reveals.get(element);
        if (!tween) return;
        tween.delay(Math.min(index * 0.08, 0.24)).play();
        observer.unobserve(element);
      });
    }, { threshold: 0.01, rootMargin: "0px 0px -32px 0px" });

    const context = gsap.context(() => {
      const candidates = [];
      groups.forEach(([selector, children]) => {
        document.querySelectorAll(selector).forEach((trigger) => {
          const targets = (children ? [...trigger.querySelectorAll(children)] : [trigger])
            .filter((element) => !claimed.has(element));
          targets.forEach((element) => claimed.add(element));
          targets.forEach((element) => {
            // A restored scroll position must not hide content already passed.
            if (element.getBoundingClientRect().bottom > 0) candidates.push(element);
          });
        });
      });
      // Measure every target first; initial styles otherwise force a fresh layout
      // for each following target during page startup.
      candidates.forEach((element) => {
        const gentle = element.dataset.reveal === "gentle";
        const tween = gsap.fromTo(element,
          { opacity: 0, y: gentle ? 12 : 22 },
          {
            opacity: 1, y: 0, duration: gentle ? 0.6 : 0.85,
            ease: "power3.out", force3D: false, paused: true,
          },
        );
        reveals.set(element, tween);
        // Each card or text block waits for its own entrance into the viewport.
        observer.observe(element);
      });
    });

    // Opacity (rather than visibility) keeps links reachable by keyboard.
    function revealFocused(event) {
      reveals.forEach((tween, target) => {
        if (target.contains(event.target)) {
          tween.delay(0).progress(1);
          observer.unobserve(target);
        }
      });
    }
    document.addEventListener("focusin", revealFocused);

    return () => {
      observer.disconnect();
      document.removeEventListener("focusin", revealFocused);
      context.revert();
    };
  }, [enabled]);
}
