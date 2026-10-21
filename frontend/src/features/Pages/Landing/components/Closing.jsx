import SectionNotch from "./SectionNotch";
import { Icon } from "../../../../components/Brand";

export default function Closing() {
  return (
    <section
      className={`
          landing-folder closing p-[72px_0_78px] bg-[radial-gradient(ellipse_at_85%_110%,#373043,transparent_65%),#11121a]
          [&_h2]:col-1 [&_h2]:row-[span_2] [&_h2]:text-[clamp(42px,4.6vw,64px)] [&_h2_em]:text-[#cbb8f5]
          [&_.button]:[justify-self:start] [&_.button]:mt-[22px] max-[767.01px]:p-[55px_0_60px]
          max-[767.01px]:[&_h2]:text-[44px] max-[767.01px]:[&_.button]:mt-6
        `}
      data-nav-theme="ink"
      aria-labelledby="closing-title"
    >
      <SectionNotch variant="closing" />
      <div className={`
          wrap w-[min(1280px,calc(100%-112px))] max-[1100.01px]:w-[calc(100%-64px)]
          max-[767.01px]:w-[calc(100%-40px)] closing-inner grid grid-cols-[minmax(0,1fr)_minmax(0,0.75fr)]
          [align-items:end] gap-x-15 [&_>_.label]:col-span-full [&_>_.label]:mb-5
          [&_>_p:not(.label)]:text-(--muted) [&_>_p:not(.label)]:max-w-[350px]
          [&_>_p:not(.label)]:text-[14px] max-[767.01px]:block max-[767.01px]:[&_>_p:not(.label)]:mt-[22px]
          mx-auto
        `}>
        <p className={`
          label font-(family-name:--mono) [font-variant-ligatures:none] [font:400_10px/1.7_var(--mono)] uppercase
          tracking-[0.07em] text-(--muted)
        `}>{"Built for the moment after the alert."}</p>
        <h2 id="closing-title">
          {"Less firefighting."}
          <br />
          <em>{"More forward."}</em>
        </h2>
        <p>
          {"Explore a sample investigation in the demo console, from the failure signal to the proposed repair."}
        </p>
        <a className={`
          button inline-flex items-center justify-center gap-[22px] min-h-[46px] p-[13px_20px]
          [border:1px_solid_transparent] rounded-[3px] bg-(--accent) text-(--night) [font:500_13px/1.4_var(--sans)]
          [transition:background-color_180ms_ease,border-color_180ms_ease,box-shadow_180ms_ease]
          [&:hover]:bg-[#d1beff] [@media((forced-colors:_active))]:[border:1px_solid_CanvasText] button-primary
        `} href="/console/">
          {"Open the demo console "}
          <Icon name="arrow-up-right" className="icon w-[18px] h-[18px] fill-current flex-[0_0_18px] align-middle pointer-events-none " />
        </a>
      </div>
    </section>
  );
}
