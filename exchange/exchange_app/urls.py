# exchange/urls.py
from django.urls import path
from .views import login_view, logout_view, rates_view, index, test, add_exchange_rate, \
    add_exchange_rate_from_api, exchange_view, transaction_history_view, add_currency_to_cash, delete_rate, register

app_name = 'exchange_app'

urlpatterns = [
    path('', index, name='index'),
    path('accounts/login/', login_view, name='login'),
    path('accounts/logout/', logout_view, name='logout'),
    path('rates/', rates_view, name='rates'),
    path('rates/delete/<int:rate_id>/', delete_rate, name='delete_rate'),
    path('add_exchange_rate/', add_exchange_rate, name='add_exchange_rate'),
    path('add_exchange_rate_from_api/', add_exchange_rate_from_api, name='add_exchange_rate_from_api'),
    path('exchange_currency/', exchange_view, name='exchange_currency'),
    path('add_currency_to_cash/', add_currency_to_cash, name='add_currency_to_cash'),
    path('exchange_history/', transaction_history_view, name='exchange_history'),
    path('test/', test, name='test'),
    path('register/', register, name='register'),
]
