from typing import Any

from aiogram_dialog import DialogManager

from bot.dialogs.models import ContextDTO, ContextValidator


class DialogContext:
    """Вспомогательные методы для доступа к контексту диалога."""
    @staticmethod
    def get_dialog_value(manager: DialogManager, key: str, default: Any) -> Any:
        # Гарантируем наличие значения в dialog_data
        value = manager.dialog_data.get(key, default)
        manager.dialog_data[key] = value
        return value

    @staticmethod
    async def load_ctx(manager: DialogManager) -> ContextDTO:
        # Пробуем получить контекст из FSM, dialog_data или start_data
        state = manager.middleware_data.get("state")
        if state:
            data = await state.get_data()
            ctx = data.get("ctx")
            if ctx:
                return ContextValidator.validate(ctx)
        ctx = manager.dialog_data.get("ctx")
        if ctx:
            return ContextValidator.validate(ctx)
        start_data = getattr(manager, "start_data", None)
        if start_data:
            return ContextValidator.validate(start_data.get("ctx"))
        return ContextDTO()

    @staticmethod
    async def get_units_by_id(manager: DialogManager) -> dict[str, str]:
        # Словарь uuid -> имя заведения (кешируется в dialog_data)
        units_by_id = manager.dialog_data.get("units_by_id")
        if units_by_id:
            return units_by_id
        ctx = await DialogContext.load_ctx(manager)
        units_by_id = {}
        for unit in ctx.units:
            units_by_id[unit.uuid] = unit.name
        manager.dialog_data["units_by_id"] = units_by_id
        return units_by_id
