import discord
from discord.ext import commands, tasks
from datetime import datetime, date, timedelta
import json
import os
from flask import Flask
from threading import Thread
import time

# Configuración - Replit usa Secrets para tokens
BOT_TOKEN = os.environ['DISCORD_BOT_TOKEN']
BIRTHDAY_CHANNEL_ID = 1236048095163318362
DATA_FILE = 'birthdays.json'

# Configurar intents
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True

# Crear bot
bot = commands.Bot(command_prefix='!', intents=intents)

# Cargar datos de cumpleaños (VERSIÓN MEJORADA)
def load_birthdays():
    try:
        # Verificar si el archivo existe y no está vacío
        if not os.path.exists(DATA_FILE) or os.path.getsize(DATA_FILE) == 0:
            print("📁 Creando nuevo archivo birthdays.json")
            with open(DATA_FILE, 'w') as f:
                json.dump({}, f)
            return {}

        with open(DATA_FILE, 'r') as f:
            data = json.load(f)

            # Verificación exhaustiva del formato
            if not isinstance(data, dict):
                print("❌ Formato inválido. Creando nuevo archivo.")
                with open(DATA_FILE, 'w') as f:
                    json.dump({}, f)
                return {}

            # Limpiar entradas corruptas
            cleaned_data = {}
            for user_id, bday_data in data.items():
                if (isinstance(bday_data, dict) and 
                    'date' in bday_data and 
                    isinstance(bday_data['date'], str) and
                    len(bday_data['date']) == 5 and
                    bday_data['date'][2] == '-'):
                    cleaned_data[user_id] = bday_data

            if cleaned_data != data:
                print("🔄 Limpiando datos corruptos")
                with open(DATA_FILE, 'w') as f:
                    json.dump(cleaned_data, f, indent=4)

            return cleaned_data

    except (FileNotFoundError, json.JSONDecodeError, TypeError) as e:
        print(f"❌ Error al cargar archivo: {e}. Creando uno nuevo.")
        with open(DATA_FILE, 'w') as f:
            json.dump({}, f)
        return {}

# Guardar datos de cumpleaños
def save_birthdays(data):
    try:
        with open(DATA_FILE, 'w') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"❌ Error al guardar: {e}")

# Función para obtener próximos cumpleaños
def get_upcoming_birthdays(days=30):
    birthdays = load_birthdays()
    today = date.today()
    upcoming = []

    for user_id, bday_data in birthdays.items():
        try:
            # Formato DD-MM (cambiado de MM-DD a DD-MM)
            bday_day = int(bday_data['date'][:2])
            bday_month = int(bday_data['date'][3:])

            # Validar fecha
            if not (1 <= bday_month <= 12 and 1 <= bday_day <= 31):
                continue

            # Crear fecha para este año
            bday_this_year = date(today.year, bday_month, bday_day)

            # Si ya pasó este año, ver para el próximo año
            if bday_this_year < today:
                bday_next_year = date(today.year + 1, bday_month, bday_day)
                days_until = (bday_next_year - today).days
                bday_date = bday_next_year
            else:
                days_until = (bday_this_year - today).days
                bday_date = bday_this_year

            if days_until <= days:
                upcoming.append({
                    'user_id': user_id,
                    'date': bday_data['date'],  # Mantiene formato DD-MM
                    'actual_date': bday_date,
                    'days_until': days_until,
                    'message': bday_data.get('message', '')
                })

        except (ValueError, KeyError):
            continue

    # Ordenar por días restantes
    upcoming.sort(key=lambda x: x['days_until'])
    return upcoming

# Comprobar cumpleaños diariamente
@tasks.loop(hours=24)
async def check_birthdays():
    await bot.wait_until_ready()

    try:
        birthdays = load_birthdays()
        today = date.today().strftime("%d-%m")  # Cambiado a DD-MM

        channel = bot.get_channel(BIRTHDAY_CHANNEL_ID)
        if not channel:
            print("❌ Canal de cumpleaños no encontrado")
            return

        print(f"📅 Comprobando cumpleaños para {today}. Total: {len(birthdays)}")

        for user_id, bday_data in birthdays.items():
            try:
                bday_date = bday_data['date']
                if bday_date == today:
                    user = await bot.fetch_user(int(user_id))
                    if user:
                        message = f"🎉 ¡Feliz cumpleaños {user.mention}! 🎂\n{bday_data.get('message', 'Que tengas un día maravilloso!')}"
                        await channel.send(message)
                        print(f"✅ Felicitación enviada a {user.name}")
            except Exception as e:
                print(f"❌ Error con usuario {user_id}: {e}")
                continue

    except Exception as e:
        print(f"❌ Error crítico en check_birthdays: {e}")

