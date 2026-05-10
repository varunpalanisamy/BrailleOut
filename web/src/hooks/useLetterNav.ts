import { useCallback, useEffect, useState } from 'react';
import { dotsToBinary, getActiveDots } from '../data/braille';

export function useLetterNav(letters: string[]) {
  const [currentIndex, setCurrentIndex] = useState(0);

  const next = useCallback(() => {
    setCurrentIndex((i) => Math.min(i + 1, letters.length - 1));
  }, [letters.length]);

  const prev = useCallback(() => {
    setCurrentIndex((i) => Math.max(i - 1, 0));
  }, []);

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

  // reset to start if letters array changes
  useEffect(() => {
    setCurrentIndex(0);
  }, [letters.join('')]);

  const currentChar = letters[currentIndex] ?? '';
  const activeDots = getActiveDots(currentChar);

  return {
    currentIndex,
    currentChar,
    activeDots,
    binaryPattern: dotsToBinary(activeDots),
    canPrev: currentIndex > 0,
    canNext: currentIndex < letters.length - 1,
    next,
    prev,
  };
}
