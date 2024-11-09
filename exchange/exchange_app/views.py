# exchange/views.py
from decimal import Decimal

from django.core.exceptions import PermissionDenied
from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils import timezone
from django.contrib import messages
from django.db import connection
import requests

# from .models import ExchangeRate, ExchangeTransaction
from .forms import ExchangeForm, AddExchangeRateForm, AddExchangeRateFromAPIForm, AddCurrencyToCashForm


def index(request):
    return render(request, 'exchange/index.html')


def test(request):
    with connection.cursor() as cursor:
        a = cursor.execute('select currency_name, currency_id from cash_reserves').fetchall()
    return render(request, 'exchange/test.html', {'t': a})


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
def delete_rate(request, rate_id):
    # Проверяем права администратора
    if not request.user.is_superuser:
        return HttpResponseForbidden("Access denied.")

    with connection.cursor() as cursor:
        cursor.execute("DELETE FROM exchange_rates WHERE rate_id = %s", [rate_id])

    return redirect('exchange:rates')


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
    # Проверяем, является ли пользователь администратором
    if not request.user.is_superuser:
        raise PermissionDenied("You are not allowed to perform this action.")
    if request.method == 'POST':
        form = AddExchangeRateForm(request.POST)
        if form.is_valid():
            currency_name = form.cleaned_data['currency_name']
            rate_to_base = form.cleaned_data['rate_to_base']
            rate_date = form.cleaned_data['rate_date'].strftime('%Y-%m-%d')
            amount_in_cash = form.cleaned_data['amount_in_cash']
            # Создаем запись в базе данных с использованием SQL
            with connection.cursor() as cursor:
                # Получаем currency_id из cash_reserves
                cursor.execute("SELECT currency_id FROM cash_reserves WHERE currency_name = %s", [currency_name])
                currency_record = cursor.fetchone()
                if currency_record:
                    currency_id = currency_record[0]
                    cursor.execute("""
                            INSERT INTO exchange_rates (currency_id, rate_to_base, rate_date)
                            VALUES (%s, %s, TO_DATE(%s, 'YYYY-MM-DD'))
                        """, [currency_id, rate_to_base, rate_date])
                    cursor.execute("""
                                UPDATE cash_reserves
                                SET amount_in_cash = amount_in_cash + %s
                                WHERE currency_id = %s
                            """, [amount_in_cash, currency_id])
                else:
                    cursor.execute("""
                                INSERT INTO cash_reserves (currency_name, amount_in_cash)
                                VALUES (%s, %s)
                            """, [currency_name, amount_in_cash])
                    cursor.execute("SELECT currency_id FROM cash_reserves WHERE currency_name = %s", [currency_name])
                    new_currency_id = cursor.fetchone()[0]
                    cursor.execute("""
                            INSERT INTO exchange_rates (currency_id, rate_to_base, rate_date)
                            VALUES (%s, %s, TO_DATE(%s, 'YYYY-MM-DD'))
                        """, [new_currency_id, rate_to_base, rate_date])

            messages.success(request, f"Курс для {currency_name} успешно добавлен!")
            return redirect('exchange:rates')  # или на нужную вам страницу
        else:
            messages.error(request, "Пожалуйста, заполните все поля.")
    else:
        form = AddExchangeRateForm()

    return render(request, 'exchange/add_exchange_rate.html', {'form': form})


@user_passes_test(lambda u: u.is_superuser)
def add_exchange_rate_from_api(request):
    if request.method == 'POST':
        form = AddExchangeRateFromAPIForm(request.POST)
        if form.is_valid():
            currency_name = form.cleaned_data['currency_name']
            amount_in_cash = form.cleaned_data['amount_in_cash']
            currency_from_api = requests.get(f'https://api.nbrb.by/exrates/rates/{currency_name}').json()
            rate_to_base = (Decimal(str(currency_from_api['Cur_OfficialRate'] / currency_from_api['Cur_Scale']))
                            .quantize(Decimal('1.000')))
            currency_name = requests.get(f'https://api.nbrb.by/exrates/currencies/{currency_name}').json()['Cur_Name']
            if rate_to_base is None:
                messages.error(request, f"Не удалось загрузить курс для {currency_name} через API.")
                return render(request, 'exchange/add_exchange_rate_from_api.html', {'form': form})

            # Обновляем или добавляем курс в базу данных
            with connection.cursor() as cursor:
                # Получаем currency_id из cash_reserves
                cursor.execute("SELECT currency_id FROM cash_reserves WHERE currency_name = %s", [currency_name])
                currency_record = cursor.fetchone()
                if currency_record:
                    currency_id = currency_record[0]
                    cursor.execute("""
                                       INSERT INTO exchange_rates (currency_id, rate_to_base)
                                       VALUES (%s, %s)
                                   """, [currency_id, rate_to_base])
                    cursor.execute("""
                                           UPDATE cash_reserves
                                           SET amount_in_cash = amount_in_cash + %s
                                           WHERE currency_id = %s
                                       """, [amount_in_cash, currency_id])
                else:
                    cursor.execute("""
                                           INSERT INTO cash_reserves (currency_name, amount_in_cash)
                                           VALUES (%s, %s)
                                       """, [currency_name, amount_in_cash])
                    cursor.execute("SELECT currency_id FROM cash_reserves WHERE currency_name = %s", [currency_name])
                    new_currency_id = cursor.fetchone()[0]
                    cursor.execute("""
                                       INSERT INTO exchange_rates (currency_id, rate_to_base)
                                       VALUES (%s, %s)
                                   """, [new_currency_id, rate_to_base])

            messages.success(request, f"Курс для {currency_name} успешно добавлен/обновлен.")
            return redirect('exchange:rates')
    else:
        form = AddExchangeRateFromAPIForm()

    return render(request, 'exchange/add_exchange_rate_from_api.html', {'form': form})


