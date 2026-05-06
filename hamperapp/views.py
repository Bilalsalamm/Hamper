from pyexpat.errors import messages

from django.shortcuts import get_object_or_404, redirect, render
from .models import Hamper, Order, EmailVerification
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import authenticate, login
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
from django.views.decorators.cache import cache_control
from django.core.paginator import Paginator
from .cart import Cart
from django import forms
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth.backends import ModelBackend
from django_countries import countries as dj_countries
import json
import secrets
import re
import random

# Create your views here.

@cache_control(no_cache=True, no_store=True, must_revalidate=True)
def hamper_list(request):
    all_hampers = Hamper.objects.all()
    
    # Pagination: 10 items per page
    paginator = Paginator(all_hampers, 10)
    page_number = request.GET.get('page')
    hampers = paginator.get_page(page_number)
    
    cart = Cart(request)
    cart_items_count = cart.get_total_items()
    return render(request, 'list.html', {
        'hampers': hampers, 
        'cart_items_count': cart_items_count,
        'paginator': paginator
    })

@cache_control(no_cache=True, no_store=True, must_revalidate=True)
def hamper_detail(request, pk):
    hamper = Hamper.objects.get(pk=pk)
    cart = Cart(request)
    cart_items_count = cart.get_total_items()
    return render(request, 'details.html', {'hamper': hamper, 'cart_items_count': cart_items_count})


# Custom Authentication Backend - Login with Email or Username
class EmailBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        try:
            # Try to find user by email first
            user = User.objects.get(email=username)
            # Verify password
            if user.check_password(password) and self.user_can_authenticate(user):
                return user
        except User.DoesNotExist:
            pass
        
        # Fallback: Try to find user by username (for admin and backward compatibility)
        try:
            user = User.objects.get(username=username)
            # Verify password
            if user.check_password(password) and self.user_can_authenticate(user):
                return user
        except User.DoesNotExist:
            pass
        
        return None


# Custom Login Form using Email
class EmailAuthenticationForm(AuthenticationForm):
    username = forms.EmailField(
        label='Email Address',
        widget=forms.EmailInput(attrs={
            'autofocus': True,
            'class': 'form-control',
            'placeholder': 'your@email.com'
        })
    )
    password = forms.CharField(
        label='Password',
        strip=False,
        widget=forms.PasswordInput(attrs={
            'autocomplete': 'current-password',
            'class': 'form-control',
            'placeholder': 'Enter your password'
        })
    )
    
    def clean_username(self):
        """Validate email exists in system"""
        email = self.cleaned_data.get('username')
        if email and not User.objects.filter(email=email).exists():
            raise forms.ValidationError('No account found with this email address.')
        return email


# Custom Registration Form with Email Only
class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True, help_text='Verify your email to activate account')
    
    class Meta:
        model = User
        fields = ('email', 'password1', 'password2')
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Remove username field if it exists
        if 'username' in self.fields:
            del self.fields['username']
        # Customize password help text
        if 'password1' in self.fields:
            self.fields['password1'].help_text = 'At least 8 characters with letters and numbers'
    
    def clean_email(self):
        """Validate email format and check if already registered"""
        email = self.cleaned_data.get('email')
        # Basic email validation
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            raise forms.ValidationError('Enter a valid email address')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('This email is already registered')
        return email
    
    def save(self, commit=True):
        user = super().save(commit=False)
        email = self.cleaned_data['email']
        # Auto-generate username from email prefix
        username = email.split('@')[0]
        # If username exists, append number to make it unique
        counter = 1
        original_username = username
        while User.objects.filter(username=username).exists():
            username = f"{original_username}{counter}"
            counter += 1
        user.username = username
        user.email = email
        if commit:
            user.save()
        return user


