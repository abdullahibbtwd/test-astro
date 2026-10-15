import { space as dsSpace } from "../../design-system/theme/tokens";
import { FlatList } from "react-native";
import { Screen } from "../../design/components";
import { SavedReportRow } from "./ReportsScreen";
import type { ReportRef } from "../../../contracts/spec-types";
const records = Array.from({ length: 200 }, (_, i) => ({
  report_id: `audit-${i}`,
  type: "natal",
  title: `Test report ${i + 1}`,
  subtitle: "Local scrolling fixture",
  created_at: "2026-10-05T12:00:00Z",
  route: "/(tabs)/chart",
})) as ReportRef[];
const noop = () => {};
export function ListAudit() {
  return (
    <Screen scroll={false} title="200 test reports">
      <FlatList
        data={records}
        keyExtractor={(item) => item.report_id}
        initialNumToRender={8}
        maxToRenderPerBatch={8}
        windowSize={7}
        contentContainerStyle={{ paddingHorizontal: 20, paddingBottom: dsSpace[8] }}
        renderItem={({ item }) => (
          <SavedReportRow item={item} onRemove={noop} onMenu={noop} />
        )}
      />
    </Screen>
  );
}