@login_required(login_url='/exchange/accounts/login/')
def exchange_view(request):
    # Только операторы могут выполнять обмен
    if request.user.is_superuser:
        messages.error(request, "Только операторы могут обменивать валюту.")
        return redirect('exchange:rates')

    if request.method == 'POST':
        form = ExchangeForm(request.POST)
        if form.is_valid():
            currency_from_id = form.cleaned_data['currency_from']
            currency_to_id = form.cleaned_data['currency_to']
            amount = form.cleaned_data['amount']
            amount_to_get = form.cleaned_data['amount_to_get']
            today = timezone.now().date()
            print(currency_from_id, currency_to_id)
            with connection.cursor() as cursor:
                cursor.execute("SELECT amount_in_cash FROM cash_reserves WHERE currency_id = %s",
                               [currency_from_id])
                available_cash = cursor.fetchone()[0]
                rate_from = (1,) if currency_from_id == '0' else None
                if not rate_from:
                    cursor.execute("""
                          SELECT rate_to_base
                          FROM exchange_rates
                          WHERE currency_id = %s
                          ORDER BY rate_date DESC
                          FETCH FIRST 1 ROW ONLY
                      """, [currency_from_id])
                    rate_from = cursor.fetchone()
                rate_to = (1,) if currency_to_id == '0' else None
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
            print(1, rate_from, rate_to, currency_from_id, currency_to_id)
            if rate_from and rate_to:
                rate_to_base_from = rate_from[0]
                rate_to_base_to = rate_to[0]
                amount_in_base = amount * rate_to_base_from
                with connection.cursor() as cursor:
                    currency_from = 'Белорусский рубль' if currency_from_id == 0 else None
                    if not currency_from:
                        cursor.execute("""
                               SELECT currency_name
                               FROM cash_reserves
                               WHERE currency_id = %s
                           """, [currency_from_id])
                        currency_from = cursor.fetchone()[0]
                    currency_to = 'Белорусский рубль' if currency_to_id == 0 else None
                    if not currency_to:
                        cursor.execute("""
                               SELECT currency_name
                               FROM cash_reserves
                               WHERE currency_id = %s
                           """, [currency_to_id])
                        currency_to = cursor.fetchone()[0]
                if amount_to_get:
                    if amount_to_get >= available_cash:
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
                    if exchanged_amount > available_cash:
                        messages.error(request,
                                       f"Недостаточно средств в кассе для обмена на {currency_to}. Доступно: {available_cash}.")
                        return redirect('exchange:exchange_currency')

                # Запись транзакции
                with connection.cursor() as cursor:
                    print(['dsad', currency_from_id, currency_to_id])
                    cursor.execute("""INSERT INTO exchange_transactions (operator_id, currency_from_id, 
                    currency_to_id, amount, exchanged_amount, change_in_base,  transaction_date) VALUES (%s, %s, %s, 
                    %s, %s, %s, TO_DATE(%s, 'YYYY-MM-DD'))
                    """,
                   [request.user.id, currency_from_id, currency_to_id, amount,
                    exchanged_amount, change_in_base, today.strftime('%Y-%m-%d')])

                # Уведомление об успешном обмене

                messages.success(request, f"Вы обменяли {amount} {currency_from} на {exchanged_amount} {currency_to}. "
                                          f"Сдача: {change_in_base:.2f} в базовой валюте.")
                return redirect('exchange:rates')
            else:
                messages.error(request, "Курс обмена не найден.")
                return redirect('exchange:exchange_currency')
    else:
        form = ExchangeForm()

    return render(request, 'exchange/exchange.html', {'form': form})


@login_required(login_url='/exchange/accounts/login/')
def transaction_history_view(request):
    is_admin = request.user.is_superuser
    # Если пользователь - администратор, показываем все транзакции
    if is_admin:
        with connection.cursor() as cursor:
            cursor.execute("""SELECT  transaction_date, (SELECT currency_name FROM cash_reserves WHERE currency_id = 
            currency_from_id) currency_from_name, (SELECT currency_name FROM cash_reserves WHERE currency_id = 
            currency_to_id) currency_to_name, amount, exchanged_amount, change_in_base, username
            FROM exchange_transactions t JOIN auth_user u ON t.operator_id = u.id ORDER BY transaction_date DESC
            """)
            transactions = cursor.fetchall()
    else:
        # Если пользователь - оператор, показываем только его транзакции
        user_id = request.user.id
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT  transaction_date, (SELECT currency_name FROM cash_reserves WHERE currency_id = 
                currency_from_id) currency_from_name, (SELECT currency_name FROM cash_reserves WHERE currency_id = 
                currency_to_id) currency_to_name, amount, exchanged_amount, change_in_base
                FROM exchange_transactions 
                WHERE operator_id = %s
                ORDER BY transaction_date DESC
            """, [user_id])
            transactions = cursor.fetchall()
    context = {
        'transactions': transactions,
        'is_admin': is_admin,
    }
    return render(request, 'exchange/history.html', context)


def add_currency_to_cash(request):
    # Проверяем, является ли пользователь администратором
    if not request.user.is_superuser:
        raise PermissionDenied("Вы не имеете прав для выполнения этого действия.")

    if request.method == 'POST':
        form = AddCurrencyToCashForm(request.POST)
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
            return redirect('exchange:rates')  # Перенаправляем на страницу с кассой
        else:
            messages.error(request, "Пожалуйста, заполните все поля.")
    else:
        form = AddCurrencyToCashForm()

    return render(request, 'exchange/add_currency_to_cash.html', {'form': form})
