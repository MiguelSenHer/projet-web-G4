from django.urls import path
from . import views

urlpatterns = [
    path("signup/", views.signup_view, name="signup"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),

    path("forgot-password/", views.forgot_password_view, name="forgot_password"),
    path("forgot-password/sent/", views.password_reset_sent_view, name="password_reset_sent"),
    path("reset-password/<uuid:reset_id>/", views.reset_password_view, name="reset_password"),

    path("profile/", views.profile_view, name="profile"),
    path("teams/", views.teams_view, name="teams"),
    path("teams/create/", views.teams_create_view, name="teams_create"),
    path("teams/<int:team_id>/details/", views.team_detail_view, name="team_details"),
    path("teams/<int:team_id>/manage/", views.team_manage_view, name="team_manage"),
    path("admin/users/", views.admin_users_view, name="admin_users"),
    path("admin/requests/", views.admin_requests_view, name="admin_requests"),
    path("requests/make-public/<int:collection_id>/", views.request_make_collection_public, name="request_make_public"
),

]
