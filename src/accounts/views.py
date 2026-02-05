from django.utils import timezone
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import login, logout, authenticate, get_user_model, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm, SetPasswordForm
from django.conf import settings
from django.core.mail import EmailMessage
from django.urls import reverse
from .forms import SignUpForm
from .models import AdminRequest, PasswordReset, Team, TeamMembership
from django.db.models import Q, Case, When, IntegerField
from django.db import transaction
from django.core.exceptions import PermissionDenied
from plasmids.models import Collection
from plasmids.models import MappingCollection
from browse.models import Assembly


User = get_user_model()

# -----------------------
# SIGNUP
# -----------------------

def signup_view(request):
    if request.user.is_authenticated:
        return redirect("profile")

    if request.method == "POST":
        form = SignUpForm(request.POST)

        if form.is_valid():
            user = form.save()

            login(
                request,
                user,
                backend=settings.AUTHENTICATION_BACKENDS[0],
            )

            messages.success(request, "Account created successfully!")
            return redirect("profile")

    else:
        form = SignUpForm()

    return render(request, "accounts/signup.html", {"form": form})

# -----------------------
# LOGIN
# -----------------------
def login_view(request):
    if request.user.is_authenticated:
        return redirect("profile")

    if request.method == "POST":
        username = request.POST.get("username", "").strip().lower() 
        password = request.POST.get("password", "")

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user, backend=settings.AUTHENTICATION_BACKENDS[0])
            next_url = request.POST.get("next")
            return redirect(next_url) if next_url else redirect("profile")

        messages.error(request, "Invalid email or password. Please try again.")
        return redirect("login")

    return render(request, "accounts/login.html")


# -----------------------
# LOGOUT
# -----------------------
def logout_view(request):
    logout(request)
    return redirect("login")


# -----------------------
# FORGOT PASSWORD
# -----------------------
def forgot_password_view(request):
    if request.user.is_authenticated:
        return redirect("profile")

    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()
        if not email:
            messages.error(request, "Please enter an email address.")
            return redirect("forgot_password")

        user = User.objects.filter(email__iexact=email).first()
        if not user:
            messages.error(request, f"No account found with email '{email}'.")
            return redirect("forgot_password")

        PasswordReset.objects.filter(user=user).delete()
        reset = PasswordReset.objects.create(user=user)

        reset_url = request.build_absolute_uri(
            reverse("reset_password", kwargs={"reset_id": reset.reset_id})
        )

        try:
            EmailMessage(
                "Reset your password",
                f"Reset your password using the link below:\n\n{reset_url}\n\n"
                "This link expires in 10 minutes.",
                settings.EMAIL_HOST_USER,
                [email],
            ).send(fail_silently=False)

        except Exception:
            messages.error(request, "An error occurred while sending the email. Please try again later.")
            return redirect("forgot_password")

        return redirect("password_reset_sent")

    return render(request, "accounts/forgot_password.html")


# -----------------------
# RESET EMAIL SENT
# -----------------------
def password_reset_sent_view(request):
    return render(request, "accounts/password_reset_sent.html")


# -----------------------
# RESET PASSWORD
# -----------------------
def reset_password_view(request, reset_id):
    reset = PasswordReset.objects.filter(reset_id=reset_id).first()

    if not reset:
        messages.error(request, "Invalid reset link.")
        return redirect("forgot_password")

    if reset.is_expired(minutes=10):
        reset.delete()
        messages.error(request, "Reset link has expired. Please request a new one.")
        return redirect("forgot_password")

    user = reset.user

    if request.method == "POST":
        form = SetPasswordForm(user, request.POST)

        if form.is_valid():
            form.save()
            reset.delete()
            messages.success(request, "Password reset. Proceed to login.")
            return redirect("login")

        # display validation errors nicely
        for field, errs in form.errors.items():
            for err in errs:
                messages.error(request, err)

    else:
        form = SetPasswordForm(user)

    return render(request, "accounts/reset_password.html", {"form": form})

