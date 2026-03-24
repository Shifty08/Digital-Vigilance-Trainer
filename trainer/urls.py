from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('instructions/<str:category>/', views.instructions, name='instructions'),
    path('modules/', views.module_select, name='module_select'),
    path('play/<str:category>/', views.play_game, name='play_game'),
    path('play/<str:category>/result/', views.round_result, name='result'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    path('signup/', views.signup, name='signup'),
    path('profile/', views.profile, name='profile'),
    path('leaderboard/', views.leaderboard, name='leaderboard'),
    
]