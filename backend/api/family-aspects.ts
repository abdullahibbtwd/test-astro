/**
 * Family / Match aspect-math adapter — family_aspects_bridge.py only.
 * No interpretation rules; placeholder text only.
 */
import { spawn } from "node:child_process";
import { fileURLToPath, URL } from "node:url";
import type { FamilyRelation } from "../../frontend/contracts/spec-types";

export const FAMILY_COMPATIBILITY_PLACEHOLDER =
  "[Family compatibility reading — pending astrologer]";

/** Engine relationship_type values accepted by compute_synastry_aspects. */
export type FamilyRelationshipType = "romantic" | "parent_child" | "sibling";

export type FamilyAspectsInput = {
  chart_a: unknown;
  chart_b: unknown;
  relationship_type: FamilyRelationshipType;
  profile_a_label?: string;
  profile_b_label?: string;
};

export type FamilyAspectsOutput = {
  relationship_type: FamilyRelationshipType;
  profile_a_label: string;
  profile_b_label: string;
  aspects: Array<Record<string, unknown>>;
  interpretation: string;
  math: { aspects: string };
};

/** Map API FamilyRelation → engine relationship_type (no invented weights). */
export function relationshipTypeFromFamilyRelation(
  relation: FamilyRelation,
): FamilyRelationshipType {
  if (relation === "parent_child") return "parent_child";
  if (relation === "siblings") return "sibling";
  // "other" — use romantic set until the astrologer supplies other rules.
  return "romantic";
}

export function runFamilyAspectsBridge(
  payload: FamilyAspectsInput,
): Promise<FamilyAspectsOutput> {
  return new Promise((resolve, reject) => {
    const child = spawn(
      process.env.PYTHON ?? "python",
      [
        "-X",
        "utf8",
        fileURLToPath(new URL("./family_aspects_bridge.py", import.meta.url)),
      ],
      { windowsHide: true, stdio: ["pipe", "pipe", "pipe"] },
    );
    let output = "";
    const timer = setTimeout(() => {
      child.kill();
      reject(new Error("Family aspects calculation timed out"));
    }, 60000);
    child.stdout.on("data", (chunk) => {
      output += chunk;
      if (output.length > 4_000_000) child.kill();
    });
    child.stderr.resume();
    child.on("error", (error) => {
      clearTimeout(timer);
      reject(error);
    });
    child.on("close", (code) => {
      clearTimeout(timer);
      try {
        const data = JSON.parse(output);
        if (code || data.error)
          throw Object.assign(
            new Error(data.detail ?? data.message ?? "Family aspects unavailable"),
            { statusCode: 503 },
          );
        resolve(data as FamilyAspectsOutput);
      } catch (error) {
        reject(error);
      }
    });
    child.stdin.on("error", () => {});
    child.stdin.end(JSON.stringify(payload));
  });
}

/** Build bilingual placeholder Compatibility readings (no LLM). */
export function familyPlaceholderReadings(interpretation?: string) {
  const text = (interpretation ?? FAMILY_COMPATIBILITY_PLACEHOLDER).trim()
    ? (interpretation ?? FAMILY_COMPATIBILITY_PLACEHOLDER)
    : FAMILY_COMPATIBILITY_PLACEHOLDER;
  return {
    en: {
      title: "Family compatibility",
      sections: [
        {
          key: "overview",
          movement: 0,
          title: "Overview",
          text,
        },
      ],
    },
    tr: {
      title: "Aile uyumu",
      sections: [
        {
          key: "overview",
          movement: 0,
          title: "Genel bakış",
          text,
        },
      ],
    },
  };
}