# Comando para agregar cumpleaños (FORMATO DD-MM)
@bot.command(name='agregar_cumple')
async def add_birthday(ctx, usuario: discord.User, fecha: str, *, mensaje: str = "Que tengas un día maravilloso!"):
    try:
        # Validar formato de fecha (DD-MM) - CAMBIADO
        # Primero verificar el formato
        if len(fecha) != 5 or fecha[2] != '-':
            raise ValueError

        day = int(fecha[:2])
        month = int(fecha[3:])

        # Validar rango de fechas
        if not (1 <= month <= 12 and 1 <= day <= 31):
            raise ValueError

        # Validar fecha específica (ej: 31-04 no existe)
        try:
            test_date = date(2024, month, day)  # Año bisiesto para probar
        except ValueError:
            await ctx.send("❌ Fecha inválida. Verifica el día y mes.")
            return

        birthdays = load_birthdays()
        birthdays[str(usuario.id)] = {
            'date': fecha,  # Formato DD-MM
            'message': mensaje,
            'added_by': str(ctx.author.id)
        }

        save_birthdays(birthdays)

        await ctx.send(f"✅ Cumpleaños de {usuario.mention} agregado para el {fecha}")
        print(f"📝 Cumpleaños agregado: {usuario.name} - {fecha}")

    except ValueError:
        await ctx.send("❌ Formato de fecha incorrecto. Usa: DD-MM (ej: 25-12 para Navidad)")
    except Exception as e:
        await ctx.send("❌ Error al agregar cumpleaños")
        print(f"❌ Error en agregar_cumple: {e}")

# Comando para ver cumpleaños
@bot.command(name='cumpleaños')
async def list_birthdays(ctx):
    try:
        birthdays = load_birthdays()

        if not birthdays:
            await ctx.send("📝 No hay cumpleaños registrados")
            return

        embed = discord.Embed(title="🎂 Lista de Cumpleaños", color=0xff69b4)

        for user_id, data in birthdays.items():
            try:
                user = await bot.fetch_user(int(user_id))
                username = user.name if user else "Usuario desconocido"
            except:
                username = "Usuario desconocido"

            embed.add_field(
                name=f"{username} - {data['date']}",  # Formato DD-MM
                value=data['message'],
                inline=False
            )

        await ctx.send(embed=embed)

    except Exception as e:
        await ctx.send("❌ Error al cargar la lista de cumpleaños")
        print(f"❌ Error en cumpleaños: {e}")

# Comando para próximos cumpleaños
@bot.command(name='proximos_cumples')
async def upcoming_birthdays(ctx, dias: int = 30):
    try:
        if dias <= 0 or dias > 365:
            await ctx.send("❌ Por favor usa un número entre 1 y 365 días")
            return

        upcoming = get_upcoming_birthdays(dias)

        if not upcoming:
            await ctx.send(f"📅 No hay cumpleaños en los próximos {dias} días")
            return

        embed = discord.Embed(
            title=f"🎂 Próximos Cumpleaños ({dias} días)",
            color=0x00ff00
        )

        for bday in upcoming:
            try:
                user = await bot.fetch_user(int(bday['user_id']))
                username = user.name if user else "Usuario desconocido"
            except:
                username = "Usuario desconocido"

            # Formatear fecha bonita (ej: "25 de Diciembre")
            meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
                    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
            dia = bday['actual_date'].day
            mes = meses[bday['actual_date'].month - 1]
            fecha_bonita = f"{dia} de {mes}"

            embed.add_field(
                name=f"{username} - {fecha_bonita}",
                value=f"📅 En {bday['days_until']} días\n💬 {bday['message']}",
                inline=False
            )

        await ctx.send(embed=embed)

    except Exception as e:
        await ctx.send("❌ Error al cargar próximos cumpleaños")
        print(f"❌ Error en proximos_cumples: {e}")

