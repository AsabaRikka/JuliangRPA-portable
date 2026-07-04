from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import time
from typing import Callable
from playwright.async_api import (
    BrowserContext,
    Error as PlaywrightError,
    Locator,
    Page,
    TimeoutError as PlaywrightTimeoutError,
    expect,
)

from juliang_rpa.browser import normalize_page_zoom, save_debug_snapshot
from juliang_rpa.config import AppSettings

ProgressCallback = Callable[[str], None]


class DeepOptimizationTargetUnavailable(RuntimeError):
    """Raised when the create page has no selectable deep optimization target."""


@dataclass(frozen=True)
class NewAdOptions:
    account_id: str
    mini_game_name: str = "看你还嘴硬"
    mini_game_asset_id: str = "7598217165828816959"
    mini_game_app_id: str = "tt62e7145afdeec8aa02"
    optimization_goal: str = "激活"
    deep_optimization_goal: str = "变现ROI-7日"
    douyin_id: str = "37573898344"
    douyin_name: str = "游多米爱游戏"
    daily_budget: str = "99999"
    roi_coefficient: str = "1.08"
    ad_texts: str = (
        "这个游戏也太好玩了吧，休闲解压，即点即玩！\n"
        "宝，别笑，真的很难！\n"
        "休闲解压，无需下载即点即玩！\n"
        "这个游戏我也只能玩到第3关，你能过几关？\n"
        "这个游戏能过第二关的人，肯定智商都不低于150！\n"
        "你！说你呢！你厉害你来把第二关过了！\n"
        "这个小游戏也太有意思了，究竟谁才能玩过第二关？\n"
        "蹲厕所千万别点，我真的怕你腿麻！"
    )
    mini_program_link: str = (
        "slocal://microgame?app_id=tt62e7145afdeec8aa02&bdp_log=%7B%22launch_from%22%3A"
        "%22ad%22%2C%22location%22%3A%22%22%7D&scene=0&uniq_id=W20260123093301271v0k1zpuy"
        "&version=v2&version_type=current&bdpsum=23a9d5a"
    )
    backup_site_link: str = (
        "https://www.chengzijianzhan.com/tetris/page/7585013162672799794?"
        "projectid=__PROJECT_ID__&creativetype=__CTYPE__&clickid=__CLICKID__&mid1=__MID1__"
        "&mid2=__MID2__&mid3=__MID3__&mid4=__MID4__&mid5=__MID5__"
    )
    product_name: str = "看你还嘴硬"
    product_selling_points: str = "被这游戏硬控一整天 近期2个好友在玩 一玩一个不吱声"
    call_to_actions: str = "进入游戏 开始游戏 点击即玩"
    project_name_prefix: str = "ubmax-看你还嘴硬-xhy-7R1.08_"
    product_image_path: str = r"C:\Users\tanyu\Desktop\icon108\我的保安人生.jpeg"
    auto_add_videos: bool = False
    auto_add_video_count: str = "40"
    submit_project: bool = False
    ensure_event_asset: bool = True
    dry_run: bool = False


async def run_new_ad(
    page: Page,
    settings: AppSettings,
    options: NewAdOptions,
    progress: ProgressCallback | None = None,
) -> None:
    create_ad_url = settings.create_ad_url(options.account_id)
    try:
        async with step(progress, "打开新建广告页"):
            await goto_create_page(page, create_ad_url)

        if options.dry_run:
            async with step(progress, "保存 Dry Run 快照"):
                screenshot_path, html_path = await save_debug_snapshot(
                    page,
                    settings.artifacts.logs_dir,
                    f"new_ad_dry_run_{options.account_id}",
                )
            print(f"create ad URL: {create_ad_url}")
            print(f"dry-run screenshot: {screenshot_path}")
            print(f"dry-run HTML: {html_path}")
            return

        async with step(progress, "检查登录态"):
            await ensure_logged_in(page)
        async with step(progress, "选择字节小游戏"):
            await choose_byte_mini_game(page, options)

        try:
            async with step(progress, "选择优化目标与深度优化目标"):
                await select_optimization_targets(page, options)
        except DeepOptimizationTargetUnavailable as target_error:
            if progress is not None:
                progress(f"{target_error}，开始补充资产与事件。")
            async with step(progress, "添加资产并配置事件"):
                await ensure_event_asset_and_events(page.context, page, settings, options, progress)
            async with step(progress, "返回新建广告页"):
                await goto_create_page(page, create_ad_url)
            async with step(progress, "重新选择字节小游戏"):
                await choose_byte_mini_game(page, options)
            async with step(progress, "选择优化目标与深度优化目标"):
                await select_optimization_targets(page, options)

        async with step(progress, "填写投放身份"):
            await select_douyin_identity(page, options)

        async with step(progress, "填写预算与 ROI"):
            await fill_budget_and_roi(page, options)

        async with step(progress, "设置基础定向"):
            await select_unlimited_targeting(page)

        async with step(progress, "勾选 AIGC 动态创意"):
            await enable_aigc_dynamic_creative(page)

        async with step(progress, "批量添加文案"):
            await batch_add_ad_texts(page, options)

        async with step(progress, "填写落地页链接"):
            await fill_landing_links(page, options)

        async with step(progress, "填写投放组件"):
            await fill_product_card(page, options)

        async with step(progress, "填写项目名称"):
            await fill_project_name(page, options)

        if options.product_image_path.strip():
            async with step(progress, "上传产品主图"):
                await upload_product_main_image(page, options)

        if options.auto_add_videos:
            async with step(progress, "自动添加视频"):
                await auto_add_videos(page, options)

        async with step(progress, "设置原生锚点自动生成"):
            await enable_native_anchor_auto_generate(page)

        async with step(progress, "保存配置后快照"):
            screenshot_path, html_path = await save_debug_snapshot(
                page,
                settings.artifacts.logs_dir,
                f"new_ad_full_configured_{options.account_id}",
            )
        if options.submit_project:
            async with step(progress, "提交项目"):
                await submit_ad_project(page)
        print(f"create ad URL: {create_ad_url}")
        print(f"Configured mini game: {options.mini_game_name}")
        print(f"Configured optimization: {options.optimization_goal} / {options.deep_optimization_goal}")
        print(f"Current screenshot: {screenshot_path}")
        print(f"Current HTML: {html_path}")
    except Exception:
        try:
            screenshot_path, html_path = await save_debug_snapshot(
                page,
                settings.artifacts.logs_dir,
                f"new_ad_failed_{options.account_id}",
            )
        except Exception as snapshot_error:  # noqa: BLE001 - keep the original automation error.
            if progress is not None:
                progress(f"保存失败现场失败：{snapshot_error}")
        else:
            if progress is not None:
                progress(f"已保存失败现场截图：{screenshot_path}")
                progress(f"已保存失败现场 HTML：{html_path}")
        raise


async def goto_create_page(page: Page, url: str) -> None:
    for attempt in range(2):
        try:
            await page.goto(url, wait_until="domcontentloaded")
            break
        except PlaywrightError:
            if "ad/web/std/ad/create" in page.url:
                break
            if attempt == 1:
                raise
            await polite_pause(page, 1200)
    await normalize_page_zoom(page)
    await wait_for_page_ready(page)
    await abandon_unpublished_project_if_prompted(page)
    await expect_unique(page.get_by_text("投放产品与载体", exact=True), "ad create form").wait_for(
        state="visible"
    )


async def choose_byte_mini_game(page: Page, options: NewAdOptions) -> None:
    await click_first_visible(page.get_by_text("字节小游戏", exact=True), "字节小游戏")
    await confirm_pending_modal(page)
    await polite_pause(page, 250)

    choose_button = page.get_by_role("button", name="选择小游戏")
    reselect_button = page.get_by_role("button", name="重新选择")
    if await choose_button.count() == 1:
        await click_unique(choose_button, "选择小游戏")
    elif await reselect_button.count() == 1:
        await click_unique(reselect_button, "重新选择")
    else:
        raise RuntimeError("Cannot find choose/reselect mini game button.")

    await expect_unique(
        page.get_by_placeholder("输入小游戏名称或ID", exact=True),
        "mini game search box",
    ).wait_for(state="visible")
    search_box = page.get_by_placeholder("输入小游戏名称或ID", exact=True)
    await search_box.fill(options.mini_game_name)
    await search_box.press("Enter")
    await page.wait_for_load_state("domcontentloaded")

    row_name = (
        f"{options.mini_game_name} {options.mini_game_asset_id} "
        f"{options.mini_game_app_id} 使用"
    )
    row = page.get_by_role("row", name=row_name)
    await expect_unique(row, "target mini game row").wait_for(state="visible")
    await polite_pause(page, 1000)
    await click_unique(row.get_by_role("button", name="使用"), "target mini game 使用")
    await expect_unique(page.get_by_role("button", name="重新选择"), "reselect mini game").wait_for(
        state="visible"
    )
    await expect(page.get_by_text(options.mini_game_name, exact=True).first).to_be_visible()
    await confirm_pending_modal(page)
    await polite_pause(page, 300)


async def optimization_goal_is_empty(page: Page) -> bool:
    dropdown = await optimization_dropdown(page)
    value = await dropdown.get_attribute("value")
    if value and value.strip():
        return False
    text = (await dropdown.input_value()).strip()
    return text in {"", "请选择"}


async def ensure_event_asset_and_events(
    context: BrowserContext,
    ad_page: Page,
    settings: AppSettings,
    options: NewAdOptions,
    progress: ProgressCallback | None = None,
) -> None:
    async with step(progress, "打开事件管理"):
        event_page = await open_event_manager_page(context, ad_page)
        await normalize_page_zoom(event_page)
        await event_page.wait_for_load_state("domcontentloaded")
        await wait_for_page_ready(event_page)

    async with step(progress, "检查事件资产 ID"):
        current_asset_id = await current_event_asset_id(event_page)
        if progress is not None:
            progress(f"事件管理当前小程序资产 ID：{current_asset_id or '未识别'}")

    added_asset = False
    if current_asset_id != options.mini_game_asset_id:
        async with step(progress, "添加小游戏资产"):
            added_asset = await add_mini_game_event_asset(event_page, options, progress)
    else:
        if progress is not None:
            progress("事件资产 ID 与配置一致，跳过添加资产。")

    async with step(progress, f"添加深度优化事件：{options.deep_optimization_goal}"):
        await add_deep_optimization_event(
            event_page,
            options,
            progress,
            configure_callback=added_asset,
        )
    async with step(progress, "切回广告创建页"):
        await ad_page.bring_to_front()
        await normalize_page_zoom(ad_page)


async def open_optimization_dropdown(page: Page) -> None:
    dropdown = await optimization_dropdown(page)
    await click_select_field(dropdown, page, "optimization selector")
    await polite_pause(page, 300)


async def open_event_manager_page(context: BrowserContext, ad_page: Page) -> Page:
    if await visible_event_manager_box(ad_page):
        event_manager_url = await visible_event_manager_url(ad_page)
        if event_manager_url:
            event_page = await context.new_page()
            await event_page.goto(event_manager_url, wait_until="domcontentloaded")
            await normalize_page_zoom(event_page)
            return event_page
        event_page = await click_event_manager_entry(context, ad_page)
        await event_page.wait_for_load_state("domcontentloaded")
        return event_page

    for description, dropdown_getter in (
        ("深度优化目标", deep_optimization_dropdown),
        ("优化目标", optimization_dropdown),
    ):
        try:
            dropdown = await dropdown_getter(ad_page)
            if await dropdown.count() == 0:
                continue
            await click_select_field(dropdown, ad_page, f"{description} selector")
            await polite_pause(ad_page, 400)
            if not await visible_event_manager_box(ad_page):
                continue
            event_manager_url = await visible_event_manager_url(ad_page)
            if event_manager_url:
                event_page = await context.new_page()
                await event_page.goto(event_manager_url, wait_until="domcontentloaded")
                await normalize_page_zoom(event_page)
                return event_page
            event_page = await click_event_manager_entry(context, ad_page)
            await event_page.wait_for_load_state("domcontentloaded")
            return event_page
        except (PlaywrightTimeoutError, RuntimeError):
            continue

    raise DeepOptimizationTargetUnavailable("找不到事件管理入口")


async def visible_event_manager_url(page: Page) -> str | None:
    return await page.evaluate(
        """() => {
            const isVisible = node => {
                const rect = node.getBoundingClientRect();
                const style = window.getComputedStyle(node);
                return rect.width > 0
                    && rect.height > 0
                    && rect.bottom > 0
                    && rect.top < window.innerHeight
                    && style.display !== 'none'
                    && style.visibility !== 'hidden';
            };
            const nodes = Array.from(document.querySelectorAll('a,button,span,div'));
            const target = nodes.find(node => {
                const text = (node.innerText || node.textContent || '').replace(/\\s+/g, ' ').trim();
                return text === '事件管理' && isVisible(node);
            });
            const anchor = target?.closest?.('a[href]');
            if (!anchor) return null;
            return anchor.href || null;
        }"""
    )


