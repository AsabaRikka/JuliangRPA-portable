from __future__ import annotations

from contextlib import asynccontextmanager
import os
from pathlib import Path
import re
from typing import AsyncIterator

from playwright.async_api import BrowserContext, Error as PlaywrightError, Page, Playwright, async_playwright

from .config import AppSettings, PROJECT_ROOT, ensure_runtime_dirs


BUNDLED_BROWSERS_DIR = PROJECT_ROOT / "ms-playwright"

OCEANENGINE_LAYOUT_FIX_SCRIPT = r"""
(() => {
    if (window.__juliangRpaLayoutFixInstalled) return;
    window.__juliangRpaLayoutFixInstalled = true;

    const style = document.createElement('style');
    style.id = 'juliang-rpa-layout-fix-style';
    style.textContent = `
        body.juliang-rpa-material-dialog-open {
            overflow: hidden !important;
        }
        .juliang-rpa-material-dialog {
            top: 0 !important;
            bottom: 0 !important;
            height: 100vh !important;
            max-height: 100vh !important;
            display: flex !important;
            flex-direction: column !important;
            overflow: hidden !important;
        }
        .juliang-rpa-material-dialog > * {
            min-height: 0 !important;
        }
        .juliang-rpa-material-scroll {
            flex: 1 1 auto !important;
            min-height: 0 !important;
            max-height: none !important;
            overflow: auto !important;
            padding-bottom: 76px !important;
        }
        .juliang-rpa-material-footer {
            flex: 0 0 auto !important;
            position: sticky !important;
            bottom: 0 !important;
            z-index: 2147483646 !important;
            display: flex !important;
            align-items: center !important;
            justify-content: flex-end !important;
            gap: 12px !important;
            min-height: 64px !important;
            padding: 12px 24px !important;
            background: #fff !important;
            border-top: 1px solid #e5e6eb !important;
            box-shadow: 0 -4px 16px rgba(0, 0, 0, 0.06) !important;
        }
    `;
    document.head.appendChild(style);

    const isVisible = node => {
        const rect = node.getBoundingClientRect();
        const computed = window.getComputedStyle(node);
        return rect.width > 0
            && rect.height > 0
            && rect.bottom > 0
            && rect.top < window.innerHeight
            && computed.display !== 'none'
            && computed.visibility !== 'hidden';
    };

    const containsAny = (text, words) => words.some(word => text.includes(word));

    const materialDialogCandidates = () => Array.from(
        document.querySelectorAll('[role="dialog"], .ovui-drawer, .byted-drawer, .ovui-modal, div')
    ).filter(node => {
        if (!isVisible(node)) return false;
        const rect = node.getBoundingClientRect();
        if (rect.width < 520 || rect.height < 360) return false;
        const text = (node.innerText || node.textContent || '').replace(/\s+/g, ' ').trim();
        return containsAny(text, ['我的视频', '抖音视频', '组织共享视频', '上传视频'])
            && containsAny(text, ['管理视频', '本页全选', '添加视频', '取消', '确定']);
    });

    const rectIntersectsViewport = node => {
        const rect = node.getBoundingClientRect();
        const computed = window.getComputedStyle(node);
        return rect.width > 0
            && rect.height > 0
            && rect.right > 0
            && rect.left < window.innerWidth
            && computed.display !== 'none'
            && computed.visibility !== 'hidden';
    };

    const findFooter = dialog => {
        const buttons = Array.from(dialog.querySelectorAll('button, [role="button"], .oc-button-wrap'))
            .filter(rectIntersectsViewport);
        const footerButtons = buttons.filter(button => {
            const text = (button.innerText || button.textContent || '').replace(/\s+/g, '').trim();
            return text === '取消' || text === '确定';
        });
        if (footerButtons.length === 0) return null;

        let footer = footerButtons[0];
        for (let depth = 0; depth < 5 && footer.parentElement && footer !== dialog; depth += 1) {
            const parent = footer.parentElement;
            const parentText = (parent.innerText || parent.textContent || '').replace(/\s+/g, '').trim();
            const hasCancel = parentText.includes('取消');
            const hasConfirm = parentText.includes('确定');
            const rect = parent.getBoundingClientRect();
            if (hasCancel && hasConfirm && rect.width > 220 && rect.height <= 120) {
                footer = parent;
                break;
            }
            footer = parent;
        }
        return footer;
    };

    const findScrollable = (dialog, footer) => {
        const children = Array.from(dialog.children).filter(child => child !== footer && isVisible(child));
        if (children.length === 0) return dialog;
        const ranked = children
            .map(child => ({ child, rect: child.getBoundingClientRect() }))
            .filter(item => item.rect.height > 160)
            .sort((a, b) => b.rect.height - a.rect.height);
        return (ranked[0]?.child) || children[children.length - 1] || dialog;
    };

    const applyMaterialDialogFix = () => {
        const dialogs = materialDialogCandidates();
        document.body.classList.toggle('juliang-rpa-material-dialog-open', dialogs.length > 0);
        for (const dialog of dialogs) {
            const footer = findFooter(dialog);
            if (!footer) continue;
            const scrollable = findScrollable(dialog, footer);
            const rect = dialog.getBoundingClientRect();
            dialog.classList.add('juliang-rpa-material-dialog');
            footer.classList.add('juliang-rpa-material-footer');
            scrollable.classList.add('juliang-rpa-material-scroll');
            footer.style.position = 'fixed';
            footer.style.left = `${Math.max(0, rect.left)}px`;
            footer.style.width = `${Math.min(rect.width, window.innerWidth - Math.max(0, rect.left))}px`;
            footer.style.right = 'auto';
            footer.style.bottom = '0px';
        }
    };

    const schedule = () => {
        window.clearTimeout(window.__juliangRpaLayoutFixTimer);
        window.__juliangRpaLayoutFixTimer = window.setTimeout(applyMaterialDialogFix, 80);
    };

    new MutationObserver(schedule).observe(document.documentElement, {
        childList: true,
        subtree: true,
        attributes: true,
        attributeFilter: ['class', 'style'],
    });
    window.addEventListener('resize', schedule);
    schedule();
})();
"""


