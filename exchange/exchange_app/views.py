# exchange/views.py
import requests
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import connection, IntegrityError
from django.shortcuts import render, redirect
from django.utils import timezone

from .forms import (
    ExchangeForm,
    AddExchangeRateForm,
    AddCurrencyToCashForm,
    UserRegisterForm,
    AddCurrencyForm,
)
from .utils import CurrencyExchangeService

currency_exchange_service = CurrencyExchangeService()


def index(request):
    return render(request, "exchange/index.html")


def login_view(request):
    if request.method == "POST":
        username = request.POST["username"]
        password = request.POST["password"]
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect("exchange:rates")
        else:
            messages.error(request, "Неправильное имя пользователя или пароль.")
    return render(request, "exchange/login.html")


def logout_view(request):
    logout(request)
    return redirect("exchange:login")


@login_required(login_url="/exchange/accounts/login/")
def rates_view(request):
    rates_data = currency_exchange_service.get_rates()
    return render(request, "exchange/rates.html", {"rates": rates_data})


@user_passes_test(lambda u: u.is_superuser)
def add_exchange_rate(request):
    form = AddExchangeRateForm(request.POST or None)
    currency_choices = currency_exchange_service.get_currency()
    form.fields["currency"].choices = [
        (f"{currency[0]}:{currency[1]}", currency[1])
        for currency in currency_choices[1:]
    ]
    if request.method == "POST":
        if form.is_valid():
            currency_id, currency_name = form.cleaned_data["currency"].split(":")
            rate_date = form.cleaned_data["rate_date"].strftime("%Y-%m-%d")
            use_api = form.cleaned_data["use_api"]
            markup = form.cleaned_data["markup"]
            if use_api:
                rate_to_base, error = currency_exchange_service.get_rate_from_api(currency_name)
                if error:
                    messages.error(request, error)
                    return redirect('exchange:add_exchange_rate')
            else:
                rate_to_base = form.cleaned_data['rate_to_base']
            if not rate_to_base:
                messages.error(request, "Введите курс валюты или добавьте его из API.")
                return redirect("exchange:add_exchange_rate")

            rate_to_base_with_markup = currency_exchange_service.apply_markup(rate_to_base, markup)
            currency_exchange_service.add_exchange_rate(currency_id, rate_to_base_with_markup, rate_date)

            messages.success(request, f"Курс для {currency_name} успешно добавлен!")
            return redirect("exchange:rates")  # или на нужную вам страницу
        else:
            messages.error(request, "Пожалуйста, заполните все поля.")

    return render(request, "exchange/add_exchange_rate.html", {"form": form})


@login_required(login_url="/exchange/accounts/login/")
def exchange_view(request):
    # Только операторы могут выполнять обмен
    if request.user.is_superuser:
        messages.error(request, "Только операторы могут обменивать валюту.")
        return redirect("exchange:rates")
    form = ExchangeForm(request.POST or None)
    currency_choices = [(i[0], i[1]) for i in currency_exchange_service.get_currency()]
    # Преобразуем множество валют в список и создаем выбор валют
    form.fields["currency_from"].choices = currency_choices
    form.fields["currency_to"].choices = currency_choices
    if request.method == "POST":
        if form.is_valid():
            currency_from_id = form.cleaned_data["currency_from"]
            currency_to_id = form.cleaned_data["currency_to"]
            amount = form.cleaned_data["amount"]
            amount_to_get = form.cleaned_data.get("amount_to_get", None)

            # Расчёт обмена
            exchanged_amount, change_in_base, error = currency_exchange_service.calculate_exchange(
                currency_from_id, currency_to_id, amount, amount_to_get
            )

            if error:
                messages.error(request, error)
                return redirect("exchange:exchange_currency")

            # Запись транзакции
            currency_exchange_service.record_transaction(
                operator_id=request.user.id,
                currency_from_id=currency_from_id,
                currency_to_id=currency_to_id,
                amount=amount,
                exchanged_amount=exchanged_amount,
                change_in_base=change_in_base,
            )

            # Уведомление об успешном обмене
            change_string = (
                f"Сдача: {change_in_base:.2f} в базовой валюте."
                if change_in_base != 0 else ""
            )
            messages.success(
                request,
                f"Вы обменяли {amount} {currency_exchange_service.get_currency_name(currency_from_id)} на "
                f"{exchanged_amount:.2f} {currency_exchange_service.get_currency_name(currency_to_id)}. "
                + change_string
            )
            return redirect("exchange:rates")

    return render(request, "exchange/exchange.html", {"form": form})


