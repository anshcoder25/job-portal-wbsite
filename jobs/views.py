import os
from pathlib import Path
from urllib.parse import urlparse
from django.urls import path
from . import views

import requests
from dotenv import load_dotenv
import re
from collections import Counter

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect

from .models import Job, Profile, Resume

from django.contrib import messages
from django.contrib.auth import (
    authenticate,
    login,
    logout,
)
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Q
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)
from django.views.decorators.http import require_POST

from .models import (
    Application,
    Job,
    JobApplication,
    Profile,
    Resume,
)


# Load environment variables from the project root .env file.
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def get_profile(request):
    """Return the logged-in user's profile, or None."""
    try:
        return request.user.profile
    except Profile.DoesNotExist:
        return None


def home(request):
    jobs = Job.objects.filter(
        is_active=True
    ).order_by("-posted_at")

    query = request.GET.get("q", "").strip()
    location = request.GET.get("location", "").strip()
    job_type = request.GET.get("job_type", "").strip()

    if query:
        jobs = jobs.filter(
            Q(title__icontains=query)
            | Q(company__icontains=query)
            | Q(description__icontains=query)
            | Q(skills__icontains=query)
        )

    if location:
        jobs = jobs.filter(location__icontains=location)

    if job_type:
        jobs = jobs.filter(job_type=job_type)

    return render(request, "home.html", {
        "jobs": jobs.distinct(),
        "query": query,
        "location": location,
        "selected_job_type": job_type,
    })


def register(request):
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")
        confirm_password = request.POST.get("confirm_password", "")
        role = request.POST.get("role", "")

        if not all([
            username, email, password,
            confirm_password, role
        ]):
            messages.error(request, "Please fill in all fields.")

        elif role not in ["candidate", "recruiter"]:
            messages.error(
                request,
                "Please select Candidate or Recruiter."
            )

        elif password != confirm_password:
            messages.error(request, "Passwords do not match.")

        elif len(password) < 8:
            messages.error(
                request,
                "Password must be at least 8 characters."
            )

        elif User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists.")

        elif User.objects.filter(email__iexact=email).exists():
            messages.error(request, "Email already registered.")

        else:
            with transaction.atomic():
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password,
                )
                Profile.objects.create(
                    user=user,
                    role=role,
                )

            login(request, user)

            if role == "recruiter":
                return redirect("recruiter_dashboard")

            return redirect("candidate_dashboard")

    return render(request, "register.html")


def user_login(request):
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")

        user = authenticate(
            request,
            username=username,
            password=password,
        )

        if user is None:
            messages.error(request, "Invalid username or password.")
            return render(request, "login.html")

        if user.is_staff or user.is_superuser:
            login(request, user)
            return redirect("/admin/")

        profile = get_profile(request) if request.user.is_authenticated else None
        # Fetch the profile for the user who is attempting to log in.
        try:
            profile = user.profile
        except Profile.DoesNotExist:
            messages.error(
                request,
                "Profile not found. Please contact the administrator."
            )
            return render(request, "login.html")

        login(request, user)

        if profile.role == "recruiter":
            return redirect("recruiter_dashboard")

        return redirect("candidate_dashboard")

    return render(request, "login.html")


@require_POST
@login_required
def user_logout(request):
    logout(request)
    return redirect("home")


@login_required
def candidate_dashboard(request):
    profile = get_profile(request)

    if profile is None:
        messages.error(request, "Your account profile was not found.")
        return redirect("home")

    if profile.role != "candidate":
        return redirect("recruiter_dashboard")

    jobs = Job.objects.filter(
        is_active=True
    ).order_by("-posted_at")

    return render(request, "candidate_dashboard.html", {
        "jobs": jobs,
    })


@login_required
def recruiter_dashboard(request):
    profile = get_profile(request)

    if profile is None:
        messages.error(request, "Your account profile was not found.")
        return redirect("home")

    if profile.role != "recruiter":
        return redirect("candidate_dashboard")

    jobs_count = Job.objects.filter(
        posted_by=request.user
    ).count()

    applications_count = JobApplication.objects.filter(
        job__posted_by=request.user
    ).count()

    return render(request, "recruiter_dashboard.html", {
        "jobs_count": jobs_count,
        "applications_count": applications_count,
    })


