# app/core/scheduler_decorators.py
from functools import wraps
from typing import Callable, Dict, Any, List

# Global registry of scheduled Dramatiq tasks
SCHEDULED_TASKS: List[Dict[str, Any]] = []

def _register_task(func: Callable, trigger: str, **trigger_args):
    """Internal: Register the decorated function and schedule info."""
    SCHEDULED_TASKS.append({
        "func": func,
        "trigger": trigger,
        "trigger_args": trigger_args,
    })
    return func

# --- Decorators for different intervals ---
def run_every_minute(func: Callable):
    return _register_task(func, "interval", minutes=1)

def run_every_hour(func: Callable):
    return _register_task(func, "interval", hours=1)

def run_every_day(hour: int = 0, minute: int = 0):
    def wrapper(func: Callable):
        return _register_task(func, "cron", hour=hour, minute=minute)
    return wrapper

def run_cron(expr: str):
    """Generic cron expression, e.g., run_cron('0 2 * * *')"""
    parts = expr.strip().split()
    if len(parts) != 5:
        raise ValueError("Invalid cron expression (expected 5 fields)")
    minute, hour, day, month, day_of_week = parts
    def wrapper(func: Callable):
        return _register_task(func, "cron", minute=minute, hour=hour, day=day, month=month, day_of_week=day_of_week)
    return wrapper
