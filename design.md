# Raphael brand and web design direction

## Cloud typography study — October 5, 2026

The latest `/direction/` concept uses the user's supplied illustrated night
clouds. The user selected the detailed `image.png` hero with reduced opacity.
Render it at 76% opacity over the night canvas, with extra shading on the text
side and a stronger mobile overlay. The original artwork retains its colors;
readability is controlled through CSS rather than editing the source image.

Use **Sentient 400** for large statements, **Switzer 400–500** for reading and
controls, and **IBM Plex Mono 400** for exact evidence. This takes the serif/sans
hierarchy from the Railway reference and interprets it with Fontshare families.
The user approved Sentient headings; the artwork/type comparison controls
have been removed. The sky is static; native scrolling and reduced-motion
preferences remain intact.

The lowercase Raphael wordmark uses **Telma 500**, whose sharp calligraphic
terminals and flowing strokes relate to the supplied winged logo. Keep this
expressive face in the wordmark; the product UI continues to use Switzer.
Explore Raphael uses smoked-violet glass with a quiet highlight, readable pearl
type, keyboard focus, and an opaque fallback when backdrop blur is unavailable.

The public landing page now uses this direction. Its navigation borrows Oryns'
surface-aware pill behavior: it begins transparent over the cloud hero, settles
into a centered frosted capsule on scroll, and crossfades between ink and pearl
surfaces as light and dark chapters pass beneath it. The movement uses native
CSS and section-aware scroll state; it does not replace or intercept scrolling.

The palette is night `#11121A`, cloud `#242335`, pearl `#EEEDF3`, and restrained
violet `#BDA4FF`. Responsive artwork fades into the canvas; evidence stays on
flat surfaces, with a light handoff chapter providing a change of pace. The
The console retains its existing implementation. This is the active landing
direction, following the accepted Pixel Sentinel study below. Details and
verification: `docs/design/cloud-study.md`.

## Earlier accepted pixel direction — October 5, 2026

The user rejected Signal & Splendor's blue/brass colors and preferred Tester's
pixel art, while also liking Railway's color and layout. **Pixel Sentinel** is
the earlier study: neutral charcoal `#151515`, chalk `#F1F1ED`,
graphite `#252525`, and soft violet `#BDA4FF`. Violet is a restrained accent,
not a requirement to copy Tester's orange. The pixel treatment of the supplied
winged mark is the hero's artwork; technical surfaces remain flat and readable.

Use Fontshare's Cabinet Grotesk 700–800 for compact display headings, Switzer
400–500 for reading/UI, and IBM Plex Mono for evidence. The flow is an asymmetric
hero, three concise repair stages, a light draft/evidence chapter, and the
design board. The original landing/console have not been migrated. This section
supersedes the proposal immediately below. Details: `docs/design/pixel-sentinel.md`.

## Proposed next direction — October 5, 2026

**Recommendation: Signal & Splendor.** A midnight-blue/silver foundation,
glacier blue, and restrained brass, with original abstract ascending ribbon
artwork that relates to the user's winged logo. Boska 500 from Fontshare carries
large statements; Switzer 400–500 carries reading and UI; IBM Plex Mono carries
exact evidence. This supersedes the earlier restriction to green/paper as a
design recommendation. The existing landing page still uses that earlier theme.

The browsable concept at `/direction/` compares sculptural, pixel, and ASCII
background treatments. Full research, references, typography, palette, and
section plan: `docs/design/signal-and-splendor.md`. Railway informs atmosphere;
Inngest informs technical clarity. Gabriel's silver/gold/blue qualities are an
abstract material reference. Keep the supplied Raphael logo and the documented
product/permission model. The main page has not yet been migrated to this study.

## Landing refinement — October 3, 2026

The public landing page now leads with a more compact hero and one unified
illustrative repair workspace. The dark repair chapter is an interactive
five-step inspection: its evidence, scope, and result change with the selected
step. Mobile presents the same steps in a legible two-row selector above the
active inspection. The final page keeps the alternating image, architecture,
and human-review compositions.

