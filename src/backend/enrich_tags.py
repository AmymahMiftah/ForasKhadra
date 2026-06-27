import os
import sys
import json
import time

# running from scripts
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, "backend"))

from groq import Groq
from dotenv import load_dotenv

load_dotenv(os.path.join(BASE_DIR, ".env"))

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
DATA_PATH = os.path.join(BASE_DIR, "data", "opportunities.json")

# ── Prompt engineering: what makes a good tag set ──
TAG_GENERATION_PROMPT = """You are tagging opportunities for a scholarship/internship search engine used by Arabic-speaking youth.

Generate 12-18 search tags for the opportunity below.

RULES:
- Include program name and common aliases/abbreviations (e.g. "Chevening", "chevening scholarship", "شيفينغ")
- Include country name in BOTH English and Arabic (e.g. "UK", "united kingdom", "بريطانيا", "المملكة المتحدة")
- Include field/topic in BOTH languages (e.g. "climate change", "تغير المناخ", "environment", "بيئة")
- Include organisation name and abbreviation (e.g. "UNDP", "united nations development programme", "الأمم المتحدة")
- Include opportunity type in both languages (e.g. "scholarship", "منحة", "internship", "تدريب")
- Include target audience (e.g. "Arab students", "youth", "طلاب عرب", "شباب")
- Include funding info if applicable (e.g. "fully funded", "ممولة بالكامل")
- ALL tags must be lowercase
- NO duplicates

Return ONLY a JSON array of strings. No explanation, no markdown, no preamble.

Example output:
["chevening", "chevening scholarship", "شيفينغ", "uk", "united kingdom", "بريطانيا", "masters", "ماجستير", "fully funded", "ممولة بالكامل", "leadership", "قيادة", "arab students", "طلاب عرب"]

Opportunity:
Title: {title}
Arabic Title: {title_ar}
Organisation: {organisation}
Location: {location}
Description: {description}

Tags:"""


def generate_tags_for_opportunity(opp: dict, retries: int = 3) -> list[str]:
    """Call LLM to generate tags for a single opportunitye"""
    prompt = TAG_GENERATION_PROMPT.format(
        title=opp.get("title", ""),
        title_ar=opp.get("title_ar", opp.get("title", "")),
        organisation=opp.get("organisation", ""),
        location=opp.get("location", ""),
        description=opp.get("description", "")[:600],  # truncate long descriptions
    )

    for attempt in range(retries):
        try:
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=300,
            )
            text = response.choices[0].message.content.strip()

            text = text.replace("```json", "").replace("```", "").strip()

            # Parse JSON array
            tags = json.loads(text)


            if not isinstance(tags, list):
                raise ValueError(f"Expected list, got {type(tags)}")
            tags = [str(t).lower().strip() for t in tags if t]
            return tags

        except json.JSONDecodeError as e:
            print(f" json parse error (attempt {attempt + 1}): {e}")
            print(f" raw response: {text[:200]}")
        except Exception as e:
            print(f"error (attempt {attempt + 1}): {e}")

        if attempt < retries - 1:
            time.sleep(2 ** attempt)  # exponential backoff

    print(f" failed after {retries} attempts")
    return []


def merge_tags(existing: list, new_tags: list) -> list:
    """Merge new tags into existing, deduplicating case-insensitively."""
    existing_lower = {t.lower() for t in existing}
    merged = list(existing)
    for tag in new_tags:
        if tag.lower() not in existing_lower:
            merged.append(tag)
            existing_lower.add(tag.lower())
    return merged


def enrich_all_opportunities(data_path: str = DATA_PATH, dry_run: bool = False):
    
    print(f"\n{'='*60}")
    print(f"{'='*60}")
    print(f"Data file: {data_path}")
    print(f"Dry run: {dry_run}")
    print()

    with open(data_path, encoding="utf-8") as f:
        opportunities = json.load(f)

    print(f"Loaded {len(opportunities)} opportunities\n")

    total_added = 0
    enriched_count = 0

    for i, opp in enumerate(opportunities):
        opp_id = opp.get("id", f"#{i}")
        title = opp.get("title", "Unknown")
        existing_tags = opp.get("tags", [])

        print(f"[{i+1:03d}/{len(opportunities)}] ID={opp_id} | {title[:50]}")
        print(f"         Existing tags ({len(existing_tags)}): {existing_tags[:5]}{'...' if len(existing_tags) > 5 else ''}")

        new_tags = generate_tags_for_opportunity(opp)

        if not new_tags:
            print()
            continue

        merged = merge_tags(existing_tags, new_tags)
        added = len(merged) - len(existing_tags)

        if added > 0:
            print(f"adding {added} new tags. Total: {len(merged)}")
            added_tags = [t for t in merged if t not in existing_tags]
            print(f"         New: {added_tags[:8]}{'...' if len(added_tags) > 8 else ''}")
            total_added += added
            enriched_count += 1
        else:
            print(f"completed")

        if not dry_run:
            opportunities[i]["tags"] = merged

        print()
        time.sleep(0.5)

    if not dry_run:
        # Save back to the same file
        with open(data_path, "w", encoding="utf-8") as f:
            json.dump(opportunities, f, ensure_ascii=False, indent=2)
        print(f" Saved enriched opportunities to: {data_path}")
        print()
        print("Next steps:")
        print("  1. Restart your FastAPI server (tag index rebuilds automatically)")
        print("  2. No need to recompute embeddings (tags don't affect them)")
        print("  3. Test: ask chatbot about 'climate change', 'chevening', 'libya'")
    else:
        print("DRY RUN — no changes saved. Run with dry_run=False to save.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Enrich opportunity tags using LLM")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without saving",
    )
    parser.add_argument(
        "--ids",
        nargs="+",
        help="Only enrich specific opportunity IDs (e.g. --ids 004 005 049)",
    )
    args = parser.parse_args()

    if args.ids:
        
        with open(DATA_PATH, encoding="utf-8") as f:
            all_opps = json.load(f)

        target_ids = set(args.ids)
        changed = 0

        for i, opp in enumerate(all_opps):
            if opp.get("id") not in target_ids:
                continue

            print(f"\nEnriching ID={opp['id']}: {opp.get('title', '')}")
            new_tags = generate_tags_for_opportunity(opp)
            if new_tags:
                merged = merge_tags(opp.get("tags", []), new_tags)
                added = len(merged) - len(opp.get("tags", []))
                print(f"  Added {added} tags. New total: {len(merged)}")
                if not args.dry_run:
                    all_opps[i]["tags"] = merged
                    changed += 1

        if not args.dry_run and changed > 0:
            with open(DATA_PATH, "w", encoding="utf-8") as f:
                json.dump(all_opps, f, ensure_ascii=False, indent=2)
            print(f"\n saved {changed} opportunities")
    else:
        enrich_all_opportunities(dry_run=args.dry_run)