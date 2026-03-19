"""Локализация и fallback-переводы интерфейса бота."""
from gettext import GNUTranslations, NullTranslations, translation

# Резервные переводы (используются, если нет .mo файлов)
FALLBACK_TRANSLATIONS: dict[str, dict[str, str]] = {
    "ru": {
        "\U0001F44B Hello, {user_name}! \n\nI'm Aida. I help you manage a restaurant or a restaurant chain remotely for Dodo Brands and make the right management decisions.": "\U0001F44B Привет, {user_name}! \n\nЯ - Aida. Помогаю удаленно управлять рестораном или сетью ресторанов Dodo Brands и принимать правильные управленческие решения.",
        "App settings: \U0001F9BE": "Настройки приложения: \U0001F9BE",
        "Choose an action:": "Выбери интересующее действие:",
        "Choose a subscription:": "Выбери подписку:",
        "Stops:": "Стопы:",
        "Select up to 4 categories in stock balances:": "Выберите до 4-х отслеживаемых категорий в складских остатках:",
        "Choose locations:": "Выбери заведения:",
        "Select notifications (reports) you want to disable.": "Выберите уведомления(отчёты), которые хотите отключить.",
        "Choose language:": "Выберите язык:",
        "Language updated.": "Язык обновлен.",
        "Manage the bot with /start \U0001F44B": "Управляйте ботом по команде /start \U0001F44B",
        "Collecting data \U0001F4C0\nPlease wait": "Идет сбор данных \U0001F4C0\nПодождите, пожалуйста",
        "Your locations data has been updated. \U0001F4F1": "Обновлены данные ваших заведений. \U0001F4F1",
        "\u23F1\uFE0F Report/notifications: <b>\"{label}\"</b>:\n\n": "\u23F1\uFE0F Отчет/уведомления: <b>\"{label}\"</b>:\n\n",
        "\U00002705 You enabled the following locations: \n{items}\n\n": "\U00002705 Вы подключили следующие заведения: \n{items}\n\n",
        "\U0000274C You disabled the following locations:\n{items}": "\U0000274C Вы отключили следующие заведения:\n{items}",
        "You did not enable any locations.": "Вы не подключили ни одного заведения.",
        "No changes. Current locations:\n{items}": "Изменений нет. Текущие заведения:\n{items}",
        "You disabled notifications <b>{label}</b>": "Вы отключили уведомления <b>{label}</b>",
        "\U0001F50A Notifications": "\U0001F50A Уведомления",
        "\U0001F4D1 Reports": "\U0001F4D1 Отчеты",
        "\U0001F4AC Live data": "\U0001F4AC Оперативные данные",
        "\U0001F6E0 Settings": "\U0001F6E0 Настройки",
        "\u274E Close menu": "\u274E Закрыть меню",
        "\U0001F4F1 Manage app": "\U0001F4F1 Управлять приложением",
        "\U0001F4DA Knowledge base": "\U0001F4DA База знаний",
        "\U0001F519 Back": "\U0001F519 Назад",
        "\U0001F310 Change language": "\U0001F310 Сменить язык",
        "\U0001F1F7\U0001F1FA Russian": "\U0001F1F7\U0001F1FA Русский",
        "\U0001F1EC\U0001F1E7 English": "\U0001F1EC\U0001F1E7 Английский",
        "\U0001F4CC Subscribe all": "\U0001F4CC Подписаться на все",
        "\U0001F4CC Unsubscribe all": "\U0001F4CC Отписаться от всех",
        "\U0001F4CA Current metrics": "\U0001F4CA Текущие метрики",
        "\U0001F4B9 Network revenue": "\U0001F4B9 Выручка по сети",
        "\U0001F69A Large stock balances": "\U0001F69A Большие складские остатки",
        "\U0001F389 Birthdays": "\U0001F389 Дни рождения",
        "\U0001F6AB Stops": "\U0001F6AB Стопы",
        "\U0001F4E9 Tickets": "\U0001F4E9 Тикеты",
        "\U0001F5C2 Tenure/Anniversary": "\U0001F5C2 Стаж/Годовщина",
        "\U0001F17E Cancellations": "\U0001F17E Отказы",
        "\U0001F9EA Defect": "\U0001F9EA Брак",
        "\U0001F699 Courier reports": "\U0001F699 Отчеты по курьерам",
        "\U0001F957 Restaurant reports": "\U0001F957 Отчеты по ресторану",
        "\U0001F4C9 Metrics": "\U0001F4C9 Метрики",
        "\U0001F69A Stock balances": "\U0001F69A Складские остатки",
        "\U0001F5D1 Write-offs": "\U0001F5D1 Списания",
        "\U0001F3E0 Restaurant stops": "\U0001F3E0 Стопы пиццерии",
        "\U0001F9C0 Key ingredient stops": "\U0001F9C0 Cтопы ключевых ингредиентов",
        "\U0001F355 Ingredient stops": "\U0001F355 Стопы ингредиентов",
        "\U0001F6A7 Sector stops": "\U0001F6A7 Стопы секторов",
        "\U0001F44C Apply": "\U0001F44C Применить",
        "\U0001F345 Ingredients": "\U0001F345 Ингредиенты",
        "\U0001F364 Semi-finished products": "\U0001F364 Полуфабрикаты",
        "\U0001F355 Finished products": "\U0001F355 Продукты",
        "\U0001F961 Packaging": "\U0001F961 Упаковка",
        "\U0001F3E2 Stops by sales channels": "\U0001F3E2 Стопы по каналам продаж",
        "\U0001F9C0 Stops by ingredients": "\U0001F9C0 Стопы по ингредиентам",
        "\U0001F355 Stops by key ingredients": "\U0001F355 Стопы по ключевым ингредиентам",
        "\U0001F5FE Stops by sectors": "\U0001F5FE Стопы по секторам",
        "\U0001F4D8 Customer tickets": "\U0001F4D8 Тикеты клиентов",
        "\U0001F69B Courier reports": "\U0001F69B Отчеты по курьерам",
        "\U0001F17E Cancelled orders": "\U0001F17E Отмененные заказы",
        "\U0001F373 Restaurant delays": "\U0001F373 Опоздания в ресторане",
        "\U0001F4B5 Network revenue": "\U0001F4B5 Выручка по сети",
        "\U0001F69A Stock balances": "\U0001F69A Складские остатки",
        "\U0001F9FE Staff info": "\U0001F9FE Информация о сотрудниках",
    },
}


