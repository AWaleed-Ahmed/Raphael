import { animate, reduceMotion, onMotionChange, setupEntrances, setupDisclosures } from './motion.js';
import { icon, buttonContent } from './icons.js';
// Presentation-only interactions. This page never calls the agent or sandbox API.
document.documentElement.classList.add("js");

const menu = document.querySelector(".menu-toggle");
const navigation = document.querySelector("#site-nav");
document.querySelector('.site-header').classList.add('js-ready');
menu.hidden = false;
function closeMenu(returnFocus = false) {
  navigation.classList.remove("is-open");
  menu.setAttribute("aria-expanded", "false");
  buttonContent(menu, 'Menu', 'plus');
  if (returnFocus) menu.focus();
}
menu.addEventListener("click", () => {
  const open = menu.getAttribute("aria-expanded") !== "true";
  menu.setAttribute("aria-expanded", String(open));
  navigation.classList.toggle("is-open", open);
  buttonContent(menu, open ? 'Close' : 'Menu', open ? 'minus' : 'plus');
});
navigation.addEventListener("click", (event) => {
  if (event.target.closest("a")) closeMenu();
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && menu.getAttribute("aria-expanded") === "true") closeMenu(true);
});
window.matchMedia("(min-width: 768px)").addEventListener("change", (event) => {
  if (event.matches) closeMenu();
});

const stages = [
  { label: '01 / Investigate', title: 'A mismatch worth investigating.', scope: 'Read-only investigation', copy: 'The container listens on 8080. The readiness probe targets 8081. Correlate the event and manifest before proposing a repair.', file: 'events + deployment.yaml', badge: 'Candidate cause', result: 'Two sources. One testable hypothesis.', lines: [['', 'Warning  Unhealthy  payments-api'], ['removed', 'GET :8081/healthz → connection refused'], ['', 'containerPort: 8080'], ['emphasis', 'readinessProbe.httpGet.port: 8081']] },
  { label: '02 / Reproduce', title: 'Same failure. Isolated environment.', scope: 'Ignis / isolated sandbox', copy: 'Deploy the failing revision in an Ignis sandbox. A matching failure signature establishes the baseline for testing the candidate repair.', file: 'sandbox / baseline observation', badge: 'Failure reproduced', result: 'A baseline to compare. Production is untouched.', lines: [['', 'revision: failing deployment'], ['', 'environment: isolated sandbox'], ['removed', 'readiness check: connection refused'], ['emphasis', 'failure signature: matched']] },
  { label: '03 / Patch', title: 'One field. A focused repair.', scope: 'Ignis / isolated sandbox', copy: 'Point the readiness probe at the declared container port. Test this narrow configuration change in the sandbox before preparing it for review.', file: 'deploy/deployment.yaml', badge: 'Candidate patch', result: 'A small diff that a human can inspect.', lines: [['', 'readinessProbe:'], ['', '  httpGet:'], ['', '    path: /healthz'], ['removed', '−   port: 8081'], ['added', '+   port: 8080']] },
  { label: '04 / Validate', title: 'The checks travel with the change.', scope: 'Sandbox validation only', copy: 'Compare the baseline with the patched run. Attach the named checks and their scope. Missing mandatory checks stop the workflow.', file: 'validation / before + after', badge: 'Evidence attached', result: 'Sandbox evidence, not production verification.', lines: [['', 'before: failure signature reproduced'], ['added', 'after: original signature absent'], ['added', 'mandatory sandbox checks: complete'], ['emphasis', 'scope: isolated sandbox only']] },
  { label: '05 / Human review', title: 'The final decision belongs to you.', scope: 'Human-controlled delivery', copy: 'Review the proposed diff alongside its evidence and validation scope. Your team decides whether to merge and deploy. Live draft publishing is opt-in.', file: 'draft / readiness probe repair', badge: 'Awaiting review', result: 'No automatic merge. No production write.', lines: [['', 'change: align probe with container port'], ['', 'attachments: evidence + validation'], ['emphasis', 'status: draft · awaiting human review'], ['', 'merge: not performed'], ['', 'production: unchanged']] },
];
const stageButtons = [...document.querySelectorAll('[data-stage]')];
const replay = document.querySelector('#replay-button');
const status = document.querySelector('#replay-status');
const walkthrough = document.querySelector('.walkthrough');
const stageDuration = 5000;
let activeStage = 0;
let playing = false;
let paused = false;
let timer;
let progressAnimation;
let contentAnimation;

