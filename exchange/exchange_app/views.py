# exchange/views.py
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
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
    if request.method == 'POST':
        form = ExchangeForm(request.POST)
        if form.is_valid():
            currency_from = form.cleaned_data['currency_from']
            currency_to = form.cleaned_data['currency_to']
            amount = form.cleaned_data['amount']

            try:
                rate = ExchangeRate.objects.get(currency_from=currency_from, currency_to=currency_to)
                exchanged_amount = amount * rate.rate
                ExchangeTransaction.objects.create(
                    operator=request.user,
                    currency_from=currency_from,
                    currency_to=currency_to,
                    amount=amount,
                    exchanged_amount=exchanged_amount
                )
                messages.success(request, f"Вы обменяли {amount} {currency_from} на {exchanged_amount} {currency_to}.")
                return redirect('exchange:rates')
            except ExchangeRate.DoesNotExist:
                messages.error(request, "Курс обмена не найден.")
    else:
        form = ExchangeForm()

    return render(request, 'exchange/exchange.html', {'form': form})


@login_required(login_url='/exchange/accounts/login/')
def transaction_history_view(request):
    transactions = ExchangeTransaction.objects.filter(operator=request.user)
    return render(request, 'exchange/history.html', {'transactions': transactions})
