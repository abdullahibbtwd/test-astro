import React from "react";
import { render } from "@testing-library/react-native";
import { SvgCss } from "react-native-svg/css";
import fs from "node:fs";
import { nativeWheelSvg } from "../../packages/wheel-core/native-svg";
import { computeWheel } from "../../packages/wheel-core/model";
import { toWheelInput } from "../../packages/wheel-core/adapter";
import type { ChartData } from "../../contracts/spec-types";
const flatten = (node: any): any[] =>
  Array.isArray(node)
    ? node.flatMap(flatten)
    : node && typeof node === "object"
      ? [node, ...flatten(node.children ?? [])]
      : [];
test("W4 native SVG props retain shared wheel chord coordinates for both themes", async () => {
  const chart = JSON.parse(
    fs.readFileSync("../backend/mock/fixtures/chart.1.json", "utf8"),
  ) as ChartData;
  const model = computeWheel(toWheelInput(chart));
  for (const theme of ["light", "dark"] as const) {
    const view = await render(
      <SvgCss xml={nativeWheelSvg(chart, theme)} width={335} height={335} />,
    );
    const nodes = flatten(view.toJSON());
    for (const chord of model.chords) {
      expect(
        nodes.some(
          (n) =>
            Number(n.props?.x1) === chord.a.x &&
            Number(n.props?.y1) === chord.a.y &&
            Number(n.props?.x2) === chord.b.x &&
            Number(n.props?.y2) === chord.b.y,
        ),
      ).toBe(true);
    }
    await view.unmount();
  }
});
