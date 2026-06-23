import uuid

from django.conf import settings
from rest_framework.response import Response
from rest_framework.views import APIView

from common.permissions import IsArtist

from store.schema import telegram_connect_schema


@telegram_connect_schema
class TelegramConnectView(APIView):
    """Генерирует ссылку для подключения Telegram-бота."""

    permission_classes = (IsArtist,)

    def post(self, request):
        artist = request.user.artist_profile

        artist.telegram_token = uuid.uuid4()
        artist.save(update_fields=['telegram_token'])

        url = (
            f'https://t.me/{settings.TELEGRAM_BOT_USERNAME}'
            f'?start={artist.telegram_token}'
        )

        return Response({
            'url': url,
            'connected': bool(artist.telegram_chat_id),
        })
