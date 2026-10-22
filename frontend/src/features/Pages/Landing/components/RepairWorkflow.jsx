"use client";

import { useId, useRef, useState } from "react";
import RepairOrb from "./RepairOrb";
import SectionNotch from "./SectionNotch";
import { Icon } from "../../../../components/Brand";
import { stages } from "../data";
import { useMotion } from "../hooks/useMotion";
import { useRepairScroll } from "../hooks/useRepairScroll";
import styles from "./RepairWorkflow.module.css";

const steps = [
  ["Investigate", "Connect the signal to its source.", "searching"],
  ["Reproduce", "Match the failure in isolation.", "connecting"],
  ["Patch", "Make the narrowest change.", "composing"],
  ["Validate", "Compare the baseline with the repair.", "solving"],
  ["Prepare draft", "Bring the change and evidence together.", "weaving"],
  ["Human review", "Your team decides what ships.", "breathing"],
];

export default function RepairWorkflow() {
  const { reduced, ready, introComplete } = useMotion();
  const [active, setActive] = useState(0);
  const root = useRef(null);
  const lineId = useId().replace(/:/g, "");
  const stage = stages[active];
  const jumpTo = useRepairScroll({
    root,
    reduced,
    ready,
    introComplete,
    setActive,
    count: stages.length,
  });

  function select(index) {
    if (!jumpTo(index)) setActive(index);
  }
  function navigate(event) {
    const direction = {
      ArrowRight: 1,
      ArrowDown: 1,
      ArrowLeft: -1,
      ArrowUp: -1,
    }[event.key];
    if (direction === undefined && !["Home", "End"].includes(event.key)) return;
    event.preventDefault();
    select(
      event.key === "Home"
        ? 0
        : event.key === "End"
          ? stages.length - 1
          : Math.min(stages.length - 1, Math.max(0, active + direction)),
    );
  }

  return (
    <section
      className={`landing-folder workflow bg-(--night) p-[88px_0_80px] max-[767.01px]:p-[60px_0] dark-section ${styles.section}`}
      id="repair"
      data-nav-theme="ink"
      aria-labelledby="workflow-title"
    >
      <SectionNotch variant="workflow" />
      <div
        className={`
          wrap relative w-[min(1280px,calc(100%-112px))] max-[1100.01px]:w-[calc(100%-64px)]
          max-[767.01px]:w-[calc(100%-40px)] mx-auto
        `}
      >
        <div
          className={`
          section-intro grid grid-cols-[1fr_2fr_1fr] gap-6 items-start mb-[45px] [&_>_.label]:pt-[7px]
          [&_>_p:last-child]:text-(--muted) [&_>_p:last-child]:text-[12px] [&_>_p:last-child]:pt-[7px]
          max-[1100.01px]:grid-cols-[1fr_2fr] max-[1100.01px]:[&_>_p:last-child]:col-2 max-[767.01px]:block
          max-[767.01px]:mb-[30px] max-[767.01px]:[&_h2]:mt-5 max-[767.01px]:[&_>_p:last-child]:pt-5 workflow-intro
        `}
        >
          <p
            className={`
          label [font:400_10px/1.7_var(--sans)] uppercase
          tracking-[0.07em] text-(--muted)
        `}
          >
            02 / The repair loop
          </p>
          <h2 id="workflow-title">
            A path through
            <br />
            the failure.
          </h2>
          <p>
            A readiness probe targets the wrong port.
            <br />
            Follow the six steps that resolve it.
          </p>
        </div>
        <div data-repair-track>
        <div
          ref={root}
          className={`walkthrough grid ${styles.layout}`}
          data-active-stage={active}
          data-reduced-motion={reduced}
        >
          <div
            className={styles.story}
            role="group"
            aria-label="Repair stages"
            tabIndex={0}
            aria-describedby="repair-navigation-hint"
            onKeyDown={navigate}
          >
            <div className={styles.stageControls} role="group" aria-label="Select repair stage">
              {steps.map(([title], index) => (
                <button
                  key={title}
                  type="button"
                  aria-label={`Step ${index + 1}: ${title}`}
                  aria-pressed={active === index}
                  aria-controls="stage-detail"
                  onClick={() => select(index)}
                >
                  {String(index + 1).padStart(2, "0")}
                </button>
              ))}
            </div>
            <div className={styles.orb}>
              {ready && introComplete ? (
                <RepairOrb
                  state={steps[active][2]}
                  reduced={reduced}
                  label={`${steps[active][0]} thinking orb`}
                />
              ) : (
                <span className={styles.orbPlaceholder} aria-hidden="true" />
              )}
            </div>
            {steps.map(([title, copy], index) => (
              <div
                key={title}
                className={styles.scene}
                data-repair-scene
                data-active={active === index}
                aria-hidden={active !== index}
              >
                <div className={styles.stageHeading}>
                  <div>
                    <span className={styles.number}>
                      {String(index + 1).padStart(2, "0")}
                    </span>
                    <h3>{title}</h3>
                  </div>
                </div>
                <p className={styles.copy}>{copy}</p>
              </div>
            ))}
            <svg
              className={styles.connection}
              viewBox="0 0 480 28"
              preserveAspectRatio="none"
              aria-hidden="true"
            >
              <defs>
                <clipPath id={lineId}>
                  <rect
                    data-repair-line-reveal
                    width={reduced ? 480 : 0}
                    height="28"
                  />
                </clipPath>
              </defs>
              <path d="M0 14H480" clipPath={`url(#${lineId})`} />
            </svg>
            <div className={styles.progress}>
              <span className={styles.hint} aria-live="polite" aria-atomic="true">
                Step {active + 1} of {steps.length} · {steps[active][0]}
              </span>
              <a className={styles.skip} href="#execution">
                Skip walkthrough
              </a>
            </div>
          </div>
          <div
            className={`
          inspection min-w-0 bg-(--surface) [border:1px_solid_#4e465f] rounded-[6px] overflow-clip
          [&_h3]:text-[26px] [&_h3]:min-h-17 [&_h3]:max-w-[470px] [&_.stage-copy]:m-[16px_0_22px]
          [&_.stage-copy]:text-[14px] [&_.stage-copy]:leading-[1.7] [&_.stage-copy]:min-h-18
          [&_.stage-copy]:max-w-[510px] [&_.stage-copy]:text-(--muted) [&_.trace-file]:min-w-0
          [&_.trace-file]:wrap-anywhere [&_.stage-evidence]:py-[15px] [&_.stage-evidence]:min-h-40
          max-[767.01px]:[&_h3]:text-[24px] max-[767.01px]:[&_h3]:min-h-[65px]
          max-[767.01px]:[&_.stage-copy]:text-[13px] max-[767.01px]:[&_.stage-copy]:min-h-25
          max-[767.01px]:[&_.stage-evidence]:text-[10px] max-[767.01px]:[&_.stage-evidence]:min-h-[170px]
          [@media((forced-colors:_active))]:[border:1px_solid_CanvasText]
        `}
            id="stage-detail"
          >
            <div
              className={`
          inspection-toolbar flex items-center justify-between flex-wrap gap-2 p-[17px_24px]
          [border-bottom:1px_solid_var(--line)] bg-[#21212e] max-[767.01px]:p-[14px_18px]
          max-[767.01px]:[&_.label]:text-[9px]
        `}
            >
              <span
                className={`
          label [font:400_10px/1.7_var(--mono)] uppercase
          tracking-[0.07em] text-(--muted)
        `}
              >
                Illustrative run / RPH-0482
              </span>
              <span
                key={active}
                className={`inspection-scope text-[#c9b7ed] text-[11px] max-[767.01px]:text-[10px] ${styles.scope}`}
                id="stage-scope"
              >
                {stage.scope}
              </span>
            </div>
            <div className={styles.cardContent}>
              {stages.map((stage, index) => (
                <div
                  className={`inspection-body p-7 min-[768px]:max-[900.01px]:p-[23px] max-[767.01px]:p-[22px_18px] ${styles.cardScene}`}
                  key={stage.label}
                  data-active={active === index}
                  aria-hidden={active !== index}
                  inert={active !== index}
                >
                  <div className="inspection-heading flex justify-between items-center mb-4 [&_.label]:text-[#c8c1d9]">
                    <span
                      className={`
          label [font:400_10px/1.7_var(--mono)] uppercase
          tracking-[0.07em] text-(--muted)
        `}
                      id={active === index ? "stage-label" : undefined}
                    >
                      {stage.label}
                    </span>
                  </div>
                  <h3 id={active === index ? "stage-title" : undefined}>
                    {stage.title}
                  </h3>
                  <p
                    className="stage-copy"
                    id={active === index ? "stage-copy" : undefined}
                  >
                    {stage.copy}
                  </p>
                  <div
                    className={`
          trace-window bg-[#11121a] [border:1px_solid_#ffffff20] rounded-[3px] overflow-clip
          [@media((forced-colors:_active))]:[border:1px_solid_CanvasText]
        `}
                  >
                    <div
                      className={`
          trace-heading flex flex-wrap items-center gap-2 p-[12px_16px] [border-bottom:1px_solid_var(--line)]
          text-[#bfb9cc] [font:10px_var(--mono)] [&_.icon]:w-[15px] [&_.icon]:h-[15px] [&_.icon]:basis-[15px]
          max-[767.01px]:p-[11px_12px] max-[767.01px]:text-[9px]
        `}
                    >
                      <Icon name="file-code" />
                      <span
                        className="trace-file"
                        id={active === index ? "trace-file" : undefined}
                      >
                        {stage.file}
                      </span>
                      <span
                        className="trace-badge ml-auto text-[#cbb8f5] [font:10px_var(--sans)] max-[767.01px]:basis-full max-[767.01px]:m-0"
                        id={active === index ? "trace-badge" : undefined}
                      >
                        {stage.badge}
                      </span>
                    </div>
                    <pre
                      className="stage-evidence"
                      id={active === index ? "stage-evidence" : undefined}
                    >
                      <code>
                        {stage.lines.map(([kind, text], index) => (
                          <span
                            key={index}
                            className={`trace-line block [padding:2px_16px] text-[#bcb7ca] [&.is-removed]:bg-[#e8aba80a] [&.is-removed]:text-[#e8aba8] [&.is-added]:bg-[#b8c9a90a] [&.is-added]:text-[#b8c9a9] [&.is-emphasis]:text-[#eeedf3] max-[767.01px]:px-3${kind ? ` is-${kind}` : ""}`}
                          >
                            {text}
                          </span>
                        ))}
                      </code>
                    </pre>
                  </div>
                  <p
                    className={`
          inspection-result flex items-center gap-[10px] text-[#cbc3da] text-[12px] mt-5 min-h-[38px]
          [&_.icon]:text-(--accent) max-[767.01px]:text-[11px]
        `}
                  >
                    <Icon name="fingerprint" />
                    <span id={active === index ? "stage-result" : undefined}>
                      {stage.result}
                    </span>
                  </p>
                </div>
              ))}
            </div>
            <div
              className={`
          inspection-footer flex items-center gap-[10px] relative [border-top:1px_solid_var(--line)] p-[15px_28px]
          text-[#bcb7ca] text-[11px] max-[767.01px]:p-[14px_18px] max-[767.01px]:text-[10px]
        `}
            >
              <span
                className={`
          status-dot inline-block w-[6px] h-[6px] rounded-[50%] bg-(--accent) flex-[0_0_6px]
          animate-[live-signal-pulse_2.4s_cubic-bezier(0.4,0,0.6,1)_infinite]
        `}
                aria-hidden="true"
              />
              Evidence for step {active + 1} of {steps.length}.
            </div>
          </div>
        </div>
        </div>
        <div
          className={`
          walkthrough-bottom flex items-start justify-between gap-[30px] mt-7 max-[767.01px]:flex-col-reverse
          max-[767.01px]:gap-[22px]
        `}
        >
          <p id="repair-navigation-hint" className="workflow-caveat text-(--muted) text-[13px] max-w-90 max-[767.01px]:text-[12px]">
            Select a step, scroll to follow the repair, or use the arrow keys.
          </p>
        </div>
      </div>
    </section>
  );
}
