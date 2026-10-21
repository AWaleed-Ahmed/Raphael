"use client";

import { useEffect, useId, useRef } from "react";
import gsap from "gsap";
import { useMotion } from "../hooks/useMotion";

const BODY =
  "M300 0C295 75 283 117 243 143C286 174 279 228 300 398C321 228 314 174 357 143C317 117 305 75 300 0Z";

export default function Intro() {
  const root = useRef(null);
  const revealId = useId();
  const { ready, reduced, introComplete, completeIntro } = useMotion();

  useEffect(() => {
    if (!ready || introComplete) return;
    if (reduced) {
      completeIntro();
      return;
    }

    const rootEl = root.current;
    if (!rootEl) return;
    const mark = rootEl.querySelector("[data-mark]");
    if (!mark) return;

    const scrollRoot = document.documentElement;
    const previousOverflow = scrollRoot.style.overflow;
    scrollRoot.style.overflow = "hidden";
    const header = document.querySelector(".site-header");
    const headerMark = header?.querySelector(".brand-mark");
    const pill = header?.querySelector(".header-intro-pill");
    const headerContent = header ? [...header.querySelectorAll(".brand-name, nav, .header-actions")] : [];

    let disposed = false;
    let destination;
    let geometry;
    const flight = { progress: 0 };

    // Measure only when layout changes, never between animation-frame writes.
    function measure() {
      // The observer can fire after the intro unmounts, before cleanup runs.
      if (disposed || !rootEl.isConnected) return;

      const bounds = rootEl.getBoundingClientRect();
      geometry = {
        centerX: bounds.left + bounds.width / 2,
        centerY: bounds.top + bounds.height / 2,
        width: mark.offsetWidth,
      };
      if (headerMark && headerMark.isConnected) {
        const headerBounds = headerMark.getBoundingClientRect();
        destination = {
          centerX: headerBounds.left + headerBounds.width / 2,
          centerY: headerBounds.top + headerBounds.height / 2,
          width: Math.min(headerBounds.width, headerBounds.height * 1.5),
          color: getComputedStyle(headerMark).color,
        };
      }
    }
    measure();
    const resizeObserver = new ResizeObserver(measure);
    if (headerMark) resizeObserver.observe(headerMark);
    resizeObserver.observe(rootEl);
    window.addEventListener("resize", measure);

    const context = gsap.context(() => {
      if (headerMark) gsap.set(headerMark, { autoAlpha: 0 });
      gsap.set(headerContent, { autoAlpha: 0, y: 6 });
      if (pill) {
        gsap.set(pill, {
          width: (header.querySelector(".wordmark")?.getBoundingClientRect().width ?? 160) + 32,
          height: 56,
          yPercent: -50,
          autoAlpha: 0,
        });
      }
      gsap.set(mark, {
        xPercent: -50,
        yPercent: -50,
        x: 0,
        y: 0,
        scale: 1,
        transformOrigin: "50% 50%",
        force3D: true,
      });
      gsap.set("[data-wing]", {
        attr: {
          transform: "translate(300 200) scale(0 0.72) translate(-300 -200)",
        },
      });
      gsap.set("[data-body]", {
        attr: { transform: "translate(300 0) scale(0.12 1) translate(-300 0)" },
      });

      gsap
        .timeline({
          defaults: { ease: "power3.inOut" },
          onComplete: completeIntro,
        })
        .timeScale(1.7)
        // A soft seed gathers at the top of the eventual body.
        .fromTo(
          "[data-seed]",
          { attr: { rx: 0, ry: 0 }, opacity: 0 },
          {
            attr: { rx: 13, ry: 12 },
            opacity: 1,
            duration: 0.55,
          },
        )
        .to("[data-seed]", { attr: { rx: 4.2, ry: 27.6 }, duration: 0.45 }, 0.4)
        // Reveal the original silhouette downward, widening it as it draws.
        .to("[data-reveal]", { attr: { height: 410 }, duration: 0.9 }, 0.62)
        .to(
          "[data-body]",
          {
            attr: {
              transform: "translate(300 0) scale(1 1) translate(-300 0)",
            },
            duration: 0.9,
          },
          0.72,
        )
        .to("[data-seed]", { opacity: 0, duration: 0.3 }, 0.72)
        // The upper feathers open first; the lower pair follows through.
        .to(
          "[data-wing='upper']",
          {
            attr: {
              transform: "translate(300 200) scale(1 1) translate(-300 -200)",
            },
            duration: 1.25,
            ease: "power4.out",
          },
          1.36,
        )
        .to(
          "[data-wing='lower']",
          {
            attr: {
              transform: "translate(300 200) scale(1 1) translate(-300 -200)",
            },
            duration: 1.15,
            ease: "power4.out",
          },
          1.53,
        )
        .call(measure, [], 2.85)
        .to(
          "[data-backdrop]",
          { opacity: 0, duration: 1.1, ease: "sine.inOut" },
          2.85,
        )
        .to(
          mark,
          {
            filter: "drop-shadow(0px 0px 0px transparent)",
            color: () => destination?.color ?? "#ffffff",
            duration: 1.5,
            ease: "sine.inOut",
          },
          2.85,
        )
        .to(
          flight,
          {
            progress: 1,
            duration: 1.5,
            ease: "power2.inOut",
            onUpdate: () => {
              if (disposed || !destination || !geometry) return;
              gsap.set(mark, {
                x: (destination.centerX - geometry.centerX) * flight.progress,
                y: (destination.centerY - geometry.centerY) * flight.progress,
                scale:
                  1 +
                  (destination.width / geometry.width - 1) * flight.progress,
              });
            },
          },
          2.85,
        )
        // A compact shell waits at the destination before the logo docks.
        .to(pill ?? [], { autoAlpha: 1, duration: 0.3 }, 3.6)
        // Reveal the native mark underneath first so the handoff never dims.
        .set(headerMark ?? [], { autoAlpha: 1 })
        .to(mark, { autoAlpha: 0, duration: 0.12, ease: "none" })
        // Expand the shell after docking, then let the normal header take over.
        .to(pill ?? [], {
          width: () => (header?.getBoundingClientRect().width ?? 0) + 32,
          height: () => header?.getBoundingClientRect().height ?? 92,
          duration: 0.95,
          ease: "power3.inOut",
        }, "<")
        .to(headerContent, { autoAlpha: 1, y: 0, duration: 0.55, stagger: 0.06 }, "<0.2")
        .to(pill ?? [], { autoAlpha: 0, duration: 0.4, ease: "sine.out" });
    }, rootEl);

    return () => {
      disposed = true;
      resizeObserver.disconnect();
      window.removeEventListener("resize", measure);
      context.revert();
      scrollRoot.style.overflow = previousOverflow;
    };
  }, [ready, reduced, introComplete, completeIntro]);

  if (introComplete || (ready && reduced)) return null;

  return (
    <div
      ref={root}
      className="raphael-intro fixed inset-0 z-[100] grid place-items-center motion-reduce:hidden"
      aria-hidden="true"
    >
      <div
        data-backdrop
        className="absolute inset-0 bg-[#090a12e8] backdrop-blur-[14px]"
      />
      <div
        data-mark
        className="absolute left-1/2 top-1/2 w-[min(48vw,260px)] aspect-[3/2] text-white"
        style={{
          transform: "translate(-50%, -50%)",
          willChange: "transform",
          filter: "drop-shadow(0px 0px 28px #ffffff35)",
        }}
      >
        <svg
          className="block h-full w-full overflow-visible"
          viewBox="0 0 600 400"
          fill="currentColor"
          focusable="false"
        >
          <defs>
            <clipPath id={revealId} clipPathUnits="userSpaceOnUse">
              <rect data-reveal x="240" y="-2" width="120" height="0" />
            </clipPath>
          </defs>
          <ellipse data-seed cx="300" cy="8" rx="13" ry="12" opacity="0" />
          <g clipPath={`url(#${revealId})`}>
            <path data-body d={BODY} />
          </g>
          <g
            data-wing="upper"
            transform="translate(300 200) scale(0 0.72) translate(-300 -200)"
          >
            <path d="M7 0C62 70 146 77 198 114C235 141 250 188 256 273C212 174 159 174 84 134C39 110 12 68 7 0Z" />
            <path d="M593 0C538 70 454 77 402 114C365 141 350 188 344 273C388 174 441 174 516 134C561 110 588 68 593 0Z" />
          </g>
          <g
            data-wing="lower"
            transform="translate(300 200) scale(0 0.72) translate(-300 -200)"
          >
            <path d="M64 146C115 184 159 182 199 218C235 250 254 301 272 370C220 292 179 294 119 248C88 225 69 190 64 146Z" />
            <path d="M536 146C485 184 441 182 401 218C365 250 346 301 328 370C380 292 421 294 481 248C512 225 531 190 536 146Z" />
          </g>
        </svg>
      </div>
    </div>
  );
}
