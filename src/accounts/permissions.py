from .models import TeamMembership


def is_team_leader(user, team):
    return TeamMembership.objects.filter(
        team=team,
        user=user,
        role=TeamMembership.Role.LEADER
    ).exists()


def is_admin(user):
    return user.is_staff