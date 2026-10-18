"""Представления чек-листа онбординга."""

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from users.schemas import onboarding_checklist_schema
from users.services import get_onboarding_checklist


@onboarding_checklist_schema
class OnboardingChecklistView(APIView):
    """Возвращает статусы чек-листа онбординга артиста."""

    permission_classes = (IsAuthenticated,)
    pagination_class = None

    def get(self, request, *args, **kwargs):
        """Возвращает актуальные статусы чек-листа."""
        user = self.request.user
        checklist = get_onboarding_checklist(user)
        return Response(checklist)
