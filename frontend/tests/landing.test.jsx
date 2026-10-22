import assert from "node:assert/strict";
import { afterEach, test } from "node:test";
import React from "react";
import { JSDOM } from "jsdom";
import { registerHooks } from "node:module";
import { renderToString } from "react-dom/server";

registerHooks({
  load(url, context, nextLoad) {
    if (url.endsWith(".module.css")) {
      return { format: "module", source: "export default new Proxy({}, { get: (_, name) => String(name) });", shortCircuit: true };
    }
    return nextLoad(url, context);
  },
});

const dom = new JSDOM("<!doctype html><html><body></body></html>", {
  url: "http://localhost:3000",
});
globalThis.React = React;
globalThis.window = dom.window;
globalThis.document = dom.window.document;
globalThis.HTMLElement = dom.window.HTMLElement;
globalThis.localStorage = dom.window.localStorage;
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
globalThis.IntersectionObserver = class {
  observe() {}
  disconnect() {}
};
let systemReduced = false;
const mediaListeners = new Set();
window.matchMedia = (query) => ({
  get matches() {
    return query.includes("prefers-reduced-motion") && systemReduced;
  },
  addEventListener: (_, listener) => {
    if (query.includes("prefers-reduced-motion")) mediaListeners.add(listener);
  },
  removeEventListener: (_, listener) => mediaListeners.delete(listener),
});

const { render, fireEvent, cleanup, act } = await import(
  "@testing-library/react"
);
const { default: Header } = await import(
  "../src/features/Pages/Landing/components/Header.jsx"
);
const { default: Workflow } = await import(
  "../src/features/Pages/Landing/components/RepairWorkflow.jsx"
);
const { default: ValidationExample } = await import(
  "../src/features/Pages/Landing/components/ValidationExample.jsx"
);
const { default: Footer } = await import(
  "../src/features/Pages/Landing/components/Footer.jsx"
);
const { default: Handoff } = await import("../src/features/Pages/Landing/components/Handoff.jsx");
const { default: Closing } = await import("../src/features/Pages/Landing/components/Closing.jsx");
const { default: Evidence } = await import("../src/features/Pages/Landing/components/Evidence.jsx");
const { default: Intro } = await import("../src/features/Pages/Landing/components/Intro.jsx");
const { MotionProvider, useMotion } = await import(
  "../src/features/Pages/Landing/hooks/useMotion.jsx"
);

afterEach(() => {
  cleanup();
  localStorage.clear();
  window.sessionStorage.clear();
  systemReduced = false;
});

test("mobile menu toggles, closes on navigation, and restores focus on Escape", () => {
  const view = render(<Header />);
  const menu = view.getByRole("button", { name: /Menu/ });
  fireEvent.click(menu);
  assert.equal(menu.getAttribute("aria-expanded"), "true");
  fireEvent.click(view.getByRole("link", { name: "Safety" }));
  assert.equal(menu.getAttribute("aria-expanded"), "false");
  fireEvent.click(menu);
  fireEvent.keyDown(document, { key: "Escape" });
  assert.equal(menu.getAttribute("aria-expanded"), "false");
  assert.equal(document.activeElement, menu);
  fireEvent.click(menu);
  fireEvent.click(document.body);
  assert.equal(menu.getAttribute("aria-expanded"), "false");
});

test("all repair stages update their evidence and support keyboard navigation", () => {
  const view = render(
    <MotionProvider>
      <Workflow />
    </MotionProvider>,
  );
  const controls = view.getByRole("group", { name: "Repair stages" });
  assert.ok(view.getByText("Step 1 of 6 · Investigate"));
  assert.equal(view.getByRole("link", { name: "Skip walkthrough" }).getAttribute("href"), "#execution");
  controls.focus();
  fireEvent.keyDown(controls, { key: "ArrowDown" });
  fireEvent.keyDown(controls, { key: "ArrowDown" });
  assert.ok(view.getByText("Step 3 of 6 · Patch"));
  assert.ok(
    view.getByRole("heading", { name: "One field. A focused repair." }),
  );
  assert.ok(view.getByText("+ port: 8080"));
  fireEvent.keyDown(controls, { key: "End" });
  assert.ok(view.getByRole("heading", { name: "The final decision belongs to you." }));
  assert.equal(document.activeElement, controls);
  fireEvent.keyDown(controls, { key: "ArrowDown" });
  assert.ok(view.getByRole("heading", { name: "The final decision belongs to you." }));
  fireEvent.keyDown(controls, { key: "Home" });
  assert.ok(
    view.getByRole("heading", { name: "A mismatch worth investigating." }),
  );
});

test("pointer users can select every repair stage directly in either motion mode", () => {
  for (const reduced of [false, true]) {
    localStorage.setItem("raphael-reduce-motion", String(reduced));
    const view = render(<MotionProvider><Workflow /></MotionProvider>);
    const buttons = view.getAllByRole("button", { name: /^Step \d:/ });
    assert.equal(buttons.length, 6);
    for (const index of [1, 2, 3, 4, 5, 0]) {
      fireEvent.click(buttons[index]);
      assert.equal(view.container.querySelector("[data-active-stage]").dataset.activeStage, String(index));
      assert.equal(buttons[index].getAttribute("aria-pressed"), "true");
      assert.equal(buttons.filter((button) => button.getAttribute("aria-pressed") === "true").length, 1);
      assert.equal(view.container.querySelectorAll('#stage-detail [aria-hidden="false"]').length, 1);
    }
    view.unmount();
  }
});

