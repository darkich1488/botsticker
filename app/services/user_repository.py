from __future__ import annotations

import threading

from app.models.pack_result import PackCreationResult
from app.models.user import UserProfile


class InMemoryUserRepository:
    def __init__(self, admin_user_ids: set[int] | None = None) -> None:
        self._lock = threading.Lock()
        self._users: dict[int, UserProfile] = {}
        self._admin_user_ids = set(admin_user_ids or set())

    def _get_or_create_unlocked(self, user_id: int) -> UserProfile:
        profile = self._users.get(user_id)
        if profile is None:
            profile = UserProfile(user_id=user_id)
            self._users[user_id] = profile
        return profile

    def get_or_create(self, user_id: int) -> UserProfile:
        with self._lock:
            return self._get_or_create_unlocked(user_id)

    def get_balance(self, user_id: int) -> float:
        return self.get_or_create(user_id).balance

    def add_balance(self, user_id: int, amount: float) -> float:
        with self._lock:
            profile = self._get_or_create_unlocked(user_id)
            profile.balance = round(profile.balance + amount, 2)
            return profile.balance

    def is_admin(self, user_id: int) -> bool:
        return user_id in self._admin_user_ids

    def deduct_balance(self, user_id: int, amount: float) -> bool:
        if self.is_admin(user_id):
            return True
        with self._lock:
            profile = self._get_or_create_unlocked(user_id)
            if profile.balance < amount:
                return False
            profile.balance = round(profile.balance - amount, 2)
            return True

    def can_afford(self, user_id: int, amount: float) -> bool:
        if self.is_admin(user_id):
            return True
        return self.get_or_create(user_id).balance >= amount

    def add_pack(self, user_id: int, pack: PackCreationResult) -> None:
        with self._lock:
            profile = self._get_or_create_unlocked(user_id)
            profile.packs.insert(0, pack)

    def list_packs(self, user_id: int) -> list[PackCreationResult]:
        return list(self.get_or_create(user_id).packs)

    def list_user_ids(self) -> list[int]:
        with self._lock:
            return list(self._users.keys())
