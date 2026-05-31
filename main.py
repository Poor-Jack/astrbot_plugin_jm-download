from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.message_components import File
from astrbot.api.star import Context, Star, register
from astrbot.core import astrbot_config, file_token_service
from astrbot.core.utils.astrbot_path import get_astrbot_data_path

try:
    from .jm_download_core import (
        FORMAT_ERROR,
        JMDownloadConfig,
        build_onebot_upload_file_actions,
        build_qq_upload_file_refs,
        cleanup_zip,
        coerce_bool,
        coerce_int,
        download_album_as_zip,
        parse_jm_command,
    )
except ImportError:
    from jm_download_core import (
        FORMAT_ERROR,
        JMDownloadConfig,
        build_onebot_upload_file_actions,
        build_qq_upload_file_refs,
        cleanup_zip,
        coerce_bool,
        coerce_int,
        download_album_as_zip,
        parse_jm_command,
    )


@register(
    "astrbot_plugin_jm_download",
    "poorjack",
    "通过 /jm [num] 下载 JM album 并发送加密 zip",
    "1.0.0",
)
class JMDownloadPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig | None = None):
        super().__init__(context)
        self.config = config or {}

    @filter.command("jm")
    async def jm(self, event: AstrMessageEvent):
        """下载 JM album，并以同编号密码打包 zip 发送。"""
        album_id, error = parse_jm_command(event.message_str)
        if error is not None or album_id is None:
            yield event.plain_result(FORMAT_ERROR)
            return

        yield event.plain_result(f"开始下载 JM {album_id}，请稍候。")

        try:
            result = await asyncio.to_thread(
                download_album_as_zip,
                album_id,
                self._build_config(),
            )
        except Exception as exc:
            logger.exception("JM 下载失败: %s", album_id)
            yield event.plain_result(f"下载失败，编号：{album_id}，原因：{_summarize_error(exc)}")
            return

        page_text = str(result.page_count) if result.page_count is not None else "未知"
        yield event.plain_result(
            f"下载完成，编号：{album_id}，页数：{page_text}，密码：{album_id}"
        )

        delivery_mode = str(
            _get_config_value(self.config, "delivery_mode", "qq_file")
        ).strip().lower()
        if delivery_mode == "file":
            yield event.chain_result(
                [
                    File(
                        name=result.zip_path.name,
                        file=str(result.zip_path),
                    )
                ]
            )
        else:
            if delivery_mode == "qq_file" or (
                delivery_mode == "link" and not _get_callback_host()
            ):
                sent, error = await self._send_qq_file(event, result.zip_path)
                if sent:
                    yield event.plain_result(f"zip 已发送到 QQ，文件名：{result.zip_path.name}")
                    if not self._build_config().keep_zip:
                        cleanup_zip(result.zip_path)
                    return
                logger.warning("QQ 文件上传不可用，降级为下载链接: %s", error)

            yield event.plain_result(
                await self._build_download_message(result.zip_path, delivery_mode)
            )

        if delivery_mode == "file" and not self._build_config().keep_zip:
            cleanup_zip(result.zip_path)

    def _build_config(self) -> JMDownloadConfig:
        base_dir = _get_config_value(
            self.config,
            "base_dir",
            str(Path(get_astrbot_data_path()) / "jm_downloads"),
        ) or str(Path(get_astrbot_data_path()) / "jm_downloads")
        return JMDownloadConfig(
            base_dir=Path(str(base_dir)).expanduser().resolve(),
            client_impl=str(_get_config_value(self.config, "client_impl", "html")),
            domain=str(_get_config_value(self.config, "domain", "18comic.vip")),
            proxy=str(_get_config_value(self.config, "proxy", "system")),
            avs_cookie=str(_get_config_value(self.config, "avs_cookie", "")),
            image_threads=coerce_int(
                _get_config_value(self.config, "image_threads", 1),
                default=1,
                minimum=1,
            ),
            cleanup_images=coerce_bool(
                _get_config_value(self.config, "cleanup_images", True),
                default=True,
            ),
            keep_zip=coerce_bool(
                _get_config_value(self.config, "keep_zip", True),
                default=True,
            ),
        )

    async def _build_download_message(self, zip_path: Path, delivery_mode: str) -> str:
        if delivery_mode == "path":
            return f"zip 已生成，请在服务器本地获取：{zip_path}"

        callback_host = _get_callback_host()
        if callback_host:
            ttl = coerce_int(
                _get_config_value(self.config, "file_link_ttl", 3600),
                default=3600,
                minimum=60,
            )
            token = await file_token_service.register_file(str(zip_path), timeout=ttl)
            return (
                f"zip 下载链接：{callback_host}/api/file/{token}\n"
                f"链接有效期：{ttl} 秒\n"
                f"服务器本地路径：{zip_path}"
            )

        return (
            "未配置 callback_api_base，无法生成低内存下载链接。\n"
            f"请在服务器本地获取：{zip_path}"
        )

    async def _send_qq_file(
        self,
        event: AstrMessageEvent,
        zip_path: Path,
    ) -> tuple[bool, str]:
        bot = getattr(event, "bot", None)
        if bot is None or not hasattr(bot, "call_action"):
            return False, "当前事件不是 aiocqhttp/OneBot QQ 事件"

        group_id = event.get_group_id()
        is_group = bool(group_id)
        target_id = group_id if is_group else event.get_sender_id()
        upload_url = await self._register_file_url(zip_path)
        file_refs = build_qq_upload_file_refs(zip_path, upload_url)
        errors = []

        try:
            actions = build_onebot_upload_file_actions(
                is_group=is_group,
                target_id=target_id,
                file_refs=file_refs,
                file_name=zip_path.name,
            )
        except Exception as exc:
            return False, _summarize_error(exc)

        for action, payload in actions:
            try:
                await bot.call_action(action, **payload)
                logger.info("QQ 文件上传成功: %s via %s", zip_path, payload["file"])
                return True, ""
            except Exception as exc:
                summary = _summarize_error(exc)
                errors.append(f"{payload['file']}: {summary}")
                logger.warning(
                    "QQ 文件上传候选失败: %s via %s: %s",
                    zip_path,
                    payload["file"],
                    summary,
                )

        return False, "；".join(errors) if errors else "没有可用的 QQ 文件上传候选"

    async def _register_file_url(self, zip_path: Path) -> str | None:
        callback_host = _get_callback_host()
        if not callback_host:
            return None

        ttl = coerce_int(
            _get_config_value(self.config, "file_link_ttl", 3600),
            default=3600,
            minimum=60,
        )
        token = await file_token_service.register_file(str(zip_path), timeout=ttl)
        return f"{callback_host}/api/file/{token}"

    async def terminate(self):
        pass


def _get_config_value(config: Any, key: str, default: Any) -> Any:
    if hasattr(config, "get"):
        value = config.get(key, default)
        return default if value is None else value
    return default


def _get_callback_host() -> str:
    return str(astrbot_config.get("callback_api_base", "")).rstrip("/")


def _summarize_error(exc: Exception) -> str:
    message = str(exc).strip().splitlines()[0] if str(exc).strip() else exc.__class__.__name__
    return message[:180]