def search_jobs(request):
    query = request.GET.get("q", "").strip()
    location = request.GET.get("location", "").strip()
    job_type = request.GET.get("job_type", "").strip()

    jobs = []
    error_message = ""

    app_id = os.getenv("ADZUNA_APP_ID")
    app_key = os.getenv("ADZUNA_APP_KEY")

    if not app_id or not app_key:
        error_message = (
            "Adzuna API credentials missing. Check your .env file."
        )
    else:
        params = {
            "app_id": app_id,
            "app_key": app_key,
            "results_per_page": 20,
            "content-type": "application/json",
        }

        if query:
            params["what"] = query

        if location:
            params["where"] = location

        if job_type.lower() in ("full-time", "full_time"):
            params["full_time"] = 1
        elif job_type.lower() in ("part-time", "part_time"):
            params["part_time"] = 1

        api_url = (
            "https://api.adzuna.com/v1/api/jobs/in/search/1"
        )

        try:
            response = requests.get(
                api_url,
                params=params,
                timeout=15,
            )
            response.raise_for_status()
            data = response.json()

            for item in data.get("results", []):
                company_data = item.get("company") or {}
                location_data = item.get("location") or {}

                salary_min = item.get("salary_min")
                salary_max = item.get("salary_max")
                salary = "Not specified"

                if salary_min is not None and salary_max is not None:
                    salary = (
                        f"₹{salary_min:,.0f} - ₹{salary_max:,.0f}"
                    )
                elif salary_min is not None:
                    salary = f"From ₹{salary_min:,.0f}"
                elif salary_max is not None:
                    salary = f"Up to ₹{salary_max:,.0f}"

                contract_time = item.get("contract_time") or ""
                contract_type = item.get("contract_type") or ""
                display_type = (
                    contract_time or contract_type or "Not specified"
                ).replace("_", " ").title()

                jobs.append({
                    "title": item.get("title", "Untitled job"),
                    "company": company_data.get(
                        "display_name", "Company not specified"
                    ),
                    "location": location_data.get(
                        "display_name", "Location not specified"
                    ),
                    "description": item.get("description", ""),
                    "job_type": display_type,
                    "salary": salary,
                    "posted_at": item.get("created", ""),
                    "apply_url": item.get("redirect_url", ""),
                })

        except requests.exceptions.Timeout:
            error_message = "Adzuna request timed out. Please try again."

        except requests.exceptions.HTTPError as exc:
            status_code = (
                exc.response.status_code if exc.response else None
            )

            if status_code in (401, 403):
                error_message = (
                    "Adzuna access denied. Check your API credentials."
                )
            elif status_code == 429:
                error_message = (
                    "Adzuna request limit reached. Please try later."
                )
            else:
                error_message = (
                    "Adzuna could not provide jobs right now."
                )

        except requests.exceptions.RequestException:
            error_message = (
                "Could not connect to Adzuna. Check your internet."
            )

        except ValueError:
            error_message = "Adzuna returned an unexpected response."

    return render(request, "search.html", {
        "jobs": jobs,
        "query": query,
        "location": location,
        "selected_job_type": job_type,
        "error_message": error_message,
    })


@login_required
def resume_builder(request):
    profile = get_profile(request)

    if profile is None or profile.role != "candidate":
        messages.error(
            request,
            "Resume Builder candidate accounts ke liye hai."
        )
        return redirect("home")

    resume, created = Resume.objects.get_or_create(
        user=request.user,
        defaults={
            "full_name": (
                request.user.get_full_name()
                or request.user.username
            ),
            "email": request.user.email,
            "education": "",
            "skills": "",
        },
    )

    if request.method == "POST":
        resume.full_name = request.POST.get("full_name", "").strip()
        resume.email = request.POST.get("email", "").strip()
        resume.phone = request.POST.get("phone", "").strip()
        resume.address = request.POST.get("address", "").strip()
        resume.career_objective = request.POST.get(
            "career_objective", ""
        ).strip()
        resume.education = request.POST.get("education", "").strip()
        resume.skills = request.POST.get("skills", "").strip()
        resume.experience = request.POST.get("experience", "").strip()
        resume.projects = request.POST.get("projects", "").strip()
        resume.certifications = request.POST.get(
            "certifications", ""
        ).strip()

        if not all([
            resume.full_name,
            resume.email,
            resume.education,
            resume.skills,
        ]):
            messages.error(
                request,
                "Name, email, education aur skills bharna zaroori hai."
            )
        else:
            resume.save()
            messages.success(request, "Resume successfully save ho gaya!")
            return redirect("resume_builder")

    return render(request, "resume_builder.html", {
        "resume": resume,
    })