async def visible_event_manager_box(page: Page) -> dict[str, float] | None:
    return await page.evaluate(
        """() => {
            const isVisible = node => {
                const rect = node.getBoundingClientRect();
                const style = window.getComputedStyle(node);
                return rect.width > 0
                    && rect.height > 0
                    && rect.bottom > 0
                    && rect.top < window.innerHeight
                    && style.display !== 'none'
                    && style.visibility !== 'hidden';
            };
            const nodes = Array.from(document.querySelectorAll('a,button,span,div'));
            const target = nodes.find(node => {
                const text = (node.innerText || node.textContent || '').replace(/\\s+/g, ' ').trim();
                return text === '事件管理' && isVisible(node);
            });
            if (!target) return null;
            const clickable = target.closest('a,button,[role="button"],.oc-msg-list__item-a') || target;
            const rect = clickable.getBoundingClientRect();
            return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2 };
        }"""
    )


async def click_event_manager_entry(context: BrowserContext, ad_page: Page) -> Page:
    pages_before = set(context.pages)
    url_before = ad_page.url
    box = await visible_event_manager_box(ad_page)
    if not box:
        raise DeepOptimizationTargetUnavailable("找不到事件管理入口")

    try:
        async with context.expect_page(timeout=8_000) as event_page_info:
            await ad_page.mouse.click(box["x"], box["y"])
        return await event_page_info.value
    except PlaywrightTimeoutError:
        pass

    await polite_pause(ad_page, 500)
    new_pages = [page for page in context.pages if page not in pages_before]
    if new_pages:
        return new_pages[-1]
    if ad_page.url != url_before:
        return ad_page

    box = await visible_event_manager_box(ad_page)
    if not box:
        raise DeepOptimizationTargetUnavailable("事件管理入口点击后没有打开页面")
    await ad_page.mouse.click(box["x"], box["y"])
    await polite_pause(ad_page, 800)
    new_pages = [page for page in context.pages if page not in pages_before]
    if new_pages:
        return new_pages[-1]
    if ad_page.url != url_before:
        return ad_page
    raise DeepOptimizationTargetUnavailable("事件管理入口点击后没有打开页面")


async def optimization_dropdown(page: Page) -> Locator:
    return input_near_label(page, "优化目标", readonly=True)


async def deep_optimization_dropdown(page: Page) -> Locator:
    return input_near_label(page, "深度优化目标", readonly=True)


async def current_event_asset_id(event_page: Page) -> str | None:
    return await event_page.evaluate(
        """() => {
            const isVisible = node => {
                const rect = node.getBoundingClientRect();
                const style = window.getComputedStyle(node);
                return rect.width > 0
                    && rect.height > 0
                    && style.display !== 'none'
                    && style.visibility !== 'hidden';
            };
            const activeCards = Array.from(document.querySelectorAll('a,div,section'))
                .filter(node => isVisible(node)
                    && /active|selected|checked|current/i.test(node.className?.toString?.() || ''));
            const activeText = activeCards.map(node => node.innerText || node.textContent || '').join('\\n');
            const activeMatch = activeText.match(/小程序资产ID[：:\\s]*([0-9]{10,})/);
            if (activeMatch) return activeMatch[1];

            const bodyText = document.body.innerText || '';
            const explicitMatch = bodyText.match(/小程序资产ID[：:\\s]*([0-9]{10,})/);
            if (explicitMatch) return explicitMatch[1];
            return null;
        }"""
    )


async def event_exists(event_page: Page, event_name: str) -> bool:
    return await event_page.evaluate(
        """eventName => {
            const isVisible = node => {
                const rect = node.getBoundingClientRect();
                const style = window.getComputedStyle(node);
                return rect.width > 0
                    && rect.height > 0
                    && style.display !== 'none'
                    && style.visibility !== 'hidden';
            };
            const rows = Array.from(document.querySelectorAll('.byted-table-row, tr, [role="row"]'));
            return rows.some(row => {
                if (!isVisible(row)) return false;
                const cells = Array.from(row.querySelectorAll('.byted-table-cell, td, [role="cell"], span, div'))
                    .filter(isVisible)
                    .map(cell => (cell.innerText || cell.textContent || '').replace(/\\s+/g, ' ').trim())
                    .filter(Boolean);
                const firstExact = cells.some(text => text === eventName);
                const apiCallback = cells.some(text => text === '小程序API回传' || text.includes('小程序API回传'));
                return firstExact && apiCallback;
            });
        }""",
        event_name,
    )


async def add_mini_game_event_asset(
    event_page: Page,
    options: NewAdOptions,
    progress: ProgressCallback | None = None,
) -> bool:
    async with step(progress, "点击添加资产"):
        await suppress_obstructive_overlays(event_page)
        await expect_unique(event_page.get_by_role("button", name="添加资产"), "添加资产").wait_for(
            state="visible"
        )
        await click_unique(event_page.get_by_role("button", name="添加资产"), "添加资产")
        drawer = event_page.locator(".byted-drawer-dialog")
        await expect_unique(drawer, "add asset drawer").wait_for(state="visible")

    async with step(progress, "资产类型选择小程序"):
        await suppress_obstructive_overlays(event_page)
        await click_drawer_card_by_text(event_page, "小程序")
        await click_unique(drawer.get_by_role("button", name="下一步"), "asset next")
        await polite_pause(event_page, 300)

    async with step(progress, "资产类别选择小游戏"):
        category = drawer.get_by_placeholder("类别", exact=True)
        await expect_unique(category, "asset category").wait_for(state="visible")
        await click_select_by_placeholder(drawer, event_page, "类别")
        await polite_pause(event_page)
        await click_unique(
            event_page.locator(".byted-select-option, .ovui-option").filter(
                has_text="小游戏", visible=True
            ),
            "category 小游戏",
        )
        await polite_pause(event_page)

    async with step(progress, "搜索并选择小游戏资产"):
        search_box = drawer.get_by_placeholder("搜索小程序名称或ID", exact=True)
        await expect_unique(search_box, "asset id search").wait_for(state="visible")
        await search_box.fill(options.mini_game_asset_id)
        await trigger_search(search_box, event_page)
        if await current_mini_program_already_added(event_page):
            await close_visible_drawer(event_page)
            return False
        await wait_for_text_in_visible_node(event_page, options.mini_game_asset_id, timeout_ms=15_000)

        await click_asset_card_by_id(event_page, options.mini_game_asset_id)

    async with step(progress, "确认添加小游戏资产"):
        if await current_mini_program_already_added(event_page):
            await close_visible_drawer(event_page)
            return False
        add_button = drawer.get_by_role("button", name="添加")
        await expect(add_button).to_be_enabled()
        await click_unique(add_button, "add asset confirm")
        await event_page.wait_for_function(
            """() => {
                const text = document.body?.innerText || '';
                return text.includes('立即添加事件')
                    || text.includes('添加小程序成功')
                    || text.includes('当前小程序已添加');
            }""",
            timeout=8_000,
        )

        if await event_page.get_by_role("button", name="立即添加事件").count() == 0:
            await expect(event_page.get_by_text("添加小程序成功", exact=True)).to_be_visible()
        return True


async def suppress_obstructive_overlays(page: Page) -> None:
    await page.evaluate(
        """() => {
            const selectors = [
                '.copilot-layout',
                '[id*="copilot"]',
                '[class*="copilot"]',
                '.floating-ball',
                '.byted-tooltip',
                '.byted-tooltip-inner',
                '.ovui-tooltip',
                '[role="tooltip"]',
            ];
            for (const selector of selectors) {
                for (const node of document.querySelectorAll(selector)) {
                    if (node instanceof HTMLElement) {
                        node.style.pointerEvents = 'none';
                    }
                }
            }
        }"""
    )


async def click_drawer_card_by_text(page: Page, text: str) -> None:
    clicked = await page.evaluate(
        """text => {
            const isVisible = node => {
                const rect = node.getBoundingClientRect();
                const style = window.getComputedStyle(node);
                return rect.width > 0
                    && rect.height > 0
                    && rect.bottom > 0
                    && rect.top < window.innerHeight
                    && style.display !== 'none'
                    && style.visibility !== 'hidden';
            };
            const drawer = Array.from(document.querySelectorAll('.byted-drawer-dialog'))
                .find(isVisible);
            if (!drawer) return false;
            const nodes = Array.from(drawer.querySelectorAll('div,button,label,li'));
            const title = nodes.find(node => {
                const value = (node.innerText || node.textContent || '').replace(/\\s+/g, ' ').trim();
                return value === text && isVisible(node);
            });
            if (!title) return false;
            const card = title.closest('[class*="asset-list-item"], label, button, li') || title;
            const rect = card.getBoundingClientRect();
            const blocker = document.elementFromPoint(rect.x + rect.width / 2, rect.y + rect.height / 2);
            if (blocker && !drawer.contains(blocker) && blocker instanceof HTMLElement) {
                blocker.style.pointerEvents = 'none';
            }
            card.click();
            return true;
        }""",
        text,
    )
    if not clicked:
        raise RuntimeError(f"Cannot find drawer card: {text}")


async def click_asset_card_by_id(page: Page, asset_id: str) -> None:
    card = page.locator(".styles-module__asset-list-item--zVGoE").filter(
        has_text=asset_id, visible=True
    )
    if await card.count() >= 1:
        await card.first.click()
        return

    # Fallback for class-name churn: click the visible text card area by JS geometry.
    box = await page.evaluate(
        """assetId => {
            const candidates = Array.from(document.querySelectorAll('div,section,article,label'));
            const el = candidates.find(node => {
                const text = (node.innerText || node.textContent || '').replace(/\\s+/g, ' ').trim();
                const rect = node.getBoundingClientRect();
                return text.includes(assetId) && rect.width > 80 && rect.height > 40;
            });
            if (!el) return null;
            const rect = el.getBoundingClientRect();
            return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2 };
        }""",
        asset_id,
    )
    if not box:
        raise RuntimeError(f"Cannot find mini game asset card for {asset_id}.")
    await page.mouse.click(box["x"], box["y"])


async def trigger_search(search_box: Locator, page: Page) -> None:
    await search_box.press("Enter")
    await polite_pause(page, 500)

    wrapper = search_box.locator(
        "xpath=ancestor::*[contains(@class, 'byted-input') "
        "or contains(@class, 'ovui-input') "
        "or contains(@class, 'input')][1]"
    )
    if await wrapper.count() >= 1:
        triggers = wrapper.first.locator(
            "button, .byted-input-inner__suffix, .ovui-input__suffix, iconpark-icon"
        )
        for index in range(await triggers.count()):
            candidate = triggers.nth(index)
            try:
                title = " ".join(
                    filter(
                        None,
                        [
                            await candidate.get_attribute("aria-label"),
                            await candidate.get_attribute("title"),
                            await candidate.get_attribute("name"),
                            await candidate.get_attribute("class"),
                        ],
                    )
                )
                if any(key in title.lower() for key in ["search", "sousuo", "搜索"]):
                    await candidate.click(timeout=1_000)
                    break
            except PlaywrightTimeoutError:
                continue
    await polite_pause(page, 2500)


async def wait_for_text_in_visible_node(page: Page, text: str, timeout_ms: int = 10_000) -> None:
    await page.wait_for_function(
        """needle => {
            const nodes = Array.from(document.querySelectorAll('body *'));
            return nodes.some(node => {
                const value = (node.innerText || node.textContent || '').replace(/\\s+/g, ' ').trim();
                if (!value.includes(needle)) return false;
                const style = window.getComputedStyle(node);
                const rect = node.getBoundingClientRect();
                return style.visibility !== 'hidden'
                    && style.display !== 'none'
                    && rect.width > 0
                    && rect.height > 0;
            });
        }""",
        arg=text,
        timeout=timeout_ms,
    )


async def wait_for_texts_in_same_visible_node(
    page: Page,
    texts: list[str],
    timeout_ms: int = 10_000,
) -> None:
    await page.wait_for_function(
        """needles => {
            const nodes = Array.from(document.querySelectorAll('body *'));
            return nodes.some(node => {
                const value = (node.innerText || node.textContent || '').replace(/\\s+/g, ' ').trim();
                if (!needles.every(needle => value.includes(needle))) return false;
                const style = window.getComputedStyle(node);
                const rect = node.getBoundingClientRect();
                return style.visibility !== 'hidden'
                    && style.display !== 'none'
                    && rect.width > 0
                    && rect.height > 0;
            });
        }""",
        arg=texts,
        timeout=timeout_ms,
    )


async def click_select_by_placeholder(root: Locator, page: Page, placeholder: str) -> None:
    field = root.get_by_placeholder(placeholder, exact=True)
    await click_select_field(field, page, f"{placeholder} selector")


async def click_select_field(field: Locator, page: Page, description: str) -> None:
    await expect_unique(field, description).wait_for(state="visible")
    wrappers = field.locator(
        "xpath=ancestor::*[contains(@class, 'byted-select') "
        "or contains(@class, 'ovui-select') "
        "or contains(@class, 'byted-input-inner__wrapper')][1]"
    )
    if await wrappers.count() >= 1:
        try:
            await wrappers.first.click(timeout=3_000)
            return
        except PlaywrightTimeoutError:
            pass

    box = await field.evaluate(
        """node => {
            const selectors = [
                '.byted-select',
                '.ovui-select',
                '.byted-input-inner__wrapper',
                'label',
            ];
            let el = node;
            while (el) {
                if (selectors.some(selector => el.matches && el.matches(selector))) {
                    const rect = el.getBoundingClientRect();
                    return { x: rect.x + rect.width - 18, y: rect.y + rect.height / 2 };
                }
                el = el.parentElement;
            }
            const rect = node.getBoundingClientRect();
            return { x: rect.x + rect.width - 18, y: rect.y + rect.height / 2 };
        }"""
    )
    await page.mouse.click(box["x"], box["y"])


