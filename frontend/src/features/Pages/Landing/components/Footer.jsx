"use client";

import SectionNotch from "./SectionNotch";
import { useMotion } from "../hooks/useMotion";
import { Icon, BrandMark } from "../../../../components/Brand";

export default function Footer() {
  const { reduced, systemReduced, toggle } = useMotion();
  return (
    <footer className={`
          landing-folder site-footer p-[45px_0_28px] [border-top:1px_solid_var(--line)] bg-[#0e0f16] max-[767.01px]:py-[35px_25px]
          dark-section
        `} data-nav-theme="ink">
      <SectionNotch variant="footer" />
      <div className={`
          wrap w-[min(1280px,calc(100%-112px))] max-[1100.01px]:w-[calc(100%-64px)]
          max-[767.01px]:w-[calc(100%-40px)] footer-main flex items-start justify-between gap-10
          [&_p]:text-(--muted) [&_p]:text-[12px] [&_p]:mt-[18px] [&_nav]:flex [&_nav]:flex-wrap
          [&_nav]:gap-[18px_28px] [&_nav]:text-[12px] [&_nav]:pt-[10px] [&_nav_a:hover]:text-(--accent)
          max-[767.01px]:block max-[767.01px]:[&_nav]:mt-[22px] max-[767.01px]:[&_nav]:gap-[16px_24px] mx-auto
        `}>
        <div>
          <a className="wordmark inline-flex items-center gap-[11px] shrink-0 max-[767.01px]:gap-[10px] max-[380.01px]:gap-2" href="#" aria-label="Raphael home">
            <BrandMark />
            <span className={`
          brand-name [font:500_34px/1.15_'Telma',var(--display)] tracking-tight whitespace-nowrap
          min-[768px]:max-[900.01px]:text-[31px] max-[767.01px]:text-[31px] max-[380.01px]:text-[28px]
        `} aria-hidden="true">
              {"raphael"}
            </span>
          </a>
          <p>{"Deployment repair. With evidence."}</p>
        </div>
        <nav aria-label="Footer navigation">
          <a href="#repair">{"The repair"}</a>
          <a href="#architecture">{"Architecture"}</a>
          <a href="#safety">{"Safety"}</a>
          <a href="/console/">
            {"Operator console "}
            <Icon name="arrow-up-right" className="icon w-[18px] h-[18px] fill-current flex-[0_0_18px] align-middle pointer-events-none " />
          </a>
        </nav>
      </div>
      <div className={`
          wrap w-[min(1280px,calc(100%-112px))] max-[1100.01px]:w-[calc(100%-64px)]
          max-[767.01px]:w-[calc(100%-40px)] footer-bottom flex items-center flex-wrap gap-5 pt-[23px]
          [border-top:1px_solid_var(--line)] mt-10 [&_>_.label]:mr-auto [&_>_.label]:text-[9px]
          max-[767.01px]:gap-4 max-[767.01px]:mt-7 max-[767.01px]:[&_>_.label]:order-3
          max-[767.01px]:[&_>_.label]:basis-full mx-auto
        `}>
        <button
          className={`
          motion-toggle [border:1px_solid_#ffffff30] rounded-[3px] bg-transparent text-(--muted) p-[8px_12px]
          min-h-11 [font:10px_var(--mono)] disabled:cursor-default
        `}
          type="button"
          aria-pressed={reduced}
          disabled={systemReduced}
          aria-label={
            systemReduced
              ? "Reduced motion is enabled in your system settings"
              : "Reduce page motion"
          }
          onClick={toggle}
        >
          {systemReduced
            ? "Motion: reduced by system"
            : `Motion: ${reduced ? "off" : "on"}`}
        </button>
        <span className={`
          label font-(family-name:--mono) [font-variant-ligatures:none] [font:400_10px/1.7_var(--mono)] uppercase
          tracking-[0.07em] text-(--muted)
        `}>{"Raphael / Deployment intelligence"}</span>
        <a className="back-top flex items-center gap-[10px] text-[11px] text-(--muted) max-[767.01px]:ml-auto" href="#main">
          {"Back to top "}
          <Icon name="arrow-up" className="icon w-[18px] h-[18px] fill-current flex-[0_0_18px] align-middle pointer-events-none " />
        </a>
      </div>
    </footer>
  );
}
