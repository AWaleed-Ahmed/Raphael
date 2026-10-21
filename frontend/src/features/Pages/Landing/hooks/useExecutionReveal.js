"use client";

import { useLayoutEffect } from "react";
import gsap from "gsap";

// Round each bend within the available segment length so tight mobile lanes
// stay outside the cards without overshooting their connection points.
export function roundedRoute(points, radius = 14) {
  const clean = [];
  points.forEach((point) => {
    const last = clean.at(-1);
    if (last && last[0] === point[0] && last[1] === point[1]) return;
    while (clean.length > 1) {
      const a = clean.at(-2);
      const b = clean.at(-1);
      const incoming = [b[0] - a[0], b[1] - a[1]];
      const outgoing = [point[0] - b[0], point[1] - b[1]];
      if (incoming[0] * outgoing[1] !== incoming[1] * outgoing[0]
        || incoming[0] * outgoing[0] + incoming[1] * outgoing[1] <= 0) break;
      clean.pop();
    }
    clean.push(point);
  });
  if (!clean.length) return "";
  const xy = (point) => point.map((value) => Math.round(value * 1000) / 1000).join(" ");
  let path = `M ${xy(clean[0])}`;
  for (let index = 1; index < clean.length - 1; index++) {
    const before = clean[index - 1];
    const corner = clean[index];
    const after = clean[index + 1];
    const incoming = Math.hypot(corner[0] - before[0], corner[1] - before[1]);
    const outgoing = Math.hypot(after[0] - corner[0], after[1] - corner[1]);
    const bend = Math.min(radius, incoming / 2, outgoing / 2);
    const entry = corner.map((value, axis) => value + (before[axis] - value) * bend / incoming);
    const exit = corner.map((value, axis) => value + (after[axis] - value) * bend / outgoing);
    path += ` L ${xy(entry)} Q ${xy(corner)} ${xy(exit)}`;
  }
  if (clean.length > 1) path += ` L ${xy(clean.at(-1))}`;
  return path;
}

// Use straight horizontal/vertical segments with small radiused corners.
export function executionRoute(source, target, kind, { rowY } = {}) {
  const sy = source.top + source.height / 2;
  const ty = target.top + target.height / 2;
  const sx = source.left + source.width / 2;
  const tx = target.left + target.width / 2;
  const overlapTop = Math.max(source.top, target.top);
  const overlapBottom = Math.min(source.bottom, target.bottom);
  const overlapLeft = Math.max(source.left, target.left);
  const overlapRight = Math.min(source.right, target.right);
  if (target.left >= source.right + 8) {
    if (overlapBottom > overlapTop) {
      const y = rowY ?? (overlapTop + overlapBottom) / 2;
      return `M ${source.right} ${y} L ${target.left} ${y}`;
    }
    const mid = (source.right + target.left) / 2;
    return roundedRoute([[source.right, sy], [mid, sy], [mid, ty], [target.left, ty]], 8);
  }
  if (target.top >= source.bottom + 8) {
    if (overlapRight > overlapLeft) {
      const x = (overlapLeft + overlapRight) / 2;
      return `M ${x} ${source.bottom} L ${x} ${target.top}`;
    }
    const mid = (source.bottom + target.top) / 2;
    return roundedRoute([[sx, source.bottom], [sx, mid], [tx, mid], [tx, target.top]], 8);
  }
  // A stacked step must skirt its detail card before entering the next step.
  if (kind === "step" || kind === "input") {
    const lane = Math.min(source.left, target.left) - 16;
    return roundedRoute([[source.left, sy], [lane, sy], [lane, ty], [target.left, ty]], 10);
  }
  const lane = Math.max(source.right, target.right) + 16;
  return roundedRoute([[source.right, sy], [lane, sy], [lane, ty], [target.right, ty]], 10);
}

