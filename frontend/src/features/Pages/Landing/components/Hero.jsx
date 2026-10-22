import { Icon } from "../../../../components/Brand";

export default function Hero() {
  return (
    <>
      <div className="cloud-chapter relative">
        <picture
          className={`
          cloud-art absolute top-[-92px] left-0 w-full h-[calc(100%+92px)] pointer-events-none [&_img]:w-full
          [&_img]:h-full [&_img]:object-cover [&_img]:object-center [&_img]:opacity-[0.76] [&::after]:[content:'']
          [&::after]:absolute [&::after]:inset-0
          [&::after]:bg-[linear-gradient(90deg,#11121a80,#11121a18_58%,transparent_82%),linear-gradient(0deg,#11121a_0%,transparent_26%,transparent_82%,#11121a35)]
          max-[767.01px]:top-[-76px] max-[767.01px]:h-[calc(100%+76px)] max-[767.01px]:[&_img]:object-[44%_center]
          max-[767.01px]:[&::after]:bg-[linear-gradient(90deg,#11121a99,#11121a30),linear-gradient(0deg,#11121a,transparent_34%)]
          [@media((forced-colors:_active))]:hidden
        `}
          aria-hidden="true"
        >
          <img
            src="/images/clouds-detailed-1672.webp"
            srcSet="/images/clouds-detailed-640.webp 640w, /images/clouds-detailed-1280.webp 1280w, /images/clouds-detailed-1672.webp 1672w"
            sizes="100vw"
            width="1672"
            height="941"
            alt=""
            fetchPriority="high"
          />
        </picture>
        <section
          className={`
          hero relative min-h-[max(540px,calc(100svh-240px))] flex flex-col items-center justify-center text-center p-[48px_0_54px]
          max-[767.01px]:min-h-145 max-[767.01px]:p-[50px_0_42px] max-[767.01px]:justify-start
          max-[767.01px]:[&_.button]:text-[12px] wrap w-[min(1280px,calc(100%-112px))]
          max-[1100.01px]:w-[calc(100%-64px)] max-[767.01px]:w-[calc(100%-40px)] mx-auto
        `}
          aria-labelledby="hero-title"
        >
          <div
            className={`
          hero-copy max-w-[650px] flex flex-col items-center [&_>_.eyebrow]:flex
          [&_>_.eyebrow]:items-center [&_>_.eyebrow]:justify-center [&_>_.eyebrow]:gap-[10px]
          max-[1100.01px]:max-w-155 max-[767.01px]:[&_>_.eyebrow]:text-[9px]
        `}
          >
            <h1
              id="hero-title"
              className="text-[clamp(52px,5.2vw,76px)] leading-[1.09] tracking-[-0.032em] mt-[18px] mb-[25px] max-[1100.01px]:text-[clamp(54px,6.2vw,68px)] max-[767.01px]:text-[clamp(42px,10.8vw,64px)] max-[767.01px]:leading-[1.13] max-[767.01px]:mt-[17px] max-[767.01px]:mb-6"
            >
              <span className="hero-line block">
                <span className="gsap-word inline-block">Clarity</span>
                {"\u00a0"}
                <span className="gsap-word inline-block">after</span>
              </span>
              <span className="hero-line block">
                <span className="gsap-word inline-block">a</span>
                {"\u00a0"}
                <span className="gsap-word inline-block">failed</span>
                {"\u00a0"}
                <span className="gsap-word inline-block">deploy.</span>
              </span>
            </h1>
            <p className="hero-description text-[#c3c1d1] max-w-[475px] text-[16px] leading-[1.75] max-[767.01px]:text-[15px]">
              {
                "Raphael investigates Kubernetes failures, tests a narrow repair in isolation, and prepares a draft pull request for your team to review."
              }
            </p>
            <div className="actions flex flex-wrap items-center justify-center gap-[23px] mt-[29px] max-[767.01px]:gap-[18px]">
              <a
                className={`
          button inline-flex items-center justify-center gap-[22px] min-h-[46px] p-[13px_20px]
          [border:1px_solid_transparent] rounded-[3px] bg-(--accent) text-(--night) [font:500_13px/1.4_var(--sans)]
          [transition:background-color_180ms_ease,border-color_180ms_ease,box-shadow_180ms_ease]
          [&:hover]:bg-[#d1beff] [@media((forced-colors:_active))]:[border:1px_solid_CanvasText] button-primary
        `}
                href="#example"
              >
                {"See the handoff "}
                <Icon
                  name="arrow-down"
                  className="icon w-[18px] h-[18px] fill-current flex-[0_0_18px] align-middle pointer-events-none"
                />
              </a>
              <a
                className={`
          text-link inline-flex items-center gap-[10px] py-[9px] text-[12px] underline-offset-[5px]
          [&:hover]:underline
        `}
                href="#safety"
              >
                {"Read the safety model "}
                <Icon
                  name="arrow-up-right"
                  className="icon w-[18px] h-[18px] fill-current flex-[0_0_18px] align-middle pointer-events-none"
                />
              </a>
            </div>
            <p className="hero-note text-[#bab6cb] text-[12px] mt-5 max-[767.01px]:text-[12px]">
              {"Production stays read-only. Your team decides what ships."}
            </p>
          </div>
        </section>
      </div>
    </>
  );
}