def section_after_text(page: Page, text: str) -> Locator:
    text_literal = xpath_literal(text)
    return page.locator(
        f"xpath=//*[normalize-space()={text_literal}]/ancestor::*"
        "[contains(@class,'subModuleContainer') or contains(@class,'moduleContainer') "
        "or contains(@class,'oc-row')][1]"
    )


async def scroll_text_into_view(page: Page, text: str) -> None:
    locator = page.get_by_text(text, exact=True)
    for index in range(await locator.count()):
        candidate = locator.nth(index)
        try:
            if await candidate.is_visible(timeout=300):
                await candidate.scroll_into_view_if_needed()
                await polite_pause(page, 500)
                return
        except PlaywrightTimeoutError:
            continue

    scrolled = await page.evaluate(
        """needle => {
            const nodes = Array.from(document.querySelectorAll('body *'));
            const target = nodes.find(node => {
                const value = (node.innerText || node.textContent || '').replace(/\\s+/g, ' ').trim();
                const rect = node.getBoundingClientRect();
                const style = window.getComputedStyle(node);
                return value === needle
                    && rect.width > 0
                    && rect.height > 0
                    && style.display !== 'none'
                    && style.visibility !== 'hidden';
            });
            if (!target) return false;
            target.scrollIntoView({ block: 'center', inline: 'nearest' });
            return true;
        }""",
        text,
    )
    if not scrolled:
        await expect(locator.first).to_be_visible()
    await polite_pause(page, 500)


async def fill_text_control(locator: Locator, value: str) -> None:
    await locator.click()
    await locator.press("Control+A")
    try:
        await locator.fill(value, timeout=2_000)
    except PlaywrightTimeoutError:
        await locator.press("Backspace")
        await locator.page.keyboard.insert_text(value)


async def paste_text(page: Page, value: str) -> None:
    try:
        await page.evaluate("text => navigator.clipboard.writeText(text)", value)
        await page.keyboard.press("Control+V")
    except Exception:
        await page.keyboard.insert_text(value)


async def fill_first_visible_input(page: Page, placeholder: str, value: str) -> None:
    fields = page.get_by_placeholder(placeholder, exact=True)
    for index in range(await fields.count()):
        field = fields.nth(index)
        try:
            if await field.is_visible(timeout=500):
                await fill_text_control(field, value)
                await field.press("Enter")
                return
        except PlaywrightTimeoutError:
            continue

    box = await page.evaluate(
        """placeholder => {
            const inputs = Array.from(document.querySelectorAll('input,textarea'));
            const el = inputs.find(node => {
                const rect = node.getBoundingClientRect();
                const style = window.getComputedStyle(node);
                return node.getAttribute('placeholder') === placeholder
                    && rect.width > 0
                    && rect.height > 0
                    && style.display !== 'none'
                    && style.visibility !== 'hidden';
            });
            if (!el) return null;
            const rect = el.getBoundingClientRect();
            return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2 };
        }""",
        placeholder,
    )
    if not box:
        raise RuntimeError(f"Cannot find visible input with placeholder {placeholder}.")
    await page.mouse.click(box["x"], box["y"])
    await page.keyboard.press("Control+A")
    await page.keyboard.insert_text(value)
    await page.keyboard.press("Enter")


async def fill_input_near_label(page: Page, label: str, value: str) -> None:
    field = input_near_label(page, label)
    await expect(field).to_be_visible()
    await fill_text_control(field, value)
    await polite_pause(page, 300)


async def fill_visible_input_near_label(page: Page, label: str, value: str) -> None:
    label_literal = xpath_literal(label)
    row = page.locator(
        f"xpath=//*[normalize-space()={label_literal}]/ancestor::*[contains(@class,'oc-row')][1]"
    )
    for index in range(await row.count()):
        candidate_row = row.nth(index)
        try:
            if not await candidate_row.is_visible(timeout=300):
                continue
            field = candidate_row.locator("input:not([readonly]), textarea:not([readonly])").first
            if await field.count() == 0 or not await field.is_visible(timeout=300):
                continue
            await fill_text_control(field, value)
            await expect(field).to_have_value(value)
            await polite_pause(page, 300)
            return
        except PlaywrightTimeoutError:
            continue
    raise RuntimeError(f"Cannot find visible editable input near {label}.")


async def fill_main_form_input_near_label(page: Page, label: str, value: str) -> None:
    filled = await page.evaluate(
        """({ label, value }) => {
            const isVisible = node => {
                const rect = node.getBoundingClientRect();
                const style = window.getComputedStyle(node);
                return rect.width > 0
                    && rect.height > 0
                    && rect.bottom > 0
                    && rect.top < window.innerHeight
                    && style.display !== 'none'
                    && style.visibility !== 'hidden';
            };
            const isMainEditor = node => {
                const center = node.closest('[data-auto-id="pageLayoutCenter"], .pageLayoutCenter-jFAaNr');
                const right = node.closest('[data-auto-id="rightLayout"], .pageLayoutRightWrapper-lmIAeh');
                const popper = node.closest('.ovui-select__popper, .oc-select__popover, .byted-select-dropdown, [role="dialog"]');
                return Boolean(center) && !right && !popper;
            };
            const rows = Array.from(document.querySelectorAll('.oc-row'))
                .filter(node => isVisible(node) && isMainEditor(node))
                .filter(node => (node.innerText || node.textContent || '').replace(/\\s+/g, ' ').trim().includes(label));
            const row = rows.find(node => {
                const inputs = Array.from(node.querySelectorAll('input:not([readonly]), textarea:not([readonly])'));
                return inputs.some(input => isVisible(input) && !input.disabled);
            });
            if (!row) return false;
            row.scrollIntoView({ block: 'center', inline: 'nearest' });
            const input = Array.from(row.querySelectorAll('input:not([readonly]), textarea:not([readonly])'))
                .find(node => isVisible(node) && !node.disabled);
            if (!input) return false;
            input.focus();
            input.value = '';
            input.dispatchEvent(new Event('input', { bubbles: true }));
            input.value = value;
            input.dispatchEvent(new Event('input', { bubbles: true }));
            input.dispatchEvent(new Event('change', { bubbles: true }));
            input.blur();
            return true;
        }""",
        {"label": label, "value": value},
    )
    if not filled:
        raise RuntimeError(f"Cannot find visible main form input near {label}.")

    await page.wait_for_function(
        """({ label, value }) => {
            const isVisible = node => {
                const rect = node.getBoundingClientRect();
                const style = window.getComputedStyle(node);
                return rect.width > 0
                    && rect.height > 0
                    && style.display !== 'none'
                    && style.visibility !== 'hidden';
            };
            const rows = Array.from(document.querySelectorAll('.oc-row'))
                .filter(node => isVisible(node)
                    && node.closest('[data-auto-id="pageLayoutCenter"], .pageLayoutCenter-jFAaNr')
                    && !node.closest('[data-auto-id="rightLayout"], .pageLayoutRightWrapper-lmIAeh')
                    && !node.closest('.ovui-select__popper, .oc-select__popover, .byted-select-dropdown, [role="dialog"]'))
                .filter(node => (node.innerText || node.textContent || '').replace(/\\s+/g, ' ').trim().includes(label));
            return rows.some(row => Array.from(row.querySelectorAll('input:not([readonly]), textarea:not([readonly])'))
                .some(input => isVisible(input) && input.value === value));
        }""",
        arg={"label": label, "value": value},
        timeout=3_000,
    )
    await polite_pause(page, 300)


def input_near_label(page: Page, label: str, readonly: bool = False) -> Locator:
    label_literal = xpath_literal(label)
    readonly_predicate = "" if readonly else "[not(@readonly)]"
    return page.locator(
        f"xpath=//*[normalize-space()={label_literal}]/ancestor::*[contains(@class,'oc-row')][1]"
        f"//*[self::input or self::textarea]{readonly_predicate}[1]"
    ).first


async def fill_multi_value_input_near_label(
    page: Page,
    label: str,
    value: str,
    clear_existing: bool = False,
) -> None:
    label_literal = xpath_literal(label)
    row = page.locator(
        f"xpath=//*[normalize-space()={label_literal}]/ancestor::*[contains(@class,'oc-row')][1]"
    ).first
    await expect(row).to_be_visible()
    if clear_existing:
        await clear_multi_value_tags(page, row)
    field = row.locator("input:not([readonly]), textarea").first
    await expect(field).to_be_visible()
    await field.click()
    await field.fill(value)
    await field.press("Enter")
    await polite_pause(page, 500)


async def clear_multi_value_tags(page: Page, row: Locator) -> None:
    for _ in range(20):
        close_buttons = row.locator(".ovui-tag__close, .byted-tag-close, [class*='tag__close']")
        clicked = False
        for index in range(await close_buttons.count()):
            close_button = close_buttons.nth(index)
            try:
                if await close_button.is_visible(timeout=300):
                    await close_button.click(timeout=1_000)
                    clicked = True
                    await polite_pause(page, 200)
                    break
            except PlaywrightTimeoutError:
                continue
        if not clicked:
            break


async def click_row_option(page: Page, label: str, option: str) -> None:
    label_literal = xpath_literal(label)
    row = page.locator(
        f"xpath=//*[normalize-space()={label_literal}]/ancestor::*[contains(@class,'oc-row')][1]"
    ).first
    await expect(row).to_be_visible()
    await click_first_visible(row.get_by_text(option, exact=True), f"{label} {option}")


async def click_option_by_text(page: Page, text: str, description: str) -> None:
    await confirm_pending_modal(page)
    option = page.locator(".ovui-option, .byted-select-option, [role='option']").filter(
        has_text=text,
        visible=True,
    )
    if await option.count() >= 1:
        await option.first.click()
        return
    box = await page.evaluate(
        """needle => {
            const candidates = Array.from(document.querySelectorAll('.ovui-option, .byted-select-option, [role="option"], div, span'));
            const el = candidates.find(node => {
                const value = (node.innerText || node.textContent || '').replace(/\\s+/g, ' ').trim();
                const rect = node.getBoundingClientRect();
                const style = window.getComputedStyle(node);
                return value === needle
                    && rect.width > 0
                    && rect.height > 0
                    && style.display !== 'none'
                    && style.visibility !== 'hidden';
            });
            if (!el) return null;
            const clickable = el.closest('.ovui-option, .byted-select-option, [role="option"]') || el;
            const rect = clickable.getBoundingClientRect();
            return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2 };
        }""",
        text,
    )
    if box:
        await page.mouse.click(box["x"], box["y"])
        return
    await click_first_visible(page.get_by_text(text, exact=True), description)


async def click_node_containing_all(page: Page, texts: list[str], description: str) -> None:
    box = await page.evaluate(
        """texts => {
            const preferred = Array.from(document.querySelectorAll('.ovui-option, .byted-select-option, [role="option"], .oc-item-group, li, tr'));
            const fallback = Array.from(document.querySelectorAll('div,label,section'));
            const candidates = preferred.concat(fallback);
            const el = candidates.find(node => {
                const value = (node.innerText || node.textContent || '').replace(/\\s+/g, ' ').trim();
                const rect = node.getBoundingClientRect();
                return texts.every(text => value.includes(text))
                    && rect.width > 50
                    && rect.height > 20
                    && window.getComputedStyle(node).display !== 'none'
                    && window.getComputedStyle(node).visibility !== 'hidden';
            });
            if (!el) return null;
            const rect = el.getBoundingClientRect();
            return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2 };
        }""",
        texts,
    )
    if not box:
        raise RuntimeError(f"Cannot find {description}.")
    await page.mouse.click(box["x"], box["y"])


async def click_douyin_account_selector(page: Page) -> None:
    selector_text = page.get_by_text("请选择抖音号", exact=True).first
    if await selector_text.count() >= 1:
        box = await selector_text.evaluate(
            """node => {
                const clickable = node.closest('.ovui-select, .ovui-custom-input, .oc-select, .oc-row-content') || node;
                const rect = clickable.getBoundingClientRect();
                return { x: rect.x + rect.width - 18, y: rect.y + rect.height / 2 };
            }"""
        )
        await page.mouse.click(box["x"], box["y"])
        return

    field = input_near_label(page, "选择身份", readonly=True)
    await click_select_field(field, page, "douyin account selector")