@cache_control(no_cache=True, no_store=True, must_revalidate=True)
def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            # Create user but don't activate yet
            user = form.save(commit=False)
            user.is_active = False  # Disable until email verified
            user.save()
            
            # Generate 6-digit OTP
            otp = str(random.randint(100000, 999999))
            otp_expires_at = timezone.now() + timedelta(minutes=10)
            
            # Create or update EmailVerification
            EmailVerification.objects.filter(user=user).delete()
            EmailVerification.objects.create(user=user, otp=otp, otp_expires_at=otp_expires_at)
            
            # Send OTP email
            email_subject = "🎁 Your Verification OTP - HamperWorld"
            email_body = f"""
Hello {user.username},

Welcome to HamperWorld! Your account verification code is:

🔐 {otp}

This code will expire in 10 minutes.

If you didn't create this account, please ignore this email.

Best regards,
HamperWorld Team
"""
            try:
                send_mail(
                    email_subject,
                    email_body,
                    settings.DEFAULT_FROM_EMAIL,
                    [user.email],
                    fail_silently=False,
                )
                request.session['pending_user_id'] = user.id
                messages.success(request, f'OTP sent to {user.email}. Please enter it to verify your account.')
                return redirect('verify_otp')
            except Exception as e:
                user.delete()
                EmailVerification.objects.filter(user=user).delete()
                messages.error(request, 'Failed to send OTP. Please try again.')
                return redirect('register')
    else:
        form = CustomUserCreationForm()
    return render(request, 'register.html', {'form': form})


@cache_control(no_cache=True, no_store=True, must_revalidate=True)
def custom_login(request):
    """Custom login view using email instead of username"""
    if request.method == 'POST':
        form = EmailAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            email = form.cleaned_data.get('username')  # username field has email
            password = form.cleaned_data.get('password')
            
            # Authenticate with custom backend
            user = authenticate(request, username=email, password=password)
            
            if user is not None:
                # Check if user is active (email verified)
                if not user.is_active:
                    messages.error(request, '❌ Your account is not active. Please verify your email first.')
                    return redirect('verify_otp')
                
                # Login successful
                login(request, user)
                messages.success(request, f'✅ Welcome back, {user.username}!')
                
                # Redirect to next page or home
                next_page = request.GET.get('next', 'hamper_list')
                return redirect(next_page)
            else:
                form.add_error(None, '❌ Invalid email or password.')
        # Form has errors, will be displayed in template
    else:
        form = EmailAuthenticationForm()
    
    return render(request, 'login.html', {'form': form})


@cache_control(no_cache=True, no_store=True, must_revalidate=True)
def verify_otp(request):
    """Verify OTP and activate user account"""
    user_id = request.session.get('pending_user_id')
    
    if not user_id:
        messages.error(request, 'Session expired. Please register again.')
        return redirect('register')
    
    try:
        user = User.objects.get(id=user_id)
        verification = EmailVerification.objects.get(user=user)
    except (User.DoesNotExist, EmailVerification.DoesNotExist):
        messages.error(request, 'Invalid session. Please register again.')
        return redirect('register')
    
    # Check if OTP already verified
    if verification.is_verified:
        messages.info(request, 'Account already verified. Please login.')
        return redirect('login')
    
    if request.method == 'POST':
        otp_entered = request.POST.get('otp', '').strip()
        
        # Check if OTP is valid
        if not verification.is_otp_valid():
            messages.error(request, 'OTP has expired. Request a new one.')
            return redirect('verify_otp_resend')
        
        # Verify OTP
        if otp_entered == verification.otp:
            # Activate user
            user.is_active = True
            user.save()
            
            # Mark as verified
            verification.is_verified = True
            verification.save()
            
            # Clear session
            del request.session['pending_user_id']
            
            messages.success(request, '✅ Email verified! Your account is activated. You can now login.')
            return redirect('login')
        else:
            messages.error(request, '❌ Invalid OTP. Please try again.')
    
    return render(request, 'verify_otp.html', {'email': user.email})


