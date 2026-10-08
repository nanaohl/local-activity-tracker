// Helpers shared by the Timeline and Summary pages.
window.ActivityCommon = (() => {
    // Categorical palette, in fixed order (validated for colour-blind separation).
    // Apps past the last slot share OTHER_COLOR.
    const PALETTE = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300', '#4a3aa7'];
    const OTHER_COLOR = '#b4b2ab';

    function pad(n) { return String(n).padStart(2, '0'); }

    function dateString(d) {
        return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
    }

    function parseDate(str) {
        const [y, m, d] = str.split('-').map(Number);
        return new Date(y, m - 1, d);
    }

    function hoursMinutes(seconds) {
        const m = Math.round(seconds / 60);
        return `${Math.floor(m / 60)}h ${pad(m % 60)}m`;
    }

    function compactDuration(seconds) {
        const m = Math.round(seconds / 60);
        if (m < 1) return `${Math.round(seconds)}s`;
        if (m < 60) return `${m}m`;
        return m % 60 ? `${Math.floor(m / 60)}h ${m % 60}m` : `${m / 60}h`;
    }

    function escapeHtml(value) {
        return String(value ?? '').replace(/[&<>"']/g, (c) => (
            { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
        ));
    }

    /**
     * Palette colours keyed by app, assigned by all-time usage so an app keeps
     * the same colour on every page and period. Fetched once per page load.
     */
    let colorsPromise = null;
    function loadColors() {
        colorsPromise = colorsPromise || fetch('/api/app-colors')
            .then((res) => (res.ok ? res.json() : { apps: [] }))
            .catch(() => ({ apps: [] }))
            .then(({ apps }) => new Map(apps.map((app, i) => [app, PALETTE[i]])));
        return colorsPromise;
    }

    /** App icon from the server, falling back to a coloured initial. */
    function iconHtml(app, color) {
        const letter = escapeHtml((app || '?').trim().charAt(0).toUpperCase());
        const fallback = `<span class="app-icon" style="background:${color || OTHER_COLOR}">${letter}</span>`;
        return `<img class="app-icon" alt="" src="/api/icon/${encodeURIComponent(app)}"
            onerror="this.outerHTML=this.dataset.fallback" data-fallback="${escapeHtml(fallback)}">`;
    }

    return { PALETTE, OTHER_COLOR, pad, dateString, parseDate, hoursMinutes, compactDuration, escapeHtml, loadColors, iconHtml };
})();
