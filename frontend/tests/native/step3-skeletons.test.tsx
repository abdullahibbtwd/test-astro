import React from "react";
import { render, screen } from "@testing-library/react-native";
import "../../src/i18n";
import { SolarReturnSkeleton } from "../../src/features/step3/SolarReturnSkeleton";
import { FamilyCompatibilitySkeleton } from "../../src/features/step3/FamilyCompatibilitySkeleton";
import {
  buildFamilySkeleton,
  buildSolarReturnSkeleton,
} from "../../src/features/step3/math";
import {
  FAMILY_COMPATIBILITY_PLACEHOLDER,
  PENDING_ASTROLOGER_BANNER_TEST_ID,
  SOLAR_RETURN_PLACEHOLDER,
  assertNoPendingAstrologerMarkers,
  findPendingAstrologerMarkers,
} from "../../src/features/step3/placeholders";
import type { ChartData } from "../../contracts/spec-types";

jest.mock("react-native-svg/css", () => ({
  SvgCss: "SvgCss",
}));
jest.mock("../../packages/wheel-core/native-svg", () => ({
  nativeWheelSvg: () => "<svg />",
}));

const chart = {
  profile_id: "p1",
  chart_key: "k1",
  utc: "2024-12-27T20:56:00Z",
  tz: "UTC",
  points: [
    {
      body: "sun",
      longitude: 276.6,
      sign: "capricorn",
      degree_in_sign: 6.6,
      house: 1,
      retrograde: false,
    },
  ],
  axes: {
    asc: { longitude: 0, sign: "aries", degree_in_sign: 0 },
    mc: { longitude: 270, sign: "capricorn", degree_in_sign: 0 },
  },
  houses: Array.from({ length: 12 }, (_, i) => ({
    house: i + 1,
    cusp_longitude: i * 30,
    sign: "aries",
    rulers: ["mars"],
    planets: [],
  })),
  aspects: [],
} as ChartData;

const solarModel = buildSolarReturnSkeleton({
  return_utc: "2024-12-27T20:56:50Z",
  year: 2024,
  chart,
  place_label: "Kano",
});

const familyModel = buildFamilySkeleton({
  relationship_type: "romantic",
  profile_a_label: "Ada",
  profile_b_label: "Bea",
  aspects: [
    {
      a_point: "Moon",
      b_point: "Sun",
      type: "trine",
      scheme: "modern",
      orb: 0.559,
      separation: 119.441,
      applying: true,
    },
  ],
});

const profiles = [
  { id: "a", label: "Ada" },
  { id: "b", label: "Bea" },
];

test("solar return skeleton renders mock data with chart and placeholder", async () => {
  await render(
    <SolarReturnSkeleton
      year={2024}
      onYearChange={() => {}}
      status="ready"
      model={solarModel}
    />,
  );
  expect(screen.getByTestId("solar-return-ready")).toBeOnTheScreen();
  expect(screen.getByTestId("solar-return-year-input")).toBeOnTheScreen();
  expect(screen.getByTestId(PENDING_ASTROLOGER_BANNER_TEST_ID)).toBeOnTheScreen();
  expect(screen.getByTestId("solar-return-placeholder")).toHaveTextContent(
    SOLAR_RETURN_PLACEHOLDER,
  );
  expect(screen.getByText(/find_solar_return_utc/)).toBeOnTheScreen();
  expect(screen.getByText(/compute_solar_return_chart/)).toBeOnTheScreen();
});

test("solar return loading and error states show", async () => {
  const loading = await render(
    <SolarReturnSkeleton
      year={2024}
      onYearChange={() => {}}
      status="loading"
      model={null}
    />,
  );
  expect(screen.getByTestId("solar-return-loading")).toBeOnTheScreen();
  await loading.rerender(
    <SolarReturnSkeleton
      year={2024}
      onYearChange={() => {}}
      status="error"
      model={null}
      error={new Error("boom")}
      onRetry={() => {}}
    />,
  );
  expect(screen.getByTestId("solar-return-error")).toBeOnTheScreen();
});

test("family skeleton renders aspects, loading, and error", async () => {
  const view = await render(
    <FamilyCompatibilitySkeleton
      profileA="a"
      profileB="b"
      profiles={profiles}
      onSelectA={() => {}}
      onSelectB={() => {}}
      relationshipType="romantic"
      onRelationshipType={() => {}}
      status="ready"
      model={familyModel}
      onCompute={() => {}}
    />,
  );
  expect(screen.getByTestId("family-compatibility-ready")).toBeOnTheScreen();
  expect(screen.getByTestId("aspect-Moon-Sun")).toBeOnTheScreen();
  expect(screen.getByTestId("family-compatibility-placeholder")).toHaveTextContent(
    FAMILY_COMPATIBILITY_PLACEHOLDER,
  );
  expect(screen.getByTestId(PENDING_ASTROLOGER_BANNER_TEST_ID)).toBeOnTheScreen();
  expect(screen.getByText(/compute_synastry_aspects/)).toBeOnTheScreen();

  await view.rerender(
    <FamilyCompatibilitySkeleton
      profileA="a"
      profileB="b"
      profiles={profiles}
      onSelectA={() => {}}
      onSelectB={() => {}}
      relationshipType="parent_child"
      onRelationshipType={() => {}}
      status="loading"
      model={null}
      onCompute={() => {}}
    />,
  );
  expect(screen.getByTestId("family-compatibility-loading")).toBeOnTheScreen();

  await view.rerender(
    <FamilyCompatibilitySkeleton
      profileA="a"
      profileB="b"
      profiles={profiles}
      onSelectA={() => {}}
      onSelectB={() => {}}
      relationshipType="sibling"
      onRelationshipType={() => {}}
      status="error"
      model={null}
      error={new Error("nope")}
      onCompute={() => {}}
      onRetry={() => {}}
    />,
  );
  expect(screen.getByTestId("family-compatibility-error")).toBeOnTheScreen();
});

test("pending-astrologer markers fail a release build gate", () => {
  const sample = `interpretation: ${SOLAR_RETURN_PLACEHOLDER}`;
  expect(findPendingAstrologerMarkers(sample).length).toBeGreaterThan(0);
  expect(() =>
    assertNoPendingAstrologerMarkers(sample, { isRelease: true }),
  ).toThrow(/pending-astrologer/);
  expect(() =>
    assertNoPendingAstrologerMarkers(sample, { isRelease: false }),
  ).not.toThrow();
});
