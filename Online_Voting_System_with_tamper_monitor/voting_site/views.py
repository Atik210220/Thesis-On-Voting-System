from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.hashers import make_password, check_password
from django.utils import timezone
from .forms import RegistrationForm, LoginForm, PositionForm
from .models import Voter, Election, ElectionVoter, Position, Candidate, Vote
import hashlib

# Landing page
def home(request):
    return render(request, "voting_site/index.html")


# Registration
def register(request):
    if request.method == "POST":
        form = RegistrationForm(request.POST, request.FILES)  # handle image upload
        if form.is_valid():
            voter = form.save(commit=False)
            voter.password_hash = make_password(form.cleaned_data['password'])
            voter.save()
            messages.success(request, "Registration successful. Please login.")
            return redirect("login")
    else:
        form = RegistrationForm()
    return render(request, "voting_site/register.html", {"form": form})


# Login
def login_view(request):
    if request.method == "POST":
        form = LoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            try:
                voter = Voter.objects.get(email=email)
                if check_password(password, voter.password_hash):
                    request.session['voter_id'] = voter.voter_id
                    if voter.is_admin:
                        messages.success(request, f"Welcome Admin {voter.name}!")
                        return redirect("admin_dashboard")
                    else:
                        messages.success(request, f"Welcome {voter.name}!")
                        return redirect("dashboard")
                else:
                    messages.error(request, "Invalid password")
            except Voter.DoesNotExist:
                messages.error(request, "Email not found")
    else:
        form = LoginForm()
    return render(request, "voting_site/login.html", {"form": form})


# Dashboard (for normal voters)
def dashboard(request):
    voter_id = request.session.get("voter_id")
    if not voter_id:
        return redirect("login")

    try:
        voter = Voter.objects.get(voter_id=voter_id)
    except Voter.DoesNotExist:
        messages.error(request, "Voter not found. Please login again.")
        return redirect("login")

    # Elections the voter is registered in (approved only)
    registered_elections = Election.objects.filter(
        voters__voter_id=voter_id,
        voters__is_approved=True
    ).distinct()

    # Filter upcoming elections for this voter
    upcoming_elections = Election.objects.exclude(
        voters__voter_id=voter_id
    ).order_by("start_date")

    # Annotate elections with current status
    for election in registered_elections:
        election.display_status = election.current_status()
    for election in upcoming_elections:
        election.display_status = election.current_status()

    return render(request, "voting_site/dashboard.html", {
        "voter": voter,
        "registered_elections": registered_elections,
        "upcoming_elections": upcoming_elections,
    })

def request_registration(request, election_id):
    voter_id = request.session.get("voter_id")
    if not voter_id:
        return redirect("login")

    election = get_object_or_404(Election, pk=election_id)
    voter = get_object_or_404(Voter, voter_id=voter_id)

    if ElectionVoter.objects.filter(election=election, voter=voter).exists():
        messages.info(request, "You have already requested registration for this election.")
    else:
        ElectionVoter.objects.create(election=election, voter=voter, is_approved=False)
        messages.success(request, f"Registration request sent for '{election.election_name}'. Wait for admin approval.")

    return redirect("dashboard")


# Election detail page (info only, with link to vote page)
def registered_election_detail(request, election_id):
    voter_id = request.session.get("voter_id")
    if not voter_id:
        return redirect("login")

    election = get_object_or_404(Election, pk=election_id)

    if not ElectionVoter.objects.filter(election=election, voter_id=voter_id, is_approved=True).exists():
        messages.error(request, "You are not approved for this election.")
        return redirect("dashboard")

    positions = Position.objects.filter(election=election).prefetch_related("candidates")
    for position in positions:
        position.approved_candidates = position.candidates.filter(is_approved=True)

    now = timezone.now()
    voting_open = election.current_status() == 'running' and not election.is_paused

    # Track positions the voter has already applied for as candidate
    voter_candidate_positions = Candidate.objects.filter(
        position__election=election,
        candidate_name=request.session.get('voter_name')  # or use voter_id
    ).values_list('position_id', flat=True)

    return render(request, "voting_site/registered_election_detail.html", {
        "election": election,
        "positions": positions,
        "voting_open": voting_open,
        "voter_candidate_positions": voter_candidate_positions,
        "current_status": election.current_status(),
    })



# Voting page (separate)
def vote_page(request, election_id):
    voter_id = request.session.get("voter_id")
    if not voter_id:
        return redirect("login")

    election = get_object_or_404(Election, pk=election_id)

    if election.is_paused:
        messages.error(request, "This election is currently paused by admin.")
        return redirect("registered_election_detail", election_id=election_id)

    now = timezone.now()
    voting_open = election.start_date <= now <= election.end_date

    if not voting_open:
        messages.error(request, "Voting is not open for this election.")
        return redirect("registered_election_detail", election_id=election_id)

    positions = Position.objects.filter(election=election)
    for position in positions:
        position.approved_candidates = position.candidates.filter(is_approved=True)

    already_voted_positions = set(
        Vote.objects.filter(voter_id=voter_id, candidate__position__election=election)
        .values_list("candidate__position_id", flat=True)
    )

    return render(request, "voting_site/vote.html", {
        "election": election,
        "positions": positions,
        "already_voted_positions": already_voted_positions,
    })


