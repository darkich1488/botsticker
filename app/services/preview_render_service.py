from __future__ import annotations

import asyncio
import gzip
import json
import logging
import math
import shlex
import subprocess
import uuid
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from app.config import Settings
from app.models.preview_result import PreviewRenderResult
from app.utils.files import write_json_file

DEFAULT_LOG_FILE = "bot_debug.log"


def _ensure_file_and_console_logging() -> None:
    root = logging.getLogger()
    if getattr(root, "_emoji_bot_logging_ready", False):
        return

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    has_console = any(
        isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler)
        for handler in root.handlers
    )
    if not has_console:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        root.addHandler(console_handler)

    has_file = any(
        isinstance(handler, logging.FileHandler)
        and Path(getattr(handler, "baseFilename", "")).name == DEFAULT_LOG_FILE
        for handler in root.handlers
    )
    if not has_file:
        file_handler = logging.FileHandler(DEFAULT_LOG_FILE, encoding="utf-8")
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)

    if root.level > logging.INFO:
        root.setLevel(logging.INFO)
    setattr(root, "_emoji_bot_logging_ready", True)


class LottieRenderAdapter(ABC):
    @abstractmethod
    def render_gif(self, input_json_path: str, output_gif_path: str) -> PreviewRenderResult:
        raise NotImplementedError

    @abstractmethod
    def render_png(self, input_json_path: str, output_png_path: str) -> PreviewRenderResult:
        raise NotImplementedError


