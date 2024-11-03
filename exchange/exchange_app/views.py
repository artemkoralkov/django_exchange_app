# exchange/views.py
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.utils import timezone

from .models import ExchangeRate, ExchangeTransaction
from .forms import ExchangeForm
from django.contrib import messages


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
    rates = ExchangeRate.objects.all()
    return render(request, 'exchange/rates.html', {'rates': rates})


@login_required(login_url='/exchange/accounts/login/')
def exchange_view(request):
    if request.user.is_staff:
        messages.error(request, "Только операторы могут обменивать валюту.")
        return redirect('exchange:rates')
    if request.method == 'POST':
        form = ExchangeForm(request.POST)
        if form.is_valid():
            currency_from = form.cleaned_data['currency_from']
            currency_to = form.cleaned_data['currency_to']
            amount = form.cleaned_data['amount']
            today = timezone.now().date()

            # Ищем последний курс для выбранных валют
            exchange_rate = ExchangeRate.objects.filter(
                currency_from=currency_from,
                currency_to=currency_to,
                date__lte=today
            ).order_by('-date').first()

            if exchange_rate:
                # Прямой курс найден
                exchanged_amount = round(amount * exchange_rate.rate, 2)
            else:
                # Пробуем найти обратный курс
                reverse_rate = ExchangeRate.objects.filter(
                    currency_from=currency_to,
                    currency_to=currency_from,
                    date__lte=today
                ).order_by('-date').first()

                if reverse_rate:
                    # Обратный курс найден
                    exchanged_amount = round(amount / reverse_rate.rate, 2)
                else:
                    # Курс не найден
                    messages.error(request, "Курс обмена не найден.")
                    return redirect('exchange:exchange_currency')

            # Создание записи о транзакции
            ExchangeTransaction.objects.create(
                operator=request.user,
                currency_from=currency_from,
                currency_to=currency_to,
                amount=amount,
                exchanged_amount=exchanged_amount
            )

            # Уведомление об успешном обмене
            messages.success(request, f"Вы обменяли {amount} {currency_from} на {exchanged_amount} {currency_to}.")
            return redirect('exchange:rates')
    else:
        form = ExchangeForm()

    return render(request, 'exchange/exchange.html', {'form': form})


@login_required(login_url='/exchange/accounts/login/')
def transaction_history_view(request):
    transactions = ExchangeTransaction.objects.filter(operator=request.user)
    return render(request, 'exchange/history.html', {'transactions': transactions})
