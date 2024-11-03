# Обменник

**Обменник** — это веб-приложение на Django, которое эмулирует работу пункта обмена валют. Проект позволяет пользователям с разными ролями управлять курсами валют и осуществлять операции обмена.

## Функционал

### Роли пользователей
- **Администратор**:
  - Добавляет и редактирует курсы валют.
  - Просматривает отчёты по всем операциям обмена валют.
- **Оператор**:
  - Просматривает актуальные курсы валют.
  - Выполняет операции обмена валют.
  - Просматривает историю своих операций за сессию.

### Основные функции
- **Добавление курсов валют**: Администратор может добавлять курсы валют с указанием даты, валюты исходной и целевой, а также курса обмена.
- **Обмен валют**: Оператор может выполнить обмен, указав валюту, сумму и желаемую валюту обмена. Программа выберет актуальный курс и произведет расчет. Если прямого курса обмена нет, будет использован обратный курс.
- **Просмотр истории операций**: Оператор может просмотреть свои предыдущие обмены в рамках текущей сессии.
- **Журнал операций**: Каждый обмен фиксируется с указанием оператора, времени и деталей обмена.

### Использование
- **Админка** доступна по адресу:  `/admin`.
- **Основные функции обмена валют:** доступны операторам после входа в систему.
### Основные страницы ###
- `/exchange/rates/` — Просмотр текущих курсов валют.
- `/exchange/exchange_currency/` — Страница для обмена валют.
- `/exchange/history/` — История операций оператора.
## Примеры использования
- **Обмен валюты:** Оператор может выбрать валюты для обмена и ввести сумму, после чего приложение автоматически рассчитает и выведет результат обмена.
- **Администрирование:** Админ может добавлять и редактировать курсы валют в админке, а также просматривать историю операций по всем датам и валютам.
