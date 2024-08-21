from django.urls import path
from .views import (
    register_view,
    login_view,
    change_password_view,
    create_quiz_view,
    edit_quiz_view,
    delete_quiz_view,
    quiz_access_and_submit_view,
    quiz_taker_analytics_view,
    quiz_master_analytics_view,
    quiz_performance_analytics_view,
    quiz_taker_dashboard_view,
    quiz_management_view,
    quiz_master_dashboard,
    profile_view,
    update_profile_view,
    available_quizzes_view,
    quizzes_taken_view, quiz_confirmation_view, logout_view, quiz_result_view, quiz_results_view,
    quiz_performance_chart_view
)
from django.contrib.auth import views as auth_views


urlpatterns = [
    path('register/', register_view, name='register'),
    path('accounts/login/', login_view, name='login'),
    path('login/', login_view, name='login'),
    path('change-password/', change_password_view, name='change_password'),
    path('profile/', profile_view, name='profile'),
    path('update-profile/', update_profile_view, name='update_profile'),

    path('create-quiz/', create_quiz_view, name='create_quiz'),
    path('edit-quiz/<uuid:quiz_uuid>/', edit_quiz_view, name='edit_quiz'),
    path('delete-quiz/<uuid:quiz_uuid>/', delete_quiz_view, name='delete_quiz'),
    path('access-quiz/<uuid:quiz_uuid>/', quiz_access_and_submit_view, name='access_quiz'),

    path('quiz-taker-analytics/', quiz_taker_analytics_view, name='quiz_taker_analytics'),
    path('quiz-master-analytics/', quiz_master_analytics_view, name='quiz_master_analytics'),
    path('quiz-performance-analytics/<uuid:quiz_uuid>/', quiz_performance_analytics_view, name='quiz_performance_analytics'),

    path('quiz-taker-dashboard/', quiz_taker_dashboard_view, name='quiz_taker_dashboard'),
    path('quiz-master-dashboard/', quiz_master_dashboard, name='quiz_master_dashboard'),
    path('quiz-management/', quiz_management_view, name='quiz_management'),

    path('password_reset/', auth_views.PasswordResetView.as_view(template_name='password_reset.html'), name='password_reset'),
    path('password_reset_done/', auth_views.PasswordResetDoneView.as_view(template_name='password_reset_done.html'), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name='password_reset_confirm.html'), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(template_name='password_reset_complete.html'), name='password_reset_complete'),



    path('available-quizzes/', available_quizzes_view, name='available_quizzes'),
    path('quizzes-taken/', quizzes_taken_view, name='quizzes_taken'),
    path('quiz-confirmation/<uuid:quiz_uuid>/', quiz_confirmation_view, name='quiz_confirmation'),
    path('quiz/<uuid:quiz_uuid>/result/', quiz_result_view, name='quiz_result'),
    path('quiz-results/<uuid:quiz_uuid>/', quiz_results_view, name='quiz_results'),
    path('quiz-performance-chart/<uuid:quiz_uuid>/', quiz_performance_chart_view, name='quiz_performance_chart'),
    path('quiz-performance-chart-data/<uuid:quiz_uuid>/', quiz_performance_chart_view,name='quiz_performance_chart_data'),
    path('logout/', logout_view, name='logout'),
]
