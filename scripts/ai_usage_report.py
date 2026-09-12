"""Prints a summary of Gemini API usage from the `ai_requests` log.

Scaled-down stand-in for spec's "AI Cost Dashboard" (section 20): for a bot
used by one or two people, a CLI report is enough visibility into cost/quota
-- no admin web UI needed. Run after a day of use, or point it at a wider
window with --days.

    python -m scripts.ai_usage_report [--days N]
"""

import argparse
import asyncio
from datetime import UTC, datetime, timedelta

from bot.database.repositories.ai_request_repository import AIRequestRepository
from bot.database.session import get_session


async def main(days: int) -> None:
    since = datetime.now(UTC) - timedelta(days=days)

    async with get_session() as session:
        repo = AIRequestRepository(session)
        requests = await repo.usage_since(since)
        summary = await repo.summary_by_model_since(since)

    print(f"AI Usage -- last {days} day(s)\n")

    if not requests:
        print("(no requests logged in this window)")
        return

    total_tokens = sum(r.total_tokens or 0 for r in requests)
    errors = [r for r in requests if r.status != "success"]

    print(f"Requests: {len(requests)}")
    print(f"Tokens: {total_tokens:,}")
    print(f"Errors: {len(errors)}\n")

    print("By model:")
    for model, count, tokens in sorted(summary, key=lambda row: row[1], reverse=True):
        print(f"  {model}: {count} requests, {tokens:,} tokens")

    if errors:
        print("\nRecent errors:")
        for r in errors[-10:]:
            print(f"  {r.created_at.isoformat()} | {r.task_type} | {r.model} | {r.error_code}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=1, help="How many days back to summarize.")
    args = parser.parse_args()
    asyncio.run(main(args.days))
