import time
import statistics
from collections import defaultdict, deque
from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse,HTMLResponse

# 🌍 Global latency store — accessible everywhere
GLOBAL_LATENCIES = defaultdict(lambda: deque(maxlen=100))


def get_stats():
    """Compute latency stats directly from GLOBAL_LATENCIES."""
    stats = {}
    for route, times in GLOBAL_LATENCIES.items():
        if not times:
            continue
        stats[route] = {
            "count": len(times),
            "avg_ms": round(statistics.mean(times), 2),
            "min_ms": round(min(times), 2),
            "max_ms": round(max(times), 2),
            "p95_ms": (
                round(statistics.quantiles(times, n=100)[94], 2)
                if len(times) >= 20
                else None
            ),
        }
    return stats


def _register_route(app: FastAPI):
    """Attach /__latency_stats__ endpoint (only once)."""
    
    @app.get("/__latency_stats__", include_in_schema=False)
    async def latency_stats():
        return JSONResponse(get_stats())
    
    @app.get("/__latency_dashboard__", include_in_schema=False)
    async def latency_dashboard():
        html = """
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <title>Latency Dashboard</title>
                <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
                <style>
                    body {
                        font-family: system-ui, sans-serif;
                        background: #0d1117;
                        color: #e6edf3;
                        margin: 0;
                        padding: 2rem;
                    }
                    h1 {
                        text-align: center;
                        margin-bottom: 1rem;
                    }
                    #charts {
                        display: grid;
                        grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
                        gap: 2rem;
                        justify-content: center;
                        padding: 1rem;
                    }
                    .chart-card {
                        background: #161b22;
                        border-radius: 12px;
                        padding: 1rem;
                        box-shadow: 0 0 10px #0006;
                        width: 100%;
                        max-width: 450px;
                        margin: 0.5rem;
                        transition: transform 0.2s ease, box-shadow 0.2s ease;
                    }
                    .chart-card:hover {
                        transform: translateY(-5px);
                        box-shadow: 0 0 12px #0008;
                    }
                    canvas {
                        width: 100% !important;
                        height: 220px !important;
                    }
                    button {
                        background: #238636;
                        color: white;
                        border: none;
                        border-radius: 6px;
                        padding: 6px 12px;
                        cursor: pointer;
                        font-size: 0.9rem;
                        margin-top: 8px;
                        transition: background 0.2s ease;
                    }
                    button:hover {
                        background: #2ea043;
                    }
                </style>
            </head>
            <body>
                <h1>🚀 Latency Dashboard</h1>
                <p style="text-align:center;">Auto-refreshes every 10 seconds</p>
                <div id="charts"></div>
                <script>
                    const container = document.getElementById('charts');
                    let charts = {};

                    async function updateCharts() {
                        const res = await fetch('/internal/__latency_stats__');
                        const data = await res.json();

                        // Clear old charts for disappeared routes
                        for (const route in charts) {
                            if (!(route in data)) {
                                charts[route].destroy();
                                delete charts[route];
                                const el = document.getElementById('chart-' + btoa(route));
                                if (el) el.parentNode.remove();
                            }
                        }

                        for (const [route, stats] of Object.entries(data)) {
                            const id = 'chart-' + btoa(route);
                            let canvas = document.getElementById(id);
                            if (!canvas) {
                                const card = document.createElement('div');
                                card.className = 'chart-card';

                                const title = document.createElement('h3');
                                title.textContent = route;
                                title.style.textAlign = 'center';
                                card.appendChild(title);

                                const canvas = document.createElement('canvas');
                                canvas.id = id;
                                card.appendChild(canvas);

                                // Add "Profile this route" button
                                const btn = document.createElement('button');
                                btn.textContent = '🧠 Profile this route';
                                btn.onclick = () => {
                                    const url = route.includes('?')
                                        ? `${route}&profile`
                                        : `${route}?profile`;
                                    window.open(url, '_blank');
                                };
                                card.appendChild(btn);

                                container.appendChild(card);
                            }

                            // (Re)create or update the chart
                            if (!charts[route]) {
                                charts[route] = new Chart(document.getElementById(id), {
                                    type: 'bar',
                                    data: {
                                        labels: ['avg', 'min', 'max', 'p95'],
                                        datasets: [{
                                            label: 'ms',
                                            data: [stats.avg_ms, stats.min_ms, stats.max_ms, stats.p95_ms || 0],
                                            backgroundColor: ['#58a6ff', '#3fb950', '#f85149', '#e3b341']
                                        }]
                                    },
                                    options: {
                                        responsive: true,
                                        plugins: { legend: { display: false } },
                                        scales: {
                                            y: { beginAtZero: true, ticks: { color: '#e6edf3' } },
                                            x: { ticks: { color: '#e6edf3' } }
                                        }
                                    }
                                });
                            } else {
                                charts[route].data.datasets[0].data = [
                                    stats.avg_ms, stats.min_ms, stats.max_ms, stats.p95_ms || 0
                                ];
                                charts[route].update();
                            }
                        }
                    }

                    updateCharts();
                    setInterval(updateCharts, 10000);
                </script>
            </body>
            </html>
            """
        return HTMLResponse(html)

class LatencyMiddleware(BaseHTTPMiddleware):
    """
    Tracks latency for each endpoint globally.
    Exposes results at /__latency_stats__ and updates GLOBAL_LATENCIES.
    """

    def __init__(self, app: FastAPI, history_size: int = 100):
        super().__init__(app)
        self.history_size = history_size

        # Update the maxlen globally if needed
        global GLOBAL_LATENCIES
        for path, dq in GLOBAL_LATENCIES.items():
            GLOBAL_LATENCIES[path] = deque(dq, maxlen=history_size)


    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        elapsed = (time.perf_counter() - start) * 1000  # ms

        path = request.url.path
        GLOBAL_LATENCIES[path].append(elapsed)
        print(f"🔹 {request.method} {path} took {elapsed:.2f} ms")

        return response
