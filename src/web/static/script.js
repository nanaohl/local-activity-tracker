
document.addEventListener('DOMContentLoaded', () => {
    const dailyBtn = document.getElementById('dailyBtn');
    const weeklyBtn = document.getElementById('weeklyBtn');
    const monthlyBtn = document.getElementById('monthlyBtn');
    const yearlyBtn = document.getElementById('yearlyBtn');
    const ctx = document.getElementById('activityChart').getContext('2d');
    let activityChart;
    let allData;

    function processData(data) {
        const appData = {};
        data.forEach(([appName, windowTitle, duration]) => {
            if (!appData[appName]) {
                appData[appName] = 0;
            }
            appData[appName] += duration;
        });
        return appData;
    }

    function renderChart(view) {
        const appData = processData(allData[view]);
        const labels = Object.keys(appData);
        const data = Object.values(appData);

        if (activityChart) {
            activityChart.destroy();
        }

        activityChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Time Spent (seconds)',
                    data: data,
                    backgroundColor: 'rgba(0, 123, 255, 0.5)',
                    borderColor: 'rgba(0, 123, 255, 1)',
                    borderWidth: 1
                }]
            },
            options: {
                scales: {
                    y: {
                        beginAtZero: true
                    }
                },
                responsive: true,
                maintainAspectRatio: false
            }
        });
    }

    fetch('/api/data')
        .then(response => response.json())
        .then(data => {
            allData = data;
            renderChart('daily'); // Default view
        });

    dailyBtn.addEventListener('click', () => renderChart('daily'));
    weeklyBtn.addEventListener('click', () => renderChart('weekly'));
    monthlyBtn.addEventListener('click', () => renderChart('monthly'));
    yearlyBtn.addEventListener('click', () => renderChart('yearly'));
});
