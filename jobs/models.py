from django.db import models
from django.contrib.auth.models import User


# =========================
# JOB MODEL
# =========================

class Job(models.Model):

    title = models.CharField(max_length=200)
    company = models.CharField(max_length=200)
    location = models.CharField(max_length=150)
    salary = models.CharField(max_length=100, blank=True)

    job_type = models.CharField(
        max_length=100,
        default="Full Time"
    )
    apply_url = models.URLField(
        max_length=1000,
        blank=True,
        null=True,
        help_text="External job application URL. Leave blank if applying through the portal."
    )

    description = models.TextField()
    skills = models.CharField(max_length=300, blank=True)

    posted_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    posted_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="posted_jobs",
        null=True,
        blank=True
    )

    def _str_(self):
        return f"{self.title} - {self.company}"


# =========================
# PROFILE MODEL
# =========================

class Profile(models.Model):

    ROLE_CHOICES = [
        ('candidate', 'Candidate'),
        ('recruiter', 'Recruiter'),
    ]

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='profile'
    )

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES
    )

    def _str_(self):
        return f"{self.user.username} - {self.role}"


# =========================
# RESUME MODEL
# =========================

class Resume(models.Model):

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="resume"
    )

    full_name = models.CharField(max_length=150)
    email = models.EmailField()

    phone = models.CharField(max_length=20, blank=True)
    address = models.CharField(max_length=255, blank=True)

    career_objective = models.TextField(blank=True)

    education = models.TextField()
    skills = models.TextField()

    experience = models.TextField(blank=True)
    projects = models.TextField(blank=True)
    certifications = models.TextField(blank=True)

    updated_at = models.DateTimeField(auto_now=True)

    def _str_(self):
        return f"{self.full_name} - Resume"


# =========================
# APPLICATION MODEL
# =========================

class Application(models.Model):

    STATUS_CHOICES = [
        ('saved', 'Saved'),
        ('applied', 'Applied'),
        ('in_progress', 'In Progress'),
        ('shortlisted', 'Shortlisted'),
        ('rejected', 'Rejected'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='applications'
    )

    job_title = models.CharField(max_length=255)

    company = models.CharField(max_length=255)

    location = models.CharField(
        max_length=255,
        blank=True
    )

    job_url = models.URLField(max_length=1000)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='saved'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:

        ordering = ['-created_at']

        constraints = [
            models.UniqueConstraint(
                fields=['user', 'job_url'],
                name='unique_user_saved_job'
            )
        ]

    def _str_(self):
        return f"{self.user.username} - {self.job_title}"
class JobApplication(models.Model):
    STATUS_CHOICES = [
        ("applied", "Applied"),
        ("in_progress", "In Progress"),
        ("shortlisted", "Shortlisted"),
        ("rejected", "Rejected"),
    ]

    job = models.ForeignKey(
        Job,
        on_delete=models.CASCADE,
        related_name="applications",
    )
    candidate = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="job_applications",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="applied",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["job", "candidate"],
                name="unique_candidate_job_application",
            )
        ]
        ordering = ["-created_at"]

    def _str_(self):
        return f"{self.candidate.username} - {self.job.title}"