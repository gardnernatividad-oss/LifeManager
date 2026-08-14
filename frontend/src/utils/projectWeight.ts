export function weightToHundredths(value: string): number | null {
  if (!/^(?:0|[1-9]\d{0,2})(?:\.\d{1,2})?$/.test(value)) return null;
  const [whole, fraction = ""] = value.split(".");
  const result = Number(whole) * 100 + Number(fraction.padEnd(2, "0"));
  return result > 0 && result <= 10_000 ? result : null;
}

export function totalWeightHundredths(steps: Array<{ weight: string }>): number | null {
  let total = 0;
  for (const step of steps) {
    const value = weightToHundredths(step.weight);
    if (value === null) return null;
    total += value;
  }
  return total;
}
