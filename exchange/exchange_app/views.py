# exchange/views.py
from decimal import Decimal

import requests
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import connection, IntegrityError
from django.shortcuts import render, redirect
from django.utils import timezone

from .utils import find_currency_id_by_name

from .forms import ExchangeForm, AddExchangeRateForm, AddCurrencyToCashForm, \
    UserRegisterForm, AddCurrencyForm


def index(request):
    return render(request, 'exchange/index.html')


def login_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('exchange:rates')
        else:
            messages.error(request, "Неправильное имя пользователя или пароль.")
    return render(request, 'exchange/login.html')


def logout_view(request):
    logout(request)
    return redirect('exchange:login')


@login_required(login_url='/exchange/accounts/login/')
def rates_view(request):
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT rate_id, currency_name, rate_to_base, rate_date, amount_in_cash
            FROM exchange_rates er
            JOIN cash_reserves cr ON er.currency_id = cr.currency_id
        """)
        rates = cursor.fetchall()

    # Формируем список словарей для удобства использования в шаблоне
    rates_data = [
        {
            "rate_id": rate[0],
            "currency_name": rate[1],
            "rate_to_base": rate[2],
            "rate_date": rate[3],
            "amount_in_cash": rate[4]
        }
        for rate in rates
    ]

    return render(request, 'exchange/rates.html', {'rates': rates_data})


@user_passes_test(lambda u: u.is_superuser)
def add_exchange_rate(request):
    form = AddExchangeRateForm(request.POST or None)
    with connection.cursor() as cursor:
        cursor.execute("SELECT currency_id, currency_name FROM cash_reserves")
        currency_choices = cursor.fetchall()
        # Преобразуем множество валют в список и создаем выбор валют
    form.fields['currency'].choices = [
        (f"{currency[0]}:{currency[1]}", currency[1]) for currency in currency_choices[1:]
    ]
    if request.method == 'POST':
        if form.is_valid():
            currency_id, currency_name = form.cleaned_data['currency'].split(':')
            rate_date = form.cleaned_data['rate_date'].strftime('%Y-%m-%d')
            use_api = form.cleaned_data['use_api']
            if use_api:
                rates = (requests.get('https://api.nbrb.by/exrates/rates?periodicity=0').json()
                         + requests.get('https://api.nbrb.by/exrates/rates?periodicity=1').json())
                currency_id_from_api = find_currency_id_by_name(rates, currency_name)

                if not currency_id_from_api:
                    messages.error(request, "Такой валюты нет в API")
                    return redirect('exchange:add_exchange_rate')

                response = requests.get(f'https://api.nbrb.by/exrates/rates/{currency_id_from_api}')

                if response.status_code == 200:
                    rate_to_base = response.json().get("Cur_OfficialRate")
                    cur_scale = response.json().get("Cur_Scale")
                    rate_date = timezone.now().date().strftime('%Y-%m-%d')
                    rate_to_base = Decimal(rate_to_base / cur_scale).quantize(Decimal('1.000'))
                    if not rate_to_base:
                        messages.error(request, "Не удалось получить курс из API.")
                        return redirect('exchange:add_exchange_rate')
                else:
                    messages.error(request, "Ошибка при запросе к API.")
                    return redirect('exchange:add_exchange_rate')
            else:
                rate_to_base = form.cleaned_data['rate_to_base']
            if not rate_to_base:
                messages.error(request, "Введите курс валюты или добавьте его из API.")
                return redirect('exchange:add_exchange_rate')
            with connection.cursor() as cursor:
                cursor.execute("""
                        INSERT INTO exchange_rates (currency_id, rate_to_base, rate_date)
                        VALUES (%s, %s, TO_DATE(%s, 'YYYY-MM-DD'))
                    """, [currency_id, rate_to_base, rate_date])

            messages.success(request, f"Курс для {currency_name} успешно добавлен!")
            return redirect('exchange:rates')  # или на нужную вам страницу
        else:
            messages.error(request, "Пожалуйста, заполните все поля.")

    return render(request, 'exchange/add_exchange_rate.html', {'form': form})


@login_required(login_url='/exchange/accounts/login/')
def exchange_view(request):
    # Только операторы могут выполнять обмен
    if request.user.is_superuser:
        messages.error(request, "Только операторы могут обменивать валюту.")
        return redirect('exchange:rates')
    form = ExchangeForm(request.POST or None)
    with connection.cursor() as cursor:
        cursor.execute("SELECT currency_id, currency_name FROM cash_reserves")
        currency_choices = cursor.fetchall()
    # Преобразуем множество валют в список и создаем выбор валют
    form.fields['currency_from'].choices = currency_choices
    form.fields['currency_to'].choices = currency_choices
    if request.method == 'POST':
        if form.is_valid():
            currency_from_id = form.cleaned_data['currency_from']
            currency_to_id = form.cleaned_data['currency_to']
            amount = form.cleaned_data['amount']
            amount_to_get = form.cleaned_data['amount_to_get']
            today = timezone.now().date()
            with connection.cursor() as cursor:
                cursor.execute("SELECT amount_in_cash FROM cash_reserves WHERE currency_id = %s",
                               [currency_to_id])
                available_cash = cursor.fetchone()[0]
                rate_from = (1,) if currency_from_id == '1' else None
                if not rate_from:
                    cursor.execute("""
                          SELECT rate_to_base
                          FROM exchange_rates
                          WHERE currency_id = %s
                          ORDER BY rate_date DESC
                          FETCH FIRST 1 ROW ONLY
                      """, [currency_from_id])
                    rate_from = cursor.fetchone()
                rate_to = (1,) if currency_to_id == '1' else None
                if not rate_to:
                    cursor.execute("""
                          SELECT rate_to_base
                          FROM exchange_rates 
                          WHERE currency_id = %s
                          ORDER BY rate_date DESC
                          FETCH FIRST 1 ROW ONLY
                      """, [currency_to_id])
                    rate_to = cursor.fetchone()
            # Проверка наличия курсов
            if rate_from and rate_to:
                rate_to_base_from = rate_from[0]
                rate_to_base_to = rate_to[0]
                amount_in_base = amount * rate_to_base_from
                with connection.cursor() as cursor:
                    currency_from = 'Белорусский рубль' if currency_from_id == '1' else None
                    if not currency_from:
                        cursor.execute("""
                               SELECT currency_name
                               FROM cash_reserves
                               WHERE currency_id = %s
                           """, [currency_from_id])
                        currency_from = cursor.fetchone()[0]
                    currency_to = 'Белорусский рубль' if currency_to_id == '1' else None
                    if not currency_to:
                        cursor.execute("""
                               SELECT currency_name
                               FROM cash_reserves
                               WHERE currency_id = %s
                           """, [currency_to_id])
                        currency_to = cursor.fetchone()[0]
                if amount_to_get:
                    if amount_to_get >= available_cash and currency_from_id != '1':
                        messages.error(request,
                                       f"Недостаточно средств в кассе для обмена на {currency_to}. "
                                       f"Вы запрашиваете {amount_to_get}, а доступно только {available_cash}.")
                        return redirect('exchange:exchange_currency')
                    else:
                        exchanged_amount = amount_to_get
                        change_in_base = amount_in_base - amount_to_get * rate_to_base_to
                else:

                    exchanged_amount = int(amount_in_base / rate_to_base_to)
                    change_in_base = amount_in_base - (exchanged_amount * rate_to_base_to)

                    # Проверка наличия достаточных средств в кассе
                if exchanged_amount > available_cash and currency_to_id != '1':
                    messages.error(request,
                                   f"Недостаточно средств в кассе для обмена на {currency_to}."
                                   f"Доступно: {available_cash}.")
                    return redirect('exchange:exchange_currency')

                # Запись транзакции
                if rate_to_base_to == 1:
                    exchanged_amount = exchanged_amount + change_in_base
                    change_in_base = 0
                with connection.cursor() as cursor:
                    cursor.execute("""INSERT INTO exchange_transactions (operator_id, currency_from_id, 
                    currency_to_id, amount, exchanged_amount, change_in_base,  transaction_date) VALUES (%s, %s, %s, 
                    %s, %s, %s, TO_DATE(%s, 'YYYY-MM-DD'))
                    """,
                                   [request.user.id, currency_from_id, currency_to_id, amount,
                                    exchanged_amount, change_in_base, today.strftime('%Y-%m-%d')])

                # Уведомление об успешном обмене
                change_string = f"Сдача: {change_in_base:.2f} в базовой валюте." if change_in_base != 0 else ''
                messages.success(request,
                                 f"Вы обменяли {amount} {currency_from} на {exchanged_amount:.2f} {currency_to}. "
                                 + change_string)
                return redirect('exchange:rates')
            else:
                messages.error(request, "Курс обмена не найден.")
                return redirect('exchange:exchange_currency')

    return render(request, 'exchange/exchange.html', {'form': form})


@login_required(login_url='/exchange/accounts/login/')
def transaction_history_view(request):
    is_admin = request.user.is_superuser
    # Если пользователь - администратор, показываем все транзакции
    if is_admin:
        with connection.cursor() as cursor:
            cursor.execute("""SELECT  transaction_id, transaction_date, (SELECT currency_name FROM cash_reserves 
            WHERE currency_id = currency_from_id) currency_from_name, (SELECT currency_name FROM cash_reserves WHERE 
            currency_id = currency_to_id) currency_to_name, amount, exchanged_amount, change_in_base, username FROM 
            exchange_transactions t JOIN auth_user u ON t.operator_id = u.id ORDER BY transaction_date DESC """)
            transactions = [{
                'transaction_id': t[0],
                'transaction_date': t[1],
                'currency_from_name': t[2],
                'currency_to_name': t[3],
                'amount': t[4],
                'exchanged_amount': t[5],
                'change_in_base': t[6],
                'username': t[7],
            } for t in cursor.fetchall()]
    else:
        # Если пользователь - оператор, показываем только его транзакции
        user_id = request.user.id
        with (connection.cursor() as cursor):
            cursor.execute("""
                SELECT  transaction_id, transaction_date, (SELECT currency_name FROM cash_reserves WHERE currency_id = 
                currency_from_id) currency_from_name, (SELECT currency_name FROM cash_reserves WHERE currency_id = 
                currency_to_id) currency_to_name, amount, exchanged_amount, change_in_base
                FROM exchange_transactions 
                WHERE operator_id = %s
                ORDER BY transaction_date DESC
            """, [user_id])
            transactions = [{
                'transaction_id': t[0],
                'transaction_date': t[1],
                'currency_from_name': t[2],
                'currency_to_name': t[3],
                'amount': t[4],
                'exchanged_amount': t[5],
                'change_in_base': t[6],
            } for t in cursor.fetchall()]
    context = {
        'transactions': transactions,
        'is_admin': is_admin,
    }
    return render(request, 'exchange/history.html', context)


@user_passes_test(lambda u: u.is_superuser)
def add_currency_to_cash(request):
    form = AddCurrencyToCashForm(request.POST or None)

    with connection.cursor() as cursor:
        cursor.execute("SELECT currency_name FROM cash_reserves")
        currencies = cursor.fetchall()
        currency_choices = [(currency[0], currency[0]) for currency in currencies[1:]]

    form.fields['currency_name'].choices = currency_choices

    if request.method == 'POST':

        if form.is_valid():
            currency_name = form.cleaned_data['currency_name']  # Получаем выбранную валюту
            amount_in_cash = form.cleaned_data['amount_in_cash']

            with connection.cursor() as cursor:
                cursor.execute("""
                    UPDATE cash_reserves
                    SET amount_in_cash = amount_in_cash + %s
                    WHERE currency_name = %s
                """, [amount_in_cash, currency_name])

            messages.success(request, f"Валюта {currency_name} успешно добавлена/обновлена в кассе!")
            return redirect('exchange:cash_reserves')  # Перенаправляем на страницу с кассой
        else:
            messages.error(request, "Пожалуйста, заполните все поля.")

    return render(request, 'exchange/add_currency_to_cash.html', {'form': form})


def register_view(request):
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('exchange:index')
    else:
        form = UserRegisterForm()
    return render(request, 'exchange/register.html', {'form': form})


@user_passes_test(lambda u: u.is_superuser)
def cash_reserves_view(request):
    with connection.cursor() as cursor:
        cursor.execute("SELECT currency_id, currency_name, amount_in_cash FROM cash_reserves")
        currencies = cursor.fetchall()
        currencies_data = [
            {
                "currency_id": currency[0],
                "currency_name": currency[1],
                "amount_in_cash": currency[2]
            }
            for currency in currencies[1:]
        ]

    return render(request, 'exchange/cash_reserves.html', {'currencies': currencies_data})


@user_passes_test(lambda u: u.is_superuser)
def add_currency_view(request):
    currencies_from_api = requests.get('https://api.nbrb.by/exrates/currencies').json()
    currencies = [cur['Cur_Name'] for cur in currencies_from_api]
    short_currencies = {cur['Cur_Abbreviation']: cur['Cur_Name'] for cur in currencies_from_api}
    if request.method == 'POST':
        form = AddCurrencyForm(request.POST)
        if form.is_valid():
            currency_name = form.cleaned_data['currency_name']  # Получаем выбранную валюту
            amount_in_cash = form.cleaned_data['amount_in_cash']
            if currency_name not in (currencies + short_currencies.keys()):
                messages.error(request, "Валюта отсутствует в перечне валют Нацбанка")
                return redirect('exchange:add_currency')
            if currency_name in short_currencies.keys():
                currency_name = short_currencies[currency_name]
            try:
                with connection.cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO cash_reserves (currency_name, amount_in_cash)
                        VALUES (%s, %s)
                    """, [currency_name, amount_in_cash])

                messages.success(request, f"Валюта {currency_name} успешно добавлена в кассу!")
                return redirect('exchange:cash_reserves')  # Перенаправляем на страницу с кассой
            except IntegrityError:
                messages.error(request, "Валюта уже есть в базе")
                return redirect('exchange:add_currency')
        else:
            messages.error(request, "Пожалуйста, заполните все поля.")
    else:
        form = AddCurrencyForm()

    return render(request, 'exchange/add_currency_to_cash.html', {'form': form})


