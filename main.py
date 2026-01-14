#!/usr/bin/env python3
"""
Black-Book Diagram Generator - CLI Entry Point

Autonomous tool that analyzes GitHub repositories and generates
professional PlantUML architectural diagrams.

Author: Tejas Sonavane

Usage:
    python main.py <github-repo-url> [--output <dir>]
    
Examples:
    python main.py https://github.com/tejas-sonavane21/VulnScraper
    python main.py https://github.com/tejas-sonavane21/VulnScraper --output my_diagrams
"""

import argparse
import os
import sys
from pathlib import Path

# Ensure parent directory is in path for imports
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv


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
    
    api_key = os.getenv("GEMINI_API_KEY")
    
    if not api_key:
        print("✗ Error: GEMINI_API_KEY not found!")
        print("")
        print("Please set your Gemini API key:")
        print("  1. Create a .env file in this directory")
        print("  2. Add: GEMINI_API_KEY=your_api_key_here")
        print("")
        print("Or set the environment variable directly:")
        print("  export GEMINI_API_KEY=your_api_key_here")
        return False
    
    if api_key == "your_api_key_here":
        print("✗ Error: Please replace 'your_api_key_here' with your actual API key!")
        return False
    
    return True


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate architectural diagrams from GitHub repositories",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py https://github.com/tejas-sonavane21/VulnScraper
  python main.py https://github.com/tejas-sonavane21/VulnScraper --output diagrams
  
The tool will:
  1. Clone the repository
  2. Analyze the codebase structure
  3. Upload source files to Gemini for context
  4. Propose architectural diagrams
  5. Let you select which diagrams to generate
  6. Generate PlantUML diagrams and render to PNG
        """
    )
    
    parser.add_argument(
        "repo_url",
        help="GitHub repository URL (e.g., https://github.com/user/repo)"
    )
    
    parser.add_argument(
        "-o", "--output",
        default="generated_diagrams",
        help="Output directory for diagrams (default: generated_diagrams)"
    )
    
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output"
    )
    
    args = parser.parse_args()
    
    # Validate inputs
    if not validate_repo_url(args.repo_url):
        print(f"✗ Error: Invalid GitHub URL: {args.repo_url}")
        print("  Expected format: https://github.com/user/repo")
        sys.exit(1)
    
    # Check environment
    if not check_environment():
        sys.exit(1)
    
    # Create output directory
    output_dir = os.path.abspath(args.output)
    os.makedirs(output_dir, exist_ok=True)
    
    # Import and run the flow
    try:
        from flow import run_flow
        
        result = run_flow(
            repo_url=args.repo_url,
            output_dir=output_dir,
        )
        
        if result["success"]:
            print(f"\n✓ Diagrams saved to: {output_dir}")
            sys.exit(0)
        else:
            print(f"\n✗ Generation failed: {result.get('error', 'Unknown error')}")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\n⚠ Interrupted by user")
        sys.exit(130)
    except ImportError as e:
        print(f"\n✗ Import error: {e}")
        print("  Make sure all dependencies are installed:")
        print("  pip install -r requirements.txt")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
