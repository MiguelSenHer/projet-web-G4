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

class Team(models.Model):
    name = models.CharField(max_length=150, unique=True)

    # The team creator becomes the team leader ("cheffe d'équipe")
    teamleader = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="owned_teams",
    )

    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.name


class TeamMembership(models.Model):
    class Role(models.TextChoices):
        LEADER = "LEADER", "Leader"
        MEMBER = "MEMBER", "Member"

    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="team_memberships",
    )

    role = models.CharField(max_length=10, choices=Role.choices, default=Role.MEMBER)
    joined_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            # A user cannot appear twice in the same team
            models.UniqueConstraint(fields=["team", "user"], name="uniq_team_user"),
        ]

    def __str__(self):
        return f"{self.team} - {self.user} ({self.role})"

class AdminRequest(models.Model):
    class RequestType(models.TextChoices):
        MAKE_COLLECTION_PUBLIC = "MAKE_COLLECTION_PUBLIC", "Make collection public"
        MAKE_ASSEMBLY_PUBLIC = "MAKE_ASSEMBLY_PUBLIC", "Make assembly public"
        MAKE_MAPPING_TABLE_PUBLIC = "MAKE_MAPPING_TABLE_PUBLIC", "Make mapping table public"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="admin_requests"
    )

    request_type = models.CharField(
        max_length=50,
        choices=RequestType.choices
    )

    collection = models.ForeignKey(
        "plasmids.Collection",
        null=True,
        blank=True,
        on_delete=models.CASCADE
    )

    mapping = models.ForeignKey(
        "plasmids.MappingTable",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
    )

    assembly = models.ForeignKey(
        "browse.Assembly",
        null=True,
        blank=True,
        on_delete=models.CASCADE
    )
    message = models.TextField(blank=True)

    admin_message = models.TextField(
        blank=True,
        help_text="Reason given by admin when rejecting"
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )

    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="processed_requests"
    )
    
    def __str__(self):
        return f"{self.user.email} - {self.request_type} - {self.status}"