class ExternalCommandLottieRenderAdapter(LottieRenderAdapter):
    def __init__(self, command_template: str | None, timeout_sec: int) -> None:
        self._command_template = command_template
        self._timeout_sec = timeout_sec

    def _build_command(self, input_path: str, output_path: str) -> list[str] | None:
        if not self._command_template:
            return None
        template = self._command_template.strip()
        if "{input}" in template and "{output}" in template:
            resolved = template.format(input=input_path, output=output_path)
            return shlex.split(resolved)
        return [template, input_path, output_path]

    def _run(self, input_path: str, output_path: str) -> PreviewRenderResult:
        command = self._build_command(input_path=input_path, output_path=output_path)
        if not command:
            return PreviewRenderResult(
                success=False,
                output_path=None,
                frame_count=0,
                width=0,
                height=0,
                error_message="Renderer command is not configured",
            )
        try:
            subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
                timeout=self._timeout_sec,
            )
            output = Path(output_path)
            if not output.exists():
                return PreviewRenderResult(
                    success=False,
                    output_path=None,
                    frame_count=0,
                    width=0,
                    height=0,
                    error_message="Renderer command finished without output file",
                )
            return PreviewRenderResult(
                success=True,
                output_path=str(output.resolve()),
                frame_count=0,
                width=0,
                height=0,
                error_message=None,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as exc:
            return PreviewRenderResult(
                success=False,
                output_path=None,
                frame_count=0,
                width=0,
                height=0,
                error_message=str(exc),
            )
        except Exception as exc:
            return PreviewRenderResult(
                success=False,
                output_path=None,
                frame_count=0,
                width=0,
                height=0,
                error_message=f"Unexpected external render error: {exc}",
            )

    def render_gif(self, input_json_path: str, output_gif_path: str) -> PreviewRenderResult:
        return self._run(input_json_path, output_gif_path)

    def render_png(self, input_json_path: str, output_png_path: str) -> PreviewRenderResult:
        return self._run(input_json_path, output_png_path)


class PillowLottieRenderAdapter(LottieRenderAdapter):
    def __init__(self, fps: int, max_frames: int) -> None:
        self._fps = max(8, fps)
        self._max_frames = max(12, max_frames)
        self._font = ImageFont.load_default()

    @staticmethod
    def _iter_nodes(payload: Any):
        if isinstance(payload, dict):
            yield payload
            for value in payload.values():
                yield from PillowLottieRenderAdapter._iter_nodes(value)
        elif isinstance(payload, list):
            for item in payload:
                yield from PillowLottieRenderAdapter._iter_nodes(item)

    @staticmethod
    def _read_json(path: str) -> dict[str, Any]:
        with Path(path).open("r", encoding="utf-8-sig") as fp:
            payload = json.load(fp)
        if not isinstance(payload, dict):
            raise ValueError("Input Lottie JSON must be an object")
        return payload

    @staticmethod
    def _to_rgb(raw_color: Any, default: tuple[int, int, int]) -> tuple[int, int, int]:
        if isinstance(raw_color, list) and len(raw_color) >= 3:
            values = raw_color[:3]
            if all(isinstance(x, (int, float)) for x in values):
                if max(values) <= 1.0:
                    return tuple(max(0, min(255, int(v * 255))) for v in values)  # type: ignore[return-value]
                return tuple(max(0, min(255, int(v))) for v in values)  # type: ignore[return-value]
        return default

    def _extract_text(self, data: dict[str, Any]) -> str:
        for node in self._iter_nodes(data):
            if not isinstance(node, dict):
                continue
            text_container = node.get("t")
            if not isinstance(text_container, dict):
                continue
            keyframes = text_container.get("d", {}).get("k")
            if not isinstance(keyframes, list):
                continue
            for keyframe in keyframes:
                if not isinstance(keyframe, dict):
                    continue
                style = keyframe.get("s")
                if isinstance(style, dict):
                    text = style.get("t")
                    if isinstance(text, str) and text.strip():
                        return text.strip()
        return "EMOJI"

    def _extract_color_from_container(
        self,
        container: Any,
        fallback: tuple[int, int, int],
    ) -> tuple[int, int, int]:
        if isinstance(container, list):
            if container and all(isinstance(item, (int, float)) for item in container[:3]):
                return self._to_rgb(container, fallback)
            for item in container:
                candidate = self._extract_color_from_container(item, fallback)
                if candidate != fallback:
                    return candidate
            return fallback
        if isinstance(container, dict):
            for key in ("k", "s", "e"):
                if key in container:
                    candidate = self._extract_color_from_container(container[key], fallback)
                    if candidate != fallback:
                        return candidate
            return fallback
        return fallback

    def _extract_colors(self, data: dict[str, Any]) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
        fill = (230, 230, 230)
        stroke = (20, 20, 20)
        for node in self._iter_nodes(data):
            if not isinstance(node, dict):
                continue
            node_type = node.get("ty")
            if node_type not in ("fl", "st"):
                continue
            color_container = node.get("c")
            candidate = self._extract_color_from_container(color_container, fill if node_type == "fl" else stroke)
            if node_type == "fl":
                fill = candidate
            else:
                stroke = candidate
        return fill, stroke

    @staticmethod
    def _extract_size(data: dict[str, Any]) -> tuple[int, int]:
        width = int(float(data.get("w", 512)))
        height = int(float(data.get("h", 512)))
        return max(128, min(width, 512)), max(128, min(height, 512))

    def _extract_frame_count(self, data: dict[str, Any]) -> int:
        ip = int(float(data.get("ip", 0)))
        op = int(float(data.get("op", 48)))
        total = max(12, op - ip)
        return min(total, self._max_frames)

    def _build_frames(
        self,
        width: int,
        height: int,
        frame_count: int,
        text: str,
        fill_color: tuple[int, int, int],
        stroke_color: tuple[int, int, int],
    ) -> list[Image.Image]:
        frames: list[Image.Image] = []
        center_x = width // 2
        center_y = height // 2
        base_radius = min(width, height) * 0.36

        for frame_index in range(frame_count):
            phase = (frame_index / max(1, frame_count - 1)) * math.pi * 2
            pulse = 1.0 + 0.06 * math.sin(phase)
            radius = int(base_radius * pulse)
            offset_y = int(8 * math.sin(phase * 1.2))

            image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            draw = ImageDraw.Draw(image)

            bbox = [
                center_x - radius,
                center_y - radius + offset_y,
                center_x + radius,
                center_y + radius + offset_y,
            ]
            draw.ellipse(
                bbox,
                fill=fill_color + (255,),
                outline=stroke_color + (255,),
                width=10,
            )

            text_box = draw.textbbox((0, 0), text, font=self._font)
            text_w = text_box[2] - text_box[0]
            text_h = text_box[3] - text_box[1]
            text_x = (width - text_w) // 2
            text_y = (height - text_h) // 2 + offset_y
            draw.text((text_x + 2, text_y + 2), text, fill=(0, 0, 0, 180), font=self._font)
            draw.text((text_x, text_y), text, fill=(255, 255, 255, 255), font=self._font)
            frames.append(image)
        return frames

    @staticmethod
    def _prepare_gif_frames(frames: list[Image.Image]) -> list[Image.Image]:
        if not frames:
            return []
        dither_none = getattr(Image, "Dither", None)
        if dither_none is not None:
            dither_mode = getattr(Image.Dither, "NONE", 0)
        else:
            dither_mode = getattr(Image, "NONE", 0)

        base_rgb = frames[0].convert("RGB")
        base = base_rgb.quantize(colors=255, method=Image.MEDIANCUT, dither=dither_mode)
        prepared: list[Image.Image] = [base]
        for frame in frames[1:]:
            prepared.append(
                frame.convert("RGB").quantize(palette=base, dither=dither_mode)
            )
        return prepared

    def render_gif(self, input_json_path: str, output_gif_path: str) -> PreviewRenderResult:
        logger = logging.getLogger(self.__class__.__name__)
        try:
            data = self._read_json(input_json_path)
            width, height = self._extract_size(data)
            frame_count = self._extract_frame_count(data)
            text = self._extract_text(data)
            fill_color, stroke_color = self._extract_colors(data)
            frames = self._build_frames(
                width=width,
                height=height,
                frame_count=frame_count,
                text=text,
                fill_color=fill_color,
                stroke_color=stroke_color,
            )
            gif_frames = self._prepare_gif_frames(frames)
            output = Path(output_gif_path)
            output.parent.mkdir(parents=True, exist_ok=True)
            duration_ms = int(1000 / self._fps)
            logger.info(
                "GIF save params adapter=%s frame_count=%s width=%s height=%s "
                "duration_ms=%s loop=%s optimize=%s",
                self.__class__.__name__,
                len(gif_frames),
                width,
                height,
                duration_ms,
                0,
                False,
            )
            gif_frames[0].save(
                output,
                save_all=True,
                append_images=gif_frames[1:],
                loop=0,
                duration=duration_ms,
                disposal=2,
                optimize=False,
            )
            return PreviewRenderResult(
                success=True,
                output_path=str(output.resolve()),
                frame_count=frame_count,
                width=width,
                height=height,
                error_message=None,
            )
        except Exception as exc:
            return PreviewRenderResult(
                success=False,
                output_path=None,
                frame_count=0,
                width=0,
                height=0,
                error_message=str(exc),
            )

    def render_png(self, input_json_path: str, output_png_path: str) -> PreviewRenderResult:
        try:
            data = self._read_json(input_json_path)
            width, height = self._extract_size(data)
            frame_count = self._extract_frame_count(data)
            text = self._extract_text(data)
            fill_color, stroke_color = self._extract_colors(data)
            frame = self._build_frames(
                width=width,
                height=height,
                frame_count=1,
                text=text,
                fill_color=fill_color,
                stroke_color=stroke_color,
            )[0]
            output = Path(output_png_path)
            output.parent.mkdir(parents=True, exist_ok=True)
            frame.save(output, format="PNG")
            return PreviewRenderResult(
                success=True,
                output_path=str(output.resolve()),
                frame_count=frame_count,
                width=width,
                height=height,
                error_message=None,
            )
        except Exception as exc:
            return PreviewRenderResult(
                success=False,
                output_path=None,
                frame_count=0,
                width=0,
                height=0,
                error_message=str(exc),
            )


class PreviewRenderService:
    def __init__(self, settings: Settings) -> None:
        _ensure_file_and_console_logging()
        self._settings = settings
        self._logger = logging.getLogger(self.__class__.__name__)
        self._adapters: list[LottieRenderAdapter] = []
        if settings.lottie_renderer_cmd:
            self._adapters.append(
                ExternalCommandLottieRenderAdapter(
                    command_template=settings.lottie_renderer_cmd,
                    timeout_sec=settings.preview_timeout_sec,
                )
            )
        self._adapters.append(
            PillowLottieRenderAdapter(
                fps=settings.preview_fps,
                max_frames=settings.preview_max_frames,
            )
        )
        self._logger.info(
            "PreviewRenderService initialized adapters=%s timeout=%s",
            [adapter.__class__.__name__ for adapter in self._adapters],
            settings.preview_timeout_sec,
        )

    def _render_with_adapters(
        self,
        json_path: str,
        output_path: str,
        render_kind: str,
    ) -> PreviewRenderResult:
        self._logger.info(
            "Preview render start kind=%s json=%s output=%s",
            render_kind,
            json_path,
            output_path,
        )
        for adapter in self._adapters:
            try:
                if render_kind == "gif":
                    result = adapter.render_gif(json_path, output_path)
                else:
                    result = adapter.render_png(json_path, output_path)
            except Exception:
                self._logger.error(
                    "Preview adapter crashed kind=%s adapter=%s json=%s",
                    render_kind,
                    adapter.__class__.__name__,
                    json_path,
                    exc_info=True,
                )
                result = PreviewRenderResult(
                    success=False,
                    output_path=None,
                    frame_count=0,
                    width=0,
                    height=0,
                    error_message="Adapter crashed",
                )

            if result.success:
                self._logger.info(
                    "Preview adapter success kind=%s adapter=%s output=%s frames=%s size=%sx%s",
                    render_kind,
                    adapter.__class__.__name__,
                    result.output_path,
                    result.frame_count,
                    result.width,
                    result.height,
                )
                return result

            self._logger.warning(
                "Preview adapter failed kind=%s adapter=%s error=%s",
                render_kind,
                adapter.__class__.__name__,
                result.error_message,
            )

        return PreviewRenderResult(
            success=False,
            output_path=None,
            frame_count=0,
            width=0,
            height=0,
            error_message=f"All preview adapters failed for kind={render_kind}",
        )

    async def _render_async(
        self,
        json_path: str,
        output_path: str,
        render_kind: str,
    ) -> PreviewRenderResult:
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(
                    self._render_with_adapters,
                    json_path,
                    output_path,
                    render_kind,
                ),
                timeout=self._settings.preview_timeout_sec,
            )
        except asyncio.TimeoutError:
            self._logger.error(
                "Preview render timeout kind=%s json=%s output=%s timeout=%s",
                render_kind,
                json_path,
                output_path,
                self._settings.preview_timeout_sec,
                exc_info=True,
            )
            return PreviewRenderResult(
                success=False,
                output_path=None,
                frame_count=0,
                width=0,
                height=0,
                error_message=f"Render timeout ({render_kind})",
            )
        except Exception:
            self._logger.error(
                "Preview render async failure kind=%s json=%s output=%s",
                render_kind,
                json_path,
                output_path,
                exc_info=True,
            )
            return PreviewRenderResult(
                success=False,
                output_path=None,
                frame_count=0,
                width=0,
                height=0,
                error_message=f"Render async failure ({render_kind})",
            )

    async def render_preview_gif_from_lottie(
        self,
        lottie_data: dict[str, Any],
        output_name: str | None = None,
    ) -> PreviewRenderResult:
        temp_id = output_name or uuid.uuid4().hex
        temp_json = self._settings.temp_dir / f"{temp_id}.json"
        output_gif = self._settings.previews_dir / f"{temp_id}.gif"
        output_png = self._settings.previews_dir / f"{temp_id}.png"
        temp_json.parent.mkdir(parents=True, exist_ok=True)
        self._settings.previews_dir.mkdir(parents=True, exist_ok=True)

        self._logger.info("Preview build start output_id=%s", temp_id)
        try:
            await asyncio.to_thread(write_json_file, temp_json, lottie_data, True)
        except Exception:
            self._logger.error(
                "Failed to write temp json for preview path=%s",
                str(temp_json),
                exc_info=True,
            )
            return PreviewRenderResult(
                success=False,
                output_path=None,
                frame_count=0,
                width=0,
                height=0,
                error_message="Failed to serialize lottie preview input",
            )

        gif_result = await self._render_async(
            json_path=str(temp_json),
            output_path=str(output_gif),
            render_kind="gif",
        )
        if gif_result.success and gif_result.output_path:
            try:
                gif_size = Path(gif_result.output_path).stat().st_size
            except OSError:
                gif_size = self._settings.preview_max_gif_bytes + 1
            if gif_size <= self._settings.preview_max_gif_bytes:
                temp_json.unlink(missing_ok=True)
                output_png.unlink(missing_ok=True)
                self._logger.info(
                    "Preview GIF ready output=%s size=%s",
                    gif_result.output_path,
                    gif_size,
                )
                return gif_result
            self._logger.warning(
                "Preview GIF too large size=%s limit=%s -> fallback PNG",
                gif_size,
                self._settings.preview_max_gif_bytes,
            )
            Path(gif_result.output_path).unlink(missing_ok=True)

        self._logger.warning(
            "Preview GIF render failed output_id=%s error=%s -> fallback PNG",
            temp_id,
            gif_result.error_message,
        )
        png_result = await self._render_async(
            json_path=str(temp_json),
            output_path=str(output_png),
            render_kind="png",
        )
        temp_json.unlink(missing_ok=True)
        if png_result.success and png_result.output_path:
            output_gif.unlink(missing_ok=True)
            self._logger.info("Preview PNG fallback ready output=%s", png_result.output_path)
            return png_result

        output_gif.unlink(missing_ok=True)
        output_png.unlink(missing_ok=True)
        self._logger.error(
            "Preview render failed completely output_id=%s gif_error=%s png_error=%s",
            temp_id,
            gif_result.error_message,
            png_result.error_message,
        )
        return PreviewRenderResult(
            success=False,
            output_path=None,
            frame_count=0,
            width=0,
            height=0,
            error_message=(
                "Preview render failed. "
                f"GIF error: {gif_result.error_message}; PNG error: {png_result.error_message}"
            ),
        )

    async def render_preview_gif_from_tgs(
        self,
        tgs_bytes: bytes,
        output_name: str | None = None,
    ) -> PreviewRenderResult:
        self._logger.info("Preview render from TGS start output_name=%s", output_name)
        try:
            raw_json = await asyncio.to_thread(
                lambda: json.loads(gzip.decompress(tgs_bytes).decode("utf-8"))
            )
        except Exception:
            self._logger.error("Failed to decode TGS for preview", exc_info=True)
            return PreviewRenderResult(
                success=False,
                output_path=None,
                frame_count=0,
                width=0,
                height=0,
                error_message="Failed to decode TGS payload",
            )

        if not isinstance(raw_json, dict):
            self._logger.error("Decoded TGS payload is not JSON object")
            return PreviewRenderResult(
                success=False,
                output_path=None,
                frame_count=0,
                width=0,
                height=0,
                error_message="Decoded TGS payload is not a JSON object",
            )
        return await self.render_preview_gif_from_lottie(raw_json, output_name=output_name)