@cache_control(no_cache=True, no_store=True, must_revalidate=True)
def verify_otp_resend(request):
    """Resend OTP to user email"""
    user_id = request.session.get('pending_user_id')
    
    if not user_id:
        messages.error(request, 'Session expired. Please register again.')
        return redirect('register')
    
    try:
        user = User.objects.get(id=user_id)
        verification = EmailVerification.objects.get(user=user)
    except (User.DoesNotExist, EmailVerification.DoesNotExist):
        messages.error(request, 'Invalid session. Please register again.')
        return redirect('register')
    
    if request.method == 'POST':
        # Generate new OTP
        otp = str(random.randint(100000, 999999))
        otp_expires_at = timezone.now() + timedelta(minutes=10)
        
        # Update verification
        verification.otp = otp
        verification.otp_expires_at = otp_expires_at
        verification.save()
        
        # Send new OTP
        email_subject = "🎁 Your New Verification OTP - HamperWorld"
        email_body = f"""
Hello {user.username},

Your new verification code is:

🔐 {otp}

This code will expire in 10 minutes.

Best regards,
HamperWorld Team
"""
        try:
            send_mail(
                email_subject,
                email_body,
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=False,
            )
            messages.success(request, 'New OTP sent to your email.')
            return redirect('verify_otp')
        except Exception as e:
            messages.error(request, 'Failed to send OTP. Please try again.')
    
    return render(request, 'verify_otp_resend.html', {'email': user.email})


def forgot_password(request):
    """Send OTP for password reset"""
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        
        # Validate email is not empty
        if not email:
            messages.error(request, '❌ Please enter your email address.')
            return render(request, 'forgot_password.html')
        
        # Check if email exists
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            messages.error(request, '❌ No account found with this email address.')
            return render(request, 'forgot_password.html')
        
        # Generate OTP
        otp = str(random.randint(100000, 999999))
        otp_expires_at = timezone.now() + timedelta(minutes=10)
        
        # Create or update EmailVerification record for password reset
        verification, created = EmailVerification.objects.get_or_create(user=user)
        verification.otp = otp
        verification.otp_expires_at = otp_expires_at
        verification.is_verified = False  # Reset verification status
        verification.save()
        
        # Send OTP via email
        email_subject = "🔐 Password Reset OTP - HamperWorld"
        email_body = f"""
Hello {user.username},

You requested to reset your password. Your verification code is:

🔐 {otp}

This code will expire in 10 minutes.

If you didn't request this, please ignore this email.

Best regards,
HamperWorld Team
"""
        try:
            send_mail(
                email_subject,
                email_body,
                settings.DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=False,
            )
            messages.success(request, f'✅ OTP sent to {email}. Please check your inbox.')
            # Store email in session for password reset
            request.session['reset_email'] = email
            return redirect('reset_password')
        except Exception as e:
            messages.error(request, f'❌ Failed to send email: {str(e)}')
            return render(request, 'forgot_password.html')
    
    return render(request, 'forgot_password.html')


def reset_password(request):
    """Reset password with OTP verification"""
    reset_email = request.session.get('reset_email')
    
    if not reset_email:
        messages.error(request, 'Invalid session. Please request password reset again.')
        return redirect('forgot_password')
    
    try:
        user = User.objects.get(email=reset_email)
        verification = EmailVerification.objects.get(user=user)
    except (User.DoesNotExist, EmailVerification.DoesNotExist):
        messages.error(request, '❌ Invalid session. Please request password reset again.')
        return redirect('forgot_password')
    
    if request.method == 'POST':
        otp_entered = request.POST.get('otp', '').strip()
        new_password = request.POST.get('new_password', '').strip()
        confirm_password = request.POST.get('confirm_password', '').strip()
        
        # Check if OTP is valid
        if not verification.is_otp_valid():
            messages.error(request, '⏰ OTP has expired. Please request a new one.')
            del request.session['reset_email']
            return redirect('forgot_password')
        
        # Verify OTP
        if otp_entered != verification.otp:
            messages.error(request, '❌ Invalid OTP. Please try again.')
            return render(request, 'reset_password.html', {'email': reset_email})
        
        # Validate passwords match
        if new_password != confirm_password:
            messages.error(request, '❌ Passwords do not match.')
            return render(request, 'reset_password.html', {'email': reset_email})
        
        # Validate password strength
        if len(new_password) < 8:
            messages.error(request, '❌ Password must be at least 8 characters long.')
            return render(request, 'reset_password.html', {'email': reset_email})
        
        # Update password
        user.set_password(new_password)
        user.save()
        
        # Clear verification
        verification.is_verified = True
        verification.save()
        
        # Clear session
        del request.session['reset_email']
        
        messages.success(request, '✅ Password reset successfully! You can now login with your new password.')
        return redirect('login')
    
    return render(request, 'reset_password.html', {'email': reset_email})


