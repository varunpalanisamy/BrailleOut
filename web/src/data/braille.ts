export const BRAILLE: Record<string, number[]> = {
  a: [1], b: [1, 2], c: [1, 4], d: [1, 4, 5], e: [1, 5],
  f: [1, 2, 4], g: [1, 2, 4, 5], h: [1, 2, 5], i: [2, 4], j: [2, 4, 5],
  k: [1, 3], l: [1, 2, 3], m: [1, 3, 4], n: [1, 3, 4, 5], o: [1, 3, 5],
  p: [1, 2, 3, 4], q: [1, 2, 3, 4, 5], r: [1, 2, 3, 5], s: [2, 3, 4],
  t: [2, 3, 4, 5], u: [1, 3, 6], v: [1, 2, 3, 6], w: [2, 4, 5, 6],
  x: [1, 3, 4, 6], y: [1, 3, 4, 5, 6], z: [1, 3, 5, 6], ' ': [],
};

// dot number → [row, col] in the 2×3 grid
export const DOT_POSITION: Record<number, [number, number]> = {
  1: [0, 0], 4: [0, 1],
  2: [1, 0], 5: [1, 1],
  3: [2, 0], 6: [2, 1],
};

export function getActiveDots(char: string): number[] {
  return BRAILLE[char.toLowerCase()] ?? [];
}

// Physical servo wiring order: servo positions 1-6 map to Braille dots [1,4,2,5,3,6]
const SERVO_DOT_ORDER = [1, 4, 2, 5, 3, 6];

export function dotsToBinary(dots: number[]): string {
  return SERVO_DOT_ORDER.map((d) => (dots.includes(d) ? '1' : '0')).join('');
}

export function parseSentenceToLetters(sentence: string): string[] {
  return sentence
    .toLowerCase()
    .split('')
    .filter((ch) => ch in BRAILLE);
}
