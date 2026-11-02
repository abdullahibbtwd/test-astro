/**
 * Step 3 interpretation is intentionally unfinished.
 * These markers MUST be removed before a store release — `release:check`
 * and `assertNoPendingAstrologerMarkers` fail if they remain in a release build.
 */
export const PENDING_ASTROLOGER_MARK = "pending astrologer";

export const SOLAR_RETURN_PLACEHOLDER =
  "[Solar return reading — pending astrologer]";

export const FAMILY_COMPATIBILITY_PLACEHOLDER =
  "[Family compatibility reading — pending astrologer]";

export const PENDING_ASTROLOGER_MARKERS = [
  SOLAR_RETURN_PLACEHOLDER,
  FAMILY_COMPATIBILITY_PLACEHOLDER,
  PENDING_ASTROLOGER_MARK,
] as const;

/** Test id for the red unfinished-content banner. */
export const PENDING_ASTROLOGER_BANNER_TEST_ID = "pending-astrologer-banner";

/**
 * Scan text (source files, bundle, or UI copy) for unfinished Step 3 markers.
 * Returns every hit so release gates can fail loudly.
 */
export function findPendingAstrologerMarkers(text: string): string[] {
  const lower = text.toLowerCase();
  return PENDING_ASTROLOGER_MARKERS.filter((marker) =>
    lower.includes(marker.toLowerCase()),
  );
}

/**
 * Call from release builds / release:check. Throws if any marker remains.
 * Dev / preview builds may keep the placeholders on purpose.
 */
export function assertNoPendingAstrologerMarkers(
  text: string,
  { isRelease }: { isRelease: boolean },
): void {
  if (!isRelease) return;
  const hits = findPendingAstrologerMarkers(text);
  if (hits.length) {
    throw new Error(
      `Step 3 pending-astrologer placeholders must be removed before release: ${hits.join("; ")}`,
    );
  }
}
