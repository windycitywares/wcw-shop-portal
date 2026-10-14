"""Pure business logic: no database, no web framework, no clock of its own.

Everything here takes plain values (and `now` where time matters), so it can be unit-tested in
milliseconds and reused by the API, the background jobs and the demo-data script alike.
"""