# Cast a vote
def vote_candidate(request, election_id, position_id, candidate_id):
    voter_id = request.session.get("voter_id")
    if not voter_id:
        return redirect("login")

    voter = get_object_or_404(Voter, pk=voter_id)  # Get Voter from session
    position = get_object_or_404(Position, pk=position_id)
    candidate = get_object_or_404(Candidate, pk=candidate_id, position=position)

    # Prevent multiple votes for the same position
    if Vote.objects.filter(voter=voter, position=position).exists():
        messages.error(request, "You have already voted for this position.")
        return redirect("vote_page", election_id=election_id)

    # Compute previous vote hash (latest vote in DB)
    last_vote = Vote.objects.order_by('-vote_id').first()
    previous_hash = last_vote.vote_hash if last_vote else ''

    # Compute hash for this vote
    vote_data = f"{voter.voter_id}-{position.position_id}-{candidate.candidate_id}-{timezone.now().isoformat()}-{previous_hash}"
    vote_hash = hashlib.sha256(vote_data.encode()).hexdigest()

    # Save vote
    Vote.objects.create(
        voter=voter,
        position=position,
        candidate=candidate,
        previous_vote_hash=previous_hash,
        vote_hash=vote_hash
    )

    messages.success(request, f"You voted for {candidate.candidate_name} in {position.position_name}.")
    return redirect("vote_page", election_id=election_id)



# Candidate application
def apply_for_position(request, election_id, position_id):
    voter_id = request.session.get("voter_id")
    if not voter_id:
        messages.error(request, "You must be logged in to apply.")
        return redirect("login")

    election = get_object_or_404(Election, election_id=election_id)
    position = get_object_or_404(Position, pk=position_id)
    voter = get_object_or_404(Voter, pk=voter_id)

    if election.is_paused:
        messages.error(request, "Candidate applications are currently paused by admin.")
        return redirect("registered_election_detail", election_id=election_id)

    if timezone.now() > election.candidate_deadline:
        messages.error(request, "Candidate application deadline has passed.")
        return redirect("registered_election_detail", election_id=election_id)

    # Check if already applied
    if Candidate.objects.filter(position=position, candidate_name=voter.name).exists():
        messages.info(request, "You have already applied for this position.")
        return redirect("registered_election_detail", election_id=election_id)

    # Create candidate
    Candidate.objects.create(
        position=position,
        candidate_name=voter.name,
        party=""  # optional, leave empty
    )
    messages.success(request, f"You have successfully applied for '{position.position_name}'. Awaiting approval.")
    return redirect("registered_election_detail", election_id=election_id)




# Logout
def logout_view(request):
    request.session.flush()
    messages.info(request, "You have been logged out.")
    return redirect("login")


# ---------------- Admin Section ---------------- #

def admin_dashboard(request):
    voter_id = request.session.get("voter_id")
    if not voter_id:
        return redirect("login")
    
    voter = Voter.objects.get(pk=voter_id)
    if not voter.is_admin:
        return redirect("dashboard")

    elections = Election.objects.all()
    for election in elections:
        election.pending_voters = election.voters.filter(is_approved=False)

    return render(request, "voting_site/admin_dashboard.html", {
        "voter": voter,
        "elections": elections,
    })


def manage_election(request, election_id):
    voter_id = request.session.get("voter_id")
    if not voter_id:
        return redirect("login")

    voter = Voter.objects.get(pk=voter_id)
    if not voter.is_admin:
        return redirect("dashboard")

    election = get_object_or_404(Election, pk=election_id)
    positions = Position.objects.filter(election=election)
    for position in positions:
        position.pending_candidates = position.candidates.filter(is_approved=False)

    pending_voters = election.voters.filter(is_approved=False)

    return render(request, "voting_site/manage_election.html", {
        "voter": voter,
        "election": election,
        "positions": positions,
        "pending_voters": pending_voters,
    })


def toggle_election_status(request, election_id):
    voter_id = request.session.get("voter_id")
    if not voter_id:
        return redirect("login")
    
    voter = get_object_or_404(Voter, voter_id=voter_id)
    if not voter.is_admin:
        return redirect("dashboard")

    election = get_object_or_404(Election, pk=election_id)
    election.is_paused = not election.is_paused
    election.save()
    
    messages.success(request, f"Election '{election.election_name}' is now {'paused' if election.is_paused else 'active'}.")
    return redirect("manage_election", election_id=election_id)


