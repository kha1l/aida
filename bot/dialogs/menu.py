from aiogram_dialog import Dialog

from bot.dialogs.windows import MenuWindows


class MenuDialog:
    """Сборка всех окон меню в один Dialog."""
    @staticmethod
    def build() -> Dialog:
        return Dialog(
            MenuWindows.main(),
            MenuWindows.settings(),
            MenuWindows.operation(),
            MenuWindows.notice(),
            MenuWindows.reports(),
            MenuWindows.stops(),
            MenuWindows.stocks(),
            MenuWindows.units(),
            MenuWindows.language(),
        )


menu_dialog = MenuDialog.build()
