import uuid

from django.conf import settings
from django.db import models


class RaceSession(models.Model):
    """An isolated race room. Room codes are shareable; race data is room-scoped."""
    code = models.CharField(max_length=8, unique=True, db_index=True)
    quote = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    @classmethod
    def new_code(cls):
        while True:
            code = uuid.uuid4().hex[:6].upper()
            if not cls.objects.filter(code=code).exists():
                return code


class RaceParticipant(models.Model):
    race = models.ForeignKey(RaceSession, related_name='participants', on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    session_key = models.CharField(max_length=40)
    display_name = models.CharField(max_length=32)
    progress = models.PositiveSmallIntegerField(default=0)
    wpm = models.PositiveSmallIntegerField(default=0)
    accuracy = models.PositiveSmallIntegerField(default=0)
    finished_at = models.DateTimeField(null=True, blank=True)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['race', 'session_key'], name='unique_race_browser_participant')]