function selectStage(index, transition = true) {
  activeStage = index;
  const stage = stages[index];
  walkthrough.dataset.activeStage = String(index);
  stageButtons.forEach((button, position) => {
    button.setAttribute('aria-pressed', String(position === index));
    button.classList.toggle('is-previous', position < index);
  });
  for (const key of ['label', 'title', 'scope', 'copy', 'result']) {
    document.querySelector(`#stage-${key}`).textContent = stage[key];
  }
  document.querySelector('.stage-count').textContent = `${String(index + 1).padStart(2, '0')} / 05`;
  document.querySelector('#trace-file').textContent = stage.file;
  document.querySelector('#trace-badge').textContent = stage.badge;
  const code = document.querySelector('#stage-evidence code');
  code.replaceChildren(...stage.lines.map(([kind, text]) => {
    const row = document.createElement('span');
    row.className = `trace-line${kind ? ` is-${kind}` : ''}`;
    row.textContent = text;
    return row;
  }));
  contentAnimation?.cancel();
  if (transition) contentAnimation = animate(document.querySelector('.inspection-body'), [
    { opacity: .3, translate: '0 8px' }, { opacity: 1, translate: '0 0' },
  ], { duration: 360 });
}
function stopReplay(message, canResume = false) {
  clearTimeout(timer);
  progressAnimation?.cancel();
  playing = false;
  paused = canResume;
  walkthrough.classList.remove('is-playing');
  buttonContent(replay, canResume ? 'Resume walkthrough' : 'Replay walkthrough', canResume ? 'play' : 'arrow-counter-clockwise');
  if (message) status.textContent = message;
}
function advance() {
  progressAnimation?.cancel();
  progressAnimation = animate(document.querySelector('.replay-progress i'), [
    { transform: 'scaleX(0)' }, { transform: 'scaleX(1)' },
  ], { duration: stageDuration, easing: 'linear', fill: 'forwards' });
  timer = setTimeout(() => {
    if (activeStage === stages.length - 1) {
      stopReplay('Walkthrough complete. Draft awaits human review.');
    } else {
      selectStage(activeStage + 1);
      advance();
    }
  }, stageDuration);
}
replay.addEventListener('click', () => {
  if (playing) return stopReplay('Paused. Resume or choose any step.', true);
  if (reduceMotion()) {
    selectStage((activeStage + 1) % stages.length);
    status.textContent = `Step ${activeStage + 1} of 5. Motion is reduced; use the steps to explore.`;
    buttonContent(replay, 'Next step', 'arrow-right');
    return;
  }
  if (!paused || activeStage === stages.length - 1) selectStage(0);
  paused = false;
  playing = true;
  walkthrough.classList.add('is-playing');
  buttonContent(replay, 'Pause walkthrough', 'pause');
  status.textContent = 'Illustrative replay · five seconds per step';
  advance();
});
stageButtons.forEach((button, index) => {
  button.addEventListener('click', () => {
    stopReplay(`Step ${index + 1} of 5 selected. Illustrative evidence shown.`);
    selectStage(index);
  });
  button.addEventListener('keydown', event => {
    const direction = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[event.key];
    if (direction === undefined && !['Home', 'End'].includes(event.key)) return;
    event.preventDefault();
    const next = event.key === 'Home' ? 0 : event.key === 'End' ? 4 : (index + direction + 5) % 5;
    stageButtons[next].focus();
    stageButtons[next].click();
  });
});
document.querySelector('.replay-controls').hidden = false;
document.addEventListener('visibilitychange', () => {
  if (document.hidden && playing) stopReplay('Paused while the page is in the background.', true);
});
new IntersectionObserver(([entry]) => {
  if (!entry.isIntersecting && playing) stopReplay('Paused. Resume when you return.', true);
}, { threshold: 0 }).observe(walkthrough);
onMotionChange(reduced => {
  if (reduced && playing) stopReplay('Motion reduced. Select a step to inspect it.');
});
window.addEventListener('pagehide', () => { if (playing) stopReplay('Paused. Resume when you return.', true); });