@login_required
@require_POST
def apply_external_job(request):
    profile = get_profile(request)

    if profile is None or profile.role != "candidate":
        messages.error(request, "Sirf candidates jobs save kar sakte hain.")
        return redirect("home")

    job_title = request.POST.get("job_title", "").strip()
    company = request.POST.get("company", "").strip()
    location = request.POST.get("location", "").strip()
    job_url = request.POST.get("job_url", "").strip()

    parsed_url = urlparse(job_url)
    hostname = (parsed_url.hostname or "").lower()

    valid_host = (
        hostname == "adzuna.com"
        or hostname.endswith(".adzuna.com")
        or hostname == "adzuna.in"
        or hostname.endswith(".adzuna.in")
    )

    if (
        not job_title
        or not company
        or parsed_url.scheme != "https"
        or not valid_host
    ):
        messages.error(request, "Job details ya Adzuna URL invalid hai.")
        return redirect("search_jobs")

    application, created = Application.objects.get_or_create(
        user=request.user,
        job_url=job_url,
        defaults={
            "job_title": job_title,
            "company": company,
            "location": location,
            "status": "saved",
        },
    )

    if created:
        messages.success(request, "Job successfully save ho gayi!")
    else:
        messages.info(request, "Ye job aap pehle hi save kar chuke hain.")

    return redirect("my_applications")


@login_required
def my_applications(request):
    profile = get_profile(request)

    if profile is None or profile.role != "candidate":
        messages.error(request, "Ye page candidate accounts ke liye hai.")
        return redirect("home")

    applications = Application.objects.filter(
        user=request.user
    ).order_by("-created_at")

    return render(request, "my_applications.html", {
        "applications": applications,
    })


@login_required
def post_job(request):
    profile = get_profile(request)

    if profile is None or profile.role != "recruiter":
        messages.error(request, "Sirf recruiters job post kar sakte hain.")
        return redirect("home")

    if request.method == "POST":
        title = request.POST.get("title", "").strip()
        company = request.POST.get("company", "").strip()
        location = request.POST.get("location", "").strip()
        salary = request.POST.get("salary", "").strip()
        job_type = request.POST.get("job_type", "Full Time").strip()
        description = request.POST.get("description", "").strip()
        skills = request.POST.get("skills", "").strip()

        if not all([title, company, location, description]):
            messages.error(
                request,
                "Title, company, location aur description zaroor bharein."
            )
        else:
            Job.objects.create(
                title=title,
                company=company,
                location=location,
                salary=salary,
                job_type=job_type,
                description=description,
                skills=skills,
                posted_by=request.user,
                is_active=True,
            )
            messages.success(request, "Job successfully post ho gayi!")
            return redirect("manage_jobs")

    return render(request, "post_job.html")


@login_required
def manage_jobs(request):
    profile = get_profile(request)

    if profile is None or profile.role != "recruiter":
        messages.error(request, "Ye page sirf recruiters ke liye hai.")
        return redirect("home")

    jobs = Job.objects.filter(
        posted_by=request.user
    ).order_by("-posted_at")

    return render(request, "manage_jobs.html", {
        "jobs": jobs,
    })


@login_required
@require_POST
def delete_job(request, job_id):
    profile = get_profile(request)

    if profile is None or profile.role != "recruiter":
        messages.error(request, "Sirf recruiters jobs delete kar sakte hain.")
        return redirect("home")

    job = get_object_or_404(
        Job,
        id=job_id,
        posted_by=request.user,
    )
    job.delete()

    messages.success(request, "Job delete ho gayi.")
    return redirect("manage_jobs")


