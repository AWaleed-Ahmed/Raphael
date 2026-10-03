// Small, cancellable motion primitives. Content is always readable without JS.
const preference = window.matchMedia('(prefers-reduced-motion: reduce)');
const active = new Set();
const listeners = new Set();
let manuallyReduced = false;
try { manuallyReduced = localStorage.getItem('raphael-reduce-motion') === 'true'; } catch {}
export const reduceMotion = () => preference.matches || manuallyReduced;
export function onMotionChange(callback) { listeners.add(callback); }

export function animate(element, frames, options = {}) {
  if (!element || reduceMotion()) return null;
  const animation = element.animate(frames, {
    duration: 500, easing: 'cubic-bezier(.22,1,.36,1)', ...options,
  });
  active.add(animation);
  animation.finished.then(() => active.delete(animation), () => active.delete(animation));
  return animation;
}

const toggle = document.querySelector('.motion-toggle');
toggle.hidden = false;
function applyPreference() {
  const reduced = reduceMotion();
  document.documentElement.dataset.motion = reduced ? 'reduced' : 'full';
  toggle.textContent = preference.matches ? 'Motion: reduced by system' : `Motion: ${reduced ? 'off' : 'on'}`;
  toggle.setAttribute('aria-pressed', String(reduced));
  toggle.setAttribute('aria-label', preference.matches ? 'Reduced motion is enabled in your system settings' : 'Reduce page motion');
  toggle.disabled = preference.matches;
  if (reduced) active.forEach(animation => animation.cancel());
  listeners.forEach(callback => callback(reduced));
}
toggle.addEventListener('click', () => {
  manuallyReduced = !manuallyReduced;
  try { localStorage.setItem('raphael-reduce-motion', String(manuallyReduced)); } catch {}
  applyPreference();
});
preference.addEventListener('change', applyPreference);
applyPreference();

export function setupEntrances() {
  const groups = [
    ['.hero-copy > .eyebrow, .hero-line, .hero-description, .actions', 70],
    ['.scene-top, .signal-artifact, .diagnosis-artifact, .review-artifact', 95],
    ['.workflow-intro, .walkthrough, .section-heading, .evidence-panel, .diff-panel, .validation-panel, .architecture-copy, .permission-map, .draft-ground, .safety-statements, .closing-inner', 0],
  ];
  const observer = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (!entry.isIntersecting) return;
      observer.unobserve(entry.target);
      const delay = Number(entry.target.dataset.entranceDelay || 0);
      animate(entry.target, [
        { opacity: .15, translate: '0 22px' },
        { opacity: 1, translate: '0 0' },
      ], { duration: 720, delay });
    });
  }, { threshold: 0.06 });
  groups.forEach(([selector, stagger]) => {
    document.querySelectorAll(selector).forEach((element, index) => {
      element.dataset.entranceDelay = String(index * stagger);
      observer.observe(element);
    });
  });
  window.addEventListener('pagehide', () => {
    active.forEach(animation => animation.cancel());
  });
}

export function setupDisclosures() {
  document.querySelectorAll('details').forEach(details => {
    const summary = details.querySelector('summary');
    let animation;
    let expanded = details.open;
    function settle() {
      animation?.cancel();
      animation = null;
      details.open = expanded;
      details.style.removeProperty('overflow');
    }
    summary.addEventListener('click', event => {
      if (reduceMotion()) return; // Preserve the native keyboard/click behavior.
      event.preventDefault();
      const start = details.getBoundingClientRect().height;
      expanded = animation ? !expanded : !details.open;
      animation?.cancel();
      details.open = true;
      const end = expanded ? details.getBoundingClientRect().height : summary.getBoundingClientRect().height;
      details.style.overflow = 'clip';
      animation = animate(details, [{ height: `${start}px` }, { height: `${end}px` }], { duration: 280 });
      if (animation) animation.onfinish = settle;
      else settle();
    });
    onMotionChange(reduced => { if (reduced && animation) settle(); });
    window.addEventListener('resize', () => { if (animation) settle(); }, { passive: true });
  });
}
