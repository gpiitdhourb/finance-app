# Добавь эти импорты к существующим
from passlib.context import CryptContext  # для хэширования паролей
from jose import JWTError, jwt  # для JWT токенов
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi import Cookie, HTTPException, status
import secrets  # для генерации безопасных ключей
from fastapi import FastAPI, Depends, HTTPException, Request, Query
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, \
    func, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime, timedelta
from typing import Optional, List
from collections import defaultdict
from fastapi.staticfiles import StaticFiles

# ===================== НАСТРОЙКА БАЗЫ ДАННЫХ =====================
SQLALCHEMY_DATABASE_URL = "sqlite:///./finance.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL,
                       connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ===================== МОДЕЛЬ =====================
class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    amount = Column(Float, nullable=False)
    category = Column(String, nullable=False)
    description = Column(String, nullable=True)
    date = Column(DateTime, default=datetime.utcnow)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)


# ===================== МОДЕЛЬ ПОЛЬЗОВАТЕЛЯ =====================
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=True)
    hashed_password = Column(String, nullable=False)
    favorite_animal = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# Создаем таблицы (обновляем, чтобы добавить users)
Base.metadata.create_all(bind=engine)


# Создаем таблицы
Base.metadata.create_all(bind=engine)

# ===================== БЕЗОПАСНОСТЬ =====================

# Секретный ключ для JWT (в реальном проекте храни в .env)
SECRET_KEY = secrets.token_urlsafe(32)  # Генерируем случайный ключ
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 30  # Токен для "запоминания" устройства

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")



def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ===================== БЕЗОПАСНОСТЬ =====================
SECRET_KEY = secrets.token_urlsafe(32)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 30

# Используем pbkdf2_sha256 вместо bcrypt (не требует внешних библиотек)
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


def authenticate_user(db: Session, username: str, password: str):
    user = db.query(User).filter(User.username == username).first()
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user