@asynccontextmanager
async def persistent_context(
    settings: AppSettings,
    close_on_exit: bool = True,
) -> AsyncIterator[BrowserContext]:
    ensure_runtime_dirs(settings)
    configure_playwright_browsers_path()
    async with async_playwright() as playwright:
        context = await _launch_persistent_context(playwright, settings)
        await context.add_init_script(OCEANENGINE_LAYOUT_FIX_SCRIPT)
        for page in context.pages:
            await install_oceanengine_layout_fix(page)
        try:
            context.set_default_timeout(settings.browser.timeout_ms)
            yield context
        finally:
            if close_on_exit:
                await context.close()


async def first_page(context: BrowserContext) -> Page:
    if context.pages:
        return context.pages[0]
    return await context.new_page()


async def fresh_page(context: BrowserContext) -> Page:
    window_state = await current_browser_window_state(context)
    if window_state == "minimized":
        page = next((candidate for candidate in context.pages if not candidate.is_closed()), None)
        if page is None:
            page = await context.new_page()
            await set_browser_window_state(page, "minimized")
    else:
        page = await context.new_page()
    for old_page in list(context.pages):
        if old_page == page:
            continue
        try:
            await old_page.close(run_before_unload=False)
        except PlaywrightError:
            pass
    await install_oceanengine_layout_fix(page)
    return page


async def goto_base(page: Page, settings: AppSettings) -> None:
    await page.goto(settings.base_url, wait_until="domcontentloaded")
    await normalize_page_zoom(page)


async def goto_login(page: Page, settings: AppSettings) -> None:
    await page.goto(settings.login_url, wait_until="domcontentloaded")
    await normalize_page_zoom(page)


async def normalize_page_zoom(page: Page, zoom_out_steps: int = 0) -> None:
    await page.keyboard.press("Control+0")
    for _ in range(zoom_out_steps):
        await page.keyboard.press("Control+-")
    await install_oceanengine_layout_fix(page)


async def install_oceanengine_layout_fix(page: Page) -> None:
    try:
        await page.evaluate(OCEANENGINE_LAYOUT_FIX_SCRIPT)
    except PlaywrightError:
        pass


