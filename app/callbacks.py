from aiogram.filters.callback_data import CallbackData


class MainMenuCallback(CallbackData, prefix="main"):
    action: str


class CategoryCallback(CallbackData, prefix="cat"):
    category_id: str


class PickModeCallback(CallbackData, prefix="pick"):
    mode: str


class TemplateToggleCallback(CallbackData, prefix="tpl"):
    template_id: int


class TemplatePageCallback(CallbackData, prefix="page"):
    page: int


class TemplateActionCallback(CallbackData, prefix="tpla"):
    action: str


class PreviewActionCallback(CallbackData, prefix="prev"):
    action: str


class PaymentActionCallback(CallbackData, prefix="pay"):
    action: str
    invoice_id: str

