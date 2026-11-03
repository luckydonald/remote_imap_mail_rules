/** Variable values are typed as text: `true`, `5` or `[1]` are taken as such, anything else is text. Quote a text that looks like one: `"5"`. */
export function parseValue(text: string): unknown {
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return text;
  }
}

export function showValue(value: unknown): string {
  if (value === undefined) return "";
  return typeof value === "string" ? value : JSON.stringify(value);
}
