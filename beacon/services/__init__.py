from beacon.models import EventRecorder
from beacon.services.base import SyntheticService
from beacon.services.files import FileService, FilePolicyError
from beacon.services.mail import MailService, ToolPolicyError
from beacon.services.registry import (
    ServiceError,
    build_service,
    import_service_module,
    is_service,
    register_service,
    registered_services,
)
from beacon.services.router import ToolRouter
from beacon.services.tickets import TicketPolicyError, TicketService
from beacon.services.web import WebPolicyError, WebService

# The services Beacon ships. A scenario pack can register its own the same
# way, from outside this package, without editing anything here.
register_service("mail", lambda fixture, recorder: MailService(fixture, recorder))
register_service("files", lambda fixture, recorder: FileService(fixture, recorder))
register_service("web", lambda fixture, recorder: WebService(fixture, recorder))
register_service("tickets", lambda fixture, recorder: TicketService(fixture, recorder))

__all__ = [
    "EventRecorder",
    "FilePolicyError",
    "FileService",
    "MailService",
    "ServiceError",
    "SyntheticService",
    "ToolPolicyError",
    "TicketPolicyError",
    "TicketService",
    "ToolRouter",
    "WebPolicyError",
    "WebService",
    "build_service",
    "import_service_module",
    "is_service",
    "register_service",
    "registered_services",
]
