import {COLORS, finite, formatRate, weekBefore, change, history, colorScale} from "./lib/model.js";

const $ = id => document.getElementById(id);
let dataset, keys, state = { disease: "influenza", key: null, prefecture: "13" };
let trendStart = null;
const nf = new Intl.NumberFormat("ja-JP");
const stamp = value => value ? new Intl.DateTimeFormat("ja-JP", { timeZone: "Asia/Tokyo", dateStyle: "medium", timeStyle: "medium" }).format(new Date(value)) + "（日本時間）" : "—";
const dateLabel = value => value.replaceAll("-", "/");
const keyLabel = key => {const [y,w] = key.split("-"); return `${y}年第${Number(w)}週`;};
function options(select, values, chosen) {
  select.replaceChildren(...values.map(([value, label]) => {
    const option = document.createElement("option"); option.value = value; option.textContent = label; return option;
  }));
  select.value = chosen; select.disabled = false;
}
function fillWeeks() {
  const year = $("year").value;
  const available = keys.filter(key => key.startsWith(year + "-") && dataset.weeks[key].diseases[state.disease]);
  if (!available.includes(state.key)) state.key = available.at(-1);
  options($("week"), available.slice().reverse().map(key => [key, `第${Number(key.split("-")[1])}週`]), state.key);
}
function fillYears() {
  const available = keys.filter(key => dataset.weeks[key].diseases[state.disease]);
  const years = [...new Set(available.map(key => key.split("-")[0]))].reverse();
  const year = state.key?.split("-")[0];
  options($("year"), years.map(y => [y, `${y}年`]), years.includes(year) ? year : years[0]);
  fillWeeks();
}
function applyClass(element, value) {
  element.classList.toggle("positive", finite(value) && value > 0);
  element.classList.toggle("negative", finite(value) && value < 0);
}
function changeText(result) {
  return finite(result.percent) ? `${result.percent > 0 ? "+" : ""}${result.percent.toFixed(1)}%` : "算出不可";
}
function breakReason() {
  return dataset.comparison_breaks?.find(point => point.week === state.key)?.reason || null;
}
function selectedDisease() {return dataset.diseases.find(d => d.id === state.disease);}
function selectedWeek() {return dataset.weeks[state.key];}
function difference(index) {
  const current = selectedWeek().diseases[state.disease].rates[index];
  const prior = dataset.weeks[weekBefore(state.key)]?.diseases[state.disease]?.rates[index] ?? null;
  return change(current, prior, breakReason());
}
function sourceLink(element, url) {element.href = url; element.textContent = url;}
function renderSources() {
  const record = selectedWeek(), source = record.source;
  sourceLink($("source-page"), source.page_url); sourceLink($("source-csv"), source.csv_url);
  $("retrieved-at").textContent = stamp(source.retrieved_at);
  $("checked-at").textContent = stamp(dataset.last_checked_at);
  $("source-dates").textContent = `${record.source_created_on ?? "不明"} / ${source.published_on ?? "不明"}`;
  const note = dataset.comparison_breaks?.[0];
  $("method-note").replaceChildren();
  if (note) {
    $("method-note").append(document.createTextNode(note.reason + " "));
    const link = document.createElement("a"); link.href = note.source_url; link.textContent = "制度変更についての一次資料"; link.target = "_blank"; link.rel = "noopener noreferrer"; $("method-note").append(link);
  }
}
function renderLegend(scale) {
  const items = COLORS.map((color, i) => {
    const item = document.createElement("span"); item.className = "legend-item";
    const swatch = document.createElement("i"); swatch.className = "legend-swatch"; swatch.style.background = color;
    const low = scale.top * i / 5, high = scale.top * (i + 1) / 5;
    item.append(swatch, document.createTextNode(`${low.toFixed(2)}–${high.toFixed(2)}${i === 4 ? "" : "未満"}`)); return item;
  });
  const missing = document.createElement("span"); missing.className = "legend-item";
  const swatch = document.createElement("i"); swatch.className = "legend-swatch legend-missing";
  missing.append(swatch, document.createTextNode("数値なし")); items.push(missing);
  $("legend").replaceChildren(...items);
}
function renderOverview() {
  const record = selectedWeek(), values = record.diseases[state.disease];
  $("period").textContent = `${dateLabel(record.start)} – ${dateLabel(record.end)}`;
  $("national-rate").textContent = formatRate(values.rates[0]);
  $("national-reports").textContent = finite(values.reports[0]) ? nf.format(values.reports[0]) : "—";
  const diff = difference(0); $("national-change").textContent = changeText(diff); $("national-change").title = diff.reason || "（当週－前週）÷前週 × 100"; applyClass($("national-change"), diff.percent);
  const validKeys = keys.filter(key => dataset.weeks[key].diseases[state.disease]);
  $("prev-week").disabled = validKeys.indexOf(state.key) <= 0;
  $("next-week").disabled = validKeys.indexOf(state.key) === validKeys.length - 1;
}
function renderMapAndList() {
  const rates = selectedWeek().diseases[state.disease].rates;
  const scale = colorScale(rates.slice(1)); renderLegend(scale);
  for (const pref of dataset.prefectures) {
    const node = $("map").querySelector(`[data-code="${pref.code}"]`);
    node.style.fill = scale.color(rates[pref.index]); node.classList.toggle("selected", state.prefecture === pref.code);
    const label = `${pref.name}：${formatRate(rates[pref.index])} 人/定点`;
    node.setAttribute("aria-label", label); node.setAttribute("aria-pressed", String(state.prefecture === pref.code)); node.querySelector("title").textContent = label;
  }
  $("pref-buttons").replaceChildren(...dataset.prefectures.map(pref => {
    const button = document.createElement("button"); button.type = "button"; button.className = "pref-button"; button.dataset.prefecture = pref.code;
    button.classList.toggle("selected", pref.code === state.prefecture); button.setAttribute("aria-pressed", String(pref.code === state.prefecture));
    const label = document.createElement("span"), dot = document.createElement("i"), value = document.createElement("span"); dot.className = "pref-dot";
    dot.style.background = finite(rates[pref.index]) ? scale.color(rates[pref.index]) : "#d7dfe6";
    label.append(dot, document.createTextNode(pref.name)); value.textContent = formatRate(rates[pref.index]); button.append(label, value);
    button.addEventListener("click", () => selectPrefecture(pref.code)); return button;
  }));
}
function svgNode(tag, attrs = {}, text = null) {
  const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [key,value] of Object.entries(attrs)) node.setAttribute(key, value);
  if (text !== null) node.textContent = text; return node;
}
function renderTrend(points, name) {
  const w = 360, h = 195, left = 37, right = 12, top = 18, bottom = 34;
  const svg = svgNode("svg", {viewBox:`0 0 ${w} ${h}`, role:"img", "aria-label":`${name}の選択期間${points.length}週の定点当たり報告数。数値は下の表で確認できます。`});
  const maximum = Math.max(1, ...points.map(p => finite(p.rate) ? p.rate : 0));
  const x = i => left + i * (w - left - right) / Math.max(1,points.length-1);
  const y = rate => h - bottom - rate / maximum * (h - top - bottom);
  for (let i=0;i<=3;i++) {
    const rate = maximum * i / 3;
    svg.append(svgNode("line", {x1:left,y1:y(rate),x2:w-right,y2:y(rate),stroke:"#e3ebf1","stroke-dasharray":"3 3"}));
    svg.append(svgNode("text", {x:left-7,y:y(rate)+3,"text-anchor":"end",fill:"#6b8091","font-size":"9"}, rate.toFixed(maximum<3?2:1)));
  }
  let segment = [];
  const flush = () => {if (segment.length > 1) svg.append(svgNode("polyline", {points:segment.join(" "),fill:"none",stroke:"#287f85","stroke-width":"2.3","stroke-linejoin":"round"})); segment = [];};
  points.forEach((point,i) => {
    const breaks = dataset.comparison_breaks?.some(p => p.week === point.key);
    if (breaks) flush();
    if (finite(point.rate)) segment.push(`${x(i)},${y(point.rate)}`); else flush();
  }); flush();
  points.forEach((point,i) => {
    if (finite(point.rate)) {
      const circle = svgNode("circle",{cx:x(i),cy:y(point.rate),r:i===points.length-1?4:2.5,fill:i===points.length-1?"#157b76":"#fff",stroke:"#287f85","stroke-width":"1.5"});
      circle.append(svgNode("title",{},`${keyLabel(point.key)}：${formatRate(point.rate)}`)); svg.append(circle);
    }
    if (i % Math.max(1,Math.ceil((points.length-1)/5)) === 0 || i === points.length-1) svg.append(svgNode("text",{x:x(i),y:h-13,"text-anchor":"middle",fill:"#6b8091","font-size":"9"},`${point.key.slice(2,4)}/${Number(point.key.split("-")[1])}週`));
  });
  $("trend").replaceChildren(svg);
  $("trend-table").replaceChildren(...points.map(point => {
    const row = document.createElement("tr");
    const week = document.createElement("td"), value = document.createElement("td"), source = document.createElement("td");
    week.textContent = keyLabel(point.key); value.textContent = formatRate(point.rate);
    if (point.source) {
      const link = document.createElement("a"); link.href = point.source.csv_url; link.target = "_blank"; link.rel = "noopener noreferrer"; link.textContent = "CSV"; link.title = `取得：${stamp(point.source.retrieved_at)}`; source.append(link);
    } else source.textContent = "未収録";
    row.append(week,value,source); return row;
  }));
  const missing = points.filter(point => !finite(point.rate)).length;
  $("trend-note").textContent = `${keyLabel(points[0].key)} – ${keyLabel(points.at(-1).key)}${missing ? ` ／ 数値なし ${missing}週（線はつないでいません）` : ""}`;
}
function renderDetail() {
  const pref = dataset.prefectures.find(p => p.code === state.prefecture), values = selectedWeek().diseases[state.disease];
  $("pref-title").textContent = pref.name; $("prefecture").value = pref.code;
  $("detail-disease").textContent = `${selectedDisease().name} · ${keyLabel(state.key)}`;
  $("pref-rate").textContent = formatRate(values.rates[pref.index]);
  const diff = difference(pref.index); $("pref-change").textContent = changeText(diff); applyClass($("pref-change"), diff.percent);
  const rateMark = values.rate_marks[pref.index];
  const rawNote = !finite(values.rates[pref.index]) ? `原CSVの表記：${rateMark ? `「${rateMark}」` : "空欄"}。0への換算はしていません。` : "";
  $("change-note").textContent = [diff.reason, finite(diff.delta) ? `前週との差：${diff.delta>0?"+":""}${diff.delta.toFixed(2)} 人/定点` : null, rawNote].filter(Boolean).join(" ／ ");
  $("pref-reports").textContent = finite(values.reports[pref.index]) ? nf.format(values.reports[pref.index]) : "—";
  if(trendStart && trendStart>state.key) trendStart=state.key;
  options($("range-start"),[["","自動（直近10週）"],...keys.filter(k=>k<=state.key).map(k=>[k,keyLabel(k)])],trendStart || "");
  options($("range-end"),keys.filter(k=>dataset.weeks[k].diseases[state.disease]).map(k=>[k,keyLabel(k)]),state.key);
  const count = trendStart ? Math.round((Date.parse(selectedWeek().start)-Date.parse(dataset.weeks[trendStart].start))/604800000)+1 : 10;
  $("trend-title").textContent=trendStart ? "指定期間の推移" : "直近10週の推移";
  renderTrend(history(dataset,state.key,state.disease,pref.index,count),pref.name);
}
function selectPrefecture(code) {state.prefecture=code;renderMapAndList();renderDetail();saveUrl();}
function saveUrl() {const params = new URLSearchParams({disease:state.disease,year:state.key.split("-")[0],week:String(Number(state.key.split("-")[1])),prefecture:state.prefecture}); window.history.replaceState(null,"",`${location.pathname}?${params}`);}
function render() {renderOverview();renderMapAndList();renderDetail();renderSources();saveUrl();}
function moveWeek(offset) {const available=keys.filter(key=>dataset.weeks[key].diseases[state.disease]);const next=available[available.indexOf(state.key)+offset];if(next){state.key=next;fillYears();render();}}
async function init() {
  try {
    const [dataResponse,mapResponse] = await Promise.all([fetch("./data/data.json"),fetch("./assets/japan.svg")]);
    if (!dataResponse.ok || !mapResponse.ok) throw new Error("静的データまたは地図を取得できませんでした");
    dataset = await dataResponse.json(); keys = Object.keys(dataset.weeks).sort();
    if(dataset.schema_version!==1 || dataset.prefectures.length!==47 || !keys.length) throw new Error("データ形式が想定と異なります");
    const parser = new DOMParser(); const svgDocument = parser.parseFromString(await mapResponse.text(), "image/svg+xml");
    if(svgDocument.querySelector("parsererror")) throw new Error("地図データを読み込めませんでした");
    $("map").replaceChildren(document.importNode(svgDocument.documentElement,true));
    const svg = $("map").querySelector("svg"), defs = svgNode("defs"), pattern = svgNode("pattern",{id:"missing-data",patternUnits:"userSpaceOnUse",width:8,height:8});
    pattern.append(svgNode("rect",{width:8,height:8,fill:"#e9edf1"}),svgNode("path",{d:"M-2 2 L2 -2 M0 8 L8 0 M6 10 L10 6",stroke:"#c9d4dd","stroke-width":2})); defs.append(pattern);svg.prepend(defs);
    const mapped = [...svg.querySelectorAll(".prefecture[data-code]")];
    if(mapped.length!==47 || new Set(mapped.map(n=>n.dataset.code)).size!==47) throw new Error("地図の都道府県対応が不正です");
    for(const node of mapped) {
      node.dataset.code = node.dataset.code.padStart(2,"0");
      node.setAttribute("tabindex","0");node.setAttribute("role","button");node.append(svgNode("title"));
      node.addEventListener("click",()=>selectPrefecture(node.dataset.code));
      node.addEventListener("keydown",event=>{if(event.key==="Enter"||event.key===" "){event.preventDefault();selectPrefecture(node.dataset.code);}});
    }
    const query = new URLSearchParams(location.search);
    state.key=dataset.latest;
    const requested=`${query.get("year")}-${String(query.get("week")).padStart(2,"0")}`;
    if(dataset.weeks[requested]) state.key=requested;
    if(dataset.diseases.some(d=>d.id===query.get("disease"))) state.disease=query.get("disease");
    if(dataset.prefectures.some(p=>p.code===query.get("prefecture"))) state.prefecture=query.get("prefecture");
    options($("disease"),dataset.diseases.map(d=>[d.id,d.name]),state.disease);fillYears();
    options($("prefecture"),dataset.prefectures.map(p=>[p.code,p.name]),state.prefecture);
    $("latest-label").textContent=`最新公開データ：${keyLabel(dataset.latest)}`;
    $("disease").addEventListener("change",()=>{state.disease=$("disease").value;fillYears();render();});
    $("year").addEventListener("change",()=>{fillWeeks();render();});
    $("week").addEventListener("change",()=>{state.key=$("week").value;render();});
    $("prefecture").addEventListener("change",()=>selectPrefecture($("prefecture").value));
    $("range-start").addEventListener("change",()=>{trendStart=$("range-start").value || null;renderDetail();});
    $("range-end").addEventListener("change",()=>{state.key=$("range-end").value;fillYears();render();});
    $("update-data").addEventListener("click",async()=>{
      const button=$("update-data"),status=$("update-status");button.disabled=true;status.textContent="公式CSVを取得・確認しています。数分かかる場合があります。";
      try {
        const response=await fetch("./api/update",{method:"POST",headers:{"X-IDWR-Update":"1"}});
        const result=await response.json();if(!response.ok) throw new Error(result.error || "更新に失敗しました");
        const dataResponse=await fetch("./data/data.json",{cache:"no-store"});if(!dataResponse.ok) throw new Error("更新後のデータを読み込めません");
        dataset=await dataResponse.json();keys=Object.keys(dataset.weeks).sort();state.key=dataset.latest;
        options($("disease"),dataset.diseases.map(d=>[d.id,d.name]),state.disease);fillYears();render();
        $("latest-label").textContent=`最新公開データ：${keyLabel(dataset.latest)}`;
        status.textContent=`更新確認完了：${keyLabel(dataset.latest)}。公式に未公開の週は表示しません。`;
      }catch(error){status.textContent=error.message;}finally{button.disabled=false;}
    });
    if(location.protocol!=="file:") {
      fetch("./api/capabilities",{cache:"no-store"}).then(r=>r.ok?r.json():null).then(value=>{if(value?.update){$("update-data").hidden=false;$("update-data").disabled=false;$("update-status").textContent="ボタンを押すと、JIHSの最新公開データを取得します。";}}).catch(()=>{});
    }
    $("prev-week").addEventListener("click",()=>moveWeek(-1));$("next-week").addEventListener("click",()=>moveWeek(1));
    render();
  } catch(error) {
    $("error").hidden=false;$("error").textContent=`表示できませんでした：${error.message}。HTTPサーバーで開いていることと、data/data.jsonが存在することを確認してください。`;
    $("latest-label").textContent="読み込み失敗";
  }
}
init();
