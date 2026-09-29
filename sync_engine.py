def apply_batch(*, source_key, messages, next_cursor, save_fn, checkpoint_fn):
    inserted = duplicates = processed = 0
    for message in messages:
        processed += 1
        result = save_fn(message)
        if result:
            inserted += 1
        else:
            duplicates += 1
    checkpoint_fn(source_key, next_cursor)
    return {"source_key": source_key, "cursor": None if next_cursor is None else str(next_cursor), "processed": processed, "inserted": inserted, "duplicates": duplicates}