async def click_douyin_account_result(page: Page, options: NewAdOptions) -> None:
    for attempt in range(10):
        found = await page.evaluate(
            """({ name, id }) => {
                const isVisible = node => {
                    const rect = node.getBoundingClientRect();
                    const style = window.getComputedStyle(node);
                    return rect.width > 0 && rect.height > 0
                        && rect.bottom > 0 && rect.top < window.innerHeight
                        && style.display !== 'none'
                        && style.visibility !== 'hidden';
                };
                const clean = node => (node.innerText || node.textContent || '').replace(/\\s+/g, ' ').trim();
                const poppers = Array.from(document.querySelectorAll(
                    '.ovui-select__popper, .oc-select__popover, .byted-select-dropdown, [class*="popover"], [class*="popper"]'
                ))
                    .filter(isVisible)
                    .filter(node => {
                        const text = clean(node);
                        return text.includes('请输入抖音ID') || text.includes(id) || text.includes(name);
                    });
                for (const popper of poppers) {
                    const candidates = Array.from(popper.querySelectorAll(
                        '.ovui-option, .byted-select-option, [role="option"], .oc-item-group, li, tr'
                    )).filter(isVisible);
                    const exactTarget = candidates.find(node => {
                        const value = clean(node);
                        return value.includes(id)
                            && value.includes(name);
                    });
                    const target = exactTarget || candidates.find(node => {
                        const value = clean(node);
                        return value.includes(id) || value.includes(name);
                    });
                    if (target) {
                        const clickable = target.closest('.ovui-option, .byted-select-option, .oc-item-group, [role="option"], li, tr')
                            || target;
                        clickable.scrollIntoView({ block: 'center', inline: 'nearest' });
                        return true;
                    }
                }
                return false;
            }""",
            {"name": options.douyin_name, "id": options.douyin_id},
        )
        if found:
            await polite_pause(page, 1000)
            clicked = await page.evaluate(
                """({ name, id }) => {
                    const isVisible = node => {
                        const rect = node.getBoundingClientRect();
                        const style = window.getComputedStyle(node);
                        return rect.width > 0 && rect.height > 0
                            && rect.bottom > 0 && rect.top < window.innerHeight
                            && style.display !== 'none'
                            && style.visibility !== 'hidden';
                    };
                    const clean = node => (node.innerText || node.textContent || '').replace(/\\s+/g, ' ').trim();
                    const poppers = Array.from(document.querySelectorAll(
                        '.ovui-select__popper, .oc-select__popover, .byted-select-dropdown, [class*="popover"], [class*="popper"]'
                    ))
                        .filter(isVisible)
                        .filter(node => {
                            const text = clean(node);
                            return text.includes('请输入抖音ID') || text.includes(id) || text.includes(name);
                        });
                    for (const popper of poppers) {
                        const candidates = Array.from(popper.querySelectorAll(
                            '.ovui-option, .byted-select-option, [role="option"], .oc-item-group, li, tr'
                        )).filter(isVisible);
                        const target = candidates.find(node => {
                            const value = clean(node);
                            return value.includes(id) && value.includes(name);
                        }) || candidates.find(node => {
                            const value = clean(node);
                            return value.includes(id) || value.includes(name);
                        });
                        if (!target) continue;
                        const clickable = target.closest('.ovui-option, .byted-select-option, .oc-item-group, [role="option"], li, tr')
                            || target;
                        for (const type of ['pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click']) {
                            clickable.dispatchEvent(new MouseEvent(type, { bubbles: true, cancelable: true, view: window }));
                        }
                        return true;
                    }
                    return false;
                }""",
                {"name": options.douyin_name, "id": options.douyin_id},
            )
            if not clicked:
                continue
            await polite_pause(page, 800)
            if await is_douyin_identity_selected(page, options):
                return

        scrolled = await page.evaluate(
            """({ name, id }) => {
                const poppers = Array.from(document.querySelectorAll(
                    '.ovui-select__popper, .oc-select__popover, .byted-select-dropdown, [class*="popover"], [class*="popper"]'
                ))
                    .filter(node => {
                        const rect = node.getBoundingClientRect();
                        const style = window.getComputedStyle(node);
                        return rect.width > 0 && rect.height > 0
                            && style.display !== 'none'
                            && style.visibility !== 'hidden';
                    });
                const popper = poppers.find(node => {
                    const text = (node.innerText || node.textContent || '');
                    return text.includes(id) || text.includes(name);
                }) || poppers[0];
                if (!popper) return false;
                const scroller = popper.querySelector('.ovui-select__options, [class*="options"]') || popper;
                const before = scroller.scrollTop;
                scroller.scrollTop = before + 220;
                return scroller.scrollTop !== before || Boolean(popper);
            }""",
            {"name": options.douyin_name, "id": options.douyin_id},
        )
        if not scrolled:
            break
        await polite_pause(page, 500)

    raise RuntimeError("Cannot find douyin account result.")


async def is_douyin_identity_selected(page: Page, options: NewAdOptions) -> bool:
    return bool(
        await page.evaluate(
            """({ name, id }) => {
                const isVisible = node => {
                    const rect = node.getBoundingClientRect();
                    const style = window.getComputedStyle(node);
                    return rect.width > 0
                        && rect.height > 0
                        && rect.bottom > 0
                        && rect.top < window.innerHeight
                        && style.display !== 'none'
                        && style.visibility !== 'hidden';
                };
                const row = Array.from(document.querySelectorAll('.oc-row, [class*="row"], section, div'))
                    .filter(isVisible)
                    .find(node => {
                        const text = (node.innerText || node.textContent || '').replace(/\\s+/g, ' ').trim();
                        return text.includes('投放身份') || text.includes('选择身份') || text.includes('抖音号');
                    });
                if (!row) return false;
                const text = (row.innerText || row.textContent || '').replace(/\\s+/g, ' ').trim();
                return text.includes(name) || text.includes(id);
            }""",
            {"name": options.douyin_name, "id": options.douyin_id},
        )
    )


async def wait_for_douyin_identity_selected(page: Page, options: NewAdOptions) -> None:
    try:
        await page.wait_for_function(
            """({ name, id }) => {
                const isVisible = node => {
                    const rect = node.getBoundingClientRect();
                    const style = window.getComputedStyle(node);
                    return rect.width > 0
                        && rect.height > 0
                        && style.display !== 'none'
                        && style.visibility !== 'hidden';
                };
                const rows = Array.from(document.querySelectorAll('.oc-row, [class*="row"], section, div'))
                    .filter(isVisible);
                return rows.some(node => {
                    const text = (node.innerText || node.textContent || '').replace(/\\s+/g, ' ').trim();
                    return (text.includes('投放身份') || text.includes('选择身份') || text.includes('抖音号'))
                        && (text.includes(name) || text.includes(id));
                });
            }""",
            arg={"name": options.douyin_name, "id": options.douyin_id},
            timeout=5_000,
        )
    except PlaywrightTimeoutError as exc:
        raise RuntimeError(
            f"抖音号未正常选中：期望 {options.douyin_name} / {options.douyin_id}"
        ) from exc


async def is_douyin_search_popover_open(page: Page) -> bool:
    return bool(
        await page.evaluate(
            """() => {
                const isVisible = node => {
                    const rect = node.getBoundingClientRect();
                    const style = window.getComputedStyle(node);
                    return rect.width > 0
                        && rect.height > 0
                        && rect.bottom > 0
                        && rect.top < window.innerHeight
                        && style.display !== 'none'
                        && style.visibility !== 'hidden';
                };
                return Array.from(document.querySelectorAll(
                    '.ovui-select__popper, .oc-select__popover, .byted-select-dropdown, [class*="popover"], [class*="popper"]'
                ))
                    .filter(isVisible)
                    .some(node => {
                        const text = (node.innerText || node.textContent || '').replace(/\\s+/g, ' ').trim();
                        return text.includes('请输入抖音ID') || Boolean(node.querySelector('input[placeholder="请输入抖音ID"]'));
                    });
            }"""
        )
    )


async def close_douyin_search_popover(page: Page) -> None:
    for _ in range(4):
        if not await is_douyin_search_popover_open(page):
            return
        await page.keyboard.press("Escape")
        await polite_pause(page, 500)

    if await is_douyin_search_popover_open(page):
        await page.mouse.click(20, 20)
        await polite_pause(page, 500)

    if await is_douyin_search_popover_open(page):
        raise RuntimeError("抖音号搜索弹层未关闭，后续输入可能会被弹层截获。")


async def fill_backup_site_link(page: Page, url: str) -> None:
    row = page.locator(
        "xpath=//*[normalize-space()='备用网页链接']/ancestor::*[contains(@class,'oc-row')][1]"
    ).first
    await expect(row).to_be_visible()
    input_box = row.locator("input").first
    if await input_box.count() >= 1:
        try:
            await input_box.fill(url, timeout=2_000)
            await polite_pause(page, 500)
            return
        except PlaywrightTimeoutError:
            pass

    select_button = row.get_by_text("选择", exact=True).first
    await click_first_visible(select_button, "备用网页链接选择")
    dialog = page.locator(".ovui-modal, .byted-modal, [role='dialog']").last
    await expect(dialog).to_be_visible()
    field = dialog.locator("input:not([readonly]), textarea").first
    await expect(field).to_be_visible()
    await fill_text_control(field, url)
    await polite_pause(page, 500)
    confirm = dialog.get_by_role("button", name="确定")
    if await confirm.count() == 0:
        confirm = dialog.get_by_role("button", name="选择")
    await click_first_visible(confirm, "备用网页链接确认")
    await expect(dialog).to_be_hidden(timeout=5_000)


async def confirm_pending_modal(page: Page) -> None:
    if await abandon_unpublished_project_if_prompted(page):
        return

    modal = page.locator(".ovui-modal, .byted-modal, [role='dialog']").filter(
        has_text="提示",
        visible=True,
    )
    if await modal.count() == 0:
        modal = page.locator(".ovui-modal, .byted-modal, [role='dialog']").filter(
            has_text="是否继续",
            visible=True,
        )
    if await modal.count() == 0:
        return

    for button_name in ("确认", "继续编辑", "确定"):
        button = modal.first.get_by_role("button", name=button_name)
        if await button.count() >= 1:
            await button.first.click()
            await polite_pause(page, 400)
            return


async def abandon_unpublished_project_if_prompted(page: Page) -> bool:
    modal = page.locator(".ovui-modal, .byted-modal, [role='dialog']").filter(
        has_text="未发布的项目信息",
        visible=True,
    )
    if await modal.count() == 0:
        modal = page.locator(".ovui-modal, .byted-modal, [role='dialog']").filter(
            has_text="继续编辑",
            visible=True,
        )
    if await modal.count() == 0:
        return False

    abandon = modal.first.get_by_role("button", name="放弃编辑")
    if await abandon.count() >= 1:
        await abandon.first.click()
        await polite_pause(page, 500)
        return True
    return False


async def current_mini_program_already_added(page: Page) -> bool:
    marker = page.get_by_text("当前小程序已添加", exact=True)
    return await marker.count() > 0 and await marker.first.is_visible(timeout=500)


async def close_visible_drawer(page: Page) -> None:
    drawer = page.locator(".byted-drawer-dialog, .ovui-drawer, [role='dialog']").last
    if await drawer.count() == 0:
        return
    close_buttons = drawer.locator(
        ".byted-drawer-close, .ovui-drawer__close, .ovui-modal__close-icon, "
        "button:has-text('关闭'), iconpark-icon[name='close']"
    )
    if await close_buttons.count() >= 1:
        await close_buttons.first.click()
        await polite_pause(page, 400)


def xpath_literal(value: str) -> str:
    if "'" not in value:
        return f"'{value}'"
    if '"' not in value:
        return f'"{value}"'
    parts = value.split("'")
    return "concat(" + ', "\"\'\"", '.join(f"'{part}'" for part in parts) + ")"


async def add_deep_optimization_event(
    event_page: Page,
    options: NewAdOptions,
    progress: ProgressCallback | None = None,
    configure_callback: bool = False,
) -> None:
    if await event_exists(event_page, options.deep_optimization_goal):
        if progress is not None:
            progress(f"事件已存在：{options.deep_optimization_goal}，跳过添加。")
        return

    async with step(progress, "点击立即添加事件"):
        add_now = event_page.get_by_role("button", name="立即添加事件")
        if await add_now.count() == 1:
            await click_unique(add_now, "立即添加事件")
        else:
            await click_unique(event_page.get_by_role("button", name="添加事件"), "添加事件")

        drawer = event_page.locator(".byted-drawer-dialog")
        await expect_unique(drawer, "add event drawer").wait_for(state="visible")

    async with step(progress, f"事件选择{options.deep_optimization_goal}"):
        event_select = await event_name_select(drawer)
        await click_select_field(event_select, event_page, "event ROI selector")
        await polite_pause(event_page)
        await filter_event_select(event_select, options.deep_optimization_goal)
        await polite_pause(event_page, 500)
        await select_event_name_option(
            event_page,
            event_select,
            options.deep_optimization_goal,
            f"event {options.deep_optimization_goal}",
        )
        await polite_pause(event_page)

    async with step(progress, "进入事件回传方式"):
        await click_unique(drawer.get_by_role("button", name="下一步"), "event next")
        await expect(drawer.get_by_role("button", name="添加")).to_be_visible()

    async with step(progress, "选择小程序API回传并添加"):
        await click_callback_card(event_page)
        add_event = drawer.get_by_role("button", name="添加")
        await expect(add_event).to_be_enabled()
        await click_unique(add_event, "event add confirm")

    async with step(progress, "关闭事件添加成功弹窗"):
        success_text = event_page.get_by_text("事件添加成功，请完成技术开发", exact=True)
        close_button = event_page.get_by_role("button", name="关闭")
        await wait_for_event_success_or_row(
            event_page,
            options.deep_optimization_goal,
            timeout_ms=20_000,
        )
        if await success_text.count() >= 1 and await success_text.first.is_visible(timeout=500):
            await expect(success_text.first).to_be_visible()
        if await close_button.count() >= 1:
            await click_first_visible(close_button, "close dev instructions")
            await polite_pause(event_page, 500)
        else:
            await close_visible_drawer(event_page)
            await polite_pause(event_page, 400)

    async with step(progress, f"确认事件已添加：{options.deep_optimization_goal}"):
        await wait_for_event_row(event_page, options.deep_optimization_goal, timeout_ms=8_000)


