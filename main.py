"""
Bot de Telegram para Gestión de Notas de Pedido y Despacho 24/7 (Railway / Cloud)
Comando principal: /nota (Modo interactivo con botones o formato rápido en 1 línea)
Gummies Viking Venezuela
"""

import os
import sys
import logging
from datetime import datetime

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# Importar motor BCV y generador de notas
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from dolar_api import get_dolar_oficial
from generar_nota_pedido import generar_nota_pedido

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuración del Bot
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "9058473536:AAHM284rhV8Js85QLdyzLPwpXC3IiKAhjFk")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "generated_notes")
RECEPTION_DIR = os.path.join(BASE_DIR, "reception_images")

os.makedirs(OUTPUT_DIR, exist_ok=True)

# Estados de la conversación para /nota
SELECT_PRODUCT, INPUT_CLIENTE, INPUT_CEDULA, INPUT_TELEFONO, INPUT_SEDE, INPUT_GUIA = range(6)

# Catálogo predefinido de combos
PRODUCT_PRESETS = {
    "combo3": {
        "nombre": "Combo 3 Pares (6 Gomitas)",
        "items": [("Combo 3 Pares (6 Gomitas Viking)", 1, "$25.00")],
        "total": 25.0
    },
    "combo3_cherry": {
        "nombre": "Combo 3 Pares + Gel Cherry",
        "items": [
            ("Combo 3 Pares (6 Gomitas Viking)", 1, "$25.00"),
            ("Gel Íntimo Potenciador Cherry (10ml)", 1, "$3.99")
        ],
        "total": 28.99
    },
    "pote30": {
        "nombre": "Pote Grande 30 Gomitas",
        "items": [("Pote Grande 30 Gomitas Viking", 1, "$45.00")],
        "total": 45.0
    },
    "pote30_cherry": {
        "nombre": "Pote 30 Gomitas + Gel Cherry",
        "items": [
            ("Pote Grande 30 Gomitas Viking", 1, "$45.00"),
            ("Gel Íntimo Potenciador Cherry (10ml)", 1, "$4.00")
        ],
        "total": 49.0
    },
    "pack1": {
        "nombre": "Pack 1 Par (2 Gomitas)",
        "items": [("Pack 1 Par (2 Gomitas Viking)", 1, "$21.00")],
        "total": 21.0
    }
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "👑 *Asistente Logístico 24/7 - Gummies Viking Venezuela*\n\n"
        "Comandos disponibles:\n"
        "🔹 `/nota` - Crear una nueva *Nota de Pedido / Comprobante de Despacho* (con botones interactivos o en 1 sola línea).\n"
        "🔹 `/recepcion` - Recibir las 2 opciones de *Fotos de Recepción* para WhatsApp.\n"
        "🔹 `/tasa` - Consultar tasa oficial BCV del día.\n"
        "🔹 `/cancel` - Cancelar creación en curso."
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def cmd_tasa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    info = get_dolar_oficial()
    tasa = info.get("tasa", 904.48)
    fecha = info.get("fecha", "Hoy")
    await update.message.reply_text(
        f"💵 *Tasa Oficial BCV:*\n`Bs {tasa:,.2f}` por USD\n📅 Fecha: {fecha}",
        parse_mode="Markdown"
    )

async def cmd_recepcion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    p1 = os.path.join(RECEPTION_DIR, "recepcion_opcion1_logistica.png")
    p2 = os.path.join(RECEPTION_DIR, "recepcion_opcion2_confidencial.png")
    
    await update.message.reply_text("📦 Enviando las 2 opciones de Fotos de Recepción para WhatsApp:")
    
    if os.path.exists(p1):
        with open(p1, "rb") as f1:
            await update.message.reply_photo(
                photo=f1,
                caption="📋 *Opción 1: Ficha Logística / Entrada a Bodega*\nIdeal para leads que vienen de la web y ya eligieron producto."
            )
    if os.path.exists(p2):
        with open(p2, "rb") as f2:
            await update.message.reply_photo(
                photo=f2,
                caption="🔒 *Opción 2: Tarjeta de Privacidad y Producto*\nIdeal para generar máxima confianza y responder objeciones de discreción."
            )

# --- FLUJO /nota ---
async def cmd_nota_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args_text = " ".join(context.args) if context.args else ""
    if "|" in args_text:
        return await process_fast_nota(update, context, args_text)

    keyboard = [
        [
            InlineKeyboardButton("🍬 Combo 3 Pares ($25)", callback_data="prod_combo3"),
            InlineKeyboardButton("🍒 Combo + Cherry ($28.99)", callback_data="prod_combo3_cherry"),
        ],
        [
            InlineKeyboardButton("⚡ Pote 30 ($45)", callback_data="prod_pote30"),
            InlineKeyboardButton("👑 Pote 30 + Cherry ($49)", callback_data="prod_pote30_cherry"),
        ],
        [
            InlineKeyboardButton("📦 Pack 1 Par ($21)", callback_data="prod_pack1"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "📝 *Creación de Nota de Pedido*\n\n"
        "*Paso 1:* Selecciona el producto o combo acordado con el cliente:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    return SELECT_PRODUCT

async def product_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    prod_key = query.data.replace("prod_", "")
    preset = PRODUCT_PRESETS.get(prod_key)
    if not preset:
        await query.edit_message_text("❌ Producto no reconocido. Cancela con /cancel")
        return ConversationHandler.END
        
    context.user_data["preset"] = preset
    context.user_data["total_usd"] = preset["total"]
    context.user_data["productos"] = preset["items"]
    
    await query.edit_message_text(
        f"✅ *Producto seleccionado:* {preset['nombre']} (${preset['total']:.2f})\n\n"
        "👤 *Paso 2:* Envía el *Nombre y Apellido* del cliente:",
        parse_mode="Markdown"
    )
    return INPUT_CLIENTE

async def client_name_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nombre = update.message.text.strip()
    context.user_data["cliente"] = nombre
    
    await update.message.reply_text(
        f"✅ Cliente: *{nombre}*\n\n"
        "🪪 *Paso 3:* Envía el número de *Cédula de Identidad* (solo números o con V-):",
        parse_mode="Markdown"
    )
    return INPUT_CEDULA

async def cedula_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ced = update.message.text.strip().upper().replace("V-", "").replace("V", "").replace(".", "").strip()
    try:
        ced_formatted = f"{int(ced):,}".replace(",", ".")
    except ValueError:
        ced_formatted = ced
        
    context.user_data["cedula"] = ced_formatted
    
    await update.message.reply_text(
        f"✅ Cédula: *V-{ced_formatted}*\n\n"
        "📱 *Paso 4:* Envía el número de *Teléfono* del cliente (ej: `0412-1234567`):",
        parse_mode="Markdown"
    )
    return INPUT_TELEFONO

async def telefono_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tel = update.message.text.strip()
    context.user_data["telefono"] = tel
    
    await update.message.reply_text(
        f"✅ Teléfono: *{tel}*\n\n"
        "🏢 *Paso 5:* Envía la *Ciudad y Sede Tealca* donde retira (ej: `Punto Fijo (Sede Centro)` o `Mérida (Sede Milla)`):",
        parse_mode="Markdown"
    )
    return INPUT_SEDE

async def sede_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sede = update.message.text.strip()
    context.user_data["sede"] = sede
    
    await update.message.reply_text(
        f"✅ Destino: *Agencia Tealca - {sede}*\n\n"
        "🔢 *Paso 6:* Envía el código de orden Dropanas (ej: `DP74634` o guía `85110297`).\n"
        "*(Si aún no lo montas en Dropanas, escribe `0` para poner EN PREPARACIÓN)*:",
        parse_mode="Markdown"
    )
    return INPUT_GUIA

async def guia_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    guia_raw = update.message.text.strip().upper()
    if guia_raw in ["0", "NO", "PENDIENTE", "NONE"]:
        guia_tracking = "EN PREPARACIÓN / TEALCA"
    elif "TEALCA" not in guia_raw:
        guia_tracking = f"{guia_raw} / TEALCA"
    else:
        guia_tracking = guia_raw
        
    context.user_data["guia"] = guia_tracking
    
    await update.message.reply_text("⏳ *Generando comprobante oficial de despacho en alta resolución...*", parse_mode="Markdown")
    
    return await render_and_send_nota(update, context)

async def render_and_send_nota(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = context.user_data
    cliente = u["cliente"]
    cedula = u["cedula"]
    telefono = u["telefono"]
    sede = u["sede"]
    productos = u["productos"]
    total_usd = u["total_usd"]
    guia = u["guia"]
    
    info = get_dolar_oficial()
    tasa = info.get("tasa", 904.48)
    
    safe_name = "".join(c for c in cliente if c.isalnum() or c in (" ", "_")).strip().lower().replace(" ", "_")
    filename = f"nota_entrega_{safe_name}.png"
    out_path = os.path.join(OUTPUT_DIR, filename)
    
    generar_nota_pedido(
        cliente=cliente,
        cedula=cedula,
        telefono=telefono,
        ciudad_agencia=sede,
        productos=productos,
        total_usd=total_usd,
        tasa_bcv=tasa,
        guia_tracking=guia,
        out_path=out_path
    )
    
    with open(out_path, "rb") as photo_file:
        await update.message.reply_photo(
            photo=photo_file,
            caption=(
                f"✅ *Comprobante Generado con Éxito*\n\n"
                f"👤 *Cliente:* {cliente}\n"
                f"🪪 *Cédula:* V-{cedula}\n"
                f"🏢 *Destino:* Tealca {sede}\n"
                f"💵 *Total:* ${total_usd:.2f} USD (Bs {total_usd*tasa:,.2f})\n"
                f"📦 *Guía:* `{guia}`"
            ),
            parse_mode="Markdown"
        )
    
    clean_tel = "".join(c for c in telefono if c.isdigit())
    if clean_tel.startswith("0"):
        clean_tel = "58" + clean_tel[1:]
    elif not clean_tel.startswith("58") and len(clean_tel) == 10:
        clean_tel = "58" + clean_tel
        
    wa_link = f"https://wa.me/{clean_tel}"
    
    primer_nombre = cliente.split()[0]
    wa_msg = (
        f"¡Excelente, {primer_nombre}! Quedó confirmada tu cédula y tu orden asegurada en sistema. 🔒📦\n\n"
        f"Aquí tienes tu *Comprobante de Despacho* con todos tus datos hacia Tealca {sede} por tus ${total_usd:.2f}. "
        f"En cuanto la valija sea despachada te comparto el número de rastreo oficial en vivo. ¡Seguimos en contacto! 🤝"
    )
    
    msg_box = (
        "💬 *Mensaje listo para copiar y enviar al cliente por WhatsApp:*\n\n"
        f"```text\n{wa_msg}\n```\n\n"
        f"📲 [Abrir Chat de WhatsApp con {primer_nombre}]({wa_link})"
    )
    await update.message.reply_text(msg_box, parse_mode="Markdown", disable_web_page_preview=True)
    
    return ConversationHandler.END

async def process_fast_nota(update: Update, context: ContextTypes.DEFAULT_TYPE, raw_text: str):
    parts = [p.strip() for p in raw_text.split("|")]
    if len(parts) < 4:
        await update.message.reply_text(
            "❌ Formato rápido incorrecto. Usa:\n"
            "`/nota Cliente | Cédula | Teléfono | Sede Tealca | Combo (opcional) | Total USD (opcional) | Código DP (opcional)`\n\n"
            "Ejemplo:\n"
            "`/nota Pedro Medina | 15592611 | 04127712248 | Punto Fijo Centro | 3 Pares Cherry | 28.99 | DP74634`",
            parse_mode="Markdown"
        )
        return
        
    cliente = parts[0]
    ced = parts[1].upper().replace("V-", "").replace("V", "").replace(".", "").strip()
    try:
        cedula = f"{int(ced):,}".replace(",", ".")
    except ValueError:
        cedula = ced
    telefono = parts[2]
    sede = parts[3]
    
    prod_name = parts[4] if len(parts) > 4 else "Combo 3 Pares + Gel Cherry"
    try:
        total_usd = float(parts[5]) if len(parts) > 5 else 28.99
    except ValueError:
        total_usd = 28.99
        
    guia_raw = parts[6] if len(parts) > 6 else "EN PREPARACIÓN"
    guia = f"{guia_raw} / TEALCA" if "TEALCA" not in guia_raw.upper() else guia_raw
    
    productos = [(prod_name, 1, f"${total_usd:.2f}")]
    
    context.user_data["cliente"] = cliente
    context.user_data["cedula"] = cedula
    context.user_data["telefono"] = telefono
    context.user_data["sede"] = sede
    context.user_data["productos"] = productos
    context.user_data["total_usd"] = total_usd
    context.user_data["guia"] = guia
    
    await update.message.reply_text("⏳ *Procesando nota rápida y generando imagen...*", parse_mode="Markdown")
    await render_and_send_nota(update, context)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚫 Operación cancelada.", parse_mode="Markdown")
    return ConversationHandler.END

def main():
    logger.info(f"Iniciando Bot de Telegram con token: {BOT_TOKEN[:10]}...")
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("nota", cmd_nota_start)],
        states={
            SELECT_PRODUCT: [CallbackQueryHandler(product_chosen, pattern="^prod_")],
            INPUT_CLIENTE: [MessageHandler(filters.TEXT & ~filters.COMMAND, client_name_received)],
            INPUT_CEDULA: [MessageHandler(filters.TEXT & ~filters.COMMAND, cedula_received)],
            INPUT_TELEFONO: [MessageHandler(filters.TEXT & ~filters.COMMAND, telefono_received)],
            INPUT_SEDE: [MessageHandler(filters.TEXT & ~filters.COMMAND, sede_received)],
            INPUT_GUIA: [MessageHandler(filters.TEXT & ~filters.COMMAND, guia_received)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(CommandHandler("tasa", cmd_tasa))
    app.add_handler(CommandHandler("recepcion", cmd_recepcion))
    app.add_handler(conv_handler)
    
    logger.info("Bot listo y escuchando en Telegram.")
    app.run_polling()

if __name__ == "__main__":
    main()
