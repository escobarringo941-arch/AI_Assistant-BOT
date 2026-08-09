# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import traceback
from typing import Any

import discord

_ACTION_TIMEOUT = 30.0


async def defer_update(interaction: discord.Interaction) -> bool:
    """Acknowledge a component interaction immediately, then edit it later."""
    if interaction.response.is_done():
        return True
    try:
        await interaction.response.defer()
        return True
    except (discord.HTTPException, discord.NotFound):
        return False


async def defer_private(interaction: discord.Interaction, *, thinking: bool = True) -> bool:
    """Acknowledge a modal/owner action immediately with a private response."""
    if interaction.response.is_done():
        return True
    try:
        await interaction.response.defer(ephemeral=True, thinking=thinking)
        return True
    except (discord.HTTPException, discord.NotFound):
        return False


async def safe_edit(interaction: discord.Interaction, **kwargs: Any):
    """Edit the source/original response regardless of ACK state."""
    try:
        if interaction.response.is_done():
            return await interaction.edit_original_response(**kwargs)
        return await interaction.response.edit_message(**kwargs)
    except (discord.NotFound, discord.HTTPException):
        try:
            return await interaction.followup.send(
                content=kwargs.get("content") or "✅ العملية كملات.",
                embed=kwargs.get("embed"),
                view=kwargs.get("view"),
                ephemeral=True,
            )
        except Exception:
            return None


async def safe_private(interaction: discord.Interaction, content: str | None = None, **kwargs: Any):
    try:
        if interaction.response.is_done():
            return await interaction.followup.send(content=content, ephemeral=True, **kwargs)
        return await interaction.response.send_message(content=content, ephemeral=True, **kwargs)
    except (discord.NotFound, discord.HTTPException):
        return None


async def guarded(coro, *, timeout: float = _ACTION_TIMEOUT):
    return await asyncio.wait_for(coro, timeout=timeout)


async def interaction_failure(interaction: discord.Interaction, error: Exception, *, where: str = "CITY"):
    print(f"[{where}] {type(error).__name__}: {error}")
    traceback.print_exception(type(error), error, error.__traceback__)
    if isinstance(error, asyncio.TimeoutError):
        message = "⏳ العملية خذات وقت أكثر من اللازم وتوقفات. البانل بقات خدامة؛ عاود جرّب مرة وحدة."
    else:
        message = "⚠️ وقع مشكل تقني، البانل بقات خدامة. ما تعاودش تضغط بسرعة؛ عاود جرّب مرة وحدة."
    # Modal submits are commonly deferred with a thinking placeholder. Replace
    # that placeholder so Discord never leaves the user on an endless spinner.
    try:
        if interaction.type == discord.InteractionType.modal_submit and interaction.response.is_done():
            await interaction.edit_original_response(content=message, embed=None, view=None)
            return
    except Exception:
        pass
    await safe_private(interaction, message)


class ReliableView(discord.ui.View):
    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item[Any]) -> None:
        await interaction_failure(interaction, error, where=f"CITY VIEW {type(self).__name__}")


class ReliableModal(discord.ui.Modal):
    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        await interaction_failure(interaction, error, where=f"CITY MODAL {type(self).__name__}")
