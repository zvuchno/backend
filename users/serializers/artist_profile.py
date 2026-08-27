"""Сериализаторы профиля артиста."""

from django.db import IntegrityError, transaction
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from common.services import get_artist_publication_readiness
from common.utils import get_client_ip, get_user_agent

from users.consents_policy import ConsentContext
from users.helpers import ensure_listener_profile
from users.models import (
    ArtistContact,
    ArtistProfile,
    ArtistProfileClaimInvitation,
    ArtistProfileType,
    ArtistSocial,
    ConsentDocument,
)
from users.services import ConsentService


class ArtistCoverUpdateSerializer(serializers.ModelSerializer):
    """Сериализатор обновления обложки артиста."""

    class Meta:
        model = ArtistProfile
        fields = ('cover',)


class ArtistContactSerializer(serializers.ModelSerializer):
    """Сериализатор контактных данных артиста."""

    id = serializers.IntegerField(required=False)

    class Meta:
        model = ArtistContact
        fields = ('id', 'label', 'value')


class ArtistSocialSerializer(serializers.ModelSerializer):
    """Сериализатор ссылок на соцсети артиста."""

    id = serializers.IntegerField(required=False)

    class Meta:
        model = ArtistSocial
        fields = ('id', 'label', 'value')


class ArtistLabelShortSerializer(serializers.ModelSerializer):
    """Сериализатор лейбла артиста."""

    class Meta:
        model = ArtistProfile
        fields = (
            'id',
            'name',
            'slug',
        )


class ArtistPublicShortSerializer(serializers.ModelSerializer):
    """Сериализатор публичного профиля артиста."""

    label = ArtistLabelShortSerializer(read_only=True)

    class Meta:
        model = ArtistProfile
        fields = (
            'id',
            'profile_type',
            'name',
            'description',
            'cover',
            'city',
            'slug',
            'label',
        )


class ArtistPublicSerializer(ArtistPublicShortSerializer):
    """Расширенный сериализатор публичного профиля артиста."""

    contacts = ArtistContactSerializer(many=True, read_only=True)
    socials = ArtistSocialSerializer(many=True, read_only=True)

    class Meta(ArtistPublicShortSerializer.Meta):
        fields = (
            'contacts',
            'socials',
        ) + ArtistPublicShortSerializer.Meta.fields


class PublicationReadinessItemSerializer(serializers.Serializer):
    """Готовность к публикации типа товара."""

    can_publish = serializers.BooleanField()
    missing_requirements = serializers.ListField(
        child=serializers.CharField(),
    )


class ArtistPublicationReadinessSerializer(serializers.Serializer):
    """Готовность артиста к публикации товаров."""

    digital = PublicationReadinessItemSerializer()
    physical = PublicationReadinessItemSerializer()


class ArtistMeSerializer(ArtistPublicSerializer):
    """Сериализатор профиля текущего артиста."""

    publication_readiness = serializers.SerializerMethodField()

    class Meta(ArtistPublicSerializer.Meta):
        fields = ArtistPublicSerializer.Meta.fields + (
            'publication_readiness',
        )

    @extend_schema_field(ArtistPublicationReadinessSerializer)
    def get_publication_readiness(self, obj):
        """Возвращает готовность артиста к публикации товаров."""
        readiness = get_artist_publication_readiness(obj)

        return {
            'digital': {
                'can_publish': readiness.can_publish_digital,
                'missing_requirements': [
                    requirement.value
                    for requirement in readiness.digital_missing
                ],
            },
            'physical': {
                'can_publish': readiness.can_publish_physical,
                'missing_requirements': [
                    requirement.value
                    for requirement in readiness.physical_missing
                ],
            },
        }


