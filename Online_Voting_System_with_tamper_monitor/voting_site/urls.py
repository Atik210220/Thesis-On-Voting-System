from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name="home"),
    path('register/', views.register, name="register"),
    path('login/', views.login_view, name="login"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path('dashboard/request-registration/<int:election_id>/', views.request_registration, name='request_registration'),
    path('dashboard/election/<int:election_id>/', views.registered_election_detail, name='registered_election_detail'),
    path("dashboard/election/<int:election_id>/apply/<int:position_id>/", views.apply_for_position, name="apply_for_position"),
    path("election/<int:election_id>/vote/", views.vote_page, name="vote_page"),
    path("election/<int:election_id>/position/<int:position_id>/candidate/<int:candidate_id>/vote/", views.vote_candidate, name="vote_candidate"),
    path("logout/", views.logout_view, name="logout"),

    # Admin URLs
    path("election_admin/dashboard/", views.admin_dashboard, name="admin_dashboard"),
    path("election_admin/approve_voter/<int:election_voter_id>/", views.approve_voter, name="approve_voter"),
    path("election_admin/dashboard/create_election/", views.create_election, name="create_election"),
    path("election_admin/dashboard/manage/create-position/<int:election_id>/", views.create_position, name="create_position"),
    path('election_admin/dashboard/manage/<int:election_id>/', views.manage_election, name='manage_election'),
    path('election_admin/dashboard/manage/<int:election_id>/toggle_status/', views.toggle_election_status, name='toggle_election_status'),
    path('election_admin/dashboard/position/edit/<int:position_id>/', views.edit_position, name='edit_position'),
    path('election_admin/dashboard/delete/<int:position_id>/', views.delete_position, name='delete_position'),
    path('election_admin/dashboard/approve_candidate/<int:candidate_id>/', views.approve_candidate, name='approve_candidate'),
    path('election_admin/dashboard/manage/<int:election_id>/verify_votes/', views.admin_verify_votes, name='admin_verify_votes'),
]

