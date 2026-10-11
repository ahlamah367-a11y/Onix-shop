import discord
from discord.ext import commands
from discord import app_commands

import json
import os
from datetime import datetime, timedelta
import asyncio
import random
import re


# ==================================
# إعداد البوت
# ==================================

intents = discord.Intents.default()
intents.members = True
intents.message_content = True


GUILD_IDS = [1532326696714240062, 1554569292282994778]


class TicketBot(commands.Bot):
    async def setup_hook(self):
        # مزامنة أوامر السلاش في السيرفرين المحددين فقط.
        for guild_id in GUILD_IDS:
            guild = discord.Object(id=guild_id)
            try:
                self.tree.copy_global_to(guild=guild)
                synced = await self.tree.sync(guild=guild)
                print(f"✅ Slash Commands Synced: {len(synced)} commands to guild {guild_id}")
            except Exception as e:
                print(f"❌ Slash Command Sync Error for guild {guild_id}: {type(e).__name__}: {e}")


bot = TicketBot(
    command_prefix="!",
    intents=intents
)


# 


def default_ticket():

    return {
        "name": "تذكرة جديدة",
        "description": "اضغط لفتح التذكرة",
        "panel_description": "اضغط لفتح التذكرة",
        "emoji": "🎫",
        "name_format": "{name}-{count}",
        "color": "blue",
        "welcome_message": "أهلاً {user} 👋\nسيتم الرد عليك قريباً.",
        "ticket_image": None,
        "image": None,
        "open_category": None,
        "close_category": None,
        "staff_roles": [],
        "staff_mention_role": None,
        "blocked_roles": [],
        "blocked_role": None,
        "open_logs": None,
        "close_logs": None,
        "rating_room": None,
        "claim": True,
        "private_mode": False,
        "rating": True,
        "transcript": True,
        "ask_reason": False,
        "max_tickets": 1,
        "prevent_same_type": True,
        "counter": 0,
        "opened": 0,
        "closed": 0,
        "ratings": [],
        "priority": "normal",
        "auto_close": False,
        "auto_close_time": 24,
        "notes": [],
        "added_members": [],
        "last_activity": None,
        "ticket_controls": {
            "close": True,
            "rename": True,
            "add_member": True,
            "remove_member": True,
            "move": True,
            "priority": True,
            "info": True,
            "add_note": True,
            "notes": True
        }
    }



def default_database():

    return {
        "tickets": {},
        "panel": {
            "title": "🎫 نظام التذاكر",
            "description": "اختر نوع التذكرة من القائمة بالأسفل",
            "image": None,
            "channel": None,
            "message_id": None
        },
        "panels": {},
        "open_tickets": {},
        "closed_today": 0,
        "stats": {
            "total_opened": 0,
            "total_closed": 0,
            "tickets_today": 0,
            "daily_opened": {},
            "daily_closed": {},
            "ratings": [],
            "staff": {},
            "logs": [],
            "permissions": {
                "managers": [],
                "setup_admins": []
            }
        },
        "auto_setup": {},
        "log_channels": {"open": None, "claim": None, "close": None, "rating": None, "note": None, "admin": None}
    }


DATABASE_FILE = "database.json"
BACKUP_FILE = "database_backup.json"

def save_database():
    with open(DATABASE_FILE, "w", encoding="utf-8") as file:
        json.dump(
            database,
            file,
            indent=4,
            ensure_ascii=False
        )



def load_database():

    if not os.path.exists(DATABASE_FILE):
        return default_database()

    with open(DATABASE_FILE, "r", encoding="utf-8") as file:
        try:
            return json.load(file)
        except:
            return default_database()



try:
    database = load_database()
except:
    database = default_database()
    save_database()

# دعم البانلات المتعددة وربط كل بانل بتذاكره الخاصة
if "panels" not in database:
    database["panels"] = {}

if "log_channels" not in database:
    database["log_channels"] = {"open": None, "claim": None, "close": None, "rating": None, "note": None, "admin": None}
else:
    for _log_key in ("open", "claim", "close", "rating", "note", "admin"):
        if _log_key not in database["log_channels"]:
            database["log_channels"][_log_key] = None
    database["log_channels"].pop("ticket", None)

for panel_id, panel in database["panels"].items():
    if "tickets" not in panel:
        panel["tickets"] = []

# دعم الإعداد الجديد للتذاكر القديمة
for ticket_type, ticket_settings in database["tickets"].items():
    if "name_format" not in ticket_settings or ticket_settings.get("name_format") == "{emoji}・{count}":
        ticket_settings["name_format"] = "{name}-{count}"
    if "counter" not in ticket_settings:
        ticket_settings["counter"] = 0
    if "private_mode" not in ticket_settings:
        ticket_settings["private_mode"] = False
    if "staff_mention_role" not in ticket_settings:
        ticket_settings["staff_mention_role"] = None
    default_controls = default_ticket()["ticket_controls"]
    ticket_settings.setdefault("ticket_controls", {})
    for _control_name, _control_default in default_controls.items():
        ticket_settings["ticket_controls"].setdefault(_control_name, _control_default)

# عداد دائم لمعرفات أنواع التذاكر (ticket_1, ticket_2...)
database.setdefault("meta", {})
_existing_type_numbers = []
for _tid in database.get("tickets", {}):
    _m = re.fullmatch(r"ticket_(\d+)", str(_tid))
    if _m:
        _existing_type_numbers.append(int(_m.group(1)))
if database["meta"].get("ticket_type_counter") is None:
    database["meta"]["ticket_type_counter"] = max(_existing_type_numbers, default=0)
else:
    database["meta"]["ticket_type_counter"] = max(
        int(database["meta"].get("ticket_type_counter", 0)),
        max(_existing_type_numbers, default=0)
    )

save_database()



# ==================================
# أدوات مساعدة وتصميم موحد
# ==================================

def make_embed(title, description, color=discord.Color.blue()):

    embed = discord.Embed(
        title=title,
        description=description,
        color=color,
        timestamp=datetime.now()
    )

    embed.set_footer(
        text="🎫 Professional Ticket System"
    )

    return embed



async def send_ticket_log(
    guild,
    log_type,
    title,
    description="",
    color=discord.Color.blue(),
    fields=None,
    file_path=None
):
    """إرسال اللوق إلى الروم المخصص لنوع الحدث."""
    log_id = database.get("log_channels", {}).get(log_type)
    if not log_id:
        return

    log = guild.get_channel(log_id)
    if not log:
        return

    embed = discord.Embed(
        title=title,
        description=description,
        color=color,
        timestamp=datetime.now()
    )

    if fields:
        for name, value, inline in fields:
            embed.add_field(
                name=name,
                value=str(value)[:1024],
                inline=inline
            )

    embed.set_footer(text=f"🎫 Ticket Logs • {log_type.upper()}")

    try:
        if file_path and os.path.exists(file_path):
            await log.send(
                embed=embed,
                file=discord.File(file_path)
            )
        else:
            await log.send(embed=embed)
    except Exception as e:
        print(f"Ticket {log_type} log error: {e}")


async def log_ticket_action(
    interaction,
    action,
    details="",
    color=discord.Color.blue(),
    log_type="admin"
):
    """إجراءات الإدارة تذهب دائماً إلى روم لوق الإدارة."""
    ticket = get_ticket_from_channel(interaction.channel.id)
    if not ticket:
        return

    settings = database["tickets"].get(ticket.get("type"))

    await send_ticket_log(
        interaction.guild,
        log_type,
        f"📝 {action}",
        fields=[
            ("🎫 صاحب التذكرة", f"<@{ticket.get('owner')}>", False),
            (
                "🎟️ النوع",
                settings.get("name", "غير معروف") if settings else "غير معروف",
                True
            ),
            ("👤 الإداري", interaction.user.mention, True),
            ("📌 التفاصيل", details or "—", False),
            (
                "📅 الوقت",
                f"<t:{int(datetime.now().timestamp())}:F>",
                False
            ),
        ],
        color=color
    )


def is_manager(user):
    if user.guild_permissions.administrator:
        return True
    return user.id in database["stats"]["permissions"]["managers"]



def create_ticket_id():
    # عداد دائم محفوظ داخل قاعدة البيانات حتى لا تتكرر أرقام أنواع التذاكر بعد إعادة التشغيل/الحذف.
    meta = database.setdefault("meta", {})
    number = int(meta.get("ticket_type_counter", 0)) + 1
    meta["ticket_type_counter"] = number
    save_database()
    return f"ticket_{number}"



def get_ticket(ticket_id):

    return database["tickets"].get(ticket_id)



def get_ticket_from_channel(channel_id):

    return database["open_tickets"].get(str(channel_id))



async def apply_private_ticket_permissions(channel, ticket):
    """الوضع الخاص: التذكرة تظهر لصاحبها + الإداري الذي استلمها فقط."""
    settings = database.get("tickets", {}).get(ticket.get("type"), {})
    if not bool(settings.get("private_mode", False)):
        return

    overwrites = {channel.guild.default_role: discord.PermissionOverwrite(view_channel=False)}
    owner_id = ticket.get("owner")
    claimed_id = ticket.get("claimed")

    owner = channel.guild.get_member(int(owner_id)) if owner_id else None
    if owner:
        overwrites[owner] = discord.PermissionOverwrite(
            view_channel=True, send_messages=True, read_message_history=True
        )

    claimer = channel.guild.get_member(int(claimed_id)) if claimed_id else None
    if claimer:
        overwrites[claimer] = discord.PermissionOverwrite(
            view_channel=True, send_messages=True, read_message_history=True
        )

    try:
        await channel.edit(overwrites=overwrites)
    except Exception as e:
        print(f"Private ticket permission error: {e}")


def check_staff(interaction):
    ticket = get_ticket_from_channel(interaction.channel.id)
    if not ticket:
        return False
    settings = database["tickets"].get(ticket["type"])
    if not settings:
        return False

    # في الوضع الخاص: الإدارة العادية لا تستطيع دخول التذكرة إلا إذا كانت هي المستلمة.
    # صلاحية Administrator للإغلاق تُعالج بشكل منفصل داخل زر الإغلاق.
    if settings.get("private_mode") and ticket.get("claimed"):
        return interaction.user.id == ticket.get("claimed")

    staff_roles = settings.get("staff_roles", [])
    if is_manager(interaction.user):
        return True
    user_roles = [role.id for role in interaction.user.roles]
    return any(role_id in user_roles for role_id in staff_roles)


print("✅ الأجزاء الأساسية وقواعد البيانات جاهزة")


# ==================================
# إنشاء أنواع التذاكر والأوامر الإدارية (مع حماية المشرفين)
# ==================================

@bot.tree.command(
    name="reload-data",
    description="إعادة تحميل قاعدة البيانات"
)
async def reload_data(interaction: discord.Interaction):

    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "❌ للمشرفين فقط",
            ephemeral=True
        )
        return

    global database
    database = load_database()

    await interaction.response.send_message(
        "✅ تم تحديث البيانات",
        ephemeral=True
    )



@bot.tree.command(
    name="backup-tickets",
    description="عمل نسخة احتياطية"
)
async def backup_tickets(interaction: discord.Interaction):

    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "❌ للمشرفين فقط",
            ephemeral=True
        )
        return

    filename = f"backup-{datetime.now().strftime('%Y-%m-%d')}.json"

    with open(filename,"w",encoding="utf-8") as f:
        json.dump(
            database,
            f,
            indent=4,
            ensure_ascii=False
        )

    await interaction.response.send_message(
        "✅ تم إنشاء نسخة احتياطية",
        file=discord.File(filename),
        ephemeral=True
    )



@bot.tree.command(
    name="restore-backup",
    description="استرجاع نسخة احتياطية"
)
async def restore_backup(interaction:discord.Interaction):

    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "❌ للمشرفين فقط",
            ephemeral=True
        )
        return

    global database

    if not os.path.exists(BACKUP_FILE):
        await interaction.response.send_message(
            "❌ لا يوجد نسخة احتياطية",
            ephemeral=True
        )
        return

    with open(BACKUP_FILE, "r", encoding="utf-8") as file:
        database = json.load(file)

    await interaction.response.send_message(
        embed=make_embed(
            "✅ تم الاسترجاع",
            "تم استرجاع قاعدة بيانات التذاكر بنجاح.",
            discord.Color.green()
        ),
        ephemeral=True
    )



@bot.tree.command(
    name="add-manager",
    description="إضافة مدير لنظام التذاكر"
)
@app_commands.describe(
    member="العضو"
)
async def add_manager(
    interaction: discord.Interaction,
    member: discord.Member
):

    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "❌ للمشرفين فقط",
            ephemeral=True
        )
        return

    database["stats"]["permissions"]["managers"].append(
        member.id
    )

    save_database()

    database["stats"]["logs"].append({
        "user": str(interaction.user.id),
        "action": f"أضاف المدير {member.id}",
        "time": str(datetime.now())
    })

    await interaction.response.send_message(
        embed=make_embed(
            "👑 تم إضافة مدير",
            f"{member.mention} أصبح مدير نظام التذاكر.",
            discord.Color.green()
        )
    )



