const PRODUCTS = [
    { id: 'firefox', label: 'Firefox Desktop' },
    { id: 'fenix', label: 'Firefox for Android' },
];

const localeSelect = document.querySelector('#localeSelect');
const statusEl = document.querySelector('#status');
const chartEl = document.querySelector('#chart');
let chart;

const urlParams = new URLSearchParams(location.search);

function setURLParam(key, value) {
    const params = new URLSearchParams(location.search);
    if (value) params.set(key, value); else params.delete(key);
    history.replaceState(null, '', `${location.pathname}?${params.toString()}`);
}

function parseAcceptLanguage() {
    const langs = (navigator.languages && navigator.languages.length
        ? navigator.languages
        : [navigator.language || 'en']);
    const expanded = new Set();
    langs.forEach(l => {
        expanded.add(l);
        const base = l.split('-')[0];
        if (base) expanded.add(base);
    });
    return Array.from(expanded);
}

function versionCompare(a, b) {
    return Number(a) - Number(b);
}

function pickDefaultLocale(allLocales) {
    const param = urlParams.get('locale');
    if (param && allLocales.has(param)) return param;
    const accept = parseAcceptLanguage();
    for (const loc of accept) {
        if (allLocales.has(loc)) return loc;
        const base = loc.split('-')[0];
        if (allLocales.has(base)) return base;
    }
    return allLocales.values().next().value;
}

function setStatus(msg, isError = false) {
    statusEl.textContent = msg;
    statusEl.className = isError ? 'error' : 'loading';
}

async function init() {
    try {
        setStatus('Loading data…');
        const res = await fetch('data/data.json');
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const db = await res.json();

        // Build locale list from JSON top-level keys
        const allLocales = new Set(Object.keys(db));
        if (!allLocales.size) throw new Error('No locales found in data.json');

        const localesSorted = Array.from(allLocales).sort((a, b) => a.localeCompare(b));
        localeSelect.innerHTML = localesSorted
            .map(l => {
                const entry = db[l];
                const name = entry?.name || '';
                return `<option value="${l}">${l}${name ? ' – ' + name : ''}</option>`;
            })
            .join('');

        const chosen = pickDefaultLocale(allLocales);
        localeSelect.value = chosen;
        if (urlParams.get('locale') !== chosen) setURLParam('locale', chosen);

        await render(db, chosen, db[chosen]?.name);

        localeSelect.addEventListener('change', async () => {
            const locale = localeSelect.value;
            setURLParam('locale', locale);
            await render(db, locale, db[locale]?.name);
        });
    } catch (err) {
        console.error(err);
        setStatus(`Failed to load data: ${err.message}`, true);
    }
}

function collectLabelsForLocale(db, locale) {
    // Expected JSON shape: db[locale][product][version] = value (0..1)
    const entry = db[locale];
    if (!entry) return [];
    const versions = new Set();
    for (const p of PRODUCTS) {
        const prodObj = entry[p.id] || {};
        Object.keys(prodObj).forEach(v => versions.add(v));
    }
    return Array.from(versions).sort(versionCompare);
}

async function render(db, locale, locale_name) {
    const entry = db[locale];
    if (!entry) {
        setStatus(`No data found for locale "${locale}".`, true);
        if (chart) { chart.destroy(); chart = null; }
        return;
    }

    const labels = collectLabelsForLocale(db, locale);
    if (!labels.length) {
        setStatus(`No versions found for locale "${locale}".`, true);
        if (chart) { chart.destroy(); chart = null; }
        return;
    }

    const datasets = PRODUCTS.map(p => {
        const prodObj = entry[p.id] || {};
        // Map each version label to a percentage value; use null when missing (Span gaps)
        const values = labels.map(v => (v in prodObj ? prodObj[v] * 100 : null));
        return {
            label: p.label,
            data: values,
            spanGaps: true,
            tension: 0.25,
            borderWidth: 2.5,
            pointRadius: 3,
            pointHoverRadius: 5,
        };
    });

    const numFmt = new Intl.NumberFormat(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    const data = { labels, datasets };
    const options = {
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 350 },
        plugins: {
            legend: { display: true, labels: { color: '#303541ff' } },
            tooltip: {
                callbacks: {
                    label: (ctx) =>
                        `${ctx.dataset.label}: ${ctx.parsed.y != null ? ctx.parsed.y.toFixed(2) : '—'}%`,
                },
            },
        },
        scales: {
            x: { ticks: { color: '#374151' }, grid: { color: 'rgba(104, 93, 93, 0.17)' } },
            y: {
                grace: '5%',
                title: { display: true, text: 'Completion %', color: '#374151' },
                ticks: { color: '#374151', callback: v => (v > 100 ? '' : numFmt.format(v) + '%') },
                grid: { color: 'rgba(255,255,255,0.06)' },
            },
        },
    };

    if (chart) chart.destroy();
    chart = new Chart(chartEl, { type: 'line', data, options });
    setStatus(`Showing ${labels.length} versions for ${locale_name} (${locale}).`);
}

init();
