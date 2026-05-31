from django.db import models
from django.conf import settings
from transactions.models import Category

class Budget(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    amount = models.FloatField()
    month = models.DateField()  # E.g., 2026-05-01 representing May 2026

    class Meta:
        unique_together = ('user', 'category', 'month')

    def __str__(self):
        return f"{self.user.username} - {self.category.name} - {self.amount} ({self.month.strftime('%Y-%m')})"
