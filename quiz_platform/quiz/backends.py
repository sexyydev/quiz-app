from django.contrib.auth.backends import BaseBackend
from django.contrib.auth import get_user_model
import logging

User = get_user_model()
logger = logging.getLogger(__name__)

class RegistrationNumberBackend(BaseBackend):
    """
    Custom authentication backend that allows users to log in using their registration number.
    """

    def authenticate(self, request, registration_number=None, password=None, **kwargs):
        try:
            user = User.objects.get(registration_number=registration_number)
            if user.check_password(password):
                logger.info(f"Authentication successful for registration number: {registration_number}")
                return user
            else:
                logger.warning(f"Authentication failed for registration number: {registration_number} (incorrect password)")
        except User.DoesNotExist:
            logger.warning(f"Authentication attempt failed for non-existent registration number: {registration_number}")
            return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            logger.error(f"User with ID {user_id} not found.")
            return None
