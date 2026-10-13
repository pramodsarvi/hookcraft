"""
Session Bootstrapper CLI
Run this utility to launch a clean, stealth browser instance to log into X (Twitter) or Instagram.
Once authenticated, the cookies and localStorage are serialized to ./sessions/<platform>_storage_state.json
for continuous reuse by the autonomous browser agent.

Usage:
    python login_cli.py --platform x
    python login_cli.py --platform instagram
"""

import argparse
import asyncio
import sys
from core.session_manager import SessionManager


async def main():
    parser = argparse.ArgumentParser(description="Authenticate and persist browser session states.")
    parser.add_argument(
        "--platform",
        "-p",
        choices=["x", "twitter", "instagram", "ig"],
        required=True,
        help="Target platform to authenticate ('x' or 'instagram')",
    )
    parser.add_argument(
        "--timeout",
        "-t",
        type=int,
        default=300,
        help="Timeout in seconds to wait for login completion (default: 300s)",
    )
    args = parser.parse_args()

    sm = SessionManager()
    target_platform = "x" if args.platform in ["x", "twitter"] else "instagram"

    print(f"\n=======================================================")
    print(f"  Interactive Session Setup: {target_platform.upper()}")
    print(f"=======================================================")
    print(f"Launching browser. Please complete login & 2FA.")
    print(f"Once you reach your home feed, the session will save automatically.\n")

    try:
        saved_file = await sm.interactive_login(target_platform, timeout_seconds=args.timeout)
        print(f"\n[SUCCESS] Session credentials successfully persisted to:\n  -> {saved_file}")
        print(f"Validating saved session...")
        is_valid = await sm.validate_session_liveness(target_platform)
        if is_valid:
            print("[SUCCESS] Session validated and operational for autonomous scraping!")
        else:
            print("[WARNING] Session verification check failed. Please check credentials or try again.")
    except Exception as e:
        print(f"\n[ERROR] Interactive login failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
