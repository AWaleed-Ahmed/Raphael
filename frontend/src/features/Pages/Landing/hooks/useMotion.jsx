"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";

const MotionContext = createContext(null);

export function MotionProvider({ children }) {
  const [systemReduced, setSystemReduced] = useState(false);
  const [manualReduced, setManualReduced] = useState(false);
  const [ready, setReady] = useState(false);
  const [introComplete, setIntroComplete] = useState(false);
  const completeIntro = useCallback(() => {
    try { window.sessionStorage.setItem("raphael-intro-seen-v2", "true"); } catch {}
    setIntroComplete(true);
  }, []);
  useEffect(() => {
    const preference = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setSystemReduced(preference.matches);
    update();
    try {
      setManualReduced(
        localStorage.getItem("raphael-reduce-motion") === "true",
      );
    } catch {}
    try {
      if (window.sessionStorage.getItem("raphael-intro-seen-v2") === "true") setIntroComplete(true);
    } catch {}
    setReady(true);
    preference.addEventListener("change", update);
    return () => preference.removeEventListener("change", update);
  }, []);
  const reduced = systemReduced || manualReduced;
  useEffect(() => {
    if (!ready) return;
    document.documentElement.dataset.motion = reduced ? "reduced" : "full";
    return () => {
      delete document.documentElement.dataset.motion;
    };
  }, [ready, reduced]);
  function toggle() {
    if (systemReduced) return;
    setManualReduced((previous) => {
      try {
        localStorage.setItem("raphael-reduce-motion", String(!previous));
      } catch {}
      return !previous;
    });
  }
  return (
    <MotionContext.Provider value={{ reduced, systemReduced, ready, toggle, introComplete, completeIntro }}>
      {children}
    </MotionContext.Provider>
  );
}

export function useMotion() {
  return useContext(MotionContext);
}