async def wait_for_event_success_or_row(page: Page, event_name: str, timeout_ms: int = 10_000) -> None:
    await page.wait_for_function(
        """eventName => {
            const isVisible = node => {
                const rect = node.getBoundingClientRect();
                const style = window.getComputedStyle(node);
                return rect.width > 0
                    && rect.height > 0
                    && style.display !== 'none'
                    && style.visibility !== 'hidden';
            };
            const bodyText = document.body.innerText || '';
            if (bodyText.includes('事件添加成功') || bodyText.includes('请完成技术开发')) {
                return true;
            }
            const rows = Array.from(document.querySelectorAll('.byted-table-row, tr, [role="row"]'));
            return rows.some(row => {
                if (!isVisible(row)) return false;
                const cells = Array.from(row.querySelectorAll('.byted-table-cell, td, [role="cell"], span, div'))
                    .filter(isVisible)
                    .map(cell => (cell.innerText || cell.textContent || '').replace(/\\s+/g, ' ').trim())
                    .filter(Boolean);
                return cells.some(text => text === eventName);
            });
        }""",
        arg=event_name,
        timeout=timeout_ms,
    )


async def event_name_select(drawer: Locator) -> Locator:
    fields = drawer.get_by_placeholder("请选择", exact=True)
    try:
        await fields.first.wait_for(state="visible", timeout=8_000)
    except PlaywrightTimeoutError as exc:
        raise RuntimeError("Cannot find event selector in add event drawer.") from exc

    count = await fields.count()
    if count == 0:
        raise RuntimeError("Cannot find event selector in add event drawer.")

    for index in range(count):
        field = fields.nth(index)
        try:
            if not await field.is_visible(timeout=300):
                continue
            value = (await field.input_value()).strip()
        except PlaywrightTimeoutError:
            continue
        if value in {"付费", "变现ROI", "变现ROI-7日", "变现ROI-30日"}:
            return field

    return fields.nth(count - 1)


async def filter_event_select(event_select: Locator, text: str) -> None:
    try:
        await event_select.press("Control+A", timeout=1_000)
        await event_select.fill(text, timeout=1_000)
    except PlaywrightTimeoutError:
        pass


async def select_event_name_option(
    page: Page,
    event_select: Locator,
    text: str,
    description: str,
) -> None:
    selected = await click_event_option_with_scroll(page, text, description)
    if not selected:
        raise RuntimeError(f"事件下拉列表中找不到精确选项：{text}")
    await polite_pause(page, 600)
    value = (await event_select.input_value()).strip()
    if normalize_event_label(value) != normalize_event_label(text):
        changed = await click_event_option_with_scroll(page, text, description)
        await polite_pause(page, 600)
        value = (await event_select.input_value()).strip()
        if not changed or normalize_event_label(value) != normalize_event_label(text):
            raise RuntimeError(f"事件下拉选择失败：期望 {text!r}，实际 {value or '空'!r}")


def normalize_event_label(value: str) -> str:
    return (
        value.replace("\u200b", "")
        .replace("\ufeff", "")
        .replace("\xa0", "")
        .strip()
    )


async def click_event_option_with_scroll(page: Page, text: str, description: str) -> bool:
    option_text = xpath_literal(text)
    option = page.locator(
        "xpath=//*[contains(concat(' ', normalize-space(@class), ' '), ' byted-popover-show ')]"
        f"//*[contains(concat(' ', normalize-space(@class), ' '), ' byted-select-option ') "
        f"and normalize-space(.)={option_text}]"
    )
    if await option.count() >= 1:
        target = option.first
        await target.scroll_into_view_if_needed(timeout=3_000)
        await polite_pause(page, 300)
        await target.click(timeout=3_000)
        return True

    # Fallback: some ByteDance dropdowns only render a window of options.
    panel = page.locator(".byted-popover-show .byted-select-popover-panel").last
    if await panel.count() == 0:
        panel = page.locator(".byted-select-popover-panel").last
    if await panel.count() == 0:
        return False

    for _ in range(24):
        option = page.locator(
            "xpath=//*[contains(concat(' ', normalize-space(@class), ' '), ' byted-popover-show ')]"
            f"//*[contains(concat(' ', normalize-space(@class), ' '), ' byted-select-option ') "
            f"and normalize-space(.)={option_text}]"
        )
        if await option.count() >= 1:
            target = option.first
            await target.scroll_into_view_if_needed(timeout=2_000)
            await polite_pause(page, 200)
            await target.click(timeout=2_000)
            return True
        try:
            await panel.evaluate(
                """node => {
                    const before = node.scrollTop;
                    node.scrollTop = Math.min(
                        node.scrollTop + Math.max(120, node.clientHeight - 24),
                        node.scrollHeight
                    );
                    return node.scrollTop !== before;
                }"""
            )
        except PlaywrightTimeoutError:
            box = await panel.bounding_box()
            if not box:
                return False
            await page.mouse.move(box["x"] + min(box["width"] / 2, 120), box["y"] + box["height"] / 2)
            await page.mouse.wheel(0, 170)
        await polite_pause(page, 200)

    return False


async def wait_for_event_row(page: Page, event_name: str, timeout_ms: int = 10_000) -> None:
    await page.wait_for_function(
        """eventName => {
            const isVisible = node => {
                const rect = node.getBoundingClientRect();
                const style = window.getComputedStyle(node);
                return rect.width > 0
                    && rect.height > 0
                    && style.display !== 'none'
                    && style.visibility !== 'hidden';
            };
            const rows = Array.from(document.querySelectorAll('.byted-table-row, tr, [role="row"], body *'));
            return rows.some(row => {
                if (!isVisible(row)) return false;
                const cells = Array.from(row.querySelectorAll('.byted-table-cell, td, [role="cell"], span, div'))
                    .filter(isVisible)
                    .map(cell => (cell.innerText || cell.textContent || '').replace(/\\s+/g, ' ').trim())
                    .filter(Boolean);
                return cells.some(text => text === eventName);
            });
        }""",
        arg=event_name,
        timeout=timeout_ms,
    )


async def click_callback_card(page: Page) -> None:
    state = await callback_card_state(page)
    if state.get("selected"):
        return
    if not state.get("found"):
        raise RuntimeError("Cannot find 小程序API回传 card.")

    for _ in range(3):
        state = await callback_card_state(page)
        if state.get("selected"):
            return
        click_target = state.get("checkbox") or state.get("card")
        if not click_target:
            break
        await page.mouse.click(click_target["x"], click_target["y"])
        await polite_pause(page, 500)

    if not await callback_card_selected(page):
        raise RuntimeError("小程序API回传复选框未能勾选。")


async def callback_card_state(page: Page) -> dict[str, object]:
    return await page.evaluate(
        """() => {
            const isVisible = node => {
                const rect = node.getBoundingClientRect();
                const style = window.getComputedStyle(node);
                return rect.width > 0
                    && rect.height > 0
                    && rect.bottom > 0
                    && rect.top < window.innerHeight
                    && style.display !== 'none'
                    && style.visibility !== 'hidden';
            };
            const clean = node => (node.innerText || node.textContent || '').replace(/\\s+/g, ' ').trim();
            const selectedByClass = node => {
                const cls = node.className?.toString?.() || '';
                return /checked|selected|active/i.test(cls)
                    || Boolean(node.querySelector('[class*="checked"], [class*="selected"], [class*="active"]'));
            };
            const selectedByControl = node => {
                const controls = Array.from(node.querySelectorAll(
                    'input[type="checkbox"], input[type="radio"], [role="checkbox"], [aria-checked]'
                )).filter(isVisible);
                return controls.some(control => control.checked === true
                    || control.getAttribute('aria-checked') === 'true'
                    || /checked|selected|active/i.test(control.className?.toString?.() || ''));
            };
            const checkboxBox = node => {
                const controls = Array.from(node.querySelectorAll(
                    'input[type="checkbox"], input[type="radio"], [role="checkbox"], [aria-checked], '
                    + '.byted-checkbox, .ovui-checkbox, [class*="checkbox"], [class*="Checkbox"]'
                )).filter(isVisible);
                let control = controls.find(item => {
                    const rect = item.getBoundingClientRect();
                    return rect.width <= 40 && rect.height <= 40;
                }) || controls[0];
                if (!control) {
                    const rect = node.getBoundingClientRect();
                    return { x: rect.right - 18, y: rect.top + 18 };
                }
                const clickable = control.closest('label, [role="checkbox"], .byted-checkbox, .ovui-checkbox')
                    || control;
                const rect = clickable.getBoundingClientRect();
                return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2 };
            };
            const cards = Array.from(document.querySelectorAll('label,div,section,article'))
                .filter(node => {
                    if (!isVisible(node)) return false;
                    const text = clean(node);
                    if (!text.includes('小程序API回传')) return false;
                    const rect = node.getBoundingClientRect();
                    return rect.width >= 160
                        && rect.width <= 760
                        && rect.height >= 54
                        && rect.height <= 240;
                })
                .sort((a, b) => {
                    const ar = a.getBoundingClientRect();
                    const br = b.getBoundingClientRect();
                    const score = node => {
                        const text = clean(node);
                        let value = 0;
                        if (text.includes('您需开发API主动回传数据')) value -= 1000;
                        if (text.includes('适用于追踪小程序深度链路用户行为')) value -= 500;
                        if (node.querySelector('input[type="checkbox"], input[type="radio"], [role="checkbox"], [aria-checked], [class*="checkbox"], [class*="Checkbox"]')) value -= 300;
                        const rect = node.getBoundingClientRect();
                        value += rect.width * rect.height / 1000;
                        return value;
                    };
                    return score(a) - score(b) || (ar.top - br.top) || (ar.left - br.left);
                });
            const card = cards[0];
            if (!card) return { found: false, selected: false };
            const rect = card.getBoundingClientRect();
            const selected = selectedByControl(card) || selectedByClass(card);
            return {
                found: true,
                selected,
                checkbox: checkboxBox(card),
                card: { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2 },
                text: clean(card).slice(0, 80),
            };
        }"""
    )


async def callback_card_selected(page: Page) -> bool:
    return bool((await callback_card_state(page)).get("selected"))


async def select_optimization_targets(page: Page, options: NewAdOptions) -> None:
    await confirm_pending_modal(page)
    dropdown = await optimization_dropdown(page)
    if (await dropdown.input_value()).strip() != options.optimization_goal:
        await open_optimization_dropdown(page)
        optimization_options = await visible_select_option_texts(page)
        if options.optimization_goal not in optimization_options:
            raise DeepOptimizationTargetUnavailable(
                f"优化目标下拉框没有 {options.optimization_goal}"
            )
        await click_option_by_text(page, options.optimization_goal, f"optimization {options.optimization_goal}")
        await expect(dropdown).to_have_value(options.optimization_goal)

    if not options.deep_optimization_goal.strip():
        return

    deep_dropdown = await deep_optimization_dropdown(page)
    if await deep_dropdown.count() == 0:
        raise DeepOptimizationTargetUnavailable("深度优化目标下拉框未显示")

    if (await deep_dropdown.input_value()).strip() != options.deep_optimization_goal:
        await click_select_field(deep_dropdown, page, "deep optimization selector")
        await polite_pause(page, 300)
        deep_options = await visible_select_option_texts(page)
        if options.deep_optimization_goal not in deep_options:
            option_hint = "、".join(deep_options) if deep_options else "无可见选项"
            raise DeepOptimizationTargetUnavailable(
                f"深度优化目标下拉框没有 {options.deep_optimization_goal}，当前可选：{option_hint}"
            )
        await click_option_by_text(
            page,
            options.deep_optimization_goal,
            f"deep optimization {options.deep_optimization_goal}",
        )

    await expect(deep_dropdown).to_have_value(options.deep_optimization_goal)
    method_label = deep_optimization_method_label(options.deep_optimization_goal)
    if method_label:
        await expect(page.get_by_text(method_label, exact=True).first).to_be_visible()


async def visible_select_option_texts(page: Page) -> list[str]:
    return await page.evaluate(
        """() => {
            const isVisible = node => {
                const rect = node.getBoundingClientRect();
                const style = window.getComputedStyle(node);
                return rect.width > 0
                    && rect.height > 0
                    && rect.bottom > 0
                    && rect.top < window.innerHeight
                    && style.display !== 'none'
                    && style.visibility !== 'hidden';
            };
            const optionSelector = '.ovui-option, .byted-select-option, [role="option"]';
            const options = Array.from(document.querySelectorAll(optionSelector)).filter(isVisible);
            const texts = options
                .map(node => (node.innerText || node.textContent || '').replace(/\\s+/g, ' ').trim())
                .filter(Boolean);
            return Array.from(new Set(texts));
        }"""
    )


