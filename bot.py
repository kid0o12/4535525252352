import discord
from discord import app_commands
from discord.ext import commands, tasks
from discord.ui import View, Button
import json
import os
import re
import asyncio
from datetime import datetime, timezone

# ============================================================
# CONFIG
# ============================================================
CONFIG_FILE = "config.json"
DATA_DIR = "data"
DATA_FILE = os.path.join(DATA_DIR, "roles.json")

DEFAULT_CONFIG = {
    "token": "PON_AQUI_EL_TOKEN",
    "guild_id": 0,
    "log_channel_id": 0,
    "prefix": "!"
}

os.makedirs(DATA_DIR, exist_ok=True)

if not os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(DEFAULT_CONFIG, f, indent=4, ensure_ascii=False)

if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump({"guilds": {}}, f, indent=4, ensure_ascii=False)

with open(CONFIG_FILE, "r", encoding="utf-8") as f:
    CONFIG = json.load(f)

TOKEN = CONFIG.get("token", "")
GUILD_ID = int(CONFIG.get("guild_id", 0) or 0)
LOG_CHANNEL_ID = int(CONFIG.get("log_channel_id", 0) or 0)

# ============================================================
# DATA
# ============================================================
def load_data():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"guilds": {}}


def save_data(data):
    temp_file = DATA_FILE + ".tmp"
    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    os.replace(temp_file, DATA_FILE)


DATA = load_data()


def guild_data(guild_id: int):
    gid = str(guild_id)
    if gid not in DATA["guilds"]:
        DATA["guilds"][gid] = {
            "roles": {},
            "settings": {
                "log_channel_id": 0
            }
        }
    return DATA["guilds"][gid]


# ============================================================
# TIME
# ============================================================
TIME_UNITS = {
    "s": 1,
    "sec": 1,
    "secs": 1,
    "second": 1,
    "seconds": 1,
    "m": 60,
    "min": 60,
    "mins": 60,
    "minute": 60,
    "minutes": 60,
    "h": 3600,
    "hr": 3600,
    "hrs": 3600,
    "hour": 3600,
    "hours": 3600,
    "d": 86400,
    "day": 86400,
    "days": 86400,
    "w": 604800,
    "week": 604800,
    "weeks": 604800
}

TIME_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*([a-zA-Z]+)\s*$")


def parse_duration(value: str):
    match = TIME_RE.match(value)
    if not match:
        return None

    amount = float(match.group(1))
    unit = match.group(2).lower()

    if unit not in TIME_UNITS or amount <= 0:
        return None

    seconds = int(amount * TIME_UNITS[unit])
    if seconds <= 0:
        return None

    return seconds