def edit_position(request, position_id):
    position = get_object_or_404(Position, pk=position_id)
    if request.method == "POST":
        form = PositionForm(request.POST, instance=position)
        if form.is_valid():
            form.save()
            messages.success(request, f"Position '{position.position_name}' updated successfully!")
            return redirect("manage_election", election_id=position.election.election_id)
    else:
        form = PositionForm(instance=position)
    return render(request, "voting_site/edit_position.html", {"form": form, "position": position})


def delete_position(request, position_id):
    position = get_object_or_404(Position, pk=position_id)
    election_id = position.election.election_id
    position.delete()
    messages.success(request, f"Position '{position.position_name}' deleted successfully!")
    return redirect("manage_election", election_id=election_id)


def approve_voter(request, election_voter_id):
    try:
        ev = ElectionVoter.objects.get(pk=election_voter_id)
        ev.is_approved = True
        ev.save()
        messages.success(request, f"Voter {ev.voter.name} approved for {ev.election.election_name}")
    except ElectionVoter.DoesNotExist:
        messages.error(request, "Approval failed")
    return redirect("admin_dashboard")


def create_election(request):
    if request.method == "POST":
        name = request.POST.get("election_name")
        start_date = request.POST.get("start_date")
        end_date = request.POST.get("end_date")
        description = request.POST.get("description")
        if name and start_date and end_date:
            Election.objects.create(
                election_name=name,
                start_date=start_date,
                end_date=end_date,
                description=description
            )
            messages.success(request, f"Election '{name}' created successfully!")
            return redirect("admin_dashboard")
        else:
            messages.error(request, "Please fill all required fields")
    return render(request, "voting_site/create_election.html")


def create_position(request, election_id):
    election = get_object_or_404(Election, pk=election_id)
    positions = Position.objects.filter(election=election)
    if request.method == "POST":
        form = PositionForm(request.POST)
        if form.is_valid():
            position_name = form.cleaned_data['position_name']
            if Position.objects.filter(election=election, position_name=position_name).exists():
                messages.error(request, "This position already exists in the election.")
            else:
                position = form.save(commit=False)
                position.election = election
                position.save()
                messages.success(request, f"Position '{position.position_name}' created successfully!")
                return redirect("create_position", election_id=election.election_id)
    else:
        form = PositionForm()
    return render(request, "voting_site/create_position.html", {"form": form, "election": election, "positions": positions})


def approve_candidate(request, candidate_id):
    voter_id = request.session.get("voter_id")
    if not voter_id:
        return redirect("login")
    
    voter = get_object_or_404(Voter, voter_id=voter_id)
    if not voter.is_admin:
        return redirect("dashboard")
    
    candidate = get_object_or_404(Candidate, pk=candidate_id)
    candidate.is_approved = True
    candidate.save()
    messages.success(request, f"{candidate.candidate_name} has been approved for '{candidate.position.position_name}'")
    return redirect("admin_dashboard")


def verify_votes_for_election(election_id):
    """
    Verify vote integrity for a specific election.
    Returns a list of tampered vote IDs (empty list if all votes are intact)
    """
    votes = Vote.objects.filter(position__election__election_id=election_id).order_by('vote_id')
    previous_hash = ''
    tampered_votes = []

    for vote in votes:
        vote_data = f"{vote.voter.voter_id}-{vote.position.position_id}-{vote.candidate.candidate_id}-{vote.timestamp.isoformat()}-{previous_hash}"
        expected_hash = hashlib.sha256(vote_data.encode()).hexdigest()

        if vote.vote_hash != expected_hash:
            tampered_votes.append(vote.vote_id)
        
        previous_hash = vote.vote_hash

    return tampered_votes


def admin_verify_votes(request, election_id):
    """
    Admin checks vote integrity for a specific election
    """
    voter_id = request.session.get("voter_id")
    if not voter_id:
        return redirect("login")

    voter = get_object_or_404(Voter, voter_id=voter_id)
    if not voter.is_admin:
        return redirect("dashboard")

    election = get_object_or_404(Election, election_id=election_id)

    tampered_votes = verify_votes_for_election(election_id)

    if tampered_votes:
        verification_status = f"Vote tampering detected! Tampered vote IDs: {tampered_votes}"
        verification_ok = False
    else:
        verification_status = "All votes for this election are intact. ✅"
        verification_ok = True

    # Fetch positions and pending voters to render manage_election template
    positions = Position.objects.filter(election=election)
    for position in positions:
        position.pending_candidates = position.candidates.filter(is_approved=False)
    pending_voters = election.voters.filter(is_approved=False)

    return render(request, "voting_site/manage_election.html", {
        "voter": voter,
        "election": election,
        "positions": positions,
        "pending_voters": pending_voters,
        "verification_status": verification_status,
        "verification_ok": verification_ok,
    })

