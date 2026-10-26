from django.urls import path
from . import views

urlpatterns = [
    # Home
    path('', views.home, name='home'),

    # Registration and Login
    path('register/', views.register, name='register'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),

    # Dashboards
    path(
        'candidate/dashboard/',
        views.candidate_dashboard,
        name='candidate_dashboard',
    ),
    path(
        'recruiter/dashboard/',
        views.recruiter_dashboard,
        name='recruiter_dashboard',
    ),

    # Job Search
    path('search/', views.search_jobs, name='search_jobs'),

    # Resume Builder
    path('resume-builder/', views.resume_builder, name='resume_builder'),

    # AI Resume Analyzer
    path(
        'ai/resume-analyzer/',
        views.ai_resume_analyzer,
        name='ai_resume_analyzer',
    ),

    # Resume Job Match
    path(
        'ai/job-match/',
        views.resume_job_match,
        name='resume_job_match',
    ),

    # Candidate Applications
    path(
        'apply-external/',
        views.apply_external_job,
        name='apply_external_job',
    ),
    path(
        'my-applications/',
        views.my_applications,
        name='my_applications',
    ),

    # Recruiter Job Management
    path(
        'recruiter/post-job/',
        views.post_job,
        name='post_job',
    ),
    path(
        'recruiter/manage-jobs/',
        views.manage_jobs,
        name='manage_jobs',
    ),
    path(
        'recruiter/delete-job/<int:job_id>/',
        views.delete_job,
        name='delete_job',
    ),

    # Recruiter Applications
    path(
        'recruiter/applications/',
        views.recruiter_applications,
        name='view_applications',
    ),
    path(
        'recruiter/applications/<int:application_id>/update/',
        views.update_application_status,
        name='update_application_status',
    ),
]