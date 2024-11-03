from django.db import models
from django.contrib.auth.models import User


class ExchangeRate(models.Model):
    id = models.AutoField(primary_key=True)
    currency_from = models.CharField(max_length=3, verbose_name='Валюта на продажу')
    currency_to = models.CharField(max_length=3, verbose_name='Валюта на покупку')
    rate = models.DecimalField(max_digits=10, decimal_places=4, verbose_name='Курс обмена')
    date = models.DateField(verbose_name='Дата')

    class Meta:
        verbose_name = "Курс обмена"
        verbose_name_plural = "Курсы обмена"

    def __str__(self):
        return f"{self.currency_from} to {self.currency_to} at {self.rate}"


class ExchangeTransaction(models.Model):
    id = models.AutoField(primary_key=True)
    operator = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='Пользователь')
    currency_from = models.CharField(max_length=3, verbose_name='Валюта на продажу')
    currency_to = models.CharField(max_length=3, verbose_name='Валюта на покупку')
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Продано')
    exchanged_amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Куплено')
    date = models.DateTimeField(auto_now_add=True, verbose_name='Дата')

    class Meta:
        verbose_name = "Транзакцию обмена"
        verbose_name_plural = "Транзакции обмена"

    def __str__(self):
        return f"{self.amount} {self.currency_from} exchanged for {self.exchanged_amount} {self.currency_to}"
