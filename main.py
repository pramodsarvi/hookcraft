"""
Autonomous Social Media Scraping Agent Entrypoint
Integrates LangGraph orchestration, browser-use, Qwen Vision-Language Model endpoint,
and anti-bot stealth evasions.

Usage Examples:
    # 1. Scrape X (Twitter) profile using LangGraph stealth pipeline:
    python main.py --platform x --target elonmusk --count 10

    # 2. Scrape Instagram profile:
    python main.py --platform instagram --target natgeo --count 10

    # 3. Run pure autonomous vision agent via browser-use:
    python main.py --platform x --target elonmusk --mode autonomous-vision
"""

import argparse
import asyncio
import json
import logging
from pathlib import Path
import sys

try:
    from rich.console import Console
    from rich.table import Table
    console = Console()
except ImportError:
    class FallbackConsole:
        def rule(self, text=""):
            print(f"\n--- {text} ---")
        def print(self, *args, **kwargs):
            import re
            cleaned = [re.sub(r"\[.*?\]", "", str(a)) for a in args]
            print(*cleaned)
    console = FallbackConsole()  # type: ignore
    Table = None  # type: ignore

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


def display_x_results(feed: XScrapedFeed):
    table = Table(title=f"Scraped Tweets for @{feed.target_query_or_user}")
    table.add_column("Index", justify="right", style="cyan", no_wrap=True)
    table.add_column("Author", style="magenta")
    table.add_column("Text Preview", style="white", max_width=50)
    table.add_column("Likes", justify="right", style="green")
    table.add_column("Retweets", justify="right", style="yellow")
    table.add_column("Timestamp", style="blue")

    for i, tweet in enumerate(feed.tweets, 1):
        text_preview = (tweet.tweet_text[:47] + "...") if len(tweet.tweet_text) > 50 else tweet.tweet_text
        table.add_row(
            str(i),
            f"@{tweet.author_handle}",
            text_preview,
            f"{tweet.likes_count:,}",
            f"{tweet.retweets_count:,}",
            str(tweet.timestamp or "N/A"),
        )

    console.print(table)
    console.print(f"[bold green]Total Distinct Tweets Extracted:[/bold green] {feed.total_tweets_captured}")


def display_instagram_results(feed: InstagramScrapedFeed):
    table = Table(title=f"Scraped Instagram Posts for @{feed.target_handle}")
    table.add_column("Index", justify="right", style="cyan", no_wrap=True)
    table.add_column("Shortcode", style="magenta")
    table.add_column("Type", style="yellow")
    table.add_column("Caption / Alt Preview", style="white", max_width=50)
    table.add_column("Post URL", style="blue")

    for i, post in enumerate(feed.posts, 1):
        caption_preview = ((post.caption or "")[:47] + "...") if post.caption and len(post.caption) > 50 else (post.caption or "N/A")
        table.add_row(
            str(i),
            str(post.shortcode or "N/A"),
            post.post_type,
            caption_preview,
            str(post.post_url or "N/A"),
        )

    console.print(table)
    console.print(f"[bold green]Total Distinct Posts Extracted:[/bold green] {feed.total_posts_captured}")


