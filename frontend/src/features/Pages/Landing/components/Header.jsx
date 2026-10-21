"use client";

import { useEffect, useRef, useState } from "react";
import { Icon, BrandMark } from "../../../../components/Brand";

export default function Header() {
  const [open, setOpen] = useState(false);
  const root = useRef(null);
  const menu = useRef(null);
  useEffect(() => {
    function onKey(event) {
      if (
        event.key === "Escape" &&
        menu.current?.getAttribute("aria-expanded") === "true"
      ) {
        setOpen(false);
        menu.current?.focus();
      }
    }
    function outside(event) {
      if (!root.current?.contains(event.target)) setOpen(false);
    }
    const preference = window.matchMedia("(min-width: 768px)");
    function resize(event) {
      if (event.matches) setOpen(false);
    }
    document.addEventListener("keydown", onKey);
    document.addEventListener("click", outside);
    preference.addEventListener("change", resize);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("click", outside);
      preference.removeEventListener("change", resize);
    };
  }, []);
  return (
    <header ref={root} className={`
          site-header sticky top-0 z-25 min-h-23 flex items-center justify-between gap-7
          [border:1px_solid_transparent] rounded-[999px]
          [transition:min-height_280ms_cubic-bezier(0.2,0.7,0.2,1),transform_280ms_cubic-bezier(0.2,0.7,0.2,1),color_280ms_ease,background-color_280ms_ease,border-color_280ms_ease,box-shadow_280ms_ease]
          [&_nav]:flex [&_nav]:items-center [&_nav]:gap-7 [&_nav]:text-[12px] [&_nav]:ml-auto [&_nav_a]:py-3
          [&_nav_a:hover]:text-(--accent) [&_nav_a[aria-current]]:text-(--accent)
          [&.is-scrolled]:w-[min(760px,calc(100vw-32px))] [&.is-scrolled]:min-h-18 [&.is-scrolled]:px-[18px]
          [&.is-scrolled]:mx-auto [&.is-scrolled]:transform-[translateY(5px)_scale(0.97)]
          [&.is-scrolled]:border-[#ffffff24] [&.is-scrolled]:bg-[#15151ce8]
          [&.is-scrolled]:[box-shadow:0_10px_34px_#07071035]
          [&.is-scrolled]:[backdrop-filter:blur(18px)_saturate(130%)]
          [&.is-scrolled]:[-webkit-backdrop-filter:blur(18px)_saturate(130%)] [&.is-scrolled.is-ink]:text-[#eeedf3]
          [&.is-scrolled.is-light]:text-[#17141f] [&.is-scrolled.is-light]:border-[#17141f1c]
          [&.is-scrolled.is-light]:bg-[#f1eff7e8] [&.is-scrolled.is-light]:[box-shadow:0_10px_34px_#15122220]
          [&.is-scrolled_nav_a]:[transition:color_280ms_ease,opacity_180ms_ease]
          [&.is-scrolled.is-light_nav_a:hover]:text-[#6740b8]
          [&.is-scrolled.is-light_nav_a[aria-current]]:text-[#6740b8]
          [&.is-scrolled.is-light_.button-glass]:text-[#211b2f]
          [&.is-scrolled.is-light_.button-glass]:bg-[#ffffffa8]
          [&.is-scrolled.is-light_.button-glass]:border-[#27203730]
          [&.is-scrolled.is-light_.button-glass]:[box-shadow:inset_0_1px_0_#ffffffb8,0_4px_16px_#08091412]
          [&.is-scrolled.is-light_.button-glass:hover]:text-[#17141f]
          [&.is-scrolled.is-light_.button-glass:hover]:bg-white
          [&.is-scrolled.is-light_.button-glass:hover]:border-[#6740b866]
          [&.is-scrolled.is-light_.button-glass:focus-visible]:text-[#17141f]
          [&.is-scrolled.is-light_.button-glass:focus-visible]:bg-white
          [&.is-scrolled.is-light_.button-glass:focus-visible]:border-[#6740b866]
          [&.is-scrolled.is-light_.menu-toggle]:text-[#17141f] [&.is-scrolled.is-light_.menu-toggle]:bg-[#ffffffa8]
          [&.is-scrolled.is-light_.menu-toggle]:border-[#27203730] max-[1100.01px]:gap-[22px]
          max-[1100.01px]:[&_nav]:gap-5 min-[768px]:max-[900.01px]:[&_nav]:gap-[14px]
          min-[768px]:max-[900.01px]:[&_nav]:text-[11px] min-[768px]:max-[900.01px]:gap-[18px]
          max-[767.01px]:min-h-19 max-[767.01px]:gap-3 max-[767.01px]:[&_nav]:flex max-[767.01px]:[&_nav]:flex-wrap
          max-[767.01px]:[&_nav]:gap-[10px_22px] max-[767.01px]:[&_nav]:p-[12px_0] max-[767.01px]:[&_nav]:ml-0
          max-[767.01px]:[&:not(.js-ready)]:flex-wrap max-[767.01px]:[&:not(.js-ready)_nav]:order-3
          max-[767.01px]:[&:not(.js-ready)_nav]:w-full max-[767.01px]:[&.js-ready]:flex-nowrap
          max-[767.01px]:[&.js-ready_nav]:hidden max-[767.01px]:[&.js-ready_nav]:absolute
          max-[767.01px]:[&.js-ready_nav]:top-[calc(100%+1px)] max-[767.01px]:[&.js-ready_nav]:left-[-10px]
          max-[767.01px]:[&.js-ready_nav]:right-[-10px] max-[767.01px]:[&.js-ready_nav]:p-[16px_20px]
          max-[767.01px]:[&.js-ready_nav]:bg-[#191a25] max-[767.01px]:[&.js-ready_nav]:[border:1px_solid_#ffffff25]
          max-[767.01px]:[&.js-ready_nav]:rounded-[0_0_6px_6px]
          max-[767.01px]:[&.js-ready_nav]:[box-shadow:0_16px_35px_#0005]
          max-[767.01px]:[&.js-ready_nav.is-open]:flex max-[767.01px]:[&.js-ready_nav.is-open]:flex-col
          max-[767.01px]:[&.js-ready_nav.is-open]:items-stretch max-[767.01px]:[&.js-ready_nav.is-open]:gap-0
          max-[767.01px]:[&.js-ready.is-light_nav.is-open]:text-[#17141f]
          max-[767.01px]:[&.js-ready.is-light_nav.is-open]:bg-[#f1eff7f5]
          max-[767.01px]:[&.js-ready.is-light_nav.is-open]:border-[#17141f20]
          max-[767.01px]:[&.js-ready.is-light_nav.is-open]:[box-shadow:0_16px_35px_#15122225]
          max-[767.01px]:[&_.button-glass]:text-[10px] max-[767.01px]:[&_.button-glass]:px-[10px]
          max-[767.01px]:[&_.button-glass]:gap-2 max-[767.01px]:[&_.button-glass_.icon]:w-[15px]
          max-[767.01px]:[&_.button-glass_.icon]:h-[15px] max-[767.01px]:[&_.button-glass_.icon]:basis-[15px]
          max-[380.01px]:gap-2 max-[380.01px]:[&.is-scrolled]:px-[10px]
          [@media((prefers-reduced-motion:_reduce))]:[transition:none] wrap w-[min(1280px,calc(100%-112px))]
          max-[1100.01px]:w-[calc(100%-64px)] max-[767.01px]:w-[calc(100%-40px)] js-ready mx-auto
        `}>
      <span className="header-intro-pill" aria-hidden="true" />
      <a className="wordmark inline-flex items-center gap-[11px] shrink-0 max-[767.01px]:gap-[10px] max-[380.01px]:gap-2" href="#" aria-label="Raphael home">
        <BrandMark />
        <span className={`
          brand-name [font:500_34px/1.15_'Telma',var(--display)] tracking-tight whitespace-nowrap
          min-[768px]:max-[900.01px]:text-[31px] max-[767.01px]:text-[31px] max-[380.01px]:text-[28px]
        `} aria-hidden="true">
          {"raphael"}
        </span>
      </a>
      <nav
        className={open ? "is-open" : ""}
        onClick={(event) => {
          if (event.target.closest("a")) setOpen(false);
        }}
        id="site-nav"
        aria-label="Main navigation"
      >
        <a href="#repair">{"How it works"}</a>
        <a href="#architecture">{"The architecture"}</a>
        <a href="#safety">{"Safety"}</a>
      </nav>
      <div className="header-actions flex items-center gap-2">
        <a className={`
          button inline-flex items-center justify-center gap-[22px] min-h-[46px] p-[13px_20px]
          [border:1px_solid_transparent] rounded-[3px] bg-(--accent) text-(--night) [font:500_13px/1.4_var(--sans)]
          [transition:background-color_180ms_ease,border-color_180ms_ease,box-shadow_180ms_ease]
          [&:hover]:bg-[#d1beff] [@media((forced-colors:_active))]:[border:1px_solid_CanvasText] button-glass
          [&.button-glass]:bg-[#262333] [&.button-glass]:text-[#eeedf3] [&.button-glass]:border-[#ddd2ff40]
          [&.button-glass]:rounded-[6px] [&.button-glass]:min-h-11 [&.button-glass]:p-[10px_15px]
          [&.button-glass]:gap-[14px] [&.button-glass]:text-[12px]
          [&.button-glass]:[box-shadow:inset_0_1px_0_#ffffff12,0_4px_16px_#08091420]
          [&.button-glass:hover]:bg-[#393044] [&.button-glass:hover]:border-[#ddd2ff80]
          [&.button-glass:hover]:text-white
          [&.button-glass:hover]:[box-shadow:inset_0_1px_0_#ffffff20,0_4px_20px_#08091435]
          [&.button-glass:focus-visible]:bg-[#393044] [&.button-glass:focus-visible]:border-[#ddd2ff80]
          [&.button-glass:focus-visible]:text-white
          [&.button-glass:focus-visible]:[box-shadow:inset_0_1px_0_#ffffff20,0_4px_20px_#08091435]
          supports-[((backdrop-filter:_blur(12px))_or_(-webkit-backdrop-filter:_blur(12px)))]:[&.button-glass]:bg-[#262333b8]
          supports-[((backdrop-filter:_blur(12px))_or_(-webkit-backdrop-filter:_blur(12px)))]:[&.button-glass]:[backdrop-filter:blur(12px)_saturate(125%)]
          supports-[((backdrop-filter:_blur(12px))_or_(-webkit-backdrop-filter:_blur(12px)))]:[&.button-glass]:[-webkit-backdrop-filter:blur(12px)_saturate(125%)]
          supports-[((backdrop-filter:_blur(12px))_or_(-webkit-backdrop-filter:_blur(12px)))]:[&.button-glass:hover]:bg-[#393044d1]
          supports-[((backdrop-filter:_blur(12px))_or_(-webkit-backdrop-filter:_blur(12px)))]:[&.button-glass:focus-visible]:bg-[#393044d1]
          min-[768px]:max-[900.01px]:[&.button-glass]:text-[11px] min-[768px]:max-[900.01px]:[&.button-glass]:gap-2
          min-[768px]:max-[900.01px]:[&.button-glass]:px-3 max-[380.01px]:[&.button-glass_.icon]:w-[14px]
          max-[380.01px]:[&.button-glass_.icon]:h-[14px] max-[380.01px]:[&.button-glass_.icon]:basis-[14px]
        `} href="/console/" aria-label="Open demo console">
          <span>
            {"Open demo"}
            <span className="cta-full max-[420.01px]:hidden">{" console"}</span>
          </span>
          <Icon name="arrow-up-right" className="icon w-[18px] h-[18px] fill-current flex-[0_0_18px] align-middle pointer-events-none" />
        </a>
        <button
          ref={menu}
          className={`
          menu-toggle hidden [border:1px_solid_var(--line)] bg-[#262333] rounded-[6px] items-center justify-center
          min-h-11 w-11 p-0 max-[767.01px]:in-[.js-ready]:flex max-[767.01px]:in-[.js-ready]:text-[0px]
        `}
          aria-expanded={open}
          aria-controls="site-nav"
          onClick={() => setOpen((previous) => !previous)}
        >
          {open ? "Close " : "Menu "}
          <Icon name={open ? "minus" : "plus"} className="icon w-[18px] h-[18px] fill-current flex-[0_0_18px] align-middle pointer-events-none" />
        </button>
      </div>
    </header>
  );
}
