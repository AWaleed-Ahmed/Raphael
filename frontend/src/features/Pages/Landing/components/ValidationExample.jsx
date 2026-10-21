"use client";

import { useState } from "react";
import { Icon } from "../../../../components/Brand";
import { validationExamples } from "../data";

export default function ValidationExample() {
  const [outcome, setOutcome] = useState("passing");
  const example = validationExamples[outcome];
  return (
    <article
      className={`validation-panel p-[26px] bg-[#ded9ed] min-w-0 [&_h3]:text-[20px] [&.is-blocked]:bg-[#eee4cd] [&.is-blocked_.icon]:text-[#89521c] max-[767.01px]:p-[22px]${outcome === "blocked" ? " is-blocked" : ""}`}
    >
      <h3>Validation with its limits visible.</h3>
      <div
        className={`
          example-switch flex flex-wrap gap-[6px] mt-[18px] [&_button]:[border:1px_solid_#aaa0be]
          [&_button]:bg-transparent [&_button]:rounded-[3px] [&_button]:p-[8px_11px] [&_button]:min-h-11
          [&_button]:text-[11px] [&_button[aria-pressed='true']]:bg-[#282333]
          [&_button[aria-pressed='true']]:text-[#eeedf3] [&_button[aria-pressed='true']]:border-[#282333]
        `}
        role="group"
        aria-label="Validation example"
      >
        {["passing", "blocked"].map((value) => (
          <button
            key={value}
            data-outcome={value}
            aria-pressed={outcome === value}
            onClick={() => setOutcome(value)}
          >
            {value === "passing" ? "Passing example" : "Blocked example"}
          </button>
        ))}
      </div>
      <ul className={`
          validation-checks list-none p-0 m-[18px_0] [&_li]:flex [&_li]:items-center [&_li]:gap-3 [&_li]:p-[10px_0]
          [&_li]:[border-bottom:1px_solid_#11121a18] [&_li]:text-[13px] [&_li:last-child]:border-0
          [&_.icon]:text-[#496741]
        `} id="validation-checks">
        {example.rows.map(([icon, label]) => (
          <li key={label}>
            <Icon name={icon} />
            <span>{label}</span>
          </li>
        ))}
      </ul>
      <p className="validation-notice text-[12px] mb-[15px] min-h-10 text-[#514c5e]" id="validation-notice" role="status">
        {example.notice}
      </p>
      <p className={`
          label font-(family-name:--mono) [font-variant-ligatures:none] [font:400_10px/1.7_var(--mono)] uppercase
          tracking-[0.07em] text-(--muted)
        `}>
        Illustrative example / not production verification
      </p>
    </article>
  );
}
