(() => {
    const { OTHER_COLOR, pad, hoursMinutes, escapeHtml, loadColors, iconHtml: appIcon } = window.ActivityCommon;
    const SHORT_SECONDS = 30;
    const REFRESH_MS = 15000;
    const DAY_MINUTES = 1440;

    const $ = (id) => document.getElementById(id);
    const el = {
        recordBtn: $('recordBtn'),
        started: $('statStarted'),
        finished: $('statFinished'),
        duration: $('statDuration'),
        todayBtn: $('todayBtn'),
        prevDayBtn: $('prevDayBtn'),
        nextDayBtn: $('nextDayBtn'),
        dateInput: $('dateInput'),
        timeline: $('timeline'),
        segments: $('timelineSegments'),
        brush: $('timelineBrush'),
        nowLine: $('timelineNow'),
        hours: $('timelineHours'),
        rangeChip: $('rangeChip'),
        rangeLabel: $('rangeLabel'),
        clearRangeBtn: $('clearRangeBtn'),
        tooltip: $('tooltip'),
        search: $('searchInput'),
        addBtn: $('addBtn'),
        ticketBtn: $('ticketBtn'),
        picker: $('ticketPicker'),
        pickerConnect: $('pickerConnect'),
        pickerConnectForm: $('pickerConnectForm'),
        pickerToken: $('pickerTokenInput'),
        pickerTasks: $('pickerTasks'),
        pickerSearch: $('pickerSearch'),
        pickerList: $('pickerList'),
        pickerRemoveBtn: $('pickerRemoveBtn'),
        pickerRefreshBtn: $('pickerRefreshBtn'),
        pickerError: $('pickerError'),
        mergeBtn: $('mergeBtn'),
        deleteBtn: $('deleteBtn'),
        hideShort: $('hideShortInput'),
        selectAll: $('selectAllInput'),
        entriesBody: $('entriesBody'),
        empty: $('emptyState'),
        selectAllGroups: $('selectAllGroupsInput'),
        groupsBody: $('groupsBody'),
        detailSelected: $('detailSelected'),
        detailTotal: $('detailTotal'),
    };

    const state = {
        date: todayString(),
        recording: false,
        entries: [],
        colors: new Map(),
        selected: new Set(),
        search: '',
        hideShort: true,
        range: null, // [startMinute, endMinute]
        sort: { key: 'start', dir: 'desc' },
        hoverKey: null,
    };

    // ---------- helpers ----------

    function todayString() {
        const d = new Date();
        return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
    }

    function hhmm(date) {
        if (date - dayStart() >= DAY_MINUTES * 60000) return '24:00'; // clipped at midnight
        return `${pad(date.getHours())}:${pad(date.getMinutes())}`;
    }
    function hms(seconds) {
        const s = Math.round(seconds);
        return `${pad(Math.floor(s / 3600))}:${pad(Math.floor(s / 60) % 60)}:${pad(s % 60)}`;
    }
    function shortDuration(seconds) {
        if (seconds < 60) return `${Math.round(seconds)}s`;
        if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
        return hoursMinutes(seconds);
    }
    function minuteLabel(minute) {
        const m = Math.round(minute);
        return `${pad(Math.floor(m / 60))}:${pad(m % 60)}`;
    }

    function dayStart() {
        const [y, m, d] = state.date.split('-').map(Number);
        return new Date(y, m - 1, d);
    }
    function toMinute(date) {
        return Math.min(DAY_MINUTES, Math.max(0, (date - dayStart()) / 60000));
    }

    function prettyUrl(url) {
        try {
            const u = new URL(url);
            return u.host + (u.pathname === '/' ? '' : u.pathname);
        } catch (_) {
            return url;
        }
    }

    function taskText(task) {
        return task ? `${task.name} ${task.custom_id || ''} ${task.id} ${task.list_name || ''}` : '';
    }

    function statusDot(task) {
        const color = /^#[0-9a-f]{3,8}$/i.test(task.status_color || '') ? task.status_color : '';
        return `<span class="status-dot" style="${color ? `background:${color}` : ''}" title="${escapeHtml(task.status || '')}"></span>`;
    }

    function ticketChip(task) {
        const label = task.custom_id ? `${task.custom_id} · ${task.name}` : task.name;
        const title = [task.name, task.status, task.list_name].filter(Boolean).join(' · ');
        return `<a class="ticket-chip" href="${escapeHtml(task.url)}" target="_blank" rel="noopener" title="${escapeHtml(title)}">${statusDot(task)}<span class="label">${escapeHtml(label)}</span></a>`;
    }

    function iconHtml(app) {
        return appIcon(app, state.colors.get(app));
    }

    async function api(path, body) {
        const res = await fetch(path, body === undefined ? {} : {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        if (!res.ok) throw new Error(`${path} failed: ${res.status}`);
        return res.json();
    }

    // ---------- data ----------

    async function load({ keepSelection = false } = {}) {
        const [data, colors] = await Promise.all([api(`/api/day?date=${state.date}`), loadColors()]);
        if (data.date !== state.date) return; // user moved to another day meanwhile
        history.replaceState(null, '', `/?date=${state.date}`);
        document.getElementById('navSummary').href = `/summary?period=day&date=${state.date}`;

        state.recording = data.recording;
        state.entries = data.entries.map((e) => ({
            ...e,
            key: e.ids.join('-'),
            startDate: new Date(e.start),
            endDate: new Date(e.end),
        }));

        state.colors = colors;

        const keys = new Set(state.entries.map((e) => e.key));
        state.selected = keepSelection
            ? new Set([...state.selected].filter((k) => keys.has(k)))
            : new Set();
        render();
    }

    function visibleEntries() {
        const q = state.search.trim().toLowerCase();
        const list = state.entries.filter((e) => {
            if (state.hideShort && e.duration < SHORT_SECONDS) return false;
            if (q && !`${e.app} ${e.title} ${e.url || ''} ${taskText(e.task)}`.toLowerCase().includes(q)) return false;
            if (state.range) {
                const [a, b] = state.range;
                if (toMinute(e.endDate) < a || toMinute(e.startDate) > b) return false;
            }
            return true;
        });

        const { key, dir } = state.sort;
        const sign = dir === 'asc' ? 1 : -1;
        const value = (e) => {
            switch (key) {
                case 'start': return e.startDate.getTime();
                case 'end': return e.endDate.getTime();
                case 'idle': return e.idle == null ? -1 : e.idle / Math.max(1, e.duration);
                case 'added': return e.added ? 1 : 0;
                case 'url': return (e.url || '').toLowerCase();
                case 'ticket': return e.task ? e.task.name.toLowerCase() : '\uffff'; // unassigned last
                case 'duration': return e.duration;
                default: return String(e[key] || '').toLowerCase();
            }
        };
        return list.sort((a, b) => {
            const va = value(a), vb = value(b);
            return (va < vb ? -1 : va > vb ? 1 : 0) * sign;
        });
    }

    // ---------- rendering ----------

    function render() {
        const visible = visibleEntries();
        renderHeader();
        renderTimeline(visible);
        renderEntries(visible);
        renderGroups(visible);
        renderFooter(visible);
    }

    function renderHeader() {
        el.recordBtn.textContent = state.recording ? 'Stop recording' : 'Start recording';
        el.recordBtn.classList.toggle('recording', state.recording);
        el.dateInput.value = state.date;
        el.nextDayBtn.disabled = state.date >= todayString();

        if (!state.entries.length) {
            el.started.textContent = el.finished.textContent = el.duration.textContent = '--:--';
            return;
        }
        const first = state.entries.reduce((a, e) => (e.startDate < a ? e.startDate : a), state.entries[0].startDate);
        const last = state.entries.reduce((a, e) => (e.endDate > a ? e.endDate : a), state.entries[0].endDate);
        el.started.textContent = hhmm(first);
        el.finished.textContent = hhmm(last);
        el.duration.textContent = minuteLabel((last - first) / 60000);
    }

    function renderTimeline(visible) {
        const visibleKeys = new Set(visible.map((e) => e.key));
        const filtering = state.search.trim() !== '' || state.range !== null;
        const focus = state.selected.size ? state.selected : (filtering ? visibleKeys : null);

        el.segments.innerHTML = state.entries.map((e) => {
            const left = toMinute(e.startDate);
            const width = toMinute(e.endDate) - left;
            const cls = ['segment'];
            if (focus && focus.has(e.key)) cls.push('focus');
            if (state.hoverKey === e.key) cls.push('hover');
            return `<div class="${cls.join(' ')}" data-key="${e.key}" style="left:${(left / DAY_MINUTES) * 100}%;width:${(width / DAY_MINUTES) * 100}%;background:${state.colors.get(e.app) || OTHER_COLOR}"></div>`;
        }).join('');
        el.timeline.classList.toggle('has-focus', Boolean(focus));

        const activeHours = new Set();
        state.entries.forEach((e) => {
            for (let h = e.startDate.getHours(); h <= e.endDate.getHours(); h++) activeHours.add(h);
        });
        el.hours.innerHTML = Array.from({ length: 24 }, (_, h) => (
            `<span class="${activeHours.has(h) ? 'active' : ''}" style="left:${(h / 24) * 100}%">${h}h</span>`
        )).join('');

        const isToday = state.date === todayString();
        el.nowLine.hidden = !isToday;
        if (isToday) el.nowLine.style.left = `${(toMinute(new Date()) / DAY_MINUTES) * 100}%`;

        if (state.range) {
            const [a, b] = state.range;
            el.brush.hidden = false;
            el.brush.style.left = `${(a / DAY_MINUTES) * 100}%`;
            el.brush.style.width = `${((b - a) / DAY_MINUTES) * 100}%`;
            el.rangeChip.hidden = false;
            el.rangeLabel.textContent = `${minuteLabel(a)} – ${minuteLabel(b)}`;
        } else if (!brushing) {
            el.brush.hidden = true;
            el.rangeChip.hidden = true;
        }
    }

    function renderEntries(visible) {
        el.empty.hidden = visible.length > 0;
        el.empty.textContent = state.entries.length
            ? 'No entries match the current filters.'
            : 'No activity recorded for this day.';

        el.entriesBody.innerHTML = visible.map((e) => {
            const selected = state.selected.has(e.key);
            const idle = e.idle == null ? '<span class="muted">—</span>' : `${Math.round((e.idle / Math.max(1, e.duration)) * 100)}%`;
            const url = e.url
                ? `<a href="${escapeHtml(e.url)}" target="_blank" rel="noopener" title="${escapeHtml(e.url)}">${escapeHtml(prettyUrl(e.url))}</a>`
                : '<span class="muted">Unknown URL</span>';
            return `<tr data-key="${e.key}" class="${selected ? 'selected' : ''}">
                <td class="col-check"><input type="checkbox" ${selected ? 'checked' : ''} aria-label="Select entry"></td>
                <td><div class="app-cell">${iconHtml(e.app)}<span class="name">${escapeHtml(e.app)}</span></div></td>
                <td class="desc" title="${escapeHtml(e.title)}">${escapeHtml(e.title) || '<span class="muted">—</span>'}</td>
                <td class="url">${url}</td>
                <td class="ticket">${e.task ? ticketChip(e.task) : ''}</td>
                <td class="num">${hhmm(e.startDate)}</td>
                <td class="num">${hhmm(e.endDate)}</td>
                <td class="num">${hms(e.duration)}</td>
                <td class="num">${idle}</td>
                <td>${e.added ? '<span class="added-mark" title="Added">✓</span>' : ''}</td>
            </tr>`;
        }).join('');

        const selectedVisible = visible.filter((e) => state.selected.has(e.key)).length;
        el.selectAll.checked = visible.length > 0 && selectedVisible === visible.length;
        el.selectAll.indeterminate = selectedVisible > 0 && selectedVisible < visible.length;

        document.querySelectorAll('thead th[data-sort]').forEach((th) => {
            const active = th.dataset.sort === state.sort.key;
            th.classList.toggle('sorted', active);
            th.classList.toggle('asc', active && state.sort.dir === 'asc');
        });

        el.addBtn.disabled = state.selected.size === 0;
        el.ticketBtn.disabled = state.selected.size === 0;
        if (el.ticketBtn.disabled) closePicker();
        el.mergeBtn.disabled = state.selected.size < 2;
        el.deleteBtn.disabled = state.selected.size === 0;
        if (el.deleteBtn.disabled) resetDeleteConfirm();
    }

    function groupsFor(visible) {
        const groups = new Map();
        visible.forEach((e) => {
            const g = groups.get(e.app) || { app: e.app, total: 0, keys: [] };
            g.total += e.duration;
            g.keys.push(e.key);
            groups.set(e.app, g);
        });
        return [...groups.values()].sort((a, b) => b.total - a.total);
    }

    function renderGroups(visible) {
        const groups = groupsFor(visible);
        const total = groups.reduce((s, g) => s + g.total, 0);
        let fullySelected = 0;

        el.groupsBody.innerHTML = groups.map((g) => {
            const count = g.keys.filter((k) => state.selected.has(k)).length;
            const all = count === g.keys.length;
            if (all) fullySelected++;
            return `<tr data-app="${escapeHtml(g.app)}" class="${all ? 'selected' : ''}">
                <td class="col-check"><input type="checkbox" ${all ? 'checked' : ''} data-partial="${count > 0 && !all}" aria-label="Select app"></td>
                <td><div class="app-cell"><span class="swatch" style="background:${state.colors.get(g.app) || OTHER_COLOR}"></span>${iconHtml(g.app)}<span class="name">${escapeHtml(g.app)}</span></div></td>
                <td class="num">${total ? Math.round((g.total / total) * 100) : 0}%</td>
                <td class="num">${hms(g.total)}</td>
            </tr>`;
        }).join('');
        el.groupsBody.querySelectorAll('input[data-partial="true"]').forEach((i) => { i.indeterminate = true; });

        el.selectAllGroups.checked = groups.length > 0 && fullySelected === groups.length;
        el.selectAllGroups.indeterminate = state.selected.size > 0 && !el.selectAllGroups.checked;
    }

    function renderFooter(visible) {
        const selected = state.entries.filter((e) => state.selected.has(e.key));
        const basis = selected.length ? selected : visible;
        el.detailSelected.textContent = `Selected ${selected.length}/${visible.length}`;
        el.detailTotal.textContent = `Total ${hoursMinutes(basis.reduce((s, e) => s + e.duration, 0))}`;
    }

    // ---------- selection ----------

    function setSelected(keys, on) {
        keys.forEach((k) => (on ? state.selected.add(k) : state.selected.delete(k)));
        render();
    }

    function selectedIds() {
        return state.entries.filter((e) => state.selected.has(e.key)).flatMap((e) => e.ids);
    }

    function revealEntry(key) {
        const row = el.entriesBody.querySelector(`tr[data-key="${key}"]`);
        if (!row) return;
        row.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
        row.classList.remove('flash');
        void row.offsetWidth;
        row.classList.add('flash');
    }

    // ---------- timeline interactions ----------

    let brushing = null; // { startMinute, moved }

    function minuteAt(clientX) {
        const rect = el.timeline.getBoundingClientRect();
        return Math.min(DAY_MINUTES, Math.max(0, ((clientX - rect.left) / rect.width) * DAY_MINUTES));
    }

    function entryAt(clientX) {
        const minute = minuteAt(clientX);
        const tolerance = (DAY_MINUTES / el.timeline.clientWidth) * 2; // ~2px
        let best = null;
        state.entries.forEach((e) => {
            const a = toMinute(e.startDate) - tolerance;
            const b = toMinute(e.endDate) + tolerance;
            if (minute >= a && minute <= b && (!best || e.duration > best.duration)) {
                // Prefer an exact hit over a nearby one, then the longest entry.
                const exact = minute >= a + tolerance && minute <= b - tolerance;
                if (!best || exact || !best.exact) best = { ...e, exact };
            }
        });
        return best;
    }

    function showTooltip(entry, clientX, clientY) {
        el.tooltip.innerHTML = `<strong>${escapeHtml(entry.app)}</strong>
            ${entry.title ? `<div class="tt-title">${escapeHtml(entry.title)}</div>` : ''}
            ${entry.task ? `<div class="tt-title">Ticket: ${escapeHtml(entry.task.name)}</div>` : ''}
            <div>${hhmm(entry.startDate)} – ${hhmm(entry.endDate)} · ${shortDuration(entry.duration)}</div>`;
        el.tooltip.hidden = false;
        const { width } = el.tooltip.getBoundingClientRect();
        el.tooltip.style.left = `${Math.min(window.innerWidth - width - 8, clientX + 12)}px`;
        el.tooltip.style.top = `${clientY + 16}px`;
    }

    function setHover(key) {
        if (state.hoverKey === key) return;
        state.hoverKey = key;
        el.segments.querySelectorAll('.segment.hover').forEach((s) => s.classList.remove('hover'));
        if (key) el.segments.querySelector(`.segment[data-key="${key}"]`)?.classList.add('hover');
    }

    el.timeline.addEventListener('mousedown', (ev) => {
        if (ev.button !== 0) return;
        brushing = { startMinute: minuteAt(ev.clientX), startX: ev.clientX, moved: false };
        ev.preventDefault();
    });

    window.addEventListener('mousemove', (ev) => {
        if (brushing) {
            if (Math.abs(ev.clientX - brushing.startX) > 4) brushing.moved = true;
            if (brushing.moved) {
                const a = Math.min(brushing.startMinute, minuteAt(ev.clientX));
                const b = Math.max(brushing.startMinute, minuteAt(ev.clientX));
                el.brush.hidden = false;
                el.brush.style.left = `${(a / DAY_MINUTES) * 100}%`;
                el.brush.style.width = `${((b - a) / DAY_MINUTES) * 100}%`;
                el.tooltip.hidden = true;
                return;
            }
        }
        if (ev.target === el.timeline || el.timeline.contains(ev.target)) {
            const entry = entryAt(ev.clientX);
            if (entry) {
                showTooltip(entry, ev.clientX, ev.clientY);
                setHover(entry.key);
                return;
            }
        }
        el.tooltip.hidden = true;
        if (!ev.target.closest || !ev.target.closest('#entriesBody')) setHover(null);
    });

    window.addEventListener('mouseup', (ev) => {
        if (!brushing) return;
        const { moved, startMinute } = brushing;
        brushing = null;
        if (moved) {
            const snap = (m) => Math.round(m / 5) * 5;
            const a = snap(Math.min(startMinute, minuteAt(ev.clientX)));
            const b = snap(Math.max(startMinute, minuteAt(ev.clientX)));
            state.range = b > a ? [a, b] : null;
            render();
            return;
        }
        const entry = entryAt(ev.clientX);
        if (!entry) return;
        const visible = visibleEntries().some((e) => e.key === entry.key);
        if (!visible) {
            // Make sure the clicked entry can be shown in the table.
            state.search = el.search.value = '';
            state.range = null;
            if (entry.duration < SHORT_SECONDS) state.hideShort = el.hideShort.checked = false;
        }
        if (!ev.metaKey && !ev.shiftKey && !ev.ctrlKey) state.selected.clear();
        state.selected.add(entry.key);
        render();
        revealEntry(entry.key);
    });

    el.timeline.addEventListener('mouseleave', () => { el.tooltip.hidden = true; });

    el.clearRangeBtn.addEventListener('click', () => {
        state.range = null;
        render();
    });

    // ---------- table interactions ----------

    el.entriesBody.addEventListener('click', (ev) => {
        if (ev.target.closest('a')) return;
        const row = ev.target.closest('tr[data-key]');
        if (!row) return;
        const key = row.dataset.key;
        setSelected([key], !state.selected.has(key));
    });

    el.entriesBody.addEventListener('mouseover', (ev) => {
        const row = ev.target.closest('tr[data-key]');
        setHover(row ? row.dataset.key : null);
    });
    el.entriesBody.addEventListener('mouseleave', () => setHover(null));

    el.selectAll.addEventListener('change', () => {
        setSelected(visibleEntries().map((e) => e.key), el.selectAll.checked);
    });

    el.groupsBody.addEventListener('click', (ev) => {
        const row = ev.target.closest('tr[data-app]');
        if (!row) return;
        const group = groupsFor(visibleEntries()).find((g) => g.app === row.dataset.app);
        if (!group) return;
        const allSelected = group.keys.every((k) => state.selected.has(k));
        setSelected(group.keys, !allSelected);
    });

    el.selectAllGroups.addEventListener('change', () => {
        if (el.selectAllGroups.checked) setSelected(visibleEntries().map((e) => e.key), true);
        else { state.selected.clear(); render(); }
    });

    document.querySelectorAll('thead th[data-sort]').forEach((th) => {
        th.addEventListener('click', () => {
            const key = th.dataset.sort;
            state.sort = state.sort.key === key
                ? { key, dir: state.sort.dir === 'asc' ? 'desc' : 'asc' }
                : { key, dir: key === 'start' || key === 'end' || key === 'duration' || key === 'idle' ? 'desc' : 'asc' };
            render();
        });
    });

    el.search.addEventListener('input', () => {
        state.search = el.search.value;
        render();
    });

    el.hideShort.addEventListener('change', () => {
        state.hideShort = el.hideShort.checked;
        render();
    });

    // ---------- actions ----------

    async function runAction(path) {
        const ids = selectedIds();
        if (!ids.length) return;
        try {
            await api(path, { ids });
        } catch (err) {
            console.error(err);
        }
        await load({ keepSelection: path.endsWith('/add') });
    }

    el.addBtn.addEventListener('click', () => runAction('/api/entries/add'));
    el.mergeBtn.addEventListener('click', () => runAction('/api/entries/merge'));

    // ---------- ClickUp ticket picker ----------

    const LOOKUP_RE = /clickup\.com\/t\/|^#?[a-z0-9]{6,12}$|^[a-z][a-z0-9]*-\d+$/i;
    const picker = {
        tasks: null, // { recent, tasks } once loaded
        items: [], // tasks currently listed, in display order
        active: 0,
        lookup: null, // { ref, task, loading }
        lookupTimer: null,
    };

    function selectedEntries() {
        return state.entries.filter((e) => state.selected.has(e.key));
    }

    function positionPicker() {
        const rect = el.ticketBtn.getBoundingClientRect();
        const width = el.picker.offsetWidth;
        el.picker.style.left = `${Math.max(16, Math.min(rect.left, window.innerWidth - width - 16))}px`;
        el.picker.style.top = `${rect.bottom + 4}px`;
    }

    function showPickerError(message) {
        el.pickerError.hidden = !message;
        el.pickerError.textContent = message || '';
    }

    async function pickerFetch(path, options) {
        const res = await fetch(path, options);
        const data = await res.json().catch(() => ({}));
        if (res.status === 401 && data.connected === false) {
            showConnect(data.error);
            return null;
        }
        if (!res.ok) throw new Error(data.error || `${path} failed: ${res.status}`);
        return data;
    }

    function showConnect(message) {
        picker.tasks = null;
        el.pickerConnect.hidden = false;
        el.pickerTasks.hidden = true;
        showPickerError(message && message !== 'ClickUp is not connected' ? message : '');
        el.pickerToken.focus();
    }

    async function loadTasks(refresh = false) {
        el.pickerConnect.hidden = true;
        el.pickerTasks.hidden = false;
        showPickerError('');
        if (!picker.tasks || refresh) {
            el.pickerList.innerHTML = '<div class="picker-empty">Loading tasks…</div>';
            try {
                const data = await pickerFetch(`/api/clickup/tasks${refresh ? '?refresh=1' : ''}`);
                if (!data) return;
                picker.tasks = data;
            } catch (err) {
                showPickerError(err.message);
                picker.tasks = picker.tasks || { recent: [], tasks: [] };
            }
        }
        renderPicker();
    }

    function openPicker() {
        if (!el.picker.hidden) return closePicker();
        el.picker.hidden = false;
        positionPicker();
        el.pickerSearch.value = '';
        picker.lookup = null;
        picker.active = 0;
        el.pickerSearch.focus();
        loadTasks();
    }

    function closePicker() {
        if (el.picker.hidden) return;
        el.picker.hidden = true;
        clearTimeout(picker.lookupTimer);
        showPickerError('');
    }

    function renderPicker() {
        if (el.picker.hidden || !picker.tasks) return;
        const query = el.pickerSearch.value.trim();
        const q = query.toLowerCase();
        const matches = (t) => !q || taskText(t).toLowerCase().includes(q);

        const recent = picker.tasks.recent.filter(matches);
        const recentIds = new Set(recent.map((t) => t.id));
        const assigned = picker.tasks.tasks.filter((t) => !recentIds.has(t.id) && matches(t));
        const groups = [['Recent', recent], ['Assigned to you', assigned]];

        const listedIds = new Set([...recentIds, ...assigned.map((t) => t.id)]);
        if (picker.lookup && picker.lookup.ref === query) {
            if (picker.lookup.task && !listedIds.has(picker.lookup.task.id)) groups.unshift(['From link', [picker.lookup.task]]);
        }

        const selected = selectedEntries();
        const currentIds = new Set(selected.map((e) => e.task && e.task.id));
        const current = currentIds.size === 1 ? [...currentIds][0] : null;
        el.pickerRemoveBtn.disabled = !selected.some((e) => e.task);

        picker.items = [];
        let html = '';
        groups.forEach(([label, tasks]) => {
            if (!tasks.length) return;
            html += `<div class="picker-group">${label}</div>`;
            tasks.forEach((t) => {
                const i = picker.items.push(t) - 1;
                const meta = [t.custom_id, t.status, t.list_name].filter(Boolean).join(' · ');
                html += `<button type="button" role="option" data-index="${i}"
                    class="picker-item ${i === picker.active ? 'active' : ''} ${t.id === current ? 'current' : ''}">
                    ${statusDot(t)}<span class="name">${escapeHtml(t.name)}</span>
                    ${meta ? `<span class="meta">${escapeHtml(meta)}</span>` : ''}
                </button>`;
            });
        });
        if (!picker.items.length) {
            const looking = picker.lookup && picker.lookup.ref === query && picker.lookup.loading;
            html = `<div class="picker-empty">${
                looking ? 'Looking up task…'
                    : query ? 'No matching tasks. Paste a ClickUp link or task ID to use any task.'
                        : 'No open tasks assigned to you.'
            }</div>`;
        }
        el.pickerList.innerHTML = html;
        el.pickerList.querySelector('.picker-item.active')?.scrollIntoView({ block: 'nearest' });
    }

    function scheduleLookup() {
        clearTimeout(picker.lookupTimer);
        const ref = el.pickerSearch.value.trim();
        if (!LOOKUP_RE.test(ref)) {
            picker.lookup = null;
            return;
        }
        picker.lookup = { ref, task: null, loading: true };
        picker.lookupTimer = setTimeout(async () => {
            try {
                const data = await pickerFetch(`/api/clickup/lookup?ref=${encodeURIComponent(ref)}`);
                if (!data || !picker.lookup || picker.lookup.ref !== ref) return;
                picker.lookup = { ref, task: data.task, loading: false };
                if (data.task) picker.active = 0;
            } catch (err) {
                showPickerError(err.message);
                if (picker.lookup) picker.lookup.loading = false;
            }
            renderPicker();
        }, 300);
    }

    async function assignTicket(taskId) {
        const ids = selectedIds();
        if (!ids.length) return;
        showPickerError('');
        try {
            const data = await pickerFetch('/api/entries/ticket', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ids, task_id: taskId }),
            });
            if (!data) return;
        } catch (err) {
            showPickerError(err.message);
            return;
        }
        closePicker();
        await load({ keepSelection: true });
    }

    el.ticketBtn.addEventListener('click', openPicker);

    el.pickerSearch.addEventListener('input', () => {
        picker.active = 0;
        scheduleLookup();
        renderPicker();
    });

    el.pickerSearch.addEventListener('keydown', (ev) => {
        if (ev.key === 'ArrowDown' || ev.key === 'ArrowUp') {
            ev.preventDefault();
            if (!picker.items.length) return;
            const step = ev.key === 'ArrowDown' ? 1 : -1;
            picker.active = (picker.active + step + picker.items.length) % picker.items.length;
            renderPicker();
        } else if (ev.key === 'Enter') {
            ev.preventDefault();
            const task = picker.items[picker.active];
            if (task) assignTicket(task.id);
        }
    });

    el.pickerList.addEventListener('click', (ev) => {
        const item = ev.target.closest('.picker-item');
        if (item) assignTicket(picker.items[Number(item.dataset.index)].id);
    });

    el.pickerRemoveBtn.addEventListener('click', () => assignTicket(null));
    el.pickerRefreshBtn.addEventListener('click', () => loadTasks(true));

    el.pickerConnectForm.addEventListener('submit', async (ev) => {
        ev.preventDefault();
        showPickerError('');
        try {
            const data = await pickerFetch('/api/clickup/token', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ token: el.pickerToken.value }),
            });
            if (!data) return;
        } catch (err) {
            showPickerError(err.message);
            return;
        }
        el.pickerToken.value = '';
        await loadTasks(true);
        el.pickerSearch.focus();
    });

    document.addEventListener('keydown', (ev) => {
        if (ev.key === 'Escape' && !el.picker.hidden) {
            closePicker();
            el.ticketBtn.focus();
        }
    });
    document.addEventListener('mousedown', (ev) => {
        if (!el.picker.hidden && !el.picker.contains(ev.target) && !el.ticketBtn.contains(ev.target)) closePicker();
    });
    window.addEventListener('resize', () => { if (!el.picker.hidden) positionPicker(); });
    window.addEventListener('scroll', () => { if (!el.picker.hidden) positionPicker(); }, true);

    let deleteTimer = null;
    function resetDeleteConfirm() {
        clearTimeout(deleteTimer);
        deleteTimer = null;
        el.deleteBtn.classList.remove('confirm');
        el.deleteBtn.textContent = 'Delete Selected';
    }
    el.deleteBtn.addEventListener('click', () => {
        if (!deleteTimer) {
            el.deleteBtn.classList.add('confirm');
            el.deleteBtn.textContent = `Confirm delete (${state.selected.size})`;
            deleteTimer = setTimeout(resetDeleteConfirm, 4000);
            return;
        }
        resetDeleteConfirm();
        runAction('/api/entries/delete');
    });

    el.recordBtn.addEventListener('click', async () => {
        el.recordBtn.disabled = true;
        try {
            const res = await api(state.recording ? '/api/recording/stop' : '/api/recording/start', {});
            state.recording = res.recording;
            if (state.recording && state.date !== todayString()) state.date = todayString();
            await load({ keepSelection: true });
        } catch (err) {
            console.error(err);
        } finally {
            el.recordBtn.disabled = false;
        }
    });

    // ---------- date navigation ----------

    function goToDate(date) {
        if (!date || date === state.date) return;
        state.date = date;
        state.range = null;
        load();
    }

    function shiftDay(delta) {
        const d = dayStart();
        d.setDate(d.getDate() + delta);
        goToDate(`${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`);
    }

    el.todayBtn.addEventListener('click', () => goToDate(todayString()));
    el.prevDayBtn.addEventListener('click', () => shiftDay(-1));
    el.nextDayBtn.addEventListener('click', () => shiftDay(1));
    el.dateInput.addEventListener('change', () => goToDate(el.dateInput.value));

    const params = new URLSearchParams(location.search);
    if (/^\d{4}-\d{2}-\d{2}$/.test(params.get('date') || '')) state.date = params.get('date');

    setInterval(() => {
        if (document.hidden || brushing) return;
        if (state.date === todayString()) load({ keepSelection: true });
    }, REFRESH_MS);

    load();
})();
