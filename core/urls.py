from django.contrib.auth import views as auth_views
from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('quote/', views.random_quote, name='random_quote'),
    path('account/signup/', views.signup, name='signup'),
    path('account/login/', auth_views.LoginView.as_view(template_name='core/login.html'), name='login'),
    path('account/logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('race/create/', views.create_race, name='create_race'),
    path('race/<str:code>/join/', views.join_race, name='join_race'),
    path('race/<str:code>/state/', views.race_state, name='race_state'),
    path('race/<str:code>/start/', views.start_race, name='start_race'),
    path('race/<str:code>/quote/', views.change_race_quote, name='change_race_quote'),
    path('race/<str:code>/progress/', views.update_progress, name='update_progress'),
]