@bot.tree.command(
    name="ticket-auto-setup",
    description="إعداد نظام التذاكر تلقائياً"
)
async def ticket_auto_setup(
    interaction: discord.Interaction
):

    if not is_manager(interaction.user):
        await interaction.response.send_message(
            "❌ لا تملك صلاحية",
            ephemeral=True
        )
        return

    guild = interaction.guild

    open_category = await guild.create_category(
        "🎫 التذاكر المفتوحة"
    )

    close_category = await guild.create_category(
        "🔒 التذاكر المغلقة"
    )

    logs = await guild.create_text_channel(
        "📜-ticket-logs"
    )

    database["panel"]["channel"] = logs.id

    database["auto_setup"] = {
        "open_category": open_category.id,
        "close_category": close_category.id,
        "logs": logs.id
    }

    save_database()

    await interaction.response.send_message(
        embed=make_embed(
            "✅ تم الإعداد",
            "تم إنشاء نظام التذاكر بالكامل.",
            discord.Color.green()
        ),
        ephemeral=True
    )



@bot.tree.command(
    name="ticket-system-info",
    description="معلومات النظام"
)
async def ticket_system_info(
    interaction: discord.Interaction
):

    embed = make_embed(
        "🤖 حالة النظام",
        ""
    )

    embed.add_field(
        name="🎫 أنواع التذاكر",
        value=str(len(database["tickets"]))
    )

    embed.add_field(
        name="📂 التذاكر المفتوحة",
        value=str(len(database["open_tickets"]))
    )

    embed.add_field(
        name="👑 المدراء",
        value=str(len(database["stats"]["permissions"]["managers"]))
    )

    await interaction.response.send_message(
        embed=embed
    )



@bot.tree.command(
    name="dashboard",
    description="لوحة إحصائيات التذاكر"
)
async def dashboard(interaction: discord.Interaction):

    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "❌ للمشرفين فقط",
            ephemeral=True
        )
        return

    stats = database["stats"]

    embed = discord.Embed(
        title="📊 لوحة التحكم",
        color=discord.Color.gold()
    )

    embed.add_field(
        name="🎫 إجمالي الفتح",
        value=str(stats["total_opened"])
    )

    embed.add_field(
        name="🔒 إجمالي الإغلاق",
        value=str(stats["total_closed"])
    )

    embed.add_field(
        name="👑 عدد الإداريين",
        value=str(len(stats["staff"]))
    )

    embed.set_footer(
        text="Ticket System Professional"
    )

    await interaction.response.send_message(
        embed=embed
    )



@bot.tree.command(
    name="ticket-create",
    description="إنشاء نوع تذكرة جديد"
)
@app_commands.describe(
    name="اسم التذكرة",
    description="وصف التذكرة في البانل",
    name_format="صيغة اسم الروم، استخدم {name} لاسم النوع و {count} للعداد"
)
async def ticket_create(
    interaction: discord.Interaction,
    name: str,
    description: str,
    name_format: str = "{name}-{count}"
):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ هذا الأمر مخصص للمشرفين فقط", ephemeral=True)
        return

    ticket_id = create_ticket_id()

    database["tickets"][ticket_id] = default_ticket()
    database["tickets"][ticket_id]["name"] = name
    database["tickets"][ticket_id]["description"] = description
    database["tickets"][ticket_id]["panel_description"] = description
    database["tickets"][ticket_id]["name_format"] = name_format.strip() or "{emoji}・{count}"

    save_database()

    await interaction.response.send_message(
        f"✅ تم إنشاء نوع تذكرة جديد\n🎫 الاسم: {name}\n🆔 المعرف: `{ticket_id}`",
        ephemeral=True
    )



@bot.tree.command(
    name="ticket-delete",
    description="حذف نوع تذكرة"
)
@app_commands.describe(
    ticket_id="معرف التذكرة"
)
async def ticket_delete(
    interaction: discord.Interaction,
    ticket_id: str
):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ هذا الأمر مخصص للمشرفين فقط", ephemeral=True)
        return

    if ticket_id not in database["tickets"]:
        await interaction.response.send_message("❌ هذا النوع غير موجود", ephemeral=True)
        return

    del database["tickets"][ticket_id]

    # إزالة التذكرة من جميع البانلات التي كانت تحتوي عليها
    for panel_id, panel in database.get("panels", {}).items():
        if ticket_id in panel.get("tickets", []):
            panel["tickets"].remove(ticket_id)
            try:
                await refresh_panel_message(interaction.guild, panel_id)
            except:
                pass

    save_database()

    await interaction.response.send_message("✅ تم حذف نوع التذكرة", ephemeral=True)



@bot.tree.command(
    name="tickets-list",
    description="عرض أنواع التذاكر"
)
async def tickets_list(
    interaction: discord.Interaction
):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ هذا الأمر مخصص للمشرفين فقط", ephemeral=True)
        return

    if not database["tickets"]:
        await interaction.response.send_message("❌ لا يوجد أنواع تذاكر حالياً", ephemeral=True)
        return

    embed = discord.Embed(
        title="🎫 أنواع التذاكر",
        color=discord.Color.blue()
    )

    for ticket_id, data in database["tickets"].items():
        embed.add_field(
            name=f"{data['emoji']} {data['name']}",
            value=f"🆔 `{ticket_id}`\n📜 {data.get('description', data.get('panel_description', ''))}",
            inline=False
        )

    await interaction.response.send_message(embed=embed, ephemeral=True)



@bot.tree.command(
    name="ticket-copy",
    description="نسخ إعدادات تذكرة موجودة بالكامل"
)
@app_commands.describe(
    ticket_id="معرف التذكرة المراد نسخها"
)
async def ticket_copy(
    interaction: discord.Interaction,
    ticket_id: str
):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ هذا الأمر مخصص للمشرفين فقط", ephemeral=True)
        return

    original_ticket = get_ticket(ticket_id)
    if not original_ticket:
        await interaction.response.send_message("❌ التذكرة المراد نسخها غير موجودة", ephemeral=True)
        return

    new_id = create_ticket_id()
    copied_data = json.loads(json.dumps(original_ticket))
    copied_data["name"] = f"{copied_data['name']} (نسخة)"
    copied_data["counter"] = 0
    copied_data["opened"] = 0
    copied_data["closed"] = 0
    copied_data["ratings"] = []

    database["tickets"][new_id] = copied_data
    save_database()

    await interaction.response.send_message(f"✅ تم نسخ التذكرة بنجاح!\n🆔 المعرف الجديد: `{new_id}`", ephemeral=True)



@bot.tree.command(
    name="ticket-rename-type",
    description="تغيير اسم نوع التذكرة"
)
@app_commands.describe(
    ticket_id="معرف التذكرة",
    new_name="الاسم الجديد"
)
async def ticket_rename_type(
    interaction: discord.Interaction,
    ticket_id: str,
    new_name: str
):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ هذا الأمر مخصص للمشرفين فقط", ephemeral=True)
        return

    ticket = get_ticket(ticket_id)

    if not ticket:
        await interaction.response.send_message("❌ التذكرة غير موجودة", ephemeral=True)
        return

    ticket["name"] = new_name
    save_database()

    await interaction.response.send_message("✅ تم تغيير الاسم", ephemeral=True)


# ==================================
# إعدادات البانل والمودال (البانلات المتعددة)
# ==================================

@bot.tree.command(
    name="add-ticket-panel",
    description="إنشاء بانل تذاكر جديد"
)
@app_commands.describe(
    title="عنوان البانل",
    description="وصف البانل",
    image="رابط صورة البانل - اختياري"
)
async def add_ticket_panel(
    interaction: discord.Interaction,
    title: str,
    description: str,
    image: str = None
):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "❌ هذا الأمر للمشرفين فقط",
            ephemeral=True
        )
        return

    await interaction.response.defer(ephemeral=True)

    panel_number = 1
    while f"panel_{panel_number}" in database["panels"]:
        panel_number += 1

    panel_id = f"panel_{panel_number}"

    database["panels"][panel_id] = {
        "title": title,
        "description": description,
        "image": image,
        "channel": interaction.channel.id,
        "message_id": None,
        "created_by": interaction.user.id,
        "created_at": str(datetime.now()),
        "tickets": []
    }

    save_database()

    embed = discord.Embed(
        title=title,
        description=description,
        color=discord.Color.blue()
    )

    if image:
        embed.set_image(url=image)

    message = await interaction.channel.send(
        embed=embed,
        view=TicketPanel(panel_id)
    )

    database["panels"][panel_id]["message_id"] = message.id
    save_database()
    await send_ticket_log(interaction.guild, "admin", "🖥️ إنشاء بانل", fields=[
        ("🖥️ البانل", panel_id, True), ("👤 بواسطة", interaction.user.mention, True),
        ("📌 الروم", interaction.channel.mention, True), ("🏷️ العنوان", title, False)
    ], color=discord.Color.green())

    await interaction.followup.send(
        embed=make_embed(
            "✅ تم إنشاء البانل",
            f"تم إنشاء البانل بنجاح.\n\n"
            f"🆔 **المعرف:** `{panel_id}`\n"
            f"📌 **البانل:** {message.jump_url}\n\n"
            f"🎫 حالياً لا توجد تذاكر داخل هذا البانل.\n"
            f"استخدم `/panel-add-ticket` لإضافة تذكرة إليه.",
            discord.Color.green()
        ),
        ephemeral=True
    )



@bot.tree.command(
    name="panels-list",
    description="عرض جميع بانلات التذاكر"
)
async def panels_list(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "❌ هذا الأمر للمشرفين فقط",
            ephemeral=True
        )
        return

    if not database.get("panels"):
        await interaction.response.send_message(
            "❌ لا يوجد أي بانلات حالياً",
            ephemeral=True
        )
        return

    embed = discord.Embed(
        title="🖥️ جميع بانلات التذاكر",
        color=discord.Color.blue()
    )

    for panel_id, panel in database["panels"].items():
        channel = interaction.guild.get_channel(panel.get("channel"))
        channel_text = channel.mention if channel else "❌ الروم غير موجود"

        embed.add_field(
            name=f"🆔 {panel_id}",
            value=(
                f"📌 **العنوان:** {panel.get('title', 'بدون عنوان')}\n"
                f"📜 **الوصف:** {panel.get('description', 'بدون وصف')}\n"
                f"📍 **الروم:** {channel_text}\n"
                f"🔗 [فتح البانل](https://discord.com/channels/"
                f"{interaction.guild.id}/"
                f"{panel.get('channel')}/"
                f"{panel.get('message_id')})"
            ),
            inline=False
        )

    await interaction.response.send_message(
        embed=embed,
        ephemeral=True
    )



@bot.tree.command(
    name="delete-ticket-panel",
    description="حذف بانل تذاكر معين"
)
@app_commands.describe(
    panel_id="معرف البانل مثل panel_1"
)
async def delete_ticket_panel(
    interaction: discord.Interaction,
    panel_id: str
):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "❌ هذا الأمر للمشرفين فقط",
            ephemeral=True
        )
        return

    panel = database["panels"].get(panel_id)

    if not panel:
        await interaction.response.send_message(
            "❌ لم يتم العثور على هذا البانل",
            ephemeral=True
        )
        return

    channel = interaction.guild.get_channel(panel.get("channel"))

    if channel:
        try:
            message = await channel.fetch_message(panel.get("message_id"))
            await message.delete()
        except:
            pass

    del database["panels"][panel_id]
    save_database()
    await send_ticket_log(interaction.guild, "admin", "🗑️ حذف بانل", fields=[
        ("🖥️ البانل", panel_id, True), ("👤 بواسطة", interaction.user.mention, True)
    ], color=discord.Color.red())

    await interaction.response.send_message(
        f"✅ تم حذف البانل `{panel_id}` بنجاح",
        ephemeral=True
    )


# ==================================
# ربط التذاكر بالبانلات
# ==================================

async def refresh_panel_message(guild, panel_id):
    panel = database["panels"].get(panel_id)
    if not panel:
        return False

    channel = guild.get_channel(panel.get("channel"))
    if not channel:
        return False

    try:
        message = await channel.fetch_message(panel.get("message_id"))
        await message.edit(view=TicketPanel(panel_id))
        return True
    except Exception as e:
        print(f"Panel refresh error: {e}")
        return False


