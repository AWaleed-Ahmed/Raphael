import assert from "node:assert/strict";
import { test } from "node:test";
import React, { useRef, useState } from "react";
import { JSDOM } from "jsdom";

const dom = new JSDOM("<!doctype html><html><body></body></html>", {
  url: "http://localhost:3000", pretendToBeVisual: true,
});
Object.assign(globalThis, {
  React, window: dom.window, document: dom.window.document,
  HTMLElement: dom.window.HTMLElement, Node: dom.window.Node,
  getComputedStyle: dom.window.getComputedStyle.bind(dom.window),
  requestAnimationFrame: dom.window.requestAnimationFrame.bind(dom.window),
  cancelAnimationFrame: dom.window.cancelAnimationFrame.bind(dom.window),
  IS_REACT_ACT_ENVIRONMENT: true,
});
window.matchMedia = () => ({ matches: false, addListener() {}, removeListener() {} });
window.scrollTo = (_x, y) => { window.pageYOffset = y; };
Object.defineProperty(document.documentElement, "scrollHeight", { value: 20000 });
HTMLElement.prototype.getBoundingClientRect = function () {
  const top = this.hasAttribute("data-walkthrough") ? 1000 - window.pageYOffset : 0;
  return { top, left: 0, right: 1000, bottom: top + 500, width: 1000, height: 500, x: 0, y: top };
};

const { render, cleanup, act } = await import("@testing-library/react");
const { default: gsap } = await import("gsap");
const { ScrollTrigger } = await import("gsap/ScrollTrigger");
const { useRepairScroll } = await import("../src/features/Pages/Landing/hooks/useRepairScroll.js");

function Repair({ reduced = false }) {
  const root = useRef(null);
  const [active, setActive] = useState(0);
  useRepairScroll({ root, reduced, ready: true, introComplete: true, setActive, count: 6 });
  return <section className="landing-folder workflow">
    <div ref={root} data-walkthrough data-active-stage={active}>
      {Array.from({ length: 6 }, (_, i) => <div key={i} data-repair-scene />)}
      <svg><rect data-repair-line-reveal width="0" /></svg>
    </div>
  </section>;
}

test("repair scroll pins the walkthrough, reaches every stage, and releases after review", () => {
  try {
    const view = render(<Repair />);
    const trigger = ScrollTrigger.getAll()[0];
    assert.ok(trigger, "scroll controller starts after the intro");
    assert.equal(trigger.pin, view.container.querySelector("[data-walkthrough]"));
    assert.ok(view.container.querySelector(".pin-spacer"));
    assert.ok(trigger.end - trigger.start >= 2880);
    const visited = new Set();
    for (let i = 0; i <= 100; i++) {
      act(() => {
        window.scrollTo(0, trigger.start + (trigger.end - trigger.start) * i / 100);
        ScrollTrigger.update();
      });
      visited.add(Number(trigger.pin.dataset.activeStage));
      if (i === 50) {
        assert.equal(trigger.isActive, true);
        assert.equal(trigger.pin.style.position, "fixed");
        assert.equal(trigger.animation.progress(), trigger.progress, "animation follows scroll without a catch-up tween");
      }
    }
    assert.deepEqual([...visited], [0, 1, 2, 3, 4, 5]);
    // Reversing the wheel should reverse the stages immediately as well.
    const reversed = new Set();
    for (let i = 100; i >= 0; i--) {
      act(() => {
        window.scrollTo(0, trigger.start + (trigger.end - trigger.start) * i / 100);
        ScrollTrigger.update();
      });
      reversed.add(Number(trigger.pin.dataset.activeStage));
    }
    assert.deepEqual([...reversed], [5, 4, 3, 2, 1, 0]);
    act(() => {
      window.scrollTo(0, trigger.end + 100);
      ScrollTrigger.update();
    });
    assert.equal(trigger.isActive, false);
    view.rerender(<Repair reduced />);
    assert.equal(ScrollTrigger.getAll().length, 0);
    assert.equal(view.container.querySelector(".pin-spacer"), null);
  } finally {
    cleanup();
    ScrollTrigger.killAll();
    ScrollTrigger.disable();
    gsap.ticker.sleep();
    dom.window.close();
  }
});
