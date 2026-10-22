import SectionNotch from "./SectionNotch";
import { Icon } from "../../../../components/Brand";

export default function Architecture() {
  return (
    <section
      className="landing-folder architecture p-[88px_0_60px] bg-[#191923] max-[767.01px]:p-[60px_0_40px]"
      id="architecture"
      data-nav-theme="ink"
      aria-labelledby="architecture-title"
    >
      <SectionNotch variant="architecture" />
      <div className={`
          wrap w-[min(1280px,calc(100%-112px))] max-[1100.01px]:w-[calc(100%-64px)]
          max-[767.01px]:w-[calc(100%-40px)] mx-auto
        `}>
        <div className={`
          architecture-grid grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)] gap-18 mb-[45px] max-[1100.01px]:gap-10
          max-[767.01px]:grid-cols-[1fr] max-[767.01px]:gap-[30px] max-[767.01px]:mb-7 grid items-center
        `}>
          <div className={`
          architecture-copy [&_h2]:mt-[23px] [&_>_p:not(.label)]:text-[14px] [&_>_p:not(.label)]:leading-[1.95]
          [&_>_p:not(.label)]:text-(--muted) [&_>_p:not(.label)]:m-[23px_0_28px]
        `}>
            <p className={`
          label font-(family-name:--mono) [font-variant-ligatures:none] [font:400_10px/1.7_var(--mono)] uppercase
          tracking-[0.07em] text-(--muted)
        `}>{"05 / A deliberate separation"}</p>
            <h2 id="architecture-title">
              {"One workflow."}
              <br />
              {"Separate powers."}
            </h2>
            <p>
              {"Raphael investigates and prepares the repair."}
              <br />
              {"Ignis executes inside the sandbox."}
              <br />
              {"Your team controls what ships."}
            </p>
            <a className={`
          button inline-flex items-center justify-center gap-[22px] min-h-[46px] p-[13px_20px]
          [border:1px_solid_transparent] rounded-[3px] bg-(--accent) text-(--night) [font:500_13px/1.4_var(--sans)]
          [transition:background-color_180ms_ease,border-color_180ms_ease,box-shadow_180ms_ease]
          [&:hover]:bg-[#d1beff] [@media((forced-colors:_active))]:[border:1px_solid_CanvasText] button-light
          [&.button-light]:bg-[#eeedf3] [&.button-light]:text-[#11121a] [&.button-light:hover]:bg-[#dcd6eb]
        `} href="#boundaries">
              {"Inspect the boundaries "}
              <Icon name="arrow-up-right" className="icon w-[18px] h-[18px] fill-current flex-[0_0_18px] align-middle pointer-events-none " />
            </a>
          </div>
          <div
            className={`
          permission-map bg-[#12131b] [border:1px_solid_#ffffff25] p-[25px] min-w-0 max-[1100.01px]:p-5
          max-[767.01px]:p-[18px]
        `}
            aria-label="Production signals enter Raphael. Raphael coordinates Ignis and publishes draft pull requests for review."
          >
            <p className={`
          label font-(family-name:--mono) [font-variant-ligatures:none] [font:400_10px/1.7_var(--mono)] uppercase
          tracking-[0.07em] text-(--muted)
        `}>{"Permission boundaries"}</p>
            <div className={`
          production-box flex items-center justify-between gap-[15px] bg-[#21212e] p-5 mt-5 [&_h3]:text-[19px]
          [&_p]:text-[12px] [&_p]:text-(--muted) [&_p]:mt-[7px] max-[767.01px]:p-4
          max-[767.01px]:[&_h3]:text-[17px]
        `}>
              <div>
                <h3>{"Production signals"}</h3>
                <p>{"Read-derived evidence only"}</p>
              </div>
              <span className={`
          badge inline-block [border:1px_solid_#bda4ff35] bg-[#bda4ff12] text-[#cfbdf8] text-[10px] p-[4px_8px]
          rounded-[3px] whitespace-nowrap
        `}>{"Read only"}</span>
            </div>
            <div className="evidence-transfer text-(--muted) p-[14px_0_14px_15%] text-[11px] [&_.icon]:w-[14px] [&_.icon]:h-[14px]">
              <span>
                <Icon name="arrow-down" className="icon w-[18px] h-[18px] fill-current flex-[0_0_18px] align-middle pointer-events-none " />
                {" evidence"}
              </span>
            </div>
            <div className={`
          actor-grid grid-cols-[minmax(0,1fr)_30px_minmax(0,1fr)] items-stretch
          max-[767.01px]:grid-cols-[minmax(0,1fr)_24px_minmax(0,1fr)] max-[380.01px]:grid-cols-[1fr]
          max-[380.01px]:gap-3 grid
        `}>
              <div className={`
          actor [border:1px_solid_#ffffff25] p-[20px_16px] min-w-0 bg-[#191a25] [&_h3]:text-[21px]
          [&_p]:text-(--muted) [&_p]:text-[11px] [&_p]:m-[10px_0_18px] [&_.label]:text-[#b9a5df]
          [&_.label]:text-[9px] max-[1100.01px]:p-[18px_12px] max-[1100.01px]:[&_h3]:text-[19px]
          max-[767.01px]:[&_h3]:text-[17px] max-[767.01px]:p-[18px_12px] max-[767.01px]:[&_p]:text-[11px]
          max-[767.01px]:[&_.label]:text-[8px] [@media((forced-colors:_active))]:[border:1px_solid_CanvasText]
          raphael-actor
        `}>
                <h3>{"Raphael core"}</h3>
                <p>{"Diagnose · propose · publish"}</p>
                <span className={`
          label font-(family-name:--mono) [font-variant-ligatures:none] [font:400_10px/1.7_var(--mono)] uppercase
          tracking-[0.07em] text-(--muted)
        `}>{"Bounded workflow"}</span>
              </div>
              <span
                className={`
          actor-connector flex items-center justify-center text-[#cbb8f5] max-[380.01px]:transform-[rotate(90deg)]
          max-[380.01px]:h-4
        `}
                aria-label="Typed actions and execution results"
              >
                <Icon name="arrows-left-right" className="icon w-[18px] h-[18px] fill-current flex-[0_0_18px] align-middle pointer-events-none " />
              </span>
              <div className={`
          actor [border:1px_solid_#ffffff25] p-[20px_16px] min-w-0 bg-[#191a25] [&_h3]:text-[21px]
          [&_p]:text-(--muted) [&_p]:text-[11px] [&_p]:m-[10px_0_18px] [&_.label]:text-[#b9a5df]
          [&_.label]:text-[9px] max-[1100.01px]:p-[18px_12px] max-[1100.01px]:[&_h3]:text-[19px]
          max-[767.01px]:[&_h3]:text-[17px] max-[767.01px]:p-[18px_12px] max-[767.01px]:[&_p]:text-[11px]
          max-[767.01px]:[&_.label]:text-[8px] [@media((forced-colors:_active))]:[border:1px_solid_CanvasText]
          ignis-actor
        `}>
                <h3>{"Ignis"}</h3>
                <p>{"Reproduce · test · return results"}</p>
                <span className={`
          label font-(family-name:--mono) [font-variant-ligatures:none] [font:400_10px/1.7_var(--mono)] uppercase
          tracking-[0.07em] text-(--muted)
        `}>{"Sandbox executor"}</span>
              </div>
            </div>
            <div className={`
          publish-path flex items-center gap-[10px] flex-wrap text-[11px] [border-top:1px_solid_var(--line)] mt-5
          pt-[18px] [&_.label]:ml-auto [&_.label]:text-[#cfbdf8] max-[380.01px]:[&_.label]:ml-0
        `}>
              <span>{"From Raphael: draft PR + evidence"}</span>
              <Icon name="git-pull-request" className="icon w-[18px] h-[18px] fill-current flex-[0_0_18px] align-middle pointer-events-none review-icon" />
              <span className={`
          label font-(family-name:--mono) [font-variant-ligatures:none] [font:400_10px/1.7_var(--mono)] uppercase
          tracking-[0.07em] text-(--muted)
        `}>{"Review"}</span>
            </div>
          </div>
        </div>
        <details className={`
          boundary-details [border-top:1px_solid_var(--line)] py-[5px] [&_summary]:text-[13px]
          [&_summary_.label]:ml-auto [&_summary_.label]:text-[9px] [&_>_p]:text-[13px] [&_>_p]:leading-[1.8]
          [&_>_p]:text-(--muted) [&_>_p]:max-w-215 [&_>_p]:m-[14px_0_20px] max-[767.01px]:[&_summary]:flex-wrap
          max-[767.01px]:[&_summary]:gap-[6px] max-[767.01px]:[&_summary]:py-[14px]
          max-[767.01px]:[&_summary_.label]:ml-0 max-[767.01px]:[&_summary_.icon]:ml-auto
        `} id="boundaries">
          <summary>
            <span>{"Inspect the execution boundary"}</span>
            <span className={`
          label font-(family-name:--mono) [font-variant-ligatures:none] [font:400_10px/1.7_var(--mono)] uppercase
          tracking-[0.07em] text-(--muted)
        `}>{"Six typed sandbox actions"}</span>
            <Icon name="plus" className={`
          icon w-[18px] h-[18px] fill-current flex-[0_0_18px] align-middle pointer-events-none disclosure-icon
          [&.disclosure-icon]:ml-auto [&.disclosure-icon]:[transition:transform_200ms_ease]
          [details[open]_>_summary_>_&.disclosure-icon]:transform-[rotate(45deg)]
        `} />
          </summary>
          <p>
            {
              "Raphael coordinates the workflow; the separate Ignis executor runs sandbox operations through a typed interface. This is a bounded workflow, not unrestricted shell access."
            }
          </p>
          <ul className={`
          verb-list flex flex-wrap gap-2 p-0 list-none my-5 [&_li]:[border:1px_solid_var(--line)]
          [&_li]:p-[8px_12px] [&_li]:text-[12px]
        `}>
            <li>
              <code>{"create_sandbox"}</code>
            </li>
            <li>
              <code>{"deploy_revision"}</code>
            </li>
            <li>
              <code>{"observe_failure"}</code>
            </li>
            <li>
              <code>{"run_validation"}</code>
            </li>
            <li>
              <code>{"finalize_result"}</code>
            </li>
            <li>
              <code>{"destroy_sandbox"}</code>
            </li>
          </ul>
          <p>
            {
              "Configured live execution and recorded fixture modes are distinct. A recorded result is not proof that a real deployment was tested."
            }
          </p>
        </details>
      </div>
    </section>
  );
}
