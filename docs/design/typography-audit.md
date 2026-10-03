# Raphael typography and interaction audit

Implemented September 19, 2026. Scope: the public landing page at `/`.

## Diagnosis

The original implementation had a coherent forest/paper palette and a useful
product story. The weakest element was hierarchy rather than missing decoration.
Segoe UI made the branding depend on the visitor's OS. Several headings had the
same scale and repeated heading/panel composition. Dense monospaced labels and
variable Unicode symbol shapes made diagrams feel assembled. The green palette
had too little temperature contrast across a long page. At small widths the
hero's tight tracking and centered text lost some of its clarity.

## Reference evaluation

- [Good Fella](https://good-fella.com/): observed large, restrained sans headings,
  small technical labels, high contrast, strong whitespace, and emphatic action
  controls. Adopt the hierarchy and editorial confidence; its orange identity,
  animated ASCII portrait, loading screen, and agency metrics do not serve
  Raphael's evidence-first story.
- [Refero's Ventriloc study](https://styles.refero.design/style/f99aca3e-5289-4595-a7cc-77a72052f4b8):
  a relevant warm editorial treatment of a technical/data product. The useful
  principle is restrained display weight alongside precise information, not
  copying its custom font or page composition.
- [Fontshare Switzer](https://www.fontshare.com/?q=Switzer): considered for its
  restrained neo-grotesque character. Instrument Sans won because its variable
  weights and open-source distribution fit a self-contained implementation.

These are design judgments from the references, not a claim that one font or
scroll library guarantees awards. The relevant contemporary techniques are
variable typography, deliberate asymmetry, art-directed imagery, fine rules,
controlled color changes, and restrained interaction.

## Font decisions

| Family | Role | Reason |
| --- | --- | --- |
| Instrument Sans | Main display, prose, UI | Precision with slightly individual letterforms; a consistent voice across headings and practical copy. |
| IBM Plex Mono | Evidence, file paths, chapter labels | Clear technical texture and stable numeral/code alignment. |
| Newsreader italic | Short emphasis and image caption | A controlled human counterpoint to the technical layers, never a whole serif hero or UI. |

Primary sources: [Instrument](https://github.com/Instrument/instrument-sans),
[IBM Plex](https://github.com/IBM/plex),
[Production Type Newsreader](https://github.com/productiontype/Newsreader).
Font binaries are original, unmodified WOFF2 assets supplied through Fontsource;
license notices are in `frontend/public/licenses/`. The three Latin webfont
files total approximately 109KB. Only the main sans is preloaded; all use swap.

## Layout and color decisions

The page now alternates composition as well as background: centered promise,
staggered repair artifacts, a wide dark sequence, an asymmetric evidence gallery,
a blue explanation plate, a warm draft with numbered principles, and a split
closing statement. Each color has a role: forest is the operational space, blue
is the architectural explanation, clay is human review, and citron is validation.
The existing nature images are sufficient; more stock imagery would dilute the
concrete repair story.

Display size is responsive rather than a fixed desktop value. Major headings
use balanced wrapping; prose has bounded line lengths. Mobile is deliberately
left-aligned with more relaxed tracking. The review sheet becomes compact while
keeping label/value relationships and readable code.

## Icons and motion

[Phosphor Light](https://github.com/phosphor-icons/core) supplies the action,
replay, disclosure, workflow, status, and principle icons. A local SVG sprite
ships only the chosen symbols. Icons inherit text color, are hidden from assistive
technology when decorative, and accompany visible action labels. Its MIT notice
is included. Native disclosure controls remain keyboard-operable without JS.

Native wheel/touch behavior is retained. Smooth anchor links, a narrow scroll
progress indicator, 650ms one-time entrances, and short icon transitions provide
motion without scroll interception or another runtime dependency. Content is
visible before scripts run. Reduced-motion preferences disable entrances and
smooth scrolling and keep the existing immediate/manual workflow behavior.

## Defects corrected and verification

- Replaced OS-dependent main typography and inconsistent decorative glyphs.
- Removed duplicate CSS-generated disclosure symbols when details are open.
- Made replay pause/resume and validation status icons use the same SVG system.
- Added explicit mobile menu close labeling and maintained Escape handling.
- Kept critical validation messages textual, even when colors/icons change.
- Relaxed mobile heading tracking; reduced mobile draft-sheet height.
- Fixed rotated workflow connectors intercepting taps on mobile: constrained
  connector boxes and disabled pointer events on decorative vectors/connectors.
- Checked 320, 390, 768, 1024, and 1440px viewports with no horizontal overflow,
  including an expanded architecture disclosure.
- Checked key text color pairs: body 5.53:1, moss display 4.77:1, architecture
  body 5.01:1, blocked validation notice 4.55:1, workflow body 9.29:1,
  failure badge 5.14:1. This is targeted contrast inspection, not a claim of a
  complete accessibility certification.
- Browser-checked navigation, disclosure opening, SVG status changes, and
  replay pause/resume. Production build passes. Console styling is isolated.

## Maintenance

`frontend/scripts/refine-brand.mjs` regenerates the selected local assets from
locked npm packages. `editorial.css` owns the new design choices; `landing.css`
retains structural/responsive foundations. Keep future type and surface changes
in that layer to avoid splitting the visual rules across unrelated components.
