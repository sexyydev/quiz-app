from rest_framework.authentication import SessionAuthentication
import logging

logger = logging.getLogger(__name__)

class CsrfExemptSessionAuthentication(SessionAuthentication):
    """
    Custom authentication class that exempts CSRF checks.
    
    Use this class cautiously, limiting its application to specific API endpoints
    where CSRF protection is not necessary, such as non-browser clients or internal APIs.
    
    WARNING: Disabling CSRF protection can expose your application to security risks.
    Ensure that this is only applied in contexts where it is absolutely safe.
    """

    def enforce_csrf(self, request):
        # Log a warning when CSRF checks are bypassed to keep track of where and when this happens
        logger.warning(f"CSRF check bypassed for {request.path} by {request.user if request.user.is_authenticated else 'unauthenticated user'}")
        return  # Overriding to disable CSRF protection

