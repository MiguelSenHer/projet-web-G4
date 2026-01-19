## reset tokens

import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone

class PasswordReset(models.Model):
    reset_id = models.UUIDField(default=uuid.uuid4, unique=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_when = models.DateTimeField(default=timezone.now)

    def is_expired(self, minutes=10):
        return timezone.now() > self.created_when + timezone.timedelta(minutes=minutes)