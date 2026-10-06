# Raphael — Cloud typography study

October 5, 2026. Preview: `/direction/`.

## Direction

The user supplied two night-cloud illustrations after requesting an art
direction inspired by Railway. Both images are visual assets, not instructions.
The user selected the detailed `C:/Users/Rehan/Downloads/image.png`. It renders
at 76% opacity over the night canvas, with a left-side shading layer and a
stronger mobile overlay. The calmer `image1.png` was the first comparison;
its encoded assets remain available for future design reference.

The Railway reference informs the serif/sans hierarchy and illustrated
atmosphere. This does not claim to use Railway's exact fonts or reproduce its
artwork. The supplied Raphael winged logo remains in the navigation.

References: [Railway gallery](https://bestsaaswebdesigns.com/site/railway),
[Sentient](https://fontshare.com/fonts/sentient),
[Switzer](https://fontshare.com/fonts/switzer),
[Telma](https://fontshare.com/fonts/telma).

## Typography

Sentient 400 gives the large statements a measured editorial voice and enough
weight to remain legible over the illustrated sky. Switzer 400–500 carries
body text, navigation, buttons, and artifact titles. IBM Plex Mono 400 is
reserved for short labels, repository paths, and diffs. Telma 500 gives the
wordmark its own voice. Cabinet Grotesk was an earlier comparison; the
accepted page now uses the selected families without comparison controls.

- Hero: responsive 52–76px on desktop, 42–64px on mobile; serif leading about
  1.09–1.13 and modest negative tracking. Two intentional headline lines.
- Reading: 15–16px with 1.75 leading, around 475px maximum line width.
- Chapter headings: 32–48px; reading and artifact titles use the sans family.
- Controls: sentence case; 12–13px primary button type, visible keyboard focus.

The Fontshare families load from separate official API stylesheets. Sentient's
400 face was verified through the official CSS endpoint. The concept requires
network access for these fonts and has Georgia/Arial fallbacks. Production
self-hosting should preserve unmodified font files, provenance, and license
terms; no Fontshare binaries were copied into the repository.

## Artwork and composition

Both source images are 1672 × 941px. Responsive WebP encodings at 640, 1280,
and 1672px preserve their original composition and colors; the source artwork
was not cropped or retouched. The largest detailed encoding is about 104KB;
the calm encoding is about 78KB. `srcset` lets the browser choose the appropriate
file. Only the selected detailed artwork is requested by the current page.

The decorative picture is hidden from assistive technology. It extends behind
the navigation and follows the hero's actual height, including when copy
wraps on narrow screens. Horizontal shading protects the text; the lower fade
joins the flat page canvas. Mobile uses a deliberate crop and a stronger
overlay. There is no animation loop, scroll interception, or moving backdrop.
Native smooth anchor scrolling respects the OS reduced-motion preference.

The sequence stays varied: illustrated hero → three concise repair stages →
light handoff chapter with dark evidence artifact → type/color study board.
The board is a design-review aid, not a proposed product feature. The earlier
comparison controls are removed. The night/pearl palette replaces neutral charcoal/chalk in this
iteration; violet remains the action accent. Review state is labeled, and
diffs retain explicit plus/minus signs.

## Scope and validation

This updates the `/direction/` concept, its static assets, and `design.md`.
The original landing page and console have not been migrated. Product claims
remain investigation, isolated sandbox checks, narrow repair, draft PR, and
human review. Production access remains read-only in the illustrated workflow;
the example is explicitly illustrative and awaiting review.

Initial comparison iteration verified in the in-app browser:

- Desktop 1280px, mobile 390px, narrow mobile 320px, and tablet 768px.
- No horizontal overflow at the checked widths, including the alternate sans
  mode at 320px. Mobile retains the complete three-step baseline.
- Both artwork selections update the image source and pressed state; both
  headline selections update the family and announce the choice.
- Desktop full-page composition and mobile hero captured for review.
- Production `npm run build` passed, including the direction entry and assets.

The browser recorded a development-only Vite HMR websocket connection failure;
the page loaded and the comparison controls worked. A final browser screenshot
request stalled after the responsive checks. The saved captures precede that
stall. No production runtime failure was observed.

Captures: `cloud-study-full.png`, `cloud-study-mobile.png`.

## Accepted direction and wordmark refinement

The user approved Sentient headings and selected the detailed sky, dimmed. The artwork/type
comparison controls and the unused Cabinet Grotesk request are removed from
the current study. The comparison verification above describes the earlier
review iteration; the accepted page no longer needs JavaScript.

The header now uses Telma 500 rather than Switzer text. Bespoke Serif, Telma,
and Dancing Script were visually inspected on their official Fontshare pages.
Telma's sharp flowing forms suit the winged symbol and illustrated identity;
Bespoke Serif felt closer to the existing headline voice, while Dancing Script
felt more informal. These are design judgments, not claims about font quality.
Telma stays in the wordmark, avoiding a competing script style in product copy.
Its official 500 stylesheet was verified. The accessible brand link continues
to expose “Raphael home.” No font was modified or converted into paths.

Explore Raphael uses a smoked-violet surface with a subdued inner highlight,
a slightly brighter edge on hover/focus, and 12px backdrop blur. The default
solid surface is the fallback, enhanced with transparency only when blur is
supported. The button has a minimum 44px height; reduced motion disables its
short state transition. The brand scales at mobile breakpoints to leave room
for the complete navigation action.

The final wordmark/button pass was visually checked at 1280px and 320px, with
no horizontal overflow. The complete button and logo both fit at 320px. The
browser confirmed Telma 500, detailed artwork at 0.76 opacity, and the glass
button's 12px blur/44px minimum height. Final capture: `cloud-wordmark-hero.png`.
