export function Icon({ name, className = "icon w-[18px] h-[18px] fill-current [flex:0_0_18px] align-middle pointer-events-none" }) {
  return (
    <svg
      className={className}
      viewBox="0 0 256 256"
      aria-hidden="true"
      focusable="false"
    >
      <use href={`/icons.svg#${name}`} />
    </svg>
  );
}
export function BrandMark() {
  return (
    <svg className={`
          brand-mark w-[38.4px] h-[33.6px] fill-current shrink-0 max-[767.01px]:w-[33.6px]
          max-[767.01px]:h-[31.2px] max-[380.01px]:w-[28.8px] max-[380.01px]:h-[28.8px]
        `} viewBox="0 0 600 400" aria-hidden="true">
      <path d="M300 0C295 75 283 117 243 143C286 174 279 228 300 398C321 228 314 174 357 143C317 117 305 75 300 0Z"></path>
      <path d="M7 0C62 70 146 77 198 114C235 141 250 188 256 273C212 174 159 174 84 134C39 110 12 68 7 0Z"></path>
      <path d="M64 146C115 184 159 182 199 218C235 250 254 301 272 370C220 292 179 294 119 248C88 225 69 190 64 146Z"></path>
      <path d="M593 0C538 70 454 77 402 114C365 141 350 188 344 273C388 174 441 174 516 134C561 110 588 68 593 0Z"></path>
      <path d="M536 146C485 184 441 182 401 218C365 250 346 301 328 370C380 292 421 294 481 248C512 225 531 190 536 146Z"></path>
    </svg>
  );
}
