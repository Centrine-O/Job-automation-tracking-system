"""Run all scrapers in sequence and print a combined summary."""
from app.scrapers import remotive, jobicy, google_jobs, myjobmag, linkedin


def run_all_scrapers() -> int:
    """Run all scrapers and return total new jobs found."""
    results = {}
    for mod in [remotive, jobicy, google_jobs, myjobmag, linkedin]:
        name = mod.__name__.split(".")[-1]
        try:
            new = mod.run()
            results[name] = new
        except Exception as e:
            print(f"  [{name}] FAILED: {e}")
            results[name] = 0
    return sum(results.values())


def main():
    print("=" * 55)
    print("  JOB SCRAPER — running all sources")
    print("=" * 55)

    results = {}

    for mod in [remotive, jobicy, google_jobs, myjobmag, linkedin]:
        name = mod.__name__.split(".")[-1]
        print()
        try:
            new = mod.run()
            results[name] = new
        except Exception as e:
            print(f"  [{name}] FAILED: {e}")
            results[name] = 0

    print()
    print("=" * 55)
    print("  SUMMARY")
    print("=" * 55)
    for name, new in results.items():
        print(f"  {name:<20} {new:>4} new jobs")
    print(f"  {'TOTAL':<20} {sum(results.values()):>4} new jobs")
    print("=" * 55)


if __name__ == "__main__":
    main()
