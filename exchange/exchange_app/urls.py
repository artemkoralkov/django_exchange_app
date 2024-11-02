# exchange/urls.py
from django.urls import path
from .views import login_view, logout_view, rates_view, exchange_view, transaction_history_view, index
app_name = 'exchange'
urlpatterns = [
    path('', index, name='index'),
    path('accounts/login/', login_view, name='login'),
    path('accounts/logout/', logout_view, name='logout'),
    path('rates/', rates_view, name='rates'),
    path('exchange_currency/', exchange_view, name='exchange_currency'),
    path('exchange_history/', transaction_history_view, name='exchange_history'),
]