@bot.tree.command(
    name="panel-add-ticket",
    description="إضافة نوع تذكرة إلى بانل معين"
)
@app_commands.describe(
    panel_id="معرف البانل مثل panel_1",
    ticket_id="معرف نوع التذكرة مثل ticket_1"
)
async def panel_add_ticket(
    interaction: discord.Interaction,
    panel_id: str,
    ticket_id: str
):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "❌ هذا الأمر للمشرفين فقط.",
            ephemeral=True
        )
        return

    panel = database["panels"].get(panel_id)
    if not panel:
        await interaction.response.send_message(
            f"❌ البانل `{panel_id}` غير موجود.",
            ephemeral=True
        )
        return

    ticket = database["tickets"].get(ticket_id)
    if not ticket:
        await interaction.response.send_message(
            f"❌ نوع التذكرة `{ticket_id}` غير موجود.",
            ephemeral=True
        )
        return

    if ticket_id in panel.get("tickets", []):
        await interaction.response.send_message(
            f"⚠️ التذكرة **{ticket['name']}** موجودة بالفعل داخل `{panel_id}`.",
            ephemeral=True
        )
        return

    panel.setdefault("tickets", [])
    panel["tickets"].append(ticket_id)
    save_database()
    await send_ticket_log(interaction.guild, "admin", "➕ إضافة نوع تذكرة إلى بانل", fields=[
        ("🖥️ البانل", panel_id, True), ("🎫 التذكرة", ticket["name"], True),
        ("👤 بواسطة", interaction.user.mention, True)
    ], color=discord.Color.green())

    updated = await refresh_panel_message(interaction.guild, panel_id)

    await interaction.response.send_message(
        embed=make_embed(
            "✅ تمت إضافة التذكرة",
            f"🎫 **التذكرة:** {ticket['name']}\n"
            f"🆔 **المعرف:** `{ticket_id}`\n\n"
            f"🖥️ **البانل:** `{panel_id}`\n\n"
            f"{'🔄 تم تحديث البانل مباشرة.' if updated else '⚠️ تمت الإضافة لكن تعذر تحديث رسالة البانل.'}",
            discord.Color.green()
        ),
        ephemeral=True
    )


@bot.tree.command(
    name="panel-remove-ticket",
    description="إزالة نوع تذكرة من بانل معين"
)
@app_commands.describe(
    panel_id="معرف البانل",
    ticket_id="معرف نوع التذكرة"
)
async def panel_remove_ticket(
    interaction: discord.Interaction,
    panel_id: str,
    ticket_id: str
):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "❌ هذا الأمر للمشرفين فقط.",
            ephemeral=True
        )
        return

    panel = database["panels"].get(panel_id)
    if not panel:
        await interaction.response.send_message(
            f"❌ البانل `{panel_id}` غير موجود.",
            ephemeral=True
        )
        return

    if ticket_id not in panel.get("tickets", []):
        await interaction.response.send_message(
            "❌ هذه التذكرة غير موجودة داخل هذا البانل.",
            ephemeral=True
        )
        return

    panel["tickets"].remove(ticket_id)
    save_database()
    await send_ticket_log(interaction.guild, "admin", "➖ إزالة نوع تذكرة من بانل", fields=[
        ("🖥️ البانل", panel_id, True), ("🎫 التذكرة", ticket_id, True),
        ("👤 بواسطة", interaction.user.mention, True)
    ], color=discord.Color.red())

    updated = await refresh_panel_message(interaction.guild, panel_id)
    ticket = database["tickets"].get(ticket_id)
    ticket_name = ticket["name"] if ticket else ticket_id

    await interaction.response.send_message(
        embed=make_embed(
            "✅ تمت إزالة التذكرة",
            f"🎫 **التذكرة:** {ticket_name}\n"
            f"🆔 **المعرف:** `{ticket_id}`\n"
            f"🖥️ **البانل:** `{panel_id}`\n\n"
            f"{'🔄 تم تحديث البانل.' if updated else '⚠️ تمت الإزالة لكن تعذر تحديث البانل.'}",
            discord.Color.green()
        ),
        ephemeral=True
    )


@bot.tree.command(
    name="panel-tickets",
    description="عرض التذاكر الموجودة داخل بانل معين"
)
@app_commands.describe(
    panel_id="معرف البانل مثل panel_1"
)
async def panel_tickets(
    interaction: discord.Interaction,
    panel_id: str
):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "❌ هذا الأمر للمشرفين فقط.",
            ephemeral=True
        )
        return

    panel = database["panels"].get(panel_id)
    if not panel:
        await interaction.response.send_message(
            f"❌ البانل `{panel_id}` غير موجود.",
            ephemeral=True
        )
        return

    ticket_ids = panel.get("tickets", [])
    if not ticket_ids:
        await interaction.response.send_message(
            f"📭 البانل `{panel_id}` لا يحتوي على أي تذاكر.",
            ephemeral=True
        )
        return

    embed = discord.Embed(
        title=f"🎫 تذاكر {panel_id}",
        color=discord.Color.blue()
    )

    text = ""
    for ticket_id in ticket_ids:
        ticket = database["tickets"].get(ticket_id)
        if ticket:
            text += (
                f"{ticket.get('emoji', '🎫')} "
                f"**{ticket['name']}**\n"
                f"🆔 `{ticket_id}`\n\n"
            )

    if not text:
        text = "❌ لا توجد تذاكر صالحة."

    embed.description = text
    await interaction.response.send_message(embed=embed, ephemeral=True)


# ==================================
# القوائم والبانل الموحد
# ==================================

class TicketSelect(discord.ui.Select):

    def __init__(self, panel_id):
        self.panel_id = panel_id
        panel = database["panels"].get(panel_id)
        options = []

        if panel:
            panel_tickets = panel.get("tickets", [])
            for ticket_id in panel_tickets:
                data = database["tickets"].get(ticket_id)
                if not data:
                    continue

                options.append(
                    discord.SelectOption(
                        label=data["name"][:100],
                        value=ticket_id,
                        description=data.get(
                            "panel_description",
                            data.get("description", "فتح تذكرة")
                        )[:100],
                        emoji=data.get("emoji", "🎫")
                    )
                )

        if not options:
            options.append(
                discord.SelectOption(
                    label="لا توجد تذاكر",
                    value="none",
                    description="لا توجد تذاكر مضافة لهذا البانل",
                    emoji="❌"
                )
            )

        options.append(
            discord.SelectOption(
                label="تحديث القائمة",
                value="refresh_menu",
                description="إعادة تحميل أنواع التذاكر",
                emoji="🔄"
            )
        )

        super().__init__(
            placeholder="🎫 اختر نوع التذكرة",
            options=options,
            custom_id=f"ticket_select_{panel_id}"
        )

    async def callback(self, interaction: discord.Interaction):
        ticket_type = self.values[0]

        if ticket_type == "refresh_menu":
            await interaction.response.edit_message(
                view=TicketPanel(self.panel_id)
            )
            return

        if ticket_type == "none":
            await interaction.response.send_message(
                "❌ لا توجد تذاكر مضافة لهذا البانل حالياً.",
                ephemeral=True
            )
            return

        user_id = interaction.user.id
        ticket_settings = database["tickets"].get(ticket_type)

        if not ticket_settings:
            await interaction.response.send_message(
                "❌ نوع التذكرة لم يعد موجوداً.",
                ephemeral=True
            )
            return

        for t in database["open_tickets"].values():
            if t.get("owner") == user_id:
                await interaction.response.send_message(
                    "❌ لديك تذكرة مفتوحة بالفعل.",
                    ephemeral=True
                )
                return

        if ticket_settings.get("ask_reason"):
            await interaction.response.send_modal(
                TicketFormModal(ticket_type, self.panel_id)
            )
            return

        await create_ticket(
            interaction,
            ticket_type,
            None,
            self.panel_id
        )



# ==================================
# View البانل
# ==================================

class TicketPanel(discord.ui.View):

    def __init__(self, panel_id):
        super().__init__(timeout=None)
        self.panel_id = panel_id
        self.add_item(
            TicketSelect(panel_id)
        )


# ==================================
# نظام نماذج التذاكر (Ticket Forms)
# ==================================

class TicketFormModal(discord.ui.Modal):

    def __init__(self, ticket_type, panel_id=None):
        super().__init__(title="معلومات فتح التذكرة")
        self.ticket_type = ticket_type
        self.panel_id = panel_id

        self.question1 = discord.ui.TextInput(
            label="ماذا تريد؟",
            placeholder="اكتب طلبك بالتفصيل",
            required=True,
            max_length=300
        )

        self.question2 = discord.ui.TextInput(
            label="التفاصيل الإضافية",
            placeholder="اكتب أي معلومات تساعد الإدارة",
            required=False,
            max_length=300
        )

        self.add_item(self.question1)
        self.add_item(self.question2)


    async def on_submit(self, interaction: discord.Interaction):

        reason = (
            f"📜 الطلب:\n{self.question1.value}\n\n"
            f"📌 التفاصيل:\n{self.question2.value}"
        )

        await create_ticket(
            interaction,
            self.ticket_type,
            reason,
            self.panel_id
        )



@bot.tree.command(
    name="ticket-form",
    description="تفعيل نموذج أسئلة لنوع تذكرة"
)
@app_commands.describe(
    ticket_id="معرف نوع التذكرة"
)
async def ticket_form(
    interaction: discord.Interaction,
    ticket_id: str
):

    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "❌ هذا الأمر للمشرفين فقط",
            ephemeral=True
        )
        return


    if ticket_id not in database["tickets"]:
        await interaction.response.send_message(
            "❌ نوع التذكرة غير موجود",
            ephemeral=True
        )
        return


    database["tickets"][ticket_id]["ask_reason"] = True

    save_database()


    await interaction.response.send_message(
        embed=make_embed(
            "✅ تم تفعيل النموذج",
            f"تم تفعيل أسئلة الفتح لنوع التذكرة:\n🎫 {database['tickets'][ticket_id]['name']}",
            discord.Color.green()
        ),
        ephemeral=True
    )


# ==================================
# نظام فتح التذاكر والترانسكريبت
# ==================================

async def create_transcript(channel):
    messages = []
    async for message in channel.history(limit=None, oldest_first=True):
        timestamp = message.created_at.strftime("%Y-%m-%d %H:%M:%S")
        author = f"{message.author.name}#{message.author.discriminator}" if message.author.discriminator != "0" else message.author.name
        avatar = message.author.display_avatar.url
        content = message.content or ""
        
        embeds_html = ""
        for embed in message.embeds:
            embeds_html += f"""
            <div style="background-color: #2f3136; border-left: 4px solid #7289da; padding: 10px; margin-top: 5px; border-radius: 4px;">
                <b style="color: #ffffff;">{embed.title or ''}</b>
                <p style="color: #dcddde; white-space: pre-wrap;">{embed.description or ''}</p>
            </div>
            """

        attachments_html = ""
        for att in message.attachments:
            attachments_html += f'<br><a href="{att.url}" target="_blank" style="color: #00b0f4;">📎 {att.filename}</a>'

        messages.append(f"""
        <div style="display: flex; margin-bottom: 15px; font-family: Arial, sans-serif;">
            <img src="{avatar}" style="width: 40px; height: 40px; border-radius: 50%; margin-right: 15px;">
            <div>
                <div><b>{author}</b> <span style="font-size: 11px; color: #72767d; margin-left: 5px;">{timestamp}</span></div>
                <div style="color: #dcddde; white-space: pre-wrap; margin-top: 2px;">{content}</div>
                {embeds_html}
                {attachments_html}
            </div>
        </div>
        """)

    html_content = f"""
    <html>
    <head>
        <meta charset="utf-8">
        <title>Transcript - {channel.name}</title>
    </head>
    <body style="background-color: #36393f; color: #dcddde; padding: 20px;">
        <h2 style="color: #ffffff; border-bottom: 1px solid #4f545c; padding-bottom: 10px;">📜 سجل التذكرة: {channel.name}</h2>
        {"".join(messages)}
    </body>
    </html>
    """

    filename = f"transcript-{channel.id}.html"
    with open(filename, "w", encoding="utf-8") as file:
        file.write(html_content)

    return filename



async def send_open_log(interaction, channel, ticket):
    settings = database["tickets"].get(ticket["type"])
    if not settings:
        return
    def fmt(value):
        try: return f"<t:{int(datetime.fromisoformat(value).timestamp())}:F>"
        except Exception: return value or "غير معروف"
    await send_ticket_log(interaction.guild, "open", "🎫 فتح تذكرة", fields=[
        ("👤 صاحب التذكرة", f"<@{ticket['owner']}>", True),
        ("🎟️ النوع", settings.get("name", "غير معروف"), True),
        ("📌 الروم", channel.mention, True),
        ("🖥️ البانل", ticket.get("panel_id", "غير محدد"), True),
        ("📅 وقت الفتح", fmt(ticket.get("created")), True),
        ("👑 المستلم", f"<@{ticket['claimed']}>" if ticket.get("claimed") else "لم يتم الاستلام بعد", True),
        ("📜 سبب الفتح", ticket.get("reason") or "بدون سبب", False),
    ], color=discord.Color.green())


