"""A2A update mechanism configuration types."""

from beholders.a2a.updates.base import (
    BaseHandlerKwargs,
    PollingHandlerKwargs,
    PushNotificationHandlerKwargs,
    PushNotificationResultStore,
    StreamingHandlerKwargs,
    UpdateHandler,
)
from beholders.a2a.updates.polling.config import PollingConfig
from beholders.a2a.updates.polling.handler import PollingHandler
from beholders.a2a.updates.push_notifications.config import PushNotificationConfig
from beholders.a2a.updates.push_notifications.handler import PushNotificationHandler
from beholders.a2a.updates.streaming.config import StreamingConfig
from beholders.a2a.updates.streaming.handler import StreamingHandler


UpdateConfig = PollingConfig | StreamingConfig | PushNotificationConfig

__all__ = [
    "BaseHandlerKwargs",
    "PollingConfig",
    "PollingHandler",
    "PollingHandlerKwargs",
    "PushNotificationConfig",
    "PushNotificationHandler",
    "PushNotificationHandlerKwargs",
    "PushNotificationResultStore",
    "StreamingConfig",
    "StreamingHandler",
    "StreamingHandlerKwargs",
    "UpdateConfig",
    "UpdateHandler",
]
