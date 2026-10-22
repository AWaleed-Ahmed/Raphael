import assert from "node:assert/strict";
import { test } from "node:test";
import React from "react";
import { JSDOM } from "jsdom";

const dom = new JSDOM("<!doctype html><html><body></body></html>", {
  url: "http://localhost:3000", pretendToBeVisual: true,
});
Object.assign(globalThis, {
  React, window: dom.window, document: dom.window.document,
  HTMLElement: dom.window.HTMLElement,
  getComputedStyle: dom.window.getComputedStyle.bind(dom.window),
  requestAnimationFrame: dom.window.requestAnimationFrame.bind(dom.window),
  cancelAnimationFrame: dom.window.cancelAnimationFrame.bind(dom.window),
  IS_REACT_ACT_ENVIRONMENT: true,
});
let visibility;
globalThis.IntersectionObserver = class {
  constructor(callback) { this.callback = callback; visibility = this; }
  observe() {}
  disconnect() {}
};
globalThis.ResizeObserver = class { observe() {} disconnect() {} };
dom.window.SVGElement.prototype.getTotalLength = () => 310;
dom.window.HTMLElement.prototype.getBoundingClientRect = function () {
  const left = Number(this.dataset.x ?? 0);
  const top = Number(this.dataset.y ?? 0);
  const width = this.hasAttribute("data-execution-board") ? 1000 : 140;
  const height = this.hasAttribute("data-execution-board") ? 450 : 100;
  return { left, top, right: left + width, bottom: top + height, width, height, x: left, y: top };
};
const { render, cleanup } = await import("@testing-library/react");
const { default: gsap } = await import("gsap");
const { useExecutionReveal, roundedRoute, executionRoute } = await import("../src/features/Pages/Landing/hooks/useExecutionReveal.js");

const nodes = [
  ["event", 0, 40], ["manifest", 0, 180],
  ["investigate", 220, 40], ["investigate-detail", 220, 200],
  ["sandbox", 400, 40], ["sandbox-detail", 400, 200],
  ["prepare", 580, 40], ["prepare-detail", 580, 200],
  ["draft", 800, 40], ["review", 800, 200],
];
const edges = [
  ["signals", "execution", "input"],
  ["investigate", "investigate-detail", "detail"],
  ["investigate", "sandbox", "step"], ["sandbox", "sandbox-detail", "detail"],
  ["sandbox", "prepare", "step"], ["prepare", "prepare-detail", "detail"],
  ["prepare", "draft", "output"], ["prepare", "review", "output"],
];

