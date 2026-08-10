(() => {
  const dashboard = document.querySelector('#bbqc-analytics');
  if (!dashboard) return;

  const rows = [...document.querySelectorAll('#hybrid-table tbody tr')];
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const palette = {
    ready: '#3b8064', candidate: '#d7301f', complete: '#276b52', missing: '#b8b3a8',
    match: '#3b8064', mismatch: '#d7301f', incomplete: '#8f948f', pending: '#c49a2f',
    pass: '#2f7d5b', fail: '#d7301f', 'follow-up': '#c48a28', review: '#4e7da6',
    note: '#8a7f70', other: '#735b8f', unreviewed: '#c9c5ba'
  };

  const titleCase = (value) => String(value || '').replace(/(^|-)([a-z])/g, (_, dash, char) => `${dash ? ' ' : ''}${char.toUpperCase()}`);
  const number = (value) => Number.parseInt(value || '0', 10) || 0;
  const countBy = (items, keyFn) => items.reduce((acc, item) => {
    const key = keyFn(item);
    acc[key] = (acc[key] || 0) + 1;
    return acc;
  }, {});

  const records = rows.map((row) => {
    const etroc = row.cells[2]?.textContent.trim() || '';
    const target = row.querySelector('[data-comments-summary]')?.dataset.commentsTarget || '';
    return {
      target,
      wafer: etroc.split('-')[0] || 'Unknown',
      candidate: number(row.dataset.noball) > 0,
      xray: row.dataset.xray === '1',
      nw: row.dataset.nw === '1',
      missing: row.dataset.missing === '1',
      consistency: row.dataset.consistency || 'review-pending'
    };
  });

  const state = dashboard.querySelector('[data-analytics-state]');
  const setState = (text, mode) => {
    if (!state) return;
    state.textContent = text;
    state.classList.toggle('is-live', mode === 'live');
    state.classList.toggle('is-degraded', mode === 'degraded');
  };

  if (!records.length) {
    setState('Dashboard data unavailable', 'degraded');
    dashboard.querySelectorAll('[data-chart-body]').forEach((node) => {
      node.innerHTML = '<div class="analytics-empty">No hybrid rows were found.</div>';
    });
    return;
  }

  const total = records.length;
  const candidate = records.filter((record) => record.candidate).length;
  const noOpticalCandidate = total - candidate;
  const evidenceComplete = records.filter((record) => !record.missing).length;
  const evidence = {
    Optical: total,
    'X-ray': records.filter((record) => record.xray).length,
    'NW scan': records.filter((record) => record.nw).length
  };
  const concordance = countBy(records, (record) => record.consistency);
  const wafer = records.reduce((acc, record) => {
    const item = acc[record.wafer] || { total: 0, candidate: 0 };
    item.total += 1;
    item.candidate += record.candidate ? 1 : 0;
    acc[record.wafer] = item;
    return acc;
  }, {});

  const setKpi = (name, value, suffix = '') => {
    const node = dashboard.querySelector(`[data-kpi="${name}"]`);
    if (!node) return null;
    node.dataset.value = String(value);
    node.dataset.suffix = suffix;
    node.textContent = reducedMotion ? `${value}${suffix}` : `0${suffix}`;
    return node;
  };
  setKpi('total', total);
  setKpi('candidate', candidate);
  setKpi('complete', evidenceComplete);

  function renderDonut(container, segments, centerValue, centerLabel, ariaLabel) {
    const valid = segments.filter((segment) => segment.value > 0);
    const sum = valid.reduce((acc, segment) => acc + segment.value, 0) || 1;
    let offset = 0;
    const circles = valid.map((segment) => {
      const pct = segment.value / sum * 100;
      const circle = `<circle class="donut-segment" pathLength="100" cx="50" cy="50" r="39" stroke="${segment.color}" data-dash="${pct.toFixed(3)} ${(100 - pct).toFixed(3)}" stroke-dashoffset="${(-offset).toFixed(3)}"></circle>`;
      offset += pct;
      return circle;
    }).join('');
    const legend = valid.map((segment) => `<div class="analytics-legend-row"><i style="background:${segment.color}"></i><span>${segment.label}</span><strong>${segment.value}</strong></div>`).join('');
    container.innerHTML = `<div class="analytics-donut"><svg viewBox="0 0 100 100" role="img" aria-label="${ariaLabel}"><circle class="donut-track" cx="50" cy="50" r="39"></circle>${circles}</svg><div class="analytics-donut-center"><strong>${centerValue}</strong><span>${centerLabel}</span></div></div><div class="analytics-legend">${legend}</div>`;
  }

  function renderBars(container, entries, maxValue) {
    container.innerHTML = `<div class="analytics-bars">${entries.map((entry) => {
      const pct = maxValue ? Math.max(0, Math.min(100, entry.value / maxValue * 100)) : 0;
      return `<div class="analytics-bar-row"><div class="analytics-bar-label"><span>${entry.label}</span><strong>${entry.value} / ${maxValue}</strong></div><div class="analytics-bar-track"><div class="analytics-bar-fill" style="--bar-pct:${pct.toFixed(2)}%;--bar-color:${entry.color}"></div></div></div>`;
    }).join('')}</div>`;
  }

  renderDonut(
    dashboard.querySelector('#screening-chart [data-chart-body]'),
    [
      { label: 'No optical no-ball candidate', value: noOpticalCandidate, color: palette.ready },
      { label: 'Screening candidate', value: candidate, color: palette.candidate }
    ],
    total,
    'hybrids',
    `${noOpticalCandidate} hybrids without an optical no-ball candidate and ${candidate} screening candidates out of ${total} hybrids`
  );

  renderBars(
    dashboard.querySelector('#evidence-chart [data-chart-body]'),
    Object.entries(evidence).map(([label, value], index) => ({
      label,
      value,
      color: index === 2 && value < total ? palette.pending : palette.complete
    })),
    total
  );

  const concordanceOrder = ['match', 'mismatch', 'incomplete', 'review-pending'];
  const concordanceLabels = { match: 'Match', mismatch: 'Mismatch', incomplete: 'Incomplete', 'review-pending': 'Review pending' };
  renderBars(
    dashboard.querySelector('#concordance-chart [data-chart-body]'),
    concordanceOrder.map((key) => ({
      label: concordanceLabels[key],
      value: concordance[key] || 0,
      color: palette[key === 'review-pending' ? 'pending' : key]
    })),
    total
  );

  const waferMax = Math.max(...Object.values(wafer).map((item) => item.total));
  const waferBody = dashboard.querySelector('#wafer-chart [data-chart-body]');
  const waferBars = document.createElement('div');
  waferBars.className = 'analytics-bars';
  Object.entries(wafer).sort(([a], [b]) => a.localeCompare(b)).forEach(([name, item]) => {
    const totalPct = item.total / waferMax * 100;
    const candidatePct = item.candidate / waferMax * 100;
    const row = document.createElement('div');
    row.className = 'analytics-wafer-row';
    const label = document.createElement('span');
    label.className = 'analytics-wafer-name';
    label.textContent = name;
    const track = document.createElement('div');
    track.className = 'analytics-wafer-track';
    track.setAttribute('aria-label', `${name}: ${item.total} hybrids, ${item.candidate} screening candidates`);
    const totalBar = document.createElement('div');
    totalBar.className = 'analytics-wafer-total';
    totalBar.style.setProperty('--wafer-total', `${totalPct.toFixed(2)}%`);
    const candidateBar = document.createElement('div');
    candidateBar.className = 'analytics-wafer-candidate';
    candidateBar.style.setProperty('--wafer-candidate', `${candidatePct.toFixed(2)}%`);
    const value = document.createElement('span');
    value.className = 'analytics-wafer-value';
    value.textContent = `${item.candidate}/${item.total}`;
    track.append(totalBar, candidateBar);
    row.append(label, track, value);
    waferBars.append(row);
  });
  waferBody.replaceChildren(waferBars);

  function animateCounters(nodes = null) {
    const counters = nodes || [...dashboard.querySelectorAll('[data-kpi][data-value]')];
    if (reducedMotion) {
      counters.forEach((node) => { node.textContent = `${node.dataset.value}${node.dataset.suffix || ''}`; });
      return;
    }
    const startedAt = performance.now();
    const duration = 850;
    const tick = (now) => {
      const progress = Math.min(1, (now - startedAt) / duration);
      const eased = 1 - Math.pow(1 - progress, 3);
      counters.forEach((node) => {
        const finalValue = number(node.dataset.value);
        node.textContent = `${Math.round(finalValue * eased)}${node.dataset.suffix || ''}`;
      });
      if (progress < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  }

  let animated = false;
  function startAnimations() {
    if (animated) return;
    animated = true;
    dashboard.classList.add('is-animated');
    dashboard.querySelectorAll('.donut-segment').forEach((circle) => {
      circle.style.strokeDasharray = reducedMotion ? circle.dataset.dash : '0 100';
    });
    if (!reducedMotion) {
      requestAnimationFrame(() => requestAnimationFrame(() => {
        dashboard.querySelectorAll('.donut-segment').forEach((circle) => {
          circle.style.strokeDasharray = circle.dataset.dash;
        });
      }));
    }
    animateCounters();
  }

  if (reducedMotion || !('IntersectionObserver' in window)) {
    startAnimations();
  } else {
    const observer = new IntersectionObserver((entries) => {
      if (entries.some((entry) => entry.isIntersecting)) {
        observer.disconnect();
        startAnimations();
      }
    }, { threshold: 0.16 });
    observer.observe(dashboard);
  }

  async function loadReviewStatus() {
    const targets = [...new Set(records.map((record) => record.target).filter(Boolean))];
    if (!targets.length) throw new Error('No comment targets');
    const targetBatches = [];
    for (let index = 0; index < targets.length; index += 30) targetBatches.push(targets.slice(index, index + 30));
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 8000);
    let summaries;
    try {
      summaries = await Promise.all(targetBatches.map(async (batch) => {
        const url = `/api/comments/summary?${batch.map((target) => `target=${encodeURIComponent(target)}`).join('&')}`;
        const response = await fetch(url, { credentials: 'same-origin', signal: controller.signal });
        if (!response.ok) throw new Error(`Review summary ${response.status}`);
        return response.json();
      }));
    } finally {
      window.clearTimeout(timeout);
    }
    const summary = Object.assign({}, ...summaries);
    const statusCounts = { pass: 0, fail: 0, 'follow-up': 0, review: 0, note: 0, other: 0, unreviewed: 0 };
    let comments = 0;
    targets.forEach((target) => {
      const item = summary[target] || { count: 0, latest: null };
      comments += number(item.count);
      if (!item.count || !item.latest) {
        statusCounts.unreviewed += 1;
        return;
      }
      const status = String(item.latest?.status || '').toLowerCase();
      statusCounts[Object.hasOwn(statusCounts, status) ? status : 'other'] += 1;
    });
    const reviewed = targets.length - statusCounts.unreviewed;
    const reviewedNode = setKpi('reviewed', reviewed);
    const reviewBody = dashboard.querySelector('#review-chart [data-chart-body]');
    const order = ['pass', 'fail', 'follow-up', 'review', 'note', 'other', 'unreviewed'];
    renderDonut(
      reviewBody,
      order.map((key) => ({ label: key === 'unreviewed' ? 'No review comment' : titleCase(key), value: statusCounts[key], color: palette[key] })),
      reviewed,
      'reviewed',
      `${reviewed} reviewed and ${statusCounts.unreviewed} without review comments out of ${targets.length} hybrids`
    );
    const meta = dashboard.querySelector('[data-review-meta]');
    if (meta) meta.textContent = `${comments} active comments · latest status per hybrid`;
    setState('Static evidence + live reviewer status', 'live');
    if (animated) {
      reviewBody.querySelectorAll('.donut-segment').forEach((circle) => {
        circle.style.strokeDasharray = reducedMotion ? circle.dataset.dash : '0 100';
      });
      if (!reducedMotion) requestAnimationFrame(() => requestAnimationFrame(() => {
        reviewBody.querySelectorAll('.donut-segment').forEach((circle) => { circle.style.strokeDasharray = circle.dataset.dash; });
      }));
      animateCounters(reviewedNode ? [reviewedNode] : []);
    }
  }

  loadReviewStatus().catch(() => {
    const card = dashboard.querySelector('#review-chart');
    card?.classList.add('is-error');
    const body = card?.querySelector('[data-chart-body]');
    if (body) body.innerHTML = '<div class="analytics-empty">Live review status unavailable.<br>Static evidence charts remain valid.</div>';
    const reviewed = dashboard.querySelector('[data-kpi="reviewed"]');
    if (reviewed) reviewed.textContent = '—';
    setState('Static evidence ready · live review unavailable', 'degraded');
  });
})();
