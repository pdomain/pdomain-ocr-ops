"""Universal page value models — imported by every pd-* consumer of pages.

Pure pydantic. No eventsourcing, no blob/file I/O. The event store
(``pdomain_ops.page_aggregate``) and blob store (``pdomain_ops.blob_store``)
are separate, lifecycle-consumer-only modules.
"""
