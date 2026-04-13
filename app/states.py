from aiogram.fsm.state import State, StatesGroup


class MainMenuState(StatesGroup):
    idle = State()
    waiting_broadcast = State()


class CreatePackState(StatesGroup):
    choosing_category = State()
    waiting_text = State()
    waiting_username = State()
    waiting_pack_title = State()
    choosing_pick_mode = State()
    choosing_templates = State()
    preview = State()
    payment = State()
    generating = State()
