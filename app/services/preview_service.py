from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.models.preview_result import PreviewAsset, PreviewContext, ProcessedTemplateData
from app.models.template import TemplateModel
from app.services.lottie_service import LottieService
from app.services.preview_render_service import PreviewRenderService
from app.services.pricing_service import PricingService


class PreviewService:
    def __init__(
        self,
        lottie_service: LottieService,
        preview_render_service: PreviewRenderService,
        pricing_service: PricingService,
        context_ttl_minutes: int = 120,
        max_preview_assets: int = 4,
    ) -> None:
        self._lottie_service = lottie_service
        self._preview_render_service = preview_render_service
        self._pricing_service = pricing_service
        self._contexts: dict[str, PreviewContext] = {}
        self._logger = logging.getLogger(self.__class__.__name__)
        self._context_ttl = timedelta(minutes=max(10, context_ttl_minutes))
        self._max_preview_assets = max(1, max_preview_assets)

    async def _prepare_template_item(
        self,
        template: TemplateModel,
        input_text: str,
        stroke_color: str,
        elements_color: str,
    ) -> ProcessedTemplateData:
        source_json = await asyncio.to_thread(self._lottie_service.load_lottie_json, template.file_path)
        enable_recolor = bool(template.supports_recolor)
        if not enable_recolor:
            self._logger.info(
                "Preview recolor skipped template_id=%s template=%s reason=supports_recolor_false",
                template.id,
                template.file_name,
            )
        processed_json, stats = await asyncio.to_thread(
            self._lottie_service.process_template_data,
            source_data=source_json,
            new_text=input_text,
            stroke_hex=stroke_color,
            elements_hex=elements_color,
            enable_recolor=enable_recolor,
            template_name=template.file_name,
        )
        tgs_bytes = await asyncio.to_thread(self._lottie_service.build_tgs, processed_json)
        return ProcessedTemplateData(
            template_id=template.id,
            template_name=template.file_name,
            processed_lottie=processed_json,
            tgs_bytes=tgs_bytes,
            text_replacements=stats.text_keyframes_updated,
            recolored_nodes=stats.recolored_nodes_total,
        )

    async def build_preview_context(
        self,
        user_id: int,
        category_id: str,
        templates: list[TemplateModel],
        input_text: str,
        stroke_color: str,
        elements_color: str,
        include_preview_assets: bool = True,
    ) -> PreviewContext:
        self.cleanup_expired_contexts()
        if not templates:
            raise ValueError("No templates selected for preview")

        processed_items: list[ProcessedTemplateData] = []
        for template in templates:
            try:
                item = await self._prepare_template_item(
                    template=template,
                    input_text=input_text,
                    stroke_color=stroke_color,
                    elements_color=elements_color,
                )
                processed_items.append(item)
                self._logger.info(
                    "Preview prepare user_id=%s template=%s text_replacements=%s recolored=%s",
                    user_id,
                    template.file_name,
                    item.text_replacements,
                    item.recolored_nodes,
                )
            except Exception as exc:
                self._logger.exception(
                    "Failed to process template user_id=%s template=%s error=%s",
                    user_id,
                    template.file_name,
                    exc,
                )
                continue

        if not processed_items:
            raise RuntimeError("No templates were processed successfully")

        preview_assets: list[PreviewAsset] = []
        if include_preview_assets:
            for item in processed_items[: self._max_preview_assets]:
                output_name = f"preview_{user_id}_{item.template_id}_{uuid.uuid4().hex[:8]}"
                result = await self._preview_render_service.render_preview_gif_from_lottie(
                    item.processed_lottie,
                    output_name=output_name,
                )
                if not result.success or not result.output_path:
                    self._logger.warning(
                        "Preview render failed user_id=%s template_id=%s error=%s",
                        user_id,
                        item.template_id,
                        result.error_message,
                    )
                    continue
                output_path = result.output_path
                suffix = Path(output_path).suffix.lower()
                media_type = "animation" if suffix == ".gif" else "photo"
                preview_assets.append(
                    PreviewAsset(
                        template_id=item.template_id,
                        media_type=media_type,
                        output_path=output_path,
                        render_result=result,
                    )
                )

        context_id = uuid.uuid4().hex
        context = PreviewContext(
            context_id=context_id,
            user_id=user_id,
            category_id=category_id,
            input_text=input_text,
            stroke_color=stroke_color,
            elements_color=elements_color,
            selected_template_ids=[item.template_id for item in processed_items],
            items=processed_items,
            preview_assets=preview_assets,
            price=self._pricing_service.calculate_templates_price(len(processed_items)),
        )
        self._contexts[context_id] = context
        return context

    def get_context(self, context_id: str, user_id: int | None = None) -> PreviewContext | None:
        context = self._contexts.get(context_id)
        if context is None:
            return None
        if user_id is not None and context.user_id != user_id:
            return None
        return context

    def release_context(self, context_id: str) -> None:
        context = self._contexts.pop(context_id, None)
        if not context:
            return
        for asset in context.preview_assets:
            try:
                Path(asset.output_path).unlink(missing_ok=True)
            except OSError:
                self._logger.warning("Failed to cleanup preview file: %s", asset.output_path)

    def cleanup_expired_contexts(self) -> None:
        now = datetime.now(timezone.utc)
        expired_ids: list[str] = []
        for context_id, context in self._contexts.items():
            if context.created_at + self._context_ttl < now:
                expired_ids.append(context_id)
        for context_id in expired_ids:
            self.release_context(context_id)
