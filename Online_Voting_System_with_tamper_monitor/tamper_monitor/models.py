from django.db import models

class TamperAlert(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    summary = models.CharField(max_length=255)
    detail = models.TextField(blank=True)
    acknowledged = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.created_at.isoformat()} - {self.summary}"