def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(
        token: Optional[str] = Cookie(None, alias="access_token"),
        db: Session = Depends(get_db)
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Не авторизован",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not token:
        raise credentials_exception

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise credentials_exception
    return user


async def get_current_user_optional(
        token: Optional[str] = Cookie(None, alias="access_token"),
        db: Session = Depends(get_db)
):
    if not token:
        return None

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
    except JWTError:
        return None

    user = db.query(User).filter(User.username == username).first()
    return user

# ===================== ИНИЦИАЛИЗАЦИЯ FASTAPI =====================
app = FastAPI(title="Финансовый учёт")
templates = Jinja2Templates(directory="templates")

# ===================== СТАТИЧЕСКИЕ ФАЙЛЫ =====================
app.mount("/static", StaticFiles(directory="static"), name="static")

# ===================== БАЗОВЫЕ API (были) =====================

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    """Страница входа"""
    return templates.TemplateResponse("login.html", {"request": request})

# GET /api/transactions - добавляем фильтр по пользователю
from datetime import datetime, timedelta, date


# ===================== ЭНДПОИНТ ДЛЯ ТРАНЗАКЦИЙ С ФИЛЬТРАЦИЕЙ =====================
@app.get("/api/transactions")
def get_transactions(
        transaction_type: Optional[str] = Query(None),
        start_date: Optional[str] = Query(None,
                                          description="Дата начала в формате YYYY-MM-DD"),
        end_date: Optional[str] = Query(None,
                                        description="Дата конца в формате YYYY-MM-DD"),
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Получить транзакции с фильтрацией по типу и дате"""
    query = db.query(Transaction).filter(
        Transaction.user_id == current_user.id)

    # Фильтр по типу
    if transaction_type == "income":
        query = query.filter(Transaction.amount > 0)
    elif transaction_type == "expense":
        query = query.filter(Transaction.amount < 0)

    # Фильтр по дате
    if start_date:
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d")
            query = query.filter(Transaction.date >= start)
        except ValueError:
            pass

    if end_date:
        try:
            end = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(
                days=1)  # включаем весь день
            query = query.filter(Transaction.date < end)
        except ValueError:
            pass

    transactions = query.order_by(Transaction.date.desc()).all()
    return transactions


# ===================== ЭНДПОИНТ ДЛЯ СТАТИСТИКИ С ФИЛЬТРАЦИЕЙ ПО ПЕРИОДУ =====================
@app.get("/api/statistics/summary-filtered")
def get_statistics_summary_filtered(
        start_date: Optional[str] = Query(None,
                                          description="Дата начала YYYY-MM-DD"),
        end_date: Optional[str] = Query(None,
                                        description="Дата конца YYYY-MM-DD"),
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Сводная статистика за период"""
    query = db.query(Transaction).filter(
        Transaction.user_id == current_user.id)

    if start_date:
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d")
            query = query.filter(Transaction.date >= start)
        except ValueError:
            pass

    if end_date:
        try:
            end = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
            query = query.filter(Transaction.date < end)
        except ValueError:
            pass

    transactions = query.all()

    total_income = sum(t.amount for t in transactions if t.amount > 0)
    total_expense = sum(t.amount for t in transactions if t.amount < 0)

    return {
        "total_income": total_income,
        "total_expense": abs(total_expense),
        "balance": total_income + total_expense,
        "transaction_count": len(transactions)
    }


# POST /api/transactions
@app.post("/api/transactions")
def add_transaction(
        amount: float,
        category: str,
        description: Optional[str] = "",
        date: Optional[str] = None,  # <-- НОВЫЙ ПАРАМЕТР
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    if amount == 0:
        raise HTTPException(status_code=400,
                            detail="Сумма не может быть равна 0")

    # Обработка даты
    transaction_date = datetime.utcnow()
    if date:
        try:
            transaction_date = datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400,
                                detail="Неверный формат даты. Используйте YYYY-MM-DD")

    new_trans = Transaction(
        amount=amount,
        category=category,
        description=description,
        date=transaction_date,  # <-- ИСПОЛЬЗУЕМ УКАЗАННУЮ ДАТУ
        user_id=current_user.id
    )
    db.add(new_trans)
    db.commit()
    db.refresh(new_trans)
    return {"status": "ok", "transaction": new_trans}


# PUT /api/transactions/{id} - проверяем, что транзакция принадлежит пользователю
@app.put("/api/transactions/{transaction_id}")
def update_transaction(
        transaction_id: int,
        amount: float,
        category: str,
        description: Optional[str] = "",
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    transaction = db.query(Transaction).filter(
        Transaction.id == transaction_id,
        Transaction.user_id == current_user.id  # <-- ПРОВЕРКА
    ).first()
    if not transaction:
        raise HTTPException(status_code=404, detail="Транзакция не найдена")

    transaction.amount = amount
    transaction.category = category
    transaction.description = description

    db.commit()
    db.refresh(transaction)
    return {"status": "ok", "transaction": transaction}


# DELETE /api/transactions/{id} - аналогично
@app.delete("/api/transactions/{transaction_id}")
def delete_transaction(
        transaction_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    transaction = db.query(Transaction).filter(
        Transaction.id == transaction_id,
        Transaction.user_id == current_user.id
    ).first()
    if not transaction:
        raise HTTPException(status_code=404, detail="Транзакция не найдена")

    db.delete(transaction)
    db.commit()
    return {"status": "ok"}


# Все остальные эндпоинты статистики тоже защищаем
@app.get("/api/balance")
def get_balance(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    transactions = db.query(Transaction).filter(
        Transaction.user_id == current_user.id).all()
    balance = sum(t.amount for t in transactions)
    return {"balance": balance}


@app.get("/api/statistics/summary")
def get_statistics_summary(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    transactions = db.query(Transaction).filter(
        Transaction.user_id == current_user.id).all()
    total_income = sum(t.amount for t in transactions if t.amount > 0)
    total_expense = sum(t.amount for t in transactions if t.amount < 0)
    return {
        "total_income": total_income,
        "total_expense": abs(total_expense),
        "balance": total_income + total_expense,
        "transaction_count": len(transactions)
    }


@app.get("/api/statistics/by-category")
def get_statistics_by_category(
        transaction_type: Optional[str] = Query(None),
        start_date: Optional[str] = Query(None,
                                          description="Дата начала YYYY-MM-DD"),
        end_date: Optional[str] = Query(None,
                                        description="Дата конца YYYY-MM-DD"),
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Группировка по категориям с фильтрацией по дате"""
    query = db.query(Transaction).filter(
        Transaction.user_id == current_user.id)

    # Фильтр по типу
    if transaction_type == "income":
        query = query.filter(Transaction.amount > 0)
    elif transaction_type == "expense":
        query = query.filter(Transaction.amount < 0)

    # Фильтр по дате
    if start_date:
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d")
            query = query.filter(Transaction.date >= start)
        except ValueError:
            pass

    if end_date:
        try:
            end = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
            query = query.filter(Transaction.date < end)
        except ValueError:
            pass

    transactions = query.all()

    # Группируем по категориям
    categories = defaultdict(float)
    for t in transactions:
        categories[t.category] += abs(t.amount)

    result = [{"category": cat, "amount": amount} for cat, amount in
              categories.items()]
    result.sort(key=lambda x: x["amount"], reverse=True)
    return result


@app.get("/api/statistics/daily")
def get_daily_statistics(
        start_date: Optional[str] = Query(None,
                                          description="Дата начала YYYY-MM-DD"),
        end_date: Optional[str] = Query(None,
                                        description="Дата конца YYYY-MM-DD"),
        days: int = Query(30,
                          description="Количество дней (если не указаны start_date и end_date)"),
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Статистика по дням с фильтрацией по дате"""
    query = db.query(Transaction).filter(
        Transaction.user_id == current_user.id)

    # Если указаны start_date и end_date - используем их
    if start_date and end_date:
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d")
            end = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
            query = query.filter(Transaction.date >= start,
                                 Transaction.date < end)
        except ValueError:
            pass
    else:
        # Иначе используем days
        start_date = datetime.utcnow() - timedelta(days=days)
        query = query.filter(Transaction.date >= start_date)

    transactions = query.all()

    # Группируем по дням
    daily_income = defaultdict(float)
    daily_expense = defaultdict(float)

    for t in transactions:
        date_key = t.date.strftime("%Y-%m-%d")
        if t.amount > 0:
            daily_income[date_key] += t.amount
        else:
            daily_expense[date_key] += abs(t.amount)

    # Сортируем по датам
    all_dates = sorted(set(daily_income.keys()) | set(daily_expense.keys()))

    return {
        "dates": all_dates,
        "income": [daily_income.get(d, 0) for d in all_dates],
        "expense": [daily_expense.get(d, 0) for d in all_dates]
    }

# ===================== АУТЕНТИФИКАЦИЯ =====================

@app.post("/api/register")
def register_user(
        username: str,
        password: str,
        email: Optional[str] = None,
        favorite_animal: Optional[str] = None,
        db: Session = Depends(get_db)
):
    """Регистрация нового пользователя"""
    # Проверяем, не занят ли логин
    existing_user = db.query(User).filter(User.username == username).first()
    if existing_user:
        raise HTTPException(status_code=400,
                            detail="Пользователь с таким логином уже существует")

    # Создаем нового пользователя
    hashed_password = get_password_hash(password)
    new_user = User(
        username=username,
        email=email,
        hashed_password=hashed_password,
        favorite_animal=favorite_animal
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {"status": "ok", "message": "Пользователь зарегистрирован"}


@app.post("/api/login")
def login(
        form_data: OAuth2PasswordRequestForm = Depends(),
        remember: bool = Query(False, description="Запомнить устройство"),
        db: Session = Depends(get_db)
):
    """Вход в систему"""
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный логин или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Создаем access токен
    access_token_expires = timedelta(
        days=REFRESH_TOKEN_EXPIRE_DAYS if remember else 1
    )
    access_token = create_access_token(
        data={"sub": user.username},
        expires_delta=access_token_expires
    )

    # Создаем response и устанавливаем куку
    response = {"status": "ok", "username": user.username}

    # Кука будет установлена через параметр response в эндпоинте
    return response, access_token


# Версия login, которая реально устанавливает куку
@app.post("/api/login-with-cookie")
def login_with_cookie(
        form_data: OAuth2PasswordRequestForm = Depends(),
        remember: bool = Query(False, description="Запомнить устройство"),
        db: Session = Depends(get_db)
):
    """Вход с установкой куки"""
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный логин или пароль",
        )

    # Создаем токен
    access_token_expires = timedelta(
        days=REFRESH_TOKEN_EXPIRE_DAYS if remember else 1
    )
    access_token = create_access_token(
        data={"sub": user.username},
        expires_delta=access_token_expires
    )

    # Создаем ответ и устанавливаем куку
    response = {"status": "ok", "username": user.username,
                "message": "Вход выполнен"}

    # Возвращаем объект Response с кукой
    from fastapi.responses import JSONResponse
    resp = JSONResponse(response)
    resp.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,  # Защита от XSS
        max_age=access_token_expires.total_seconds(),
        samesite="lax",
        secure=False  # В production ставь True (HTTPS)
    )
    return resp


@app.post("/api/logout")
def logout():
    """Выход из системы (удаляем куку)"""
    from fastapi.responses import JSONResponse
    resp = JSONResponse({"status": "ok", "message": "Выход выполнен"})
    resp.delete_cookie(key="access_token")
    return resp


# ===================== НОВЫЕ ЭНДПОИНТЫ ДЛЯ ДАШБОРДА =====================

@app.get("/api/statistics/daily-balance")
def get_daily_balance(
        start_date: Optional[str] = Query(None),
        end_date: Optional[str] = Query(None),
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Динамика баланса по дням"""
    query = db.query(Transaction).filter(
        Transaction.user_id == current_user.id)

    if start_date:
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d")
            query = query.filter(Transaction.date >= start)
        except ValueError:
            pass

    if end_date:
        try:
            end = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
            query = query.filter(Transaction.date < end)
        except ValueError:
            pass

    transactions = query.order_by(Transaction.date.asc()).all()

    # Вычисляем накопленный баланс
    daily_balance = {}
    balance = 0
    for t in transactions:
        balance += t.amount
        date_key = t.date.strftime("%Y-%m-%d")
        daily_balance[date_key] = balance

    return {
        "dates": list(daily_balance.keys()),
        "balance": list(daily_balance.values())
    }


@app.get("/api/statistics/monthly-comparison")
def get_monthly_comparison(
        start_date: Optional[str] = Query(None),
        end_date: Optional[str] = Query(None),
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Сравнение доходов и расходов по месяцам"""
    query = db.query(Transaction).filter(
        Transaction.user_id == current_user.id)

    if start_date:
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d")
            query = query.filter(Transaction.date >= start)
        except ValueError:
            pass

    if end_date:
        try:
            end = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
            query = query.filter(Transaction.date < end)
        except ValueError:
            pass

    transactions = query.all()

    monthly_income = defaultdict(float)
    monthly_expense = defaultdict(float)

    for t in transactions:
        month_key = t.date.strftime("%Y-%m")
        if t.amount > 0:
            monthly_income[month_key] += t.amount
        else:
            monthly_expense[month_key] += abs(t.amount)

    all_months = sorted(
        set(monthly_income.keys()) | set(monthly_expense.keys()))

    return {
        "months": all_months,
        "income": [monthly_income.get(m, 0) for m in all_months],
        "expense": [monthly_expense.get(m, 0) for m in all_months]
    }


@app.get("/api/statistics/weekday-analysis")
def get_weekday_analysis(
        start_date: Optional[str] = Query(None),
        end_date: Optional[str] = Query(None),
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Анализ трат по дням недели"""
    query = db.query(Transaction).filter(
        Transaction.user_id == current_user.id)

    if start_date:
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d")
            query = query.filter(Transaction.date >= start)
        except ValueError:
            pass

    if end_date:
        try:
            end = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
            query = query.filter(Transaction.date < end)
        except ValueError:
            pass

    transactions = query.all()

    weekdays = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
    weekday_expense = [0] * 7
    weekday_income = [0] * 7
    weekday_count = [0] * 7

    for t in transactions:
        wd = t.date.weekday()  # 0 = понедельник
        weekday_count[wd] += 1
        if t.amount > 0:
            weekday_income[wd] += t.amount
        else:
            weekday_expense[wd] += abs(t.amount)

    # Средние значения
    avg_expense = [expense / count if count > 0 else 0 for expense, count in
                   zip(weekday_expense, weekday_count)]
    avg_income = [income / count if count > 0 else 0 for income, count in
                  zip(weekday_income, weekday_count)]

    return {
        "weekdays": weekdays,
        "income": avg_income,
        "expense": avg_expense
    }


@app.get("/api/statistics/top-categories")
def get_top_categories(
        transaction_type: str = Query(..., description="income или expense"),
        limit: int = Query(5, description="Количество категорий"),
        start_date: Optional[str] = Query(None),
        end_date: Optional[str] = Query(None),
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Топ N категорий по сумме"""
    query = db.query(Transaction).filter(
        Transaction.user_id == current_user.id)

    if transaction_type == "income":
        query = query.filter(Transaction.amount > 0)
    else:
        query = query.filter(Transaction.amount < 0)

    if start_date:
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d")
            query = query.filter(Transaction.date >= start)
        except ValueError:
            pass

    if end_date:
        try:
            end = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
            query = query.filter(Transaction.date < end)
        except ValueError:
            pass

    transactions = query.all()

    # Группируем и суммируем
    categories = defaultdict(float)
    for t in transactions:
        categories[t.category] += abs(t.amount)

    # Сортируем и берем топ N
    sorted_categories = sorted(categories.items(), key=lambda x: x[1],
                               reverse=True)[:limit]

    return {
        "categories": [item[0] for item in sorted_categories],
        "amounts": [item[1] for item in sorted_categories]
    }


@app.get("/api/statistics/summary-extended")
def get_summary_extended(
        start_date: Optional[str] = Query(None),
        end_date: Optional[str] = Query(None),
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Расширенная сводка с дополнительной аналитикой"""
    query = db.query(Transaction).filter(
        Transaction.user_id == current_user.id)

    if start_date:
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d")
            query = query.filter(Transaction.date >= start)
        except ValueError:
            pass

    if end_date:
        try:
            end = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
            query = query.filter(Transaction.date < end)
        except ValueError:
            pass

    transactions = query.all()

    total_income = sum(t.amount for t in transactions if t.amount > 0)
    total_expense = sum(abs(t.amount) for t in transactions if t.amount < 0)

    # Транзакций в день
    days = 1
    if start_date and end_date:
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d")
            end = datetime.strptime(end_date, "%Y-%m-%d")
            days = (end - start).days + 1
        except ValueError:
            pass

    return {
        "total_income": total_income,
        "total_expense": total_expense,
        "balance": total_income - total_expense,
        "transaction_count": len(transactions),
        "avg_income_per_day": total_income / days if days > 0 else 0,
        "avg_expense_per_day": total_expense / days if days > 0 else 0,
        "days": days
    }


@app.get("/api/me")
def get_me(current_user: User = Depends(get_current_user)):
    """Получить информацию о текущем пользователе"""
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "created_at": current_user.created_at
    }

# ===================== ФРОНТЕНД =====================

@app.get("/", response_class=HTMLResponse)
def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    """Страница с расширенными диаграммами"""
    return templates.TemplateResponse("dashboard.html", {"request": request})