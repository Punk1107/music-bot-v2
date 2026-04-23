# -*- coding: utf-8 -*-
"""
core/audio.py — FFmpeg argument builder & audio-effects processor.

AudioEffectsProcessor.build_ffmpeg_options() returns the `before_options`
and `options` dicts expected by discord.py's FFmpegPCMAudio.
"""

from __future__ import annotations

from models.enums import AudioEffect, AudioQuality


# ── FFmpeg effect filter strings ──────────────────────────────────────────────

_EFFECT_FILTERS: dict[AudioEffect, str] = {
    AudioEffect.BASS_BOOST:     "bass=g=15,dynaudnorm",
    AudioEffect.NIGHTCORE:      "asetrate=48000*1.25,aresample=48000,atempo=1.06",
    AudioEffect.VAPORWAVE:      "asetrate=48000*0.8,aresample=48000,atempo=1.1",
    AudioEffect.TREBLE_BOOST:   "treble=g=8",
    AudioEffect.VOCAL_BOOST:    "afftfilt=real='re * (f >= 300 && f <= 3000)'",
    AudioEffect.KARAOKE:        "pan=mono|c0=0.5*c0+-0.5*c1",
    AudioEffect.VIBRATO:        "vibrato=f=6.5:d=0.35",
    AudioEffect.TREMOLO:        "tremolo=f=8.8:d=0.6",
    AudioEffect.CHORUS:         "chorus=0.7:0.9:55:0.4:0.25:2",
    AudioEffect.REVERB:         "aecho=0.8:0.9:1000:0.3",
    AudioEffect.ECHO:           "aecho=0.8:0.88:60:0.4",
    AudioEffect.DISTORTION:     "afftfilt=real='hypot(re,im)*sin(0)'",
    AudioEffect.MONO:           "pan=mono|c0=0.5*c0+0.5*c1",
    AudioEffect.STEREO_ENHANCE: "extrastereo=m=2.5",
    AudioEffect.COMPRESSOR:     "acompressor=threshold=0.089:ratio=9:attack=200:release=1000",
    AudioEffect.LIMITER:        "alimiter=level_in=1:level_out=0.8:limit=0.8",
    AudioEffect.NOISE_GATE:     "agate=threshold=0.03:ratio=2:attack=20:release=250",
    AudioEffect.AUDIO_8D:       "apulsator=hz=0.125,extrastereo=m=1.5",
}

# ── Quality bitrate map ───────────────────────────────────────────────────────

_QUALITY_BITRATE: dict[str, str] = {
    "LOW":    "96k",
    "MEDIUM": "128k",
    "HIGH":   "192k",
    "ULTRA":  "256k",
}


# ── Processor ─────────────────────────────────────────────────────────────────

class AudioEffectsProcessor:
    """Build FFmpeg before_options / options strings for discord.py playback."""

    def build_ffmpeg_options(
        self,
        *,
        effects:    list[AudioEffect] | None = None,
        volume:     float = 1.0,
        start_time: int   = 0,
        quality:    str   = "MEDIUM",
    ) -> dict[str, str]:
        """
        Return a dict with keys `before_options` and `options` suitable
        for `discord.FFmpegPCMAudio(**result)`.

        Parameters
        ----------
        effects:    list of AudioEffect members to apply (order matters)
        volume:     linear volume multiplier (1.0 = unity)
        start_time: seek position in seconds
        quality:    one of LOW / MEDIUM / HIGH / ULTRA
        """
        # ── before_options ────────────────────────────────────────────────────
        before_parts = [
            "-reconnect",        "1",
            "-reconnect_streamed","1",
            "-reconnect_delay_max","5",
            "-analyzeduration",  "0",
            "-loglevel",         "quiet",
            "-fflags",           "+discardcorrupt",
        ]
        if start_time > 0:
            before_parts += ["-ss", str(start_time)]

        # ── options (output side) ─────────────────────────────────────────────
        bitrate = _QUALITY_BITRATE.get(quality.upper(), "128k")
        option_parts = ["-vn", "-b:a", bitrate, "-ar", "48000", "-ac", "2"]

        # Assemble filter chain
        filters: list[str] = []
        for eff in (effects or []):
            flt = _EFFECT_FILTERS.get(eff)
            if flt:
                filters.append(flt)

        if volume != 1.0:
            filters.append(f"volume={volume:.4f}")

        # Always append dynamic normalisation at the end
        filters.append("dynaudnorm=f=75:g=25:p=0.55")

        option_parts += ["-af", ",".join(filters)]

        return {
            "before_options": " ".join(before_parts),
            "options":        " ".join(option_parts),
        }
