from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from PIL import Image
import os
from io import BytesIO
from django.core.files.base import ContentFile
from django.utils import timezone
from datetime import timedelta

# Create your models here.
class Hamper(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    image = models.ImageField(upload_to='hamper_images/')

    def __str__(self):
        return self.name

class EmailVerification(models.Model):
    """Track OTP verification for new accounts"""
    user = models.OneToOneField('auth.User', on_delete=models.CASCADE)
    otp = models.CharField(max_length=6, default='000000')
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    otp_expires_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f'OTP Verification for {self.user.email}'
    
    def is_otp_valid(self):
        """Check if OTP is still valid (within 10 minutes)"""
        return timezone.now() <= self.otp_expires_at and not self.is_verified


class Order(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Verifying', 'Verifying Payment'), # New status for review
        ('Packed', 'Packed'),
        ('Shipped', 'Shipped'),
        ('Delivered', 'Delivered'),
        ('Cancelled', 'Cancelled'),
    ]

    PAYMENT_STATUS_CHOICES = [
        ('Not Paid', 'Not Paid'),
        ('Pending Verification', 'Pending Verification'),
        ('Paid', 'Paid'),
    ]

    user = models.ForeignKey('auth.User', on_delete=models.CASCADE)
    hamper = models.ForeignKey(Hamper, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)    
    full_name = models.CharField(max_length=100)
    email = models.EmailField(max_length=255, blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    country = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=100, blank=True, null=True)
    city = models.CharField(max_length=100)
    address = models.CharField(max_length=255)
    postal_code = models.CharField(max_length=20)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    payment_status = models.CharField(max_length=25, choices=PAYMENT_STATUS_CHOICES, default='Not Paid')
    created_at = models.DateTimeField(auto_now_add=True)
    
    # New field for manual payment verification
    payment_screenshot = models.ImageField(upload_to='payment_proofs/', blank=True, null=True)

    def __str__(self):
        return f'Order {self.id} by {self.user.username}'
    
    @property
    def is_paid(self):
        """Backward compatibility property"""
        return self.payment_status == 'Paid'
# Signal to optimize images on save
@receiver(post_save, sender=Hamper)
def optimize_hamper_image(sender, instance, created, **kwargs):
    """Automatically compress and optimize images when hamper is saved"""
    if instance.image:
        try:
            # Open the image
            img = Image.open(instance.image.path)
            
            # Convert RGBA to RGB if necessary
            if img.mode in ('RGBA', 'LA'):
                rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                rgb_img.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = rgb_img
            
            # Resize if too large (max 1200px width)
            max_width = 1200
            if img.width > max_width:
                ratio = max_width / img.width
                new_height = int(img.height * ratio)
                img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
            
            # Save with compression
            output = BytesIO()
            img.save(output, format='JPEG', quality=80, optimize=True)
            output.seek(0)
            
            # Save the compressed image back
            instance.image.save(instance.image.name, ContentFile(output.read()), save=False)
            instance.save(update_fields=['image'])
        except Exception as e:
            print(f"Error optimizing image: {e}")
            pass