import assert from "node:assert/strict";
import { test } from "node:test";
import React from "react";
import { JSDOM } from "jsdom";

const dom = new JSDOM("<!doctype html><html><body></body></html>", {
  url: "http://localhost:3000", pretendToBeVisual: true,
});
globalThis.React = React;
globalThis.window = dom.window;
globalThis.document = dom.window.document;
globalThis.HTMLElement = dom.window.HTMLElement;
globalThis.getComputedStyle = dom.window.getComputedStyle.bind(dom.window);
globalThis.IS_REACT_ACT_ENVIRONMENT = true;

let visibility;
globalThis.IntersectionObserver = class {
  observed = new Set();
  constructor(callback) { this.callback = callback; visibility = this; }
  observe(element) { this.observed.add(element); }
  unobserve(element) { this.observed.delete(element); }
  disconnect() { this.observed.clear(); }
};
dom.window.HTMLElement.prototype.getBoundingClientRect = function () {
  const top = Number(this.dataset.top ?? 1200);
  return { top, bottom: top + 200, left: 0, right: 360, width: 360, height: 200, x: 0, y: top };
};

const { render, cleanup } = await import("@testing-library/react");
const { default: gsap } = await import("gsap");
const { useScrollReveals } = await import("../src/features/Pages/Landing/hooks/useScrollReveals.js");

function Sections({ enabled = true }) {
  useScrollReveals({ enabled });
  return <>
    <div data-reveal data-testid="evidence" data-top="1200">Evidence</div>
    <div data-reveal data-testid="safety" data-top="2200">Safety</div>
  </>;
}

test("later sections wait for actual visibility, including after a stale pin-layout entry", () => {
  try {
    const view = render(<Sections />);
    const evidence = view.getByTestId("evidence");
    const safety = view.getByTestId("safety");
    const evidenceTween = gsap.getTweensOf(evidence)[0];
    const safetyTween = gsap.getTweensOf(safety)[0];
    assert.equal(evidenceTween.paused(), true);

    // A pin spacer can invalidate a visibility entry queued before layout settled.
    visibility.callback([{ target: evidence, isIntersecting: true }]);
    assert.equal(evidenceTween.paused(), true);
    assert.equal(visibility.observed.has(evidence), true);

    evidence.dataset.top = "100";
    visibility.callback([
      { target: evidence, isIntersecting: true },
      { target: safety, isIntersecting: true },
    ]);
    assert.equal(evidenceTween.paused(), false);
    assert.equal(safetyTween.paused(), true);
    assert.equal(visibility.observed.has(evidence), false);
    assert.equal(visibility.observed.has(safety), true);

    // Disabling motion restores content and removes the visibility controller.
    view.rerender(<Sections enabled={false} />);
    assert.equal(visibility.observed.size, 0);
    assert.equal(evidence.style.opacity, "");
    assert.equal(safety.style.opacity, "");
  } finally {
    cleanup();
    gsap.ticker.sleep();
    dom.window.close();
  }
});
