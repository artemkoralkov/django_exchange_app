# exchange/forms.py
import requests
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import connection
from django.utils import timezone


# from .models import ExchangeRate


class ExchangeForm(forms.Form):
    currency_from = forms.ChoiceField(choices=[], label='Продаю:')
    currency_to = forms.ChoiceField(choices=[], label='Покупаю:')
    amount = forms.DecimalField(decimal_places=2, label='Количество:', min_value=0.01, required=True)
    amount_to_get = forms.IntegerField(label='Укажите сколько хотите получить,'
                                             ' если оставить пустым обменяется вся валюта', required=False)

    def clean(self):
        cleaned_data = super().clean()
        currency_from = cleaned_data.get('currency_from')
        currency_to = cleaned_data.get('currency_to')

        # Проверяем, что валюты не одинаковые
        if currency_from and currency_to and currency_from == currency_to:
            raise ValidationError("Невозможно провести операцию: валюты одинаковы")

        return cleaned_data


class AddExchangeRateForm(forms.Form):
    currency = forms.ChoiceField(choices=[], required=True, label='Валюта')
    use_api = forms.BooleanField(required=False, label="Получить курс из API")
    rate_to_base = forms.DecimalField(max_digits=10, required=False, decimal_places=4, label='Курс к базовой валюте')
    rate_date = forms.DateField(initial=timezone.now().date(), required=False,
                                widget=forms.SelectDateWidget(years=range(2000, 2050)), label='Дата курса')


class AddCurrencyToCashForm(forms.Form):
    # Получаем список валют из таблицы cash_reserves
    currency_name = forms.ChoiceField(choices=[], label="Выберите валюту")
    amount_in_cash = forms.IntegerField(min_value=1, max_value=10000000, required=True,
                                        label='Количество валюты для пополнения')


class UserRegisterForm(UserCreationForm):
    class Meta:
        model = User
        fields = ['username', 'password1', 'password2']


class AddCurrencyForm(forms.Form):
    currency_name = forms.CharField(max_length=50, label='Название валюты')
    amount_in_cash = forms.IntegerField(max_value=999999, label='Начальный баланс', min_value=0)
