import { BrandMark, Icon } from "../../../../components/Brand";
import styles from "./DeploymentStage.module.css";
import { useId } from "react";

function StageOutline({ id }) {
  const maskId = useId();
  return (
    <svg className={styles.stageOutline} data-execution-frame={id} aria-hidden="true">
      <defs><mask id={maskId} maskUnits="userSpaceOnUse" x="0" y="0" width="100%" height="100%">
        <rect data-frame-reveal x="1" y="1" rx="7" pathLength="1" fill="none" stroke="white" strokeWidth="4" />
      </mask></defs>
      <rect data-frame-outline className={styles.frameDots} x="1" y="1" rx="7" fill="none" mask={`url(#${maskId})`} />
    </svg>
  );
}

function PhaseHeading({ id, number, children, note }) {
  return <p className={styles.groupLabel} data-execution-phase={id}>
    <span className={styles.phaseLabel} data-phase-label>
      <span className={styles.phaseDot} aria-hidden="true" />
      <span className={styles.phaseNumber}>{number}</span><span>{children}</span>
    </span>
    {note && <span className={styles.boundary}>{note}</span>}
  </p>;
}

function ExecutionGraphic({ kind }) {
  // Small schematics use Raphael's own evidence / sandbox / handoff vocabulary.
  const drawings = {
    event: <><path d="M4 24H22L30 12L40 35L52 5L65 24H91" /><circle cx="101" cy="24" r="4" fill="currentColor" stroke="none" /><path d="M101 5V12M101 36V43" opacity=".35" /></>,
    manifest: <><path d="M15 9V36M15 18H42Q51 18 51 27V33H96" /><circle cx="15" cy="8" r="4" /><circle cx="15" cy="37" r="4" /><circle cx="99" cy="33" r="4" /><path d="M65 10H99M76 17H99" opacity=".35" /></>,
    investigate: <><path d="M6 10H24C39 10 31 24 49 24M6 38H24C39 38 31 24 49 24M65 24H105" /><circle cx="7" cy="10" r="3" fill="currentColor" /><circle cx="7" cy="38" r="3" fill="currentColor" /><path d="m49 24 8-8 8 8-8 8Z" fill="currentColor" fillOpacity=".15" /><path d="M88 10H105M95 38H105" opacity=".3" /></>,
    sandbox: <><path d="m18 9 15 8v17l-15 8-15-8V17Zm0 16 15-8M18 25 3 17m15 8v17M56 9l15 8v17l-15 8-15-8V17Zm0 16 15-8M56 25l-15-8m15 8v17" /><path d="m83 27 7 7 15-18" strokeWidth="2.5" /></>,
    prepare: <><path d="M7 9H52M7 19H42M7 29H32M7 39H43M62 9V39H91" opacity=".55" /><path d="m73 16 7 7 14-15M98 25V41" /><circle cx="98" cy="42" r="3" fill="currentColor" /></>,
    draft: <><path d="M18 37H7V6H77V15M23 16H104V45H23Z" /><path d="M33 26H56M33 35H50M71 31h23M82 20v22" strokeWidth="2" /></>,
    review: <><path d="M20 7 37 13V26C37 36 29 41 20 45 11 41 3 36 3 26V13Z" fill="currentColor" fillOpacity=".1" /><path d="m11 25 6 6 12-14M51 13H107M51 25H94M51 37H79" /></>,
  };
  return <svg className={styles.nodeGraphic} viewBox="0 0 112 50" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{drawings[kind]}</svg>;
}

function DetailHeading({ children }) {
  return <div className={styles.detailHeading}><span aria-hidden="true" /><span>{children}</span></div>;
}

function Node({ id, icon, label, title, children, light = false }) {
  return (
    <div data-execution-node={id} className={`${styles.node} ${light ? styles.paper : ""}`}>
      <span className={styles.wash} data-execution-wash aria-hidden="true" />
      <div className={styles.nodeLabel}><span className={styles.nodeIcon}>{icon ? <Icon name={icon} /> : <BrandMark />}</span><span>{label}</span></div>
      <h3>{title}</h3>
      {children}
      <ExecutionGraphic kind={id} />
    </div>
  );
}

const edges = [
  ["signals", "execution", "input"],
  ["investigate", "investigate-detail", "detail"],
  ["investigate", "sandbox", "step"], ["sandbox", "sandbox-detail", "detail"],
  ["sandbox", "prepare", "step"], ["prepare", "prepare-detail", "detail"],
  ["prepare", "draft", "output"], ["prepare", "review", "output"],
];