# -----------------------
# PROFILE (template has TWO raw forms with form_type)
# Important to signal which one is submitted to avoid confusion
# -----------------------
@login_required
def profile_view(request):
    if request.method == "POST":
        form_type = request.POST.get("form_type")

        # change password block (Django built-in form)
        if form_type == "change_password":
            password_form = PasswordChangeForm(request.user, request.POST)
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)  # to keep session active
                messages.success(request, "Your password has been successfully updated!")
                return redirect("profile")

            for field, errs in password_form.errors.items():
                for err in errs:
                    messages.error(request, err)
            return redirect("profile")

        # personal info block
        if form_type == "personal_info":
            first_name = request.POST.get("first_name", "").strip()
            last_name = request.POST.get("last_name", "").strip()
            email = request.POST.get("email", "").strip().lower()

            if not first_name or not last_name or not email:
                messages.error(request, "Please fill in all required fields.")
                return redirect("profile")

            # unique email check
            if email != request.user.email:
                if User.objects.filter(email__iexact=email).exclude(pk=request.user.pk).exists():
                    messages.error(request, "This email is already in use. Please choose a different one.")
                    return redirect("profile")

            request.user.first_name = first_name
            request.user.last_name = last_name
            request.user.email = email
            request.user.username = email
            request.user.save()

            messages.success(request,
                            "Your personal information has been successfully updated!")
            return redirect("profile")

    return render(request, "accounts/profile.html", {"user": request.user})


# -----------------------
# TEAMS PAGES
# -----------------------

@login_required
def teams_view(request):
    # All memberships of the current user
    memberships = (
        TeamMembership.objects
        .select_related("team")
        .filter(user=request.user)
    )

    teams_data = []

    for membership in memberships:
        team = membership.team

        # All members of the team, leader first
        members = (
            team.memberships
            .select_related("user")
            .annotate(
                role_order=Case(
                    When(role=TeamMembership.Role.LEADER, then=0),
                    default=1,
                    output_field=IntegerField(),
                )
            )
            .order_by("role_order", "joined_at")
        )

        teams_data.append({
            "team": team,
            "my_role": membership.role,
            "members_preview": members[:3],
            "members_count": members.count(),
            "is_leader": membership.role == TeamMembership.Role.LEADER,
        })

    return render(
        request,
        "accounts/teams.html",
        {"teams_data": teams_data},
    )

@login_required
def teams_create_view(request):
    q = request.GET.get("user_q", "").strip()

    # Selected users stored in session
    selected_ids = request.session.get("team_selected_ids", [])
    selected_ids = [int(x) for x in selected_ids if str(x).isdigit()]
    request.session["team_selected_ids"] = selected_ids

    selected_users = User.objects.filter(id__in=selected_ids).order_by("email")

    users = []
    if q:
        users = (
            User.objects
            .filter(
                Q(email__icontains=q) |
                Q(username__icontains=q) |
                Q(first_name__icontains=q) |
                Q(last_name__icontains=q)
            )
            .exclude(pk=request.user.pk)        
            .exclude(id__in=selected_ids)       
            .order_by("email")[:20]
        )

    if request.method == "POST":
        action = request.POST.get("action", "").strip()

        # 1) Add/remove members
        if action in {"add", "remove"}:
            user_id = request.POST.get("user_id")

            if user_id and user_id.isdigit():
                user_id = int(user_id)

                if action == "add":
                    if user_id not in selected_ids:
                        selected_ids.append(user_id)
                        request.session["team_selected_ids"] = selected_ids
                        messages.success(request, "Member added.")
                    return redirect(f"{request.path}?user_q={q}")

                if action == "remove":
                    if user_id in selected_ids:
                        selected_ids.remove(user_id)
                        request.session["team_selected_ids"] = selected_ids
                        messages.success(request, "Member removed.")
                    return redirect(f"{request.path}?user_q={q}")

            messages.error(request, "Invalid member action.")
            return redirect(request.path)

        # 2) Create the team in DB
        if action == "create_team":
            team_name = request.POST.get("team_name", "").strip()

            if not team_name:
                messages.error(request, "Please provide a team name.")
                return redirect(request.path)
            try:
                with transaction.atomic():
                    team = Team.objects.create(name=team_name, teamleader=request.user)

                    # Owner becomes leader (and also a member)
                    TeamMembership.objects.create(
                        team=team,
                        user=request.user,
                        role=TeamMembership.Role.LEADER,
                    )

                    # Add selected users as members
                    for u in selected_users:
                        TeamMembership.objects.get_or_create(
                            team=team,
                            user=u,
                            defaults={"role": TeamMembership.Role.MEMBER},
                        )

                # Clear session selection after successful creation
                request.session["team_selected_ids"] = []
                messages.success(request, "Team created successfully.")
                return redirect("teams")

            except Exception:
                messages.error(request, "An unexpected error occurred. Please try again.")
                return redirect(request.path)

        messages.error(request, "Invalid action.")
        return redirect(request.path)

    return render(
        request,
        "accounts/teams_create.html",
        {
            "users": users,
            "selected_users": selected_users,
            "user_q": q,
        },
    )

