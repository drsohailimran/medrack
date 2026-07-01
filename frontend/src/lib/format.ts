// Helper utilities for the MedRack frontend.

/**
 * Parse a timestamp that may be in either:
 *  - ISO 8601 extended: "2026-06-29T20:02:21Z" (JavaScript native)
 *  - ISO 8601 basic:   "20260629T200221Z" (used by backend benchmark reports)
 *  - Anything `new Date()` would accept directly.
 * Returns a valid Date or null on failure.
 */
export function parseTimestamp(input: string | null | undefined): Date | null {
  if (!input) return null;
  // Native Date handles the extended form directly.
  const direct = new Date(input);
  if (!isNaN(direct.getTime())) return direct;
  // Convert ISO basic (YYYYMMDDTHHMMSSZ) to extended form.
  const m = /^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})Z$/.exec(input);
  if (m) {
    return new Date(`${m[1]}-${m[2]}-${m[3]}T${m[4]}:${m[5]}:${m[6]}Z`);
  }
  return null;
}

/** Format a timestamp for display, returning a placeholder if unparseable. */
export function formatTimestamp(input: string | null | undefined, fallback = "—"): string {
  const d = parseTimestamp(input);
  if (!d) return fallback;
  return d.toLocaleString();
}

/** Format a date only (no time), returning a placeholder if unparseable. */
export function formatDate(input: string | null | undefined, fallback = "—"): string {
  const d = parseTimestamp(input);
  if (!d) return fallback;
  return d.toLocaleDateString();
}
