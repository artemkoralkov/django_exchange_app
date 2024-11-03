from django.db import models
from django.contrib.auth.models import User


class ExchangeRate(models.Model):
    id = models.AutoField(primary_key=True)
    currency_from = models.CharField(max_length=3)
    currency_to = models.CharField(max_length=3)
    rate = models.DecimalField(max_digits=10, decimal_places=4)
    date = models.DateField()

    class Meta:
        verbose_name = "Курс обмена"
        verbose_name_plural = "Курсы обмена"

    def __str__(self):
        return f"{self.currency_from} to {self.currency_to} at {self.rate}"


class ExchangeTransaction(models.Model):
    id = models.AutoField(primary_key=True)
    operator = models.ForeignKey(User, on_delete=models.CASCADE)
    currency_from = models.CharField(max_length=3)
    currency_to = models.CharField(max_length=3)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    exchanged_amount = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Транзакцию обмена"
        verbose_name_plural = "Транзакции обмена"

    def __str__(self):
        return f"{self.amount} {self.currency_from} exchanged for {self.exchanged_amount} {self.currency_to}"