## Still issue here for  mapping tables management 
## to be fixed when mapping models are stabilized
@login_required
def team_detail_view(request, team_id):
    team = get_object_or_404(Team, id=team_id)

    membership = TeamMembership.objects.filter(
        team=team,
        user=request.user
    ).first()

    if not membership:
        messages.error(request, "You are not a member of this team.")
        return redirect("teams")

    members = (
        team.memberships
        .select_related("user")
        .order_by("role", "joined_at")
    )

    collections = (
        Collection.objects
        .filter(team=team)
        .select_related("owner")
        .order_by("-created_at")
    )

    assemblies = (
        Assembly.objects
        .filter(team=team)
        .order_by("-creation_date")
    )

    if request.method == "POST":
        action = request.POST.get("action")

        # ADMIN here can make collection public
        if action == "make_public":
            if not request.user.is_superuser:
                raise PermissionDenied

            collection_id = request.POST.get("collection_id")
            collection = get_object_or_404(Collection, id=collection_id, team=team)

            collection.is_public = True
            collection.save()
            messages.success(request, f"Collection '{collection.name}' is now public.")
            return redirect("team_details", team_id=team.id)
        
        if action == "attach_collection":
            if membership.role != TeamMembership.Role.LEADER:
                raise PermissionDenied

            collection_id = request.POST.get("collection_id")
            collection = get_object_or_404(
                Collection,
                id=collection_id,
                owner=request.user,
                team__isnull=True
            )

            collection.team = team
            collection.save()

            messages.success(
                request,
                f"Collection '{collection.name}' added to the team."
            )
            return redirect("team_details", team_id=team.id)

        if action == "detach_collection":
            if membership.role != TeamMembership.Role.LEADER:
                raise PermissionDenied

            collection_id = request.POST.get("collection_id")
            collection = get_object_or_404(
                Collection,
                id=collection_id,
                team=team
            )

            collection.team = None
            collection.save()

            messages.success(
                request,
                f"Collection '{collection.name}' removed from the team."
            )
            return redirect("team_details", team_id=team.id)

        if action == "attach_assembly":
            if membership.role != TeamMembership.Role.LEADER:
                raise PermissionDenied

            assembly_id = request.POST.get("assembly_id")
            assembly = get_object_or_404(
                Assembly,
                id=assembly_id,
                owner=request.user,
                team__isnull=True
            )

            assembly.team = team
            assembly.save()

            messages.success(
                request,
                f"Assembly '{assembly.name}' added to the team."
            )
            return redirect("team_details", team_id=team.id)

        if action == "detach_assembly":
            if membership.role != TeamMembership.Role.LEADER:
                raise PermissionDenied

            assembly_id = request.POST.get("assembly_id")
            assembly = get_object_or_404(
                Assembly,
                id=assembly_id,
                team=team
            )

            assembly.team = None
            assembly.save()

            messages.success(
                request,
                f"Assembly '{assembly.name}' removed from the team."
            )
            return redirect("team_details", team_id=team.id)
        

    available_collections = Collection.objects.filter(
        owner=request.user,
        team__isnull=True
    )
    available_assemblies = Assembly.objects.filter(
        owner=request.user,
        team__isnull=True
    ).order_by("-creation_date")

    return render(request, "accounts/team_details.html", {
        "team": team,
        "members": members,
        "membership": membership,
        "collections": collections,
        "assemblies": assemblies,
        "available_collections": available_collections,
        "available_assemblies": available_assemblies,
        "is_admin": request.user.is_superuser,
    })



