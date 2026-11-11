# Data layer

Run database commands as modules from the project root, using the same activated
Python environment as the backend. See [the root setup guide](../README.md) for
configuration, Windows commands and isolated testing.

* `connection.py` loads root `.env` and caches one lazy MongoDB database/client.
* `collections.py` preserves all 25 collection accessors and collection names.
* `queries.py` owns reused record lookups and existing readable ID generation.
* `create_indexes.py` contains index definitions and supports `--dry-run`.
* `seeds.py` contains idempotent SOP seeds; `seed_sop_templates.py` bootstraps Django
  for its timezone/schema dependencies and supports `--dry-run`.
* `check_connection.py` pings MongoDB without printing raw connection exceptions.

Do not store database files, exports, uploads or credentials here. Existing SQLite
and uploaded files stay at the project root, ignored by Git. No data migration is
required for this refactor; app labels, migration history and document paths stay
compatible. Optional `SQLITE_PATH` and `MEDIA_ROOT` settings select private locations.

Indexes must be installed explicitly; the app does not create them at startup.
Duplicate records may prevent unique index creation. The setup command reports the
affected index without displaying record values and never deletes duplicates.