async def save_debug_snapshot(page: Page, output_dir: Path, prefix: str) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_prefix = re.sub(r"[^a-zA-Z0-9._-]+", "_", prefix).strip("._")
    if not safe_prefix:
        safe_prefix = "snapshot"
    screenshot_path = output_dir / f"{safe_prefix}.png"
    html_path = output_dir / f"{safe_prefix}.html"
    await page.screenshot(path=str(screenshot_path), full_page=True)
    html_path.write_text(await page.content(), encoding="utf-8")
    return screenshot_path, html_path


async def _launch_persistent_context(
    playwright: Playwright,
    settings: AppSettings,
) -> BrowserContext:
    launch_args = [
        "--disable-blink-features=AutomationControlled",
        "--force-device-scale-factor=1",
        "--high-dpi-support=1",
        "--window-size=1920,1080",
    ]

    base_kwargs = {
        "user_data_dir": str(settings.browser.user_data_dir),
        "headless": settings.browser.headless,
        "slow_mo": settings.browser.slow_mo_ms,
        "no_viewport": True,
        "args": launch_args,
        "ignore_default_args": ["--enable-automation"],
    }
    if should_record_video():
        base_kwargs["record_video_dir"] = str(settings.artifacts.recordings_dir)

    if settings.browser.executable_path is not None:
        return await playwright.chromium.launch_persistent_context(
            executable_path=str(settings.browser.executable_path),
            **base_kwargs,
        )

    if settings.browser.use_system_chrome:
        try:
            return await playwright.chromium.launch_persistent_context(
                channel=settings.browser.channel or "chrome",
                **base_kwargs,
            )
        except PlaywrightError:
            if not BUNDLED_BROWSERS_DIR.exists():
                raise

    bundled_executable = bundled_chromium_executable()
    if bundled_executable is not None:
        return await playwright.chromium.launch_persistent_context(
            executable_path=str(bundled_executable),
            **base_kwargs,
        )

    return await playwright.chromium.launch_persistent_context(
        **base_kwargs,
    )


def browser_mode_label(settings: AppSettings) -> str:
    if settings.browser.executable_path is not None:
        return f"指定浏览器：{settings.browser.executable_path}"
    if settings.browser.use_system_chrome:
        return "优先使用本机 Chrome，失败后使用项目内 Chromium"
    return "使用项目内 Chromium"


def configure_playwright_browsers_path() -> None:
    if BUNDLED_BROWSERS_DIR.exists():
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(BUNDLED_BROWSERS_DIR)


def should_record_video() -> bool:
    requested = os.getenv("JULIANG_RECORD_VIDEO", "").strip().lower() in {"1", "true", "yes", "y", "on"}
    return requested and playwright_ffmpeg_available()


async def current_browser_window_state(context: BrowserContext) -> str | None:
    page = next((candidate for candidate in context.pages if not candidate.is_closed()), None)
    if page is None:
        return None
    try:
        session = await context.new_cdp_session(page)
        result = await session.send("Browser.getWindowForTarget")
        bounds = result.get("bounds", {})
        return bounds.get("windowState")
    except Exception:
        return None


async def set_browser_window_state(page: Page, window_state: str) -> None:
    try:
        session = await page.context.new_cdp_session(page)
        result = await session.send("Browser.getWindowForTarget")
        await session.send(
            "Browser.setWindowBounds",
            {
                "windowId": result["windowId"],
                "bounds": {"windowState": window_state},
            },
        )
    except Exception:
        pass


def playwright_ffmpeg_available() -> bool:
    search_roots = []
    configured = os.getenv("PLAYWRIGHT_BROWSERS_PATH", "").strip()
    if configured:
        search_roots.append(Path(configured))
    search_roots.append(BUNDLED_BROWSERS_DIR)

    for root in search_roots:
        if not root.exists():
            continue
        if any(root.glob("ffmpeg-*/ffmpeg-win64.exe")):
            return True
    return False


def bundled_chromium_executable() -> Path | None:
    if not BUNDLED_BROWSERS_DIR.exists():
        return None
    candidates = sorted(
        BUNDLED_BROWSERS_DIR.glob("chromium-*/chrome-win64/chrome.exe"),
        reverse=True,
    )
    if not candidates:
        candidates = sorted(
            BUNDLED_BROWSERS_DIR.glob("chromium-*/chrome-win/chrome.exe"),
            reverse=True,
        )
    return candidates[0] if candidates else None
