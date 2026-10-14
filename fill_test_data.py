"""
Генерирует ~1000 реалистичных тестовых записей в CRM.

Запуск (из папки mini_crm):
    python fill_test_data.py
"""

import random
import sys
from datetime import datetime, timedelta

sys.path.insert(0, ".")

from backend.database import CRMDatabase

# ---------------------------------------------------------------------------
# Данные
# ---------------------------------------------------------------------------

FIRST_NAMES = ["Алексей", "Дмитрий", "Иван", "Сергей", "Андрей", "Михаил", "Николай",
               "Александр", "Виктор", "Евгений", "Ольга", "Наталья", "Татьяна", "Марина",
               "Елена", "Анна", "Ирина", "Светлана", "Юлия", "Екатерина"]

LAST_NAMES = ["Иванов", "Петров", "Сидоров", "Козлов", "Новиков", "Морозов", "Волков",
              "Соколов", "Кузнецов", "Попов", "Лебедев", "Смирнов", "Зайцев", "Орлов"]

COMPANIES = ["ООО РемСтрой", "ИП Техника", "АО МегаПром", "Завод Юг", "СервисДом",
             "КотельПлюс", "АкваТех", "СтройМонтаж", "ЭнергоГрупп", "ПромБаза",
             "ДачаСервис", "ВодоМастер", "ФильтрПро", "БетонМикс", "АгроХолдинг"]

CITIES = ["Москва", "Санкт-Петербург", "Краснодар", "Ростов-на-Дону", "Казань",
          "Екатеринбург", "Новосибирск", "Нижний Новгород", "Воронеж", "Самара",
          "Подмосковье", "Тула", "Рязань", "Владимир", "Калуга"]

PRODUCTS = ["Умягчитель FSF-0844", "Умягчитель FSF-1044", "Комбинированный FSF-1035",
            "Фильтр обезжелезивания", "Обратный осмос RO-5", "Дозирующий насос PKX",
            "Реагент для промывки", "Соль таблетированная 25кг", "Картридж SL-BB",
            "Установка под ключ (2 этажа)", "Сервисное обслуживание"]

TASK_TITLES = ["Позвонить клиенту", "Отправить коммерческое предложение",
               "Выехать на замер", "Согласовать договор", "Контрольный звонок",
               "Проверить оплату", "Назначить монтаж", "Отправить счёт",
               "Уточнить анализ воды", "Согласовать дату установки"]

DEAL_TITLES = ["Поставка фильтра", "Установка системы водоподготовки",
               "Сервисное обслуживание", "Замена картриджей",
               "Монтаж под ключ", "Подбор оборудования", "Комплектация 2 этажа"]

CLIENT_STATUSES = ["lead"] * 5 + ["active"] * 3 + ["churned"]
DEAL_STAGES = ["new"] * 3 + ["negotiation"] * 2 + ["won"] * 3 + ["lost"]
TASK_STATUSES = ["open"] * 4 + ["in_progress"] * 2 + ["done"] * 3
PRIORITIES = ["low", "medium", "medium", "high"]


def rand_email(first, last):
    domains = ["gmail.com", "mail.ru", "yandex.ru", "bk.ru", "inbox.ru"]
    return f"{first.lower()}.{last.lower()}{random.randint(1, 999)}@{random.choice(domains)}"


def rand_phone():
    return f"+7{random.randint(900, 999)}{random.randint(1000000, 9999999)}"


def rand_date_past(days=365):
    return datetime.utcnow() - timedelta(days=random.randint(0, days))


def rand_date_future(days=60):
    return datetime.utcnow() + timedelta(days=random.randint(1, days))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    db = CRMDatabase(db_url="sqlite:///data/crm.db")

    print("Создаю клиентов...")
    client_ids = []
    used_emails = set()

    for i in range(350):
        first = random.choice(FIRST_NAMES)
        last = random.choice(LAST_NAMES)
        email = rand_email(first, last)
        while email in used_emails:
            email = rand_email(first, last)
        used_emails.add(email)

        client = db.create_client(
            name=f"{last} {first}",
            email=email,
            phone=rand_phone(),
            company=random.choice(COMPANIES) if random.random() > 0.3 else None,
            city=random.choice(CITIES),
            status=random.choice(CLIENT_STATUSES),
            notes=f"Источник: {random.choice(['Директ', 'Сайт', 'Рекомендация', 'Звонок'])}" if random.random() > 0.5 else None,
        )
        client_ids.append(client.id)

    print(f"Создано клиентов: {len(client_ids)}")

    print("Создаю сделки...")
    deal_count = 0
    for cid in client_ids:
        n_deals = random.choices([0, 1, 2, 3], weights=[20, 50, 20, 10])[0]
        for _ in range(n_deals):
            stage = random.choice(DEAL_STAGES)
            db.create_deal(
                client_id=cid,
                title=random.choice(DEAL_TITLES),
                amount=round(random.uniform(5000, 180000), 2),
                stage=stage,
                product=random.choice(PRODUCTS),
                notes=f"Скидка {random.choice([0, 5, 10, 15])}%" if random.random() > 0.6 else None,
                closed_at=rand_date_past(180) if stage in ("won", "lost") else None,
            )
            deal_count += 1

    print(f"Создано сделок: {deal_count}")

    print("Создаю задачи...")
    task_count = 0
    for cid in client_ids:
        n_tasks = random.choices([0, 1, 2, 3, 4], weights=[15, 40, 25, 15, 5])[0]
        for _ in range(n_tasks):
            status = random.choice(TASK_STATUSES)
            db.create_task(
                client_id=cid,
                title=random.choice(TASK_TITLES),
                description=None,
                priority=random.choice(PRIORITIES),
                status=status,
                due_date=rand_date_future() if status != "done" else rand_date_past(30),
            )
            task_count += 1

    print(f"Создано задач: {task_count}")

    stats = db.get_stats()
    print("\n--- Итого в базе ---")
    for k, v in stats.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
