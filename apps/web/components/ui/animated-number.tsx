"use client";
import { useEffect, useRef, useState } from "react";
import { animate, useReducedMotion } from "framer-motion";

// Counts smoothly to the new value. With reduced motion it simply shows it.
export function AnimatedNumber({ value }: { value: number }) {
  const reduced = useReducedMotion();
  const [shown, setShown] = useState(reduced ? value : 0);
  const from = useRef(reduced ? value : 0);
  useEffect(() => {
    if (reduced) {
      setShown(value);
      from.current = value;
      return;
    }
    const controls = animate(from.current, value, {
      duration: 0.8,
      ease: [0.2, 0.7, 0.2, 1],
      onUpdate: (v) => setShown(Math.round(v)),
      onComplete: () => {
        from.current = value;
      },
    });
    return () => controls.stop();
  }, [value, reduced]);
  return <>{shown.toLocaleString()}</>;
}
