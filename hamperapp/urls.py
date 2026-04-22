from django.urls import path
from . import views
from django.contrib.auth import views as auth_views
from django.views.decorators.cache import cache_control

# Wrap auth views with cache control
login_view = cache_control(no_cache=True, no_store=True, must_revalidate=True)(
    views.custom_login
)
logout_view = cache_control(no_cache=True, no_store=True, must_revalidate=True)(
    auth_views.LogoutView.as_view(next_page='hamper_list')
)

urlpatterns = [
    path('', views.hamper_list, name='hamper_list'),
    path('hamper/<int:pk>/', views.hamper_detail, name='hamper_detail'),
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('register/', views.register, name='register'),
    path('verify-otp/', views.verify_otp, name='verify_otp'),
    path('verify-otp-resend/', views.verify_otp_resend, name='verify_otp_resend'),
    path('checkout/<int:pk>/', views.checkout, name='checkout'),
    path('checkout-cart/', views.checkout_cart, name='checkout_cart'),
    path('checkout-success/<int:pk>/', views.checkout_success, name='checkout_success'),
    path('cart/add/<int:pk>/', views.cart_add, name='cart_add'),
    path('cart/', views.cart_summary, name='cart_summary'),
    path('orders/', views.order_history, name='order_history'),
]