from gettext import GNUTranslations, NullTranslations, translation

LOCALIZATIONS_DIR = 'services/localizations'


def setup_i18n(language: str = 'ru') -> GNUTranslations | NullTranslations:
    """
    Функция для получения функции перевода. Подробнее нужно читать про локализацию с gettext и i18n.

    :param language: Двух символьное обозначение нужного языка.
    :return: Функция для перевода текста.
    """
    try:
        locales = translation(
            domain='messages',           # Имя домена (файла .po/.mo)
            localedir=LOCALIZATIONS_DIR, # Путь к папке locales
            languages=[language],        # Язык (например, "ru", "en")
        )
        locales.install()
        return locales
    except FileNotFoundError:
        return NullTranslations()