Motion is opt-in by interaction for the walkthrough. Short entrance and
disclosure transitions accompany native scrolling; the footer provides a
persistent motion preference, and OS reduced-motion settings take priority.
The page remains readable before scripts execute. Do not add scroll-jacking,
unverified product claims, invented customer proof, or production-write actions.

The audit, reference interpretation, motion rules, and verification are in
`docs/design/landing-refinement-october.md`.

## Implemented refinement — September 19, 2026

This section supersedes earlier typography, logo, section-color, and motion
recommendations below. The product and permission model remain unchanged.

- **Typography:** locally hosted Instrument Sans variable (400–700) for headings,
  copy, and UI; IBM Plex Mono 400 for evidence and metadata; Newsreader italic
  for brief editorial emphasis only. Keep the hero sans-serif. Use 450 display
  weight, approximately 40–96px responsive hero type, 39–66px chapter headings,
  16–19px lead/body copy, and 12–15px artifact detail. Tight display tracking must
  relax on mobile; never apply display tracking to paragraphs or code.
- **Palette:** paper `#f5f4ee`, ink `#192c25`, forest `#10241c`, moss `#547451`,
  blueprint blue `#dce8ed`, clay `#eadacc`, and pale citron `#e5edc9`.
  Blue identifies the architectural explanation; clay supports human review;
  green continues to anchor the brand and validation. Status must always have
  a text label in addition to color.
- **Logo:** use the user's wing-and-central-spear mark, reconstructed as SVG.
  Preserve its geometry; dark on light surfaces, light on dark surfaces.
- **Iconography:** Phosphor Light, served from a small local SVG sprite. Use
  18–25px icons with consistent weight. No emoji or Unicode substitutes for
  buttons, disclosure affordances, replay states, or diagram connectors.
  Mathematical/code notation stays selectable text.
- **Page rhythm:** spacious centered desktop hero; left-aligned mobile hero;
  forest product scene; dark asymmetric repair chapter; image-led evidence
  gallery; blue architecture plate; clay draft beside numbered review
  principles; broad split closing statement. Avoid repeating a single grid.
- **Motion:** native scrolling and smooth anchor links, a quiet progress line,
  short one-time entrance animations, and deliberate button/disclosure
  feedback. No wheel interception, mandatory animation, pinned-scroll story,
  auto-playing workflow, or content hidden until JavaScript runs. Respect
  reduced motion for scrolling, reveals, and replay.
- **Assets:** fonts, images, SVG sprite, and licenses ship locally. Asset
  provenance and evaluation are in `docs/design/typography-audit.md`.

Implementation: `frontend/src/editorial.css` defines the editorial layer on the
existing layout; `frontend/src/icons.js` keeps dynamic SVG controls consistent.
The operator console retains its separate entry point and styling.

**Status:** recommended foundation for the marketing site, product UI, and Ignis companion site
**Decision:** adopt **The Quiet Guardian** — an editorial, evidence-led infrastructure brand. It is a warm-paper / deep-forest system with a small amount of directional, abstract landscape motion. It should feel like a careful platform engineer's field notebook, not a generic AI dashboard or a fantasy game site.

## 1. What Raphael needs to communicate

Raphael observes a failed delivery, gathers evidence, reproduces the failure in an isolated sandbox, validates the smallest safe repair, and opens a reviewable PR. It never writes to production in the MVP. That makes the brand promise:

> **A calm, inspectable path from failed deployment to reviewed fix.**

The visual tension is intentional:

| Raphael quality | Visual expression |
| --- | --- |
| Evidence before action | Sources, trace lines, command fragments, and confidence states are legible rather than hidden. |
| Safe, human-controlled delivery | Quiet surfaces, clear gates, and restrained animation. No “agent magic” theatrics. |
| Movement through a complex system | Slow directional currents and a visible five-stage pipeline. |
| Isolation and repeatability | Deliberate frames, bounded panels, exact status labels, and plenty of empty space. |
| An intelligent guardian | An original abstract sentinel mark—not a literal character or a mascotted robot. |

