try:
    from .tamper_monitor import start_tamper_monitor
    start_tamper_monitor()
except Exception:
    pass
