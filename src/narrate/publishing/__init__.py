"""Publishing layer: deliver rendered artifacts to destinations.

A *publisher* is a plugin that takes an artifact's bytes plus metadata
and delivers them somewhere -- a directory, a static site, a webhook, a
CMS.  Publishers never touch storage; the orchestration engine records a
:class:`~narrate.models.Publication` for every attempt.
"""

from narrate.publishing.base import Publisher, PublishReceipt, PublishRequest
from narrate.publishing.registry import PublisherRegistry

__all__ = ["PublishReceipt", "PublishRequest", "Publisher", "PublisherRegistry"]
