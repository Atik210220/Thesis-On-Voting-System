import hashlib
from django.db import models
from django.utils import timezone


class Voter(models.Model):
    voter_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255)   # single name field
    email = models.EmailField(unique=True)
    password_hash = models.CharField(max_length=255)
    voter_image = models.ImageField(upload_to='voter_images/', blank=True, null=True)
    is_admin = models.BooleanField(default=False)
    registration_date = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "voters"

    def __str__(self):
        return f"{self.name} ({'Admin' if self.is_admin else 'Voter'})"


class Election(models.Model):
    election_id = models.AutoField(primary_key=True)
    election_name = models.CharField(max_length=255)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    candidate_deadline = models.DateTimeField()  # Deadline for candidate applications

    STATUS_CHOICES = [
        ('upcoming', 'Upcoming'),
        ('running', 'Running'),
        ('closed', 'Closed'),
    ]
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="upcoming")
    is_paused = models.BooleanField(default=False)  # Admin can pause/resume election
    description = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "elections"
        ordering = ["-start_date"]

    def __str__(self):
        return f"{self.election_name} ({self.current_status()})"

    def is_candidate_application_open(self):
        """Check if candidate applications are still open"""
        return timezone.now() <= self.candidate_deadline and not self.is_paused

    def current_status(self):
        """
        Return the current website-visible status:
        - 'paused' if admin paused
        - 'upcoming', 'running', 'closed' based on start/end date
        """
        if self.is_paused:
            return 'paused'

        now = timezone.now()
        if now < self.start_date:
            return 'upcoming'
        elif self.start_date <= now <= self.end_date:
            return 'running'
        else:
            return 'closed'

    def can_vote(self):
        """Check if voting is currently allowed"""
        now = timezone.now()
        return self.start_date <= now <= self.end_date and not self.is_paused


class Position(models.Model):
    position_id = models.AutoField(primary_key=True)
    election = models.ForeignKey(
        Election, on_delete=models.CASCADE, db_column="election_id", related_name="positions"
    )
    position_name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "positions"
        unique_together = ("election", "position_name")  # no duplicate positions in same election

    def __str__(self):
        return f"{self.position_name} ({self.election.election_name})"


class Candidate(models.Model):
    candidate_id = models.AutoField(primary_key=True)
    position = models.ForeignKey(
        Position, on_delete=models.CASCADE, db_column="position_id", related_name="candidates"
    )
    candidate_name = models.CharField(max_length=255)
    party = models.CharField(max_length=255, blank=True, null=True)
    candidate_image = models.ImageField(upload_to='candidate_images/', blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    is_approved = models.BooleanField(default=False)  # <--- add this field

    class Meta:
        db_table = "candidates"
        ordering = ["candidate_name"]

    def __str__(self):
        return f"{self.candidate_name} ({self.party if self.party else 'Independent'})"




class ElectionVoter(models.Model):
    election_voter_id = models.AutoField(primary_key=True)
    voter = models.ForeignKey(Voter, on_delete=models.CASCADE, db_column="voter_id", related_name="election_participations")
    election = models.ForeignKey(Election, on_delete=models.CASCADE, db_column="election_id", related_name="voters")
    has_voted = models.BooleanField(default=False)
    is_approved = models.BooleanField(default=False)

    class Meta:
        db_table = "election_voters"
        unique_together = ("voter", "election")

    def __str__(self):
        return f"{self.voter.name} → {self.election.election_name}"


class Vote(models.Model):
    vote_id = models.AutoField(primary_key=True)
    voter = models.ForeignKey(Voter, on_delete=models.CASCADE, db_column="voter_id", related_name="votes")
    position = models.ForeignKey(Position, on_delete=models.CASCADE, db_column="position_id", related_name="votes")
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, db_column="candidate_id", related_name="votes")
    timestamp = models.DateTimeField(default=timezone.now)

    # New fields for hash-based tamper-proofing
    vote_hash = models.CharField(max_length=64, editable=False, blank=True, null=True)
    previous_vote_hash = models.CharField(max_length=64, blank=True, null=True)

    class Meta:
        db_table = "votes"
        unique_together = ("voter", "position")  # voter can only vote once per position

    def __str__(self):
        return f"{self.voter.name} voted {self.candidate.candidate_name} for {self.position.position_name}"

    def save(self, *args, **kwargs):
        # Compute previous hash from the latest vote
        if not self.vote_hash:
            last_vote = Vote.objects.order_by('-vote_id').first()
            prev_hash = last_vote.vote_hash if last_vote else ''
            self.previous_vote_hash = prev_hash

            # Create hash for this vote
            vote_data = f"{self.voter_id}-{self.position_id}-{self.candidate_id}-{self.timestamp.isoformat()}-{prev_hash}"
            self.vote_hash = hashlib.sha256(vote_data.encode()).hexdigest()

        super().save(*args, **kwargs)