def format_duration(seconds: float):
    seconds = max(0, int(seconds))

    weeks, rem = divmod(seconds, 604800)
    days, rem = divmod(rem, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, seconds = divmod(rem, 60)

    parts = []
    if weeks:
        parts.append(f"{weeks} semana{'s' if weeks != 1 else ''}")
    if days:
        parts.append(f"{days} día{'s' if days != 1 else ''}")
    if hours:
        parts.append(f"{hours} hora{'s' if hours != 1 else ''}")
    if minutes:
        parts.append(f"{minutes} minuto{'s' if minutes != 1 else ''}")
    if seconds and not weeks and not days:
        parts.append(f"{seconds} segundo{'s' if seconds != 1 else ''}")

    return ", ".join(parts) if parts else "menos de 1 segundo"


def discord_timestamp(unix: int):
    return f"<t:{unix}:F>"


def discord_relative(unix: int):
    return f"<t:{unix}:R>"


# ============================================================
# EMBEDS
# ============================================================
def embed_success(title, description):
    return discord.Embed(
        title=f"✅ {title}",
        description=description,
        color=discord.Color.green(),
        timestamp=datetime.now(timezone.utc)
    )


def embed_error(title, description):
    return discord.Embed(
        title=f"❌ {title}",
        description=description,
        color=discord.Color.red(),
        timestamp=datetime.now(timezone.utc)
    )


def embed_info(title, description):
    return discord.Embed(
        title=f"ℹ️ {title}",
        description=description,
        color=discord.Color.blurple(),
        timestamp=datetime.now(timezone.utc)
    )


def embed_expired(title, description):
    return discord.Embed(
        title=f"⏰ {title}",
        description=description,
        color=discord.Color.orange(),
        timestamp=datetime.now(timezone.utc)
    )


# ============================================================
# UI
# ============================================================
class HelpView(View):
    def __init__(self):
        super().__init__(timeout=120)

    @discord.ui.button(label="Comandos", emoji="📜", style=discord.ButtonStyle.primary)
    async def commands_button(self, interaction: discord.Interaction, button: Button):
        e = embed_info(
            "Comandos disponibles",
            "**/addrole** `@usuario @rol 7d`\n"
            "Añade un rol durante un tiempo determinado.\n\n"
            "**/remove_role** `@usuario @rol`\n"
            "Elimina un rol temporal.\n\n"
            "**/roltime** `@usuario`\n"
            "Muestra los roles temporales y su tiempo restante.\n\n"
            "**/temproles**\n"
            "Lista todos los roles temporales activos.\n\n"
            "**/rolinfo** `@rol`\n"
            "Información del rol y sus usuarios temporales.\n\n"
            "**/settings**\n"
            "Configuración del sistema."
        )
        await interaction.response.edit_message(embed=e, view=self)

    @discord.ui.button(label="Ayuda", emoji="❓", style=discord.ButtonStyle.secondary)
    async def help_button(self, interaction: discord.Interaction, button: Button):
        e = embed_info(
            "TempRole Manager",
            "Sistema de gestión de **roles temporales**.\n\n"
            "Usa `/addrole` para crear una duración y el bot eliminará "
            "automáticamente el rol cuando llegue la fecha de expiración."
        )
        await interaction.response.edit_message(embed=e, view=self)


# ============================================================
# BOT
# ============================================================
class TempRoleBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.guilds = True
        intents.members = True
        super().__init__(
            command_prefix=CONFIG.get("prefix", "!"),
            intents=intents
        )

    async def setup_hook(self):
        self.expiration_loop.start()

        if GUILD_ID:
            guild = discord.Object(id=GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            print(f"Slash commands sincronizados en {GUILD_ID}")
        else:
            await self.tree.sync()
            print("Slash commands globales sincronizados.")

    async def on_ready(self):
        print("=" * 55)
        print(f"Bot conectado como {self.user}")
        print(f"ID: {self.user.id}")
        print("=" * 55)

    async def send_log(self, guild, embed):
        settings = guild_data(guild.id)["settings"]
        channel_id = settings.get("log_channel_id", 0) or LOG_CHANNEL_ID

        if not channel_id:
            return

        channel = guild.get_channel(int(channel_id))
        if channel:
            try:
                await channel.send(embed=embed)
            except discord.HTTPException:
                pass

    @tasks.loop(seconds=30)
    async def expiration_loop(self):
        now = int(datetime.now(timezone.utc).timestamp())
        changed = False

        for guild_id, gd in list(DATA["guilds"].items()):
            guild = self.get_guild(int(guild_id))
            if guild is None:
                continue

            for key, record in list(gd.get("roles", {}).items()):
                if int(record["expires_at"]) > now:
                    continue

                member = guild.get_member(int(record["user_id"]))
                role = guild.get_role(int(record["role_id"]))

                if member and role:
                    try:
                        if role in member.roles:
                            await member.remove_roles(
                                role,
                                reason="Rol temporal expirado"
                            )

                        e = embed_expired(
                            "Rol expirado",
                            f"El rol {role.mention} de {member.mention} "
                            f"ha expirado y ha sido eliminado automáticamente."
                        )
                        e.add_field(name="Rol", value=role.mention, inline=True)
                        e.add_field(name="Usuario", value=member.mention, inline=True)
                        await self.send_log(guild, e)
                    except discord.Forbidden:
                        pass
                    except discord.HTTPException:
                        pass

                del gd["roles"][key]
                changed = True

        if changed:
            save_data(DATA)

    @expiration_loop.before_loop
    async def before_expiration_loop(self):
        await self.wait_until_ready()


bot = TempRoleBot()


# ============================================================
# PERMISSION HELPERS
# ============================================================
def can_manage_roles(interaction: discord.Interaction):
    if not interaction.guild or not isinstance(interaction.user, discord.Member):
        return False
    return interaction.user.guild_permissions.manage_roles


def valid_bot_role(guild: discord.Guild, role: discord.Role):
    me = guild.me
    if me is None:
        return False, "No puedo comprobar mis permisos."

    if role.is_default():
        return False, "No puedes usar `@everyone`."

    if role.managed:
        return False, "Ese rol está gestionado por una integración y no puede modificarse."

    if role >= me.top_role:
        return False, "Ese rol está por encima o al mismo nivel que mi rol más alto."

    return True, ""


# ============================================================
# COMMAND: /addrole
# ============================================================
@bot.tree.command(name="addrole", description="Añade un rol temporal a un usuario.")
@app_commands.describe(
    usuario="Usuario que recibirá el rol.",
    rol="Rol temporal que quieres añadir.",
    duracion="Duración: 30m, 2h, 7d, 2w..."
)
async def addrole(
    interaction: discord.Interaction,
    usuario: discord.Member,
    rol: discord.Role,
    duracion: str
):
    if not can_manage_roles(interaction):
        await interaction.response.send_message(
            embed=embed_error(
                "Sin permisos",
                "Necesitas el permiso **Gestionar roles** para utilizar este comando."
            ),
            ephemeral=True
        )
        return

    seconds = parse_duration(duracion)
    if seconds is None:
        await interaction.response.send_message(
            embed=embed_error(
                "Duración incorrecta",
                "Usa formatos como:\n"
                "`30m` → 30 minutos\n"
                "`2h` → 2 horas\n"
                "`7d` → 7 días\n"
                "`2w` → 2 semanas"
            ),
            ephemeral=True
        )
        return

    valid, reason = valid_bot_role(interaction.guild, rol)
    if not valid:
        await interaction.response.send_message(
            embed=embed_error("No puedo gestionar ese rol", reason),
            ephemeral=True
        )
        return

    if usuario.bot:
        await interaction.response.send_message(
            embed=embed_error(
                "Usuario no válido",
                "No puedes asignar roles temporales a bots."
            ),
            ephemeral=True
        )
        return

    await interaction.response.defer()

    key = f"{usuario.id}:{rol.id}"
    now = int(datetime.now(timezone.utc).timestamp())
    expires_at = now + seconds

    existing = guild_data(interaction.guild.id)["roles"].get(key)

    # Renovación: si ya existe, suma el nuevo tiempo al que quedaba.
    if existing and int(existing["expires_at"]) > now:
        expires_at = int(existing["expires_at"]) + seconds
        action = "renovado"
    else:
        action = "añadido"

    try:
        await usuario.add_roles(
            rol,
            reason=f"Rol temporal: {duracion} | por {interaction.user}"
        )
    except discord.Forbidden:
        await interaction.followup.send(
            embed=embed_error(
                "No puedo añadir el rol",
                "Comprueba que mi rol está por encima del rol que intentas asignar."
            ),
            ephemeral=True
        )
        return
    except discord.HTTPException:
        await interaction.followup.send(
            embed=embed_error(
                "Error de Discord",
                "Discord no ha permitido modificar los roles. Inténtalo de nuevo."
            ),
            ephemeral=True
        )
        return

    guild_data(interaction.guild.id)["roles"][key] = {
        "user_id": usuario.id,
        "role_id": rol.id,
        "expires_at": expires_at,
        "added_by": interaction.user.id
    }
    save_data(DATA)

    e = embed_success(
        "Rol temporal " + action,
        f"{rol.mention} ha sido asignado a {usuario.mention}."
    )
    e.add_field(name="⏳ Duración añadida", value=f"`{duracion}`", inline=True)
    e.add_field(name="🕐 Expira", value=discord_timestamp(expires_at), inline=True)
    e.add_field(name="📅 Tiempo restante", value=discord_relative(expires_at), inline=True)
    e.set_footer(text=f"Gestionado por {interaction.user}", icon_url=interaction.user.display_avatar.url)

    await interaction.followup.send(embed=e)
    await bot.send_log(interaction.guild, e)


# ============================================================
# COMMAND: /remove_role
# ============================================================
@bot.tree.command(name="remove_role", description="Elimina un rol temporal de un usuario.")
@app_commands.describe(
    usuario="Usuario al que quitar el rol.",
    rol="Rol que quieres eliminar."
)
async def remove_role(
    interaction: discord.Interaction,
    usuario: discord.Member,
    rol: discord.Role
):
    if not can_manage_roles(interaction):
        await interaction.response.send_message(
            embed=embed_error(
                "Sin permisos",
                "Necesitas el permiso **Gestionar roles** para utilizar este comando."
            ),
            ephemeral=True
        )
        return

    key = f"{usuario.id}:{rol.id}"
    record = guild_data(interaction.guild.id)["roles"].get(key)

    try:
        await usuario.remove_roles(rol, reason=f"Rol temporal eliminado por {interaction.user}")
    except discord.Forbidden:
        await interaction.response.send_message(
            embed=embed_error(
                "No puedo quitar el rol",
                "Comprueba la jerarquía de roles del bot."
            ),
            ephemeral=True
        )
        return
    except discord.HTTPException:
        await interaction.response.send_message(
            embed=embed_error("Error de Discord", "No se pudo eliminar el rol."),
            ephemeral=True
        )
        return

    if record:
        del guild_data(interaction.guild.id)["roles"][key]
        save_data(DATA)

    e = embed_success(
        "Rol eliminado",
        f"{rol.mention} ha sido eliminado de {usuario.mention}."
    )

    if record:
        e.add_field(name="Estado", value="Temporizador cancelado.", inline=False)
    else:
        e.add_field(name="Estado", value="No había un temporizador registrado.", inline=False)

    await interaction.response.send_message(embed=e)
    await bot.send_log(interaction.guild, e)


# ============================================================
# COMMAND: /roltime
# ============================================================
@bot.tree.command(name="roltime", description="Muestra cuánto tiempo queda de los roles temporales.")
@app_commands.describe(usuario="Usuario que quieres consultar.")
async def roltime(
    interaction: discord.Interaction,
    usuario: discord.Member
):
    records = [
        r for r in guild_data(interaction.guild.id)["roles"].values()
        if int(r["user_id"]) == usuario.id
    ]

    now = int(datetime.now(timezone.utc).timestamp())
    records = [r for r in records if int(r["expires_at"]) > now]

    e = discord.Embed(
        title="⏳ Roles temporales",
        description=f"Información de {usuario.mention}",
        color=discord.Color.blurple(),
        timestamp=datetime.now(timezone.utc)
    )
    e.set_thumbnail(url=usuario.display_avatar.url)

    if not records:
        e.description += "\n\n`Este usuario no tiene roles temporales activos.`"
        await interaction.response.send_message(embed=e)
        return

    for record in sorted(records, key=lambda x: int(x["expires_at"])):
        role = interaction.guild.get_role(int(record["role_id"]))
        if role is None:
            continue

        expires = int(record["expires_at"])
        e.add_field(
            name=f"🎭 {role.name}",
            value=(
                f"**Expira:** {discord_timestamp(expires)}\n"
                f"**Queda:** {discord_relative(expires)}\n"
                f"**Tiempo exacto:** `{format_duration(expires - now)}`"
            ),
            inline=False
        )

    e.set_footer(text=f"{len(records)} rol(es) temporal(es) activo(s)")
    await interaction.response.send_message(embed=e)


# ============================================================
# COMMAND: /temproles
# ============================================================
@bot.tree.command(name="temproles", description="Lista todos los roles temporales activos del servidor.")
async def temproles(interaction: discord.Interaction):
    records = []

    now = int(datetime.now(timezone.utc).timestamp())

    for record in guild_data(interaction.guild.id)["roles"].values():
        expires = int(record["expires_at"])
        if expires <= now:
            continue

        member = interaction.guild.get_member(int(record["user_id"]))
        role = interaction.guild.get_role(int(record["role_id"]))

        if member and role:
            records.append((member, role, expires))

    e = embed_info(
        "Roles temporales activos",
        f"Hay **{len(records)}** temporizador(es) activo(s) en este servidor."
    )

    if not records:
        e.description += "\n\nNo hay roles temporales activos."
        await interaction.response.send_message(embed=e)
        return

    records.sort(key=lambda x: x[2])

    chunks = []
    for member, role, expires in records[:25]:
        chunks.append(
            f"**{role.name}** → {member.mention}\n"
            f"└ Expira {discord_relative(expires)}"
        )

    e.add_field(
        name="📋 Temporizadores",
        value="\n\n".join(chunks),
        inline=False
    )

    if len(records) > 25:
        e.set_footer(text=f"Mostrando 25 de {len(records)} temporizadores.")

    await interaction.response.send_message(embed=e)


# ============================================================
# COMMAND: /rolinfo
# ============================================================
@bot.tree.command(name="rolinfo", description="Muestra información sobre un rol temporal.")
@app_commands.describe(rol="Rol que quieres consultar.")
async def rolinfo(
    interaction: discord.Interaction,
    rol: discord.Role
):
    now = int(datetime.now(timezone.utc).timestamp())
    records = [
        r for r in guild_data(interaction.guild.id)["roles"].values()
        if int(r["role_id"]) == rol.id and int(r["expires_at"]) > now
    ]

    e = discord.Embed(
        title=f"🎭 Información de {rol.name}",
        description=f"ID: `{rol.id}`\nMenciones: {rol.mention}",
        color=rol.color if rol.color.value else discord.Color.blurple(),
        timestamp=datetime.now(timezone.utc)
    )

    e.add_field(name="👥 Temporales activos", value=f"`{len(records)}`", inline=True)
    e.add_field(name="🎨 Color", value=str(rol.color), inline=True)
    e.add_field(name="🔒 Gestionado", value="Sí" if rol.managed else "No", inline=True)

    if records:
        users = []
        for record in records[:25]:
            member = interaction.guild.get_member(int(record["user_id"]))
            if member:
                users.append(
                    f"{member.mention} — {discord_relative(int(record['expires_at']))}"
                )

        e.add_field(
            name="👤 Usuarios",
            value="\n".join(users) if users else "Ninguno",
            inline=False
        )

    await interaction.response.send_message(embed=e)


# ============================================================
# COMMAND: /settings
# ============================================================
@bot.tree.command(name="settings", description="Configura el sistema de roles temporales.")
@app_commands.describe(
    canal_logs="Canal donde se enviarán los avisos de expiración."
)
async def settings(
    interaction: discord.Interaction,
    canal_logs: discord.TextChannel | None = None
):
    if not interaction.user.guild_permissions.manage_guild:
        await interaction.response.send_message(
            embed=embed_error(
                "Sin permisos",
                "Necesitas **Gestionar servidor** para cambiar la configuración."
            ),
            ephemeral=True
        )
        return

    gd = guild_data(interaction.guild.id)

    if canal_logs:
        gd["settings"]["log_channel_id"] = canal_logs.id
        save_data(DATA)

        e = embed_success(
            "Configuración actualizada",
            f"Los avisos de expiración se enviarán en {canal_logs.mention}."
        )
        await interaction.response.send_message(embed=e)
        return

    channel_id = gd["settings"].get("log_channel_id", 0)
    channel = interaction.guild.get_channel(int(channel_id)) if channel_id else None

    e = embed_info(
        "Configuración",
        f"**Canal de logs:** {channel.mention if channel else 'No configurado'}\n\n"
        "Para configurarlo usa:\n"
        "`/settings #canal`"
    )
    await interaction.response.send_message(embed=e, ephemeral=True)


# ============================================================
# COMMAND: /temprolehelp
# ============================================================
@bot.tree.command(name="temprolehelp", description="Muestra la ayuda del sistema.")
async def temprolehelp(interaction: discord.Interaction):
    e = discord.Embed(
        title="🎛️ TempRole Manager",
        description=(
            "Sistema avanzado de **roles temporales**.\n\n"
            "Los temporizadores se guardan automáticamente, por lo que "
            "reiniciar el bot no elimina la información."
        ),
        color=discord.Color.blurple()
    )
    e.add_field(
        name="➕ Añadir",
        value="`/addrole @usuario @rol 7d`",
        inline=False
    )
    e.add_field(
        name="➖ Eliminar",
        value="`/remove_role @usuario @rol`",
        inline=False
    )
    e.add_field(
        name="⏱️ Tiempo restante",
        value="`/roltime @usuario`",
        inline=False
    )
    e.add_field(
        name="📋 Todos los temporales",
        value="`/temproles`",
        inline=False
    )
    e.add_field(
        name="🎭 Información del rol",
        value="`/rolinfo @rol`",
        inline=False
    )
    e.add_field(
        name="⚙️ Configuración",
        value="`/settings #canal`",
        inline=False
    )
    e.set_footer(text="TempRole Manager • Sistema de roles temporales")

    await interaction.response.send_message(embed=e, view=HelpView())


# ============================================================
# ERROR HANDLER
# ============================================================
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.MissingPermissions):
        message = "No tienes permisos suficientes para utilizar este comando."
    elif isinstance(error, app_commands.CommandOnCooldown):
        message = "Este comando está en cooldown. Espera un momento."
    else:
        print(f"Command error: {repr(error)}")
        message = "Ha ocurrido un error inesperado. Revisa la consola del bot."

    try:
        if interaction.response.is_done():
            await interaction.followup.send(
                embed=embed_error("Error", message),
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                embed=embed_error("Error", message),
                ephemeral=True
            )
    except discord.HTTPException:
        pass


# ============================================================
# START
# ============================================================
if __name__ == "__main__":
    if not TOKEN or TOKEN == "PON_AQUI_EL_TOKEN":
        print("ERROR: introduce el token del bot en config.json")
    else:
        bot.run(TOKEN)
