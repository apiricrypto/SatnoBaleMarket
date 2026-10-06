import argparse
import json

from crm_connector import process_outbox


def main():
    parser = argparse.ArgumentParser(description="Process due SATNO CRM outbox items.")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()
    results = process_outbox(limit=max(1, min(args.limit, 50)))
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