export function useExecutionReveal({ ready, reduced }) {
  useLayoutEffect(() => {
    if (!ready) return;
    const board = document.querySelector("[data-execution-board]");
    if (!board) return;
    const svg = board.querySelector("[data-execution-wires]");
    const nodes = new Map([...board.querySelectorAll("[data-execution-node]")]
      .map((node) => [node.dataset.executionNode, node]));
    const paths = new Map([...svg.querySelectorAll("[data-execution-edge]")]
      .map((path) => [path.dataset.executionEdge, path]));
    const headerSvg = board.querySelector("[data-execution-header-wires]");
    const phaseLabels = new Map([...board.querySelectorAll("[data-execution-phase]")]
      .map((phase) => [phase.dataset.executionPhase, phase.querySelector("[data-phase-label]") ?? phase]));
    const phaseGroups = new Map([...board.querySelectorAll("[data-execution-group]")]
      .map((group) => [group.dataset.executionGroup, group]));
    const progressPaths = new Map([...(headerSvg?.querySelectorAll("[data-execution-progress]") ?? [])]
      .map((path) => [path.dataset.executionProgress, path]));
    const frames = new Map([...board.querySelectorAll("[data-execution-frame]")]
      .map((frame) => [frame.dataset.executionFrame, frame]));
    let disposed = false;
    let frame = 0;

    function measure() {
      frame = 0;
      if (disposed) return;
      const bounds = board.getBoundingClientRect();
      function relativeBox(node) {
        const rect = node.getBoundingClientRect();
        return {
          left: rect.left - bounds.left, right: rect.right - bounds.left,
          top: rect.top - bounds.top, bottom: rect.bottom - bounds.top,
          width: rect.width, height: rect.height,
        };
      }
      const boxes = new Map([...nodes].map(([id, node]) => [id, relativeBox(node)]));
      const headers = new Map([...phaseLabels].map(([id, node]) => [id, relativeBox(node)]));
      const groups = new Map([...phaseGroups].map(([id, node]) => [id, relativeBox(node)]));
      const frameSizes = new Map([...frames].map(([id, frame]) => [id, relativeBox(frame.parentElement)]));
      const executionNodes = ["investigate", "sandbox", "prepare"].map((id) => boxes.get(id));
      const rowTop = Math.max(...executionNodes.map((box) => box.top));
      const rowBottom = Math.min(...executionNodes.map((box) => box.bottom));
      const rowY = rowBottom > rowTop ? (rowTop + rowBottom) / 2 : undefined;
      // Read all boxes first. Drawing the SVG does not change document layout.
      svg.setAttribute("viewBox", `0 0 ${bounds.width} ${bounds.height}`);
      paths.forEach((path, edge) => {
        const [from, to] = edge.split(":");
        let source = groups.get(from) ?? boxes.get(from);
        const target = groups.get(to) ?? boxes.get(to);
        // Vertical step links leave below the supporting detail, keeping the
        // inter-step connector entirely in the empty gap between step frames.
        if (path.dataset.edgeKind === "step" && target.top >= source.bottom + 8) {
          source = boxes.get(`${from}-detail`) ?? source;
        }
        path.setAttribute("d", executionRoute(source, target, path.dataset.edgeKind, {
          rowY: path.dataset.edgeKind === "step" ? rowY : undefined,
        }));
      });
      headerSvg?.setAttribute("viewBox", `0 0 ${bounds.width} ${bounds.height}`);
      progressPaths.forEach((path, edge) => {
        const [from, to] = edge.split(":");
        const source = headers.get(from);
        const target = headers.get(to);
        if (!source || !target) return;
        const sourceGroup = groups.get(from);
        const targetGroup = groups.get(to);
        const y = Math.max(source.top, target.top) + Math.min(source.height, target.height) / 2;
        const d = targetGroup.left >= sourceGroup.right + 8
          ? `M ${sourceGroup.right} ${y} L ${targetGroup.left} ${y}`
          : "";
        path.setAttribute("d", d);
        headerSvg.querySelector(`[data-progress-track="${edge}"]`)?.setAttribute("d", d);
      });
      frames.forEach((frame, id) => {
        const { width, height } = frameSizes.get(id);
        frame.setAttribute("viewBox", `0 0 ${width} ${height}`);
        frame.querySelectorAll("rect").forEach((rect) => {
          rect.setAttribute("width", Math.max(0, width - 2));
          rect.setAttribute("height", Math.max(0, height - 2));
        });
      });
    }
    function scheduleMeasure() {
      if (!disposed && !frame) frame = requestAnimationFrame(measure);
    }
    measure();
    const resize = new ResizeObserver(scheduleMeasure);
    resize.observe(board);
    document.fonts?.ready.then(scheduleMeasure);

    let observer;
    let timeline;
    let waitingFor;
    let boardVisible = false;
    let started = false;
    let finished = false;
    const visible = new Set();
    function resume() {
      if (!timeline || !started || finished || !boardVisible || document.visibilityState === "hidden") return;
      if (waitingFor && !visible.has(waitingFor) && waitingFor.getBoundingClientRect().bottom > 0) return;
      waitingFor = null;
      timeline.play();
    }
    function onTabVisibility() {
      if (document.visibilityState === "hidden") timeline?.pause();
      else resume();
    }

    const context = gsap.context(() => {
      if (reduced) {
        phaseGroups.forEach((group) => { group.dataset.phaseState = "complete"; });
        return;
      }
      gsap.set([...nodes.values()], { opacity: 0 });
      gsap.set([...paths.values()], { attr: { "stroke-dasharray": 1, "stroke-dashoffset": 1 } });
      if (progressPaths.size) gsap.set([...progressPaths.values()], { attr: { "stroke-dasharray": 1, "stroke-dashoffset": 1 } });
      if (phaseLabels.size) gsap.set([...phaseLabels.values()], { opacity: 0.7 });
      const frameReveals = [...frames.values()].map((frame) => frame.querySelector("[data-frame-reveal]"));
      if (frameReveals.length) gsap.set(frameReveals, { attr: { "stroke-dasharray": 1, "stroke-dashoffset": 1 } });
      const washes = [...board.querySelectorAll("[data-execution-wash]")];
      if (washes.length) gsap.set(washes, { clipPath: "inset(0 100% 0 0)" });
      timeline = gsap.timeline({ paused: true, onComplete: () => { finished = true; } });

      function gate(id, at) {
        const node = nodes.get(id);
        timeline.addPause(at, () => { waitingFor = node; resume(); });
      }
      function show(id, at) {
        const node = nodes.get(id);
        timeline.to(node, { opacity: 1, duration: 0.4, ease: "power2.out" }, at);
        const wash = node.querySelector("[data-execution-wash]");
        if (wash) timeline.to(wash, { clipPath: "inset(0 0% 0 0)", duration: 0.6, ease: "power2.out" }, at);
        revealFrame(id, at);
      }
      function revealFrame(id, at) {
        const frame = frames.get(id);
        if (!frame) return;
        timeline.to(frame.querySelector("[data-frame-reveal]"), {
          attr: { "stroke-dashoffset": 0 }, duration: 0.9, ease: "power2.inOut",
        }, at);
        if (!id.startsWith("phase-")) {
          timeline.call(() => { frame.parentElement.dataset.stageState = "active"; }, [], at);
        }
      }
      function enterPhase(id, at) {
        const label = phaseLabels.get(id);
        if (label) timeline.to(label, { opacity: 1, duration: 0.4, ease: "power2.out" }, at);
        timeline.call(() => {
          phaseGroups.forEach((group, phase) => {
            if (phase === id) group.dataset.phaseState = "active";
            else if (group.dataset.phaseState === "active") group.dataset.phaseState = "complete";
          });
        }, [], at);
        revealFrame(`phase-${id}`, at);
      }
      function advancePhase(from, to, at, duration) {
        const path = progressPaths.get(`${from}:${to}`);
        if (path) timeline.to(path, { attr: { "stroke-dashoffset": 0 }, duration, ease: "none" }, at);
        enterPhase(to, at + duration);
      }
      function connect(from, to, at) {
        const path = paths.get(`${from}:${to}`);
        // A consistent drawing speed is the key: a box appears on line arrival.
        const duration = Math.max(0.32, Math.min(1.4, path.getTotalLength() / 310));
        timeline.to(path, { attr: { "stroke-dashoffset": 0 }, duration, ease: "none" }, at);
        return duration;
      }
      let cursor = 0;
      enterPhase("signals", cursor);
      ["event", "manifest"].forEach((id) => {
        gate(id, cursor);
        show(id, cursor);
        cursor += 0.55;
      });
      gate("investigate", cursor);
      const inputsAt = cursor;
      const inputDuration = connect("signals", "execution", inputsAt);
      advancePhase("signals", "execution", inputsAt, inputDuration);
      cursor += inputDuration;
      const steps = ["investigate", "sandbox", "prepare"];
      steps.forEach((id, index) => {
        if (index > 0) {
          gate(id, cursor);
          cursor += connect(steps[index - 1], id, cursor);
          const previousFrame = frames.get(steps[index - 1]);
          if (previousFrame) timeline.call(() => { previousFrame.parentElement.dataset.stageState = "complete"; }, [], cursor);
        }
        show(id, cursor);
        cursor += 0.4;
        const detail = `${id}-detail`;
        gate(detail, cursor);
        cursor += connect(id, detail, cursor);
        show(detail, cursor);
        cursor += 0.55;
      });
      ["draft", "review"].forEach((id, index) => {
        gate(id, cursor);
        const duration = connect("prepare", id, cursor);
        if (index === 0) {
          advancePhase("execution", "handoff", cursor, duration);
          const lastFrame = frames.get("prepare");
          if (lastFrame) timeline.call(() => { lastFrame.parentElement.dataset.stageState = "complete"; }, [], cursor + duration);
        }
        cursor += duration;
        show(id, cursor);
        cursor += 0.55;
      });
      timeline.call(() => {
        const handoff = phaseGroups.get("handoff");
        if (handoff) handoff.dataset.phaseState = "complete";
      }, [], cursor);

      observer = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
          if (entry.target === board) boardVisible = entry.isIntersecting;
          else if (entry.isIntersecting) visible.add(entry.target);
          else visible.delete(entry.target);
        });
        if (!boardVisible) timeline.pause();
        else {
          started = true;
          resume();
        }
      }, { threshold: 0.01 });
      observer.observe(board);
      nodes.forEach((node) => observer.observe(node));
    }, board);
    document.addEventListener("visibilitychange", onTabVisibility);

    return () => {
      disposed = true;
      cancelAnimationFrame(frame);
      resize.disconnect();
      observer?.disconnect();
      document.removeEventListener("visibilitychange", onTabVisibility);
      context.revert();
      phaseGroups.forEach((group) => group.removeAttribute("data-phase-state"));
      frames.forEach((frame) => frame.parentElement.removeAttribute("data-stage-state"));
    };
  }, [ready, reduced]);
}
