from __future__ import annotations


def register_music_commands(bot, service) -> None:
    @bot.command(name="play")
    async def play(ctx, *, query: str) -> None:
        await service.enqueue_track_by_query(
            guild_id=ctx.guild.id,
            channel_id=ctx.author.voice.channel.id,
            query=query,
            requester_id=ctx.author.id,
        )
        await ctx.send(f"Queued: {query}")

    @bot.command(name="queue")
    async def queue(ctx) -> None:
        tracks = await service.get_queue(guild_id=ctx.guild.id)
        if not tracks:
            await ctx.send("Queue is empty.")
            return
        await ctx.send("\n".join(f"{idx}. {track.title}" for idx, track in enumerate(tracks, 1)))

    @bot.command(name="skip")
    async def skip(ctx) -> None:
        await service.skip_track(guild_id=ctx.guild.id)
        await ctx.send("Skipped.")

    @bot.command(name="pause")
    async def pause(ctx) -> None:
        await service.pause_player(ctx.guild.voice_client)
        await ctx.send("Paused.")

    @bot.command(name="resume")
    async def resume(ctx) -> None:
        await service.resume_player(ctx.guild.voice_client)
        await ctx.send("Resumed.")

    @bot.command(name="stop")
    async def stop(ctx) -> None:
        await service.stop_player(ctx.guild.id, ctx.guild.voice_client)
        await ctx.send("Stopped.")


async def handle_interaction_play(interaction, service, query: str) -> None:
    await interaction.response.defer(thinking=True)
    result = await service.enqueue_track_by_query(
        guild_id=interaction.guild.id,
        channel_id=interaction.user.voice.channel.id,
        query=query,
        requester_id=interaction.user.id,
    )
    await interaction.followup.send(f"Queued: {result.track.title}")