@user_passes_test(lambda u: u.is_superuser)
def delete_currencies_view(request):
    # Получаем список выбранных валют из POST-запроса
    currency_ids = request.POST.getlist('currency_ids')

    if currency_ids:
        try:
            with connection.cursor() as cursor:
                # Преобразуем список валют в строку, пригодную для SQL-запроса
                placeholders = ', '.join(['%s'] * len(currency_ids))
                cursor.execute(f"DELETE FROM cash_reserves WHERE currency_id IN ({placeholders})", currency_ids)
            messages.success(request, "Выбранные валюты успешно удалены.")
        except IntegrityError:
            messages.error(request, "Нельзя удалить валюты, которые участвовали в обмене.")
            return redirect('exchange:cash_reserves')
    else:
        messages.warning(request, "Вы не выбрали ни одной валюты для удаления.")

    return redirect('exchange:cash_reserves')


@user_passes_test(lambda u: u.is_superuser)
def delete_rate(request):
    # Проверяем права администратора
    rates_ids = request.POST.getlist('rates_ids')

    if rates_ids:
        with connection.cursor() as cursor:
            # Преобразуем список валют в строку, пригодную для SQL-запроса
            placeholders = ', '.join(['%s'] * len(rates_ids))
            cursor.execute(f"DELETE FROM exchange_rates WHERE rate_id IN ({placeholders})", rates_ids)
        messages.success(request, "Выбранные курсы успешно удалены.")
    else:
        messages.warning(request, "Вы не выбрали ни одного курса для удаления.")

    return redirect('exchange:rates')


