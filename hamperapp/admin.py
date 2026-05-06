from django.contrib import admin
from .models import Hamper, Order, EmailVerification
from django.utils.html import format_html, mark_safe

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

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['order_id_badge', 'customer_name', 'hamper_name', 'quantity', 'verification_status', 'payment_status_display', 'payment_proof_thumbnail', 'created_at']
    list_editable = [] 
    list_filter = ['status', 'payment_status', 'created_at']
    search_fields = ['full_name', 'id', 'user__email', 'email']
    
    # CRITICAL: We only list the display methods here, NOT 'payment_screenshot'
    readonly_fields = ['payment_screenshot_display', 'payment_proof_link', 'created_at', 'user', 'hamper'] 
    
    fieldsets = (
        ('Order Information', {
            'fields': ('user', 'hamper', 'quantity', 'status', 'payment_status', 'created_at')
        }),
        ('Customer Details', {
            'fields': ('full_name', 'email', 'phone', 'country', 'state', 'city', 'address', 'postal_code')
        }),
        ('Payment Proof for Admin Verification', {
            'fields': ('payment_screenshot_display', 'payment_proof_link'),
            'description': '👇 Review the customer\'s payment screenshot below and verify the transaction'
        }),
    )
    
    actions = ['approve_payment', 'reject_payment', 'mark_packed', 'mark_shipped', 'cancel_order']

    def order_id_badge(self, obj):
        """Display order ID with color coding"""
        color = '#27ae60' if obj.payment_status == 'Paid' else '#e74c3c'
        return format_html(
            '<span style="background-color: {}; color: white; padding: 5px 10px; border-radius: 4px; font-weight: bold; font-size: 12px;">Order #{}</span>',
            color, obj.id
        )
    order_id_badge.short_description = 'Order ID'
    
    def customer_name(self, obj):
        """Display customer name and email"""
        return format_html(
            '<div><strong>{}</strong><br><small style="color: #666;">{}</small></div>',
            obj.full_name, obj.email or obj.user.email
        )
    customer_name.short_description = 'Customer'
    
    def hamper_name(self, obj):
        """Display hamper name"""
        return obj.hamper.name
    hamper_name.short_description = 'Product'
    
    def verification_status(self, obj):
        """Show payment verification status with visual indicator"""
        if obj.status == 'Verifying':
            return mark_safe(
                '<span style="background-color: #f39c12; color: white; padding: 6px 12px; border-radius: 4px; font-weight: bold; font-size: 11px; display: inline-block;"'
                '>⏳ AWAITING VERIFICATION</span>'
            )
        elif obj.payment_status == 'Paid' and obj.status != 'Verifying':
            return format_html(
                '<span style="background-color: #27ae60; color: white; padding: 6px 12px; border-radius: 4px; font-weight: bold; font-size: 11px; display: inline-block;">'
                '✅ {}</span>',
                obj.status
            )
        else:
            return format_html(
                '<span style="background-color: #95a5a6; color: white; padding: 6px 12px; border-radius: 4px; font-weight: bold; font-size: 11px; display: inline-block;">'
                '❌ {}</span>',
                obj.status
            )
    verification_status.short_description = 'Status'
    
    def payment_status_display(self, obj):
        """Show payment verification status"""
        if obj.payment_status == 'Paid':
            return mark_safe(
                '<span style="color: #27ae60; font-weight: bold;">✅ PAID</span>'
            )
        elif obj.payment_status == 'Pending Verification':
            return mark_safe(
                '<span style="color: #f39c12; font-weight: bold;">⏳ PENDING VERIFICATION</span>'
            )
        else:
            return mark_safe(
                '<span style="color: #e74c3c; font-weight: bold;">❌ NOT PAID</span>'
            )
    payment_status_display.short_description = 'Payment Status'

    def payment_proof_thumbnail(self, obj):
        """Small preview in the main list table - clickable"""
        if obj.payment_screenshot:
            return format_html(
                '<a href="{}" target="_blank" style="display: inline-block; cursor: pointer;">'
                '<img src="{}" style="width: 50px; height: 50px; object-fit: cover; border-radius: 4px; border: 2px solid #e61e2a; transition: transform 0.2s;" '
                'onmouseover="this.style.transform=\'scale(1.3)\';" onmouseout="this.style.transform=\'scale(1)\';" title="Click to view full screenshot" />'
                '</a>', 
                obj.payment_screenshot.url, obj.payment_screenshot.url
            )
        return mark_safe('<span style="color: #bdc3c7;">—</span>')
    payment_proof_thumbnail.short_description = 'Screenshot'

    def payment_screenshot_display(self, obj):
        """Display the payment screenshot in detail view - LARGE"""
        if obj.payment_screenshot:
            return format_html(
                '<div style="border: 2px solid #e61e2a; padding: 15px; border-radius: 8px; max-width: 600px; background: #f8f9fa;">'
                '<div style="margin-bottom: 10px; font-weight: bold; color: #333;">📸 Payment Receipt:</div>'
                '<img src="{}" style="max-width: 100%; height: auto; border-radius: 4px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);" />'
                '<div style="margin-top: 10px; font-size: 12px; color: #666;">File: {}</div>'
                '</div>',
                obj.payment_screenshot.url, obj.payment_screenshot.name
            )
        else:
            # Debug: show what's actually stored
            return mark_safe(
                '<div style="background: #fff3cd; padding: 15px; border-radius: 8px; border-left: 4px solid #ffc107;">'
                '<em style="color: #e74c3c; font-size: 14px;"><strong>⚠️ No File Uploaded</strong></em>'
                '<p style="margin-top: 10px; font-size: 12px; color: #666;">Field value: "{}"</p>'
                '<p style="font-size: 12px; color: #666;">Make sure the file was selected in the checkout form and the upload completed successfully.</p>'
                '</div>'.format(obj.payment_screenshot.name if obj.payment_screenshot else 'NULL/Empty')
            )
    payment_screenshot_display.short_description = '💳 Payment Receipt'
    
    def payment_proof_link(self, obj):
        """Action button to open or download"""
        if obj.payment_screenshot:
            return format_html(
                '<a href="{}" target="_blank" download style="background-color: #e61e2a; color: white; padding: 10px 18px; '
                'border-radius: 4px; text-decoration: none; font-weight: bold; font-size: 13px; display: inline-block; transition: background 0.3s;">'
                '📥 Download Screenshot</a> '
                '<a href="{}" target="_blank" style="background-color: #3498db; color: white; padding: 10px 18px; '
                'border-radius: 4px; text-decoration: none; font-weight: bold; font-size: 13px; display: inline-block; margin-left: 5px; transition: background 0.3s;">'
                '🔍 View Full Size</a>', 
                obj.payment_screenshot.url, obj.payment_screenshot.url
            )
        return mark_safe('<em style="color: #999;">No file available</em>')
    payment_proof_link.short_description = 'Download / View'    
    
    def display_product_image(self, obj):
        """Display product image"""
        if obj.hamper and obj.hamper.image:
            return format_html(
                '<img src="{}" style="width: 50px; height: 50px; object-fit: cover; border-radius: 5px;" />',
                obj.hamper.image.url
            )
        return "No Image"

    display_product_image.short_description = 'Product Image'

    @admin.action(description='✅ APPROVE Payment - Mark as Paid & Packed')
    def approve_payment(self, request, queryset):
        """Approve payment and set status to Packed"""
        updated = queryset.filter(status='Verifying', payment_screenshot__isnull=False).update(
            payment_status='Paid', 
            status='Packed'
        )
        self.message_user(request, f'✅ {updated} order(s) payment approved and marked as Packed.')
    
    @admin.action(description='❌ REJECT Payment - Keep as Pending')
    def reject_payment(self, request, queryset):
        """Reject payment and revert to Pending"""
        updated = queryset.filter(status='Verifying').update(
            payment_status='Not Paid',
            status='Pending'
        )
        self.message_user(request, f'❌ {updated} order(s) payment rejected. Customer can resubmit.')

    @admin.action(description='📦 Mark as Packed')
    def mark_packed(self, request, queryset):
        updated = queryset.update(status='Packed')
        self.message_user(request, f'✅ {updated} order(s) marked as Packed.')

    @admin.action(description='🚚 Mark as Shipped')
    def mark_shipped(self, request, queryset):
        updated = queryset.update(status='Shipped')
        self.message_user(request, f'✅ {updated} order(s) marked as Shipped.')

    @admin.action(description='❌ Cancel Order - No Payment/Verification')
    def cancel_order(self, request, queryset):
        """Cancel orders that don't have verified payment"""
        # Only allow cancelling orders that are not yet shipped
        cancellable = queryset.exclude(status__in=['Shipped', 'Delivered', 'Cancelled'])
        updated = cancellable.update(status='Cancelled', payment_status='Not Paid')
        self.message_user(request, f'❌ {updated} order(s) cancelled.')


@admin.register(EmailVerification)
class EmailVerificationAdmin(admin.ModelAdmin):
    list_display = ['user', 'is_verified', 'created_at', 'otp_expires_at']
    list_filter = ['is_verified', 'created_at']
    search_fields = ['user__email', 'user__username']
    readonly_fields = ['otp', 'created_at', 'otp_expires_at']