# -----------------------
# Team Management
# -----------------------
@login_required
def team_manage_view(request, team_id):
    team = get_object_or_404(Team, id=team_id)

    membership = TeamMembership.objects.filter(
        team=team,
        user=request.user,
        role=TeamMembership.Role.LEADER
    ).first()

    if not membership:
        messages.error(request, "Only the team leader can manage this team.")
        return redirect("team_details", team_id=team.id)

    members = team.memberships.select_related("user")

    q = request.GET.get("user_q", "").strip()
    candidates = User.objects.none()

    if q:
        candidates = (
            User.objects
            .filter(email__icontains=q)
            .exclude(id__in=members.values_list("user_id", flat=True))
        )

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "rename":
            new_name = request.POST.get("team_name", "").strip()
            if not new_name:
                messages.error(request, "Team name cannot be empty.")
            else:
                team.name = new_name
                team.save()
                messages.success(request, "Team name updated.")

        elif action == "remove":
            deleted, _ = TeamMembership.objects.filter(
                team=team,
                user_id=request.POST.get("user_id"),
                role=TeamMembership.Role.MEMBER
            ).delete()

            if deleted:
                messages.warning(request, "Member removed from the team.")
            else:
                messages.error(request, "Unable to remove this member.")

        elif action == "add":
            obj, created = TeamMembership.objects.get_or_create(
                team=team,
                user_id=request.POST.get("user_id"),
                defaults={"role": TeamMembership.Role.MEMBER},
            )

            if created:
                messages.success(request, "Member added to the team.")
            else:
                messages.info(request, "This user is already a member of the team.")

        return redirect("team_manage", team_id=team.id)

    return render(request, "accounts/team_manage.html", {
        "team": team,
        "members": members,
        "candidates": candidates,
        "user_q": q,
    })

# ------------------------
# ADMIN VIEWS - Users list
# ------------------------
@login_required
def admin_users_view(request):
    if not request.user.is_superuser:
        raise PermissionDenied

    if request.method == "POST":
        user_id = request.POST.get("user_id")
        user = get_object_or_404(User, id=user_id)

        if not user.is_superuser:
            user.is_superuser = True
            user.is_staff = True
            user.save()
            messages.success(
                request,
                f"{user.email} is now an administrator."
            )

        return redirect("admin_users")

    users = User.objects.all().order_by("-last_login", "email")

    return render(
        request,
        "accounts/admin_users.html",
        {"users": users},
    )

