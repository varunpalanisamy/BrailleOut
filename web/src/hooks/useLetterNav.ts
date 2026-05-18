import { useCallback, useEffect, useRef, useState } from 'react';
import { dotsToBinary, getActiveDots } from '../data/braille';

export function useLetterNav(letters: string[], suggestedDelay?: number) {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isAuto, setIsAuto] = useState(false);
  const [isRepeat, setIsRepeat] = useState(false);
  const [speed, setSpeed] = useState(1.0); // seconds between letters, minimum 0.3
  const autoRef = useRef(isAuto);
  const speedRef = useRef(speed);
  const prevJoinRef = useRef('');
  autoRef.current = isAuto;
  speedRef.current = speed;

  const next = useCallback(() => {
    setCurrentIndex((i) => Math.min(i + 1, letters.length - 1));
  }, [letters.length]);

  const prev = useCallback(() => {
    setCurrentIndex((i) => Math.max(i - 1, 0));
  }, []);

  const startAuto = useCallback(() => setIsAuto(true), []);
  const stopAuto = useCallback(() => setIsAuto(false), []);
  const toggleAuto = useCallback(() => setIsAuto((v) => !v), []);
  const toggleRepeat = useCallback(() => setIsRepeat((v) => !v), []);

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

  // Smart reset: only reset if letters changed non-append (queue accumulation keeps position)
  useEffect(() => {
    const newJoin = letters.join('');
    const prevJoin = prevJoinRef.current;
    if (newJoin === '' || !newJoin.startsWith(prevJoin)) {
      setCurrentIndex(0);
      setIsAuto(false);
    }
    prevJoinRef.current = newJoin;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [letters.join('')]);

  // seed pacing speed from Gemma's content-type suggestion
  useEffect(() => {
    if (suggestedDelay !== undefined) {
      setSpeed(suggestedDelay);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [suggestedDelay]);

  // auto-advance loop
  useEffect(() => {
    if (!isAuto || letters.length === 0) return;
    const delayMs = Math.max(300, speed * 1000);
    const id = setTimeout(() => {
      setCurrentIndex((i) => {
        if (i + 1 >= letters.length) {
          if (isRepeat) return 0;
          setIsAuto(false);
          return i;
        }
        return i + 1;
      });
    }, delayMs);
    return () => clearTimeout(id);
  }, [isAuto, isRepeat, currentIndex, speed, letters.length]);

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
    isRepeat,
    speed,
    setSpeed,
    startAuto,
    toggleAuto,
    toggleRepeat,
    stopAuto,
  };
}