async def send_claim_log(interaction, channel, ticket):
    settings = database["tickets"].get(ticket.get("type"))
    def fmt(value):
        try: return f"<t:{int(datetime.fromisoformat(value).timestamp())}:F>"
        except Exception: return value or "غير معروف"
    await send_ticket_log(interaction.guild, "claim", "👑 استلام تذكرة", fields=[
        ("👤 صاحب التذكرة", f"<@{ticket.get('owner')}>", True),
        ("🎟️ النوع", settings.get("name", "غير معروف") if settings else "غير معروف", True),
        ("👑 المستلم", interaction.user.mention, True),
        ("📌 الروم", channel.mention, True),
        ("📅 وقت الاستلام", fmt(ticket.get("claimed_at")), True),
        ("⏱️ وقت الفتح", fmt(ticket.get("created")), True),
    ], color=discord.Color.gold())


async def send_close_log(interaction, channel, transcript=None, close_reason=None):
    ticket = database["open_tickets"].get(str(channel.id))
    if not ticket:
        return
    settings = database["tickets"].get(ticket["type"])
    def fmt(value):
        try: return f"<t:{int(datetime.fromisoformat(value).timestamp())}:F>"
        except Exception: return value or "غير معروف"
    notes = "\n".join(f"• <@{n.get('staff')}> — {n.get('note','')}" for n in ticket.get("notes", [])) or "لا توجد ملاحظات"
    await send_ticket_log(interaction.guild, "close", "🔒 إغلاق تذكرة", fields=[
        ("👤 صاحب التذكرة", f"<@{ticket.get('owner')}>", True),
        ("🎟️ النوع", settings.get("name", "غير معروف") if settings else "غير معروف", True),
        ("📌 الروم", f"#{channel.name}", True),
        ("👑 المستلم", f"<@{ticket['claimed']}>" if ticket.get("claimed") else "لا يوجد", True),
        ("🔒 أغلقها", f"<@{ticket.get('closed_by')}>" if ticket.get("closed_by") else interaction.user.mention, True),
        ("📅 وقت الفتح", fmt(ticket.get("created")), True),
        ("👑 وقت الاستلام", fmt(ticket.get("claimed_at")), True),
        ("🔒 وقت الإغلاق", fmt(ticket.get("closed_at")), True),
        ("📝 سبب الإغلاق", close_reason or "لم يتم تحديد سبب", False),
        ("📑 الملاحظات", notes, False),
    ], color=discord.Color.red(), file_path=transcript)


def normalize_ticket_emoji(value):
    """تحويل الإيموجي المخصص إلى اسم آمن عند استخدامه داخل اسم الروم."""
    value = str(value or "").strip()
    match = re.fullmatch(r"<a?:([^:>]+):\d+>", value)
    if match:
        return match.group(1)
    if re.fullmatch(r"a?emoji_\d+", value, flags=re.IGNORECASE):
        return ""
    return value


def sanitize_ticket_channel_name(name, fallback="ticket"):
    """تنظيف اسم الروم ومنع ظهور aemoji_ID أو صيغ Discord غير الصالحة."""
    name = str(name or "").strip()
    name = re.sub(r"<a?:([^:>]+):\d+>", lambda m: m.group(1), name)
    name = re.sub(r"\s+", "-", name)
    name = re.sub(r"-{2,}", "-", name)
    name = name.replace("@", "").replace("#", "")
    name = name.strip("- ")
    return (name or fallback)[:100]


async def create_ticket(interaction, ticket_type, reason=None, panel_id=None):
    settings = database["tickets"].get(ticket_type)
    if not settings:
        if not interaction.response.is_done():
            await interaction.response.send_message("❌ نوع التذكرة غير موجود", ephemeral=True)
        return

    category_id = settings.get("open_category")
    category = interaction.guild.get_channel(category_id) if category_id else None

    # عداد مستقل لكل نوع تذكرة، ويتم حفظه في قاعدة البيانات
    settings["counter"] = int(settings.get("counter", 0)) + 1
    number = settings["counter"]

    # استبدال المتغيرات داخل صيغة اسم الروم
    name_format = settings.get("name_format", "{emoji}・{count}")
    replacements = {
        "{count}": str(number),
        "{emoji}": normalize_ticket_emoji(settings.get("emoji", "🎫")) or "ticket",
        "{name}": str(settings.get("name", "ticket")),
        "{user}": str(interaction.user.name),
        "{userid}": str(interaction.user.id),
        "{id}": str(number),
    }
    channel_name = name_format
    for placeholder, value in replacements.items():
        channel_name = channel_name.replace(placeholder, value)

    # Discord يفرض حداً أقصى لطول اسم الروم
    channel_name = sanitize_ticket_channel_name(channel_name, fallback=f"ticket-{number}")
    if not channel_name:
        channel_name = f"{settings.get('emoji', '🎫')}・{number}"

    overwrites = {
        interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
        interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
    }

    for role_id in settings.get("staff_roles", []):
        role = interaction.guild.get_role(role_id)
        if role:
            overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)

    channel = await interaction.guild.create_text_channel(
        name=channel_name,
        category=category,
        overwrites=overwrites
    )

    database["open_tickets"][str(channel.id)] = {
        "owner": interaction.user.id,
        "user": str(interaction.user.id),
        "type": ticket_type,
        "created": str(datetime.now()),
        "claimed": None,
        "reason": reason,
        "panel_id": panel_id,
        "closed": False,
        "closed_by": None,
        "closed_at": None,
        "claimed_at": None,
        "rating": None,
        "rating_reason": None,
        "priority": "normal",
        "last_activity": str(datetime.now()),
        "added_members": []
    }

    database["stats"]["total_opened"] += 1
    settings["opened"] += 1
    save_database()

    colors = {
        "blue": discord.Color.blue(),
        "red": discord.Color.red(),
        "green": discord.Color.green(),
        "gold": discord.Color.gold()
    }
    embed_color = colors.get(settings.get("color"), discord.Color.blue())

    welcome_text = settings.get("welcome_message", "أهلاً {user} 👋\nسيتم الرد عليك قريباً.")
    staff_role_id = settings.get("staff_mention_role")
    staff_role = interaction.guild.get_role(int(staff_role_id)) if staff_role_id else None
    staff_mention = staff_role.mention if staff_role else ""
    welcome_text = welcome_text.replace("{user}", interaction.user.mention).replace("{staff}", staff_mention)
    embed = discord.Embed(
        title=f"{settings['emoji']} {settings['name']}",
        description=welcome_text,
        color=embed_color
    )

    embed.add_field(name="👤 صاحب التذكرة", value=interaction.user.mention, inline=False)
    embed.add_field(name="🔢 رقم التذكرة", value=f"#{number}", inline=False)

    if reason:
        embed.add_field(name="📜 السبب", value=reason, inline=False)

    if settings.get("ticket_image") or settings.get("image"):
        embed.set_image(url=settings.get("ticket_image") or settings.get("image"))

    embed.set_footer(text="نظام التذاكر الاحترافي")

    await channel.send(
        content=staff_mention or None,
        embed=embed,
        view=TicketButtons(),
        allowed_mentions=discord.AllowedMentions(roles=True, users=True, everyone=False, replied_user=False)
    )
    await send_open_log(interaction, channel, database["open_tickets"][str(channel.id)])

    if not interaction.response.is_done():
        await interaction.response.send_message(f"✅ تم فتح التذكرة {channel.mention}", ephemeral=True)


# ==================================
# أزرار وأدوات داخل التذكرة
# ==================================

class TicketButtons(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Claim",
        emoji="👑",
        style=discord.ButtonStyle.blurple,
        custom_id="claim_button_secure"
    )
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not check_staff(interaction):
            await interaction.response.send_message("❌ ليس لديك صلاحية لاستلام التذكرة", ephemeral=True)
            return

        ticket = database["open_tickets"].get(str(interaction.channel.id))
        if not ticket:
            await interaction.response.send_message("❌ التذكرة غير موجودة", ephemeral=True)
            return

        if ticket.get("claimed"):
            await interaction.response.send_message("⚠️ هذه التذكرة تم استلامها مسبقاً", ephemeral=True)
            return

        ticket["claimed"] = interaction.user.id
        ticket["claimed_at"] = str(datetime.now())
        staff = str(interaction.user.id)
        if staff not in database["stats"]["staff"]:
            database["stats"]["staff"][staff] = {"claimed": 0, "closed": 0}
        database["stats"]["staff"][staff]["claimed"] += 1
        database["stats"]["logs"].append({
            "user": str(interaction.user.id),
            "action": "استلم التذكرة",
            "time": str(datetime.now())
        })
        save_database()
        if database["tickets"].get(ticket.get("type"), {}).get("private_mode"):
            await apply_private_ticket_permissions(interaction.channel, ticket)
        await send_claim_log(interaction, interaction.channel, ticket)
        button.disabled = True
        await interaction.message.edit(view=self)
        await interaction.channel.send(embed=make_embed(
            "👑 تم استلام التذكرة",
            f"الإداري المسؤول الآن:\n{interaction.user.mention}",
            discord.Color.gold()
        ))
        await interaction.response.send_message("👑 تم استلام التذكرة بنجاح", ephemeral=True)

    @discord.ui.button(
        label="Ticket Settings",
        emoji="⚙️",
        style=discord.ButtonStyle.gray,
        custom_id="ticket_settings_button_secure"
    )
    async def settings(self, interaction: discord.Interaction, button: discord.ui.Button):
        ticket = database["open_tickets"].get(str(interaction.channel.id))
        if not ticket:
            await interaction.response.send_message("❌ هذا الروم ليس تذكرة", ephemeral=True)
            return
        if not check_staff(interaction):
            await interaction.response.send_message("❌ لا تملك صلاحية إدارة هذه التذكرة", ephemeral=True)
            return
        await interaction.response.send_message(
            embed=build_ticket_settings_embed(ticket),
            view=TicketManagementView(str(interaction.channel.id)),
            ephemeral=True
        )


# ==================================
# نظام التقييم والإغلاق
# ==================================

class AdminCloseReasonModal(discord.ui.Modal):
    def __init__(self, ticket_channel_id):
        super().__init__(title="سبب إغلاق التذكرة")
        self.ticket_channel_id = ticket_channel_id
        self.reason = discord.ui.TextInput(
            label="سبب الإغلاق",
            placeholder="اكتب سبب إغلاق التذكرة...",
            required=True, min_length=2, max_length=1000,
            style=discord.TextStyle.paragraph
        )
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        if not check_staff(interaction):
            await interaction.response.send_message("❌ لا تملك صلاحية إغلاق التذكرة.", ephemeral=True)
            return

        channel = interaction.channel
        channel_id = str(channel.id)
        ticket = database["open_tickets"].get(channel_id)
        if not ticket:
            await interaction.response.send_message("❌ التذكرة غير موجودة.", ephemeral=True)
            return
        if ticket.get("closed"):
            await interaction.response.send_message("⚠️ التذكرة مغلقة بالفعل.", ephemeral=True)
            return

        reason = self.reason.value.strip()
        ticket["closed"] = True
        ticket["closed_by"] = interaction.user.id
        ticket["closed_at"] = str(datetime.now())
        ticket["close_reason"] = reason

        staff = str(interaction.user.id)
        if staff not in database["stats"]["staff"]:
            database["stats"]["staff"][staff] = {"claimed": 0, "closed": 0}
        database["stats"]["staff"][staff]["closed"] += 1
        database["stats"]["logs"].append({
            "user": str(interaction.user.id),
            "action": f"أغلق التذكرة: {reason}",
            "time": str(datetime.now())
        })
        save_database()

        await interaction.response.send_message("🔒 تم إغلاق التذكرة من الإدارة.", ephemeral=True)
        transcript = await create_transcript(channel)
        await send_close_log(interaction, channel, transcript, reason)
        await asyncio.sleep(2)
        try:
            await channel.delete()
        except Exception:
            pass


class CloseRatingReasonModal(discord.ui.Modal):
    def __init__(self, ticket_channel_id, stars):
        super().__init__(title="سبب التقييم المنخفض")
        self.ticket_channel_id = ticket_channel_id
        self.stars = stars
        self.reason = discord.ui.TextInput(
            label="سبب التقييم",
            placeholder="اكتب سبب إعطائك أقل من 5 نجوم...",
            required=True, min_length=3, max_length=1000,
            style=discord.TextStyle.paragraph
        )
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        if not self.reason.value.strip():
            await interaction.response.send_message("❌ يجب كتابة سبب التقييم.", ephemeral=True)
            return
        await RatingView(self.ticket_channel_id).finalize_rating(
            interaction, self.stars, self.reason.value.strip()
        )


