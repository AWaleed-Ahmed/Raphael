import SectionNotch from "./SectionNotch";
import { Icon } from "../../../../components/Brand";

export default function Safety() {
  return (
    <section
      className={`
          landing-folder safety-section [&.safety-section]:[--text:#11121a] [&.safety-section]:[--muted:#62616d]
          [&.safety-section]:[--line:#11121a22] [&.safety-section]:[--accent:#6740b8]
          [&.safety-section]:text-(--text) [&.safety-section]:bg-(--paper) [&.safety-section]:scheme-light
          [&.safety-section]:w-full [&.safety-section]:p-[80px_max(56px,calc((100%-1280px)/2))]
          max-[1100.01px]:[&.safety-section]:px-8 max-[767.01px]:[&.safety-section]:w-full
          max-[767.01px]:[&.safety-section]:p-[55px_20px_60px] wrap w-[min(1280px,calc(100%-112px))]
          max-[1100.01px]:w-[calc(100%-64px)] max-[767.01px]:w-[calc(100%-40px)] mx-auto
        `}
      id="safety"
      data-nav-theme="light"
      aria-labelledby="safety-title"
    >
      <SectionNotch variant="safety" />
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
        `}>{"06 / The last step is human"}</p>
          <h2 id="safety-title">
            {"The judgment"}
            <br />
            {"stays "}
            <em>{"yours."}</em>
          </h2>
        </div>
        <p>
          {"Know what Raphael can access."}
          <br />
          {"Know where it stops."}
        </p>
      </div>
      <div className={`
          safety-grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)] gap-[70px] max-[1100.01px]:gap-10
          max-[767.01px]:grid-cols-[1fr] max-[767.01px]:gap-[35px] grid items-start
        `}>
        <div className={`
          draft-ground p-[26px] bg-[#ded9ed] min-w-0 max-[1100.01px]:p-5 min-[768px]:max-[900.01px]:p-[14px]
          max-[767.01px]:p-[18px]
        `}>
          <article className={`
          draft-sheet [--text:#eeedf3] [--muted:#aaa8b6] [--line:#ffffff20] [--accent:#bda4ff] bg-(--surface)
          text-(--text) min-w-0 p-[25px] [border:1px_solid_#ffffff25] [&_h3]:text-[23px] [&_h3]:m-[24px_0]
          [&_dl]:m-0 [&_dl]:text-[12px] [&_dl_>_div]:grid [&_dl_>_div]:grid-cols-[90px_minmax(0,1fr)]
          [&_dl_>_div]:gap-3 [&_dl_>_div]:[border-top:1px_solid_var(--line)] [&_dl_>_div]:p-[12px_0]
          [&_dt]:text-(--muted) [&_dd]:m-0 max-[1100.01px]:p-5
          min-[768px]:max-[900.01px]:[&_dl_>_div]:grid-cols-[1fr] min-[768px]:max-[900.01px]:[&_dl_>_div]:gap-1
          max-[767.01px]:p-5 max-[767.01px]:[&_h3]:text-[21px]
          max-[767.01px]:[&_dl_>_div]:grid-cols-[78px_minmax(0,1fr)] max-[767.01px]:[&_dl_>_div]:gap-[10px]
          max-[767.01px]:[&_.artifact-top]:flex-wrap max-[380.01px]:[&_dl_>_div]:grid-cols-[1fr]
          max-[380.01px]:[&_dl_>_div]:gap-1
        `}>
            <div className={`
          artifact-top flex items-center justify-between gap-3 [border-bottom:1px_solid_var(--line)] pb-[18px]
          [&_.label]:text-[9px]
        `}>
              <p className={`
          label font-(family-name:--mono) [font-variant-ligatures:none] [font:400_10px/1.7_var(--mono)] uppercase
          tracking-[0.07em] text-(--muted)
        `}>{"Illustrative draft pull request"}</p>
              <span className={`
          badge inline-block [border:1px_solid_#bda4ff35] bg-[#bda4ff12] text-[#cfbdf8] text-[10px] p-[4px_8px]
          rounded-[3px] whitespace-nowrap
        `}>{"Draft"}</span>
            </div>
            <h3>{"Align readiness probe with container port"}</h3>
            <dl>
              <div>
                <dt>{"Change"}</dt>
                <dd>
                  <code>{"8081 → 8080"}</code>
                </dd>
              </div>
              <div>
                <dt>{"Evidence"}</dt>
                <dd>{"Event + deployment manifest"}</dd>
              </div>
              <div>
                <dt>{"Validation"}</dt>
                <dd>{"Sandbox checks and scope attached"}</dd>
              </div>
              <div>
                <dt>{"Open question"}</dt>
                <dd>{"Review within your deployment process"}</dd>
              </div>
            </dl>
            <p className={`
          review-status flex gap-[10px] items-center pt-[18px] [border-top:1px_solid_var(--line)] mt-[18px]
          text-[11px] text-[#cbc3da]
        `}>
              <Icon name="git-pull-request" className="icon w-[18px] h-[18px] fill-current flex-[0_0_18px] align-middle pointer-events-none review-icon" />
              {"Awaiting review · no automatic merge"}
            </p>
          </article>
        </div>
        <div className={`
          safety-statements [&_article]:grid [&_article]:grid-cols-[22px_minmax(0,1fr)_20px]
          [&_article]:gap-x-[15px] [&_article]:[border-bottom:1px_solid_var(--line)] [&_article]:p-[22px_0]
          [&_article:first-child]:pt-0 [&_h3]:col-2 [&_h3]:row-1 [&_h3]:text-[19px] [&_article_p]:col-2
          [&_article_p]:text-[13px] [&_article_p]:text-(--muted) [&_article_p]:mt-[9px]
        `}>
          <article>
            <span className="principle-number col-1 row-1 text-(--muted) [font:10px_var(--mono)] pt-[5px]">{"01"}</span>
            <Icon name="shield-check" className={`
          icon w-[18px] h-[18px] fill-current flex-[0_0_18px] align-middle pointer-events-none principle-icon col-3
          row-1 text-[#6740b8]
        `} />
            <h3>{"Production stays read-only."}</h3>
            <p>{"Observation never becomes an unreviewed write."}</p>
          </article>
          <article>
            <span className="principle-number col-1 row-1 text-(--muted) [font:10px_var(--mono)] pt-[5px]">{"02"}</span>
            <Icon name="warning" className={`
          icon w-[18px] h-[18px] fill-current flex-[0_0_18px] align-middle pointer-events-none principle-icon col-3
          row-1 text-[#6740b8]
        `} />
            <h3>{"A blocked run stays blocked."}</h3>
            <p>{"Missing checks and uncertainty stay in the report."}</p>
          </article>
          <article>
            <span className="principle-number col-1 row-1 text-(--muted) [font:10px_var(--mono)] pt-[5px]">{"03"}</span>
            <Icon name="git-pull-request" className={`
          icon w-[18px] h-[18px] fill-current flex-[0_0_18px] align-middle pointer-events-none principle-icon col-3
          row-1 text-[#6740b8]
        `} />
            <h3>{"Your team controls delivery."}</h3>
            <p>
              {
                "Draft creation, review, merge and deployment are distinct. Live publishing is opt-in; dry-run is the default."
              }
            </p>
          </article>
          <details className={`
          delivery-details [&_>_p]:text-[13px] [&_>_p]:leading-[1.8] [&_>_p]:text-(--muted) [&_>_p]:max-w-215
          [&_>_p]:m-[14px_0_20px] [&_summary]:text-[12px]
        `}>
            <summary>
              {"Delivery modes and validation scope"}
              <Icon name="plus" className={`
          icon w-[18px] h-[18px] fill-current flex-[0_0_18px] align-middle pointer-events-none disclosure-icon
          [&.disclosure-icon]:ml-auto [&.disclosure-icon]:[transition:transform_200ms_ease]
          [details[open]_>_summary_>_&.disclosure-icon]:transform-[rotate(45deg)]
        `} />
            </summary>
            <p>
              {
                "This example follows the sandbox-backed draft-PR route. The issue-snippet route does not open a PR and can have a different validation scope. Check the evidence attached to each output."
              }
            </p>
            <p>
              {
                "Production Secret payloads are outside the permission model. Sandbox fixtures use synthetic values rather than copied production secrets."
              }
            </p>
          </details>
        </div>
      </div>
    </section>
  );
}
