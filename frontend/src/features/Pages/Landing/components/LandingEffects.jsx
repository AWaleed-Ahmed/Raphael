"use client";

import { useEffect } from "react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { useMotion } from "../hooks/useMotion";
import { useScrollReveals } from "../hooks/useScrollReveals";
import { useExecutionReveal } from "../hooks/useExecutionReveal";

export default function LandingEffects() {
  const { reduced, ready, introComplete } = useMotion();
  useScrollReveals({ enabled: ready && introComplete && !reduced });
  useExecutionReveal({ ready: ready && introComplete, reduced });

  useEffect(() => {
    const progress = document.querySelector(".reading-progress");
    const header = document.querySelector(".site-header");
    const links = [...header.querySelectorAll('a[href^="#"]')].filter(
      (link) => link.hash.length > 1,
    );
    const chapters = links
      .map((link) => document.querySelector(link.hash))
      .filter(Boolean);
    let frame = 0;
    let previousChapter;
    let previousTheme;
    let previousScrolled;
    function update() {
      frame = 0;
      // Read geometry before writing styles; avoid forcing layout mid-scroll.
      const range = document.documentElement.scrollHeight - window.innerHeight;
      const current = chapters
        .filter((section) => section.getBoundingClientRect().top <= 160)
        .at(-1);
      const scrolled = window.scrollY > 30;
      const y = Math.min(
        window.innerHeight - 1,
        header.getBoundingClientRect().bottom + 8,
      );
      const light =
        scrolled &&
        document
          .elementFromPoint(window.innerWidth / 2, y)
          ?.closest('[data-nav-theme="light"]');
      const theme = light ? "light" : scrolled ? "ink" : "top";
      const chapter = current?.id ?? "";
      progress.style.transform = `scaleX(${range > 0 ? Math.min(1, Math.max(0, window.scrollY / range)) : 0})`;
      if (chapter !== previousChapter) {
        links.forEach((link) => {
          if (chapter && link.hash === `#${chapter}`)
            link.setAttribute("aria-current", "location");
          else link.removeAttribute("aria-current");
        });
        previousChapter = chapter;
      }
      if (scrolled !== previousScrolled) {
        header.classList.toggle("is-scrolled", scrolled);
        previousScrolled = scrolled;
      }
      if (theme !== previousTheme) {
        header.classList.toggle("is-light", theme === "light");
        header.classList.toggle("is-ink", theme === "ink");
        previousTheme = theme;
      }
    }
    function schedule() {
      if (!frame) frame = requestAnimationFrame(update);
    }
    function revealBoundary() {
      if (window.location.hash === "#boundaries")
        document.querySelector("#boundaries").open = true;
    }
    function onBoundaryClick(event) {
      if (event.target.closest('a[href="#boundaries"]'))
        document.querySelector("#boundaries").open = true;
    }
    window.addEventListener("scroll", schedule, { passive: true });
    window.addEventListener("resize", schedule);
    window.addEventListener("hashchange", revealBoundary);
    document.addEventListener("toggle", schedule, true);
    document.addEventListener("click", onBoundaryClick);
    const observer = new ResizeObserver(schedule);
    observer.observe(document.body);
    revealBoundary();
    schedule();
    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      window.removeEventListener("scroll", schedule);
      window.removeEventListener("resize", schedule);
      window.removeEventListener("hashchange", revealBoundary);
      document.removeEventListener("toggle", schedule, true);
      document.removeEventListener("click", onBoundaryClick);
    };
  }, []);

  useEffect(() => {
    if (!ready || reduced) return;
    gsap.registerPlugin(ScrollTrigger);

    const animations = new Set();
    let disposed = false;
    const animate = (element, frames, options) => {
      const animation = element.animate(frames, options);
      animations.add(animation);
      animation.finished.then(
        () => animations.delete(animation),
        () => animations.delete(animation),
      );
      return animation;
    };
    const context = gsap.context(() => {
      gsap.set(".gsap-word", { autoAlpha: 0, y: 30 });
      gsap.set(".hero-description", { autoAlpha: 0, y: 18 });
      gsap.set(".hero .actions", { autoAlpha: 0, y: 14 });
      gsap.set(".hero-note", { autoAlpha: 0 });
      gsap.set(".hero-baseline span", { autoAlpha: 0, x: -18 });
      gsap
        .timeline({ paused: !introComplete, defaults: { ease: "power3.out" } })
        .to(
          ".gsap-word",
          { autoAlpha: 1, y: 0, duration: 0.65, stagger: 0.065 },
          0.3,
        )
        .to(".hero-description", { autoAlpha: 1, y: 0, duration: 0.65 }, 0.88)
        .to(".hero .actions", { autoAlpha: 1, y: 0, duration: 0.55 }, 1.02)
        .to(".hero-note", { autoAlpha: 1, duration: 0.6 }, 1.18);
      gsap.to(".hero-baseline span", {
        autoAlpha: 1,
        x: 0,
        duration: 0.5,
        stagger: 0.1,
        ease: "power2.out",
        scrollTrigger: {
          trigger: ".hero-baseline",
          start: "top 90%",
          once: true,
        },
      });
      gsap.to(".cloud-art", {
        yPercent: -18,
        ease: "none",
        scrollTrigger: {
          trigger: ".cloud-chapter",
          start: "top top",
          end: "bottom top",
          scrub: 1.2,
        },
      });
      gsap.to(".hero-copy", {
        yPercent: 10,
        opacity: 0.55,
        ease: "none",
        scrollTrigger: {
          trigger: ".hero",
          start: "center top",
          end: "bottom top",
          scrub: true,
        },
      });
    });
    const cleanups = [];
    document.querySelectorAll("details").forEach((details) => {
      const summary = details.querySelector("summary");
      let animation;
      let expanded = details.open;
      function settle() {
        animation?.cancel();
        animation = null;
        details.open = expanded;
        details.style.removeProperty("overflow");
        // The handoff is before the pinned walkthrough. Expanded attachments
        // change its start position, so measure again after the height settles.
        if (!disposed && details.closest(".handoff-section")) ScrollTrigger.refresh(true);
      }
      function onClick(event) {
        event.preventDefault();
        const start = details.getBoundingClientRect().height;
        expanded = animation ? !expanded : !details.open;
        animation?.cancel();
        details.open = true;
        const end = expanded
          ? details.getBoundingClientRect().height
          : summary.getBoundingClientRect().height;
        details.style.overflow = "clip";
        animation = animate(
          details,
          [{ height: `${start}px` }, { height: `${end}px` }],
          { duration: 280, easing: "cubic-bezier(.22,1,.36,1)" },
        );
        animation.onfinish = settle;
      }
      const resize = () => {
        if (animation) settle();
      };
      summary.addEventListener("click", onClick);
      window.addEventListener("resize", resize, { passive: true });
      cleanups.push(() => {
        if (animation) settle();
        summary.removeEventListener("click", onClick);
        window.removeEventListener("resize", resize);
      });
    });
    return () => {

      disposed = true;
      cleanups.forEach((cleanup) => cleanup());
      animations.forEach((animation) => animation.cancel());
      context.revert();
    };
  }, [ready, reduced, introComplete]);

  return null;
}
