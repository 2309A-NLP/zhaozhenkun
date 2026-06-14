"""
Simple Prometheus-compatible metrics for RAGFlow.
Provides a /metrics endpoint for Prometheus scraping.
No external dependencies - uses plain text format.
"""
import time
import threading
from collections import defaultdict
from functools import wraps

# Global metrics store
_metrics = {}
_lock = threading.Lock()

# Track these counters
METRICS = {
    "ragflow_chat_requests_total": "counter",
    "ragflow_chat_requests_failed": "counter", 
    "ragflow_chat_request_duration_seconds": "histogram",
    "ragflow_llmbundle_cache_hits": "counter",
    "ragflow_llmbundle_cache_misses": "counter",
    "ragflow_langfuse_cache_hits": "counter",
    "ragflow_langfuse_cache_misses": "counter",
    "ragflow_concurrent_requests": "gauge",
    "ragflow_db_connections_active": "gauge",
}

def init_metrics():
    for name, mtype in METRICS.items():
        if mtype == "counter":
            _metrics[name] = 0
        elif mtype == "histogram":
            _metrics[name] = []
        elif mtype == "gauge":
            _metrics[name] = 0

def inc_counter(name, value=1):
    with _lock:
        if name in _metrics:
            _metrics[name] += value

def observe_histogram(name, value):
    with _lock:
        if name in _metrics:
            _metrics[name].append(value)
            # Keep last 1000 observations
            if len(_metrics[name]) > 1000:
                _metrics[name] = _metrics[name][-1000:]

def set_gauge(name, value):
    with _lock:
        if name in _metrics:
            _metrics[name] = value

def get_metrics_text():
    """Generate Prometheus text format output."""
    lines = []
    with _lock:
        for name, mtype in METRICS.items():
            lines.append(f"# HELP {name} RAGFlow metric")
            lines.append(f"# TYPE {name} {mtype}")
            value = _metrics.get(name, 0)
            if mtype == "histogram":
                data = list(value)
                if data:
                    lines.append(f"{name}_sum {sum(data)}")
                    lines.append(f"{name}_count {len(data)}")
                    sorted_data = sorted(data)
                    lines.append(f"{name}_bucket{{le=\"1.0\"}} {sum(1 for v in sorted_data if v <= 1.0)}")
                    lines.append(f"{name}_bucket{{le=\"5.0\"}} {sum(1 for v in sorted_data if v <= 5.0)}")
                    lines.append(f"{name}_bucket{{le=\"10.0\"}} {sum(1 for v in sorted_data if v <= 10.0)}")
                    lines.append(f"{name}_bucket{{le=\"30.0\"}} {sum(1 for v in sorted_data if v <= 30.0)}")
                    lines.append(f"{name}_bucket{{le=\"+Inf\"}} {len(data)}")
            else:
                lines.append(f"{name} {value}")
    return "\n".join(lines) + "\n"


def track_chat_request(func):
    """Decorator to track chat request metrics."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        inc_counter("ragflow_chat_requests_total")
        set_gauge("ragflow_concurrent_requests", 
                  _metrics.get("ragflow_chat_requests_total", 0) - _metrics.get("ragflow_chat_requests_failed", 0))
        start = time.perf_counter()
        try:
            result = func(*args, **kwargs)
            return result  # Returns coroutine for async functions
        except Exception:
            inc_counter("ragflow_chat_requests_failed")
            raise
        finally:
            elapsed = time.perf_counter() - start
            observe_histogram("ragflow_chat_request_duration_seconds", elapsed)
            set_gauge("ragflow_concurrent_requests",
                      _metrics.get("ragflow_chat_requests_total", 0) - _metrics.get("ragflow_chat_requests_failed", 0))
    return wrapper


# Initialize metrics
init_metrics()