@cache_control(no_cache=True, no_store=True, must_revalidate=True)
@login_required
def checkout(request, pk):
    """Checkout for a single hamper from product page"""
    hamper = Hamper.objects.get(pk=pk)
    
    # Get quantity from request (query parameter or POST)
    quantity = request.POST.get('quantity') or request.GET.get('quantity', 1)
    quantity = int(quantity) if str(quantity).isdigit() and int(quantity) > 0 else 1
    
    # Calculate total price for quantity
    total_price = hamper.price * quantity
    
    if request.method == 'POST':
        full_name = request.POST.get('full_name')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        country = request.POST.get('country')
        state = request.POST.get('state')
        city = request.POST.get('city')
        address = request.POST.get('address')
        postal_code = request.POST.get('postal_code')
        
        try:
            order = Order.objects.create(
                user=request.user,
                hamper=hamper,
                full_name=full_name,
                email=email or request.user.email,
                phone=phone,
                country=country,
                state=state,
                city=city,
                address=address,
                postal_code=postal_code
            )
            
            # Get country and state names
            country_name = dict(dj_countries)[country] if country in dict(dj_countries) else country
            state_display = state or 'N/A'
            
            subject = f"Order Confirmed! Order #{order.id}"
            message = f"""
╔════════════════════════════════════════════════════════════╗
║                   ORDER CONFIRMATION                       ║
║                    HamperWorld                             ║
╚════════════════════════════════════════════════════════════╝

Dear {full_name},

Thank you for shopping with HamperWorld! Your order has been confirmed.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ORDER DETAILS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Order Number: #{order.id}
Order Date: {order.created_at.strftime('%d %B %Y')}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ITEM DETAILS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Product: {hamper.name}
Price: ₹{hamper.price}
Quantity: {quantity}
Subtotal: ₹{total_price}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PRICE SUMMARY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Subtotal: ₹{total_price}
Shipping: FREE
Tax: ₹0.00
────────────────────
TOTAL: ₹{total_price}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DELIVERY INFORMATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Delivery Address:
{full_name}
{address}
{city}, {state_display}
{country_name} - {postal_code}

Status: Processing
Estimated Delivery: 5-7 Business Days

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

If you have any questions about your order, please reply to this email.

Best regards,
HamperWorld Team

"""
            
            try:
                send_mail(
                    subject,
                    message,
                    settings.EMAIL_HOST_USER,
                    [email or request.user.email],
                    fail_silently=False,
                )
            except Exception as e:
                print(f"Email error: {e}")
            
            # Store total in session for success page
            request.session['order_total'] = float(total_price)
            request.session.modified = True
            
            return redirect('checkout_success', pk=order.id)
        except Exception as e:
            messages.error(request, f'Error processing order: {str(e)}')
            return redirect('hamper_detail', pk=pk)
    
    # Get countries data
    countries_list = [(code, name) for code, name in dj_countries]
    
    cart = Cart(request)
    return render(request, 'checkout.html', {
        'hamper': hamper,
        'quantity': quantity,
        'total_price': total_price,
        'cart_items_count': cart.get_total_items(),
        'countries': json.dumps(countries_list),
    })


