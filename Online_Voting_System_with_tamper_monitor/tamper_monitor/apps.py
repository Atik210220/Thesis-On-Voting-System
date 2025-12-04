from django.apps import AppConfig

class TamperMonitorConfig(AppConfig):
    name = 'tamper_monitor'
    default_auto_field = 'django.db.models.BigAutoField'

    def ready(self):
        try:
            from .detector import start_monitor_thread
            import sys
            if len(sys.argv) > 1 and sys.argv[1] in ('runserver', 'gunicorn', 'uwsgi'):
                start_monitor_thread()
        except Exception:
            pass