test("server HTML contains page content without an intro overlay", () => {
  const html = renderToString(<MotionProvider><Intro /><main>Repair your service</main></MotionProvider>);
  assert.ok(html.includes("Repair your service"));
  assert.ok(!html.includes("raphael-intro"));
});

test("six repair stages can be explored in order without autoplay", () => {
  const view = render(
    <MotionProvider>
      <Workflow />
    </MotionProvider>,
  );
  const controls = view.getByRole("group", { name: "Repair stages" });
  assert.equal(view.queryByRole("button", { name: "Previous repair stage" }), null);
  assert.equal(view.queryByRole("button", { name: "Next repair stage" }), null);
  fireEvent.keyDown(controls, { key: "ArrowUp" });
  assert.ok(view.getByRole("heading", { name: "A mismatch worth investigating." }));
  assert.equal(view.queryByRole("button", { name: /Play the walkthrough/ }), null);
  for (let index = 0; index < 4; index++) fireEvent.keyDown(controls, { key: "ArrowDown" });
  assert.ok(view.getByRole("heading", { name: "Package the repair with its evidence." }));
  assert.ok(view.getByText("baseline + validation: attached"));
  fireEvent.keyDown(controls, { key: "ArrowDown" });
  assert.ok(view.getByRole("heading", { name: "The final decision belongs to you." }));
  fireEvent.keyDown(controls, { key: "ArrowUp" });
  assert.ok(view.getByRole("heading", { name: "Package the repair with its evidence." }));
});

test("validation switches between passing and blocked evidence", () => {
  const view = render(<ValidationExample />);
  fireEvent.click(view.getByRole("button", { name: "Blocked example" }));
  assert.ok(view.getByText("Rollout check / unavailable"));
  assert.match(
    view.getByRole("status").textContent,
    /mandatory check could not run/,
  );
  fireEvent.click(view.getByRole("button", { name: "Passing example" }));
  assert.ok(view.getByText("After / signature absent"));
});

test("saved reduced motion advances manually and respects system preferences", () => {
  localStorage.setItem("raphael-reduce-motion", "true");
  const view = render(
    <MotionProvider>
      <Workflow />
      <Footer />
    </MotionProvider>,
  );
  fireEvent.keyDown(view.getByRole("group", { name: "Repair stages" }), { key: "ArrowDown" });
  assert.ok(
    view.getByRole("heading", { name: "Same failure. Isolated environment." }),
  );
  const toggle = view.getByRole("button", { name: "Reduce page motion" });
  fireEvent.click(toggle);
  assert.equal(localStorage.getItem("raphael-reduce-motion"), "false");
  act(() => {
    systemReduced = true;
    mediaListeners.forEach((listener) => listener({ matches: true }));
  });
  const systemToggle = view.getByRole("button", {
    name: "Reduced motion is enabled in your system settings",
  });
  assert.equal(systemToggle.disabled, true);
  assert.equal(document.documentElement.dataset.motion, "reduced");
});


test("handoff attachments expand independently and collapse again", () => {
  const view = render(<Handoff />);
  for (const title of ["Inspect the full diff", "Inspect the source evidence", "Inspect the validation summary"]) {
    const summary = view.getByText(title);
    const attachment = summary.closest("details");
    assert.equal(attachment.open, false);
    fireEvent.click(summary);
    assert.equal(attachment.open, true);
    assert.ok(attachment.querySelector("pre, ul"));
    fireEvent.click(summary);
    assert.equal(attachment.open, false);
  }
});

test("header and closing actions lead to the demo console", () => {
  const view = render(<><Header /><Closing /></>);
  assert.equal(view.getByRole("link", { name: "Open demo console" }).getAttribute("href"), "/console/");
  assert.equal(view.getByRole("link", { name: "Open the demo console" }).getAttribute("href"), "/console/");
});

function IntroState() {
  const { introComplete, completeIntro } = useMotion();
  return <button onClick={completeIntro}>{introComplete ? "Intro complete" : "Play intro"}</button>;
}

test("completed intro is skipped on a later visit in the same session", () => {
  const first = render(<MotionProvider><IntroState /></MotionProvider>);
  fireEvent.click(first.getByRole("button", { name: "Play intro" }));
  assert.equal(window.sessionStorage.getItem("raphael-intro-seen-v2"), "true");
  first.unmount();
  const returning = render(<MotionProvider><IntroState /></MotionProvider>);
  assert.ok(returning.getByRole("button", { name: "Intro complete" }));
  returning.unmount();
  window.sessionStorage.clear();
  const fresh = render(<MotionProvider><IntroState /></MotionProvider>);
  assert.ok(fresh.getByRole("button", { name: "Play intro" }));
});


test("evidence starts collapsed and opens only the selected source", () => {
  const view = render(<Evidence />);
  const details = [...view.container.querySelectorAll("details")];
  assert.equal(details.length, 4);
  assert.ok(details.every((item) => !item.open));
  const event = view.getByText("Kubernetes event").closest("summary");
  fireEvent.click(event);
  assert.equal(details[0].open, true);
  assert.ok(details.slice(1).every((item) => !item.open));
  fireEvent.click(event);
  assert.ok(details.every((item) => !item.open));
});