@cache_control(no_cache=True, no_store=True, must_revalidate=True)
@login_required
def checkout_cart(request):
    """Checkout for all items in cart"""
    cart = Cart(request)
    
    if not cart.cart:
        messages.error(request, 'Your cart is empty!')
        return redirect('cart_summary')
    
    if request.method == 'POST':
        full_name = request.POST.get('full_name')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        country = request.POST.get('country')
        state = request.POST.get('state')
        city = request.POST.get('city')
        address = request.POST.get('address')
        postal_code = request.POST.get('postal_code')
        
        try:
            # Create an order for each item in cart
            orders_created = []
            total_amount = 0
            order_items_dict = {}
            
            for hamper_id, item in cart.cart.items():
                try:
                    hamper = Hamper.objects.get(id=int(hamper_id))
                    qty = item['quantity']
                    price = float(item['price'])
                    item_total = price * qty
                    total_amount += item_total
                    
                    # Store for email display
                    order_items_dict[hamper_id] = {
                        'name': item['name'],
                        'price': price,
                        'quantity': qty,
                        'total': item_total
                    }
                    
                    # Create one order per quantity
                    for _ in range(qty):
                        order = Order.objects.create(
                            user=request.user,
                            hamper=hamper,
                            full_name=full_name,
                            email=email or request.user.email,
                            phone=phone,
                            country=country,
                            state=state,
                            city=city,
                            address=address,
                            postal_code=postal_code
                        )
                        orders_created.append(order)
                except Hamper.DoesNotExist:
                    continue
            
            if orders_created:
                # Build detailed order items list with quantities
                order_items_detail = []
                for hamper_id, item_info in order_items_dict.items():
                    qty = item_info['quantity']
                    price = item_info['price']
                    item_total = item_info['total']
                    order_items_detail.append(f"{item_info['name']:<35} | Qty: {qty:2} | ₹{price:>8.2f} | ₹{item_total:>8.2f}")
                
                order_lines = '\n'.join(order_items_detail)
                order_ids = ', '.join([str(o.id) for o in orders_created])
                subject = f"Order Confirmed! Order IDs: {order_ids}"
                message = f"""
╔════════════════════════════════════════════════════════════╗
║                   ORDER CONFIRMATION                       ║
║                    HamperWorld                             ║
╚════════════════════════════════════════════════════════════╝

Dear {full_name},

Thank you for shopping with HamperWorld! Your order has been confirmed.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ORDER DETAILS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Order Number(s): {order_ids}
Order Date: {orders_created[0].created_at.strftime('%d %B %Y')}
Total Items: {len(orders_created)}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ITEM DETAILS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Product Name                    | Qty | Price    | Total
────────────────────────────────────────────────────────────
{order_lines}
────────────────────────────────────────────────────────────

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PRICE SUMMARY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Subtotal: ₹{total_amount:.2f}
Shipping: FREE
Tax: ₹0.00
────────────────────
TOTAL: ₹{total_amount:.2f}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DELIVERY INFORMATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Delivery Address:
{full_name}
{address}
{city}, {state or 'N/A'}
{dict(dj_countries).get(country, country)} - {postal_code}

Status: Processing
Estimated Delivery: 5-7 Business Days

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

If you have any questions about your order, please reply to this email.

Best regards,
HamperWorld Team

"""
                
                try:
                    send_mail(
                        subject,
                        message,
                        settings.EMAIL_HOST_USER,
                        [request.user.email],
                        fail_silently=False,
                    )
                except Exception as e:
                    print(f"Email error: {e}")
                
                # Store total in session to display on success page
                request.session['order_total'] = total_amount
                request.session.modified = True
                
                # Clear cart
                cart.cart.clear()
                request.session.modified = True
                
                # Redirect to success page with first order
                return redirect('checkout_success', pk=orders_created[0].id)
        except Exception as e:
            messages.error(request, f'Error processing order: {str(e)}')
            return redirect('cart_summary')
    
    # GET request - show checkout form
    cart_items = []
    total = 0
    for hamper_id, item in cart.cart.items():
        price = float(item['price'])
        qty = item['quantity']
        cart_items.append({
            'id': hamper_id,
            'name': item['name'],
            'price': price,
            'quantity': qty,
            'total': price * qty
        })
        total += price * qty
    
    # Get countries data
    countries_list = [(code, name) for code, name in dj_countries]
    
    return render(request, 'checkout_cart.html', {
        'cart_items': cart_items,
        'total': total,
        'cart_items_count': cart.get_total_items(),
        'countries': json.dumps(countries_list),
    })


