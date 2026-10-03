# Landing page audit — October 3, 2026

## Observations before implementation

- Desktop's first 700px contains almost entirely hero copy. The central claim
  is legible, but the product example arrives too late and the caption adds
  another divider before the visitor sees what Raphael does.
- Three disconnected cards float on a landscape. The image is distinctive;
  the cards need the hierarchy and alignment of an actual repair workspace.
- The five-step workflow becomes a long stack of nested bordered cards on
  mobile. Its selected explanation sits below all five steps. The replay
  changes copy, but lacks corresponding evidence, progress, or completion cues.
- Chapter headings repeat the same scale; some metadata is too small. Thick
  blocks of pastel color compete with the evidence rather than framing it.
- Entrance motion is identical across every section and doesn't include the
  hero. It animates entire large panels with no meaningful sequence.
- Disclosure content opens abruptly. Replay timing is too short for the long
  descriptions. Step selection changes the page height. Mobile navigation
  lacks outside-click dismissal and active-section feedback.
- The page has useful keyboard controls and reduced-motion handling already.
  Retain those, the original logo, licensed local fonts, and truthful product
  boundaries. The operator console is a separate application.

## Direction

A calm engineering product with editorial warmth. Keep Instrument Sans,
Newsreader accents, IBM Plex Mono, paper, forest, clay, and the supplied images.
Use a smaller display scale, consistent gutters, fine rules, and fewer nested
frames. Make the example feel like one workspace and the workflow an interactive
five-step inspection with a stable evidence panel. On mobile, a compact step
selector keeps the result immediately accessible.

## References inspected

- [Refero / Cursor](https://styles.refero.design/style/4e3b4717-84c8-4599-baaf-a343c3d619b6):
  warm neutral surfaces, restrained type weight, thin borders, and product-led
  editorial hierarchy. Secondary reference interpretation, not Cursor source code.
- [Refero / Linear](https://styles.refero.design/style/90ce5883-bb24-4466-93f7-801cd617b0d1):
  compact dark product surfaces and functional accent color. Preserve Raphael's
  green identity rather than adopting Linear's palette.
- [Revolte](https://revolte.ai/): visible execution story and human control.
  Do not copy its broad product promises, customer logos, or numerical claims.
- [Good Fella](https://good-fella.com/): current text retrieval only exposed a
  loading screen; no new conclusions about its motion are claimed.

## Motion specification

- Native wheel/touch scroll. Smooth anchors, no scroll interception.
- Hero entrance: brief stagger, translate/opacity only, once per page load.
- Section reveals: smaller targeted elements, once, no hidden-content dependency.
- Repair walkthrough: user-started, 5-second steps, visible step progress,
  pause/resume, selection feedback, separate evidence for every stage.
- Disclosures: reversible height animation, keyboard-native summary controls.
- Honor OS reduced motion and a visible page motion control. Cancel active
  animations immediately, finish disclosures, and stop replay when disabled.
- Pause replay when out of view or in a background tab. Clean up on pagehide.

## Verification

- Production Vite build passes and still emits the separate `/console/` entry.
- Browser widths 320, 390, 768, 1024, and 1440px have no horizontal overflow
  or broken image assets. The tablet review card was corrected during QA.
- Tested desktop and mobile first screens and the repair, evidence,
  architecture, and closing chapters in browser screenshots.
- Confirmed all five step buttons, keyboard Home selection, replay
  pause/resume/completion, reduced-motion step navigation, mobile menu close,
  passing/blocked validation, and expandable source evidence.
- All seven disclosures open at 320px without horizontal overflow.
- Browser console reports no errors. `git diff --check` passes.
