/* Pure helpers for the OPEN_SITE fallback path. */

export function absoluteSiteUrl(url, origin) {
  try {
    const target = new URL(url, origin);
    const base = new URL(origin);
    if (target.origin !== base.origin && target.protocol !== "https:") return "";
    return target.href;
  } catch {
    return "";
  }
}

export function needsOpenSiteFallback(ack, popup) {
  return !(ack && ack.ok) && !popup;
}
