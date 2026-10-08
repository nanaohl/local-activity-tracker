(() => {
    const {
        OTHER_COLOR, pad, dateString, parseDate, hoursMinutes, compactDuration,
        escapeHtml, loadColors, iconHtml,
    } = window.ActivityCommon;

    const APPS_COLLAPSED = 12;
    const PLOT_HEIGHT = 220;
    const REFRESH_MS = 30000;
    const DAY_NAMES = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
    const MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    const MONTH_LONG = ['January', 'February', 'March', 'April', 'May', 'June', 'July',
        'August', 'September', 'October', 'November', 'December'];

    const $ = (id) => document.getElementById(id);
    const el = {
        periodButtons: document.querySelectorAll('.segmented button'),
        periodLabel: $('periodLabel'),
        prevBtn: $('prevBtn'),
        nextBtn: $('nextBtn'),
        todayBtn: $('todayBtn'),
        unidentified: $('unidentifiedInput'),
        tileTracked: $('tileTracked'),
        tileTrackedSub: $('tileTrackedSub'),
        tileActive: $('tileActive'),
        tileActiveSub: $('tileActiveSub'),
        tileThirdLabel: $('tileThirdLabel'),
        tileThird: $('tileThird'),
        tileThirdSub: $('tileThirdSub'),
        tileBusiestLabel: $('tileBusiestLabel'),
        tileBusiest: $('tileBusiest'),
        tileBusiestSub: $('tileBusiestSub'),
        chartTitle: $('chartTitle'),
        legend: $('legend'),
        yAxis: $('yAxis'),
        plot: $('plot'),
        xAxis: $('xAxis'),
        tooltip: $('tooltip'),
        appsBody: $('appsBody'),
        showAllBtn: $('showAllBtn'),
        empty: $('emptyState'),
        sideTitle: $('sideTitle'),
        sideList: $('sideList'),
        navTimeline: $('navTimeline'),
    };

    const params = new URLSearchParams(location.search);
    const state = {
        period: ['day', 'week', 'month'].includes(params.get('period')) ? params.get('period') : 'week',
        date: /^\d{4}-\d{2}-\d{2}$/.test(params.get('date') || '') ? params.get('date') : dateString(new Date()),
        unidentified: params.get('unidentified') === '1',
        data: null,
        colors: new Map(),
        expanded: new Set(),
        showAll: false,
    };

    // ---------- labels ----------

    function bucketDate(bucket) { return new Date(bucket.start); }

    function longDay(d) {
        return `${DAY_NAMES[d.getDay()]} ${d.getDate()} ${MONTH_NAMES[d.getMonth()]} ${d.getFullYear()}`;
    }

    function periodLabel(data) {
        const start = parseDate(data.start);
        const end = parseDate(data.end);
        if (data.period === 'day') return longDay(start);
        if (data.period === 'month') return `${MONTH_LONG[start.getMonth()]} ${start.getFullYear()}`;
        const sameMonth = start.getMonth() === end.getMonth();
        return sameMonth
            ? `${start.getDate()} – ${end.getDate()} ${MONTH_NAMES[end.getMonth()]} ${end.getFullYear()}`
            : `${start.getDate()} ${MONTH_NAMES[start.getMonth()]} – ${end.getDate()} ${MONTH_NAMES[end.getMonth()]} ${end.getFullYear()}`;
    }

    function bucketLabel(bucket, period, full) {
        const d = bucketDate(bucket);
        if (period === 'day') {
            return full ? `${pad(d.getHours())}:00 – ${pad((d.getHours() + 1) % 24)}:00` : `${d.getHours()}h`;
        }
        if (period === 'week') return full ? longDay(d) : `${DAY_NAMES[d.getDay()]} ${d.getDate()}`;
        return full ? longDay(d) : String(d.getDate());
    }

    function isCurrentBucket(bucket, period) {
        const d = bucketDate(bucket);
        const now = new Date();
        if (period === 'day') return dateString(d) === dateString(now) && d.getHours() === now.getHours();
        return dateString(d) === dateString(now);
    }

    // ---------- data ----------

    async function load() {
        const query = `period=${state.period}&date=${state.date}${state.unidentified ? '&unidentified=1' : ''}`;
        history.replaceState(null, '', `/summary?${query}`);
        const [res, colors] = await Promise.all([fetch(`/api/summary?${query}`), loadColors()]);
        if (!res.ok) return;
        const data = await res.json();
        if (data.period !== state.period) return; // a newer request superseded this one

        state.data = data;
        state.colors = colors;
        render();
    }

    function colorFor(app) { return state.colors.get(app) || OTHER_COLOR; }

    // ---------- rendering ----------

    function render() {
        const data = state.data;
        el.periodButtons.forEach((b) => {
            const active = b.dataset.period === state.period;
            b.classList.toggle('active', active);
            b.setAttribute('aria-selected', active);
        });
        el.periodLabel.textContent = periodLabel(data);
        el.nextBtn.disabled = data.end >= dateString(new Date());
        el.unidentified.checked = state.unidentified;
        el.navTimeline.href = `/?date=${state.period === 'day' ? data.start : dateString(new Date())}`;

        renderTiles(data);
        renderChart(data);
        renderApps(data);
        renderSide(data);
    }

    function renderTiles(data) {
        const totals = data.buckets.map((b) => Object.values(b.apps).reduce((s, v) => s + v, 0));

        el.tileTracked.textContent = hoursMinutes(data.total);
        el.tileTrackedSub.textContent = data.unidentified && !state.unidentified
            ? `+ ${compactDuration(data.unidentified)} unidentified (excluded)`
            : `${data.apps.length} app${data.apps.length === 1 ? '' : 's'}`;

        if (data.idle == null) {
            el.tileActive.textContent = '–';
            el.tileActiveSub.textContent = 'No idle data for this period yet';
        } else {
            el.tileActive.textContent = hoursMinutes(data.total - data.idle);
            const idlePct = Math.round((data.idle / Math.max(1, data.total)) * 100);
            el.tileActiveSub.textContent = data.idle_coverage < 0.95
                ? `${idlePct}% idle · measured for ${Math.round(data.idle_coverage * 100)}% of time`
                : `${idlePct}% idle`;
        }

        if (data.period === 'day') {
            el.tileThirdLabel.textContent = 'Top app';
            const top = data.apps[0];
            el.tileThird.textContent = top ? top.app : '–';
            el.tileThirdSub.textContent = top ? `${hoursMinutes(top.seconds)} · ${Math.round((top.seconds / data.total) * 100)}%` : ' ';
        } else {
            el.tileThirdLabel.textContent = 'Daily average';
            el.tileThird.textContent = data.days_active ? hoursMinutes(data.total / data.days_active) : '–';
            el.tileThirdSub.textContent = `over ${data.days_active} active day${data.days_active === 1 ? '' : 's'}`;
        }

        el.tileBusiestLabel.textContent = data.period === 'day' ? 'Busiest hour' : 'Busiest day';
        const max = Math.max(0, ...totals);
        if (max > 0) {
            const bucket = data.buckets[totals.indexOf(max)];
            el.tileBusiest.textContent = bucketLabel(bucket, data.period, true).replace(/ \d{4}$/, '');
            el.tileBusiestSub.textContent = hoursMinutes(max);
        } else {
            el.tileBusiest.textContent = '–';
            el.tileBusiestSub.textContent = ' ';
        }
    }

    function niceStep(max) {
        const steps = [300, 600, 900, 1800, 3600, 7200, 10800, 14400, 21600, 28800, 43200];
        return steps.find((s) => max / s <= 4) || 86400;
    }

    function renderChart(data) {
        el.chartTitle.textContent = data.period === 'day' ? 'Time by hour' : 'Time by day';

        const legendApps = data.apps.filter((a) => state.colors.has(a.app));
        const hasOther = legendApps.length < data.apps.length;
        el.legend.innerHTML = legendApps.map((a) => (
            `<li><span class="dot" style="background:${colorFor(a.app)}"></span>${escapeHtml(a.app)}</li>`
        )).join('') + (hasOther ? `<li><span class="dot" style="background:${OTHER_COLOR}"></span>Other</li>` : '');

        // Stack order follows the period's ranking so each app sits in the same place in every column.
        const order = legendApps.map((a) => a.app);
        const columns = data.buckets.map((b) => {
            const parts = order.map((app) => ({ app, seconds: b.apps[app] || 0 })).filter((p) => p.seconds > 0);
            const other = Object.entries(b.apps)
                .filter(([app]) => !state.colors.has(app))
                .reduce((s, [, v]) => s + v, 0);
            if (other > 0) parts.push({ app: 'Other', seconds: other, other: true });
            return { bucket: b, parts, total: parts.reduce((s, p) => s + p.seconds, 0) };
        });

        const maxTotal = Math.max(0, ...columns.map((c) => c.total));
        const step = niceStep(maxTotal || 3600);
        const yMax = Math.max(step, Math.ceil(maxTotal / step) * step);

        let grid = '';
        let ticks = '';
        for (let v = 0; v <= yMax; v += step) {
            const top = PLOT_HEIGHT - (v / yMax) * PLOT_HEIGHT;
            if (v > 0) grid += `<div class="gridline" style="top:${top}px"></div>`;
            ticks += `<span style="top:${top}px">${v === 0 ? '0' : compactDuration(v)}</span>`;
        }
        el.yAxis.innerHTML = ticks;

        el.plot.innerHTML = grid + columns.map((c, i) => {
            const height = (c.total / yMax) * PLOT_HEIGHT;
            const gaps = Math.max(0, c.parts.length - 1) * 2;
            const available = Math.max(0, height - gaps);
            const segs = c.parts.map((p) => {
                const h = Math.max(1, (p.seconds / c.total) * available);
                return `<div class="seg" style="height:${h}px;background:${p.other ? OTHER_COLOR : colorFor(p.app)}"></div>`;
            }).join('');
            const label = `${bucketLabel(c.bucket, data.period, true)}: ${hoursMinutes(c.total)}`;
            return `<div class="column" data-index="${i}" tabindex="0" role="button" aria-label="${escapeHtml(label)}">
                ${c.total ? `<div class="stack">${segs}</div>` : ''}
            </div>`;
        }).join('');

        const labelEvery = data.period === 'day' ? 3 : data.period === 'month' ? (el.plot.clientWidth < 700 ? 5 : 2) : 1;
        el.xAxis.innerHTML = columns.map((c, i) => {
            const show = i % labelEvery === 0;
            const today = data.period !== 'day' && isCurrentBucket(c.bucket, data.period);
            return `<span class="${today ? 'today' : ''}">${show || today ? bucketLabel(c.bucket, data.period, false) : ''}</span>`;
        }).join('');

        state.columns = columns;
    }

    function showTooltip(index, anchor) {
        const c = state.columns[index];
        const period = state.data.period;
        const rows = c.parts.slice().sort((a, b) => b.seconds - a.seconds).map((p) => (
            `<div class="tt-row"><span class="dot" style="background:${p.other ? OTHER_COLOR : colorFor(p.app)}"></span>
                <span class="label">${escapeHtml(p.app)}</span><span class="value">${compactDuration(p.seconds)}</span></div>`
        )).join('');
        const hint = period === 'day' ? 'Click to open this hour in the timeline' : 'Click to see this day';
        el.tooltip.innerHTML = `<div class="tt-head"><span>${escapeHtml(bucketLabel(c.bucket, period, true))}</span>
            <span>${c.total ? hoursMinutes(c.total) : 'No activity'}</span></div>${rows}
            ${c.total ? `<div class="tt-hint">${hint}</div>` : ''}`;
        el.tooltip.hidden = false;

        const rect = anchor.getBoundingClientRect();
        const tip = el.tooltip.getBoundingClientRect();
        let left = rect.right + 8;
        if (left + tip.width > window.innerWidth - 8) left = rect.left - tip.width - 8;
        const top = Math.max(8, Math.min(window.innerHeight - tip.height - 8, rect.top + 20));
        el.tooltip.style.left = `${Math.max(8, left)}px`;
        el.tooltip.style.top = `${top}px`;
    }

    function openColumn(index) {
        const c = state.columns[index];
        if (!c || !c.total) return;
        const d = bucketDate(c.bucket);
        if (state.data.period === 'day') {
            location.href = `/?date=${dateString(d)}`;
            return;
        }
        state.period = 'day';
        state.date = dateString(d);
        el.tooltip.hidden = true;
        load();
    }

    function renderApps(data) {
        el.empty.hidden = data.apps.length > 0;
        const apps = state.showAll ? data.apps : data.apps.slice(0, APPS_COLLAPSED);

        el.appsBody.innerHTML = apps.map((a) => {
            const pct = data.total ? (a.seconds / data.total) * 100 : 0;
            const open = state.expanded.has(a.app);
            const idle = a.idle == null ? '<span class="muted">—</span>' : `${Math.round((a.idle / Math.max(1, a.seconds)) * 100)}%`;
            const items = open ? a.items.map((item) => `
                <tr class="item-row">
                    <td class="item-label" title="${escapeHtml(item.label)}">${escapeHtml(item.label)}</td>
                    <td><div class="share"><div class="share-track"><div class="share-fill" style="width:${(item.seconds / a.seconds) * 100}%;background:#c3c2b7"></div></div>
                        <span class="share-pct">${Math.round((item.seconds / a.seconds) * 100)}%</span></div></td>
                    <td class="right num">${hoursMinutes(item.seconds)}</td>
                    <td></td>
                </tr>`).join('') : '';
            return `<tr class="app-row ${open ? 'open' : ''}" data-app="${escapeHtml(a.app)}">
                <td><div class="app-cell"><span class="caret">▶</span>${iconHtml(a.app, colorFor(a.app))}<span class="name">${escapeHtml(a.app)}</span></div></td>
                <td><div class="share"><div class="share-track"><div class="share-fill" style="width:${pct}%;background:${colorFor(a.app)}"></div></div>
                    <span class="share-pct">${pct < 1 && pct > 0 ? '<1' : Math.round(pct)}%</span></div></td>
                <td class="right num">${hoursMinutes(a.seconds)}</td>
                <td class="right num">${idle}</td>
            </tr>${items}`;
        }).join('');

        const hidden = data.apps.length - APPS_COLLAPSED;
        el.showAllBtn.hidden = hidden <= 0;
        el.showAllBtn.textContent = state.showAll ? 'Show fewer' : `Show all ${data.apps.length} apps`;
    }

    function renderSide(data) {
        const useSites = data.sites.length > 0;
        const items = useSites ? data.sites : data.windows;
        el.sideTitle.textContent = useSites ? 'Top websites' : 'Top windows';
        if (!items.length) {
            el.sideList.innerHTML = `<li class="side-empty">Nothing to show for this period.</li>`;
            return;
        }
        const max = items[0].seconds;
        el.sideList.innerHTML = items.map((item) => `
            <li title="${escapeHtml(item.app ? `${item.app} — ${item.label}` : item.label)}">
                <div class="side-row">
                    ${item.app ? iconHtml(item.app, colorFor(item.app)) : ''}
                    <span class="label">${escapeHtml(item.label)}</span>
                    <span class="value">${hoursMinutes(item.seconds)}</span>
                </div>
                <div class="side-bar" style="width:${(item.seconds / max) * 100}%"></div>
            </li>`).join('');
    }

    // ---------- events ----------

    el.periodButtons.forEach((b) => b.addEventListener('click', () => {
        if (state.period === b.dataset.period) return;
        state.period = b.dataset.period;
        state.showAll = false;
        load();
    }));

    function shift(delta) {
        const d = parseDate(state.date);
        if (state.period === 'day') d.setDate(d.getDate() + delta);
        else if (state.period === 'week') d.setDate(d.getDate() + 7 * delta);
        else { d.setDate(1); d.setMonth(d.getMonth() + delta); }
        state.date = dateString(d);
        load();
    }

    el.prevBtn.addEventListener('click', () => shift(-1));
    el.nextBtn.addEventListener('click', () => shift(1));
    el.todayBtn.addEventListener('click', () => {
        state.date = dateString(new Date());
        load();
    });
    el.unidentified.addEventListener('change', () => {
        state.unidentified = el.unidentified.checked;
        load();
    });

    el.plot.addEventListener('mouseover', (ev) => {
        const col = ev.target.closest('.column');
        if (col) showTooltip(Number(col.dataset.index), col);
    });
    el.plot.addEventListener('mouseleave', () => { el.tooltip.hidden = true; });
    el.plot.addEventListener('focusin', (ev) => {
        const col = ev.target.closest('.column');
        if (col) showTooltip(Number(col.dataset.index), col);
    });
    el.plot.addEventListener('focusout', () => { el.tooltip.hidden = true; });
    el.plot.addEventListener('click', (ev) => {
        const col = ev.target.closest('.column');
        if (col) openColumn(Number(col.dataset.index));
    });
    el.plot.addEventListener('keydown', (ev) => {
        const col = ev.target.closest('.column');
        if (col && (ev.key === 'Enter' || ev.key === ' ')) {
            ev.preventDefault();
            openColumn(Number(col.dataset.index));
        }
    });

    el.appsBody.addEventListener('click', (ev) => {
        const row = ev.target.closest('tr.app-row');
        if (!row) return;
        const app = row.dataset.app;
        if (state.expanded.has(app)) state.expanded.delete(app);
        else state.expanded.add(app);
        renderApps(state.data);
    });

    el.showAllBtn.addEventListener('click', () => {
        state.showAll = !state.showAll;
        renderApps(state.data);
    });

    window.addEventListener('resize', () => { if (state.data) renderChart(state.data); });

    setInterval(() => {
        if (!document.hidden && state.data && state.data.end >= dateString(new Date())) load();
    }, REFRESH_MS);

    load();
})();