@user_passes_test(lambda u: u.is_superuser)
def delete_currencies_view(request):
    # Получаем список выбранных валют из POST-запроса
    currency_ids = request.POST.getlist('currency_ids')

    if currency_ids:
        try:
            with connection.cursor() as cursor:
                # Преобразуем список валют в строку, пригодную для SQL-запроса
                placeholders = ', '.join(['%s'] * len(currency_ids))
                cursor.execute(f"DELETE FROM cash_reserves WHERE currency_id IN ({placeholders})", currency_ids)
            messages.success(request, "Выбранные валюты успешно удалены.")
        except IntegrityError:
            messages.error(request, "Нельзя удалить валюты, которые участвовали в обмене.")
            return redirect('exchange:cash_reserves')
    else:
        messages.warning(request, "Вы не выбрали ни одной валюты для удаления.")

    return redirect('exchange:cash_reserves')


@user_passes_test(lambda u: u.is_superuser)
def delete_exchange(request):
    # Получаем список выбранных валют из POST-запроса
    transactions_ids = request.POST.getlist('transactions_ids')
    if transactions_ids:
        with connection.cursor() as cursor:
            # Преобразуем список валют в строку, пригодную для SQL-запроса
            placeholders = ', '.join(['%s'] * len(transactions_ids))
            cursor.execute(f"DELETE FROM exchange_transactions WHERE transaction_id IN ({placeholders})",
                           transactions_ids)
    else:
        messages.warning(request, "Вы не выбрали ни одной транзакции.")
    
    return redirect('exchange:exchange_history')
