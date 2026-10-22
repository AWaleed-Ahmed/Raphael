import ValidationExample from "./ValidationExample";
import SectionNotch from "./SectionNotch";
import { Icon } from "../../../../components/Brand";

export default function Evidence() {
  return (
    <section
      className={`
          landing-folder evidence-section [&.evidence-section]:[--text:#11121a] [&.evidence-section]:[--muted:#62616d]
          [&.evidence-section]:[--line:#11121a22] [&.evidence-section]:[--accent:#6740b8]
          [&.evidence-section]:text-(--text) [&.evidence-section]:bg-(--paper) [&.evidence-section]:scheme-light
          [&.evidence-section]:w-full [&.evidence-section]:p-[80px_max(56px,calc((100%-1280px)/2))]
          max-[1100.01px]:[&.evidence-section]:px-8 max-[767.01px]:[&.evidence-section]:w-full
          max-[767.01px]:[&.evidence-section]:p-[55px_20px_60px] wrap w-[min(1280px,calc(100%-112px))]
          max-[1100.01px]:w-[calc(100%-64px)] max-[767.01px]:w-[calc(100%-40px)] mx-auto
        `}
      data-nav-theme="light"
      id="evidence"
      aria-labelledby="evidence-title"
    >
      <SectionNotch variant="evidence" />
      <div className={`
          section-heading flex items-end justify-between gap-10 mb-[45px] [&_h2]:mt-5 [&_>_p]:text-(--muted)
          [&_>_p]:text-[13px] min-[768px]:max-[900.01px]:gap-[25px]
          min-[768px]:max-[900.01px]:[&_>_p]:max-w-[230px] max-[767.01px]:block max-[767.01px]:mb-[30px]
          max-[767.01px]:[&_>_p]:mt-5
        `}>
        <div>
          <p className={`
          label font-(family-name:--mono) [font-variant-ligatures:none] [font:400_10px/1.7_var(--mono)] uppercase
          tracking-[0.07em] text-(--muted)
        `}>{"04 / The evidence room"}</p>
          <h2 id="evidence-title">
            {"Less guesswork."}
            <br />
            <em>{"More evidence."}</em>
          </h2>
        </div>
        <p>
          {"The source, the change, and the result."}
          <br />
          {"Together when you need to review."}
        </p>
      </div>
      <div className={`
          evidence-grid grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)] gap-5 max-[767.01px]:grid-cols-[1fr]
          max-[767.01px]:gap-[18px] grid
        `}>
        <article className="evidence-panel row-[span_2] self-start [border:1px_solid_var(--line)] bg-[#f5f4f8] min-w-0">
          <div className={`
          panel-heading p-[26px_26px_20px] [&_h3]:text-[21px] [&_p]:text-[13px] [&_p]:text-(--muted) [&_p]:mt-2
          max-[767.01px]:p-[22px]
        `}>
            <h3>{"Context with a source."}</h3>
            <p>{"Trace the diagnosis back to what happened."}</p>
          </div>
          <div className="evidence-landscape p-[0_26px_26px] max-[767.01px]:p-[0_22px_22px]">
            <div className="source-sheet [border-top:1px_solid_var(--line)] [&_>_.label]:p-[18px_0_4px]">
              <p className={`
          label font-(family-name:--mono) [font-variant-ligatures:none] [font:400_10px/1.7_var(--mono)] uppercase
          tracking-[0.07em] text-(--muted)
        `}>{"Evidence / payments-api"}</p>
              <details className={`
          source [border-bottom:1px_solid_var(--line)] last:border-0 [&_summary]:relative [&_summary]:flex-wrap
          [&_summary]:gap-[3px] [&_summary]:p-[19px_30px_19px_0] [&_summary_>_span]:basis-full
          [&_summary_>_span]:[font:10px_var(--mono)] [&_summary_>_span]:text-(--muted)
          [&_summary_strong]:[font:500_15px_var(--sans)] [&_summary_.icon]:absolute [&_summary_.icon]:right-0
          [&_summary_.icon]:top-[29px] [&_>_p]:text-[13px] [&_>_p]:text-(--muted) [&_>_p]:pb-[15px]
          [&_>_code]:block [&_>_code]:mb-5 [&_>_code]:p-3 [&_>_code]:bg-[#e9e7ef] [&_>_code]:text-[11px]
          [&_>_pre]:block [&_>_pre]:mb-5 [&_>_pre]:p-3 [&_>_pre]:bg-[#e9e7ef] [&_>_pre]:text-[11px]
        `}>
                <summary>
                  <span>{"Kubernetes event"}</span>
                  <strong>{"Readiness probe failed"}</strong>
                  <Icon name="plus" className={`
          icon w-[18px] h-[18px] fill-current flex-[0_0_18px] align-middle pointer-events-none disclosure-icon
          [&.disclosure-icon]:ml-auto [&.disclosure-icon]:[transition:transform_200ms_ease]
          [details[open]_>_summary_>_&.disclosure-icon]:transform-[rotate(45deg)]
        `} />
                </summary>
                <p>
                  {
                    "Illustrative event: the readiness probe received a connection refusal at port 8081. A running container does not necessarily pass its readiness check."
                  }
                </p>
                <code>{"GET :8081/healthz → refused"}</code>
              </details>
              <details className={`
          source [border-bottom:1px_solid_var(--line)] last:border-0 [&_summary]:relative [&_summary]:flex-wrap
          [&_summary]:gap-[3px] [&_summary]:p-[19px_30px_19px_0] [&_summary_>_span]:basis-full
          [&_summary_>_span]:[font:10px_var(--mono)] [&_summary_>_span]:text-(--muted)
          [&_summary_strong]:[font:500_15px_var(--sans)] [&_summary_.icon]:absolute [&_summary_.icon]:right-0
          [&_summary_.icon]:top-[29px] [&_>_p]:text-[13px] [&_>_p]:text-(--muted) [&_>_p]:pb-[15px]
          [&_>_code]:block [&_>_code]:mb-5 [&_>_code]:p-3 [&_>_code]:bg-[#e9e7ef] [&_>_code]:text-[11px]
          [&_>_pre]:block [&_>_pre]:mb-5 [&_>_pre]:p-3 [&_>_pre]:bg-[#e9e7ef] [&_>_pre]:text-[11px]
        `}>
                <summary>
                  <span>{"Repository manifest"}</span>
                  <strong>{"containerPort: 8080"}</strong>
                  <Icon name="plus" className={`
          icon w-[18px] h-[18px] fill-current flex-[0_0_18px] align-middle pointer-events-none disclosure-icon
          [&.disclosure-icon]:ml-auto [&.disclosure-icon]:[transition:transform_200ms_ease]
          [details[open]_>_summary_>_&.disclosure-icon]:transform-[rotate(45deg)]
        `} />
                </summary>
                <p>
                  {"Illustrative excerpt from "}
                  <code>{"deploy/deployment.yaml"}</code>
                  {". The workload declares port 8080."}
                </p>
                <pre>
                  <code>{"ports:\n  - containerPort: 8080"}</code>
                </pre>
              </details>
              <details className={`
          source [border-bottom:1px_solid_var(--line)] last:border-0 [&_summary]:relative [&_summary]:flex-wrap
          [&_summary]:gap-[3px] [&_summary]:p-[19px_30px_19px_0] [&_summary_>_span]:basis-full
          [&_summary_>_span]:[font:10px_var(--mono)] [&_summary_>_span]:text-(--muted)
          [&_summary_strong]:[font:500_15px_var(--sans)] [&_summary_.icon]:absolute [&_summary_.icon]:right-0
          [&_summary_.icon]:top-[29px] [&_>_p]:text-[13px] [&_>_p]:text-(--muted) [&_>_p]:pb-[15px]
          [&_>_code]:block [&_>_code]:mb-5 [&_>_code]:p-3 [&_>_code]:bg-[#e9e7ef] [&_>_code]:text-[11px]
          [&_>_pre]:block [&_>_pre]:mb-5 [&_>_pre]:p-3 [&_>_pre]:bg-[#e9e7ef] [&_>_pre]:text-[11px]
        `}>
                <summary>
                  <span>{"Probe configuration"}</span>
                  <strong>{"httpGet.port: 8081"}</strong>
                  <Icon name="plus" className={`
          icon w-[18px] h-[18px] fill-current flex-[0_0_18px] align-middle pointer-events-none disclosure-icon
          [&.disclosure-icon]:ml-auto [&.disclosure-icon]:[transition:transform_200ms_ease]
          [details[open]_>_summary_>_&.disclosure-icon]:transform-[rotate(45deg)]
        `} />
                </summary>
                <p>
                  {
                    "The probe targets a different port. Reproduction is needed before this discrepancy can be treated as a validated cause."
                  }
                </p>
                <pre>
                  <code>
                    {
                      "readinessProbe:\n  httpGet:\n    path: /healthz\n    port: 8081"
                    }
                  </code>
                </pre>
              </details>
            </div>
          </div>
        </article>
        <article className={`
          diff-panel [--text:#eeedf3] [--muted:#aaa8b6] [--line:#ffffff20] [--accent:#bda4ff] bg-(--surface)
          text-(--text) min-w-0 p-[26px] [&_h3]:text-[23px] [&_h3]:m-[12px_0_18px] [&_>_.mono]:text-(--muted)
          [&_>_.mono]:text-[11px] [&_>_.mono]:wrap-anywhere max-[767.01px]:p-[22px]
        `}>
          <p className={`
          label font-(family-name:--mono) [font-variant-ligatures:none] [font:400_10px/1.7_var(--mono)] uppercase
          tracking-[0.07em] text-(--muted)
        `}>{"The proposed change"}</p>
          <h3>{"Small enough to inspect."}</h3>
          <p className="mono font-(family-name:--mono) [font-variant-ligatures:none] text-[12px]">{"deploy/deployment.yaml"}</p>
          <div className="diff-lines bg-[#11121a] m-[18px_0] p-[15px] [&_code]:block [&_code]:text-[12px] [&_code]:leading-[1.9]">
            <code className="deletion text-[#e8aba8]">{"−     port: 8081"}</code>
            <code className="addition text-[#b8c9a9]">{"+     port: 8080"}</code>
          </div>
          <details className={`
          full-diff [&_summary]:text-[12px] [&_summary]:[border-top:1px_solid_var(--line)] [&_pre]:p-[14px]
          [&_pre]:bg-[#11121a] [&_pre]:text-[11px] [&_p]:text-[11px] [&_p]:text-(--muted) [&_p]:mt-3
        `}>
            <summary>
              {"See the surrounding configuration"}
              <Icon name="plus" className={`
          icon w-[18px] h-[18px] fill-current flex-[0_0_18px] align-middle pointer-events-none disclosure-icon
          [&.disclosure-icon]:ml-auto [&.disclosure-icon]:[transition:transform_200ms_ease]
          [details[open]_>_summary_>_&.disclosure-icon]:transform-[rotate(45deg)]
        `} />
            </summary>
            <pre>
              <code>
                {"readinessProbe:\n  httpGet:\n    path: /healthz\n"}
                <span className="deletion text-[#e8aba8]">{"−   port: 8081"}</span>
                <span className="addition text-[#b8c9a9]">{"+   port: 8080"}</span>
              </code>
            </pre>
            <p>{"Illustrative excerpt · one field changed."}</p>
          </details>
        </article>
        <ValidationExample />
      </div>
    </section>
  );
}
