// Pure functions shared by the UI and tests; missing values are never coerced to zero.
export const COLORS = ["#fff3b0", "#fed976", "#fda343", "#f46b32", "#c92a24"];
export const finite = value => typeof value === "number" && Number.isFinite(value);
export const formatRate = value => finite(value) ? value.toFixed(2) : "—";
export function weekBefore(key) {
  const [year, week] = key.split("-").map(Number);
  const jan4 = new Date(Date.UTC(year, 0, 4));
  const day = jan4.getUTCDay() || 7;
  const monday = new Date(jan4.getTime() - (day - 1) * 86400000 + (week - 2) * 7 * 86400000);
  return keyFromDate(monday);
}
export function keyFromDate(input) {
  const date = new Date(input);
  date.setUTCDate(date.getUTCDate() + 4 - (date.getUTCDay() || 7));
  const year = date.getUTCFullYear();
  const jan1 = new Date(Date.UTC(year, 0, 1));
  const week = Math.ceil((((date - jan1) / 86400000) + 1) / 7);
  return `${year}-${String(week).padStart(2, "0")}`;
}
export function change(current, previous, breakReason = null) {
  if (breakReason) return { percent: null, delta: null, reason: breakReason };
  if (!finite(current) || !finite(previous)) return { percent: null, delta: null, reason: "当週または前週に数値がありません" };
  const delta = current - previous;
  if (previous === 0) return { percent: null, delta, reason: "前週が0のため増減率を算出できません" };
  return { percent: delta / previous * 100, delta, reason: null };
}
export function history(dataset, key, disease, index, count = 10) {
  const result = [];
  let cursor = key;
  for (let i = 0; i < count; i++) {
    const record = dataset.weeks[cursor];
    const values = record?.diseases[disease];
    result.push({ key: cursor, rate: values?.rates?.[index] ?? null, mark: values?.rate_marks?.[index] ?? null, source: record?.source ?? null, record: record ?? null });
    cursor = weekBefore(cursor);
  }
  return result.reverse();
}
export function colorScale(values) {
  const valid = values.filter(finite);
  const maximum = valid.length ? Math.max(...valid) : 0;
  const top = maximum > 0 ? maximum : 1;
  return { max: maximum, top, color(value) {
    if (!finite(value)) return "url(#missing-data)";
    return COLORS[Math.min(4, Math.max(0, Math.floor(value / top * 5)))];
  } };
}
