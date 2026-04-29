"""Entry point — validates config, initialises DB, starts dashboard + scheduler."""
import sys
from app.config import settings
from app.tracking.db import init_db


def validate_config():
    errors = []
    if not settings.cohere_api_key and not settings.openrouter_api_key \
            and not settings.gemini_api_key and not settings.groq_api_key:
        errors.append("At least one AI API key required (COHERE_API_KEY, OPENROUTER_API_KEY, GEMINI_API_KEY, or GROQ_API_KEY)")
    if not settings.serpapi_key:
        errors.append("SERPAPI_KEY is required for Google Jobs scraping")
    if errors:
        print("Config validation failed:")
        for e in errors:
            print(f"  ✗ {e}")
        sys.exit(1)
    print("✓ Config valid")
    print(f"  DRY_RUN = {settings.dry_run}")
    print(f"  Max applications/day = {settings.max_applications_per_day}")


if __name__ == "__main__":
    validate_config()
    init_db()

    import uvicorn
    uvicorn.run(
        "app.dashboard.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
    )