@login_required
def recruiter_applications(request):
    profile = get_profile(request)

    if profile is None or profile.role != "recruiter":
        messages.error(
            request,
            "Ye page sirf recruiters ke liye hai."
        )
        return redirect("home")

    applications = JobApplication.objects.filter(
        job__posted_by=request.user
    ).select_related("job", "candidate").order_by("-id")

    return render(request, "recruiter_applications.html", {
        "applications": applications,
        "status_choices": JobApplication.STATUS_CHOICES,
    })


@login_required
@require_POST
def update_application_status(request, application_id):
    profile = get_profile(request)

    if profile is None or profile.role != "recruiter":
        messages.error(
            request,
            "Sirf recruiters application status update kar sakte hain."
        )
        return redirect("home")

    application = get_object_or_404(
        JobApplication,
        id=application_id,
        job__posted_by=request.user,
    )

    new_status = request.POST.get("status", "")
    valid_statuses = dict(JobApplication.STATUS_CHOICES)

    if new_status not in valid_statuses:
        messages.error(request, "Invalid application status.")
    else:
        application.status = new_status
        application.save(update_fields=["status", "updated_at"])
        messages.success(
            request,
            "Application status successfully update ho gaya."
        )

    return redirect("recruiter_applications")
# ==========================================
# AI RESUME ANALYZER
# ==========================================

@login_required
def ai_resume_analyzer(request):
    profile = get_profile(request)

    if profile is None:
        messages.error(request, "Your profile was not found.")
        return redirect("home")

    if profile.role != "candidate":
        messages.error(
            request,
            "Resume Analyzer is available for candidates only."
        )
        return redirect("recruiter_dashboard")

    resume = Resume.objects.filter(user=request.user).first()

    if resume is None:
        messages.info(
            request,
            "Please create your resume first."
        )
        return redirect("resume_builder")

    sections = {
        "Full Name": resume.full_name,
        "Email": resume.email,
        "Career Objective": resume.career_objective,
        "Education": resume.education,
        "Skills": resume.skills,
        "Experience": resume.experience,
        "Projects": resume.projects,
        "Certifications": resume.certifications,
    }

    completed_sections = []
    missing_sections = []
    suggestions = []

    for section, value in sections.items():
        if value and value.strip():
            completed_sections.append(section)
        else:
            missing_sections.append(section)

    total_sections = len(sections)

    score = round(
        len(completed_sections) / total_sections * 100
    ) if total_sections else 0

    if not resume.career_objective.strip():
        suggestions.append(
            "Add a clear career objective related to your target role."
        )

    if not resume.education.strip():
        suggestions.append(
            "Add your educational qualifications."
        )

    if not resume.skills.strip():
        suggestions.append(
            "Add relevant technical and professional skills."
        )

    if not resume.experience.strip():
        suggestions.append(
            "Add relevant experience, internships, or practical training if applicable."
        )

    if not resume.projects.strip():
        suggestions.append(
            "Add projects and mention the technologies you used."
        )

    if not resume.certifications.strip():
        suggestions.append(
            "Add relevant certifications if you have any."
        )

    if not suggestions:
        suggestions.append(
            "Your resume sections are filled. Review spelling, formatting, and relevance to your target job."
        )

    context = {
        "resume": resume,
        "score": score,
        "total_sections": total_sections,
        "completed_sections": completed_sections,
        "missing_sections": missing_sections,
        "suggestions": suggestions,
    }

    return render(
        request,
        "ai_resume_analyzer.html",
        context
    )


# ==========================================
# RESUME-JOB MATCH SCORE
# ==========================================