def deep_optimization_method_label(deep_goal: str) -> str | None:
    if "7日" in deep_goal:
        return "7日ROI"
    if "30日" in deep_goal:
        return "30日ROI"
    return None


async def select_douyin_identity(page: Page, options: NewAdOptions) -> None:
    await scroll_text_into_view(page, "投放身份")
    await click_first_visible(page.get_by_text("抖音号", exact=True), "抖音号")
    await polite_pause(page, 250)

    await click_douyin_account_selector(page)
    await polite_pause(page, 300)

    search_box = page.get_by_placeholder("请输入抖音ID", exact=True)
    if await search_box.count() >= 1:
        await fill_first_visible_input(page, "请输入抖音ID", options.douyin_id)
        await wait_for_texts_in_same_visible_node(
            page,
            [options.douyin_name, options.douyin_id],
            timeout_ms=8_000,
        )
    else:
        await page.keyboard.insert_text(options.douyin_id)
        await polite_pause(page, 1500)

    await click_douyin_account_result(page, options)
    await wait_for_douyin_identity_selected(page, options)
    await close_douyin_search_popover(page)
    await wait_for_douyin_identity_selected(page, options)
    await polite_pause(page, 300)


async def fill_budget_and_roi(page: Page, options: NewAdOptions) -> None:
    await close_douyin_search_popover(page)
    await scroll_text_into_view(page, "日预算")
    await fill_main_form_input_near_label(page, "日预算", options.daily_budget)
    await fill_main_form_input_near_label(page, "ROI系数", options.roi_coefficient)
    await polite_pause(page, 250)


async def select_unlimited_targeting(page: Page) -> None:
    await scroll_text_into_view(page, "基础定向")
    await click_row_option(page, "基础定向", "不限")
    await polite_pause(page, 250)


async def enable_aigc_dynamic_creative(page: Page) -> None:
    await scroll_text_into_view(page, "AIGC动态创意")
    checked = await page.evaluate(
        """() => {
            const cards = Array.from(document.querySelectorAll('label,div,section'));
            const card = cards.find(node => {
                const text = (node.innerText || node.textContent || '').replace(/\\s+/g, ' ').trim();
                const rect = node.getBoundingClientRect();
                return text.includes('AIGC动态创意') && rect.width > 120 && rect.height > 40;
            });
            if (!card) return false;
            const input = card.querySelector('input[type="checkbox"]');
            if (input && input.checked) return true;
            const checkbox = card.querySelector('.ovui-checkbox, .byted-checkbox, [role="checkbox"]') || card;
            checkbox.click();
            return true;
        }"""
    )
    if not checked:
        raise RuntimeError("Cannot find AIGC动态创意 checkbox.")
    await polite_pause(page, 250)


async def batch_add_ad_texts(page: Page, options: NewAdOptions) -> None:
    await scroll_text_into_view(page, "文案素材")
    title_section = section_after_text(page, "文案素材")
    await click_first_visible(title_section.get_by_role("button", name="批量添加"), "文案批量添加")
    dialog = page.locator(".ovui-modal, .byted-modal, [role='dialog']").filter(has_text="批量添加")
    await expect(dialog.first).to_be_visible()
    editor = dialog.locator("textarea, [contenteditable='true']").first
    if await editor.count() >= 1 and await editor.is_visible(timeout=1_000):
        await fill_text_control(editor, options.ad_texts)
    else:
        box = await page.evaluate(
            """() => {
                const dialog = Array.from(document.querySelectorAll('.ovui-modal, .byted-modal, [role="dialog"]'))
                    .find(node => {
                        const text = node.innerText || node.textContent || '';
                        const rect = node.getBoundingClientRect();
                        const style = window.getComputedStyle(node);
                        return text.includes('批量添加')
                            && rect.width > 0
                            && rect.height > 0
                            && style.display !== 'none'
                            && style.visibility !== 'hidden';
                    });
                if (!dialog) return null;
                const inputArea = dialog.querySelector(
                    '.oc-textarea-plus-component__content, .oc-textarea-plus-component__body'
                );
                const target = inputArea || dialog;
                const rect = target.getBoundingClientRect();
                return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2 };
            }"""
        )
        if not box:
            raise RuntimeError("Cannot find batch title editor.")
        await page.mouse.click(box["x"], box["y"])
        await paste_text(page, options.ad_texts)

    await page.wait_for_function(
        """expected => {
            const dialogs = Array.from(document.querySelectorAll('.ovui-modal, .byted-modal, [role="dialog"]'));
            const dialog = dialogs.find(node => (node.innerText || node.textContent || '').includes('批量添加'));
            if (!dialog) return false;
            const text = dialog.innerText || dialog.textContent || '';
            const expectedCount = expected.split('\\n').filter(line => line.trim()).length;
            return text.includes(`(${expectedCount}/`)
                || text.includes(`批量添加标题 (${expectedCount}/`)
                || text.includes(`(${expectedCount + 1}/`)
                || text.includes(`批量添加标题 (${expectedCount + 1}/`);
        }""",
        arg=options.ad_texts,
        timeout=5_000,
    )
    await click_first_visible(dialog.get_by_role("button", name="确定"), "批量添加确定")
    await polite_pause(page, 400)


async def fill_landing_links(page: Page, options: NewAdOptions) -> None:
    await scroll_text_into_view(page, "落地页")
    await fill_input_near_label(page, "小游戏链接", options.mini_program_link)
    await fill_backup_site_link(page, options.backup_site_link)


async def fill_product_card(page: Page, options: NewAdOptions) -> None:
    await scroll_text_into_view(page, "投放组件")
    await fill_input_near_label(page, "产品名称", options.product_name)
    await fill_multi_value_input_near_label(page, "产品卖点", options.product_selling_points)
    await fill_multi_value_input_near_label(page, "行动号召", options.call_to_actions, clear_existing=True)
    await polite_pause(page, 250)


async def fill_project_name(page: Page, options: NewAdOptions) -> None:
    timestamp = datetime.now().astimezone().strftime("%Y%m%d_%H:%M:%S")
    project_name = f"{options.project_name_prefix}{timestamp}"
    await scroll_text_into_view(page, "项目名称")
    field = page.get_by_placeholder("请输入项目名称", exact=True).first
    await expect(field).to_be_visible()
    await fill_text_control(field, project_name)
    await polite_pause(page, 250)


async def enable_native_anchor_auto_generate(page: Page) -> None:
    try:
        await scroll_text_into_view(page, "原生锚点")
    except Exception:
        pass

    if not await native_anchor_available(page):
        return

    await click_native_anchor_auto_generate(page)
    await polite_pause(page, 300)


async def native_anchor_state(page: Page) -> dict[str, object]:
    return await page.evaluate(
        """() => {
            const hasBox = node => {
                const rect = node.getBoundingClientRect();
                const style = window.getComputedStyle(node);
                return rect.width > 0
                    && rect.height > 0
                    && rect.bottom > 0
                    && rect.top < window.innerHeight
                    && rect.right > 0
                    && rect.left < window.innerWidth
                    && style.display !== 'none'
                    && style.visibility !== 'hidden';
            };
            const clean = node => (node.innerText || node.textContent || node.getAttribute('aria-label') || '')
                .replace(/\\s+/g, ' ')
                .trim();
            const classTokens = node => (node?.className?.toString?.() || '')
                .split(/\\s+/)
                .filter(Boolean);
            const asState = (container, label) => {
                const input = label.querySelector?.('input[type="radio"][value="2"]')
                    || container.querySelector?.('input[type="radio"][value="2"]')
                    || label.querySelector?.('input[type="radio"], [role="radio"]')
                    || null;
                const selected = Boolean(input && input.checked === true);
                const labelRect = label.getBoundingClientRect();
                const inputRect = input?.getBoundingClientRect?.();
                return {
                    found: true,
                    selected,
                    target: {
                        x: inputRect && inputRect.width > 0 ? inputRect.x + inputRect.width / 2 : labelRect.x + labelRect.width / 2,
                        y: inputRect && inputRect.height > 0 ? inputRect.y + inputRect.height / 2 : labelRect.y + labelRect.height / 2,
                    },
                    label: {
                        x: labelRect.x + labelRect.width / 2,
                        y: labelRect.y + labelRect.height / 2,
                    },
                };
            };
            const candidateContainers = Array.from(document.querySelectorAll(
                '[data-auto-id="NativeAnchorWrapperModule"], [data-auto-id="NativeAnchorModule"], [data-e2e="createad_anchorSelect"]'
            ))
                .filter(hasBox)
                .filter(node => {
                    const text = clean(node);
                    return text.includes('原生锚点') || text.includes('设置锚点');
                })
                .filter(node => node.querySelector('[data-e2e="createad_anchorSelect__createAnchorSelect__ocRadioGroup_1_radio"], input[type="radio"][value="2"]'))
                .sort((a, b) => {
                    const ar = a.getBoundingClientRect();
                    const br = b.getBoundingClientRect();
                    const aDistance = Math.abs(ar.top - window.innerHeight / 2);
                    const bDistance = Math.abs(br.top - window.innerHeight / 2);
                    return aDistance - bDistance;
                });
            const stableContainer = candidateContainers[0] || null;
            const stableLabel = stableContainer?.querySelector?.('[data-e2e="createad_anchorSelect__createAnchorSelect__ocRadioGroup_1_radio"]')
                || stableContainer?.querySelector?.('input[type="radio"][value="2"]')?.closest?.('label')
                || null;
            if (stableContainer && stableLabel && hasBox(stableLabel)) {
                return asState(stableContainer, stableLabel);
            }
            const area = node => {
                const rect = node.getBoundingClientRect();
                return rect.width * rect.height;
            };
            const visibleNodes = selector => Array.from(document.querySelectorAll(selector)).filter(hasBox);
            const settingLabels = visibleNodes('label, span, div')
                .filter(node => clean(node) === '设置锚点');
            const rowContainers = settingLabels
                .map(node => node.closest('.oc-row, .byted-form-item, .ovui-form-item, [class*="form"], [class*="row"]') || node.parentElement)
                .filter(Boolean)
                .filter(node => {
                    const text = clean(node);
                    return text.includes('不启用') && text.includes('自动生成');
                });
            const widerContainers = visibleNodes('div, section, article')
                .filter(node => {
                    const text = clean(node);
                    return text.includes('原生锚点')
                        && text.includes('设置锚点')
                        && text.includes('不启用')
                        && text.includes('自动生成');
                });
            const containers = [...rowContainers, ...widerContainers]
                .filter((node, index, all) => all.indexOf(node) === index)
                .sort((a, b) => area(a) - area(b));
            const container = containers[0];
            if (!container) return { found: false, selected: false };
            const nodes = visibleNodes.call(null, 'label, span, div, input[type="radio"], [role="radio"]')
                .filter(node => container.contains(node));
            const autoText = nodes.find(node => clean(node) === '自动生成')
                || visibleNodes('label').find(node => container.contains(node) && clean(node).includes('自动生成'));
            if (!autoText) return { found: true, selected: false };
            const label = autoText.closest('label') || autoText.parentElement || autoText;
            let input = label.querySelector?.('input[type="radio"], [role="radio"]')
                || autoText.querySelector?.('input[type="radio"], [role="radio"]')
                || null;
            if (!input) {
                const labelRect = label.getBoundingClientRect();
                const radios = visibleNodes('input[type="radio"], [role="radio"]')
                    .filter(node => container.contains(node))
                    .sort((a, b) => {
                        const ar = a.getBoundingClientRect();
                        const br = b.getBoundingClientRect();
                        const da = Math.abs((ar.y + ar.height / 2) - (labelRect.y + labelRect.height / 2))
                            + Math.abs((ar.x + ar.width / 2) - labelRect.x);
                        const db = Math.abs((br.y + br.height / 2) - (labelRect.y + labelRect.height / 2))
                            + Math.abs((br.x + br.width / 2) - labelRect.x);
                        return da - db;
                    });
                input = radios[0] || null;
            }
            return asState(container, label);
        }"""
    )


async def native_anchor_available(page: Page) -> bool:
    return bool((await native_anchor_state(page)).get("found"))


async def click_native_anchor_auto_generate(page: Page) -> None:
    state = await native_anchor_state(page)
    if not state.get("found"):
        raise RuntimeError("找不到原生锚点自动生成选项")
    if state.get("selected"):
        return
    target = state.get("target") or state.get("label")
    if not isinstance(target, dict):
        raise RuntimeError("找不到原生锚点自动生成选项")
    await page.mouse.click(float(target["x"]), float(target["y"]))
    await polite_pause(page, 500)
    state = await native_anchor_state(page)
    if state.get("selected"):
        return
    label = state.get("label")
    if isinstance(label, dict):
        await page.mouse.click(float(label["x"]), float(label["y"]))
        await polite_pause(page, 500)
    state = await native_anchor_state(page)
    if state.get("selected"):
        return
    auto_labels = page.locator('[data-e2e="createad_anchorSelect__createAnchorSelect__ocRadioGroup_1_radio"]')
    for index in range(await auto_labels.count()):
        candidate = auto_labels.nth(index)
        try:
            if await candidate.is_visible(timeout=300):
                await candidate.click(force=True, timeout=2_000)
                await polite_pause(page, 700)
                break
        except PlaywrightTimeoutError:
            continue
    state = await native_anchor_state(page)
    if not state.get("selected"):
        raise RuntimeError("原生锚点自动生成未能选中")


