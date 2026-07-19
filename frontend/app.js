// State Management
let activeSource = "All Sources";
let searchQuery = "";

// Chart instances (tracked globally to allow updates/destruction)
let sourceChart = null;
let keywordChart = null;
let trendChart = null;

// Fetch and load initial configurations
document.addEventListener("DOMContentLoaded", () => {
    initFilters();
    loadDashboard();
    
    // Setup event listeners
    document.getElementById("source-filter").addEventListener("change", (e) => {
        activeSource = e.target.value;
        loadDashboard();
    });
    
    document.getElementById("article-search").addEventListener("input", (e) => {
        searchQuery = e.target.value;
        loadArticles();
    });
});

async function initFilters() {
    try {
        const res = await fetch("/api/sources");
        const sources = await res.json();
        const select = document.getElementById("source-filter");
        
        sources.forEach(src => {
            const opt = document.createElement("option");
            opt.value = src.source_name;
            opt.textContent = src.source_name.replace("_", " ").toUpperCase();
            select.appendChild(opt);
        });
    } catch (e) {
        console.error("Failed to load filter options:", e);
    }
}

function loadDashboard() {
    loadMetrics();
    loadSourceChart();
    loadKeywordChart();
    loadTrendChart();
    loadArticles();
}

async function loadMetrics() {
    try {
        const url = `/api/metrics?source=${encodeURIComponent(activeSource)}`;
        const res = await fetch(url);
        const data = await res.json();
        
        document.getElementById("total-articles-val").textContent = data.total_articles.toLocaleString();
        document.getElementById("avg-sentiment-val").textContent = data.avg_sentiment.toFixed(2);
        document.getElementById("positive-pct-val").textContent = `${data.pos_pct.toFixed(0)}%`;
        document.getElementById("negative-pct-val").textContent = `${data.neg_pct.toFixed(0)}%`;
        
        // Color avg sentiment based on value
        const valEl = document.getElementById("avg-sentiment-val");
        if (data.avg_sentiment > 0.05) {
            valEl.style.color = "#10b981"; // Positive Green
        } else if (data.avg_sentiment < -0.05) {
            valEl.style.color = "#ef4444"; // Negative Red
        } else {
            valEl.style.color = "#f3f1f7"; // Default Neutral
        }
    } catch (e) {
        console.error("Failed to load metrics:", e);
    }
}

async function loadSourceChart() {
    try {
        const res = await fetch("/api/sources");
        const data = await res.json();
        
        const ctx = document.getElementById("source-sentiment-chart").getContext("2d");
        
        if (sourceChart) sourceChart.destroy();
        
        const labels = data.map(item => item.source_name.replace("_", " ").toUpperCase());
        const scores = data.map(item => item.avg_sentiment);
        
        const gradient = ctx.createLinearGradient(0, 0, 0, 300);
        gradient.addColorStop(0, '#8b5cf6'); // Purple
        gradient.addColorStop(1, '#06b6d4'); // Cyan
        
        sourceChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Avg Sentiment',
                    data: scores,
                    backgroundColor: gradient,
                    borderRadius: 6,
                    borderWidth: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false }
                },
                scales: {
                    x: {
                        grid: { display: false },
                        ticks: { color: '#a49cb5', font: { family: 'Outfit' } }
                    },
                    y: {
                        min: -1.0,
                        max: 1.0,
                        grid: { color: 'rgba(255, 255, 255, 0.05)' },
                        ticks: { color: '#a49cb5', font: { family: 'Outfit' } }
                    }
                }
            }
        });
    } catch (e) {
        console.error("Failed to load source chart:", e);
    }
}

async function loadKeywordChart() {
    try {
        const res = await fetch("/api/keywords");
        const data = await res.json();
        
        const ctx = document.getElementById("top-keywords-chart").getContext("2d");
        
        if (keywordChart) keywordChart.destroy();
        
        const labels = data.map(item => item.keyword);
        const counts = data.map(item => item.mentions);
        
        const gradient = ctx.createLinearGradient(0, 0, 300, 0);
        gradient.addColorStop(0, '#14b8a6'); // Teal
        gradient.addColorStop(1, '#3b82f6'); // Blue
        
        keywordChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Mentions',
                    data: counts,
                    backgroundColor: gradient,
                    borderRadius: 6,
                    borderWidth: 0
                }]
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false }
                },
                scales: {
                    x: {
                        grid: { color: 'rgba(255, 255, 255, 0.05)' },
                        ticks: { color: '#a49cb5', font: { family: 'Outfit' } }
                    },
                    y: {
                        grid: { display: false },
                        ticks: { color: '#a49cb5', font: { family: 'Outfit' } }
                    }
                }
            }
        });
    } catch (e) {
        console.error("Failed to load keyword chart:", e);
    }
}

async function loadTrendChart() {
    try {
        const url = `/api/trends?source=${encodeURIComponent(activeSource)}`;
        const res = await fetch(url);
        const data = await res.json();
        
        const ctx = document.getElementById("sentiment-trend-chart").getContext("2d");
        
        if (trendChart) trendChart.destroy();
        
        const labels = data.map(item => item.date);
        const scores = data.map(item => item.avg_sentiment);
        
        trendChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Sentiment Trend',
                    data: scores,
                    borderColor: '#8b5cf6',
                    backgroundColor: 'rgba(139, 92, 246, 0.05)',
                    fill: true,
                    tension: 0.3,
                    pointBackgroundColor: '#14b8a6',
                    pointBorderWidth: 2,
                    pointHoverRadius: 6,
                    borderWidth: 3
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false }
                },
                scales: {
                    x: {
                        grid: { display: false },
                        ticks: { color: '#a49cb5', font: { family: 'Outfit' } }
                    },
                    y: {
                        min: -1.0,
                        max: 1.0,
                        grid: { color: 'rgba(255, 255, 255, 0.05)' },
                        ticks: { color: '#a49cb5', font: { family: 'Outfit' } }
                    }
                }
            }
        });
    } catch (e) {
        console.error("Failed to load trend chart:", e);
    }
}

async function loadArticles() {
    try {
        const url = `/api/articles?source=${encodeURIComponent(activeSource)}&search=${encodeURIComponent(searchQuery)}`;
        const res = await fetch(url);
        const articles = await res.json();
        
        const tbody = document.getElementById("articles-table-body");
        tbody.innerHTML = "";
        
        if (articles.length === 0) {
            const tr = document.createElement("tr");
            tr.innerHTML = `<td colspan="6" style="text-align: center; color: var(--text-secondary);">No articles found matching filters.</td>`;
            tbody.appendChild(tr);
            return;
        }
        
        articles.forEach(art => {
            const tr = document.createElement("tr");
            
            // Format source name
            const sourceDisplay = art.source_name.replace("_", " ").toUpperCase();
            
            // Determine sentiment label classes
            const labelClass = art.sentiment_label;
            
            tr.innerHTML = `
                <td>${art.published_at}</td>
                <td><span class="source-name">${sourceDisplay}</span></td>
                <td>${art.headline}</td>
                <td><strong>${art.sentiment_score.toFixed(2)}</strong></td>
                <td><span class="badge ${labelClass}">${art.sentiment_label}</span></td>
                <td><a href="${art.url}" target="_blank" class="btn-link">Open</a></td>
            `;
            tbody.appendChild(tr);
        });
    } catch (e) {
        console.error("Failed to load articles table:", e);
    }
}
