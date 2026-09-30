import os

DEFAULT_PER_SOURCE=int(os.getenv("BALE_BACKFILL_PER_SOURCE","1000"))
BATCH_SIZE=int(os.getenv("BALE_BACKFILL_BATCH_SIZE","100"))

def next_budget(scanned, limit=DEFAULT_PER_SOURCE):
    return max(0, limit-int(scanned or 0))

def should_complete(batch_size, requested):
    return batch_size < requested

def oldest_rid(messages):
    for message in reversed(messages):
        rid=str(getattr(message,"rid","") or "")
        if rid:
            return rid
    return None