@login_required(login_url="/exchange/accounts/login/")
def transaction_history_view(request):
    is_admin = request.user.is_superuser
    # Если пользователь - администратор, показываем все транзакции
    if is_admin:
        transactions = currency_exchange_service.get_transactions()
    else:
        # Если пользователь - оператор, показываем только его транзакции
        user_id = request.user.id
        transactions = currency_exchange_service.get_transactions(user_id)
    context = {
        "transactions": transactions,
        "is_admin": is_admin,
    }
    return render(request, "exchange/history.html", context)


@user_passes_test(lambda u: u.is_superuser)
def add_currency_to_cash(request):
    form = AddCurrencyToCashForm(request.POST or None)
    currency_choices = [(currency[1], currency[1]) for currency in currency_exchange_service.get_currency()[1:]]
    form.fields["currency_name"].choices = currency_choices
    if request.method == "POST":

        if form.is_valid():
            currency_name = form.cleaned_data[
                "currency_name"
            ]  # Получаем выбранную валюту
            amount_in_cash = form.cleaned_data["amount_in_cash"]
            currency_exchange_service.update_currency_cash(amount_in_cash, currency_name)
            messages.success(
                request, f"Валюта {currency_name} успешно добавлена/обновлена в кассе!"
            )
            return redirect(
                "exchange:cash_reserves"
            )  # Перенаправляем на страницу с кассой
        else:
            messages.error(request, "Пожалуйста, заполните все поля.")

    return render(request, "exchange/add_currency_to_cash.html", {"form": form})


def register_view(request):
    if request.method == "POST":
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("exchange:index")
    else:
        form = UserRegisterForm()
    return render(request, "exchange/register.html", {"form": form})


@user_passes_test(lambda u: u.is_superuser)
def cash_reserves_view(request):
    currencies_data = [
        {
            "currency_id": currency[0],
            "currency_name": currency[1],
            "amount_in_cash": currency[2],
        }
        for currency in currency_exchange_service.get_currency()[1:]
    ]

    return render(
        request, "exchange/cash_reserves.html", {"currencies": currencies_data}
    )


@user_passes_test(lambda u: u.is_superuser)
def add_currency_view(request):
    # Получаем данные через сервис
    currency_choices, short_currencies = currency_exchange_service.get_currency_choices()
    if request.method == "POST":
        form = AddCurrencyForm(request.POST)
        if form.is_valid():
            currency_name = form.cleaned_data["currency_name"]
            amount_in_cash = form.cleaned_data["amount_in_cash"]
            # Проверяем валидность валюты
            if currency_name not in currency_choices and currency_name not in short_currencies:
                messages.error(request, "Валюта отсутствует в перечне валют Нацбанка")
                return redirect("exchange:add_currency")
            # Конвертируем сокращенное название в полное
            currency_name = short_currencies.get(currency_name, currency_name)
            # Добавляем валюту в базу через сервис
            if currency_exchange_service.add_currency_to_cash(currency_name, amount_in_cash):
                messages.success(request, f"Валюта {currency_name} успешно добавлена в кассу!")
                return redirect("exchange:cash_reserves")
            else:
                messages.error(request, "Валюта уже есть в базе")
        else:
            messages.error(request, "Пожалуйста, заполните все поля.")
    else:
        form = AddCurrencyForm()

    return render(request, "exchange/add_currency_to_cash.html", {"form": form})


@user_passes_test(lambda u: u.is_superuser)
def delete_currencies_view(request):
    # Получаем список выбранных валют из POST-запроса
    currency_ids = request.POST.getlist("currency_ids")
    if currency_ids:
        try:
            currency_exchange_service.delete_currencies(currency_ids)
            messages.success(request, "Выбранные валюты успешно удалены.")
        except IntegrityError:
            messages.error(
                request, "Нельзя удалить валюты, которые участвовали в обмене."
            )
            return redirect("exchange:cash_reserves")
    else:
        messages.warning(request, "Вы не выбрали ни одной валюты для удаления.")

    return redirect("exchange:cash_reserves")


@user_passes_test(lambda u: u.is_superuser)
def delete_rate(request):
    # Проверяем права администратора
    rates_ids = request.POST.getlist("rates_ids")
    currency_exchange_service.delete_rates(rates_ids)
    if rates_ids:
        messages.success(request, "Выбранные курсы успешно удалены.")
    else:
        messages.warning(request, "Вы не выбрали ни одного курса для удаления.")

    return redirect("exchange:rates")


@user_passes_test(lambda u: u.is_superuser)
def delete_exchange(request):
    # Получаем список выбранных валют из POST-запроса
    transactions_ids = request.POST.getlist("transactions_ids")
    if transactions_ids:
        currency_exchange_service.delete_exchange_transactions(transactions_ids)
    else:
        messages.warning(request, "Вы не выбрали ни одной транзакции.")

    return redirect("exchange:exchange_history")