@login_required
def resume_job_match(request):
    profile = get_profile(request)

    if profile is None or profile.role != "candidate":
        messages.error(
            request,
            "Resume Job Match sirf candidate accounts ke liye hai."
        )
        return redirect("home")

    resume = Resume.objects.filter(user=request.user).first()

    if resume is None:
        messages.info(
            request,
            "Pehle Resume Builder mein apna resume save karein."
        )
        return redirect("resume_builder")

    # Resume mein maujood skills
    resume_skills = [
        skill.strip().lower()
        for skill in re.split(r"[,;\n]+", resume.skills or "")
        if skill.strip()
    ]

    # Duplicate skills remove karein
    resume_skills = list(dict.fromkeys(resume_skills))

    matched_jobs = []
    error_message = ""

    # 1. Local portal jobs
    local_jobs = Job.objects.filter(is_active=True).order_by("-posted_at")

    for job in local_jobs:
        job_text = " ".join([
            job.title or "",
            job.description or "",
            job.skills or "",
        ]).lower()

        matched = [
            skill for skill in resume_skills
            if re.search(
                r"(?<!\w)" + re.escape(skill) + r"(?!\w)",
                job_text
            )
        ]

        missing = [
            skill for skill in resume_skills
            if skill not in matched
        ]

        score = round(
            len(matched) / len(resume_skills) * 100
        ) if resume_skills else 0

        matched_jobs.append({
            "source": "Portal",
            "title": job.title,
            "company": job.company,
            "location": job.location,
            "description": job.description,
            "skills": job.skills,
            "match_score": score,
            "matched_skills": matched,
            "missing_skills": missing,
            "apply_url": job.apply_url,
        })

    # 2. Adzuna jobs
    app_id = os.getenv("ADZUNA_APP_ID")
    app_key = os.getenv("ADZUNA_APP_KEY")

    if not app_id or not app_key:
        error_message = (
            "Adzuna API credentials nahi mile. "
            "Apni .env file mein ADZUNA_APP_ID aur "
            "ADZUNA_APP_KEY check karein."
        )
    else:
        # Skills ko search query banayein; resume skills na hon
        # to career objective se query banane ki koshish karein.
        search_query = " ".join(resume_skills[:5])

        if not search_query:
            search_query = (resume.career_objective or "").strip()[:100]

        if search_query:
            api_url = (
                "https://api.adzuna.com/v1/api/jobs/in/search/1"
            )

            params = {
                "app_id": app_id,
                "app_key": app_key,
                "results_per_page": 20,
                "what": search_query,
                "content-type": "application/json",
            }

            try:
                response = requests.get(
                    api_url,
                    params=params,
                    timeout=15,
                )
                response.raise_for_status()
                data = response.json()

                for item in data.get("results", []):
                    company_data = item.get("company") or {}
                    location_data = item.get("location") or {}

                    title = item.get("title", "Untitled job")
                    description = item.get("description", "")
                    job_text = f"{title} {description}".lower()

                    matched = [
                        skill for skill in resume_skills
                        if re.search(
                            r"(?<!\w)" + re.escape(skill) + r"(?!\w)",
                            job_text
                        )
                    ]

                    missing = [
                        skill for skill in resume_skills
                        if skill not in matched
                    ]

                    score = round(
                        len(matched) / len(resume_skills) * 100
                    ) if resume_skills else 0

                    matched_jobs.append({
                        "source": "Adzuna",
                        "title": title,
                        "company": company_data.get(
                            "display_name",
                            "Company not specified"
                        ),
                        "location": location_data.get(
                            "display_name",
                            "Location not specified"
                        ),
                        "description": description,
                        "skills": "",
                        "match_score": score,
                        "matched_skills": matched,
                        "missing_skills": missing,
                        "apply_url": item.get("redirect_url", ""),
                    })

            except requests.exceptions.Timeout:
                error_message = (
                    "Adzuna request timeout ho gaya. Dobara try karein."
                )
            except requests.exceptions.HTTPError as exc:
                status = exc.response.status_code if exc.response else None
                if status in (401, 403):
                    error_message = (
                        "Adzuna access denied. API credentials check karein."
                    )
                elif status == 429:
                    error_message = (
                        "Adzuna request limit reach ho gayi. Baad mein try karein."
                    )
                else:
                    error_message = (
                        "Adzuna se jobs abhi fetch nahi ho paayi."
                    )
            except (requests.exceptions.RequestException, ValueError):
                error_message = (
                    "Adzuna se connect nahi ho paaya. Internet aur API settings check karein."
                )
        else:
            error_message = (
                "Resume Builder mein skills ya career objective add karein "
                "taaki Adzuna jobs search ki ja sakein."
            )

    # Highest match score pehle dikhayein
    matched_jobs.sort(
        key=lambda job: job["match_score"],
        reverse=True
    )

    return render(request, "resume_job_match.html", {
        "resume": resume,
        "matched_jobs": matched_jobs,
        "error_message": error_message,
    })