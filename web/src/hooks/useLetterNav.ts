import { useCallback, useEffect, useRef, useState } from 'react';
import { dotsToBinary, getActiveDots } from '../data/braille';

export function useLetterNav(letters: string[]) {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isAuto, setIsAuto] = useState(false);
  const [speed, setSpeed] = useState(1.5); // seconds between letters, minimum 0.3
  const autoRef = useRef(isAuto);
  const speedRef = useRef(speed);
  autoRef.current = isAuto;
  speedRef.current = speed;

  const next = useCallback(() => {
    setCurrentIndex((i) => Math.min(i + 1, letters.length - 1));
  }, [letters.length]);

  const prev = useCallback(() => {
    setCurrentIndex((i) => Math.max(i - 1, 0));
  }, []);

  const stopAuto = useCallback(() => setIsAuto(false), []);
  const toggleAuto = useCallback(() => setIsAuto((v) => !v), []);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'ArrowRight' || e.key === ' ') {
        e.preventDefault();
        next();
      }
      if (e.key === 'ArrowLeft') {
        e.preventDefault();
        prev();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [next, prev]);

  // reset to start and stop auto if letters array changes
  useEffect(() => {
    setCurrentIndex(0);
    setIsAuto(false);
  }, [letters.join('')]);

  // auto-advance loop
  useEffect(() => {
    if (!isAuto || letters.length === 0) return;
    const delayMs = Math.max(300, speed * 1000);
    const id = setTimeout(() => {
      setCurrentIndex((i) => {
        if (i + 1 >= letters.length) {
          setIsAuto(false);
          return i;
        }
        return i + 1;
      });
    }, delayMs);
    return () => clearTimeout(id);
  }, [isAuto, currentIndex, speed, letters.length]);

  const currentChar = letters[currentIndex] ?? '';
  const activeDots = getActiveDots(currentChar);
  const binaryPattern = dotsToBinary(activeDots);

  // Send pattern to Arduino whenever the displayed letter changes
  useEffect(() => {
    if (!letters.length) return;
    fetch('/api/send-pattern', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pattern: binaryPattern }),
    }).catch(() => {});
  }, [binaryPattern, letters.length]);

  return {
    currentIndex,
    currentChar,
    activeDots,
    binaryPattern,
    canPrev: currentIndex > 0,
    canNext: currentIndex < letters.length - 1,
    next,
    prev,
    isAuto,
    speed,
    setSpeed,
    toggleAuto,
    stopAuto,
  };
}