async def main():
    parser = argparse.ArgumentParser(description="Autonomous Social Scraping Agent")
    parser.add_argument("--platform", "-p", choices=["x", "twitter", "instagram", "ig"], default="x")
    parser.add_argument("--target", "-t", default="elonmusk", help="Target handle (e.g. 'elonmusk' or 'natgeo')")
    parser.add_argument("--count", "-c", type=int, default=10, help="Number of posts to extract (default: 10)")
    parser.add_argument(
        "--mode",
        "-m",
        choices=["pipeline", "autonomous-vision", "flywheel"],
        default="pipeline",
        help="Execution mode: 'pipeline' (LangGraph Stealth), 'autonomous-vision' (browser-use Agent), or 'flywheel' (Full 4-Phase Flywheel)",
    )
    parser.add_argument("--brief", "-b", default="sample_brief.md", help="Path to Markdown Marketing Brief (for flywheel mode)")
    parser.add_argument("--output", "-o", default=None, help="Path to save JSON output")
    parser.add_argument("--test-proxy", action="store_true", help="Probe and validate proxy connection latency and IP")

    args = parser.parse_args()

    if args.test_proxy:
        from core.proxy_providers import ProxyProviderManager
        mgr = ProxyProviderManager()
        console.rule("[bold cyan]Testing Proxy Provider Connection[/bold cyan]")
        console.print(f"Provider: [yellow]{mgr.config.provider.value.upper()}[/yellow] | Host: [yellow]{mgr.config.host}:{mgr.config.port}[/yellow]")
        probe = await mgr.test_proxy_connection()
        if probe.get("success"):
            console.print(f"[bold green]✅ Connection Successful![/bold green] Egress IP: [cyan]{probe.get('origin_ip')}[/cyan] (Latency: {probe.get('latency_ms', 0):.1f}ms)")
        else:
            console.print(f"[bold red]❌ Proxy Check Failed:[/bold red] {probe.get('error')}")
        return

    platform = "x" if args.platform in ["x", "twitter"] else "instagram"

    console.rule(f"[bold blue]Autonomous Marketing Flywheel Agent: {platform.upper()}[/bold blue]")
    console.print(f"Target: [bold cyan]@{args.target}[/bold cyan] | Target Count: [bold yellow]{args.count}[/bold yellow] | Mode: [bold magenta]{args.mode}[/bold magenta]")


    if args.mode == "flywheel":
        from flywheel_master import AutonomousMarketingFlywheel
        from generation.schemas import TargetPlatform

        brief_text = ""
        brief_file = Path(args.brief)
        if brief_file.exists():
            with open(brief_file, "r", encoding="utf-8") as f:
                brief_text = f.read()
        else:
            brief_text = "# Product: Autonomous Flywheel Agent\nTarget: Founders & Growth Leads."

        target_plat = TargetPlatform.X if platform == "x" else TargetPlatform.INSTAGRAM

        console.print("[bold yellow]Launching Full 4-Phase Autonomous Marketing Flywheel...[/bold yellow]")
        flywheel = AutonomousMarketingFlywheel()
        final_state = await flywheel.run(
            campaign_name=f"Flywheel_{platform}_{args.target}",
            marketing_brief_md=brief_text,
            target_platform=target_plat,
            target_handle=args.target,
        )

        console.rule("[bold green]Flywheel Lifecycle Complete[/bold green]")
        console.print(f"Status: [bold cyan]{final_state['status_summary']}[/bold cyan]")
        console.print(f"Derived Personas: [bold green]{len(final_state['derived_personas'])}[/bold green]")
        console.print(f"Ad Variations Synthesized: [bold green]{len(final_state['generated_ad_variations'])}[/bold green]")
        console.print(f"Staged in Ads Manager: [bold yellow]{len(final_state['staged_ad_sets'])}[/bold yellow]")
        console.print(f"Killed Underperformers: [bold red]{len(final_state['killed_ad_ids'])}[/bold red]")
        console.print(f"Scaled Top Performers: [bold green]{len(final_state['scaled_ad_ids'])}[/bold green]")
        console.print(f"New Winner Variants Spawned: [bold magenta]{len(final_state['spawned_winner_variants'])}[/bold magenta]")

        out_path = args.output or f"./{platform}_{args.target}_flywheel_results.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(final_state, f, indent=2, default=str)
        console.print(f"[bold green]Full Flywheel Telemetry saved to:[/bold green] {out_path}")
        return

    if args.mode == "autonomous-vision":
        console.print("[yellow]Launching autonomous browser-use agent loop with Qwen VLM...[/yellow]")
        history = await run_autonomous_vision_agent(platform, args.target, max_items=args.count)
        console.print("[green]Autonomous vision execution completed.[/green]")
        return

    # Default Mode: High-performance LangGraph Stealth Pipeline
    pipeline = SocialScraperPipeline()
    result = await pipeline.run(
        platform=platform,
        target_handle=args.target,
        target_count=args.count,
    )

    if platform == "x":
        display_x_results(result)
    else:
        display_instagram_results(result)

    # Export to JSON if specified
    out_path = args.output or f"./{platform}_{args.target}_scraped.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result.model_dump(mode="json"), f, indent=2, ensure_ascii=False)
    console.print(f"[bold green]Scraped payload saved to:[/bold green] {out_path}")


if __name__ == "__main__":
    asyncio.run(main())

