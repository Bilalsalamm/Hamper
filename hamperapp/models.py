from django.db import models

# Create your models here.
class Hamper(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    image = models.ImageField(upload_to='hamper_images/')

    def __str__(self):
        return self.name

class Order(models.Model):
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE)
    hamper = models.ForeignKey(Hamper, on_delete=models.CASCADE)    
    full_name = models.CharField(max_length=100)
    address = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)
    is_paid = models.BooleanField(default=False)

    def __str__(self):
        return f'Order {self.id} by {self.user.username}'