async def upload_product_main_image(page: Page, options: NewAdOptions) -> None:
    image_path = Path(options.product_image_path).expanduser()
    if not image_path.exists():
        raise RuntimeError(f"产品主图图片不存在：{image_path}")
    if not image_path.is_file():
        raise RuntimeError(f"产品主图路径不是文件：{image_path}")

    await scroll_text_into_view(page, "产品主图")
    await click_product_main_image_add(page)

    upload_dialog = product_image_upload_drawer(page)
    await expect(upload_dialog).to_be_visible(timeout=10_000)
    await click_first_visible(upload_dialog.get_by_text("本地上传", exact=True), "产品主图本地上传")
    await polite_pause(page, 300)

    file_input = upload_dialog.locator('input[type="file"]').first
    if await file_input.count() >= 1:
        await file_input.set_input_files(str(image_path), timeout=30_000)
    else:
        async with page.expect_file_chooser(timeout=10_000) as chooser_info:
            await click_product_upload_area(page)
        chooser = await chooser_info.value
        await chooser.set_files(str(image_path), timeout=30_000)

    await wait_for_product_image_uploaded(page, image_path.name)
    confirm = upload_dialog.get_by_role("button", name="确定").last
    await expect(confirm).to_be_enabled(timeout=30_000)
    await confirm.click()
    await page.wait_for_function(
        """filename => {
            const isVisible = node => {
                const rect = node.getBoundingClientRect();
                const style = window.getComputedStyle(node);
                return rect.width > 0
                    && rect.height > 0
                    && style.display !== 'none'
                    && style.visibility !== 'hidden';
            };
            const dialogs = Array.from(document.querySelectorAll(
                '.ovui-drawer__wrap, .ovui-drawer, .ovui-modal, .byted-modal, .byted-drawer-dialog, [role="dialog"]'
            ));
            const uploadDialogVisible = dialogs.some(node => isVisible(node)
                && (node.innerText || node.textContent || '').includes(filename));
            const bodyText = document.body?.innerText || '';
            return !uploadDialogVisible && (bodyText.includes('已添加：1/10') || bodyText.includes(filename));
        }""",
        arg=image_path.name,
        timeout=15_000,
    )
    await polite_pause(page, 300)


async def auto_add_videos(page: Page, options: NewAdOptions) -> None:
    count = normalize_video_page_size(options.auto_add_video_count)
    await click_add_video_button(page)

    video_dialog = video_material_dialog(page)
    await expect(video_dialog).to_be_visible(timeout=10_000)
    actual_count = await set_video_page_size(page, count)
    await select_current_video_page(page)
    confirm = video_dialog.get_by_role("button", name="确定").last
    await expect(confirm).to_be_enabled(timeout=10_000)
    await confirm.click()
    await wait_for_video_selection_applied(page, actual_count)
    await polite_pause(page, 300)


def normalize_video_page_size(value: str) -> int:
    try:
        count = int(str(value).strip().replace("条/页", ""))
    except ValueError as exc:
        raise RuntimeError(f"自动添加视频数量无效：{value}") from exc
    if count not in {40, 80, 120, 160}:
        raise RuntimeError("自动添加视频数量只能是 40、80、120、160。")
    return count


def video_material_dialog(page: Page) -> Locator:
    return page.locator(
        ".ovui-drawer__wrap, .ovui-drawer, .ovui-modal, .byted-modal, .byted-drawer-dialog, [role='dialog']"
    ).filter(has_text="本页全选").last


async def click_add_video_button(page: Page) -> None:
    clicked = await page.evaluate(
        """() => {
            const isVisible = node => {
                const rect = node.getBoundingClientRect();
                const style = window.getComputedStyle(node);
                return rect.width > 0
                    && rect.height > 0
                    && rect.bottom > 0
                    && rect.top < window.innerHeight
                    && style.display !== 'none'
                    && style.visibility !== 'hidden';
            };
            const clean = node => (node.innerText || node.textContent || '').replace(/\\s+/g, ' ').trim();
            const findButton = () => {
                const buttons = Array.from(document.querySelectorAll('button, [role="button"], div, span'))
                    .filter(node => clean(node) === '添加视频');
                let button = buttons.find(node => node.closest('button, [role="button"]')) || buttons[0] || null;
                if (button) return button;
                const videoTab = Array.from(document.querySelectorAll('div, span'))
                    .find(node => /^视频\\s*\\(\\d+个\\)$/.test(clean(node)));
                let section = videoTab;
                for (let depth = 0; section && depth < 8; depth += 1, section = section.parentElement) {
                    if (!clean(section).includes('基础素材')) continue;
                    button = Array.from(section.querySelectorAll('button, [role="button"], div, span'))
                        .find(node => clean(node) === '添加视频');
                    if (button) return button;
                }
                return null;
            };
            let button = findButton();
            if (!button) return false;
            const clickable = button.closest('button, [role="button"]') || button;
            clickable.scrollIntoView({ block: 'center', inline: 'nearest' });
            return true;
        }"""
    )
    if not clicked:
        raise RuntimeError("找不到添加视频按钮")
    await polite_pause(page, 700)

    clicked = await page.evaluate(
        """() => {
            const isVisible = node => {
                const rect = node.getBoundingClientRect();
                const style = window.getComputedStyle(node);
                return rect.width > 0
                    && rect.height > 0
                    && rect.bottom > 0
                    && rect.top < window.innerHeight
                    && style.display !== 'none'
                    && style.visibility !== 'hidden';
            };
            const clean = node => (node.innerText || node.textContent || '').replace(/\\s+/g, ' ').trim();
            const buttons = Array.from(document.querySelectorAll('button, [role="button"], div, span'))
                .filter(node => isVisible(node) && clean(node) === '添加视频');
            const button = buttons.find(node => node.closest('button, [role="button"]')) || buttons[0];
            if (!button) return false;
            const clickable = button.closest('button, [role="button"]') || button;
            clickable.click();
            return true;
        }"""
    )
    if not clicked:
        raise RuntimeError("找不到添加视频按钮")
    await polite_pause(page, 500)


async def set_video_page_size(page: Page, count: int) -> int:
    target = f"{count}条/页"
    current = await current_video_page_size(page)
    if current == target:
        return count

    box = await video_page_size_box(page)
    if not box:
        raise RuntimeError("找不到视频个数/页下拉框")
    await page.mouse.click(box["x"], box["y"])
    await polite_pause(page, 300)
    await choose_video_page_size_by_keyboard(page, current, count)
    if await current_video_page_size(page) != target:
        await click_video_page_size_option(page, target)
    try:
        await page.wait_for_function(
            """target => {
                const isVisible = node => {
                    const rect = node.getBoundingClientRect();
                    const style = window.getComputedStyle(node);
                    return rect.width > 0
                        && rect.height > 0
                        && rect.bottom > 0
                        && rect.top < window.innerHeight
                        && style.display !== 'none'
                        && style.visibility !== 'hidden';
                };
                const drawers = Array.from(document.querySelectorAll(
                    '.ovui-drawer__wrap, .ovui-drawer, .ovui-modal, .byted-modal, .byted-drawer-dialog, [role="dialog"]'
                )).filter(node => isVisible(node) && (node.innerText || node.textContent || '').includes('本页全选'));
                const drawer = drawers.at(-1);
                if (!drawer) return false;
                return Array.from(drawer.querySelectorAll('input, div, span'))
                    .filter(isVisible)
                    .some(node => (((node.value || node.innerText || node.textContent || '') + '')
                        .replace(/\\s+/g, ' ')
                        .trim()) === target);
            }""",
            arg=target,
            timeout=4_000,
        )
    except PlaywrightTimeoutError:
        pass
    await polite_pause(page, 500)
    return parse_video_page_size(await current_video_page_size(page)) or count


def parse_video_page_size(value: str | None) -> int | None:
    if not value:
        return None
    try:
        parsed = int(str(value).strip().replace("条/页", ""))
    except ValueError:
        return None
    if parsed in {40, 80, 120, 160}:
        return parsed
    return None


async def current_video_page_size(page: Page) -> str | None:
    return await page.evaluate(
        """() => {
            const isVisible = node => {
                const rect = node.getBoundingClientRect();
                const style = window.getComputedStyle(node);
                return rect.width > 0
                    && rect.height > 0
                    && rect.bottom > 0
                    && rect.top < window.innerHeight
                    && style.display !== 'none'
                    && style.visibility !== 'hidden';
            };
            const drawers = Array.from(document.querySelectorAll(
                '.ovui-drawer__wrap, .ovui-drawer, .ovui-modal, .byted-modal, .byted-drawer-dialog, [role="dialog"]'
            )).filter(node => isVisible(node) && (node.innerText || node.textContent || '').includes('本页全选'));
            const drawer = drawers.at(-1);
            if (!drawer) return null;
            const nodes = Array.from(drawer.querySelectorAll('input, div, span'))
                .filter(isVisible);
            const node = nodes.find(item => {
                const text = ((item.value || item.innerText || item.textContent || '') + '').replace(/\\s+/g, ' ').trim();
                return /^\\d+条\\/页$/.test(text);
            });
            if (!node) return null;
            return ((node.value || node.innerText || node.textContent || '') + '').replace(/\\s+/g, ' ').trim();
        }"""
    )


async def video_page_size_box(page: Page) -> dict[str, float] | None:
    return await page.evaluate(
        """() => {
            const isVisible = node => {
                const rect = node.getBoundingClientRect();
                const style = window.getComputedStyle(node);
                return rect.width > 0
                    && rect.height > 0
                    && rect.bottom > 0
                    && rect.top < window.innerHeight
                    && style.display !== 'none'
                    && style.visibility !== 'hidden';
            };
            const drawers = Array.from(document.querySelectorAll(
                '.ovui-drawer__wrap, .ovui-drawer, .ovui-modal, .byted-modal, .byted-drawer-dialog, [role="dialog"]'
            )).filter(node => isVisible(node) && (node.innerText || node.textContent || '').includes('本页全选'));
            const drawer = drawers.at(-1);
            if (!drawer) return null;
            const stable = drawer.querySelector('[data-e2e$="pagination_group_select"], .ovui-page-select');
            if (stable && isVisible(stable)) {
                const rect = stable.getBoundingClientRect();
                return { x: rect.x + Math.max(rect.width - 18, rect.width / 2), y: rect.y + rect.height / 2 };
            }
            const nodes = Array.from(drawer.querySelectorAll('input, div, span'))
                .filter(isVisible);
            const node = nodes.find(item => {
                const text = ((item.value || item.innerText || item.textContent || '') + '').replace(/\\s+/g, ' ').trim();
                return /^\\d+条\\/页$/.test(text);
            });
            if (!node) return null;
            const clickable = node.closest('.ovui-select, .byted-select, [class*="select"], [role="combobox"], label')
                || node;
            const rect = clickable.getBoundingClientRect();
            return { x: rect.x + Math.max(rect.width - 18, rect.width / 2), y: rect.y + rect.height / 2 };
        }"""
    )


async def choose_video_page_size_by_keyboard(page: Page, current: str | None, count: int) -> None:
    ordered_counts = [40, 80, 120, 160]
    try:
        current_count = int(str(current or "40").replace("条/页", "").strip())
    except ValueError:
        current_count = 40
    if current_count not in ordered_counts:
        current_count = 40
    steps = ordered_counts.index(count) - ordered_counts.index(current_count)
    if steps < 0:
        for _ in range(abs(steps)):
            await page.keyboard.press("ArrowUp")
            await polite_pause(page, 120)
        await page.keyboard.press("Enter")
        await polite_pause(page, 500)
        return
    for _ in range(steps):
        await page.keyboard.press("ArrowDown")
        await polite_pause(page, 120)
    await page.keyboard.press("Enter")
    await polite_pause(page, 500)


async def click_video_page_size_option(page: Page, target: str) -> None:
    let_clicked = await page.evaluate(
        """target => {
            const clean = node => (node.innerText || node.textContent || '').replace(/\\s+/g, ' ').trim();
            const options = Array.from(document.querySelectorAll('.ovui-select__popper .ovui-option, .byted-select-option, [role="option"]'))
                .filter(node => clean(node) === target);
            const option = options.find(node => node.className?.toString?.().includes('ovui-option--xs'))
                || options.at(-1);
            if (!option) return false;
            const clickable = option.closest('.ovui-option, .byted-select-option, [role="option"], li') || option;
            for (const type of ['mousedown', 'mouseup', 'click']) {
                clickable.dispatchEvent(new MouseEvent(type, { bubbles: true, cancelable: true, view: window }));
            }
            return true;
        }""",
        target,
    )
    if let_clicked:
        return

    clicked = await page.evaluate(
        """target => {
            const hasBox = node => {
                const rect = node.getBoundingClientRect();
                const style = window.getComputedStyle(node);
                return rect.width > 0
                    && rect.height > 0
                    && style.display !== 'none'
                    && style.visibility !== 'hidden';
            };
            const clean = node => (node.innerText || node.textContent || '').replace(/\\s+/g, ' ').trim();
            const options = Array.from(document.querySelectorAll('.ovui-option, .byted-select-option, [role="option"], li, div'))
                .filter(node => hasBox(node) && clean(node) === target);
            const option = options.at(-1);
            if (!option) return false;
            const clickable = option.closest('.ovui-option, .byted-select-option, [role="option"], li') || option;
            clickable.click();
            return true;
        }""",
        target,
    )
    if not clicked:
        return


