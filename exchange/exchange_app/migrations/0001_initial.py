# exchange/migrations/0001_initial.py

from django.db import migrations, connection


def create_exchange_tables(apps, schema_editor):
    with connection.cursor() as cursor:
        cursor.execute("""
            CREATE TABLE cash_reserves (
                currency_id SERIAL PRIMARY KEY,
                currency_name VARCHAR(40) UNIQUE NOT NULL,
                amount_in_cash NUMERIC(15, 2) DEFAULT 0.00
    )
        """)
        cursor.execute("""
            INSERT INTO cash_reserves (currency_name, amount_in_cash)
            VALUES (%s, %s)
        """, ['Белорусский рубль', 1])
        cursor.execute("""
            CREATE TABLE exchange_rates (
                rate_id SERIAL PRIMARY KEY,
                currency_id INTEGER,
                rate_to_base NUMERIC(10, 4) NOT NULL,
                rate_date DATE NOT NULL DEFAULT CURRENT_DATE,
                FOREIGN KEY (currency_id) REFERENCES cash_reserves(currency_id) ON DELETE CASCADE
            )
        """)

        cursor.execute("""
            CREATE TABLE exchange_transactions (
                transaction_id SERIAL PRIMARY KEY,
                operator_id INTEGER  NOT NULL,
                currency_from_id INTEGER ,
                currency_to_id INTEGER ,
                amount NUMERIC(15, 2) NOT NULL,
                exchanged_amount NUMERIC(15, 2) NOT NULL,
                change_in_base NUMERIC(15, 2) NOT NULL,
                transaction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (operator_id) REFERENCES auth_user(id),
                FOREIGN KEY (currency_from_id) REFERENCES cash_reserves(currency_id) ON DELETE CASCADE,
                FOREIGN KEY (currency_to_id) REFERENCES cash_reserves(currency_id) ON DELETE CASCADE
            )
        """)

        cursor.execute("""
            CREATE OR REPLACE FUNCTION update_cash_after_exchange() RETURNS TRIGGER AS $$
    DECLARE
        v_amount_in_cash NUMERIC(15, 2);
    BEGIN
        IF NEW.currency_from_id != 1 THEN
            SELECT amount_in_cash INTO v_amount_in_cash
            FROM cash_reserves
            WHERE currency_id = NEW.currency_from_id;
        
            UPDATE cash_reserves
            SET amount_in_cash = amount_in_cash + NEW.amount
            WHERE currency_id = NEW.currency_from_id;
        END IF;

        IF NEW.currency_to_id != 1 THEN
            SELECT amount_in_cash INTO v_amount_in_cash
            FROM cash_reserves
            WHERE currency_id = NEW.currency_to_id;
        
            UPDATE cash_reserves
            SET amount_in_cash = amount_in_cash - NEW.exchanged_amount
            WHERE currency_id = NEW.currency_to_id;
        END IF;

        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
        """)
        cursor.execute("""
            CREATE TRIGGER update_cash_after_exchange
            AFTER INSERT ON exchange_transactions
            FOR EACH ROW
            EXECUTE FUNCTION update_cash_after_exchange();
        """)


def reverse_create_exchange_tables(apps, schema_editor):
    with connection.cursor() as cursor:
        cursor.execute("DROP TRIGGER update_cash_after_exchange")
        cursor.execute("DROP TABLE exchange_transactions")
        cursor.execute("DROP TABLE exchange_rates")


class Migration(migrations.Migration):
    dependencies = []

    operations = [
        migrations.RunPython(create_exchange_tables, reverse_create_exchange_tables),
    ]
