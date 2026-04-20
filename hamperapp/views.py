from pyexpat.errors import messages

from django.shortcuts import redirect, render
from .models import Hamper, Order
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
# Create your views here.

def hamper_list(request):
    hampers = Hamper.objects.all()
    return render(request, 'list.html', {'hampers': hampers})

def hamper_detail(request, pk):
    hamper = Hamper.objects.get(pk=pk)
    return render(request, 'details.html', {'hamper': hamper})

def register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get('username')
            messages.success(request, f'Account created for {username}!')
            return redirect('login')
    else:
        form = UserCreationForm()
    return render(request, 'register.html', {'form': form} )

@login_required
def checkout(request, pk):
    hamper = Hamper.objects.get(pk=pk)
    if request.method == 'POST':
        full_name = request.POST.get('full_name')
        address = request.POST.get('address')
        city = request.POST.get('city')
        postal_code = request.POST.get('postal_code')
        # Here you would handle the payment and order creation logic
        order = Order.objects.create(
            user=request.user,
            hamper=hamper,
            full_name=full_name,
            address=address,
            city=city,
            postal_code=postal_code
        )
        subject = f"New Order Received! Order #{order.id}"
        message = f"""
        Hello Owner,

        You have a new order for: {hamper.name}
        Total Price: ${hamper.price}

        Customer Details:
        Name: {full_name}
        Address: {address}, {city}, {postal_code}
        Customer Email: {request.user.email}

        Please log in to the admin panel to process this order.
        """
        
        try:
            send_mail(
                subject,
                message,
                settings.EMAIL_HOST_USER,
                ['bilalsalam65@gmail.com'],
                fail_silently=False,
            )
        except Exception as e:
            print(f"Email error: {e}")
        
        return render(request,'success.html',{'order': order})
    return render(request, 'checkout.html', {'hamper': hamper})