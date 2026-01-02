"""
Settings Handler - User preferences configuration
"""

from pyrogram import Client
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from services import database


async def handle(client: Client, message: Message):
    """Handle /settings command."""
    user_id = message.from_user.id
    settings = await database.get_user_settings(user_id)
    
    text = format_settings_text(settings)
    keyboard = create_settings_keyboard(settings)
    
    await message.reply(text, reply_markup=keyboard)


async def handle_callback(client: Client, callback: CallbackQuery):
    """Handle settings button callbacks."""
    data = callback.data
    user_id = callback.from_user.id
    
    if data == "set:menu":
        # Show settings menu
        settings = await database.get_user_settings(user_id)
        text = format_settings_text(settings)
        keyboard = create_settings_keyboard(settings)
        await callback.message.edit_text(text, reply_markup=keyboard)
    
    elif data.startswith("set:source:"):
        # Change source
        source = data.split(":")[-1]
        await database.update_user_setting(user_id, "source", source)
        await refresh_settings(callback)
        await callback.answer(f"Source set to {source}")
    
    elif data.startswith("set:tidal_q:"):
        # Change Tidal quality
        quality = data.split(":")[-1]
        await database.update_user_setting(user_id, "tidal_quality", quality)
        await refresh_settings(callback)
        await callback.answer(f"Tidal quality set to {quality}")
    
    elif data.startswith("set:qobuz_q:"):
        # Change Qobuz quality
        quality = data.split(":")[-1]
        await database.update_user_setting(user_id, "qobuz_quality", quality)
        await refresh_settings(callback)
        
        quality_names = {"6": "16-bit", "7": "24-bit", "27": "Hi-Res"}
        await callback.answer(f"Qobuz quality set to {quality_names.get(quality, quality)}")
    
    elif data == "set:lyrics":
        # Toggle embed lyrics
        settings = await database.get_user_settings(user_id)
        new_value = 0 if settings.get("embed_lyrics", 0) else 1
        await database.update_user_setting(user_id, "embed_lyrics", new_value)
        await refresh_settings(callback)
        await callback.answer(f"Embed lyrics: {'ON' if new_value else 'OFF'}")
    
    elif data == "set:cover":
        # Toggle max quality cover
        settings = await database.get_user_settings(user_id)
        new_value = 0 if settings.get("embed_max_cover", 1) else 1
        await database.update_user_setting(user_id, "embed_max_cover", new_value)
        await refresh_settings(callback)
        await callback.answer(f"Max quality cover: {'ON' if new_value else 'OFF'}")
    
    elif data == "set:back":
        # Close settings
        await callback.message.delete()
        await callback.answer()
    
    else:
        await callback.answer()


async def refresh_settings(callback: CallbackQuery):
    """Refresh settings display."""
    settings = await database.get_user_settings(callback.from_user.id)
    text = format_settings_text(settings)
    keyboard = create_settings_keyboard(settings)
    await callback.message.edit_text(text, reply_markup=keyboard)


def format_settings_text(settings: dict) -> str:
    """Format settings as text."""
    source = settings.get("source", "auto").title()
    tidal_q = settings.get("tidal_quality", "LOSSLESS")
    qobuz_q = settings.get("qobuz_quality", "6")
    lyrics = "✅" if settings.get("embed_lyrics", 0) else "❌"
    cover = "✅" if settings.get("embed_max_cover", 1) else "❌"
    
    qobuz_names = {"6": "16-bit (CD)", "7": "24-bit", "27": "Hi-Res 24-bit"}
    
    return f"""
⚙️ **Your Settings**

**Source:** {source}
**Tidal Quality:** {tidal_q.replace('_', ' ')}
**Qobuz Quality:** {qobuz_names.get(qobuz_q, qobuz_q)}

**Embed Lyrics:** {lyrics}
**Max Quality Cover:** {cover}

_Tap buttons below to change settings_
"""


def create_settings_keyboard(settings: dict) -> InlineKeyboardMarkup:
    """Create settings inline keyboard."""
    source = settings.get("source", "auto")
    
    buttons = [
        # Source selection
        [InlineKeyboardButton(
            f"{'🔘' if source == 'auto' else '⚪'} Auto",
            callback_data="set:source:auto"
        ), InlineKeyboardButton(
            f"{'🔘' if source == 'tidal' else '⚪'} Tidal",
            callback_data="set:source:tidal"
        )],
        [InlineKeyboardButton(
            f"{'🔘' if source == 'qobuz' else '⚪'} Qobuz",
            callback_data="set:source:qobuz"
        ), InlineKeyboardButton(
            f"{'🔘' if source == 'amazon' else '⚪'} Amazon",
            callback_data="set:source:amazon"
        )],
    ]
    
    # Quality settings based on source
    if source == "tidal":
        tidal_q = settings.get("tidal_quality", "LOSSLESS")
        buttons.append([
            InlineKeyboardButton(
                f"{'✓' if tidal_q == 'LOSSLESS' else ''} Lossless",
                callback_data="set:tidal_q:LOSSLESS"
            ),
            InlineKeyboardButton(
                f"{'✓' if tidal_q == 'HI_RES_LOSSLESS' else ''} Hi-Res",
                callback_data="set:tidal_q:HI_RES_LOSSLESS"
            )
        ])
    elif source == "qobuz":
        qobuz_q = settings.get("qobuz_quality", "6")
        buttons.append([
            InlineKeyboardButton(
                f"{'✓' if qobuz_q == '6' else ''} 16-bit",
                callback_data="set:qobuz_q:6"
            ),
            InlineKeyboardButton(
                f"{'✓' if qobuz_q == '7' else ''} 24-bit",
                callback_data="set:qobuz_q:7"
            ),
            InlineKeyboardButton(
                f"{'✓' if qobuz_q == '27' else ''} Hi-Res",
                callback_data="set:qobuz_q:27"
            )
        ])
    
    # Toggles
    lyrics_icon = "✅" if settings.get("embed_lyrics", 0) else "❌"
    cover_icon = "✅" if settings.get("embed_max_cover", 1) else "❌"
    
    buttons.append([
        InlineKeyboardButton(f"{lyrics_icon} Embed Lyrics", callback_data="set:lyrics"),
        InlineKeyboardButton(f"{cover_icon} Max Cover", callback_data="set:cover")
    ])
    
    # Close button
    buttons.append([InlineKeyboardButton("✖️ Close", callback_data="set:back")])
    
    return InlineKeyboardMarkup(buttons)
