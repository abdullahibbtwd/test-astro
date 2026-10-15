import { Component, useEffect, useState, type ComponentType, type ReactNode } from "react";
import { TurboModuleRegistry, View } from "react-native";
import { ErrorNotice, Skeleton } from "../../design/components";
import type {
  AcgLines,
  AcgHeat,
  Body,
  Angle,
  Destination,
} from "../../../contracts/spec-types";

export { planetColors } from "./mapColors";

export type MapCanvasProps = {
  fill?: boolean;
  lines?: AcgLines;
  heat?: AcgHeat;
  bodies: Body[];
  parans?: boolean;
  center?: [number, number];
  onLine?: (body: Body, angle: Angle) => void;
  onPoint?: (point: [number, number], zoom: number, long: boolean) => void;
  destinations?: Destination[];
  onDestination?: (place: Destination) => void;
  emphasized?: string[];
};

const MAP_UNAVAILABLE = new Error(
  "MapLibre native module (MLRN) is not in this iOS build. Rebuild with MapLibre pods linked, or use Android preview.",
);

/** Non-throwing probe — never call getEnforcing / never import MapLibre until this is true. */
function hasMapLibreNative(): boolean {
  try {
    return TurboModuleRegistry.get("MLRNCameraModule") != null;
  } catch {
    return false;
  }
}

class MapErrorBoundary extends Component<
  { children: ReactNode; onError: () => void },
  { broken: boolean }
> {
  state = { broken: false };

  static getDerivedStateFromError() {
    return { broken: true };
  }

  componentDidCatch() {
    this.props.onError();
  }

  render() {
    if (this.state.broken) return null;
    return this.props.children;
  }
}

/**
 * Lazily loads MapLibre only when MLRNCameraModule is in the binary.
 * Otherwise shows a notice — no MapLibre JS import, no redbox.
 */
export function MapCanvas(props: MapCanvasProps) {
  const [Native, setNative] = useState<ComponentType<MapCanvasProps> | null>(
    null,
  );
  const [failed, setFailed] = useState(() => !hasMapLibreNative());

  useEffect(() => {
    if (failed) return;
    let alive = true;
    void import("./MapCanvasNative")
      .then((mod) => {
        if (alive) setNative(() => mod.MapCanvasNative as ComponentType<MapCanvasProps>);
      })
      .catch(() => {
        if (alive) setFailed(true);
      });
    return () => {
      alive = false;
    };
  }, [failed]);

  if (failed)
    return (
      <View style={{ flex: 1, justifyContent: "center", padding: 24 }}>
        <ErrorNotice error={MAP_UNAVAILABLE} />
      </View>
    );
  if (!Native) return <Skeleton variant="block" />;
  return (
    <MapErrorBoundary onError={() => setFailed(true)}>
      <Native {...props} />
    </MapErrorBoundary>
  );
}
