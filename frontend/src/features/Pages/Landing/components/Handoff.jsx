import SectionNotch from "./SectionNotch";
import { Icon } from "../../../../components/Brand";

function Attachment({ title, children }) {
  return (
    <details className="handoff-attachment">
      <summary>{title}<Icon name="plus" /></summary>
      <div>{children}</div>
    </details>
  );
}

export default function Handoff() {
  return (
    <section
      className={`
          landing-folder handoff-section [--text:#11121a] [--muted:#62616d] [--line:#11121a22] [--accent:#6740b8] text-(--text)
          bg-(--paper) scheme-light py-18 max-[767.01px]:py-[50px]
        `}
      id="example"
      data-nav-theme="light"
      aria-labelledby="example-title"
    >
      <SectionNotch variant="handoff" />
      <div data-reveal="gentle" className={`
          wrap w-[min(1280px,calc(100%-112px))] max-[1100.01px]:w-[calc(100%-64px)]
          max-[767.01px]:w-[calc(100%-40px)] handoff-layout grid-cols-[1fr_1fr] gap-[75px] max-[1100.01px]:gap-10
          max-[767.01px]:grid-cols-[1fr] max-[767.01px]:gap-7 grid items-center mx-auto
        `}>
        <div className={`
          handoff-copy [&_h2]:mt-[22px] [&_>_p:not(.label)]:max-w-95 [&_>_p:not(.label)]:text-[14px]
          [&_>_p:not(.label)]:text-(--muted) [&_>_p:not(.label)]:mt-5 [&_.text-link]:mt-4
        `}>
          <p className={`
          label font-(family-name:--mono) [font-variant-ligatures:none] [font:400_10px/1.7_var(--mono)] uppercase
          tracking-[0.07em] text-(--muted)
        `}>{"01 / The handoff"}</p>
          <h2 id="example-title">
            {"The change is small."}
            <br />
            {"The context isn’t."}
          </h2>
          <p>
            {
              "A focused diff, the source behind it, and the results of sandbox checks. Open each attachment to see what comes with the draft."
            }
          </p>
          <a className={`
          text-link inline-flex items-center gap-[10px] py-[9px] text-[12px] underline-offset-[5px]
          [&:hover]:underline
        `} href="#repair">
            {"Follow this repair "}
            <Icon name="arrow-down" className="icon w-[18px] h-[18px] fill-current flex-[0_0_18px] align-middle pointer-events-none" />
          </a>
        </div>
        <article className={`
          handoff-draft [--text:#eeedf3] [--muted:#aaa8b6] [--line:#ffffff20] [--accent:#bda4ff] bg-(--surface)
          text-(--text) min-w-0 [border:1px_solid_#ffffff26]
        `}>
          <div className={`
          draft-toolbar flex items-center justify-between gap-3 [border-bottom:1px_solid_var(--line)] p-[14px_20px]
          max-[767.01px]:p-[12px_14px]
        `}>
            <span className={`
          label font-(family-name:--mono) [font-variant-ligatures:none] [font:400_10px/1.7_var(--mono)] uppercase
          tracking-[0.07em] text-(--muted)
        `}>{"Illustrative / RPH-0482"}</span>
            <span className="draft-status text-(--accent) text-[10px]">{"Awaiting review"}</span>
          </div>
          <div className={`
          draft-heading flex items-center gap-4 p-[24px_20px] [&_>_.icon]:w-10 [&_>_.icon]:h-10
          [&_>_.icon]:basis-[40px] [&_>_.icon]:p-[10px] [&_>_.icon]:[border:1px_solid_#ffffff28] [&_h3]:text-[17px]
          [&_.mono]:text-[11px] [&_.mono]:text-(--muted) [&_.mono]:mt-[5px] [&_.mono]:wrap-anywhere
          max-[767.01px]:p-[20px_14px] max-[767.01px]:gap-3 max-[767.01px]:[&_h3]:text-[16px]
        `}>
            <Icon name="git-pull-request" className="icon w-[18px] h-[18px] fill-current flex-[0_0_18px] align-middle pointer-events-none" />
            <div>
              <h3>{"Align the readiness probe"}</h3>
              <p className="mono font-(family-name:--mono) [font-variant-ligatures:none] text-[12px]">{"payments-api / deploy/deployment.yaml"}</p>
            </div>
          </div>
          <div className={`
          draft-diff m-[0_20px_22px] bg-[#101017] p-[13px_16px] [&_code]:block [&_code]:text-[13px]
          [&_code]:leading-[1.9] max-[767.01px]:mx-[14px]
        `}>
            <code className="deletion text-[#e8aba8]">{"− port: 8081"}</code>
            <code className="addition text-[#b8c9a9]">{"+ port: 8080"}</code>
          </div>
          <div className="handoff-attachments">
            <Attachment title="Inspect the full diff">
              <p>Only the probe port changes in this illustrative deployment.</p>
              <pre><code>{"readinessProbe:\n  httpGet:\n    path: /healthz\n"}<span className="text-[#e8aba8]">{"-   port: 8081\n"}</span><span className="text-[#b8c9a9]">{"+   port: 8080"}</span></code></pre>
            </Attachment>
            <Attachment title="Inspect the source evidence">
              <p>The Kubernetes event reports a refused connection on port 8081. The same revision's manifest declares container port 8080.</p>
              <pre><code>{"Warning  Unhealthy  payments-api\nGET :8081/healthz → connection refused\ncontainerPort: 8080\nrevision: a81f2c"}</code></pre>
              <p>This mismatch is the hypothesis tested in the sandbox.</p>
            </Attachment>
            <Attachment title="Inspect the validation summary">
              <ul>
                <li>Before: original failure reproduced.</li>
                <li>After: original failure signature absent.</li>
                <li>Required sandbox checks: passed.</li>
              </ul>
              <p>Scope: this illustrative isolated sandbox run. These checks do not establish production readiness.</p>
            </Attachment>
          </div>
          <div className={`
          draft-bottom flex justify-between flex-wrap gap-3 p-[13px_20px] [border-top:1px_solid_var(--line)]
          text-[11px] text-(--muted) [&_span:first-child]:flex [&_span:first-child]:items-center
          [&_span:first-child]:gap-[6px] [&_.icon]:w-[13px] [&_.icon]:h-[13px] [&_.icon]:basis-[13px]
          max-[767.01px]:p-[12px_14px]
        `}>
            <span>
              <Icon name="shield-check" className="icon w-[18px] h-[18px] fill-current flex-[0_0_18px] align-middle pointer-events-none" />
              {"Sandbox checks attached"}
            </span>
            <span>{"One field changed"}</span>
          </div>
        </article>
      </div>
    </section>
  );
}
