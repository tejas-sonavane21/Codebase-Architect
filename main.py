#!/usr/bin/env python3
"""
Codebase Architect - CLI Entry Point

Autonomous tool that analyzes GitHub repositories and generates
professional PlantUML architectural diagrams using gemini_webapi.

Author: Tejas Sonavane

Usage:
    python main.py <github-repo-url> [--output <dir>]
    
Developer Mode (DEV_MODE=true in .env):
    python main.py --gems-list          # List all gems
    python main.py --gems-sync          # Sync gems with current prompts
    python main.py --gems-create        # Create fresh gems
    python main.py --gems-delete        # Delete all custom gems
    
Examples:
    python main.py https://github.com/tejas-sonavane21/VulnScraper
    python main.py https://github.com/tejas-sonavane21/VulnScraper --output my_diagrams
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

from utils.gemini_client import get_client
from utils.gem_manager import GemManager
from utils.console import console
from flow import run_flow

# Ensure parent directory is in path for imports
sys.path.insert(0, str(Path(__file__).parent))


def normalize_repo_url(url: str) -> str:
    """Normalize a GitHub URL by removing trailing .git if present."""
    if url and url.endswith(".git"):
        return url[:-4]
    return url


def validate_repo_url(url: str) -> bool:
    """Validate that the URL looks like a GitHub repo URL."""
    if not url:
        return False
    
    valid_prefixes = [
        "https://github.com/",
        "http://github.com/",
        "git@github.com:",
    ]
    
    return any(url.startswith(prefix) for prefix in valid_prefixes)


def check_environment() -> bool:
    """Verify required environment variables are set."""
    load_dotenv()
    
    # Check for gemini_webapi cookies
    secure_1psid = os.getenv("GEMINI_SECURE_1PSID")
    
    if not secure_1psid:
        print("✗ Error: GEMINI_SECURE_1PSID not found!")
        print("")
        print("This tool uses gemini_webapi for LLM access.")
        print("Please set your Gemini browser cookies:")
        print("")
        print("  1. Open Gemini in your browser (https://gemini.google.com)")
        print("  2. Open Developer Tools → Application → Cookies")
        print("  3. Copy the values for __Secure-1PSID and __Secure-1PSIDTS")
        print("")
        print("  4. Create a .env file in this directory with:")
        print("     GEMINI_SECURE_1PSID=your_cookie_value")
        print("     GEMINI_SECURE_1PSIDTS=your_cookie_value")
        return False
    
    if secure_1psid == "your_cookie_value":
        print("✗ Error: Please replace 'your_cookie_value' with your actual cookie!")
        return False
    
    print("✓ Gemini cookies configured")
    return True


def is_dev_mode() -> bool:
    """Check if developer mode is enabled."""
    return os.getenv("DEV_MODE", "false").lower() == "true"


# ============================================
# GEM MANAGEMENT (using GemManager)
# ============================================

async def gems_list():
    """List all gems from local config."""
    GemManager.print_status()


async def gems_sync():
    """Sync gems with current prompts."""
    print("\n🔄 Syncing gems with current prompts...\n")
    
    client = get_client()
    await client._ensure_initialized()
    
    result = await GemManager.sync_all(client)
    
    print(f"\n✓ Synced {len(result)} gems")


async def gems_create():
    """Create all gems fresh."""
    print("\n🆕 Creating fresh gems...\n")
    
    client = get_client()
    await client._ensure_initialized()
    
    result = await GemManager.create_all(client)
    
    print(f"\n✓ Created {len(result)} gems")


async def gems_delete():
    """Delete all gems."""
    print("\n🗑️ Deleting all gems...\n")
    
    client = get_client()
    await client._ensure_initialized()
    
    count = await GemManager.delete_all(client)
    
    print(f"\n✓ Deleted {count} gems")


def run_gem_command(command: str):
    """Run a gem management command."""
    commands = {
        "list": gems_list,
        "sync": gems_sync,
        "create": gems_create,
        "delete": gems_delete,
    }
    
    if command not in commands:
        print(f"✗ Unknown gem command: {command}")
        print(f"  Available: {', '.join(commands.keys())}")
        sys.exit(1)
    
    asyncio.run(commands[command]())


def main():
    """Main entry point."""
    load_dotenv()
    
    parser = argparse.ArgumentParser(
        description="Generate architectural diagrams from GitHub repositories",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py https://github.com/tejas-sonavane21/VulnScraper
  python main.py https://github.com/tejas-sonavane21/VulnScraper --output diagrams
  
Developer Mode (DEV_MODE=true in .env):
  python main.py --gems-list          # List all gems
  python main.py --gems-sync          # Sync gems with current prompts
  python main.py --gems-create        # Create fresh gems
  python main.py --gems-delete        # Delete all custom gems
  
The tool will:
  1. Clone the repository
  2. Analyze the codebase structure
  3. Build a semantic knowledge base
  4. Propose architectural diagrams
  5. Let you select which diagrams to generate
  6. Generate PlantUML diagrams and render to PNG
        """
    )
    
    parser.add_argument(
        "repo_url",
        nargs="?",  # Optional when using gem commands
        help="GitHub repository URL (e.g., https://github.com/user/repo)"
    )
    
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="Output directory (default: artifacts/results/<repo_name>)"
    )
    
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output"
    )
    
    # Developer mode gem management options
    if is_dev_mode():
        gem_group = parser.add_argument_group("Developer Mode - Gem Management")
        gem_group.add_argument(
            "--gems-list",
            action="store_true",
            help="List all available gems"
        )
        gem_group.add_argument(
            "--gems-sync",
            action="store_true",
            help="Sync gems with current prompts (create or update)"
        )
        gem_group.add_argument(
            "--gems-create",
            action="store_true",
            help="Create fresh gems from current prompts"
        )
        gem_group.add_argument(
            "--gems-delete",
            action="store_true",
            help="Delete all custom gems"
        )
    
    args = parser.parse_args()
    
    # Set console verbosity
    if args.verbose:
        console.set_verbosity(console.VERBOSE)
    
    # Handle gem management commands (dev mode only)
    if is_dev_mode():
        if args.gems_list:
            run_gem_command("list")
            sys.exit(0)
        elif args.gems_sync:
            if not check_environment():
                sys.exit(1)
            run_gem_command("sync")
            sys.exit(0)
        elif args.gems_create:
            if not check_environment():
                sys.exit(1)
            run_gem_command("create")
            sys.exit(0)
        elif args.gems_delete:
            if not check_environment():
                sys.exit(1)
            run_gem_command("delete")
            sys.exit(0)
    
    # Standard flow - require repo URL
    if not args.repo_url:
        parser.print_help()
        sys.exit(1)
    
    # Normalize URL
    repo_url = normalize_repo_url(args.repo_url)
    
    # Validate inputs
    if not validate_repo_url(repo_url):
        console.error(f"Invalid GitHub URL: {args.repo_url}")
        console.info("Expected format: https://github.com/user/repo")
        sys.exit(1)
    
    # Check environment
    if not check_environment():
        sys.exit(1)
    
    # Create output directory
    if args.output:
        output_dir = os.path.abspath(args.output)
        os.makedirs(output_dir, exist_ok=True)
    else:
        output_dir = None
    
    # Import and run the flow
    try:
        
        result = run_flow(
            repo_url=repo_url,
            output_dir=output_dir,
        )
        
        if result["success"]:
            console.success(f"Diagrams saved to: {output_dir}")
            sys.exit(0)
        else:
            console.error(f"Generation failed: {result.get('error', 'Unknown error')}")
            sys.exit(1)
            
    except KeyboardInterrupt:
        console.warning("Interrupted by user")
        sys.exit(130)
    except ImportError as e:
        console.error(f"Import error: {e}")
        console.info("Make sure all dependencies are installed:")
        console.info("pip install -r requirements.txt")
        sys.exit(1)
    except Exception as e:
        console.error(f"Unexpected error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
