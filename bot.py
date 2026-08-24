import os
import sqlite3
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands, tasks


# =========================================================
# CONFIG
# =========================================================

TOKEN = os.getenv("TOKEN")

POINTS_PER_HOUR = 10
INACTIVITY_MINUTES = 15
TICK_SECONDS = 30

DB_FILE = "points.db"


# =========================================================
# DATABASE
# =========================================================

db = sqlite3.connect(DB_FILE, check_same_thread=False)
db.row_factory = sqlite3.Row

db.execute("""
CREATE TABLE IF NOT EXISTS users (
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    points INTEGER NOT NULL DEFAULT 0,
    voice_seconds INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (guild_id, user_id)
)
""")

db.execute("""
CREATE TABLE IF NOT EXISTS guild_settings (
    guild_id INTEGER PRIMARY KEY,
    notification_channel_id INTEGER,
    dm_enabled INTEGER NOT NULL DEFAULT 0,
    afk_channel_id INTEGER,
    notification_message TEXT NOT NULL DEFAULT '🎉 حصلت على **{added} نقطة**! - 🎙️ وقتك المحتسب: **{time}** - 🪙 رصيدك الحالي: **{points} نقطة**'
)
""")

db.execute("""
CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    amount INTEGER NOT NULL,
    old_points INTEGER NOT NULL,
    new_points INTEGER NOT NULL,
    reason TEXT,
    created_at TEXT NOT NULL
)
""")

db.commit()


# =========================================================
# DATABASE FUNCTIONS
# =========================================================

def ensure_user(guild_id: int, user_id: int):
    db.execute(
        """
        INSERT OR IGNORE INTO users
        (guild_id, user_id, points, voice_seconds)
        VALUES (?, ?, 0, 0)
        """,
        (guild_id, user_id)
    )
    db.commit()


def get_user(guild_id: int, user_id: int):
    ensure_user(guild_id, user_id)

    return db.execute(
        """
        SELECT *
        FROM users
        WHERE guild_id = ?
        AND user_id = ?
        """,
        (guild_id, user_id)
    ).fetchone()


def update_user(
    guild_id: int,
    user_id: int,
    points=None,
    voice_seconds=None
):
    current = get_user(guild_id, user_id)

    new_points = (
        current["points"]
        if points is None
        else points
    )

    new_seconds = (
        current["voice_seconds"]
        if voice_seconds is None
        else voice_seconds
    )

    db.execute(
        """
        UPDATE users
        SET points = ?,
            voice_seconds = ?
        WHERE guild_id = ?
        AND user_id = ?
        """,
        (
            new_points,
            new_seconds,
            guild_id,
            user_id
        )
    )

    db.commit()


