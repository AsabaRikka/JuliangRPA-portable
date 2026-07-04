from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from .browser import first_page, goto_base, goto_login, persistent_context, save_debug_snapshot
from .config import DEFAULT_CONFIG_PATH, load_settings
from .tasks.new_ad import NewAdOptions, run_new_ad


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "doctor":
        asyncio.run(_doctor(args.config))
    elif args.command == "login":
        asyncio.run(_login(args.config))
    elif args.command == "open":
        asyncio.run(_open(args.config))
    elif args.command == "new-ad":
        asyncio.run(_new_ad(args))
    elif args.command == "gui":
        from .gui import main as gui_main

        gui_main(args.config)
    else:
        parser.print_help()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="juliang-rpa",
        description="Juliang ad Playwright RPA CLI",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="Config file path. Default: config/settings.yaml",
    )
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("doctor", help="Check config and browser startup")
    subparsers.add_parser("login", help="Open login page and save persistent session")
    subparsers.add_parser("open", help="Open backend with saved session")
    subparsers.add_parser("gui", help="Launch desktop GUI")

    new_ad_parser = subparsers.add_parser("new-ad", help="Run new-ad automation")
    new_ad_parser.add_argument("--account-id", required=True, help="Juliang account ID for aadvid")
    new_ad_parser.add_argument("--mini-game-name", default="看你还嘴硬")
    new_ad_parser.add_argument("--mini-game-asset-id", default="7598217165828816959")
    new_ad_parser.add_argument("--mini-game-app-id", default="tt62e7145afdeec8aa02")
    new_ad_parser.add_argument("--optimization-goal", default="激活")
    new_ad_parser.add_argument("--deep-optimization-goal", default="变现ROI-7日")
    new_ad_parser.add_argument("--douyin-id", default="37573898344")
    new_ad_parser.add_argument("--douyin-name", default="游多米爱游戏")
    new_ad_parser.add_argument("--daily-budget", default="99999")
    new_ad_parser.add_argument("--roi-coefficient", default="1.08")
    new_ad_parser.add_argument("--mini-program-link")
    new_ad_parser.add_argument("--backup-site-link")
    new_ad_parser.add_argument("--product-name", default="看你还嘴硬")
    new_ad_parser.add_argument(
        "--product-selling-points",
        default="被这游戏硬控一整天 近期2个好友在玩 一玩一个不吱声",
    )
    new_ad_parser.add_argument("--call-to-actions", default="进入游戏 开始游戏 点击即玩")
    new_ad_parser.add_argument("--project-name-prefix", default="ubmax-看你还嘴硬-xhy-7R1.08_")
    new_ad_parser.add_argument("--dry-run", action="store_true", help="Open page and save snapshot")

    return parser


async def _doctor(config_path: Path) -> None:
    settings = load_settings(config_path)
    print(f"base_url: {settings.base_url}")
    print(f"login_url: {settings.login_url}")
    print(f"create_ad_url_template: {settings.create_ad_url_template}")
    print(f"user_data_dir: {settings.browser.user_data_dir}")
    print(f"headless: {settings.browser.headless}")
    print(f"channel: {settings.browser.channel}")
    async with persistent_context(settings) as context:
        page = await first_page(context)
        print(f"browser_ready: {page is not None}")


async def _login(config_path: Path) -> None:
    settings = load_settings(config_path)
    async with persistent_context(settings) as context:
        page = await first_page(context)
        await goto_login(page, settings)
        print("Complete login in the opened browser, then press Enter here.")
        await asyncio.to_thread(input)
        screenshot_path, html_path = await save_debug_snapshot(
            page,
            settings.artifacts.logs_dir,
            "after_login",
        )
        print(f"Saved login screenshot: {screenshot_path}")
        print(f"Saved login HTML: {html_path}")


async def _open(config_path: Path) -> None:
    settings = load_settings(config_path)
    async with persistent_context(settings) as context:
        page = await first_page(context)
        await goto_base(page, settings)
        print("Backend opened. Press Enter to close the browser.")
        await asyncio.to_thread(input)


async def _new_ad(args: argparse.Namespace) -> None:
    settings = load_settings(args.config)
    options = NewAdOptions(
        account_id=args.account_id,
        mini_game_name=args.mini_game_name,
        mini_game_asset_id=args.mini_game_asset_id,
        mini_game_app_id=args.mini_game_app_id,
        optimization_goal=args.optimization_goal,
        deep_optimization_goal=args.deep_optimization_goal,
        douyin_id=args.douyin_id,
        douyin_name=args.douyin_name,
        daily_budget=args.daily_budget,
        roi_coefficient=args.roi_coefficient,
        mini_program_link=args.mini_program_link or NewAdOptions.mini_program_link,
        backup_site_link=args.backup_site_link or NewAdOptions.backup_site_link,
        product_name=args.product_name,
        product_selling_points=args.product_selling_points,
        call_to_actions=args.call_to_actions,
        project_name_prefix=args.project_name_prefix,
        dry_run=args.dry_run,
    )
    close_on_exit = options.dry_run
    async with persistent_context(settings, close_on_exit=close_on_exit) as context:
        page = await first_page(context)
        await run_new_ad(page, settings, options, progress=lambda message: print(message, flush=True))
        if not close_on_exit:
            print("新建广告页面已保留。检查完成后可手动关闭浏览器窗口。", flush=True)
            while context.pages:
                await asyncio.sleep(0.5)
