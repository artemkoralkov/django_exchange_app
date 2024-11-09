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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        with connection.cursor() as cursor:
            cursor.execute("SELECT currency_id, currency_name FROM cash_reserves")
            currency_choices = cursor.fetchall()
        # Преобразуем множество валют в список и создаем выбор валют
        self.fields['currency_from'].choices = currency_choices
        self.fields['currency_to'].choices = currency_choices

    def clean(self):
        cleaned_data = super().clean()
        currency_from = cleaned_data.get('currency_from')
        currency_to = cleaned_data.get('currency_to')

        # Проверяем, что валюты не одинаковые
        if currency_from and currency_to and currency_from == currency_to:
            raise ValidationError("Невозможно провести операцию: валюты одинаковы")

        return cleaned_data


class AddExchangeRateForm(forms.Form):
    currency_name = forms.CharField(max_length=30, required=True, label='Валюта')
    rate_to_base = forms.DecimalField(max_digits=10, decimal_places=4, required=True, label='Курс к базовой валюте')
    amount_in_cash = forms.IntegerField(initial=0, max_value=10000000, required=False,
                                        label='Количество валюты для пополнения')
    rate_date = forms.DateField(required=True, initial=timezone.now().date(),
                                widget=forms.SelectDateWidget(years=range(2000, 2050)), label='Дата курса')


class AddExchangeRateFromAPIForm(forms.Form):
    currencies_from_api = [(i['Cur_ID'], requests.get(f'https://api.nbrb.by/exrates/currencies/{i['Cur_ID']}')
                            .json()['Cur_Name']) for i in
                           requests.get('https://api.nbrb.by/exrates/rates?periodicity=0')
                           .json()]

    currency_name = forms.ChoiceField(
        choices=currencies_from_api,
        label="Выберите валюту для добавления из API"
    )
    amount_in_cash = forms.IntegerField(initial=0, max_value=10000000, required=False,
                                        label='Количество валюты для пополнения')


class AddCurrencyToCashForm(forms.Form):
    # Получаем список валют из таблицы cash_reserves
    with connection.cursor() as cursor:
        cursor.execute("SELECT currency_name FROM cash_reserves")
        currencies = cursor.fetchall()
        currency_choices = [(currency[0], currency[0]) for currency in currencies]
    currency_name = forms.ChoiceField(choices=currency_choices, label="Выберите валюту")
    amount_in_cash = forms.IntegerField(initial=0, max_value=10000000, required=False,
                                        label='Количество валюты для пополнения')


class UserRegisterForm(UserCreationForm):

    class Meta:
        model = User
        fields = ['username', 'password1', 'password2']