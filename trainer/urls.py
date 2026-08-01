from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('instructions/<str:category>/', views.instructions, name='instructions'),
    path('instructions/<str:category>/<str:difficulty>/', views.instructions, name='instructions_diff'),
    path('modules/', views.module_select, name='module_select'),
    path('play/<str:category>/', views.play_game, name='play_game'),
    path('play/<str:category>/<str:difficulty>/', views.play_game, name='play_game_diff'),
    path('play/<str:category>/result/', views.round_result, name='result'),
    path('play/<str:category>/<str:difficulty>/result/', views.round_result, name='result_diff'),
    path('login/', views.user_login, name='login'),
    path('verify-otp/', views.verify_otp, name='verify_otp'),
    path('logout/', views.user_logout, name='logout'),
    path('signup/', views.signup, name='signup'),
    path('profile/', views.profile, name='profile'),
    path('leaderboard/', views.leaderboard, name='leaderboard'),
    
]