class RatingView(discord.ui.View):
    def __init__(self, ticket_channel_id):
        super().__init__(timeout=None)
        self.ticket_channel_id = ticket_channel_id

    async def start_rating(self, interaction, stars):
        ticket = database["open_tickets"].get(str(self.ticket_channel_id))
        if not ticket:
            await interaction.response.send_message("❌ التذكرة غير موجودة.", ephemeral=True)
            return
        # التقييم متاح لصاحب التذكرة أو للإداري المصرح له بها.
        is_owner = interaction.user.id == ticket.get("owner")
        if not is_owner and not check_staff(interaction):
            await interaction.response.send_message("❌ لا تملك صلاحية تقييم هذه التذكرة.", ephemeral=True)
            return
        if stars < 5:
            await interaction.response.send_modal(CloseRatingReasonModal(self.ticket_channel_id, stars))
        else:
            await self.finalize_rating(interaction, stars)

    async def finalize_rating(self, interaction, stars, rating_reason=None):
        ticket = database["open_tickets"].get(str(self.ticket_channel_id))
        if not ticket:
            return
        ticket_settings = database["tickets"].get(ticket["type"])
        if ticket_settings:
            ticket_settings["ratings"].append({
                "user": str(interaction.user.id),
                "stars": stars,
                "staff": ticket.get("claimed"),
                "reason": rating_reason,
                "time": str(datetime.now())
            })

        ticket["rating"] = stars
        ticket["rating_reason"] = rating_reason
        ticket["close_reason"] = "إغلاق بعد إتمام التقييم"
        if not ticket.get("closed_by"):
            ticket["closed_by"] = interaction.user.id
        if not ticket.get("closed_at"):
            ticket["closed_at"] = str(datetime.now())

        save_database()
        await send_rating_log(interaction, stars, ticket, rating_reason)

        channel = interaction.channel
        close_cat_id = ticket_settings.get("close_category") if ticket_settings else None
        if close_cat_id:
            close_category = interaction.guild.get_channel(close_cat_id)
            if close_category:
                try:
                    await channel.edit(category=close_category)
                except Exception:
                    pass

        transcript = await create_transcript(channel)
        await send_close_log(interaction, channel, transcript, ticket.get("close_reason"))

        if not interaction.response.is_done():
            await interaction.response.send_message(
                "⭐ تم حفظ تقييمك بنجاح، سيتم حذف الروم خلال 3 ثواني...", ephemeral=True
            )
        await asyncio.sleep(3)
        try:
            await channel.delete()
        except Exception:
            pass

    @discord.ui.button(label="⭐", style=discord.ButtonStyle.gray, custom_id="rating_1_sec")
    async def one(self, interaction, button):
        await self.start_rating(interaction, 1)

    @discord.ui.button(label="⭐⭐⭐", style=discord.ButtonStyle.blurple, custom_id="rating_3_sec")
    async def three(self, interaction, button):
        await self.start_rating(interaction, 3)

    @discord.ui.button(label="⭐⭐⭐⭐", style=discord.ButtonStyle.blurple, custom_id="rating_4_sec")
    async def four(self, interaction, button):
        await self.start_rating(interaction, 4)

    @discord.ui.button(label="⭐⭐⭐⭐⭐", style=discord.ButtonStyle.green, custom_id="rating_5_sec")
    async def five(self, interaction, button):
        await self.start_rating(interaction, 5)


async def send_rating_log(interaction, stars, ticket, rating_reason=None):
    staff = ticket.get("claimed")
    await send_ticket_log(interaction.guild, "rating", "⭐ تقييم تذكرة", fields=[
        ("👤 صاحب التذكرة", f"<@{ticket.get('owner')}>", True),
        ("👑 الإداري المستلم", f"<@{staff}>" if staff else "لا يوجد", True),
        ("⭐ التقييم", f"{stars}/5", True),
        ("📝 السبب", rating_reason or "لا يوجد — التقييم 5/5", False),
    ], color=discord.Color.gold())


# ==================================
# أوامر الإدارة داخل التذكرة
# ==================================

def _register_ticket_log_command(name, log_type, description, success_text):
    async def command(interaction: discord.Interaction, channel: discord.TextChannel):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ هذا الأمر مخصص للمشرفين فقط",
                ephemeral=True
            )
            return

        database.setdefault("log_channels", {})[log_type] = channel.id
        save_database()

        await interaction.response.send_message(
            embed=make_embed(
                "📜 تم ضبط روم اللوق",
                success_text.format(channel=channel.mention),
                discord.Color.green()
            ),
            ephemeral=True
        )

    command.__name__ = name.replace("-", "_")
    command.__doc__ = description
    command = app_commands.command(name=name, description=description)(command)
    command = app_commands.describe(channel="روم اللوق المخصص لهذا الحدث")(command)
    bot.tree.add_command(command)


_register_ticket_log_command(
    "ticket-open-log",
    "open",
    "تحديد روم لوق فتح التذاكر",
    "لوق **فتح التذاكر** سيصل إلى {channel}."
)
_register_ticket_log_command(
    "ticket-claim-log",
    "claim",
    "تحديد روم لوق استلام التذاكر",
    "لوق **استلام التذاكر** سيصل إلى {channel}."
)
_register_ticket_log_command(
    "ticket-close-log",
    "close",
    "تحديد روم لوق إغلاق التذاكر",
    "لوق **إغلاق التذاكر** سيصل إلى {channel}."
)
_register_ticket_log_command(
    "ticket-rating-log",
    "rating",
    "تحديد روم لوق تقييم التذاكر",
    "لوق **التقييمات** سيصل إلى {channel}."
)
_register_ticket_log_command(
    "ticket-note-log",
    "note",
    "تحديد روم لوق ملاحظات التذاكر",
    "لوق **الملاحظات** سيصل إلى {channel}."
)
_register_ticket_log_command(
    "ticket-admin-log",
    "admin",
    "تحديد روم لوق إجراءات الإدارة",
    "لوق **إجراءات الإدارة** سيصل إلى {channel}."
)


@bot.tree.command(name="claim", description="استلام التذكرة")
async def claim_ticket(interaction: discord.Interaction):
    if not check_staff(interaction):
        await interaction.response.send_message("❌ ليس لديك صلاحية لاستلام التذكرة", ephemeral=True)
        return

    ticket = get_ticket_from_channel(interaction.channel.id)
    if not ticket:
        await interaction.response.send_message("❌ التذكرة غير موجودة", ephemeral=True)
        return

    if ticket.get("claimed"):
        await interaction.response.send_message("⚠️ هذه التذكرة تم استلامها مسبقاً", ephemeral=True)
        return

    ticket["claimed"] = interaction.user.id
    ticket["claimed_at"] = str(datetime.now())
    
    staff = str(interaction.user.id)
    if staff not in database["stats"]["staff"]:
        database["stats"]["staff"][staff] = {"claimed": 0, "closed": 0}
    database["stats"]["staff"][staff]["claimed"] += 1

    database["stats"]["logs"].append({
        "user": str(interaction.user.id),
        "action": "استلم التذكرة",
        "time": str(datetime.now())
    })

    save_database()
    if database["tickets"].get(ticket.get("type"), {}).get("private_mode"):
        await apply_private_ticket_permissions(interaction.channel, ticket)
    await send_claim_log(interaction, interaction.channel, ticket)
    
    embed = make_embed(
        "👑 تم استلام التذكرة",
        f"الإداري المسؤول الآن:\n{interaction.user.mention}",
        discord.Color.gold()
    )
    await interaction.channel.send(embed=embed)
    await interaction.response.send_message(f"👑 تم استلام التذكرة", ephemeral=True)



@bot.tree.command(name="close", description="إغلاق التذكرة من الإدارة مع سبب")
async def close_ticket(interaction: discord.Interaction):
    if not check_staff(interaction):
        await interaction.response.send_message("❌ لا تملك صلاحية إغلاق التذكرة.", ephemeral=True)
        return

    ticket = get_ticket_from_channel(interaction.channel.id)
    if not ticket:
        await interaction.response.send_message("❌ التذكرة غير موجودة.", ephemeral=True)
        return
    if ticket.get("closed"):
        await interaction.response.send_message("⚠️ التذكرة مغلقة بالفعل.", ephemeral=True)
        return

    await interaction.response.send_modal(AdminCloseReasonModal(interaction.channel.id))

@bot.tree.command(name="rename", description="تغيير اسم التذكرة")
@app_commands.describe(name="الاسم الجديد")
async def rename_ticket(interaction: discord.Interaction, name: str):
    if not check_staff(interaction):
        await interaction.response.send_message("❌ لا تملك صلاحية", ephemeral=True)
        return

    await interaction.channel.edit(name=name)
    await log_ticket_action(interaction, "تغيير اسم التذكرة", f"الاسم الجديد: `{name}`", discord.Color.blue())
    database["stats"]["logs"].append({
        "user": str(interaction.user.id),
        "action": f"غير اسم التذكرة إلى {name}",
        "time": str(datetime.now())
    })
    save_database()
    await interaction.response.send_message("✅ تم تغيير الاسم")



@bot.tree.command(name="priority", description="تحديد أولوية التذكرة")
@app_commands.choices(
    level=[
        app_commands.Choice(name="عادي", value="normal"),
        app_commands.Choice(name="مهم", value="important"),
        app_commands.Choice(name="عاجل", value="urgent")
    ]
)
async def priority_ticket(interaction: discord.Interaction, level: app_commands.Choice[str]):
    if not check_staff(interaction):
        await interaction.response.send_message("❌ لا تملك صلاحية", ephemeral=True)
        return

    ticket = get_ticket_from_channel(interaction.channel.id)
    ticket["priority"] = level.value
    ticket["last_activity"] = str(datetime.now())
    save_database()
    await log_ticket_action(interaction, "تغيير أولوية", f"الأولوية الجديدة: **{level.name}**", discord.Color.orange())
    await interaction.response.send_message(f"📌 تم تغيير الأولوية إلى: {level.name}")



@bot.tree.command(name="ticket-add", description="إضافة عضو للتذكرة")
async def ticket_add(interaction: discord.Interaction, member: discord.Member):
    if not check_staff(interaction):
        await interaction.response.send_message("❌ لا تملك صلاحية", ephemeral=True)
        return

    await interaction.channel.set_permissions(member, view_channel=True, send_messages=True)
    ticket = get_ticket_from_channel(interaction.channel.id)
    if ticket:
        ticket.setdefault("added_members", []).append(member.id)
        save_database()
    await log_ticket_action(interaction, "إضافة عضو", f"تمت إضافة {member.mention}", discord.Color.green())
    await interaction.response.send_message(f"✅ تمت إضافة {member.mention}")



@bot.tree.command(name="ticket-remove", description="إزالة عضو من التذكرة")
async def ticket_remove(interaction: discord.Interaction, member: discord.Member):
    if not check_staff(interaction):
        await interaction.response.send_message("❌ لا تملك صلاحية", ephemeral=True)
        return

    await interaction.channel.set_permissions(member, overwrite=None)
    ticket = get_ticket_from_channel(interaction.channel.id)
    if ticket:
        ticket.setdefault("added_members", [])
        if member.id in ticket["added_members"]:
            ticket["added_members"].remove(member.id)
        save_database()
    await log_ticket_action(interaction, "إزالة عضو", f"تمت إزالة {member.mention}", discord.Color.red())
    await interaction.response.send_message(f"✅ تمت إزالة {member.mention}")



@bot.tree.command(name="lock", description="قفل الكتابة في التذكرة")
async def lock_ticket(interaction: discord.Interaction):
    if not check_staff(interaction):
        await interaction.response.send_message("❌ لا تملك صلاحية", ephemeral=True)
        return

    await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=False)
    await log_ticket_action(interaction, "قفل التذكرة", "تم منع إرسال الرسائل", discord.Color.red())
    await interaction.response.send_message("🔒 تم قفل التذكرة")



@bot.tree.command(name="unlock", description="فتح الكتابة في التذكرة")
async def unlock_ticket(interaction: discord.Interaction):
    if not check_staff(interaction):
        await interaction.response.send_message("❌ لا تملك صلاحية", ephemeral=True)
        return

    await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=True)
    await log_ticket_action(interaction, "فتح الكتابة", "تم السماح بإرسال الرسائل", discord.Color.green())
    await interaction.response.send_message("🔓 تم فتح التذكرة")



@bot.tree.command(name="reopen", description="إعادة فتح التذكرة")
async def reopen_ticket(interaction: discord.Interaction):
    if not check_staff(interaction):
        await interaction.response.send_message("❌ لا تملك صلاحية", ephemeral=True)
        return

    await interaction.channel.set_permissions(interaction.guild.default_role, view_channel=True)
    ticket = get_ticket_from_channel(interaction.channel.id)
    if ticket:
        ticket["closed"] = False
        ticket["reopened_at"] = str(datetime.now())
        save_database()
    await log_ticket_action(interaction, "إعادة فتح التذكرة", "تمت إعادة التذكرة للحالة المفتوحة", discord.Color.green())
    await interaction.response.send_message("🔄 تم إعادة فتح التذكرة")



