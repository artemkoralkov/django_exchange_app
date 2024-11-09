def find_currency_id_by_name(currencies, currency_name):
    for currency in currencies:
        if currency.get("Cur_Name") == currency_name:
            return currency.get("Cur_ID")
    return None
