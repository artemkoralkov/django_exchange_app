# exchange/services.py
from decimal import Decimal

import requests
from django.db import connection
from django.utils import timezone


class CurrencyExchangeService:

    @staticmethod
    def get_rate_from_api(currency_name):
        rates = (
                requests.get("https://api.nbrb.by/exrates/rates?periodicity=0").json()
                + requests.get("https://api.nbrb.by/exrates/rates?periodicity=1").json()
        )
        currency_id_from_api = find_currency_id_by_name(rates, currency_name)

    @staticmethod
    def get_rates():
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT rate_id, currency_name, rate_to_base, rate_date, amount_in_cash
                FROM exchange_rates er
                JOIN cash_reserves cr ON er.currency_id = cr.currency_id
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
            cursor.execute("SELECT currency_id, currency_name, amount_in_cash FROM cash_reserves")
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
    def get_currency_name(currency_id):
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
            return cursor.fetchone()[0]

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
    def delete_currencies(currency_ids):
        with connection.cursor() as cursor:
            # Преобразуем список валют в строку, пригодную для SQL-запроса
            placeholders = ", ".join(["%s"] * len(currency_ids))
            cursor.execute(
                f"DELETE FROM cash_reserves WHERE currency_id IN ({placeholders})",
                currency_ids,
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

    def perform_exchange(self, currency_from_id, currency_to_id, amount):
        rate_from = self.get_exchange_rate(currency_from_id) or (1,)
        rate_to = self.get_exchange_rate(currency_to_id) or (1,)
        amount_in_base = amount * Decimal(rate_from[0])
        exchanged_amount = int(amount_in_base / Decimal(rate_to[0]))
        change_in_base = amount_in_base - (exchanged_amount * Decimal(rate_to[0]))

        return exchanged_amount, change_in_base

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


def find_currency_id_by_name(currencies, currency_name):
    for currency in currencies:
        if currency.get("Cur_Name") == currency_name:
            return currency.get("Cur_ID")
    return None
