# -*- coding: utf-8 -*-
"""models/enums.py — Enumerations shared across the bot."""

from enum import Enum


class LoopMode(Enum):
    OFF   = "off"
    TRACK = "track"
    QUEUE = "queue"

    def next(self) -> "LoopMode":
        """Cycle OFF → TRACK → QUEUE → OFF."""
        order = [LoopMode.OFF, LoopMode.TRACK, LoopMode.QUEUE]
        idx = order.index(self)
        return order[(idx + 1) % len(order)]

    def label(self) -> str:
        return {
            LoopMode.OFF:   "🔁 Loop Off",
            LoopMode.TRACK: "🔂 Loop Track",
            LoopMode.QUEUE: "🔁 Loop Queue",
        }[self]

    def short_label(self) -> str:
        """Short label without emoji, for embed field values."""
        return {
            LoopMode.OFF:   "Off",
            LoopMode.TRACK: "Track",
            LoopMode.QUEUE: "Queue",
        }[self]

    @property
    def emoji(self) -> str:
        """Emoji for use in buttons and compact display."""
        return {
            LoopMode.OFF:   "🔁",
            LoopMode.TRACK: "🔂",
            LoopMode.QUEUE: "🔁🇺",
        }[self]


class AudioEffect(Enum):
    BASS_BOOST     = "bassboost"
    NIGHTCORE      = "nightcore"
    VAPORWAVE      = "vaporwave"
    TREBLE_BOOST   = "trebleboost"
    VOCAL_BOOST    = "vocalboost"
    KARAOKE        = "karaoke"
    VIBRATO        = "vibrato"
    TREMOLO        = "tremolo"
    CHORUS         = "chorus"
    REVERB         = "reverb"
    ECHO           = "echo"
    DISTORTION     = "distortion"
    MONO           = "mono"
    STEREO_ENHANCE = "stereo"
    COMPRESSOR     = "compressor"
    LIMITER        = "limiter"
    NOISE_GATE     = "noisegate"
    AUDIO_8D       = "8d"

    @property
    def display_name(self) -> str:
        return {
            AudioEffect.BASS_BOOST:     "🔊 Bass Boost",
            AudioEffect.NIGHTCORE:      "⚡ Nightcore",
            AudioEffect.VAPORWAVE:      "🌊 Vaporwave",
            AudioEffect.TREBLE_BOOST:   "🎵 Treble Boost",
            AudioEffect.VOCAL_BOOST:    "🎤 Vocal Boost",
            AudioEffect.KARAOKE:        "🎙️ Karaoke",
            AudioEffect.VIBRATO:        "〰️ Vibrato",
            AudioEffect.TREMOLO:        "🎶 Tremolo",
            AudioEffect.CHORUS:         "🎼 Chorus",
            AudioEffect.REVERB:         "🏛️ Reverb",
            AudioEffect.ECHO:           "📣 Echo",
            AudioEffect.DISTORTION:     "🎸 Distortion",
            AudioEffect.MONO:           "📻 Mono",
            AudioEffect.STEREO_ENHANCE: "🔈 Stereo Enhance",
            AudioEffect.COMPRESSOR:     "📊 Compressor",
            AudioEffect.LIMITER:        "🚧 Limiter",
            AudioEffect.NOISE_GATE:     "🚪 Noise Gate",
            AudioEffect.AUDIO_8D:       "🎧 8D Audio",
        }[self]

    @classmethod
    def from_value(cls, value: str) -> "AudioEffect | None":
        for member in cls:
            if member.value == value:
                return member
        return None


class AudioQuality(Enum):
    LOW    = ("96k",  "Low Quality")
    MEDIUM = ("128k", "Medium Quality")
    HIGH   = ("192k", "High Quality")
    ULTRA  = ("256k", "Ultra Quality")

    @property
    def bitrate(self) -> str:
        return self.value[0]

    @property
    def label(self) -> str:
        return self.value[1]