class ArtistProfileUpdateSerializer(serializers.ModelSerializer):
    """Сериализатор обновления профиля артиста."""

    contacts = ArtistContactSerializer(many=True, required=False)
    socials = ArtistSocialSerializer(many=True, required=False)

    @staticmethod
    def _sync_nested_items(instance, items_data, model, related_name) -> None:
        """Синхронизирует состав связанных объектов по id.

        Новые создает, отсутствующие в запросе удаляет.
        """
        manager = getattr(instance, related_name)
        existing_items = {item.id: item for item in manager.all()}
        received_ids = set()
        new_items = []
        items_to_update = []

        for item_data in items_data:
            item_id = item_data.get('id')
            if item_id is None:
                new_items.append(model(artist=instance, **item_data))
                continue

            item = existing_items.get(item_id)
            if item is None:
                raise serializers.ValidationError({
                    related_name: (
                        f'Запись с id={item_id} не найдена '
                        'или не принадлежит артисту.'
                    ),
                })
            for attr, value in item_data.items():
                if attr != 'id':
                    setattr(item, attr, value)
            items_to_update.append(item)
            received_ids.add(item_id)
        if new_items:
            model.objects.bulk_create(new_items)
        if items_to_update:
            model.objects.bulk_update(items_to_update, ['label', 'value'])

        ids_for_delete = set(existing_items.keys()) - received_ids
        if ids_for_delete:
            manager.filter(id__in=ids_for_delete).delete()

    @transaction.atomic
    def update(self, instance, validated_data):
        """Обновляет профиль артиста и синхронизирует контакты и соцсети."""
        contacts_data = validated_data.pop('contacts', None)
        socials_data = validated_data.pop('socials', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if contacts_data is not None:
            self._sync_nested_items(
                instance,
                contacts_data,
                ArtistContact,
                'contacts',
            )
        if socials_data is not None:
            self._sync_nested_items(
                instance,
                socials_data,
                ArtistSocial,
                'socials',
            )
        return instance

    class Meta:
        model = ArtistProfile
        fields = (
            'name',
            'description',
            'city',
            'slug',
            'socials',
            'contacts',
        )
        extra_kwargs = {
            'slug': {
                'required': False,
                'allow_blank': False,
            },
        }


class BecomeArtistOrLabelSerializer(serializers.ModelSerializer):
    """Сериализатор создания профиля или повышения артиста до лейбла."""

    profile_type = serializers.ChoiceField(
        choices=ArtistProfileType.choices,
        default=ArtistProfileType.ARTIST,
    )
    name = serializers.CharField(
        required=False,
        allow_blank=False,
    )
    consents = serializers.ListField(
        child=serializers.ChoiceField(
            choices=ConsentDocument.DocumentType.choices,
        ),
        required=False,
        write_only=True,
        label='Принятые согласия',
    )

    class Meta:
        model = ArtistProfile
        fields = ('name', 'profile_type', 'consents')

    def validate(self, attrs):
        """Проверяет создание профиля или повышение артиста до лейбла."""
        user = self.context['request'].user
        profile = getattr(user, 'artist_profile', None)
        target_type = attrs.get(
            'profile_type',
            ArtistProfileType.ARTIST,
        )

        if profile is None:
            if not attrs.get('name'):
                raise serializers.ValidationError({
                    'name': 'Это поле обязательно при создании профиля.',
                })
            return attrs

        if target_type != ArtistProfileType.LABEL:
            raise serializers.ValidationError({
                'profile_type': (
                    'У пользователя уже есть профиль артиста. '
                    'Допустим только переход к профилю лейбла.'
                ),
            })

        if profile.label_id is not None:
            raise serializers.ValidationError({
                'profile_type': (
                    'Нельзя стать лейблом, находясь под управлением '
                    'другого лейбла.'
                ),
            })

        context = self._get_consent_context(
            user,
            target_type,
        )
        if context is not None:
            ConsentService.validate(
                context=context,
                accepted_types=set(attrs.get('consents') or ()),
            )

        return attrs

    @transaction.atomic
    def create(self, validated_data):
        """Создаёт профиль или повышает независимого артиста до лейбла."""
        user = self.context['request'].user
        profile = getattr(user, 'artist_profile', None)

        if profile is not None:
            profile.profile_type = ArtistProfileType.LABEL
            profile.save(update_fields=('profile_type', 'updated_at'))
            return profile

        ensure_listener_profile(user)
        try:
            with transaction.atomic():
                accepted_types = set(validated_data.pop('consents', ()))
                profile = ArtistProfile.objects.create(
                    user=user,
                    **validated_data,
                )
                context = (
                    ConsentContext.LABEL_ONBOARDING
                    if profile.profile_type == ArtistProfileType.LABEL
                    else ConsentContext.ARTIST_ONBOARDING
                )

                request = self.context['request']

                ConsentService.accept(
                    context=context,
                    accepted_types=accepted_types,
                    user=user,
                    email=user.email,
                    ip_address=get_client_ip(request),
                    user_agent=get_user_agent(request),
                )
                return profile

        except IntegrityError:
            if ArtistProfile.objects.filter(user=user).exists():
                raise serializers.ValidationError(
                    {
                        'detail': (
                            'У пользователя уже есть профиль '
                            'артиста или лейбла.'
                        ),
                    },
                )
            raise

    def _get_consent_context(
        self,
        user,
        profile_type,
    ) -> ConsentContext | None:
        """Возвращает контекст согласий для повышения пользователя."""
        profile = getattr(user, 'artist_profile', None)

        if profile is not None:
            return None

        if profile_type == ArtistProfileType.LABEL:
            return ConsentContext.LABEL_ONBOARDING

        return ConsentContext.ARTIST_ONBOARDING


class ArtistProfileClaimInvitationShortSerializer(
    serializers.ModelSerializer,
):
    """Краткое состояние приглашения на управление профилем."""

    email = serializers.EmailField(
        source='invitation.recipient_email',
    )
    status = serializers.CharField(
        source='invitation.status',
    )
    expires_at = serializers.DateTimeField(
        source='invitation.expires_at',
    )
    can_resend = serializers.BooleanField(
        source='invitation.can_resend',
        read_only=True,
    )
    resend_available_at = serializers.DateTimeField(
        source='invitation.resend_available_at',
        read_only=True,
        allow_null=True,
    )

    class Meta:
        model = ArtistProfileClaimInvitation
        fields = (
            'email',
            'status',
            'expires_at',
            'can_resend',
            'resend_available_at',
        )


class ManagedArtistProfileSerializer(ArtistPublicShortSerializer):
    """Профиль, доступный для управления текущему аккаунту."""

    has_account = serializers.SerializerMethodField()
    is_self = serializers.SerializerMethodField()
    claim_invitation = serializers.SerializerMethodField()

    class Meta(ArtistPublicShortSerializer.Meta):
        fields = ArtistPublicShortSerializer.Meta.fields + (
            'has_account',
            'is_self',
            'claim_invitation',
        )

    def get_has_account(self, obj: ArtistProfile) -> bool:
        """Определяет наличие аккаунта у профиля."""
        return obj.user_id is not None

    def get_is_self(self, obj: ArtistProfile) -> bool:
        """Определяет, принадлежит ли профиль текущему аккаунту."""
        request = self.context.get('request')
        return bool(request and obj.user_id == request.user.id)

    @extend_schema_field(
        ArtistProfileClaimInvitationShortSerializer(
            allow_null=True,
        ),
    )
    def get_claim_invitation(self, obj: ArtistProfile):
        """Возвращает приглашение на управление профилем."""
        try:
            claim = obj.claim_invitation
        except ArtistProfileClaimInvitation.DoesNotExist:
            return None

        return ArtistProfileClaimInvitationShortSerializer(
            claim,
        ).data


class ManagedArtistProfileCreateSerializer(serializers.ModelSerializer):
    """Сериализатор создания артиста лейблом."""

    class Meta:
        model = ArtistProfile
        fields = (
            'id',
            'name',
            'description',
            'city',
            'slug',
        )
        read_only_fields = ('id',)
        extra_kwargs = {
            'slug': {
                'required': False,
                'allow_blank': False,
            },
        }

    def create(self, validated_data):
        """Создает профиль артиста, управляемый текущим лейблом."""
        label = self.context['request'].user.artist_profile

        return ArtistProfile.objects.create(
            profile_type=ArtistProfileType.ARTIST,
            label=label,
            user=None,
            **validated_data,
        )