@bot.tree.command(name="move", description="نقل التذكرة")
@app_commands.describe(category="ID الكاتجوري الجديد")
async def move_ticket(interaction: discord.Interaction, category: str):
    if not check_staff(interaction):
        await interaction.response.send_message("❌ لا تملك صلاحية", ephemeral=True)
        return

    try:
        category_id = int(category)
    except:
        await interaction.response.send_message("❌ ID غير صحيح", ephemeral=True)
        return

    new_category = interaction.guild.get_channel(category_id)
    if not new_category:
        await interaction.response.send_message("❌ لم يتم العثور على الكاتجوري", ephemeral=True)
        return

    old_category = interaction.channel.category.name if interaction.channel.category else "بدون كاتجوري"
    await interaction.channel.edit(category=new_category)
    await log_ticket_action(interaction, "نقل التذكرة", f"من: **{old_category}** إلى: **{new_category.name}**", discord.Color.blue())
    await interaction.response.send_message("🚚 تم نقل التذكرة")



@bot.tree.command(
    name="auto-move",
    description="نقل التذكرة تلقائياً إلى كاتجوري"
)
@app_commands.describe(
    category="ID الكاتجوري"
)
async def auto_move(
    interaction: discord.Interaction,
    category: str
):
    if not check_staff(interaction):
        await interaction.response.send_message(
            "❌ لا تملك صلاحية",
            ephemeral=True
        )
        return

    try:
        category_id = int(category)
    except:
        await interaction.response.send_message(
            "❌ ID غير صحيح",
            ephemeral=True
        )
        return

    new_category = interaction.guild.get_channel(category_id)

    if not new_category:
        await interaction.response.send_message(
            "❌ الكاتجوري غير موجود",
            ephemeral=True
        )
        return

    old_category = interaction.channel.category.name if interaction.channel.category else "بدون كاتجوري"
    await interaction.channel.edit(
        category=new_category
    )
    await log_ticket_action(interaction, "نقل تلقائي", f"من: **{old_category}** إلى: **{new_category.name}**", discord.Color.blue())

    embed = discord.Embed(
        title="🚚 تم نقل التذكرة",
        description=f"تم نقل التذكرة إلى:\n{new_category.name}",
        color=discord.Color.blue()
    )

    await interaction.response.send_message(
        embed=embed
    )



@bot.tree.command(
    name="ticket-info",
    description="عرض معلومات التذكرة الحالية"
)
async def ticket_info(interaction: discord.Interaction):

    ticket = get_ticket_from_channel(interaction.channel.id)

    if not ticket:
        await interaction.response.send_message(
            "❌ هذا الروم ليس تذكرة",
            ephemeral=True
        )
        return

    settings = database["tickets"].get(ticket["type"])

    embed = discord.Embed(
        title="🎫 معلومات التذكرة",
        color=discord.Color.blue()
    )

    embed.add_field(
        name="👤 صاحب التذكرة",
        value=f"<@{ticket['owner']}>",
        inline=False
    )

    embed.add_field(
        name="📌 النوع",
        value=settings["name"] if settings else "غير معروف",
        inline=False
    )

    embed.add_field(
        name="👑 المستلم",
        value=f"<@{ticket['claimed']}>" if ticket["claimed"] else "لا يوجد",
        inline=False
    )

    embed.add_field(
        name="📌 الأولوية",
        value=ticket.get("priority","normal"),
        inline=False
    )

    embed.add_field(
        name="📅 التاريخ",
        value=ticket.get("created","غير معروف"),
        inline=False
    )

    await interaction.response.send_message(
        embed=embed,
        ephemeral=True
    )



@bot.tree.command(
    name="ticket-note",
    description="إضافة ملاحظة للتذكرة"
)
@app_commands.describe(
    note="الملاحظة"
)
async def ticket_note(
    interaction: discord.Interaction,
    note: str
):

    if not check_staff(interaction):
        await interaction.response.send_message(
            "❌ ليس لديك صلاحية",
            ephemeral=True
        )
        return

    ticket = get_ticket_from_channel(interaction.channel.id)

    if not ticket:
        await interaction.response.send_message(
            "❌ ليست تذكرة",
            ephemeral=True
        )
        return

    ticket.setdefault("notes", [])

    ticket["notes"].append({
        "staff": interaction.user.id,
        "note": note,
        "time": str(datetime.now())
    })

    save_database()
    await log_ticket_action(interaction, "إضافة ملاحظة", f"📝 {note}", discord.Color.gold(), "note")

    await interaction.response.send_message(
        "✅ تم حفظ الملاحظة",
        ephemeral=True
    )



@bot.tree.command(
    name="ticket-notes",
    description="عرض ملاحظات التذكرة"
)
async def ticket_notes(interaction: discord.Interaction):

    ticket = get_ticket_from_channel(interaction.channel.id)

    if not ticket:
        await interaction.response.send_message(
            "❌ ليست تذكرة",
            ephemeral=True
        )
        return

    notes = ticket.get("notes", [])

    if not notes:
        await interaction.response.send_message(
            "📑 لا يوجد ملاحظات",
            ephemeral=True
        )
        return

    text = ""

    for n in notes:
        text += f"👤 <@{n['staff']}> : {n['note']}\n"

    embed = discord.Embed(
        title="📜 ملاحظات التذكرة",
        description=text,
        color=discord.Color.gold()
    )

    await interaction.response.send_message(
        embed=embed,
        ephemeral=True
    )



# ==================================
# أدوات Ticket Settings داخل التذكرة
# ==================================

TICKET_CONTROL_LABELS = {
    "close": ("Close Ticket", "🔒"),
    "rename": ("Rename Ticket", "✏️"),
    "add_member": ("Add Member", "➕"),
    "remove_member": ("Remove Member", "➖"),
    "move": ("Move Ticket", "🚚"),
    "priority": ("Priority", "📌"),
    "info": ("Ticket Info", "ℹ️"),
    "add_note": ("Add Note", "📝"),
    "notes": ("Ticket Notes", "📑")
}


def get_ticket_controls(ticket):
    settings = database.get("tickets", {}).get(ticket.get("type"), {})
    controls = settings.get("ticket_controls", {})
    defaults = default_ticket()["ticket_controls"]
    return {key: bool(controls.get(key, default)) for key, default in defaults.items()}


def build_ticket_settings_embed(ticket):
    controls = get_ticket_controls(ticket)
    enabled = [f"{emoji} {label}" for key, (label, emoji) in TICKET_CONTROL_LABELS.items() if controls.get(key)]
    description = "\n".join(enabled) if enabled else "لا توجد خيارات مفعلة حالياً."
    return discord.Embed(
        title="⚙️ Ticket Settings",
        description=f"اختر الإجراء الذي تريد تنفيذه:\n\n{description}",
        color=discord.Color.blurple()
    )


class TicketActionModal(discord.ui.Modal):
    def __init__(self, channel_id, action):
        titles = {
            "rename": "Rename Ticket",
            "add_member": "Add Member",
            "remove_member": "Remove Member",
            "move": "Move Ticket",
            "add_note": "Add Note"
        }
        super().__init__(title=titles.get(action, "Ticket Settings"))
        self.channel_id = str(channel_id)
        self.action = action
        prompts = {
            "rename": ("New name", "Enter the new ticket channel name."),
            "add_member": ("Member ID", "Enter the member ID."),
            "remove_member": ("Member ID", "Enter the member ID."),
            "move": ("Category ID", "Enter the new category ID."),
            "add_note": ("Note", "Write the note.")
        }
        label, placeholder = prompts[action]
        self.value = discord.ui.TextInput(
            label=label, placeholder=placeholder, required=True, max_length=1000,
            style=discord.TextStyle.paragraph if action == "add_note" else discord.TextStyle.short
        )
        self.add_item(self.value)

    async def on_submit(self, interaction: discord.Interaction):
        ticket = database.get("open_tickets", {}).get(self.channel_id)
        if not ticket:
            await interaction.response.send_message("❌ التذكرة غير موجودة", ephemeral=True)
            return
        if not check_staff(interaction):
            await interaction.response.send_message("❌ لا تملك صلاحية", ephemeral=True)
            return
        controls = get_ticket_controls(ticket)
        if not controls.get(self.action):
            await interaction.response.send_message("❌ هذا الخيار غير مفعل في إعدادات التذكرة", ephemeral=True)
            return

        value = self.value.value.strip()
        try:
            if self.action == "rename":
                await interaction.channel.edit(name=sanitize_ticket_channel_name(value, fallback="ticket"))
                await log_ticket_action(interaction, "تغيير اسم التذكرة", f"الاسم الجديد: `{value}`", discord.Color.blue())
                await interaction.response.send_message("✅ تم تغيير اسم التذكرة", ephemeral=True)
            elif self.action in {"add_member", "remove_member"}:
                member_id = int(re.search(r"\d+", value).group())
                member = interaction.guild.get_member(member_id)
                if not member:
                    raise ValueError
                if self.action == "add_member":
                    await interaction.channel.set_permissions(member, view_channel=True, send_messages=True, read_message_history=True)
                    ticket.setdefault("added_members", [])
                    if member.id not in ticket["added_members"]:
                        ticket["added_members"].append(member.id)
                    await interaction.response.send_message(f"✅ تمت إضافة {member.mention}", ephemeral=True)
                else:
                    await interaction.channel.set_permissions(member, overwrite=None)
                    ticket.setdefault("added_members", [])
                    ticket["added_members"] = [m for m in ticket["added_members"] if m != member.id]
                    await interaction.response.send_message(f"✅ تمت إزالة {member.mention}", ephemeral=True)
                save_database()
            elif self.action == "move":
                category_id = int(re.search(r"\d+", value).group())
                category = interaction.guild.get_channel(category_id)
                if not category or not isinstance(category, discord.CategoryChannel):
                    raise ValueError
                await interaction.channel.edit(category=category)
                await log_ticket_action(interaction, "نقل التذكرة", f"إلى: **{category.name}**", discord.Color.blue())
                await interaction.response.send_message(f"🚚 تم نقل التذكرة إلى **{category.name}**", ephemeral=True)
            elif self.action == "add_note":
                ticket.setdefault("notes", [])
                ticket["notes"].append({"staff": interaction.user.id, "note": value, "time": str(datetime.now())})
                save_database()
                await log_ticket_action(interaction, "إضافة ملاحظة", f"📝 {value}", discord.Color.gold())
                await interaction.response.send_message("✅ تم حفظ الملاحظة", ephemeral=True)
        except (ValueError, AttributeError):
            await interaction.response.send_message("❌ القيمة غير صحيحة", ephemeral=True)


class TicketManagementView(discord.ui.View):
    def __init__(self, channel_id):
        super().__init__(timeout=180)
        self.channel_id = str(channel_id)
        ticket = database.get("open_tickets", {}).get(self.channel_id)
        controls = get_ticket_controls(ticket) if ticket else {}
        for key, (label, emoji) in TICKET_CONTROL_LABELS.items():
            if not controls.get(key):
                continue
            button = discord.ui.Button(
                label=label, emoji=emoji, style=discord.ButtonStyle.secondary,
                custom_id=f"ticket_action_{key}_{self.channel_id}"[:100]
            )
            button.callback = self._callback_for(key)
            self.add_item(button)

    def _callback_for(self, action):
        async def callback(interaction: discord.Interaction):
            ticket = database.get("open_tickets", {}).get(self.channel_id)
            if not ticket:
                await interaction.response.send_message("❌ التذكرة غير موجودة", ephemeral=True)
                return
            if not check_staff(interaction):
                await interaction.response.send_message("❌ لا تملك صلاحية", ephemeral=True)
                return
            if not get_ticket_controls(ticket).get(action):
                await interaction.response.send_message("❌ هذا الخيار غير مفعل", ephemeral=True)
                return

            if action == "close":
                if ticket.get("closed"):
                    await interaction.response.send_message("⚠️ التذكرة مغلقة بالفعل", ephemeral=True)
                    return
                await interaction.response.send_message("🔒 تم طلب إغلاق التذكرة.\n⭐ اختر تقييمك للخدمة:", view=RatingView(interaction.channel.id), ephemeral=True)
            elif action in {"rename", "add_member", "remove_member", "move", "add_note"}:
                await interaction.response.send_modal(TicketActionModal(self.channel_id, action))
            elif action == "priority":
                await interaction.response.send_message("📌 اختر الأولوية من الأمر `/priority` داخل التذكرة.", ephemeral=True)
            elif action == "info":
                settings = database["tickets"].get(ticket["type"])
                embed = discord.Embed(title="🎫 معلومات التذكرة", color=discord.Color.blue())
                embed.add_field(name="👤 صاحب التذكرة", value=f"<@{ticket['owner']}>", inline=False)
                embed.add_field(name="📌 النوع", value=settings.get("name", "غير معروف") if settings else "غير معروف", inline=False)
                embed.add_field(name="👑 المستلم", value=f"<@{ticket['claimed']}>" if ticket.get("claimed") else "لا يوجد", inline=False)
                embed.add_field(name="📌 الأولوية", value=ticket.get("priority", "normal"), inline=False)
                await interaction.response.send_message(embed=embed, ephemeral=True)
            elif action == "notes":
                notes = ticket.get("notes", [])
                if not notes:
                    await interaction.response.send_message("📑 لا توجد ملاحظات", ephemeral=True)
                    return
                text_value = "\n".join(f"👤 <@{n.get('staff')}> : {n.get('note','')}" for n in notes)
                await interaction.response.send_message(embed=discord.Embed(title="📜 ملاحظات التذكرة", description=text_value, color=discord.Color.gold()), ephemeral=True)
        return callback


