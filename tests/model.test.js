import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import {change,history,weekBefore,colorScale,formatRate} from "../public/lib/model.js";

test("前週が年をまたぐ場合と53週の年",()=>{
  assert.equal(weekBefore("2026-01"),"2025-52");
  assert.equal(weekBefore("2021-01"),"2020-53");
  assert.equal(weekBefore("2026-39"),"2026-38");
});
test("欠測と0を区別し、ゼロ除算を避ける",()=>{
  assert.equal(formatRate(0),"0.00");assert.equal(formatRate(null),"—");
  assert.equal(change(2,1).percent,100);
  assert.equal(change(0,2).percent,-100);
  assert.equal(change(2,0).percent,null);
  assert.equal(change(2,null).percent,null);
  assert.equal(change(2,1,"制度変更").percent,null);
});
test("直近10週は欠けた週を飛ばさず、年をまたぐ",()=>{
  const dataset={weeks:{"2026-01":{diseases:{flu:{rates:[1]}},source:{}},"2025-51":{diseases:{flu:{rates:[3]}},source:{}}}};
  const points=history(dataset,"2026-01","flu",0);
  assert.equal(points.length,10);
  assert.equal(points.at(-2).key,"2025-52");assert.equal(points.at(-2).rate,null);
  assert.equal(points.at(-3).rate,3);
});
test("色の階級は欠測・0・最大値を安全に処理",()=>{
  const scale=colorScale([0,1,5,null]);
  assert.equal(scale.max,5);assert.notEqual(scale.color(0),scale.color(null));
  assert.equal(scale.color(5),"#c92a24");assert.equal(colorScale([null]).max,0);
});
test("同梱した一次データ由来JSONの値と全都道府県を確認",()=>{
  const data=JSON.parse(fs.readFileSync(new URL("../public/data/data.json",import.meta.url)));
  assert.equal(data.prefectures.length,47);
  const value=data.weeks["2026-39"].diseases.influenza;
  assert.ok(value.rates[0]===null || typeof value.rates[0]==="number");
  for(const [key,week] of Object.entries(data.weeks)) {
    assert.match(week.source.csv_url,/id-info\.jihs\.go\.jp|idsc\.nih\.go\.jp/);
    assert.ok(week.source.retrieved_at);
    for(const values of Object.values(week.diseases)) assert.equal(values.rates.length,48,key);
  }
});
