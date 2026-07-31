import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from bot.dialogs.getters import MenuGetters, _deduplicate_unit_payloads
from bot.dialogs.helpers import DialogContext
from bot.dialogs.models import ContextDTO, UnitDTO
from database.requests.users import _deduplicate_units_by_uuid


class UnitDeduplicationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.duplicate_units = [
            {
                "uuid": "unit-1",
                "name": "Белгород-1",
                "country": "RU",
                "account_id": 10,
            },
            {
                "uuid": "unit-1",
                "name": "Белгород-1",
                "country": "RU",
                "account_id": 20,
            },
            {
                "uuid": "unit-2",
                "name": "Белгород-1",
                "country": "RU",
                "account_id": 20,
            },
        ]

    def assert_unique_units(self, units: list[dict]) -> None:
        self.assertEqual(["unit-1", "unit-2"], [unit["uuid"] for unit in units])
        self.assertEqual(10, units[0]["account_id"])

    def test_database_context_keeps_first_access_path_per_uuid(self) -> None:
        self.assert_unique_units(_deduplicate_units_by_uuid(self.duplicate_units))

    def test_cached_dialog_context_is_deduplicated(self) -> None:
        self.assert_unique_units(_deduplicate_unit_payloads(self.duplicate_units))


class UnitsDataTests(unittest.IsolatedAsyncioTestCase):
    async def test_units_data_deduplicates_cached_context_and_metadata(self) -> None:
        context = ContextDTO(
            units=[
                UnitDTO(
                    uuid="unit-1",
                    name="Белгород-1",
                    country="RU",
                    account_id=10,
                ),
                UnitDTO(
                    uuid="unit-1",
                    name="Белгород-1",
                    country="RU",
                    account_id=20,
                ),
                UnitDTO(
                    uuid="unit-2",
                    name="Белгород-1",
                    country="RU",
                    account_id=20,
                ),
            ]
        )
        dialog_manager = SimpleNamespace(
            dialog_data={},
            middleware_data={},
        )

        with (
            patch.object(DialogContext, "load_ctx", new=AsyncMock(return_value=context)),
            patch.object(MenuGetters, "_translator", return_value=lambda text: text),
            patch.object(MenuGetters, "_texts", return_value={}),
        ):
            data = await MenuGetters.units_data(dialog_manager)

        self.assertEqual(["unit-1", "unit-2"], [unit["uuid"] for unit in data["units"]])
        self.assertEqual(
            {
                "unit-1": {"name": "Белгород-1", "account_id": 10},
                "unit-2": {"name": "Белгород-1", "account_id": 20},
            },
            dialog_manager.dialog_data["units_meta"],
        )


if __name__ == "__main__":
    unittest.main()