async def select_current_video_page(page: Page) -> None:
    checkbox = video_material_dialog(page).get_by_role("checkbox", name="本页全选")
    await expect(checkbox).to_be_visible(timeout=8_000)
    try:
        await checkbox.check(timeout=5_000)
    except PlaywrightTimeoutError:
        box = await page.evaluate(
            """() => {
                const isVisible = node => {
                    const rect = node.getBoundingClientRect();
                    const style = window.getComputedStyle(node);
                    return rect.width > 0
                        && rect.height > 0
                        && rect.bottom > 0
                        && rect.top < window.innerHeight
                        && style.display !== 'none'
                        && style.visibility !== 'hidden';
                };
                const clean = node => (node.innerText || node.textContent || '').replace(/\\s+/g, ' ').trim();
                const target = Array.from(document.querySelectorAll('label, div, span'))
                    .find(node => isVisible(node) && clean(node) === '本页全选');
                if (!target) return null;
                const clickable = target.closest('label, [role="checkbox"], .ovui-checkbox, .byted-checkbox') || target;
                const rect = clickable.getBoundingClientRect();
                return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2 };
            }"""
        )
        if not box:
            raise RuntimeError("找不到本页全选复选框")
        await page.mouse.click(box["x"], box["y"])

    await page.wait_for_function(
        """() => {
            const text = document.body?.innerText || '';
            return /已选择\\d+\\/800/.test(text);
        }""",
        timeout=8_000,
    )
    await polite_pause(page, 300)


async def wait_for_video_selection_applied(page: Page, count: int) -> None:
    await page.wait_for_function(
        """count => {
            const text = document.body?.innerText || '';
            return text.includes(`视频 (${count}个)`) || text.includes(`视频(${count}个)`);
        }""",
        arg=count,
        timeout=15_000,
    )


async def submit_ad_project(page: Page) -> None:
    await scroll_text_into_view(page, "项目名称")
    submit = page.get_by_role("button", name="发布项目")
    await expect(submit.first).to_be_visible(timeout=8_000)
    await expect(submit.first).to_be_enabled(timeout=15_000)
    await click_first_visible(submit, "发布项目")
    await polite_pause(page, 800)
    await confirm_submit_project_if_prompted(page)


async def confirm_submit_project_if_prompted(page: Page) -> None:
    confirm_selectors = (
        ("button", "确认发布"),
        ("button", "确定发布"),
        ("button", "确认"),
        ("button", "确定"),
    )
    for role, name in confirm_selectors:
        locator = page.get_by_role(role, name=name)
        for index in range(await locator.count()):
            candidate = locator.nth(index)
            try:
                if await candidate.is_visible(timeout=500) and await candidate.is_enabled(timeout=500):
                    await candidate.click(timeout=2_000)
                    await polite_pause(page, 800)
                    return
            except PlaywrightTimeoutError:
                continue


def product_image_upload_drawer(page: Page) -> Locator:
    return page.locator(
        ".ovui-drawer__wrap, .ovui-drawer, .ovui-modal, .byted-modal, .byted-drawer-dialog, [role='dialog']"
    ).filter(has_text="本地上传").last


async def click_product_main_image_add(page: Page) -> None:
    box = await page.evaluate(
        """() => {
            const isVisible = node => {
                const rect = node.getBoundingClientRect();
                const style = window.getComputedStyle(node);
                return rect.width > 0
                    && rect.height > 0
                    && rect.bottom > 0
                    && rect.top < window.innerHeight
                    && style.display !== 'none'
                    && style.visibility !== 'hidden';
            };
            const clean = node => (node.innerText || node.textContent || '').replace(/\\s+/g, ' ').trim();
            const labels = Array.from(document.querySelectorAll('span,div,label,p'))
                .filter(node => clean(node) === '产品主图' && isVisible(node));
            for (const label of labels) {
                let row = label;
                for (let depth = 0; row && depth < 8; depth += 1, row = row.parentElement) {
                    const rowText = clean(row);
                    if (!rowText.includes('产品主图') || !rowText.includes('已添加')) continue;
                    const candidates = Array.from(row.querySelectorAll('button,label,div,span'))
                        .filter(node => isVisible(node));
                    const plus = candidates.find(node => {
                        const text = clean(node);
                        const rect = node.getBoundingClientRect();
                        const cls = node.className?.toString?.() || '';
                        return (text === '+' || text === '＋' || text.includes('点击上传') || /add|upload|plus/i.test(cls))
                            && rect.width >= 18
                            && rect.height >= 18
                            && rect.width <= 220
                            && rect.height <= 220;
                    });
                    if (plus) {
                        const clickable = plus.closest('button,label,[role="button"]') || plus;
                        const rect = clickable.getBoundingClientRect();
                        return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2 };
                    }
                    const nearTiles = candidates
                        .map(node => ({ node, rect: node.getBoundingClientRect(), text: clean(node) }))
                        .filter(item => {
                            const labelRect = label.getBoundingClientRect();
                            return item.rect.left > labelRect.right
                                && item.rect.top >= labelRect.top - 20
                                && item.rect.top <= labelRect.top + 140
                                && item.rect.width >= 28
                                && item.rect.height >= 28
                                && item.rect.width <= 180
                                && item.rect.height <= 180
                                && (item.text === '+' || item.text === '＋' || item.node.querySelector('svg, iconpark-icon'));
                        })
                        .sort((a, b) => (a.rect.left - b.rect.left) || (a.rect.top - b.rect.top));
                    if (nearTiles.length) {
                        const rect = nearTiles[0].rect;
                        return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2 };
                    }
                }
            }
            return null;
        }"""
    )
    if not box:
        raise RuntimeError("找不到产品主图加号")
    await page.mouse.click(box["x"], box["y"])


async def click_product_upload_area(page: Page) -> None:
    box = await page.evaluate(
        """() => {
            const isVisible = node => {
                const rect = node.getBoundingClientRect();
                const style = window.getComputedStyle(node);
                return rect.width > 0
                    && rect.height > 0
                    && rect.bottom > 0
                    && rect.top < window.innerHeight
                    && style.display !== 'none'
                    && style.visibility !== 'hidden';
            };
            const clean = node => (node.innerText || node.textContent || '').replace(/\\s+/g, ' ').trim();
            const drawers = Array.from(document.querySelectorAll(
                '.ovui-drawer__wrap, .ovui-drawer, .ovui-modal, .byted-modal, .byted-drawer-dialog, [role="dialog"]'
            )).filter(node => isVisible(node) && clean(node).includes('本地上传'));
            const drawer = drawers.at(-1);
            if (!drawer) return null;
            const uploadText = Array.from(drawer.querySelectorAll('span,div,button,label'))
                .find(node => isVisible(node) && clean(node) === '点击上传');
            if (!uploadText) return null;
            const clickable = uploadText.closest('button,label,[role="button"],[data-auto-id="create-upload-select"],.oc-create-upload-select-wrapper')
                || uploadText;
            const rect = clickable.getBoundingClientRect();
            return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2 };
        }"""
    )
    if not box:
        raise RuntimeError("找不到产品主图点击上传入口")
    await page.mouse.click(box["x"], box["y"])


async def wait_for_product_image_uploaded(page: Page, filename: str) -> None:
    await page.wait_for_function(
        """filename => {
            const isVisible = node => {
                const rect = node.getBoundingClientRect();
                const style = window.getComputedStyle(node);
                return rect.width > 0
                    && rect.height > 0
                    && style.display !== 'none'
                    && style.visibility !== 'hidden';
            };
            const dialogs = Array.from(document.querySelectorAll(
                '.ovui-drawer__wrap, .ovui-drawer, .ovui-modal, .byted-modal, .byted-drawer-dialog, [role="dialog"]'
            ))
                .filter(isVisible);
            const dialog = dialogs.find(node => (node.innerText || node.textContent || '').includes(filename));
            if (!dialog) return false;
            const text = dialog.innerText || dialog.textContent || '';
            const confirm = Array.from(dialog.querySelectorAll('button')).find(button =>
                isVisible(button) && (button.innerText || button.textContent || '').trim() === '确定'
            );
            const failed = /失败|错误|超过|不符合|重新上传/.test(text);
            return !failed && Boolean(confirm) && !confirm.disabled && !confirm.getAttribute('aria-disabled');
        }""",
        arg=filename,
        timeout=60_000,
    )


async def ensure_logged_in(page: Page) -> None:
    login_markers = [
        page.get_by_text("登录", exact=True),
        page.get_by_text("扫码登录"),
        page.get_by_text("手机号登录"),
    ]
    for marker in login_markers:
        try:
            if await marker.count() > 0 and await marker.first.is_visible(timeout=1500):
                raise RuntimeError(
                    "The page still looks like a login page. Run `juliang-rpa login` first."
                )
        except PlaywrightTimeoutError:
            continue

    await expect(page.locator("body")).to_be_visible()


async def wait_for_page_ready(page: Page) -> None:
    await page.wait_for_load_state("domcontentloaded")
    try:
        await page.wait_for_load_state("networkidle", timeout=1_500)
    except PlaywrightTimeoutError:
        pass
    await polite_pause(page, 250)


async def polite_pause(page: Page, timeout_ms: int = 600) -> None:
    await page.wait_for_timeout(timeout_ms)


@asynccontextmanager
async def step(progress: ProgressCallback | None, name: str):
    started = time.perf_counter()
    if progress is not None:
        progress(f"开始：{name}")
    try:
        yield
    except Exception:
        elapsed = time.perf_counter() - started
        if progress is not None:
            progress(f"失败：{name}，耗时 {elapsed:.1f} 秒")
        raise
    else:
        elapsed = time.perf_counter() - started
        if progress is not None:
            progress(f"完成：{name}，耗时 {elapsed:.1f} 秒")


async def click_unique(locator: Locator, description: str) -> None:
    count = await locator.count()
    if count != 1:
        raise RuntimeError(f"Expected one {description}, found {count}.")
    await locator.click()


async def click_first_visible(locator: Locator, description: str) -> None:
    count = await locator.count()
    for index in range(count):
        candidate = locator.nth(index)
        try:
            if await candidate.is_visible(timeout=500):
                try:
                    await candidate.click(timeout=2_000)
                except PlaywrightTimeoutError:
                    box = await candidate.evaluate(
                        """node => {
                            const clickable = node.closest('.ovui-option, .byted-select-option, [role="option"], button, label') || node;
                            const rect = clickable.getBoundingClientRect();
                            return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2 };
                        }"""
                    )
                    await candidate.page.mouse.click(box["x"], box["y"])
                return
        except PlaywrightTimeoutError:
            continue
    raise RuntimeError(f"Cannot find visible {description}.")


async def click_first_visible_with_modifiers(
    locator: Locator,
    description: str,
    modifiers: list[str],
) -> None:
    count = await locator.count()
    for index in range(count):
        candidate = locator.nth(index)
        try:
            if await candidate.is_visible(timeout=500):
                await candidate.click(timeout=2_000, modifiers=modifiers)
                return
        except PlaywrightTimeoutError:
            continue
    raise RuntimeError(f"Cannot find visible {description}.")


async def click_exact_visible_option(page: Page, text: str, description: str) -> None:
    clicked = await page.evaluate(
        """needle => {
            const isVisible = node => {
                const rect = node.getBoundingClientRect();
                const style = window.getComputedStyle(node);
                return rect.width > 0
                    && rect.height > 0
                    && rect.bottom > 0
                    && rect.top < window.innerHeight
                    && style.display !== 'none'
                    && style.visibility !== 'hidden';
            };
            const candidates = Array.from(
                document.querySelectorAll('.ovui-option, .byted-select-option, [role="option"], li, div')
            );
            const target = candidates.find(node => {
                if (!isVisible(node)) return false;
                const value = (node.innerText || node.textContent || '').replace(/\\s+/g, ' ').trim();
                return value === needle;
            });
            if (!target) return false;
            const clickable = target.closest('.ovui-option, .byted-select-option, [role="option"], li') || target;
            clickable.click();
            return true;
        }""",
        text,
    )
    if not clicked:
        raise RuntimeError(f"Cannot find exact visible option for {description}.")


async def has_visible_locator(locator: Locator) -> bool:
    for index in range(await locator.count()):
        candidate = locator.nth(index)
        try:
            if await candidate.is_visible(timeout=300):
                return True
        except PlaywrightTimeoutError:
            continue
    return False


async def expect_count(locator: Locator, expected: int, description: str) -> None:
    count = await locator.count()
    if count != expected:
        raise RuntimeError(f"Expected {expected} {description}, found {count}.")


def expect_unique(locator: Locator, description: str) -> Locator:
    # This wrapper is used for readability at call sites. The count is checked
    # before actions; Playwright expect handles waiting for visibility/enabled.
    _ = description
    return locator
