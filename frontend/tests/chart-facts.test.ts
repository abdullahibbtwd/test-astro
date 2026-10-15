import { test } from "node:test";
import assert from "node:assert/strict";
import { fixture } from "../../backend/mock/fixtures";
import type { ChartData, NatalReading } from "../contracts/spec-types";
import { degrees, axisPoint, isRetrograde, readingSections, aspectOrder } from "../src/features/chart/facts";
test("chart formatting never rounds a position into the next sign or marks nodes retrograde", () => {
 assert.equal(degrees(6+56/60), "6°56′"); assert.equal(degrees(29.999999), "29°59′");
 const chart=fixture("chart.1") as ChartData;
 for(const p of chart.points.filter(p=>p.body.endsWith("_node"))) assert.equal(isRetrograde({...p,retrograde:true}),false);
 assert.equal(axisPoint(chart,"DSC").longitude,(chart.axes.asc.longitude+180)%360);
 assert.equal(axisPoint(chart,"IC").longitude,(chart.axes.mc.longitude+180)%360);
 assert.deepEqual(aspectOrder,["conjunction","opposition","square","trine","sextile"]);
});
test("detail links reuse only existing reading sections with no duplicates", () => {
 const chart=fixture("chart.1") as ChartData, reading=fixture("natal.1.en") as NatalReading;
 assert.deepEqual(readingSections(chart,reading,{kind:"body",body:"sun"}).map(s=>s.key),reading.sections.filter(s=>["sun_house","core_identity"].includes(s.key)).map(s=>s.key));
 for(let index=0;index<chart.aspects.length;index++) { const sections=readingSections(chart,reading,{kind:"aspect",index}); assert.equal(sections.length,new Set(sections.map(s=>s.key)).size); sections.forEach(s=>assert.ok(reading.sections.includes(s))); }
 const house=readingSections(chart,reading,{kind:"house",house:9}); assert.ok(house.length); assert.ok(house.every(s=>s.house===9));
});
