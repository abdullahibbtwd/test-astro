import { space as dsSpace } from "../../design-system/theme/tokens";
import {
  Children,
  Fragment,
  isValidElement,
  cloneElement,
  memo,
  useMemo,
  type ReactNode,
  type ReactElement,
} from "react";
import { FlatList, SectionList, View, type FlatListProps } from "react-native";
import { BottomSheetFlatList } from "@gorhom/bottom-sheet";
function flatten(children: ReactNode, prefix = ""): ReactElement[] {
  return Children.toArray(children).flatMap((child, index) => {
    if (!isValidElement(child)) return [];
    const key = `${prefix}/${child.key ?? index}`;
    return child.type === Fragment
      ? flatten((child.props as { children: ReactNode }).children, key)
      : [cloneElement(child, { key })];
  });
}
const ContentRow = memo(({ item }: { item: ReactElement }) => (
  <View style={{ marginBottom: dsSpace[4] }}>{item}</View>
));
const renderItem = ({ item }: { item: ReactElement }) => (
  <ContentRow item={item} />
);
const keyExtractor = (item: ReactElement, index: number) =>
  String(item.key ?? index);
export type ContentListProps = Pick<
  FlatListProps<ReactElement>,
  "onEndReached" | "refreshing" | "onRefresh" | "ListEmptyComponent"
>;
/** Virtualizes keyed content blocks; fragments and arrays never become giant list rows. */
export function ContentList({
  children,
  sheet = false,
  ...props
}: { children: ReactNode; sheet?: boolean } & ContentListProps) {
  const data = useMemo(() => flatten(children), [children]);
  const List = sheet
    ? BottomSheetFlatList<ReactElement>
    : FlatList<ReactElement>;
  return (
    <List
      data={data}
      renderItem={renderItem}
      keyExtractor={keyExtractor}
      initialNumToRender={8}
      maxToRenderPerBatch={8}
      windowSize={7}
      onEndReachedThreshold={0.5}
      keyboardShouldPersistTaps="handled"
      contentContainerStyle={{ paddingHorizontal: dsSpace[8], paddingTop: dsSpace[6], paddingBottom: dsSpace[12] }}
      {...props}
    />
  );
}

export function ContentSections({
  sections,
  header,
  footer,
}: {
  sections: { key: string; header: ReactNode; children: ReactNode }[];
  header?: ReactElement;
  footer?: ReactElement;
}) {
  const data = useMemo(
    () =>
      sections.map((section) => ({
        key: section.key,
        header: section.header,
        data: flatten(section.children, section.key),
      })),
    [sections],
  );
  return (
    <SectionList
      sections={data}
      renderItem={renderItem}
      keyExtractor={keyExtractor}
      renderSectionHeader={({ section }) => (
        <View style={{ marginBottom: dsSpace[4] }}>{section.header}</View>
      )}
      ListHeaderComponent={header}
      ListFooterComponent={footer}
      stickySectionHeadersEnabled={false}
      initialNumToRender={8}
      maxToRenderPerBatch={8}
      windowSize={7}
      contentContainerStyle={{ paddingHorizontal: dsSpace[8], paddingTop: dsSpace[6], paddingBottom: dsSpace[12] }}
      keyboardShouldPersistTaps="handled"
    />
  );
}
