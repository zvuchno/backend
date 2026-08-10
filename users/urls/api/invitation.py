from django.urls import path

from users.views import (
    ArtistProfileClaimInvitationAcceptView,
    ArtistProfileClaimInvitationRejectView,
    ArtistProfileClaimInvitationView,
)

urlpatterns = [
    path(
        'artist-profile-claim/',
        ArtistProfileClaimInvitationView.as_view(),
        name='artist_profile_claim_inspect',
    ),
    path(
        'artist-profile-claim/accept/',
        ArtistProfileClaimInvitationAcceptView.as_view(),
        name='artist_profile_claim_accept',
    ),
    path(
        'artist-profile-claim/reject/',
        ArtistProfileClaimInvitationRejectView.as_view(),
        name='artist_profile_claim_reject',
    ),
]