# ==================================
# إحصائيات استلام التذاكر
# ==================================

def parse_stats_duration(value):
    """تحويل مدة مثل 30s / 15m / 2h / 7d / 1w / 1mo / 1y إلى ثوانٍ.
    يدعم أيضاً المدد المركبة مثل 1d12h30m.
    """
    if not value:
        return None

    value = str(value).strip().lower().replace(" ", "")
    if value in {"all", "كل", "الكل", "0"}:
        return None

    pattern = re.compile(r"(\d+(?:\.\d+)?)(mo|y|w|d|h|m|s)")
    matches = list(pattern.finditer(value))
    if not matches or "".join(m.group(0) for m in matches) != value:
        raise ValueError("صيغة المدة غير صحيحة")

    units = {
        "s": 1,
        "m": 60,
        "h": 60 * 60,
        "d": 24 * 60 * 60,
        "w": 7 * 24 * 60 * 60,
        "mo": 30 * 24 * 60 * 60,
        "y": 365 * 24 * 60 * 60,
    }
    return sum(float(m.group(1)) * units[m.group(2)] for m in matches)


def get_claim_count(user_id, duration=None):
    """إحصاء الاستلام من سجل اللوق المحفوظ.
    بدون مدة: يرجع إجمالي الاستلام، بما فيه البيانات القديمة.
    مع مدة: يعتمد على أوقات الاستلام المحفوظة في stats.logs.
    """
    user_id = str(user_id)
    if duration is None:
        staff = database.get("stats", {}).get("staff", {}).get(user_id, {})
        return int(staff.get("claimed", 0))

    cutoff = datetime.now() - timedelta(seconds=duration)
    count = 0
    for log in database.get("stats", {}).get("logs", []):
        if str(log.get("user")) != user_id or log.get("action") != "استلم التذكرة":
            continue
        try:
            log_time = datetime.fromisoformat(str(log.get("time")))
            if log_time >= cutoff:
                count += 1
        except (ValueError, TypeError):
            continue
    return count


def get_all_claim_counts(duration=None):
    """إرجاع أعداد الاستلام مرتبة تنازلياً."""
    counts = {}
    stats = database.get("stats", {})
    staff_stats = stats.get("staff", {})

    if duration is None:
        for user_id, data in staff_stats.items():
            claimed = int(data.get("claimed", 0))
            if claimed > 0:
                counts[str(user_id)] = claimed
        return counts

    cutoff = datetime.now() - timedelta(seconds=duration)
    for log in stats.get("logs", []):
        if log.get("action") != "استلم التذكرة":
            continue
        try:
            log_time = datetime.fromisoformat(str(log.get("time")))
            if log_time < cutoff:
                continue
        except (ValueError, TypeError):
            continue
        user_id = str(log.get("user"))
        counts[user_id] = counts.get(user_id, 0) + 1

    return counts


def format_stats_duration(value):
    if not value:
        return "كل الوقت"
    return str(value).strip()


def can_use_claim_stats(interaction):
    """صلاحية إحصائيات الاستلام بدون اشتراط أن يكون الأمر داخل تذكرة."""
    user = interaction.user
    if user.guild_permissions.administrator or is_manager(user):
        return True
    user_role_ids = {role.id for role in getattr(user, "roles", [])}
    for settings in database.get("tickets", {}).values():
        if user_role_ids.intersection(set(settings.get("staff_roles", []))):
            return True
    return False


class TopClaimersView(discord.ui.View):
    def __init__(self, guild, duration=None, page=0):
        super().__init__(timeout=180)
        self.guild = guild
        self.duration = duration
        self.page = page
        self.refresh_button()

    def refresh_button(self):
        self.clear_items()
        counts = get_all_claim_counts(self.duration)
        ordered = sorted(counts.items(), key=lambda item: (-item[1], int(item[0])))
        start = self.page * 10
        has_more = start + 10 < len(ordered)

        if self.page > 0:
            back = discord.ui.Button(label="Back", style=discord.ButtonStyle.secondary, custom_id=f"top_claimers_back_{self.page}")
            back.callback = self.go_back
            self.add_item(back)

        if has_more:
            more = discord.ui.Button(label="More", style=discord.ButtonStyle.secondary, custom_id=f"top_claimers_more_{self.page}")
            more.callback = self.go_more
            self.add_item(more)

    async def go_more(self, interaction: discord.Interaction):
        self.page += 1
        self.refresh_button()
        await interaction.response.edit_message(embed=build_top_claimers_embed(self.guild, self.duration, self.page), view=self)

    async def go_back(self, interaction: discord.Interaction):
        self.page = max(0, self.page - 1)
        self.refresh_button()
        await interaction.response.edit_message(embed=build_top_claimers_embed(self.guild, self.duration, self.page), view=self)


def build_top_claimers_embed(guild, duration=None, page=0):
    counts = get_all_claim_counts(duration)
    ordered = sorted(counts.items(), key=lambda item: (-item[1], int(item[0])))
    start = page * 10
    page_items = ordered[start:start + 10]

    lines = []
    for index, (user_id, count) in enumerate(page_items, start=start + 1):
        member = guild.get_member(int(user_id))
        name = member.mention if member else f"<@{user_id}>"
        lines.append(f"**{index}**  {name} — `{count}` تذكرة")

    if not lines:
        description = "لا توجد تذاكر مستلمة ضمن هذه المدة."
    else:
        description = "\n".join(lines)

    embed = discord.Embed(
        title="توب مستلمين التذاكر",
        description=description,
        color=discord.Color.blurple()
    )
    embed.add_field(name="المدة", value=format_stats_duration(duration), inline=False)
    embed.set_footer(text=f"الصفحة {page + 1} • إجمالي المستلمين: {len(ordered)}")
    return embed


@bot.tree.command(name="claimer-count", description="Show how many tickets a staff member has claimed")
@app_commands.describe(
    member="الإداري المطلوب معرفة عدد التذاكر التي استلمها",
    duration="اختياري: 1s أو 1m أو 1h أو 1d أو 1w أو 1mo أو 1y"
)
async def claimed_count(interaction: discord.Interaction, member: discord.Member, duration: str = None):
    if not can_use_claim_stats(interaction):
        await interaction.response.send_message("❌ لا تملك صلاحية استخدام إحصائيات الاستلام", ephemeral=True)
        return


    try:
        seconds = parse_stats_duration(duration)
    except ValueError:
        await interaction.response.send_message(
            "❌ صيغة المدة غير صحيحة. أمثلة: `1s` `10m` `2h` `7d` `1w` `1mo` `1y` أو `1d12h`.",
            ephemeral=True
        )
        return

    count = get_claim_count(member.id, seconds)
    period = format_stats_duration(duration)
    embed = discord.Embed(
        title="عدد التذاكر المستلمة",
        description=f"{member.mention} استلم **{count}** تذكرة.",
        color=discord.Color.blurple()
    )
    embed.add_field(name="المدة", value=period, inline=False)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="top-claimers", description="Show the top ticket claimers")
@app_commands.describe(duration="اختياري: 1s أو 1m أو 1h أو 1d أو 1w أو 1mo أو 1y")
async def top_claimers(interaction: discord.Interaction, duration: str = None):
    if not can_use_claim_stats(interaction):
        await interaction.response.send_message("❌ لا تملك صلاحية استخدام إحصائيات الاستلام", ephemeral=True)
        return


    try:
        seconds = parse_stats_duration(duration)
    except ValueError:
        await interaction.response.send_message(
            "❌ صيغة المدة غير صحيحة. أمثلة: `1s` `10m` `2h` `7d` `1w` `1mo` `1y` أو `1d12h`.",
            ephemeral=True
        )
        return

    view = TopClaimersView(interaction.guild, seconds)
    await interaction.response.send_message(
        embed=build_top_claimers_embed(interaction.guild, seconds),
        view=view
    )


@bot.tree.command(name="ticket-stats", description="إحصائيات التذاكر")
async def ticket_stats(interaction: discord.Interaction):
    if not check_staff(interaction):
        await interaction.response.send_message("❌ لا تملك صلاحية", ephemeral=True)
        return

    opened = len(database["open_tickets"])
    closed = database.get("closed_today", 0)

    embed = discord.Embed(title="📊 إحصائيات التذاكر", color=discord.Color.blue())
    embed.add_field(name="🎫 المفتوحة", value=str(opened))
    embed.add_field(name="🔒 المغلقة", value=str(closed))
    await interaction.response.send_message(embed=embed)


# ==================================
# إعدادات التذكرة المخصصة
# ==================================

class TicketSettingsModal(discord.ui.Modal):
    def __init__(self, ticket_id, option):
        titles = {"welcome": "تعديل رسالة الترحيب", "staff_mention": "منشن الإدارة"}
        super().__init__(title=titles.get(option, "تعديل إعداد التذكرة"))
        self.ticket_id = ticket_id
        self.option = option
        self.value = discord.ui.TextInput(
            label="رسالة الترحيب" if option == "welcome" else "القيمة الجديدة",
            placeholder=("اكتب الرسالة ويمكنك استخدام عدة أسطر" if option == "welcome" else "أدخل ID الرتبة أو منشنها مثل <@&123456789>"),
            required=True,
            max_length=4000,
            style=discord.TextStyle.paragraph
        )
        self.add_item(self.value)

    async def on_submit(self, interaction: discord.Interaction):
        ticket = database["tickets"][self.ticket_id]
        value = self.value.value.strip()
        try:
            if self.option == "name": ticket["name"] = value
            elif self.option == "description":
                ticket["description"] = value; ticket["panel_description"] = value
            elif self.option == "emoji": ticket["emoji"] = value
            elif self.option == "color": ticket["color"] = value
            elif self.option == "welcome": ticket["welcome_message"] = self.value.value
            elif self.option == "image": ticket["ticket_image"] = value; ticket["image"] = value
            elif self.option == "open_category": ticket["open_category"] = int(value)
            elif self.option == "close_category": ticket["close_category"] = int(value)
            elif self.option == "staff_role":
                role_id = int(re.search(r"\d+", value).group()); ticket.setdefault("staff_roles", [])
                if role_id not in ticket["staff_roles"]: ticket["staff_roles"].append(role_id)
            elif self.option == "remove_staff_role":
                role_id = int(re.search(r"\d+", value).group())
                if role_id in ticket.get("staff_roles", []): ticket["staff_roles"].remove(role_id)
            elif self.option == "staff_mention":
                role_id = int(re.search(r"\d+", value).group())
                if not interaction.guild.get_role(role_id): raise ValueError
                ticket["staff_mention_role"] = role_id
            elif self.option == "remove_staff_mention": ticket["staff_mention_role"] = None
            save_database()
            await interaction.response.send_message("✅ تم حفظ التعديل بنجاح", ephemeral=True)
        except (ValueError, AttributeError):
            await interaction.response.send_message("❌ القيمة غير صحيحة. تأكد من ID/منشن الرتبة.", ephemeral=True)


class TicketSettingsView(discord.ui.View):
    def __init__(self, ticket_id):
        super().__init__(timeout=None); self.ticket_id = ticket_id

    @discord.ui.select(
        placeholder="اختر إعداد للتعديل",
        options=[
            discord.SelectOption(label="اسم التذكرة", value="name", emoji="🏷️"),
            discord.SelectOption(label="وصف البانل", value="description", emoji="📜"),
            discord.SelectOption(label="إيموجي التذكرة", value="emoji", emoji="😀"),
            discord.SelectOption(label="لون التذكرة", value="color", emoji="🎨"),
            discord.SelectOption(label="رسالة الترحيب متعددة الأسطر", value="welcome", emoji="👋"),
            discord.SelectOption(label="صورة داخل التذكرة", value="image", emoji="🖼️"),
            discord.SelectOption(label="كاتجوري الفتح", value="open_category", emoji="📂"),
            discord.SelectOption(label="كاتجوري الإغلاق", value="close_category", emoji="🔒"),
            discord.SelectOption(label="إضافة رتبة إدارة", value="staff_role", emoji="🛡️"),
            discord.SelectOption(label="إزالة رتبة إدارة", value="remove_staff_role", emoji="❌"),
            discord.SelectOption(label="منشن الإدارة عند فتح التذكرة", value="staff_mention", emoji="📢"),
            discord.SelectOption(label="إزالة منشن الإدارة", value="remove_staff_mention", emoji="🔕")
        ]
    )
    async def select_callback(self, interaction: discord.Interaction, select: discord.ui.Select):
        await interaction.response.send_modal(TicketSettingsModal(self.ticket_id, select.values[0]))


