from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from app.callbacks import PreviewActionCallback, TemplateActionCallback
from app.config import Settings
from app.handlers.create_pack import show_template_selection_screen
from app.handlers.preview_helpers import build_and_send_preview
from app.services.preview_service import PreviewService
from app.services.pricing_service import PricingService
from app.services.template_repository import TemplateRepository
from app.states import CreatePackState

router = Router(name="preview")


@router.callback_query(CreatePackState.choosing_templates, TemplateActionCallback.filter(F.action == "preview"))
async def preview_from_templates(
    callback: CallbackQuery,
    state: FSMContext,
    template_repository: TemplateRepository,
    preview_service: PreviewService,
    settings: Settings,
) -> None:
    await build_and_send_preview(
        target=callback,
        state=state,
        template_repository=template_repository,
        preview_service=preview_service,
        settings=settings,
    )


@router.callback_query(CreatePackState.preview, PreviewActionCallback.filter(F.action == "back_to_templates"))
async def back_to_templates(
    callback: CallbackQuery,
    state: FSMContext,
    template_repository: TemplateRepository,
    pricing_service: PricingService,
    settings: Settings,
) -> None:
    await state.set_state(CreatePackState.choosing_templates)
    await show_template_selection_screen(
        target=callback,
        state=state,
        template_repository=template_repository,
        pricing_service=pricing_service,
        settings=settings,
    )