@cache_control(no_cache=True, no_store=True, must_revalidate=True)
@login_required
def checkout_success(request, pk):
    """Show order success page"""
    try:
        order = Order.objects.get(pk=pk, user=request.user)
    except Order.DoesNotExist:
        return redirect('hamper_list')
    
    # Get total from session if it was a cart checkout, otherwise use single order price
    total_amount = request.session.pop('order_total', None)
    if total_amount is None:
        total_amount = order.hamper.price
    
    return render(request, 'success.html', {
        'order': order,
        'total_amount': total_amount
    })

@cache_control(no_cache=True, no_store=True, must_revalidate=True)
def cart_add(request, pk):
    from django.http import JsonResponse
    
    # Check if user is authenticated
    if not request.user.is_authenticated:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'message': 'Please login to add items to cart',
                'redirect': request.build_absolute_uri('/login/?next=' + request.path)
            }, status=401)
        else:
            return redirect(f'/login/?next={request.path}')
    
    cart = Cart(request)
    hamper = get_object_or_404(Hamper, id=pk)
    
    # Get quantity from request (either from AJAX data or query parameter)
    quantity_str = str(request.GET.get('quantity', '1'))
    quantity = int(quantity_str) if quantity_str.isdigit() and int(quantity_str) > 0 else 1
    
    cart.add(hamper=hamper, quantity=quantity)
    
    # If AJAX request, return JSON response
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'message': f'{hamper.name} added to cart!',
            'cart_count': cart.get_total_items()
        })
    
    # Otherwise, redirect (for non-AJAX requests)
    return redirect('cart_summary')

@cache_control(no_cache=True, no_store=True, must_revalidate=True)
def cart_summary(request):
    cart = Cart(request)
    cart_items = []
    
    # We iterate through the session dictionary
    for item_id, item in cart.cart.items():
        cart_items.append({
            'product_id': item_id, # MUST match the template tag: item.product_id
            'name': item.get('name'),
            'price': float(item.get('price', 0)),
            'quantity': item.get('quantity', 0),
            'image': item.get('image'),
            'total': float(item.get('price', 0)) * item.get('quantity', 0)
        })
    
    return render(request, 'cart_summary.html', {
        'cart_items': cart_items,
        'total': cart.get_total(),
        'cart_items_count': cart.get_total_items()
    })
@login_required
def order_history(request):
    orders = Order.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'order_history.html', {'orders': orders})


from django.shortcuts import redirect

def clear_cart(request):
    if 'cart' in request.session:
        request.session['cart'] = {}
        request.session.modified = True
    return redirect('cart_summary')


def cart_remove_one(request, product_id):
    cart = request.session.get('cart', {})
    product_id = str(product_id)
    
    if product_id in cart:
        if cart[product_id]['quantity'] > 1:
            cart[product_id]['quantity'] -= 1
        else:
            del cart[product_id]
        request.session.modified = True
    return redirect('cart_summary')

def cart_item_delete(request, product_id):
    cart = request.session.get('cart', {})
    product_id = str(product_id)
    
    if product_id in cart:
        del cart[product_id]
        request.session.modified = True
    return redirect('cart_summary')