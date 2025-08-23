from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from scripts.ingestion.ingest import ingest as run_ingest


def load_dotenv():
    """Load environment variables from .env file"""
    env_path = Path("/app/.env")
    if env_path.exists():
        print(f"Loading environment variables from {env_path}")
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                key, value = line.split("=", 1)
                # Don't override existing environment variables
                if key not in os.environ:
                    os.environ[key] = value
                    if key == "HA_TOKEN" and value == "YOUR_HA_TOKEN_HERE":
                        print(
                            "Warning: You need to set your actual Home Assistant token in .env file"
                        )


def main() -> None:
    """CLI entry point for ingest command."""
    # Load environment variables from .env file
    load_dotenv()

    parser = argparse.ArgumentParser()
    group = (
        parser.add_mutually_exclusive_group()
    )  # Removing required=True to allow for default values
    group.add_argument(
        "--full",
        action="store_true",
        help="Full ingest of all states (re-embed everything)",
    )
    group.add_argument("--entity", help="Single entity id")
    parser.add_argument(
        "--delay",
        type=int,
        default=5,
        help="Delay in seconds between embedding batches (default: 5)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode",
    )
    args = parser.parse_args()

    # Set debug logging if requested
    if args.debug:
        import logging

        logging.basicConfig(level=logging.DEBUG)

    try:
        # If no arguments are provided, default to full ingest when in debug mode
        if not args.full and not args.entity:
            if args.debug:
                print(
                    "No entity or full flag specified, defaulting to full ingest in debug mode"
                )
                run_ingest(None, delay_sec=args.delay, full=True)
            else:
                print(
                    "Error: Either --full or --entity must be specified",
                    file=sys.stderr,
                )
                parser.print_help()
                sys.exit(1)
        elif args.full:
            run_ingest(None, delay_sec=args.delay, full=True)
        else:
            run_ingest(args.entity, delay_sec=args.delay)
    except KeyError as e:
        print(f"Error: Missing required environment variable: {e}", file=sys.stderr)
        print("Required environment variables:", file=sys.stderr)
        print("  HA_URL - Home Assistant URL", file=sys.stderr)
        print("  HA_TOKEN - Home Assistant access token", file=sys.stderr)
        print("  ARANGO_URL - ArangoDB URL", file=sys.stderr)
        print("  ARANGO_USER - ArangoDB username", file=sys.stderr)
        print("  ARANGO_PASS - ArangoDB password", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
