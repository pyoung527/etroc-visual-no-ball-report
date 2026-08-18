(() => {
  "use strict";

  const EXPECTED_GROUPS = new Map([["HPK1", 8], ["HPK3", 9], ["LF1", 9], ["LF2", 9]]);
  const EXPECTED_SENSORS = 35;
  const TILES_PER_SENSOR = 256;
  const root = document.querySelector("#lgad-optical-analytics");
  const state = document.querySelector("[data-lgad-analytics-state]");

  globalThis.LGADOpticalStatsContract = Object.freeze({ summarizeInventory });
  if (!root || !state) return;

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = String(text);
    return node;
  }

  function summarizeInventory(items) {
    if (!Array.isArray(items) || items.length !== EXPECTED_SENSORS) {
      throw new Error("expected exactly 35 LGAD panorama records");
    }
    const sensors = new Set();
    const groups = new Map([...EXPECTED_GROUPS.keys()].map((group) => [group, 0]));
    items.forEach((item) => {
      if (!item || typeof item.sensor !== "string" || typeof item.group !== "string") {
        throw new Error("invalid LGAD panorama record");
      }
      if (!EXPECTED_GROUPS.has(item.group) || !item.sensor.startsWith(`${item.group}/`)) {
        throw new Error("LGAD source-group identity mismatch");
      }
      if (sensors.has(item.sensor)) throw new Error("duplicate LGAD sensor");
      sensors.add(item.sensor);
      groups.set(item.group, groups.get(item.group) + 1);
    });
    EXPECTED_GROUPS.forEach((expected, group) => {
      if (groups.get(group) !== expected) throw new Error(`unexpected ${group} panorama count`);
    });
    return {
      sensorCount: sensors.size,
      tileCount: sensors.size * TILES_PER_SENSOR,
      panoramaCount: items.length,
      groupCount: groups.size,
      groups: Object.fromEntries(groups),
    };
  }

  function collectInventory() {
    return [...document.querySelectorAll("#lgad-optical .lgad-card")].map((card) => {
      const group = card.closest(".lgad-group")?.querySelector(".wafer h2")?.textContent?.trim();
      return { sensor: card.dataset.sensor, group };
    });
  }

  function setKpi(name, value) {
    const node = root.querySelector(`[data-lgad-kpi="${name}"]`);
    if (!node) throw new Error(`missing LGAD KPI ${name}`);
    node.textContent = Number(value).toLocaleString("en-US");
  }

  function render(summary) {
    setKpi("sensors", summary.sensorCount);
    setKpi("tiles", summary.tileCount);
    setKpi("panoramas", summary.panoramaCount);
    setKpi("groups", summary.groupCount);

    const body = root.querySelector("[data-lgad-group-body]");
    if (!body) throw new Error("LGAD group chart is unavailable");
    const fragment = document.createDocumentFragment();
    EXPECTED_GROUPS.forEach((_expected, group) => {
      const count = summary.groups[group];
      const row = element("div", "optical-stat-row");
      const heading = element("div", "optical-stat-row-heading");
      const percent = 100 * count / summary.panoramaCount;
      heading.append(
        element("strong", "", group),
        element("span", "", `${count} / ${summary.panoramaCount} panoramas (${percent.toFixed(1)}%)`)
      );
      const track = element("div", "optical-stat-track");
      track.setAttribute("role", "img");
      track.setAttribute("aria-label", `${group}: ${count} of ${summary.panoramaCount} available panoramas`);
      const fill = element("span", "optical-stat-fill lgad nonzero");
      fill.style.width = `${percent}%`;
      track.append(fill);
      row.append(heading, track);
      fragment.append(row);
    });
    body.replaceChildren(fragment);
    root.setAttribute("aria-busy", "false");
    state.textContent = "35 / 35 panoramas available · 8,960 source tiles represented";
    state.classList.add("loaded");
  }

  function fail(error) {
    root.setAttribute("aria-busy", "false");
    state.textContent = "LGAD panorama statistics unavailable";
    state.classList.add("failed");
    const body = root.querySelector("[data-lgad-group-body]");
    if (body) {
      const message = element("p", "optical-chart-empty", "LGAD panorama statistics unavailable");
      message.setAttribute("role", "alert");
      body.replaceChildren(message);
    }
    console.error("LGAD optical statistics failed", error);
  }

  try {
    render(summarizeInventory(collectInventory()));
  } catch (error) {
    fail(error);
  }
})();
