# exchange/admin.py
from django.contrib import admin
from django.utils import timezone

from .models import ExchangeRate, ExchangeTransaction


class ExchangeRateAdmin(admin.ModelAdmin):

    list_display = ('currency_from', 'currency_to', 'rate', 'date')  # Поля, отображаемые в списке
    search_fields = ('currency_from', 'currency_to')  # Поля для поиска
    list_filter = ('date',)

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if not obj:  # Если объект не существует (т.е. создаётся новая запись)
            form.base_fields['date'].initial = timezone.now().date()  # Установите сегодняшнюю дату
        return form


class ExchangeTransactionAdmin(admin.ModelAdmin):
    list_display = (
        'operator', 'currency_from', 'currency_to', 'amount', 'exchanged_amount', 'date')  # Поля, отображаемые в списке
    search_fields = ('operator', 'date', 'currency_from', 'currency_to')  # Поля для поиска
    list_filter = ('date',)


# Регистрация модели
admin.site.register(ExchangeRate, ExchangeRateAdmin)
admin.site.register(ExchangeTransaction, ExchangeTransactionAdmin)