# Comando para eliminar cumpleaños
@bot.command(name='eliminar_cumple')
async def remove_birthday(ctx, usuario: discord.User):
    try:
        birthdays = load_birthdays()

        if str(usuario.id) in birthdays:
            if (birthdays[str(usuario.id)]['added_by'] == str(ctx.author.id) or 
                ctx.author.guild_permissions.administrator):

                del birthdays[str(usuario.id)]
                save_birthdays(birthdays)
                await ctx.send(f"✅ Cumpleaños de {usuario.mention} eliminado")
                print(f"🗑️ Cumpleaños eliminado: {usuario.name}")
            else:
                await ctx.send("❌ Solo quien agregó el cumpleaños o un administrador puede eliminarlo")
        else:
            await ctx.send("❌ No hay cumpleaños registrado para este usuario")

    except Exception as e:
        await ctx.send("❌ Error al eliminar cumpleaños")
        print(f"❌ Error en eliminar_cumple: {e}")

# Comando para probar el bot
@bot.command(name='probar_cumple')
@commands.has_permissions(administrator=True)
async def test_birthday(ctx, usuario: discord.User):
    """Comando de prueba para administradores"""
    try:
        channel = bot.get_channel(BIRTHDAY_CHANNEL_ID)
        if channel:
            await channel.send(f"🎉 ¡Feliz cumpleaños de prueba {usuario.mention}! 🎂")
            await ctx.send("✅ Mensaje de prueba enviado")
            print(f"🧪 Prueba exitosa para {usuario.name}")
        else:
            await ctx.send("❌ Canal no encontrado")
    except Exception as e:
        await ctx.send("❌ Error en prueba")
        print(f"❌ Error en probar_cumple: {e}")

# Evento cuando el bot está listo
@bot.event
async def on_ready():
    print(f'✅ Bot conectado como {bot.user}')
    # Agrega esta línea para cambiar el estado
    await bot.change_presence(activity=discord.Activity(
        type=discord.ActivityType.watching, 
        name="los cumpleaños 🎂"
    ))
    birthdays = load_birthdays()
    print(f'📊 Cumpleaños cargados: {len(birthdays)}')
    check_birthdays.start()
    print('✅ Comprobación de cumpleaños iniciada')

# Manejar errores
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ Faltan argumentos. Usa: !agregar_cumple @usuario DD-MM [mensaje]")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("❌ Argumento inválido. Asegúrate de mencionar al usuario correctamente")
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ No tienes permisos para usar este comando")
    else:
        await ctx.send("❌ Error desconocido")
        print(f"Error: {error}")

# Servidor Flask para mantener vivo el bot (VERSIÓN MEJORADA)
app = Flask(__name__)

@app.route('/')
def home():
    try:
        # Verificar si el bot está conectado
        if bot.is_ready():
            return "🤖 Birthday Bot está funcionando! ✅"
        else:
            return "🤖 Birthday Bot está iniciando... ⏳"
    except:
        return "🤖 Birthday Bot está en mantenimiento 🛠️"

@app.route('/health')
def health_check():
    """Endpoint especial para UptimeRobot - SIEMPRE devuelve 200"""
    try:
        if bot.is_ready() and not bot.is_closed():
            return {
                "status": "online", 
                "bot": "connected",
                "timestamp": datetime.now().isoformat(),
                "users": len(load_birthdays())
            }, 200
        else:
            return {
                "status": "booting", 
                "bot": "reconnecting",
                "timestamp": datetime.now().isoformat(),
                "message": "Bot se está reconectando, esto es normal en Replit"
            }, 200
    except Exception as e:
        return {
            "status": "reconnecting",
            "error": "Reconexión automática en progreso",
            "timestamp": datetime.now().isoformat(),
            "message": "Esto es normal después de inactividad en Replit"
        }, 200

# Función para mantener el servidor activo
def run_flask():
    print("🌐 Iniciando servidor Flask...")
    app.run(host='0.0.0.0', port=8080, debug=False, use_reloader=False)

def keep_alive():
    server = Thread(target=run_flask)
    server.daemon = True
    server.start()
    print("✅ Servidor Flask iniciado en segundo plano")

# Iniciar el bot
try:
    keep_alive()
    print("🚀 Iniciando bot de Discord...")
    bot.run(BOT_TOKEN)
except Exception as e:
    print(f"❌ Error crítico: {e}")
    print("🔄 Reiniciando en 10 segundos...")
    time.sleep(10)
    # Auto-reconexión
    os._exit(1)