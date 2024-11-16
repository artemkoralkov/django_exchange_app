from datetime import datetime
from decimal import Decimal

import requests
from django.db import connection
from django.utils import timezone


class CurrencyExchangeService:
    def __init__(self):
        self.api_url = "https://api.nbrb.by/exrates"

    @staticmethod
    def apply_markup(rate, markup):
        """Добавляет наценку в процентах к курсу."""
        if markup:
            return (rate * (1 + Decimal(markup) / 100)).quantize(Decimal("1.000"))
        return rate

    @staticmethod
    def find_currency_id_by_name(currencies, currency_name):
        for currency in currencies:
            if currency.get("Cur_Abbreviation") == currency_name:
                return currency.get("Cur_ID")
        return None

    def get_rate_from_api(self, currency_name):

        # Получаем все доступные валюты
        currencies_from_api = self.get_all_currencies_from_api()
        current_date = datetime.now().date()

        # Фильтруем валюты по актуальной дате
        valid_currencies = [
            cur for cur in currencies_from_api
            if datetime.strptime(cur.get("Cur_DateEnd"), "%Y-%m-%dT%H:%M:%S").date() >= current_date
        ]
        currency_id_from_api = next(
            (cur["Cur_ID"] for cur in valid_currencies if cur.get("Cur_Name") == currency_name), None
        )
        if not currency_id_from_api:
            return None, "Такой валюты нет в API"

        # Запрашиваем курс конкретной валюты
        response = requests.get(f"{self.api_url}/rates/{currency_id_from_api}")
        if response.status_code == 200:
            data = response.json()
            rate_to_base = Decimal(data["Cur_OfficialRate"] / data["Cur_Scale"]).quantize(Decimal("1.000"))
            return rate_to_base, None

        return None, "Ошибка при запросе к API."

    def get_all_currencies_from_api(self):
        """Получение списка валют из API"""
        response = requests.get(f"{self.api_url}/currencies")
        if response.status_code == 200:
            return response.json()
        return []

    def get_currency_choices(self):
        """
        Получение списка валют и их аббревиатур.
        Возвращает:
        - currency_choices: Полные названия валют.
        - short_currencies: Словарь аббревиатур и полных названий.
        """
        currencies_from_api = self.get_all_currencies_from_api()

        # Фильтруем валюты по Cur_DateEnd
        today = timezone.now().date()
        valid_currencies = [
            cur for cur in currencies_from_api
            if datetime.strptime(cur["Cur_DateEnd"], "%Y-%m-%dT%H:%M:%S").date() >= today
        ]

        # Формируем выборки
        currency_choices = {cur["Cur_Name"] for cur in valid_currencies}
        short_currencies = {cur["Cur_Abbreviation"]: cur["Cur_Name"] for cur in valid_currencies}

        return currency_choices, short_currencies

    @staticmethod
    def currency_exists(currency_name):
        """Проверка, существует ли валюта в базе."""
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(1) FROM cash_reserves WHERE currency_name = %s",
                [currency_name]
            )
            return cursor.fetchone()[0] > 0

    def add_currency_to_cash(self, currency_name, amount_in_cash):
        """Добавление валюты в базу."""
        if self.currency_exists(currency_name):
            return False
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO cash_reserves (currency_name, amount_in_cash)
                VALUES (%s, %s)
                """,
                [currency_name, amount_in_cash]
            )
        return True

    @staticmethod
    def add_exchange_rate(currency_id, rate_to_base, rate_date):
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO exchange_rates (currency_id, rate_to_base, rate_date)
                VALUES (%s, %s, TO_DATE(%s, 'YYYY-MM-DD'))
                """,
                [currency_id, rate_to_base, rate_date],
            )

    @staticmethod
    def get_rates():
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT rate_id, currency_name, rate_to_base, rate_date, amount_in_cash
                FROM exchange_rates er
                JOIN cash_reserves cr ON er.currency_id = cr.currency_id WHERE is_archived != 1
            """
            )
            rates = cursor.fetchall()

        # Формируем список словарей для удобства использования в шаблоне
        return [
            {
                "rate_id": rate[0],
                "currency_name": rate[1],
                "rate_to_base": rate[2],
                "rate_date": rate[3],
                "amount_in_cash": rate[4],
            }
            for rate in rates
        ]

    @staticmethod
    def get_currency():
        with connection.cursor() as cursor:
            cursor.execute("SELECT currency_id, currency_name, amount_in_cash, is_archived FROM cash_reserves")
            return cursor.fetchall()

    @staticmethod
    def get_exchange_rate(currency_id):
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT rate_to_base
                FROM exchange_rates
                WHERE currency_id = %s
                ORDER BY rate_date DESC
                FETCH FIRST 1 ROW ONLY
            """,
                [currency_id],
            )
            return cursor.fetchone()

    @staticmethod
    def record_transaction(operator_id, currency_from_id, currency_to_id, amount, exchanged_amount,
                           change_in_base):
        """Запись транзакции в базу данных."""
        today = timezone.now().date().strftime("%Y-%m-%d")
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO exchange_transactions (
                    operator_id, currency_from_id, currency_to_id, amount, exchanged_amount, change_in_base, transaction_date
                ) VALUES (%s, %s, %s, %s, %s, %s, TO_DATE(%s, 'YYYY-MM-DD'))
                """,
                [operator_id, currency_from_id, currency_to_id, amount, exchanged_amount, change_in_base, today],
            )

    @staticmethod
    def get_currency_name(currency_id):
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT currency_name
                FROM cash_reserves
                WHERE currency_id = %s
                FETCH FIRST 1 ROW ONLY
            """,
                [currency_id],
            )
            return cursor.fetchone()[0]

    def calculate_exchange(self, currency_from_id, currency_to_id, amount, amount_to_get):

        # Получение курсов валют
        rate_from = 1 if currency_from_id == "1" else self.get_exchange_rate(currency_from_id)[0]
        rate_to = 1 if currency_to_id == "1" else self.get_exchange_rate(currency_to_id)[0]

        if not rate_from or not rate_to:
            return None, None, "Курс обмена не найден."

        # Получение доступных средств в кассе
        available_cash = self.get_currency_cash(currency_to_id)

        # Расчёты
        amount_in_base = amount * rate_from
        exchanged_amount = 0
        change_in_base = 0

        if amount_to_get:
            # Проверка наличия средств в кассе для фиксированного количества
            if amount_to_get > available_cash and currency_to_id != "1":
                return None, None, (
                    f"Недостаточно средств в кассе для обмена на {self.get_currency_name(currency_to_id)}. "
                    f"Запрашиваемая сумма: {amount_to_get}, доступно: {available_cash}."
                )
            exchanged_amount = amount_to_get
            if currency_to_id != "1":
                change_in_base = amount_in_base - exchanged_amount * rate_to
        else:
            # Автоматический расчёт
            exchanged_amount = int(amount_in_base / rate_to)
            if currency_to_id != "1":
                change_in_base = amount_in_base - exchanged_amount * rate_to

        # Если покупаем базовую валюту, сдача отсутствует
        if currency_to_id == "1":
            exchanged_amount += change_in_base
            change_in_base = 0

        # Проверка достаточности средств в кассе
        if exchanged_amount > available_cash and currency_to_id != "1":
            return None, None, (
                f"Недостаточно средств в кассе для обмена на {self.get_currency_name(currency_to_id)}. "
                f"Доступно: {available_cash}."
            )

        return exchanged_amount, change_in_base, None

    @staticmethod
    def get_currency_cash(currency_id):
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT amount_in_cash FROM cash_reserves WHERE currency_id = %s",
                [currency_id],
            )
            return cursor.fetchone()[0]

    @staticmethod
    def update_currency_cash(amount_in_cash, currency_name):
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE cash_reserves
                SET amount_in_cash = amount_in_cash + %s
                WHERE currency_name = %s
            """,
                [amount_in_cash, currency_name],
            )

    @staticmethod
    def get_transactions(user_id=None):
        with connection.cursor() as cursor:
            if user_id:
                cursor.execute(
                    """
                    SELECT  transaction_id, transaction_date, cr_from.currency_name  currency_from_name,
                    cr_to.currency_name currency_to_name, amount, exchanged_amount, change_in_base
                    FROM exchange_transactions t
                    JOIN 
                        cash_reserves cr_from ON t.currency_from_id = cr_from.currency_id
                    JOIN
                        cash_reserves cr_to ON t.currency_to_id = cr_to.currency_id
                    WHERE operator_id = %s
                    ORDER BY transaction_date DESC
                    """,
                    [user_id],
                )

            else:
                cursor.execute(
                    """
                    SELECT  transaction_id, transaction_date, cr_from.currency_name  currency_from_name,
                    cr_to.currency_name currency_to_name, amount, exchanged_amount, change_in_base, username
                    FROM exchange_transactions t
                    JOIN 
                        cash_reserves cr_from ON t.currency_from_id = cr_from.currency_id
                    JOIN
                        cash_reserves cr_to ON t.currency_to_id = cr_to.currency_id 
                    JOIN 
                        auth_user u ON t.operator_id = u.id 
                    ORDER BY transaction_date DESC """
                )
            return [
                {
                    "transaction_id": t[0],
                    "transaction_date": t[1],
                    "currency_from_name": t[2],
                    "currency_to_name": t[3],
                    "amount": t[4],
                    "exchanged_amount": t[5],
                    "change_in_base": t[6],
                    "username": t[7] if not user_id else None,
                }
                for t in cursor.fetchall()
            ]

    @staticmethod
    def delete_currencies(currency_id):
        with connection.cursor() as cursor:
            # Преобразуем список валют в строку, пригодную для SQL-запроса
            cursor.execute(
                f"DELETE FROM cash_reserves WHERE currency_id = %s",
                [currency_id],
            )

    @staticmethod
    def delete_rates(rates_ids):
        with connection.cursor() as cursor:
            # Преобразуем список валют в строку, пригодную для SQL-запроса
            placeholders = ", ".join(["%s"] * len(rates_ids))
            cursor.execute(
                f"DELETE FROM exchange_rates WHERE rate_id IN ({placeholders})",
                rates_ids,
            )

    @staticmethod
    def delete_exchange_transactions(transactions_ids):
        with connection.cursor() as cursor:
            # Преобразуем список валют в строку, пригодную для SQL-запроса
            placeholders = ", ".join(["%s"] * len(transactions_ids))
            cursor.execute(
                f"DELETE FROM exchange_transactions WHERE transaction_id IN ({placeholders})",
                transactions_ids,
            )

    @staticmethod
    def log_exchange_transaction(
            user_id,
            currency_from_id,
            currency_to_id,
            amount,
            exchanged_amount,
            change_in_base,
    ):
        today = timezone.now().date().strftime("%Y-%m-%d")
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO exchange_transactions (operator_id, currency_from_id, currency_to_id, amount,
                exchanged_amount, change_in_base, transaction_date)
                VALUES (%s, %s, %s, %s, %s, %s, TO_DATE(%s, 'YYYY-MM-DD'))
            """,
                [
                    user_id,
                    currency_from_id,
                    currency_to_id,
                    amount,
                    exchanged_amount,
                    change_in_base,
                    today,
                ],
            )

    @staticmethod
    def archive_currency(currency_id):
        with connection.cursor() as cursor:
            cursor.execute("UPDATE cash_reserves SET is_archived = 1 WHERE currency_id = %s", [currency_id])

    @staticmethod
    def unarchived_currency(currency_id):
        with connection.cursor() as cursor:
            cursor.execute("UPDATE cash_reserves SET is_archived = 0 WHERE currency_id = %s", [currency_id])
