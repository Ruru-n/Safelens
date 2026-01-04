let crimeBarChart = null;
let monthLineChart = null;
let yearLineChart = null;

function safeEmptyChart(ctx, type, message) {
    // draw a single-label chart showing no data
    return new Chart(ctx, {
        type: type,
        data: {
            labels: [message],
            datasets: [{ label: message, data: [0], backgroundColor: 'rgba(200,200,200,0.5)' }]
        },
        options: { responsive: true, plugins: { legend: { display: false } } }
    });
}

function loadSummary(muni, event) {
    const muniClean = (muni || "").trim();
    if (!muniClean) return;

    // highlight selected
    document.querySelectorAll('#municipality-list li').forEach(li => li.classList.remove('selected'));
    if (event && event.target) event.target.classList.add('selected');

    document.getElementById('muni-name').textContent = muniClean;

    fetch(`/api/summary/${encodeURIComponent(muniClean)}`)
        .then(res => {
            if (!res.ok) throw new Error('Network response not ok');
            return res.json();
        })
        .then(data => {
            // update summary cards
            document.getElementById('most-crime').textContent = data.most_crime || 'N/A';
            document.getElementById('total-crimes').textContent = data.total_crimes ?? 0;
            document.getElementById('peak-month').textContent = data.peak_month || 'N/A';
            document.getElementById('peak-year').textContent = data.peak_year || 'N/A';

            // if analytics visible, update charts (otherwise user will click See Detailed Analytics)
            if (document.getElementById('analytics').style.display !== 'none') {
                updateChartsFromData(data);
            }
        })
        .catch(err => {
            console.error('Failed to load summary:', err);
        });
}

function toggleAnalytics() {
    const div = document.getElementById('analytics');
    const visible = div.style.display !== 'none';
    if (visible) {
        div.style.display = 'none';
        return;
    }
    div.style.display = 'block';
    // load charts for currently selected municipality
    const muni = document.getElementById('muni-name').textContent.trim();
    if (!muni) return;
    fetch(`/api/summary/${encodeURIComponent(muni)}`)
        .then(res => res.json())
        .then(data => updateChartsFromData(data))
        .catch(err => console.error(err));
}

function updateChartsFromData(data) {
    // crime bar chart (data.crime_counts.labels, data.crime_counts.values)
    const barCtx = document.getElementById('crimeBarChart').getContext('2d');
    if (crimeBarChart) { crimeBarChart.destroy(); crimeBarChart = null; }

    const crimeLabels = (data.crime_counts && data.crime_counts.labels) || [];
    const crimeValues = (data.crime_counts && data.crime_counts.values) || [];

    if (crimeLabels.length === 0) {
        crimeBarChart = safeEmptyChart(barCtx, 'bar', 'No crime-type data (excl. Others)');
    } else {
        crimeBarChart = new Chart(barCtx, {
            type: 'bar',
            data: { labels: crimeLabels, datasets: [{ label: 'Counts', data: crimeValues, backgroundColor: 'rgba(255,99,132,0.6)' }] },
            options: { responsive: true, scales: { y: { beginAtZero: true } } }
        });
    }

    // month line chart
    const monthCtx = document.getElementById('monthLineChart').getContext('2d');
    if (monthLineChart) { monthLineChart.destroy(); monthLineChart = null; }
    const monthLabels = (data.month_trend && data.month_trend.labels) || [];
    const monthValues = (data.month_trend && data.month_trend.values) || [];
    if (monthLabels.length === 0) {
        monthLineChart = safeEmptyChart(monthCtx, 'line', 'No monthly data');
    } else {
        monthLineChart = new Chart(monthCtx, {
            type: 'line',
            data: { labels: monthLabels, datasets: [{ label: 'Monthly crimes', data: monthValues, borderColor: 'rgba(54,162,235,1)', backgroundColor: 'rgba(54,162,235,0.15)', fill: true }] },
            options: { responsive: true, scales: { y: { beginAtZero: true } } }
        });
    }

    // year line chart
    const yearCtx = document.getElementById('yearLineChart').getContext('2d');
    if (yearLineChart) { yearLineChart.destroy(); yearLineChart = null; }
    const yearLabels = (data.year_trend && data.year_trend.labels) || [];
    const yearValues = (data.year_trend && data.year_trend.values) || [];
    if (yearLabels.length === 0) {
        yearLineChart = safeEmptyChart(yearCtx, 'line', 'No yearly data');
    } else {
        yearLineChart = new Chart(yearCtx, {
            type: 'line',
            data: { labels: yearLabels, datasets: [{ label: 'Yearly crimes', data: yearValues, borderColor: 'rgba(255,206,86,1)', backgroundColor: 'rgba(255,206,86,0.15)', fill: true }] },
            options: { responsive: true, scales: { y: { beginAtZero: true } } }
        });
    }
}

// initialize first municipality on page load
window.addEventListener('DOMContentLoaded', () => {
    const firstLi = document.querySelector('#municipality-list li.selected') || document.querySelector('#municipality-list li');
    if (firstLi) {
        const muni = firstLi.textContent.trim();
        // add selected class explicitly
        firstLi.classList.add('selected');
        // load summary (do not expand analytics automatically)
        loadSummary(muni, { target: firstLi });
    }
});
