"""Base event listener for Beholders event system."""

from abc import ABC, abstractmethod

from beholders.events.event_bus import BeholdersEventsBus, beholders_event_bus


class BaseEventListener(ABC):
    """Abstract base class for event listeners."""

    verbose: bool = False

    def __init__(self) -> None:
        """Initialize the event listener and register handlers."""
        super().__init__()
        self.setup_listeners(beholders_event_bus)
        beholders_event_bus.validate_dependencies()

    @abstractmethod
    def setup_listeners(self, beholders_event_bus: BeholdersEventsBus) -> None:
        """Setup event listeners on the event bus.

        Args:
            beholders_event_bus: The event bus to register listeners on.
        """