def add_history(
    guild_id,
    user_id,
    action,
    amount,
    old_points,
    new_points,
    reason
):
    db.execute(
        """
        INSERT INTO history (
            guild_id,
            user_id,
            action,
            amount,
            old_points,
            new_points,
            reason,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            guild_id,
            user_id,
            action,
            amount,
            old_points,
            new_points,
            reason,
            datetime.now(timezone.utc).isoformat()
        )
    )

    db.commit()


def get_settings(guild_id: int):
    row = db.execute(
        """
        SELECT *
        FROM guild_settings
        WHERE guild_id = ?
        """,
        (guild_id,)
    ).fetchone()

    if row is None:

        db.execute(
            """
            INSERT INTO guild_settings (
                guild_id
            )
            VALUES (?)
            """,
            (guild_id,)
        )

        db.commit()

        row = db.execute(
            """
            SELECT *
            FROM guild_settings
            WHERE guild_id = ?
            """,
            (guild_id,)
        ).fetchone()

    return row


# =========================================================
# TIME FORMAT
# =========================================================

def format_time(seconds: int):

    seconds = int(seconds)

    days = seconds // 86400
    seconds %= 86400

    hours = seconds // 3600
    seconds %= 3600

    minutes = seconds // 60
    seconds %= 60

    parts = []

    if days:
        parts.append(f"{days} يوم")

    if hours:
        parts.append(f"{hours} ساعة")

    if minutes:
        parts.append(f"{minutes} دقيقة")

    if seconds and not parts:
        parts.append(f"{seconds} ثانية")

    if not parts:
        return "0 دقيقة"

    return " و".join(parts)


# =========================================================
# BOT
# =========================================================

intents = discord.Intents.default()

intents.guilds = True
intents.members = True
intents.message_content = True
intents.voice_states = True
intents.reactions = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)


# =========================================================
# VOICE SESSIONS
# =========================================================

voice_sessions = {}


def current_time():
    return datetime.now(timezone.utc)


def is_in_afk(member: discord.Member):

    settings = get_settings(
        member.guild.id
    )

    afk_channel_id = settings[
        "afk_channel_id"
    ]

    if not afk_channel_id:
        return False

    if not member.voice:
        return False

    if not member.voice.channel:
        return False

    return (
        member.voice.channel.id
        == afk_channel_id
    )


def is_active(guild_id, user_id):

    session = voice_sessions.get(
        (guild_id, user_id)
    )

    if not session:
        return False

    inactive_seconds = (
        current_time()
        - session["last_activity"]
    ).total_seconds()

    return (
        inactive_seconds
        < INACTIVITY_MINUTES * 60
    )


# =========================================================
# ACTIVITY
# =========================================================

def register_activity(member: discord.Member):

    if member.bot:
        return

    if not member.voice:
        return

    if not member.voice.channel:
        return

    key = (
        member.guild.id,
        member.id
    )

    if key in voice_sessions:

        voice_sessions[key][
            "last_activity"
        ] = current_time()


# =========================================================
# NOTIFICATIONS
# =========================================================

async def send_point_notification(
    guild: discord.Guild,
    member: discord.Member,
    added: int,
    total_points: int,
    total_seconds: int
):

    settings = get_settings(
        guild.id
    )

    message = settings[
        "notification_message"
    ]

    replacements = {
        "{user}": member.mention,
        "{points}": str(total_points),
        "{added}": str(added),
        "{time}": format_time(total_seconds),
        "{total_time}": format_time(total_seconds)
    }

    for key, value in replacements.items():
        message = message.replace(
            key,
            value
        )

    # -----------------------------------------
    # CHANNEL
    # -----------------------------------------

    channel_id = settings[
        "notification_channel_id"
    ]

    if channel_id:

        channel = guild.get_channel(
            channel_id
        )

        if channel:

            try:
                await channel.send(
                    message
                )

            except Exception as error:
                print(
                    f"[CHANNEL ERROR] {error}"
                )

    # -----------------------------------------
    # DM
    # -----------------------------------------

    if settings["dm_enabled"]:

        try:
            await member.send(
                message
            )

        except Exception as error:
            print(
                f"[DM ERROR] {member}: {error}"
            )


# =========================================================
# PROCESS VOICE
# =========================================================

async def process_voice_member(
    guild: discord.Guild,
    member: discord.Member,
    now_time: datetime
):

    if member.bot:
        return

    if not member.voice:
        return

    if not member.voice.channel:
        return

    key = (
        guild.id,
        member.id
    )

    # -----------------------------------------
    # AFK
    # -----------------------------------------

    if is_in_afk(member):

        if key in voice_sessions:

            voice_sessions[key][
                "last_tick"
            ] = now_time

        return

    # -----------------------------------------
    # NEW SESSION
    # -----------------------------------------

    if key not in voice_sessions:

        voice_sessions[key] = {
            "last_tick": now_time,
            "last_activity": now_time
        }

        return

    session = voice_sessions[key]

    elapsed = (
        now_time
        - session["last_tick"]
    ).total_seconds()

    session["last_tick"] = now_time

    if elapsed <= 0:
        return

    # -----------------------------------------
    # INACTIVITY
    # -----------------------------------------

    if not is_active(
        guild.id,
        member.id
    ):

        session[
            "last_tick"
        ] = now_time

        return

    # -----------------------------------------
    # SAVE TIME
    # -----------------------------------------

    user = get_user(
        guild.id,
        member.id
    )

    old_seconds = user[
        "voice_seconds"
    ]

    new_seconds = (
        old_seconds
        + int(elapsed)
    )

    old_points = user[
        "points"
    ]

    old_hours = (
        old_seconds // 3600
    )

    new_hours = (
        new_seconds // 3600
    )

    gained_hours = (
        new_hours
        - old_hours
    )

    gained_points = (
        gained_hours
        * POINTS_PER_HOUR
    )

    update_user(
        guild.id,
        member.id,
        points=old_points + gained_points,
        voice_seconds=new_seconds
    )

    # -----------------------------------------
    # POINTS REWARD
    # -----------------------------------------

    if gained_points > 0:

        new_points = (
            old_points
            + gained_points
        )

        add_history(
            guild.id,
            member.id,
            "voice",
            gained_points,
            old_points,
            new_points,
            "Voice activity"
        )

        await send_point_notification(
            guild,
            member,
            gained_points,
            new_points,
            new_seconds
        )


# =========================================================
# BACKGROUND LOOP
# =========================================================

@tasks.loop(seconds=TICK_SECONDS)
async def points_loop():

    now_time = current_time()

    for guild in bot.guilds:

        for member in guild.members:

            if member.bot:
                continue

            if not member.voice:
                continue

            try:

                await process_voice_member(
                    guild,
                    member,
                    now_time
                )

            except Exception as error:

                print(
                    f"[POINT LOOP ERROR] "
                    f"{guild.id}/{member.id}: "
                    f"{error}"
                )


@points_loop.before_loop
async def before_points_loop():

    await bot.wait_until_ready()


# =========================================================
# VOICE EVENT
# =========================================================

@bot.event
async def on_voice_state_update(
    member,
    before,
    after
):

    if member.bot:
        return

    key = (
        member.guild.id,
        member.id
    )

    now_time = current_time()

    # -----------------------------------------
    # JOIN
    # -----------------------------------------

    if (
        before.channel is None
        and after.channel is not None
    ):

        voice_sessions[key] = {
            "last_tick": now_time,
            "last_activity": now_time
        }

        return

    # -----------------------------------------
    # LEAVE
    # -----------------------------------------

    if (
        before.channel is not None
        and after.channel is None
    ):

        voice_sessions.pop(
            key,
            None
        )

        return

    # -----------------------------------------
    # MOVE
    # -----------------------------------------

    if (
        before.channel is not None
        and after.channel is not None
        and before.channel.id
        != after.channel.id
    ):

        voice_sessions[key] = {
            "last_tick": now_time,
            "last_activity": now_time
        }


# =========================================================
# MESSAGE ACTIVITY
# =========================================================

@bot.event
async def on_message(message):

    if message.author.bot:
        return

    if isinstance(
        message.author,
        discord.Member
    ):

        register_activity(
            message.author
        )

    await bot.process_commands(
        message
    )


# =========================================================
# REACTION ACTIVITY
# =========================================================

@bot.event
async def on_raw_reaction_add(
    payload
):

    if payload.guild_id is None:
        return

    guild = bot.get_guild(
        payload.guild_id
    )

    if not guild:
        return

    member = guild.get_member(
        payload.user_id
    )

    if not member:
        return

    if member.bot:
        return

    register_activity(
        member
    )


# =========================================================
# /points
# =========================================================

@bot.tree.command(
    name="points",
    description="عرض نقاطك ووقت الفويس"
)
async def points(
    interaction: discord.Interaction
):

    data = get_user(
        interaction.guild.id,
        interaction.user.id
    )

    embed = discord.Embed(
        title="🪙 نقاطك",
        color=discord.Color.gold()
    )

    embed.add_field(
        name="🪙 النقاط",
        value=f"**{data['points']}**",
        inline=True
    )

    embed.add_field(
        name="🎙️ وقت الفويس",
        value=format_time(
            data["voice_seconds"]
        ),
        inline=True
    )

    await interaction.response.send_message(
        embed=embed,
        ephemeral=True
    )


# =========================================================
# /points-top
# =========================================================

@bot.tree.command(
    name="points-top",
    description="عرض أعلى الأعضاء بالنقاط"
)
async def points_top(
    interaction: discord.Interaction
):

    rows = db.execute(
        """
        SELECT user_id, points, voice_seconds
        FROM users
        WHERE guild_id = ?
        ORDER BY points DESC
        LIMIT 10
        """,
        (interaction.guild.id,)
    ).fetchall()

    if not rows:

        return await interaction.response.send_message(
            "❌ لا توجد بيانات بعد.",
            ephemeral=True
        )

    text = ""

    medals = [
        "🥇",
        "🥈",
        "🥉"
    ]

    for index, row in enumerate(
        rows,
        start=1
    ):

        member = interaction.guild.get_member(
            row["user_id"]
        )

        name = (
            member.display_name
            if member
            else f"User {row['user_id']}"
        )

        medal = (
            medals[index - 1]
            if index <= 3
            else f"**{index}.**"
        )

        text += (
            f"{medal} {name} — "
            f"**{row['points']} نقطة**\n"
        )

    embed = discord.Embed(
        title="🏆 Top Points",
        description=text,
        color=discord.Color.gold()
    )

    await interaction.response.send_message(
        embed=embed
    )


# =========================================================
# /points-user
# =========================================================

@bot.tree.command(
    name="points-user",
    description="عرض نقاط عضو معين"
)
@app_commands.describe(
    user="العضو"
)
async def points_user(
    interaction,
    user: discord.Member
):

    data = get_user(
        interaction.guild.id,
        user.id
    )

    embed = discord.Embed(
        title=f"🪙 نقاط {user.display_name}",
        color=discord.Color.blurple()
    )

    embed.add_field(
        name="🪙 النقاط",
        value=str(data["points"]),
        inline=True
    )

    embed.add_field(
        name="🎙️ وقت الفويس",
        value=format_time(
            data["voice_seconds"]
        ),
        inline=True
    )

    await interaction.response.send_message(
        embed=embed
    )


# =========================================================
# ADMIN CHECK
# =========================================================

def admin_only():

    return app_commands.checks.has_permissions(
        administrator=True
    )


# =========================================================
# /points-give
# =========================================================

@bot.tree.command(
    name="points-give",
    description="إعطاء نقاط لعضو"
)
@admin_only()
@app_commands.describe(
    user="العضو",
    amount="عدد النقاط",
    reason="سبب العملية"
)
async def points_give(
    interaction,
    user: discord.Member,
    amount: app_commands.Range[int, 1, 1000000],
    reason: str = "بدون سبب"
):

    data = get_user(
        interaction.guild.id,
        user.id
    )

    old = data["points"]
    new = old + amount

    update_user(
        interaction.guild.id,
        user.id,
        points=new
    )

    add_history(
        interaction.guild.id,
        user.id,
        "give",
        amount,
        old,
        new,
        reason
    )

    await interaction.response.send_message(
        f"✅ تم إعطاء {user.mention} "
        f"**{amount} نقطة**.\n"
        f"🪙 رصيده الآن: **{new}**\n"
        f"📝 السبب: {reason}"
    )


# =========================================================
# /points-remove
# =========================================================

@bot.tree.command(
    name="points-remove",
    description="خصم نقاط من عضو"
)
@admin_only()
@app_commands.describe(
    user="العضو",
    amount="عدد النقاط",
    reason="سبب العملية"
)
async def points_remove(
    interaction,
    user: discord.Member,
    amount: app_commands.Range[int, 1, 1000000],
    reason: str = "بدون سبب"
):

    data = get_user(
        interaction.guild.id,
        user.id
    )

    old = data["points"]

    new = max(
        0,
        old - amount
    )

    removed = old - new

    update_user(
        interaction.guild.id,
        user.id,
        points=new
    )

    add_history(
        interaction.guild.id,
        user.id,
        "remove",
        removed,
        old,
        new,
        reason
    )

    await interaction.response.send_message(
        f"✅ تم خصم **{removed} نقطة** "
        f"من {user.mention}.\n"
        f"🪙 رصيده الآن: **{new}**\n"
        f"📝 السبب: {reason}"
    )


# =========================================================
# /points-set
# =========================================================

@bot.tree.command(
    name="points-set",
    description="تحديد نقاط عضو"
)
@admin_only()
@app_commands.describe(
    user="العضو",
    amount="النقاط الجديدة",
    reason="سبب العملية"
)
async def points_set(
    interaction,
    user: discord.Member,
    amount: app_commands.Range[int, 0, 1000000],
    reason: str = "بدون سبب"
):

    data = get_user(
        interaction.guild.id,
        user.id
    )

    old = data["points"]

    update_user(
        interaction.guild.id,
        user.id,
        points=amount
    )

    add_history(
        interaction.guild.id,
        user.id,
        "set",
        amount - old,
        old,
        amount,
        reason
    )

    await interaction.response.send_message(
        f"✅ تم تغيير نقاط {user.mention} "
        f"من **{old}** إلى **{amount}**."
    )


# =========================================================
# /points-history
# =========================================================

@bot.tree.command(
    name="points-history",
    description="عرض سجل النقاط"
)
@app_commands.describe(
    user="عضو معين - اختياري"
)
async def points_history(
    interaction,
    user: discord.Member = None
):

    target = (
        user
        if user
        else interaction.user
    )

    rows = db.execute(
        """
        SELECT *
        FROM history
        WHERE guild_id = ?
        AND user_id = ?
        ORDER BY id DESC
        LIMIT 15
        """,
        (
            interaction.guild.id,
            target.id
        )
    ).fetchall()

    if not rows:

        return await interaction.response.send_message(
            "📜 لا يوجد سجل.",
            ephemeral=True
        )

    text = ""

    for row in rows:

        if row["action"] == "remove":
            symbol = "🔻"

        elif row["action"] == "give":
            symbol = "🔺"

        elif row["action"] == "voice":
            symbol = "🎙️"

        elif row["action"] == "buy":
            symbol = "🛒"

        else:
            symbol = "⚙️"

        text += (
            f"{symbol} **{row['action']}** — "
            f"{row['amount']} نقطة\n"
            f"↳ {row['old_points']} → "
            f"{row['new_points']}\n"
            f"↳ {row['reason'] or 'بدون سبب'}\n\n"
        )

    embed = discord.Embed(
        title=f"📜 سجل {target.display_name}",
        description=text[:4096],
        color=discord.Color.blurple()
    )

    await interaction.response.send_message(
        embed=embed,
        ephemeral=True
    )


# =========================================================
# /points-reset
# =========================================================

@bot.tree.command(
    name="points-reset",
    description="تصفير نقاط عضو"
)
@admin_only()
@app_commands.describe(
    user="العضو",
    reason="سبب التصفير"
)
async def points_reset(
    interaction,
    user: discord.Member,
    reason: str = "بدون سبب"
):

    data = get_user(
        interaction.guild.id,
        user.id
    )

    old = data["points"]

    update_user(
        interaction.guild.id,
        user.id,
        points=0
    )

    add_history(
        interaction.guild.id,
        user.id,
        "reset",
        -old,
        old,
        0,
        reason
    )

    await interaction.response.send_message(
        f"♻️ تم تصفير نقاط "
        f"{user.mention}.\n"
        f"🪙 كان لديه: **{old} نقطة**."
    )


# =========================================================
# /points-setup
# =========================================================

@bot.tree.command(
    name="points-setup",
    description="إعداد نظام النقاط"
)
@admin_only()
@app_commands.describe(
    notification_channel="روم إشعارات النقاط - اختياري",
    dm="إرسال إشعارات DM؟",
    afk_channel="روم AFK المستثنى من الحساب - اختياري"
)
async def points_setup(
    interaction,
    notification_channel: discord.TextChannel = None,
    dm: bool = False,
    afk_channel: discord.VoiceChannel = None
):

    db.execute(
        """
        INSERT INTO guild_settings (
            guild_id,
            notification_channel_id,
            dm_enabled,
            afk_channel_id
        )
        VALUES (?, ?, ?, ?)
        ON CONFLICT(guild_id)
        DO UPDATE SET
            notification_channel_id =
                excluded.notification_channel_id,
            dm_enabled =
                excluded.dm_enabled,
            afk_channel_id =
                excluded.afk_channel_id
        """,
        (
            interaction.guild.id,
            (
                notification_channel.id
                if notification_channel
                else None
            ),
            int(dm),
            (
                afk_channel.id
                if afk_channel
                else None
            )
        )
    )

    db.commit()

    channel_text = (
        notification_channel.mention
        if notification_channel
        else "❌ غير محدد"
    )

    afk_text = (
        afk_channel.mention
        if afk_channel
        else "❌ غير محدد"
    )

    dm_text = (
        "✅ مفعّل"
        if dm
        else "❌ معطل"
    )

    embed = discord.Embed(
        title="⚙️ إعدادات نظام النقاط",
        color=discord.Color.green()
    )

    embed.add_field(
        name="📢 روم الإشعارات",
        value=channel_text,
        inline=False
    )

    embed.add_field(
        name="💌 DM",
        value=dm_text,
        inline=True
    )

    embed.add_field(
        name="💤 AFK",
        value=afk_text,
        inline=True
    )

    embed.add_field(
        name="🎙️ النظام",
        value=(
            "10 نقاط لكل ساعة\n"
            "15 دقيقة بدون نشاط = إيقاف الحساب\n"
            "الميكروفون المغلق لا يمنع احتساب الوقت"
        ),
        inline=False
    )

    await interaction.response.send_message(
        embed=embed
    )


# =========================================================
# /points-message
# =========================================================

@bot.tree.command(
    name="points-message",
    description="تغيير رسالة إشعار النقاط"
)
@admin_only()
@app_commands.describe(
    message="رسالة الإشعار"
)
async def points_message(
    interaction,
    message: str
):

    if len(message) > 2000:

        return await interaction.response.send_message(
            "❌ الرسالة طويلة جدًا.",
            ephemeral=True
        )

    db.execute(
        """
        UPDATE guild_settings
        SET notification_message = ?
        WHERE guild_id = ?
        """,
        (
            message,
            interaction.guild.id
        )
    )

    db.commit()

    await interaction.response.send_message(
        "✅ تم تغيير رسالة إشعار النقاط."
    )


# =========================================================
# /points-channel
# =========================================================

@bot.tree.command(
    name="points-channel",
    description="تحديد روم إشعارات النقاط"
)
@admin_only()
@app_commands.describe(
    channel="الروم - اتركه فارغًا لإلغاء الإشعارات"
)
async def points_channel(
    interaction,
    channel: discord.TextChannel = None
):

    db.execute(
        """
        UPDATE guild_settings
        SET notification_channel_id = ?
        WHERE guild_id = ?
        """,
        (
            channel.id
            if channel
            else None,
            interaction.guild.id
        )
    )

    db.commit()

    if channel:

        text = (
            f"✅ تم تحديد {channel.mention} "
            f"كروم إشعارات."
        )

    else:

        text = (
            "✅ تم إلغاء روم الإشعارات."
        )

    await interaction.response.send_message(
        text
    )


# =========================================================
# SHOP
# =========================================================

SHOP_ITEMS = {
    "100": "🎁 مكافأة 100 نقطة",
    "500": "⭐ مكافأة 500 نقطة",
    "1000": "💎 مكافأة 1000 نقطة",
    "2500": "👑 مكافأة 2500 نقطة"
}


# =========================================================
# /shop
# =========================================================

@bot.tree.command(
    name="shop",
    description="عرض متجر النقاط"
)
async def shop(
    interaction: discord.Interaction
):

    text = (
        "🛒 **متجر النقاط**\n\n"
        "استخدم `/buy` للشراء.\n\n"
        "🎁 `100` نقطة — مكافأة صغيرة\n"
        "⭐ `500` نقطة — مكافأة متوسطة\n"
        "💎 `1000` نقطة — مكافأة كبيرة\n"
        "👑 `2500` نقطة — مكافأة أسطورية"
    )

    await interaction.response.send_message(
        text
    )


# =========================================================
# /buy
# =========================================================

@bot.tree.command(
    name="buy",
    description="شراء مكافأة بالنقاط"
)
@app_commands.describe(
    item="سعر العنصر"
)
async def buy(
    interaction,
    item: str
):

    if item not in SHOP_ITEMS:

        return await interaction.response.send_message(
            "❌ العنصر غير موجود.\n"
            "استخدم `/shop`.",
            ephemeral=True
        )

    price = int(item)

    data = get_user(
        interaction.guild.id,
        interaction.user.id
    )

    if data["points"] < price:

        return await interaction.response.send_message(
            f"❌ نقاطك غير كافية.\n"
            f"رصيدك: **{data['points']}**\n"
            f"السعر: **{price}**",
            ephemeral=True
        )

    old = data["points"]
    new = old - price

    update_user(
        interaction.guild.id,
        interaction.user.id,
        points=new
    )

    add_history(
        interaction.guild.id,
        interaction.user.id,
        "buy",
        -price,
        old,
        new,
        SHOP_ITEMS[item]
    )

    await interaction.response.send_message(
        f"🛒 تم شراء:\n"
        f"**{SHOP_ITEMS[item]}**\n\n"
        f"🪙 رصيدك الجديد: **{new} نقطة**"
    )


# =========================================================
# /stats
# =========================================================

@bot.tree.command(
    name="stats",
    description="عرض إحصائيات عضو"
)
@app_commands.describe(
    user="العضو - اختياري"
)
async def stats(
    interaction,
    user: discord.Member = None
):

    target = (
        user
        if user
        else interaction.user
    )

    data = get_user(
        interaction.guild.id,
        target.id
    )

    rank = db.execute(
        """
        SELECT COUNT(*) + 1 AS rank
        FROM users
        WHERE guild_id = ?
        AND points > ?
        """,
        (
            interaction.guild.id,
            data["points"]
        )
    ).fetchone()

    embed = discord.Embed(
        title=f"📊 إحصائيات {target.display_name}",
        color=discord.Color.blurple()
    )

    embed.set_thumbnail(
        url=target.display_avatar.url
    )

    embed.add_field(
        name="🪙 النقاط",
        value=f"**{data['points']}**",
        inline=True
    )

    embed.add_field(
        name="🏆 الترتيب",
        value=f"**#{rank['rank']}**",
        inline=True
    )

    embed.add_field(
        name="🎙️ وقت الفويس",
        value=format_time(
            data["voice_seconds"]
        ),
        inline=False
    )

    await interaction.response.send_message(
        embed=embed
    )


# =========================================================
# ERROR HANDLER
# =========================================================

@bot.tree.error
async def on_app_command_error(
    interaction,
    error
):

    if isinstance(
        error,
        app_commands.errors.MissingPermissions
    ):

        message = (
            "❌ هذا الأمر للإدارة فقط."
        )

    else:

        print(
            f"[COMMAND ERROR] {error}"
        )

        message = (
            "❌ حدث خطأ أثناء تنفيذ الأمر."
        )

    try:

        if interaction.response.is_done():

            await interaction.followup.send(
                message,
                ephemeral=True
            )

        else:

            await interaction.response.send_message(
                message,
                ephemeral=True
            )

    except Exception:
        pass


# =========================================================
# READY
# =========================================================

@bot.event
async def on_ready():

    print("=" * 50)
    print(
        f"Logged in as: {bot.user}"
    )
    print(
        f"Bot ID: {bot.user.id}"
    )
    print(
        f"Guilds: {len(bot.guilds)}"
    )
    print("=" * 50)

    try:

        synced = await bot.tree.sync()

        print(
            f"Synced {len(synced)} slash commands."
        )

    except Exception as error:

        print(
            f"[SYNC ERROR] {error}"
        )

    if not points_loop.is_running():

        points_loop.start()


# =========================================================
# START
# =========================================================

if not TOKEN:

    raise RuntimeError(
        "TOKEN environment variable is missing."
    )

bot.run(TOKEN)
