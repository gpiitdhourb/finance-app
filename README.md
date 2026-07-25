# Финансовый учёт

Веб-приложение для управления личными финансами с возможностью:

- Добавление доходов и расходов
- Категоризация транзакций с цветовой маркировкой
- Фильтрация по периоду (неделя, месяц, год)
- Визуализация статистики в виде диаграмм
- Аутентификация с запоминанием устройства
- Дашборд с аналитикой

## Технологии

- **Backend**: FastAPI, SQLAlchemy, SQLite
- **Frontend**: HTML, CSS, JavaScript, Chart.js
- **Аутентификация**: JWT с хранением в cookies

## Установка и запуск

1. Клонируйте репозиторий:
```bash
git clone https://github.com/ваш-username/finance-app.git
cd finance-app
````
2. Создайте виртуальное окружение:

```bash
python -m venv venv
source venv/bin/activate  # для Mac/Linux # или venv\Scripts\activate  # для Windows
```

3. Установите зависимости:

```bash
pip install -r requirements.txt
```

4. Запустите приложение:
```bash
uvicorn main:app --reload
```
Откройте в браузере: http://127.0.0.1:8000