class DictTranslations(NullTranslations):
    """Мини-реализация gettext на базе словаря."""
    def __init__(self, mapping: dict[str, str]):
        """Сохраняет словарь fallback-переводов."""
        super().__init__()
        self._mapping = mapping

    def gettext(self, message: str) -> str:  # type: ignore[override]
        """Возвращает перевод из словаря или исходную строку."""
        return self._mapping.get(message, message)

LOCALIZATIONS_DIR = 'services/localizations'


def _normalize_language(language: str) -> str:
    """Нормализует язык до короткого кода вроде ru/en."""
    # Приводим язык к виду "ru"/"en" без региональных суффиксов
    lang = (language or "ru").strip().lower()
    if "-" in lang:
        lang = lang.split("-", 1)[0]
    if "_" in lang:
        lang = lang.split("_", 1)[0]
    return lang or "ru"


def setup_i18n(language: str = 'ru') -> GNUTranslations | NullTranslations:
    """Возвращает объект переводов для выбранного языка."""
    lang = _normalize_language(language)
    try:
        locales = translation(
            domain='messages',           # Имя домена (файла .po/.mo)
            localedir=LOCALIZATIONS_DIR, # Путь к папке locales
            languages=[lang],        # Язык (например, "ru", "en")
        )
        locales.install()
        return locales
    except FileNotFoundError:
        # Если нет файлов локализации — используем словарь или отдаём исходный текст
        mapping = FALLBACK_TRANSLATIONS.get(lang)
        if mapping:
            return DictTranslations(mapping)
        return NullTranslations()
