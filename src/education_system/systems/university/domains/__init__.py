"""University business domains, as vertical slices.

Each subpackage owns one business area end to end — its domain rules, the
application use cases over them, its own infrastructure adapters, and the thin
inbound adapters (api/cli/gui/web) that reach it. A slice is migrated here one
at a time; areas still under ``university/domain/`` have not moved yet.
"""
