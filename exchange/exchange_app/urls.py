# exchange/urls.py
from django.urls import path
from .views import (
    login_view,
    logout_view,
    rates_view,
    index,
    add_exchange_rate,
    exchange_view,
    transaction_history_view,
    add_currency_to_cash,
    delete_rate,
    cash_reserves_view,
    add_currency_view,
    register_view,
    delete_currencies_view,
    delete_exchange,
    archive_currency_view,
    unarchived_currency_view,
)

app_name = "exchange_app"

urlpatterns = [
    path("", index, name="index"),
    path("accounts/login/", login_view, name="login"),
    path("accounts/logout/", logout_view, name="logout"),
    path("rates/", rates_view, name="rates"),
    path("rates/delete/", delete_rate, name="delete_rate"),
    path("add_exchange_rate/", add_exchange_rate, name="add_exchange_rate"),
    path("exchange_currency/", exchange_view, name="exchange_currency"),
    path("add_currency_to_cash/", add_currency_to_cash, name="add_currency_to_cash"),
    path("exchange_history/", transaction_history_view, name="exchange_history"),
    path("exchange_history/delete_exchange", delete_exchange, name="delete_exchange"),
    path("register/", register_view, name="register"),
    path("cash_reserves/", cash_reserves_view, name="cash_reserves"),
    path("cash_reserves/add_currency/", add_currency_view, name="add_currency"),
    path(
        "cash_reserves/delete/<int:currency_id>/",
        delete_currencies_view,
        name="delete_currencies",
    ),
    path(
        "cash_reserves/archive/<int:currency_id>/",
        archive_currency_view,
        name="archive_currency",
    ),
    path(
        "cash_reserves/unarchived/<int:currency_id>/",
        unarchived_currency_view,
        name="unarchived_currency",
    ),
]