@bot.tree.command(name="ticket-mode", description="تفعيل الوضع الخاص أو الجماعي لنوع تذكرة")
@app_commands.describe(
    ticket_id="معرف نوع التذكرة مثل ticket_1",
    mode="اختر الخاص أو الجماعي"
)
@app_commands.choices(
    mode=[
        app_commands.Choice(name="🔒 خاص - صاحب التذكرة + الإداري المستلم", value="private"),
        app_commands.Choice(name="👥 جماعي - كل الإدارة المسموح لها", value="group"),
    ]
)
async def ticket_mode(
    interaction: discord.Interaction,
    ticket_id: str,
    mode: app_commands.Choice[str]
):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ هذا الأمر للمشرفين فقط", ephemeral=True)
        return

    settings = database.get("tickets", {}).get(ticket_id)
    if not settings:
        await interaction.response.send_message("❌ نوع التذكرة غير موجود. مثال: `ticket_1`", ephemeral=True)
        return

    settings["private_mode"] = mode.value == "private"
    save_database()

    # تطبيق الإعداد فوراً على كل التذاكر المفتوحة من نفس النوع.
    for channel_id, ticket in list(database.get("open_tickets", {}).items()):
        if ticket.get("type") != ticket_id:
            continue
        channel = interaction.guild.get_channel(int(channel_id))
        if not channel:
            continue
        if settings["private_mode"]:
            await apply_private_ticket_permissions(channel, ticket)
        else:
            # إعادة صلاحيات الرتب المعتادة للتذكرة.
            overwrites = {
                interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            }
            owner = interaction.guild.get_member(int(ticket.get("owner"))) if ticket.get("owner") else None
            if owner:
                overwrites[owner] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
            for role_id in settings.get("staff_roles", []):
                role = interaction.guild.get_role(role_id)
                if role:
                    overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
            try:
                await channel.edit(overwrites=overwrites)
            except Exception as e:
                print(f"Group ticket permission error: {e}")

    label = "🔒 الخاص" if settings["private_mode"] else "👥 الجماعي"
    await interaction.response.send_message(
        f"✅ تم ضبط `{ticket_id}` على **{label}**.\n"
        "في الخاص: التذكرة تظهر لصاحبها وللإداري المستلم فقط، ويمكن لصاحب صلاحية Administrator إغلاقها عند الحاجة.",
        ephemeral=True
    )


@bot.tree.command(name="ticket-quick-setup", description="إنشاء تذكرة وبانل وربطهما بضغطة واحدة")
@app_commands.describe(
    name="اسم نوع التذكرة",
    description="الوصف الذي يظهر في البانل",
    emoji="الإيموجي الذي يظهر بجانب خيار فتح التذكرة",
    panel_id="معرف بانل موجود، اتركه فارغاً لإنشاء بانل جديد",
    panel_title="عنوان البانل الجديد (اختياري)",
    panel_description="وصف البانل الذي يظهر تحت العنوان",
    name_format="صيغة اسم الروم، استخدم {name} و {count} و {emoji} و {user}",
    panel_image="صورة البانل (اختياري)"
)
async def ticket_quick_setup(
    interaction: discord.Interaction,
    name: str,
    description: str,
    emoji: str = "🎫",
    panel_id: str = None,
    panel_title: str = "🎫 نظام التذاكر",
    panel_description: str = "اختر نوع التذكرة من القائمة بالأسفل",
    name_format: str = "{name}-{count}",
    panel_image: discord.Attachment = None
):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ هذا الأمر للمشرفين فقط", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    ticket_id = create_ticket_id()
    ticket_data = default_ticket()
    ticket_data["name"] = name.strip() or "تذكرة جديدة"
    ticket_data["description"] = description.strip() or "اضغط لفتح التذكرة"
    ticket_data["panel_description"] = ticket_data["description"]
    ticket_data["emoji"] = emoji.strip() or "🎫"
    ticket_data["name_format"] = name_format.strip() or "{name}-{count}"
    database["tickets"][ticket_id] = ticket_data

    created_panel = False
    if panel_id:
        panel = database.get("panels", {}).get(panel_id)
        if not panel:
            await interaction.followup.send(f"❌ البانل `{panel_id}` غير موجود.", ephemeral=True)
            del database["tickets"][ticket_id]
            return
    else:
        panel_number = 1
        while f"panel_{panel_number}" in database.get("panels", {}):
            panel_number += 1
        panel_id = f"panel_{panel_number}"
        panel = {
            "title": panel_title.strip() or "🎫 نظام التذاكر",
            "description": panel_description.strip() or "اختر نوع التذكرة من القائمة بالأسفل",
            "image": panel_image.url if panel_image else None,
            "channel": interaction.channel.id,
            "message_id": None,
            "created_by": interaction.user.id,
            "created_at": str(datetime.now()),
            "tickets": []
        }
        database.setdefault("panels", {})[panel_id] = panel
        created_panel = True

    panel.setdefault("tickets", [])
    if ticket_id not in panel["tickets"]:
        panel["tickets"].append(ticket_id)

    save_database()

    if created_panel:
        embed = discord.Embed(
            title=panel["title"],
            description=panel["description"],
            color=discord.Color.blue()
        )
        message = await interaction.channel.send(
            embed=embed,
            view=TicketPanel(panel_id)
        )
        panel["message_id"] = message.id
        save_database()
    else:
        await refresh_panel_message(interaction.guild, panel_id)

    await send_ticket_log(
        interaction.guild,
        "admin",
        "⚡ إعداد تذكرة سريع",
        fields=[
            ("🎫 التذكرة", f"{ticket_data['emoji']} {ticket_data['name']}", True),
            ("🆔 المعرف", ticket_id, True),
            ("🖥️ البانل", panel_id, True),
            ("👤 بواسطة", interaction.user.mention, True)
        ],
        color=discord.Color.green()
    )

    await interaction.followup.send(
        embed=make_embed(
            "⚡ تم الإعداد بسرعة",
            f"🎫 **التذكرة:** {ticket_data['emoji']} {ticket_data['name']}\n"
            f"🆔 **المعرف:** `{ticket_id}`\n"
            f"🖥️ **البانل:** `{panel_id}`\n"
            f"📍 **الروم:** {interaction.channel.mention}\n\n"
            f"📝 صيغة الاسم: `{ticket_data['name_format']}`\n"
            "تم إنشاء النوع وربطه بالبانل وتحديث القائمة تلقائياً.",
            discord.Color.green()
        ),
        ephemeral=True
    )


@bot.tree.command(name="ticket-settings", description="Control which actions appear in Ticket Settings")
@app_commands.describe(
    ticket_id="Ticket type ID, for example ticket_1",
    setting="Choose the Ticket Settings option",
    enabled="Show or hide this option"
)
@app_commands.choices(
    setting=[
        app_commands.Choice(name="Close Ticket", value="close"),
        app_commands.Choice(name="Rename Ticket", value="rename"),
        app_commands.Choice(name="Add Member", value="add_member"),
        app_commands.Choice(name="Remove Member", value="remove_member"),
        app_commands.Choice(name="Move Ticket", value="move"),
        app_commands.Choice(name="Priority", value="priority"),
        app_commands.Choice(name="Ticket Info", value="info"),
        app_commands.Choice(name="Add Note", value="add_note"),
        app_commands.Choice(name="Ticket Notes", value="notes")
    ],
    enabled=[
        app_commands.Choice(name="Yes", value="yes"),
        app_commands.Choice(name="No", value="no")
    ]
)
async def ticket_settings(
    interaction: discord.Interaction,
    ticket_id: str,
    setting: app_commands.Choice[str],
    enabled: app_commands.Choice[str]
):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ هذا الأمر للمشرفين فقط", ephemeral=True)
        return
    ticket = database.get("tickets", {}).get(ticket_id)
    if not ticket:
        await interaction.response.send_message("❌ نوع التذكرة غير موجود", ephemeral=True)
        return
    ticket.setdefault("ticket_controls", {}).setdefault(setting.value, True)
    ticket["ticket_controls"][setting.value] = enabled.value == "yes"
    save_database()
    state = "مفعل" if enabled.value == "yes" else "مخفي"
    await interaction.response.send_message(
        f"✅ **{setting.name}** أصبح **{state}** داخل Ticket Settings لنوع `{ticket_id}`.",
        ephemeral=True
    )


@bot.tree.command(name="ticket-type-settings", description="Edit the general settings of a ticket type")
@app_commands.describe(ticket_id="Ticket type ID")
async def ticket_type_settings(interaction: discord.Interaction, ticket_id: str):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ هذا الأمر مخصص للمشرفين فقط", ephemeral=True)
        return
    if ticket_id not in database["tickets"]:
        await interaction.response.send_message("❌ نوع التذكرة غير موجود", ephemeral=True)
        return
    embed = discord.Embed(
        title="⚙️ إعدادات نوع التذكرة",
        description=f"تعديل:\n🎫 {database['tickets'][ticket_id]['name']}",
        color=discord.Color.gold()
    )
    await interaction.response.send_message(embed=embed, view=TicketSettingsView(ticket_id), ephemeral=True)


# ==================================
# نظام الحماية و Anti-Spam والخلفيات
# ==================================

spam_users = {}
SPAM_LIMIT = 5
SPAM_TIME = 5


async def anti_spam(message):
    user = message.author.id
    now = asyncio.get_event_loop().time()

    if user not in spam_users:
        spam_users[user] = []

    spam_users[user].append(now)

    spam_users[user] = [
        x for x in spam_users[user]
        if now - x <= SPAM_TIME
    ]

    if len(spam_users[user]) >= SPAM_LIMIT:
        try:
            await message.delete()
        except:
            pass

        embed = discord.Embed(
            title="⚠️ حماية السبام",
            description=f"{message.author.mention} تم منع الإرسال السريع.",
            color=discord.Color.orange()
        )

        await message.channel.send(
            embed=embed,
            delete_after=5
        )

        spam_users[user] = []


AUTO_CLOSE_TIME = 24 * 60 * 60

async def auto_close_checker():
    await bot.wait_until_ready()
    while not bot.is_closed():
        now = datetime.now()
        for channel_id, ticket in list(database["open_tickets"].items()):
            try:
                created = datetime.fromisoformat(ticket["created"])
                if (now - created).total_seconds() >= AUTO_CLOSE_TIME:
                    channel = bot.get_channel(int(channel_id))
                    if channel:
                        embed = discord.Embed(
                            title="🔒 إغلاق تلقائي",
                            description="تم إغلاق التذكرة بسبب عدم النشاط لمدة 24 ساعة.",
                            color=discord.Color.red()
                        )
                        await channel.send(embed=embed)
                        try:
                            await channel.delete()
                        except:
                            pass
                    del database["open_tickets"][channel_id]
                    save_database()
            except:
                pass
        await asyncio.sleep(300)


async def database_backup():
    await bot.wait_until_ready()
    while not bot.is_closed():
        with open(BACKUP_FILE, "w", encoding="utf-8") as file:
            json.dump(
                database,
                file,
                indent=4,
                ensure_ascii=False
            )
        await asyncio.sleep(3600)


@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return

    channel_id = message.channel.id
    if str(channel_id) in database["open_tickets"]:
        database["open_tickets"][str(channel_id)]["last_activity"] = str(datetime.now())
        save_database()

    await anti_spam(message)
    await bot.process_commands(message)



@bot.event
async def on_guild_channel_delete(channel):
    if str(channel.id) in database["open_tickets"]:
        database["open_tickets"].pop(str(channel.id))
        database["stats"]["total_closed"] += 1
        save_database()


# ==================================
# تشغيل البوت واستقرار الـ Persistent Views
# ==================================

@bot.event
async def on_ready():
    print(f"✅ Bot Online: {bot.user}")

    for panel_id in database.get("panels", {}):
        try:
            bot.add_view(TicketPanel(panel_id))
        except Exception as e:
            print(f"❌ Failed to load panel {panel_id}: {e}")

    bot.add_view(TicketButtons())

    for channel_id in database["open_tickets"]:
        bot.add_view(RatingView(int(channel_id)))

    bot.loop.create_task(auto_close_checker())
    bot.loop.create_task(database_backup())

    # تمت مزامنة Slash Commands في setup_hook عند بدء البوت.


TOKEN = os.getenv("DISCORD_TOKEN")

if TOKEN:
    bot.run(TOKEN)
else:
    print("❌ Token not found!")
