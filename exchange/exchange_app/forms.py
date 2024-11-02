# exchange/forms.py
from django import forms
from .models import ExchangeRate


class ExchangeForm(forms.Form):
    currency_from = forms.ChoiceField(choices=[], label='Валюта из:')
    currency_to = forms.ChoiceField(choices=[], label='Валюта в:')
    amount = forms.DecimalField(decimal_places=2, label='Количество:', min_value=0.01)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Получаем все доступные пары валют
        rates = ExchangeRate.objects.all()
        currencies = set()

        # Добавляем валюты, которые имеют пары
        for rate in rates:
            currencies.add(rate.currency_from)
            currencies.add(rate.currency_to)

        # Преобразуем множество в список и создаем выбор валют
        currency_choices = [(currency, currency) for currency in currencies]
        self.fields['currency_from'].choices = currency_choices
        self.fields['currency_to'].choices = currency_choices

    def clean(self):
        cleaned_data = super().clean()
        currency_from = cleaned_data.get('currency_from')
        currency_to = cleaned_data.get('currency_to')

        if currency_from and currency_to and currency_from == currency_to:
            raise forms.ValidationError("Валюты 'из' и 'в' не могут быть одинаковыми.")

        # Проверяем, существуют ли пары обмена для выбранных валют
        if currency_from and currency_to:
            if not ExchangeRate.objects.filter(currency_from=currency_from, currency_to=currency_to).exists():
                raise forms.ValidationError("Нет доступного курса обмена для данной пары валют.")