test("connector bends are rounded and retain their attachment points", () => {
  assert.equal(
    roundedRoute([[0, 0], [50, 0], [50, 100], [100, 100]]),
    "M 0 0 L 36 0 Q 50 0 50 14 L 50 86 Q 50 100 64 100 L 100 100",
  );
  // Narrow lanes limit the radius; aligned or repeated points remain straight.
  assert.equal(roundedRoute([[0, 0], [4, 0], [4, 4]]), "M 0 0 L 2 0 Q 4 0 4 2 L 4 4");
  assert.equal(roundedRoute([[0, 0], [0, 0], [10, 0], [20, 0]]), "M 0 0 L 20 0");
  const source = { left: 0, right: 100, top: 0, bottom: 60, width: 100, height: 60 };
  const target = { left: 200, right: 300, top: 120, bottom: 180, width: 100, height: 60 };
  const route = executionRoute(source, target, "input");
  assert.ok(route.startsWith("M 100 30 "));
  assert.ok(route.includes(" Q "));
  assert.equal(route.includes(" C "), false);
  assert.ok(route.endsWith("200 150"));
  const adjacent = { ...target, top: 20, bottom: 100, height: 80 };
  assert.equal(executionRoute(source, adjacent, "step"), "M 100 40 L 200 40");
  const below = { ...source, top: 100, bottom: 160 };
  assert.equal(executionRoute(source, below, "detail"), "M 50 60 L 50 100");
});
function Board({ reduced = false }) {
  useExecutionReveal({ ready: true, reduced });
  return <div data-execution-board>
    <svg data-execution-wires>{edges.map(([from, to, kind]) =>
      <path key={`${from}:${to}`} data-execution-edge={`${from}:${to}`} data-edge-kind={kind} pathLength="1" />,
    )}</svg>
    <svg data-execution-header-wires>{["execution:handoff"].map((edge) =>
      <g key={edge}><path data-progress-track={edge} /><path data-execution-progress={edge} pathLength="1" /></g>,
    )}</svg>
    {[["signals", 0], ["execution", 220], ["handoff", 800]].map(([id, x]) =>
      <div key={id} data-execution-group={id} data-x={x} data-y="0">
        <p data-execution-phase={id}><span data-phase-label data-x={x} data-y="0">{id}</span></p>
        <svg data-execution-frame={`phase-${id}`}><rect data-frame-reveal pathLength="1" /><rect data-frame-outline /></svg>
      </div>,
    )}
    {nodes.map(([id, x, y]) => <div key={id} data-x={x} data-y={y}>
      {["investigate", "sandbox", "prepare"].includes(id) && <svg data-execution-frame={id}><rect data-frame-reveal pathLength="1" /><rect data-frame-outline /></svg>}
      <div data-execution-node={id} data-x={x} data-y={y}>{id}</div>
    </div>)}
  </div>;
}

test("execution boxes wait for line arrival; offscreen playback pauses and reduced motion restores the full diagram", () => {
  try {
    const view = render(<Board />);
    const board = view.container.querySelector("[data-execution-board]");
    const incoming = board.querySelector('[data-execution-edge="signals:execution"]');
    const destination = board.querySelector('[data-execution-node="investigate"]');
    assert.equal(board.querySelectorAll('[data-edge-kind="input"]').length, 1);
    assert.equal(board.querySelector('[data-execution-progress="signals:execution"]'), null);
    const frame = board.querySelector('[data-execution-frame="investigate"] [data-frame-reveal]');
    const lineTween = gsap.getTweensOf(incoming)[0];
    const timeline = lineTween.parent;
    const arrival = lineTween.startTime() + lineTween.duration();
    assert.equal(timeline.paused(), true);
    assert.equal(destination.style.opacity, "0");
    assert.equal(Number(frame.getAttribute("stroke-dashoffset")), 1);
    assert.equal(Number(frame.getAttribute("width")), 138);

    timeline.time(arrival - 0.05, true);
    assert.equal(destination.style.opacity, "0");
    assert.ok(Number(incoming.getAttribute("stroke-dashoffset")) > 0);
    timeline.time(arrival + 0.2, true);
    assert.ok(Number(destination.style.opacity) > 0);
    assert.equal(Number(incoming.getAttribute("stroke-dashoffset")), 0);
    assert.ok(Number(frame.getAttribute("stroke-dashoffset")) < 1);
    assert.ok(Number(frame.getAttribute("stroke-dashoffset")) > 0);

    visibility.callback([{ target: board, isIntersecting: true }]);
    assert.equal(timeline.paused(), false);
    visibility.callback([{ target: board, isIntersecting: false }]);
    assert.equal(timeline.paused(), true);

    view.rerender(<Board reduced />);
    assert.equal(destination.style.opacity, "");
    assert.equal(Number(incoming.getAttribute("stroke-dashoffset") || 0), 0);
    assert.ok(incoming.getAttribute("d").startsWith("M "));
    assert.equal(board.querySelector('[data-execution-group="handoff"]').dataset.phaseState, "complete");
    assert.equal(Number(frame.getAttribute("stroke-dashoffset") || 0), 0);
  } finally {
    cleanup();
    gsap.ticker.sleep();
    dom.window.close();
  }
});
