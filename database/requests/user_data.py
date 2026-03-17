"""Backward-compatible wrapper. Use database.requests.users/settings instead."""

from database.requests.users import get_user_context as _get_user_context
from database.requests.settings import get_user_settings as _get_user_settings


class UserData:
    def __init__(self, tg_user, session):
        self.tg_user = tg_user
        self.session = session

    async def get_user_data(self):
        return await _get_user_context(self.session, self.tg_user)

    async def get_user_settings(self):
        return await _get_user_settings(self.session, self.tg_user)
