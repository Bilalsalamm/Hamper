from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('', views.hamper_list, name='hamper_list'),
    path('hamper/<int:pk>/', views.hamper_detail, name='hamper_detail'),
    path('login/',auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    path('logout/',auth_views.LogoutView.as_view(), name='logout'),
    path('checkout/<int:pk>/', views.checkout, name='checkout'),
    path('register/', views.register, name='register'),
]