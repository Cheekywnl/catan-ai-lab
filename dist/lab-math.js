/** Exact joint posterior after one uniformly random, unobserved resource theft. */
export function theftOutcomes(ore, wheat) {
  if (![ore, wheat].every(n => Number.isInteger(n) && n >= 0 && n <= 100) || ore + wheat === 0) {
    throw new RangeError('Use nonnegative whole-card counts with at least one card in total.');
  }
  const total = ore + wheat;
  return [
    ...(ore ? [{ stolen: 'ore', probability: ore / total, victim: { ore: ore - 1, wheat }, thief: { ore: 1, wheat: 0 } }] : []),
    ...(wheat ? [{ stolen: 'wheat', probability: wheat / total, victim: { ore, wheat: wheat - 1 }, thief: { ore: 0, wheat: 1 } }] : [])
  ];
}