# -------------------------------------
# ADMIN manage users requests -> public
# -------------------------------------
@login_required
def admin_requests_view(request):
    if not request.user.is_superuser:
        raise PermissionDenied

    pending_requests = (
        AdminRequest.objects
        .filter(status=AdminRequest.Status.PENDING)
        .select_related("user", "collection", "assembly", "mapping_collection")
        .prefetch_related("collection__plasmids")
        .order_by("-created_at")
    )

    completed_requests = (
        AdminRequest.objects
        .exclude(status=AdminRequest.Status.PENDING)
        .select_related("user", "collection", "assembly", "mapping_collection")
        .order_by("-processed_at")
    )

    if request.method == "POST":
        req = get_object_or_404(AdminRequest, id=request.POST.get("request_id"))
        action = request.POST.get("action")

        if action == "approve":

            if req.request_type == AdminRequest.RequestType.MAKE_COLLECTION_PUBLIC:
                if req.collection:
                    req.collection.make_public()

            elif req.request_type == AdminRequest.RequestType.MAKE_ASSEMBLY_PUBLIC:
                if req.assembly:
                    req.assembly.is_public = True
                    req.assembly.save()

            elif req.request_type == AdminRequest.RequestType.MAKE_MAPPING_COLLECTION_PUBLIC:
                if req.mapping_collection:
                    req.mapping_collection.make_public()

            req.status = AdminRequest.Status.APPROVED
            req.processed_at = timezone.now()
            req.processed_by = request.user
            req.save()

            messages.success(
                request,
                f"Request approved successfully for {req.user.email}."
            )
        elif action == "reject":
            req.status = AdminRequest.Status.REJECTED
            req.admin_message = request.POST.get("admin_message", "")
            req.processed_at = timezone.now()
            req.save()
            req.processed_by = request.user
            req.save()

            messages.success(
                request,
                f"Request rejected successfully for {req.user.email}."
            )

        return redirect("admin_requests")

    return render(request, "accounts/admin_requests.html", {
        "pending_requests": pending_requests,
        "completed_requests": completed_requests,
    })

# --------------------------------------------
# user sends request to make collection public
# --------------------------------------------
@login_required
def request_make_collection_public(request, collection_id):
    collection = get_object_or_404(
        Collection,
        id=collection_id,
        owner=request.user,
        is_public=False
    )

    # Remove any existing requests for this collection
    AdminRequest.objects.filter(
        collection=collection
    ).delete()

    # old request replaced by new one
    AdminRequest.objects.create(
        user=request.user,
        request_type=AdminRequest.RequestType.MAKE_COLLECTION_PUBLIC,
        collection=collection,
        message="Please make this collection public."
    )

    messages.info(
        request,
        "Your request has been sent."
    )

    return redirect("plasmids:collections_list")


# ------------------------------------------
# user requests view - list of his requests
# ------------------------------------------
@login_required
def user_requests_view(request):
    requests = (
        AdminRequest.objects
        .filter(user=request.user)
        .order_by("-created_at")
    )

    return render(request, "accounts/user_requests.html", {
        "requests": requests
    })


# ------------------------------------------
# user sends request to make assembly public
# ------------------------------------------
@login_required
def request_make_assembly_public(request, assembly_id):
    assembly = get_object_or_404(
        Assembly,
        id=assembly_id,
        owner=request.user,
        is_public=False
    )

    AdminRequest.objects.filter(
        assembly=assembly
    ).delete()

    AdminRequest.objects.create(
        user=request.user,
        request_type=AdminRequest.RequestType.MAKE_ASSEMBLY_PUBLIC,
        assembly=assembly,
        message="Please make this assembly public."
    )

    messages.info(request, "Your request has been sent.")

    return redirect("browse:browse_templates")

# ------------------------------------------------
# user sends request to make mapping table public
# ------------------------------------------------

@login_required
def request_make_mapping_collection_public(request, collection_id):
    # Fetch the collection instead of a single table
    collection = get_object_or_404(
        MappingCollection,
        id=collection_id,
        owner=request.user,
        is_public=False,
    )

    AdminRequest.objects.filter(mapping_collection=collection).delete()

    AdminRequest.objects.create(
        user=request.user,
        request_type=AdminRequest.RequestType.MAKE_MAPPING_COLLECTION_PUBLIC, 
        mapping_collection=collection, 
        message=f"Please make the mapping collection '{collection.name}' public.",
    )

    messages.info(request, "Your request for the collection has been sent.")
    return redirect(request.META.get("HTTP_REFERER", "/"))
