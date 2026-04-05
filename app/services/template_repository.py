from __future__ import annotations

import logging
import random
import re
from pathlib import Path

from app.config import Settings
from app.models.category import TemplateCategory
from app.models.template import TemplateModel
from app.utils.pagination import paginate


class TemplateRepository:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._logger = logging.getLogger(self.__class__.__name__)
        self._categories: dict[str, TemplateCategory] = {}
        self._templates_by_category: dict[str, list[TemplateModel]] = {}
        self._templates_by_id: dict[int, TemplateModel] = {}
        self.reload()

    def reload(self) -> None:
        self._categories.clear()
        self._templates_by_category.clear()
        self._templates_by_id.clear()

        next_template_id = 1
        for category_cfg in self._settings.categories:
            category = TemplateCategory(
                id=category_cfg.id,
                title=category_cfg.title,
                description=category_cfg.description,
                path_to_templates=str(category_cfg.path_to_templates),
                supports_recolor=category_cfg.supports_recolor,
            )
            self._categories[category.id] = category
            templates = self._scan_templates(category, next_template_id)
            self._templates_by_category[category.id] = templates
            for template in templates:
                self._templates_by_id[template.id] = template
            next_template_id += len(templates)

    def _scan_templates(self, category: TemplateCategory, start_id: int) -> list[TemplateModel]:
        template_dir = Path(category.path_to_templates).resolve()
        self._logger.info(
            "Scan templates category=%s dir=%s",
            category.id,
            str(template_dir),
        )
        if not template_dir.exists():
            self._logger.warning("Template directory does not exist: %s", template_dir)
            return []

        files = sorted(template_dir.glob("*.json"), key=self._sort_key)
        templates: list[TemplateModel] = []
        for index, path in enumerate(files, start=1):
            preview_path = self._find_preview(path)
            template = TemplateModel(
                id=start_id + index - 1,
                category_id=category.id,
                file_name=path.name,
                file_path=str(path.resolve()),
                preview_path=str(preview_path.resolve()) if preview_path else None,
                supports_text=True,
                supports_recolor=category.supports_recolor,
                order_index=index,
            )
            templates.append(template)
            self._logger.info(
                "Template loaded id=%s category=%s file_name=%s file_path=%s",
                template.id,
                category.id,
                template.file_name,
                template.file_path,
            )
        self._logger.info(
            "Loaded %s templates for category=%s", len(templates), category.id
        )
        return templates

    @staticmethod
    def _sort_key(path: Path) -> tuple[int, str]:
        stem = path.stem
        if stem.isdigit():
            return int(stem), stem
        match = re.search(r"(\d+)", stem)
        if match:
            return int(match.group(1)), stem
        return 10_000, stem

    @staticmethod
    def _find_preview(template_path: Path) -> Path | None:
        gif = template_path.with_suffix(".gif")
        png = template_path.with_suffix(".png")
        if gif.exists():
            return gif
        if png.exists():
            return png
        return None

    def get_categories(self) -> list[TemplateCategory]:
        return list(self._categories.values())

    def get_category(self, category_id: str) -> TemplateCategory | None:
        return self._categories.get(category_id)

    def get_templates_by_category(self, category_id: str) -> list[TemplateModel]:
        return list(self._templates_by_category.get(category_id, []))

    def get_template_by_id(self, template_id: int) -> TemplateModel | None:
        template = self._templates_by_id.get(template_id)
        if template is None:
            self._logger.warning("Template id not found: %s", template_id)
            return None
        path = Path(template.file_path)
        if path.exists():
            return template

        self._logger.warning(
            "Template file missing template_id=%s file_name=%s file_path=%s. Reloading repository.",
            template.id,
            template.file_name,
            str(path),
        )
        self.reload()

        refreshed = self._templates_by_id.get(template_id)
        if refreshed is None:
            self._logger.error(
                "Template id still missing after reload: %s",
                template_id,
            )
            return None

        refreshed_path = Path(refreshed.file_path)
        if not refreshed_path.exists():
            self._logger.error(
                "Template file missing after reload template_id=%s file_name=%s file_path=%s",
                refreshed.id,
                refreshed.file_name,
                str(refreshed_path),
            )
            return None

        self._logger.info(
            "Template path refreshed template_id=%s file_name=%s file_path=%s",
            refreshed.id,
            refreshed.file_name,
            str(refreshed_path),
        )
        return refreshed

    def get_templates_by_ids(self, template_ids: list[int]) -> list[TemplateModel]:
        found: list[TemplateModel] = []
        for template_id in template_ids:
            template = self.get_template_by_id(template_id)
            if template is not None:
                found.append(template)
        return sorted(found, key=lambda item: item.order_index)

    def get_templates_page(
        self,
        category_id: str,
        page: int,
        per_page: int,
    ) -> tuple[list[TemplateModel], int, int, int]:
        templates = self.get_templates_by_category(category_id)
        page_items, current_page, total_pages = paginate(templates, page, per_page)
        return page_items, current_page, total_pages, len(templates)

    def random_templates(self, category_id: str, count: int | None) -> list[TemplateModel]:
        templates = self.get_templates_by_category(category_id)
        if not templates:
            return []
        if count is None or count <= 0:
            count = random.randint(1, len(templates))
        count = max(1, min(count, len(templates)))
        return random.sample(templates, count)
