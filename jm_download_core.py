from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any


FORMAT_ERROR = "格式错误，正确格式：/jm [num]，例如：/jm 1424612"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


@dataclass(frozen=True)
class JMDownloadConfig:
    base_dir: Path
    client_impl: str = "html"
    domain: str = "18comic.vip"
    proxy: str = "system"
    avs_cookie: str = ""
    image_threads: int = 2
    cleanup_images: bool = True
    keep_zip: bool = True


@dataclass(frozen=True)
class JMDownloadResult:
    album_id: str
    page_count: int | None
    pdf_path: Path
    zip_path: Path


def parse_jm_command(message: str) -> tuple[str | None, str | None]:
    parts = message.strip().split()
    if len(parts) == 1 and parts[0].isdigit():
        return parts[0], None
    if len(parts) == 2 and parts[0] in {"/jm", "jm"} and parts[1].isdigit():
        return parts[1], None
    return None, FORMAT_ERROR


def download_album_as_zip(album_id: str, config: JMDownloadConfig) -> JMDownloadResult:
    work_dir = config.base_dir / album_id
    image_dir = work_dir / "images"
    pdf_path = work_dir / f"{album_id}.pdf"
    zip_path = work_dir / f"{album_id}.zip"

    work_dir.mkdir(parents=True, exist_ok=True)
    image_dir.mkdir(parents=True, exist_ok=True)

    option = _build_jm_option(config, image_dir)
    album, _downloader = _download_album(album_id, option)

    image_paths = collect_image_paths(image_dir)
    create_pdf(image_paths, pdf_path)
    create_password_zip(pdf_path, zip_path, album_id)

    if config.cleanup_images:
        shutil.rmtree(image_dir, ignore_errors=True)

    return JMDownloadResult(
        album_id=album_id,
        page_count=_get_page_count(album),
        pdf_path=pdf_path,
        zip_path=zip_path,
    )


def collect_image_paths(image_dir: Path) -> list[Path]:
    images = [
        path
        for path in image_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    ]
    images.sort(key=lambda path: [part.lower() for part in path.relative_to(image_dir).parts])
    if not images:
        raise RuntimeError("下载完成但没有找到图片文件")
    return images


def create_pdf(image_paths: list[Path], pdf_path: Path) -> None:
    import img2pdf

    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    with pdf_path.open("wb") as fp:
        img2pdf.convert([str(path) for path in image_paths], outputstream=fp)


def create_password_zip(pdf_path: Path, zip_path: Path, password: str) -> None:
    import pyzipper

    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with pyzipper.AESZipFile(
        zip_path,
        "w",
        compression=pyzipper.ZIP_STORED,
        encryption=pyzipper.WZ_AES,
    ) as zf:
        zf.setpassword(password.encode("utf-8"))
        zf.write(pdf_path, arcname=pdf_path.name)


def cleanup_zip(zip_path: Path) -> None:
    try:
        zip_path.unlink()
    except FileNotFoundError:
        pass


def _build_jm_option(config: JMDownloadConfig, image_dir: Path) -> Any:
    import jmcomic

    option_dict = {
        "log": True,
        "dir_rule": {
            "rule": "Bd_Pname",
            "base_dir": str(image_dir),
        },
        "download": {
            "cache": True,
            "image": {
                "decode": True,
                "suffix": None,
            },
            "threading": {
                "image": max(1, int(config.image_threads)),
                "photo": 1,
            },
        },
        "client": {
            "cache": None,
            "domain": {
                "html": [config.domain],
                "api": [config.domain],
            },
            "postman": {
                "type": "curl_cffi",
                "meta_data": {
                    "impersonate": "chrome",
                    "headers": None,
                    "proxies": _normalize_proxy(config.proxy),
                },
            },
            "impl": config.client_impl,
            "retry_times": 5,
        },
        "plugins": {
            "valid": "log",
        },
    }
    option = jmcomic.JmOption.construct(option_dict)
    if config.avs_cookie.strip():
        option.update_cookies({"AVS": config.avs_cookie.strip()})
    return option


def _download_album(album_id: str, option: Any) -> tuple[Any, Any]:
    import jmcomic

    result = jmcomic.download_album(album_id, option)
    if isinstance(result, tuple) and len(result) >= 2:
        return result[0], result[1]
    raise RuntimeError("jmcomic 返回了无法识别的下载结果")


def _normalize_proxy(proxy: str) -> dict[str, str] | None:
    value = (proxy or "").strip()
    if value == "" or value.lower() in {"system", "none", "false", "no"}:
        return None
    return {
        "http": value,
        "https": value,
    }


def _get_page_count(album: Any) -> int | None:
    page_count = getattr(album, "page_count", None)
    if isinstance(page_count, int):
        return page_count
    try:
        return int(page_count)
    except (TypeError, ValueError):
        return None