// Explicitly separate a blocked illustrative result from the passing example.
const validationExamples = {
  passing: {
    rows: [["check", "Before / reproduced failure"], ["check", "After / signature absent"], ["arrow-elbow-down-right", "Scope / sandbox checks only"]],
    notice: "Sandbox evidence is attached to the draft. Production has not been changed.",
  },
  blocked: {
    rows: [["check", "Before / reproduced failure"], ["warning", "Rollout check / unavailable"], ["pause", "Delivery / no draft prepared"]],
    notice: "A mandatory check could not run. Validation is inconclusive; the workflow stops and reports the gap for human investigation.",
  },
};
document.querySelector(".example-switch").hidden = false;
document.querySelectorAll("[data-outcome]").forEach((button) => button.addEventListener("click", () => {
  const outcome = button.dataset.outcome;
  const example = validationExamples[outcome];
  document.querySelectorAll("[data-outcome]").forEach((item) => item.setAttribute("aria-pressed", String(item === button)));
  document.querySelector(".validation-panel").classList.toggle("is-blocked", outcome === "blocked");
  const list = document.querySelector("#validation-checks");
  list.replaceChildren(...example.rows.map(([symbol, label]) => {
    const row = document.createElement("li");
    const marker = document.createElement("span");
    marker.setAttribute("aria-hidden", "true");
    marker.append(icon(symbol));
    const copy = document.createElement("span");
    copy.textContent = label;
    row.append(marker, copy);
    return row;
  }));
  document.querySelector("#validation-notice").textContent = example.notice;
}));

function revealBoundary() {
  if (window.location.hash === "#boundaries") document.querySelector("#boundaries").open = true;
}
document.querySelector('a[href="#boundaries"]').addEventListener("click", () => {
  document.querySelector("#boundaries").open = true;
});
window.addEventListener("hashchange", revealBoundary);
revealBoundary();

// Native wheel/touch scrolling; only the lightweight progress bar tracks scroll.
const progress = document.querySelector('.reading-progress');
let progressFrame = 0;
function updateProgress() {
  progressFrame = 0;
  updateNavigation();
  const range = document.documentElement.scrollHeight - window.innerHeight;
  progress.style.transform = `scaleX(${range > 0 ? Math.min(1, Math.max(0, window.scrollY / range)) : 0})`;
}
function scheduleProgress() {
  if (!progressFrame) progressFrame = requestAnimationFrame(updateProgress);
}
window.addEventListener('scroll', scheduleProgress, { passive: true });
window.addEventListener('resize', scheduleProgress);
document.addEventListener('toggle', scheduleProgress, true);
scheduleProgress();

setupEntrances();
setupDisclosures();

// Keep navigation available during long-page exploration without trapping focus.
const header = document.querySelector('.site-header');
document.addEventListener('click', event => {
  if (!header.contains(event.target) && menu.getAttribute('aria-expanded') === 'true') closeMenu();
});
const navLinks = [...navigation.querySelectorAll('a[href^="#"]')];
const chapters = navLinks.map(link => document.querySelector(link.hash)).filter(Boolean);
function updateNavigation() {
  const current = [...chapters].sort((a, b) => a.offsetTop - b.offsetTop)
    .filter(section => section.getBoundingClientRect().top <= 160).at(-1);
  navLinks.forEach(link => {
    if (current && link.hash === `#${current.id}`) link.setAttribute('aria-current', 'location');
    else link.removeAttribute('aria-current');
  });
  const isScrolled = window.scrollY > 30;
  header.classList.toggle('is-scrolled', isScrolled);

  // Follow the surface passing beneath the nav so links stay legible across
  // the landing page's alternating light and dark chapters.
  const lightChapter = isScrolled && (() => {
    const y = Math.min(window.innerHeight - 1, header.getBoundingClientRect().bottom + 8);
    const beneathHeader = document.elementFromPoint(window.innerWidth / 2, y);
    return beneathHeader?.closest('[data-nav-theme="light"]');
  })();
  header.classList.toggle('is-light', Boolean(lightChapter));
  header.classList.toggle('is-ink', isScrolled && !lightChapter);
}
new ResizeObserver(scheduleProgress).observe(document.body);
updateNavigation();
