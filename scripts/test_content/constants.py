"""Константы импорта тестового контента."""

FIXTURE_NAMESPACE = 'test_server_content'
AUDIO_FIXTURE = b'ID3\x03\x00\x00\x00\x00\x00\x21TEST_FIXTURE_AUDIO'
MERCH_KIND_ALIASES = {
    'cassette': ('cassette', 'audio-cassette', 'tape', 'кассета'),
    'cap': ('cap', 'baseball-cap', 'hat', 'kepka', 'кепка', 'бейсболка'),
    'cd': ('cd', 'compact-disc', 'compactdisc', 'audio-cd', 'disc', 'диск'),
    'tshirt': ('tshirt', 't-shirt', 'shirt', 'tee', 'футболка'),
    'vinyl': ('vinyl', 'vinyl-record', 'record', 'lp', 'винил', 'пластинка'),
}
