import type { toWheelInput } from "./adapter";
export type WheelInput = ReturnType<typeof toWheelInput>;
export interface WheelOptions {
  theme?: string;
  degreeLabels?: boolean;
  fortune?: boolean;
  applyingStyle?: boolean;
  highlight?: {
    highlight_points?: string[];
    highlight_relations?: [string, string][];
  } | null;
}
