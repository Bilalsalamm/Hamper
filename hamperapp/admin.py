from django.contrib import admin
from .models import Hamper, Order, EmailVerification
from django.utils.html import format_html

@admin.register(Hamper)
class HamperAdmin(admin.ModelAdmin):
    list_display = ['name', 'image_preview', 'price']
    list_filter = ['price']
    search_fields = ['name', 'description']
    
    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="max-width: 50px; max-height: 50px; border-radius: 4px;" />',
                obj.image.url
            )
        return "No Image"
    
    # 3. This must also be indented inside the class
    image_preview.short_description = 'Preview'

# hamperapp/admin.py
from django.contrib import admin
from .models import Order

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    # status must be in list_display to be in list_editable
    list_display = ['id', 'user', 'full_name', 'status', 'is_paid', 'created_at']
    
    # This allows you to change status without opening the order
    list_editable = ['status'] 
    
    list_filter = ['status', 'is_paid']
    search_fields = ['full_name', 'id']
    
    # Custom actions for bulk updating
    actions = ['make_shipped', 'make_packed']


    def display_product_image(self, obj):
        # 1. Check if the order has a hamper and the hamper has an image
        if obj.hamper and obj.hamper.image:
            return format_html(
                '<img src="{}" style="width: 50px; height: 50px; object-fit: cover; border-radius: 5px;" />',
                obj.hamper.image.url
            )
        return "No Image"

    # 2. Make sure this line is indented correctly (aligned with 'def')
    display_product_image.short_description = 'Product Image'

    @admin.action(description='Mark selected orders as Shipped')
    def make_shipped(self, request, queryset):
        queryset.update(status='Shipped')

    @admin.action(description='Mark selected orders as Packed')
    def make_packed(self, request, queryset):
        queryset.update(status='Packed')

@admin.register(EmailVerification)
class EmailVerificationAdmin(admin.ModelAdmin):
    list_display = ['user', 'is_verified', 'created_at', 'otp_expires_at']
    list_filter = ['is_verified', 'created_at']
    search_fields = ['user__email', 'user__username']
    readonly_fields = ['otp', 'created_at', 'otp_expires_at']

