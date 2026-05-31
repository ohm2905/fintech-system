from django.db import models
from django.conf import settings

class Portfolio(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    stock_name = models.CharField(max_length=100)
    quantity = models.IntegerField()
    buy_price = models.FloatField()

    def __str__(self):
        return f"{self.stock_name} - {self.user.username}"


class StockTransaction(models.Model):
    TRANSACTION_TYPES = (
        ('BUY', 'Buy'),
        ('SELL', 'Sell'),
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    stock_name = models.CharField(max_length=100)
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPES)
    quantity = models.IntegerField()
    price = models.FloatField()
    date = models.DateField()

    def __str__(self):
        return f"{self.user.username} - {self.transaction_type} {self.quantity} {self.stock_name} @ {self.price}"
    
