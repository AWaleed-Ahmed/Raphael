// Fixed silhouettes keep each chapter distinct without changing between renders.
const edges = {
  handoff: "M0 48V20Q0 2 20 2H250Q266 2 276 17L288 33Q298 48 316 48H1440",
  workflow: "M0 48H980Q998 48 1008 32L1018 17Q1028 2 1046 2H1420Q1440 2 1440 22V48",
  evidence: "M0 48V24Q0 2 22 2H456Q474 2 484 18L494 32Q504 48 522 48H1140Q1158 48 1168 34L1180 18Q1190 2 1208 2H1418Q1440 2 1440 24V48",
  architecture: "M0 48H174Q192 48 202 32L212 18Q222 2 240 2H654Q672 2 682 18L692 32Q702 48 720 48H1440",
  safety: "M0 48V22Q0 2 20 2H850Q868 2 878 18L888 32Q898 48 916 48H1440",
  closing: "M0 48H708Q726 48 736 32L746 18Q756 2 774 2H1418Q1440 2 1440 24V48",
  footer: "M0 48V24Q0 2 22 2H304Q322 2 332 18L342 32Q352 48 370 48H1440",
};

export default function SectionNotch({ variant }) {
  const edge = edges[variant];
  return (
    <svg className="section-notch" viewBox="0 0 1440 50" preserveAspectRatio="none" aria-hidden="true" focusable="false">
      <path className="section-notch-fill" d={`${edge}V50H0Z`} />
      <path className="section-notch-edge" d={edge} />
    </svg>
  );
}