export default function DeploymentStage() {
  return (
    <section className={`deployment-stage ${styles.stage}`} id="execution" aria-labelledby="deployment-stage-title">
      <svg className={styles.notch} viewBox="0 0 1440 90" preserveAspectRatio="none" aria-hidden="true"><path d="M0 90V29Q0 1 28 1H292Q316 1 324 25Q332 49 356 49H1084Q1108 49 1116 25Q1124 1 1148 1H1412Q1440 1 1440 29V90" /></svg>
      <div className={styles.baseline}>
        <div
          className={`
          hero-baseline flex gap-[34px] pt-5 [border-top:1px_solid_#d0c8f526] text-[#bcb7cf] text-[11px]
          [&_span]:flex [&_span]:items-center [&_span]:gap-2 [&_.icon]:w-[15px] [&_.icon]:h-[15px]
          [&_.icon]:basis-[15px] [&_.icon]:text-[#cbb8f5] max-[767.01px]:flex-col max-[767.01px]:gap-3
          max-[767.01px]:pt-[18px]
        `}
        >
          <span>
            <Icon
              name="magnifying-glass"
              className="icon w-[18px] h-[18px] fill-current flex-[0_0_18px] align-middle pointer-events-none"
            />
            {"Event + source"}
          </span>
          <span>
            <Icon
              name="cube"
              className="icon w-[18px] h-[18px] fill-current flex-[0_0_18px] align-middle pointer-events-none"
            />
            {"Sandbox boundary"}
          </span>
          <span>
            <Icon
              name="git-pull-request"
              className="icon w-[18px] h-[18px] fill-current flex-[0_0_18px] align-middle pointer-events-none"
            />
            {"Draft + attachments"}
          </span>
        </div>
      </div>
      <div className={styles.surface}>
        <div className={styles.heading}>
          <div><p className={styles.eyebrow}>03 / Under the hood</p><h2 id="deployment-stage-title">How the pieces connect.</h2><p className={styles.intro}>Trace the inputs, the sandbox boundary, and the artifacts passed between components.</p></div>
          <div className={styles.context}><span>Illustrative run / RPH-0482</span><strong>payments-api</strong><span>Source revision / a81f2c</span></div>
        </div>
        <div className={styles.board} data-execution-board>
          <svg className={styles.wires} data-execution-wires aria-hidden="true">
            {edges.map(([from, to, kind]) => <path key={`${from}-${to}`} data-execution-edge={`${from}:${to}`} data-edge-kind={kind} pathLength="1" />)}
          </svg>
          <svg className={styles.headerRail} data-execution-header-wires aria-hidden="true">
            {["execution:handoff"].map((edge) => <g key={edge}>
              <path data-progress-track={edge} className={styles.progressTrack} />
              <path data-execution-progress={edge} className={styles.progressFill} pathLength="1" />
            </g>)}
          </svg>
          <div className={styles.signals} data-execution-group="signals">
            <StageOutline id="phase-signals" />
            <PhaseHeading id="signals" number="01">Signals</PhaseHeading>
            <Node id="event" icon="warning" label="Kubernetes event" title="Readiness probe failed">
              <code>GET :8081/healthz</code><p>Connection refused.</p>
            </Node>
            <Node id="manifest" icon="file-code" label="Repository" title="Deployment manifest">
              <code>containerPort: 8080</code><p>Source revision / a81f2c</p>
            </Node>
          </div>
          <div className={styles.execution} data-execution-group="execution">
            <StageOutline id="phase-execution" />
            <PhaseHeading id="execution" number="02" note="Isolated. Scoped. Traceable.">Execution</PhaseHeading>
            <div className={styles.steps}>
              <div className={styles.step} data-execution-stage="investigate">
                <StageOutline id="investigate" />
                <Node id="investigate" label="Raphael" title="Correlate the inputs"><p>Kubernetes event + repository revision.</p></Node>
                <div data-execution-node="investigate-detail" className={styles.detail}>
                  <DetailHeading>Evidence cross-check</DetailHeading>
                  <span className={styles.detailLabel}>Finding / candidate cause</span>
                  <div className={styles.portRow}><span>Container</span><strong>8080</strong></div>
                  <div className={styles.portRow}><span>Probe</span><strong className={styles.failed}>8081</strong></div>
                  <p className={styles.finding}>Port mismatch identified.</p>
                </div>
              </div>
              <div className={styles.step} data-execution-stage="sandbox">
                <StageOutline id="sandbox" />
                <Node id="sandbox" icon="cube" label="Ignis sandbox" title="Execute in Ignis"><p>Baseline and patched runs share an isolated fixture.</p></Node>
                <div data-execution-node="sandbox-detail" className={styles.detail}>
                  <DetailHeading>Isolated patch</DetailHeading>
                  <span className={styles.detailLabel}>deploy/deployment.yaml</span>
                  <code className={styles.diff}><span className={styles.removed}>− port: 8081</span><span className={styles.added}>+ port: 8080</span></code>
                  <p className={styles.check}><Icon name="shield-check" />Original failure reproduced</p>
                </div>
              </div>
              <div className={styles.step} data-execution-stage="prepare">
                <StageOutline id="prepare" />
                <Node id="prepare" icon="git-pull-request" label="Raphael" title="Assemble the artifacts"><p>Diff, check results, and validation scope.</p></Node>
                <div data-execution-node="prepare-detail" className={styles.detail}>
                  <DetailHeading>Validation attached</DetailHeading>
                  <span className={styles.detailLabel}>Sandbox validation</span>
                  <p className={styles.check}><Icon name="shield-check" />Original signature absent</p>
                  <p className={styles.check}><Icon name="shield-check" />Required checks passed</p>
                  <div className={styles.checkGraph} aria-hidden="true"><span /><span /></div>
                  <span className={styles.scope}>Scope / isolated sandbox only</span>
                </div>
              </div>
            </div>
          </div>
          <div className={styles.outputs} data-execution-group="handoff">
            <StageOutline id="phase-handoff" />
            <PhaseHeading id="handoff" number="03">Handoff</PhaseHeading>
            <Node id="draft" icon="git-pull-request" label="Draft pull request" title="A repair you can inspect" light><p>One-field diff. Evidence and validation attached.</p><span className={styles.badge}>Ready for review</span></Node>
            <Node id="review" icon="shield-check" label="Human review" title="Repository handoff"><p>The draft returns to your existing review process.</p><span className={styles.scope}>Delivery boundary</span></Node>
          </div>
        </div>
        <div className={styles.bottom}><p>Every connection carries an input, a result, or its validation scope.</p><a href="#evidence">Inspect the repair evidence <Icon name="arrow-down" /></a></div>
      </div>
    </section>
  );
}