## 2. The direction to choose

### The Quiet Guardian

Use a **warm mineral light mode as Raphael’s primary marketing mode**, with deep forest-black “evidence rooms” for the workflow, product walkthrough, and CTA. The visual language is editorial and technical at once:

- Pale paper makes the product feel calm and credible instead of neon-AI or SOC-dashboard aggressive.
- Deep forest-black carries operational seriousness without defaulting to blue-black cyberpunk.
- Desaturated blue-green long-exposure imagery supplies the sense of current, investigation, and movement suggested by the supplied references.
- A single ember note belongs to **Ignis**, the isolated sandbox executor. It must not become a generic orange SaaS CTA color throughout Raphael.

This is **not** a Greek/Renaissance theme. The supplied Structured reference has useful materiality, typography, and alternating dark/light galleries, but its classical paintings and monumental serif would make a Kubernetes product feel like crypto/finance or a museum. Do not use columns, marble busts, laurel wreaths, Greek keys, oil paintings, armor, halos, or Roman numerals as decoration.

Use “sacred” only as an invisible design quality: symmetry, restraint, a watchful vertical mark, and light passing through a system. The product remains a contemporary developer tool.

## 3. Reference board

Study the *principles*, not the exact compositions or assets.

| Reference | Borrow | Avoid | Why it is relevant |
| --- | --- | --- | --- |
| [Revolte](https://revolte.ai/) | Its narrative makes the agentic loop visible and pairs automation with governance language. The animated loop is a strong model for Raphael’s `Detect → Investigate → Reproduce → Validate → PR` story. | Its broad “entire SDLC” scope and busy full-page motion. Raphael needs a tighter, more forensic story. | Closest product-category reference. |
| [Structured / Refero](https://styles.refero.design/style/6c0b77d3-71f9-469d-98aa-4ce1d6d76ac8) | Warm putty paper, black rooms, hairline structure, high-quality display type, and flat tonal depth. | Classical art, the giant 374px wordmark, and finance-gallery cues. | This is the right emotional starting material, but not the right literal art direction. |
| [SST / Refero](https://styles.refero.design/style/19f92be1-65ac-4432-a82b-0aa1e685d97d) | Treat a truthful technical artifact—an evidence log or diff—as hero imagery. | Making the whole page look like a terminal. | Raphael earns trust through real operational detail. |
| [Oxide Computer Company / Refero](https://styles.refero.design/style/b721fa94-72e6-49ad-a9bc-bab3d075f19c) | Small mono labels, thin lines, status color used as signal rather than decoration. | A permanently dark data-center aesthetic and saturated green everywhere. | Excellent language for the product’s operational layer. |
| [Tailscale / Refero](https://styles.refero.design/style/5b679fb6-8d53-402d-a77b-c88bfb397623) | A warm paper-grounded infrastructure product that stays approachable. | One large, highly saturated brand color. | Good benchmark for friendly, serious developer tooling. |
| [Mesh / Refero](https://styles.refero.design/style/1a03b8d7-9204-4c16-ad3c-16306f99fba9) | A dark editorial section can feel considered and information-dense without cards and gradients. | Its amber-led visual identity. | Useful for the “evidence room” tone. |

### References to reject

- Neon grids, floating glassmorphism, purple gradients, starscapes, animated code rain, and a chatbot-orb hero. They over-promise autonomy and make auditability feel secondary.
- Literal angel/gaming imagery. It makes the product look like fan art and risks unwanted association with *ULTRAKILL*.
- A fully Greek theme. It does not connect to deployment remediation, and it will age poorly once the user enters the actual product.

## 4. Brand architecture

**Raphael** is the customer-facing remediation agent: composed, observant, and evidence-first.

**Ignis** is a Raphael component, not a competing consumer brand: the local/customer-controlled sandbox executor. Its identity is warmer and more contained.

Use this relationship consistently:

```text
RAPHAEL                  Detect · investigate · propose · validate · open PR
  └── IGNIS              Isolated sandbox executor
      └── result         Bounded, typed validation evidence
```

- First mention: **Ignis — the Raphael sandbox executor**.
- In the Raphael UI, name it `IGNIS SANDBOX`, with a small ember status dot only when a sandbox is actually running.
- Do not give Ignis a separate marketing voice, separate logo family, or its own palette beyond the ember token.

## 5. Logo system

### Recommended mark: the Sentinel

Create an original, geometric vertical mark composed of two mirrored, open strokes that lean toward a narrow central spine. At small sizes it reads as an `R`-adjacent trace or an observed signal; at larger sizes it can suggest a calm, wing-like guardian without containing a face, halo, weapon, or character silhouette.

The central spine represents an evidence trail. The two outer strokes represent the two bounded worlds Raphael connects: production observation and isolated validation. A small break/pivot in the lower right can subtly form an `R` without forcing a monogram.

**Important:** do not trace, emulate, or use a silhouette of Gabriel from *ULTRAKILL*. The prompt can be “abstract protective symmetry, vertical signal, two restrained wing-like arcs,” but the final geometry must be freshly drawn and recognizably Raphael’s own.

### Mark rules

- Default: Forest Ink on Paper; reverse to Paper on Night.
- Use one color only. No gradient, glow, feathers, or illustration inside the mark.
- The mark is 20–24px in the navigation and 48–64px only for a hero seal or empty state.
- Clear space: at least the width of the central spine on all sides.
- Ignis uses the same geometric DNA, but splits the central spine into a small upward ember/chevron. Never use a flame clip-art icon.

## 6. Color system

The supplied long-exposure landscapes are a good reference for temperature and movement. The palette should feel pulled from overcast water, moss, cloud, and a small furnace ember.

```css
:root {
  /* Raphael foundation */
  --r-paper: #f4f4ed;       /* default marketing canvas */
  --r-bone: #e5e5da;        /* secondary section / quiet fill */
  --r-mist: #cbd2cb;        /* inset surface / inactive diagram line */
  --r-lichen: #8d9a85;      /* decorative landscape tint only */
  --r-ink: #18201b;         /* primary text and strong rules */
  --r-forest: #2f604b;      /* focus, link, active-but-not-success */
  --r-night: #101612;       /* dark evidence room */
  --r-night-raised: #172019;/* code/evidence panel on night */
  --r-paper-on-night: #eef1e9;

  /* Semantic operational colors — never use as broad decoration */
  --r-verified: #3f7657;
  --r-attention: #b66d2e;
  --r-risk: #b64f4a;
  --r-info: #506f89;

  /* Ignis-only warmth */
  --i-ember: #c7613f;
  --i-ember-pale: #f0d2c5;
}
```

### Color behavior

- The page should be roughly **70% Paper/Bone, 20% Night, 8% neutral structure, and 2% semantic color**.
- `--r-forest` is a functional signal (focused, selected, verified link), not an entire section background.
- Green must not solely communicate success; pair every status with a text label and icon.
- `--i-ember` means “Ignis is executing inside the sandbox.” It never means “danger,” “delete,” or the global primary button.
- Primary buttons are Ink/Night with Paper text. This preserves the seriousness of a product that must not appear to “go rogue.”

## 7. Typography

### Selected system: one shifting family, then evidence

Use **ABC Arizona** as the brand family and let its related forms move from expressive to functional: **Arizona Flare** for the voice, **Arizona Sans** for the interface. Pair it with **Commit Mono** for unambiguous evidence. This has character without turning a deployment product into fashion editorial or a generic “modern SaaS” site.

Arizona is particularly right for Raphael because it is a sans-to-serif superfamily: the public site can feel human and atmospheric, while the product UI retains the same underlying DNA in a practical sans. That continuity is much more distinctive than pairing an editorial font with a default startup sans.

| Role | Family | Weights / usage |
| --- | --- | --- |
| Brand / display voice | **ABC Arizona Flare** | Light or Regular only. Hero, major section statements, and a rare pull-quote; 56–88px desktop, 42–56px mobile. It is the calm, slightly otherworldly Raphael voice. |
| UI + body | **ABC Arizona Sans** | Regular and Medium. Navigation, paragraphs, buttons, feature titles, controls, and dashboard UI. Its geometry retains the brand family without asking the display face to do operational work. |
| Evidence + metadata | **Commit Mono** | 400–500. Run IDs, sources, paths, confidence, timestamps, diff/evidence blocks, and stage labels. It is crisp, deliberately neutral, and released under the SIL Open Font License. |

```css
:root {
  --font-display: "ABC Arizona Flare", "Iowan Old Style", serif;
  --font-sans: "ABC Arizona Sans", "Helvetica Neue", sans-serif;
  --font-mono: "Commit Mono", "SFMono-Regular", Consolas, monospace;

  --text-display: clamp(3.5rem, 8vw, 6.5rem);
  --text-h1: clamp(2.6rem, 5vw, 4.75rem);
  --text-h2: clamp(2rem, 3.5vw, 3.25rem);
  --text-body: 1rem;
  --text-meta: 0.75rem;
}
```

### How it should look

- **Arizona Flare** is restrained, not theatrical: use it at Light/Regular, in sentence case, with a tight `0.95–1` line-height and `-0.02em` tracking. It should feel like light changing across a landscape, not like a Renaissance title page.
- **Arizona Sans** should run the functional layer at Regular; use Medium only for navigation, buttons, selected states, and short feature titles. Use tabular numerals (`font-variant-numeric: tabular-nums`) for run IDs, durations, percentages, and confidence values.
- **Commit Mono** is never body copy. Use it for short, factual labels and evidence. Disable discretionary ligatures in code/diff surfaces if they obscure exact characters.
- Use normal sentence case for almost everything. Technical section eyebrows may be Commit Mono uppercase with `0.08em` tracking.
- Never use faux-Greek display typefaces, Trajan, Cinzel, blackletter, or a “futuristic” sci-fi face.

### Licensing and loading

ABC Arizona is a commercial Dinamo family; buy the appropriate web/app license before shipping its WOFF2 files. Do not take its files from another site or a trial package. Commit Mono is open-source, but still self-host a version-pinned copy and retain its OFL notice.

Subset the web fonts to the weights actually used: Arizona Flare Light + Regular, Arizona Sans Regular + Medium, and Commit Mono Regular + Medium. This protects the page’s load performance and preserves the deliberate typographic hierarchy.

### Two good alternates to test before purchase

1. **Diatype + Diatype Mono** (Dinamo) with Arizona Flare retained for display: the sharpest, most technical variation. Use this if the product console becomes very dense or highly multilingual; Diatype was made for screen reading and has matching mono styles.
2. **PP Editorial New + PP Neue Montreal** (Pangram Pangram) with Commit Mono: softer and more luxurious, but less ownable for Raphael because the pairing is common in contemporary editorial SaaS. Use only if the visual identity is intentionally more art-directed than operator-led.

## 8. Visual assets and imagery

### Use the blurred nature direction—under these constraints

Yes: treat it as **operational atmosphere**, not as stock lifestyle photography. The provided long-exposure, blue-green landscape references are the preferred image direction. They imply a signal moving through a living system and give the brand a tactile counterweight to logs and manifests.

Image brief:

- Long-exposure coastal water, wind through grass, mossed stone, fog along a ridge, or cloud shadow across a slope.
- Directional horizontal motion; cool blue/green base with a small muted mineral/amber moment at most.
- No people, server racks, glowing circuit boards, angel statues, mountain summit clichés, or literal flames.
- Slightly abstract enough that the image is felt before it is identified.
- Apply a consistent Raphael grade: lower saturation 15–25%, lifted blacks, soft grain, no high-contrast HDR.

Use imagery in only three places: the first hero backdrop (low-opacity), one full-width transition between the product story and governance story, and occasional section-edge crop. All product screenshots and evidence panels remain sharp.

On an image, place a Paper-to-transparent scrim behind readable text. Never place small body copy directly on the busy portion of an image. Decorative images use empty alt text; content images get useful alt text.

### Product imagery is the primary proof

The best “illustration” is a polished but truthful Raphael run:

```text
RUN RPH-0482                     CONFIDENCE 0.92
ImagePullBackOff / payments-api  SOURCE: Kubernetes event

01 Detect ✓   02 Investigate ✓   03 Reproduce ✓   04 Validate ✓   05 Review →

Evidence                             Proposed patch
Failed to pull image ...             values.prod.yaml
last known good tag: 2026.09.02      - tag: 2026.09.05
                                     + tag: 2026.09.02

Sandbox / Ignis                      Validation
isolated namespace · 4m 18s          render ✓ · rollout ✓ · health ✓
```

The product image should be rendered as a single broad, gently notched evidence sheet—not a fake browser window, a dense collection of generic cards, or an exploded dashboard collage.

## 9. Landing-page narrative

### 1. Hero — “the failure has a path”

- Quiet Paper canvas with a very soft motion-landscape crop behind or below the hero; navigation has no heavy container.
- Eyebrow: `EVIDENCE-LED DEPLOYMENT REMEDIATION` in mono.
- Recommended headline: **“From failed deployment to a reviewed fix.”**
- Supporting copy: “Raphael investigates the evidence, reproduces the failure in isolation, and prepares the smallest validated change—while production stays read-only.”
- Primary CTA: `See a run` / `Request access`; secondary text link: `Read the safety model`.
- Right/below: the stage pipeline, initially still. One calm current moves through it after the page has settled.

### 2. Proof — “a run you can inspect”

Show a real-looking incident record, source links, confidence, a minimal diff, and validation results. Do not lead with a huge statistic before a pilot has defensible metrics.

### 3. Method — “observe, reproduce, validate”

Use five horizontal stages: `Detect`, `Investigate`, `Reproduce`, `Validate`, `Review`. Each one exposes one piece of evidence instead of showing a generic feature icon. The path from Observe to Reproduce should visibly cross into an outlined `IGNIS / ISOLATED SANDBOX` enclosure.

### 4. Constraint — “autonomy you can audit”

Night evidence room. State the non-negotiables as precise claims: production read-only, bounded source collection, synthetic/mapped sandbox secrets, scoped changes, human-reviewed PR. This is where strong security-language design earns its place.

### 5. Integration — “fits the stack you already run”

Small, sober GitHub / GitHub Actions / Kubernetes / Helm / Kustomize marks and a one-line description. Never visually imply endorsement without permission.

### 6. CTA + footer

Return to Paper with one low-contrast landscape edge and a simple action. Keep the footer compact, documentation-led, and technical.

## 10. Motion rules

Borrow the *idea* of Revolte’s animated pipeline, but make Raphael's animation documentary rather than spectacular.

- **Pipeline current:** a 1–2px soft blue-green highlight traverses the five stages over 8–12 seconds. It stops at the current step and waits for user interaction before looping again.
- **Evidence reveal:** sources, commands, and diff lines appear in causal order at 100–160ms intervals. Never simulate typing more than once; it quickly becomes decorative and inaccessible.
- **Landscape drift:** a 1–2% translate/scale shift over 20–30 seconds, no parallax that changes reading position.
- **State changes:** 160–220ms ease-out for expand/collapse and focus. Do not use springy motion for an operational tool.
- **Reduced motion:** `prefers-reduced-motion: reduce` freezes current, drift, and all automatic reveals at their final, comprehensible state.

The animation must explain the product: an evidence-backed sequence enters a sandbox, a bounded validation returns, and a review gate remains human. If it cannot explain one of those facts, remove it.

## 11. Component language

| Component | Direction |
| --- | --- |
| Navigation | Paper/transparent, 1px bottom rule only after scroll. Sentinel mark + Raphael wordmark left; Docs, Security, Sign in; dark `Request access` button right. |
| Buttons | 8px radius, Ink fill / Paper text. Secondary is text with a 1px Ink rule. No floating gradient pills. |
| Cards | Mostly flat Paper or Night Raised; 1px `--r-mist` / low-opacity Paper border; 8–12px radius; no obvious shadow. Use cards only to group actual evidence or an interaction. |
| Stage nodes | Tiny mono numeral, clear state label, a 1px path. Stage state is text + icon + color. |
| Code/diff | Monospace, 14–15px, 1.55 line-height. Do not use syntax color as the only meaning; additions/deletions get an icon, label, and subtle surface. |
| Badges | Reserved for state (`READ ONLY`, `VALIDATED`, `POLICY BLOCKED`), not marketing (“AI-powered”, “10x”). |
| Icons | 1.5px rounded line icons or custom geometry matching the Sentinel. Avoid shields with checkmarks everywhere. |

### Product UI mode

The console is denser than marketing, but it stays in the same family: Paper default, precise mono labels, forest selection state, semantic statuses, and dark evidence drawers. It should feel like the landing page became a working incident dossier—not like a totally separate dashboard theme.

## 12. Copy voice

Raphael speaks with specific, bounded confidence.

**Use:**

- “Evidence attached to every conclusion.”
- “Reproduced in an isolated sandbox.”
- “Proposed a minimal change for review.”
- “Production access remains read-only.”
- “Validation was inconclusive; here is what we found.”

**Avoid:**

- “Fixes everything while you sleep.”
- “Fully autonomous DevOps.”
- “Eliminate on-call.”
- “Magic,” “superhuman,” “god mode,” “angelic intelligence,” or language that suggests unsupervised production changes.

## 13. Build guardrails

1. Default to content and product proof over decorative visuals. One intentional image is better than five AI backgrounds.
2. No more than one active accent per viewport. Semantic state colors do not count as decorative accents.
3. Every contrast pairing must meet WCAG AA; status always has text and an icon in addition to color.
4. Render and test the pipeline at 320px, 768px, and 1440px. On mobile, stages become a vertically ordered evidence trail; never shrink it into unreadable nodes.
5. Do not invent customer logos, compliance certifications, performance figures, or incident outcomes. Use product truth from the PRD and replace placeholders only with verified proof.
6. Keep production read-only and human review visible in the hero and in the product flow—not just in the legal/footer copy.

## 14. First implementation checklist

- [ ] Draw 8–12 original Sentinel mark thumbnails, test at 16px and 64px, then select one.
- [ ] License and self-host the selected ABC Arizona Flare/Sans cuts; self-host a version-pinned Commit Mono with its OFL notice.
- [ ] Build the color tokens and semantic status tokens above before styling individual sections.
- [ ] Create one accurate `RPH-0482` fictional-but-clearly-labelled demo incident, including source evidence, sandbox isolation, minimal diff, and review gate.
- [ ] Build the five-stage motion pipeline with a no-motion static state first.
- [ ] Establish one repeatable landscape grade using the supplied visual direction; art-direct all future images through it.
- [ ] Conduct contrast, keyboard-focus, and reduced-motion QA before adding decorative detail.

## Source notes

The references were reviewed on 2026-09-06. The recommendations above are original interpretation for Raphael, based on the product PRD and the linked public design references; they are not a request to copy their assets, wording, layouts, or trademarks.
