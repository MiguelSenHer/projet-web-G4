from django.contrib import admin
from .models import PasswordReset, Team, TeamMembership

admin.site.register(PasswordReset)
admin.site.register(Team)
admin.site.register(TeamMembership)