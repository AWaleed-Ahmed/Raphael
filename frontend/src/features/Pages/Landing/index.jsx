import Header from "./components/Header";
import Intro from "./components/Intro";
import Hero from "./components/Hero";
import Handoff from "./components/Handoff";
import Workflow from "./components/RepairWorkflow";
import DeploymentStage from "./components/DeploymentStage";
import Evidence from "./components/Evidence";
import Architecture from "./components/Architecture";
import Safety from "./components/Safety";
import Closing from "./components/Closing";
import Footer from "./components/Footer";
import LandingEffects from "./components/LandingEffects";
import { MotionProvider } from "./hooks/useMotion";

export default function LandingPage() {
  return (
    <MotionProvider>
      <Intro />
      <div className={`
          reading-progress fixed top-0 left-0 w-full h-[2px] bg-(--accent) z-40 transform-[scaleX(0)] origin-left
          pointer-events-none
        `} aria-hidden="true" />
      <a className="skip-link fixed left-5 top-[-80px] z-40 p-[10px_16px] bg-(--paper) text-(--night) focus:top-[10px]" href="#main">
        Skip to content
      </a>
      <Header />
      <main id="main">
        <Hero />
        <Handoff />
        <Workflow />
        <DeploymentStage />
        <Evidence />
        <Architecture />
        <Safety />
        <Closing />
      </main>
      <Footer />
      <LandingEffects />
    </MotionProvider>
  );
}
