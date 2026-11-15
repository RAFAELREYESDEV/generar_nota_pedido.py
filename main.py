"""
Bot de Telegram para Gestión Integral de Pedidos, Envíos Tealca y Finanzas 24/7
Gummies Viking & E-Commerce Venezuela (Railway / Cloud Deployment)
"""

import os
import sys
import json
import logging
import difflib
import html
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
from dropanas_api import obtener_resumen_dropanas, sincronizar_dropanas_crm

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuración del Bot (Prioriza variable de entorno en Railway, fallback automático para prevenir crash)
FALLBACK_BOT_TOKEN = "9058473536:AAHM284rhV8Js85QLdyzLPwpXC3IiKAhjFk"
BOT_TOKEN = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip() or FALLBACK_BOT_TOKEN
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "generated_notes")
RECEPTION_DIR = os.path.join(BASE_DIR, "reception_images")
CRM_FILE = os.path.join(BASE_DIR, "crm_pedidos.json")
TEALCA_FILE = os.path.join(BASE_DIR, "tealca_all_offices.json")

os.makedirs(OUTPUT_DIR, exist_ok=True)

# Estados de la conversación para /nota interactiva
SELECT_PRODUCT, INPUT_CLIENTE, INPUT_CEDULA, INPUT_TELEFONO, INPUT_SEDE, INPUT_GUIA = range(6)

# Catálogo predefinido de combos
PRODUCT_PRESETS = {
    "combo3": {
        "nombre": "Combo 3 Pares (6 Gomitas Viking)",
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
    },
    "wart_remover": {
        "nombre": "Wart Remover Tónico 30ml",
        "items": [("Wart Remover Tónico 30ml", 1, "$29.99")],
        "total": 29.99
    },
    "mucina_caracol": {
        "nombre": "Crema Mucina de Caracol 92%",
        "items": [("Crema Facial Mucina Caracol 92%", 1, "$26.99")],
        "total": 26.99
    }
}

# --- FUNCIONES DE BASE DE DATOS Y TEALCA ---
def cargar_crm():
    if os.path.exists(CRM_FILE):
        try:
            with open(CRM_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error cargando CRM: {e}")
    return []

def guardar_crm(pedidos):
    try:
        with open(CRM_FILE, "w", encoding="utf-8") as f:
            json.dump(pedidos, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Error guardando CRM: {e}")

def buscar_sede_tealca(query):
    """Busca en el directorio oficial de 134 sedes Tealca la coincidencia más cercana."""
    if not os.path.exists(TEALCA_FILE):
        return []
    
    try:
        with open(TEALCA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            offices = data.get("data", [])
    except Exception as e:
        logger.error(f"Error leyendo Tealca DB: {e}")
        return []
        
    query_clean = query.lower().strip()
    coincidencias = []
    
    for o in offices:
        ciudad = o.get("city", "").lower()
        estado = o.get("state", "").lower()
        nombre = o.get("post", {}).get("name", "").lower()
        codigo = str(o.get("fields", {}).get("code", "")).lower()
        direccion = o.get("fields", {}).get("address", "").lower()
        
        texto_busqueda = f"{ciudad} {estado} {nombre} {codigo} {direccion}"
        
        if query_clean in texto_busqueda:
            coincidencias.append(o)
            
    # Si no hay coincidencia exacta de subcadena, usar coincidencia aproximada
    if not coincidencias:
        nombres = [f"{o.get('city','')} {o.get('state','')} {o.get('post',{}).get('name','')}".lower() for o in offices]
        matches = difflib.get_close_matches(query_clean, nombres, n=5, cutoff=0.35)
        for m in matches:
            idx = nombres.index(m)
            coincidencias.append(offices[idx])
            
    return coincidencias[:5]

def formatear_telefono_wa(telefono):
    clean_tel = "".join(c for c in str(telefono) if c.isdigit())
    if clean_tel.startswith("0"):
        clean_tel = "58" + clean_tel[1:]
    elif not clean_tel.startswith("58") and len(clean_tel) == 10:
        clean_tel = "58" + clean_tel
    return clean_tel

# --- COMANDOS DEL BOT ---

async def cmd_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "👑 *CENTRAL OPERATIVA 24/7 - GUMMIES VIKING VENEZUELA*\n"
        "Comandos integrados para gestión de pedidos, Tealca y finanzas:\n\n"
        "📋 *COMANDOS DISPONIBLES:*\n\n"
        "🔹 `/info`\n"
        "Muestra esta guía completa con instrucciones y ejemplos.\n\n"
        "🔹 `/sede <ciudad o estado>`\n"
        "Busca en el directorio de las *134 sedes oficiales Tealca*. Te da código exacto, nombre, dirección y link a Google Maps. ¡Evita errores de destino!\n"
        "👉 *Ejemplo:* `/sede villa del rosario` o `/sede maracaibo`\n\n"
        "🔹 `/nota`\n"
        "Crea el *Comprobante Oficial de Despacho* en alta resolución con tasa BCV del día, lo registra en sistema y te da el mensaje listo para WhatsApp.\n"
        "👉 *Modo Interactivo:* Escribe `/nota` solo y el bot te va preguntando con botones.\n"
        "👉 *Modo Rápido en 1 línea:* `/nota Nombre | Cédula | Teléfono | Sede | Combo | Total $ | Código DP`\n\n"
        "🔹 `/guia <cliente o DP> | <guía Tealca>`\n"
        "Asigna la guía de valija nacional al pedido, actualiza su estado y genera el mensaje de rastreo para WhatsApp con link directo al chat del cliente.\n"
        "👉 *Ejemplo:* `/guia Pedro Medina | 85117354` o `/guia DP74634 | 85117354`\n\n"
        "🔹 `/taquilla <cliente o DP>`\n"
        "Genera la alerta de llegada a taquilla Tealca con el monto exacto en bolívares (tasa BCV) y recordatorio de cédula para que el cliente retire de inmediato.\n"
        "👉 *Ejemplo:* `/taquilla Pedro Medina`\n\n"
        "🔹 `/dropanas`\n"
        "Consulta en tiempo real la API oficial de Dropanas: pedidos en taquilla, en valija y entregados con un solo clic.\n\n"
        "🔹 `/sync`\n"
        "Sincroniza automáticamente los estados y guías de Dropanas API con tu base de datos local.\n\n"
        "🔹 `/dashboard`\n"
        "Muestra el resumen financiero de pedidos (taquilla, valija, entregados) y *días de oxígeno de Meta Ads*.\n\n"
        "🔹 `/tasa` o `/bcv`\n"
        "Consulta la tasa oficial del día del Banco Central de Venezuela en tiempo real.\n\n"
        "🔹 `/recepcion`\n"
        "Envía las 2 opciones de fotos de entrada a bodega para enviar por WhatsApp a clientes que piden fotos reales.\n\n"
        "🔹 `/cancel`\n"
        "Cancela cualquier flujo interactivo en curso."
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def cmd_sede(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args).strip() if context.args else ""
    if not query:
        await update.message.reply_text(
            "🏢 *Buscador Oficial de Agencias Tealca*\n\n"
            "Por favor indica la ciudad, estado o código que deseas buscar.\n\n"
            "👉 *Ejemplos:*\n"
            "• `/sede villa del rosario`\n"
            "• `/sede maracaibo`\n"
            "• `/sede punto fijo`\n"
            "• `/sede coro`",
            parse_mode="Markdown"
        )
        return

    coincidencias = buscar_sede_tealca(query)
    if not coincidencias:
        await update.message.reply_text(
            f"❌ No se encontró ninguna agencia Tealca para *'{query}'*.\n"
            f"Prueba buscando por el estado o por la ciudad principal más cercana.",
            parse_mode="Markdown"
        )
        return

    resultado = f"🏢 *Agencias Tealca encontradas para '{query}':* ({len(coincidencias)})\n\n"
    for i, o in enumerate(coincidencias, start=1):
        ciudad = html.unescape(o.get("city", "N/D"))
        estado = html.unescape(o.get("state", "N/D"))
        nombre = html.unescape(o.get("post", {}).get("name", "N/D"))
        fields = o.get("fields", {})
        codigo = fields.get("code", "S/C")
        direccion = html.unescape(fields.get("address", "Consultar en agencia"))
        maps_url = fields.get("url_google_map", "")

        resultado += f"📍 *{i}. {ciudad} ({estado})*\n"
        resultado += f"🏢 *Agencia:* {nombre}\n"
        resultado += f"🔢 *Código Tealca:* `{codigo}`\n"
        resultado += f"📌 *Dirección:* {direccion}\n"
        if maps_url:
            resultado += f"🗺️ [Ver en Google Maps]({maps_url})\n"
        resultado += "\n"

    resultado += "💡 *Copia el código o nombre para usarlo en la Nota de Pedido.*"
    await update.message.reply_text(resultado, parse_mode="Markdown", disable_web_page_preview=True)

async def cmd_guia(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw_args = " ".join(context.args).strip() if context.args else ""
    if not raw_args:
        await update.message.reply_text(
            "📦 *Asignar Número de Guía Tealca*\n\n"
            "Usa el formato:\n"
            "`/guia <cliente o código DP> | <número_guía>`\n\n"
            "👉 *Ejemplo:* `/guia Pedro Medina | 85117354`\n"
            "👉 *Ejemplo:* `/guia DP74634 | 85117354`",
            parse_mode="Markdown"
        )
        return

    parts = [p.strip() for p in raw_args.split("|")] if "|" in raw_args else raw_args.split(None, 1)
    if len(parts) < 2:
        await update.message.reply_text("❌ Formato incorrecto. Usa: `/guia Cliente | NúmeroGuía`", parse_mode="Markdown")
        return

    cliente_query = parts[0]
    numero_guia = parts[1]

    crm = cargar_crm()
    pedido = None
    for p in crm:
        if cliente_query.lower() in p["cliente"].lower() or cliente_query.upper() == p.get("codigo_dp", "").upper():
            pedido = p
            break

    info = get_dolar_oficial()
    tasa_actual = info.get("tasa", 904.48)

    if pedido:
        pedido["guia_tealca"] = numero_guia
        pedido["estado"] = "4. En Tránsito / Valija"
        guardar_crm(crm)

        nombre_cliente = pedido["cliente"]
        telefono = pedido["telefono"]
        sede = pedido["sede_tealca_asignada"]
        total_usd = pedido["total_usd"]
        total_bs = total_usd * tasa_actual
    else:
        # Fallback genérico si no está en CRM
        nombre_cliente = cliente_query
        telefono = ""
        sede = "Agencia Tealca Asignada"
        total_usd = 28.99
        total_bs = total_usd * tasa_actual

    primer_nombre = nombre_cliente.split()[0]
    wa_clean = formatear_telefono_wa(telefono) if telefono else ""
    wa_link = f"https://wa.me/{wa_clean}" if wa_clean else None

    wa_msg = (
        f"¡Buenas tardes, {primer_nombre}! Tu pedido ya va en tránsito en valija nacional Tealca. 🚚💨\n\n"
        f"📦 *Número de Guía:* `{numero_guia}`\n"
        f"📍 *Destino:* {sede}\n"
        f"💵 *Monto a cancelar al retirar:* ${total_usd:.2f} USD (Bs {total_bs:,.2f})\n"
        f"🔎 *Rastreo en vivo:* https://www.tealca.com/rastreo-de-envios/\n\n"
        f"Te avisaremos por acá en cuanto esté disponible en taquilla para tu retiro. ¡Gracias por tu compra! 🤝"
    )

    respuesta = (
        f"✅ *Guía Tealca Asignada:* `{numero_guia}`\n"
        f"👤 *Cliente:* {nombre_cliente}\n\n"
        f"💬 *Mensaje listo para WhatsApp:*\n"
        f"```text\n{wa_msg}\n```\n"
    )
    if wa_link:
        respuesta += f"📲 [Abrir Chat de WhatsApp con {primer_nombre}]({wa_link})"

    await update.message.reply_text(respuesta, parse_mode="Markdown", disable_web_page_preview=True)

async def cmd_taquilla(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cliente_query = " ".join(context.args).strip() if context.args else ""
    if not cliente_query:
        await update.message.reply_text(
            "🏢 *Aviso de Paquete en Taquilla Tealca*\n\n"
            "Usa el formato:\n"
            "`/taquilla <cliente o código DP>`\n\n"
            "👉 *Ejemplo:* `/taquilla Pedro Medina`\n"
            "👉 *Ejemplo:* `/taquilla 85093987`",
            parse_mode="Markdown"
        )
        return

    crm = cargar_crm()
    pedido = None
    for p in crm:
        if (cliente_query.lower() in p["cliente"].lower() or 
            cliente_query.upper() == p.get("codigo_dp", "").upper() or
            cliente_query.strip() == str(p.get("guia_tealca", "")).strip()):
            pedido = p
            break

    info = get_dolar_oficial()
    tasa_actual = info.get("tasa", 904.48)

    if pedido:
        pedido["estado"] = "5. En Taquilla para Retiro"
        guardar_crm(crm)

        nombre_cliente = pedido["cliente"]
        telefono = pedido["telefono"]
        sede = pedido["sede_tealca_asignada"]
        guia = pedido.get("guia_tealca", "Consultar")
        total_usd = pedido["total_usd"]
        total_bs = total_usd * tasa_actual
    else:
        nombre_cliente = cliente_query
        telefono = ""
        sede = "Agencia Tealca"
        guia = "En Taquilla"
        total_usd = 28.99
        total_bs = total_usd * tasa_actual

    primer_nombre = nombre_cliente.split()[0]
    wa_clean = formatear_telefono_wa(telefono) if telefono else ""
    wa_link = f"https://wa.me/{wa_clean}" if wa_clean else None

    wa_msg = (
        f"¡Hola, {primer_nombre}! Te notifico que tu paquete *ya se encuentra en taquilla Tealca listo para retiro*. 🏢🎉\n\n"
        f"📍 *Sede:* {sede}\n"
        f"📦 *Guía:* `{guia}`\n"
        f"🪪 Recuerda llevar tu cédula laminada.\n"
        f"💵 *Monto a cancelar:* Bs {total_bs:,.2f} (Efectivo o Pago Móvil directo en taquilla).\n\n"
        f"¡Esperamos que lo disfrutes al máximo! Quedamos a tu orden. 🤝"
    )

    respuesta = (
        f"🏢 *Aviso de Taquilla Generado*\n"
        f"👤 *Cliente:* {nombre_cliente}\n\n"
        f"💬 *Mensaje listo para WhatsApp:*\n"
        f"```text\n{wa_msg}\n```\n"
    )
    if wa_link:
        respuesta += f"📲 [Abrir Chat de WhatsApp con {primer_nombre}]({wa_link})"

    await update.message.reply_text(respuesta, parse_mode="Markdown", disable_web_page_preview=True)

async def cmd_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    crm = cargar_crm()
    total_pedidos = len(crm)
    entregados = [p for p in crm if "Entregado" in p["estado"]]
    en_taquilla = [p for p in crm if "Taquilla" in p["estado"]]
    en_transito = [p for p in crm if "Tránsito" in p["estado"] or "Montado" in p["estado"]]

    cobrado_usd = sum(p.get("total_usd", 0) for p in entregados)
    taquilla_usd = sum(p.get("total_usd", 0) for p in en_taquilla)
    transito_usd = sum(p.get("total_usd", 0) for p in en_transito)
    total_usd = sum(p.get("total_usd", 0) for p in crm)

    # Parámetros de Meta Ads
    gasto_meta = 76.91
    presupuesto_diario = 5.0
    umbral_meta = 58.0
    gasto_en_ciclo = gasto_meta % umbral_meta
    oxigeno_dolares = umbral_meta - gasto_en_ciclo
    dias_oxigeno = oxigeno_dolares / presupuesto_diario if presupuesto_diario > 0 else 99

    msg = (
        "📊 *DASHBOARD OPERATIVO Y FINANCIERO*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📦 *Total Pedidos en Sistema:* `{total_pedidos}`\n"
        f"🟢 *Entregados y Cobrados:* `{len(entregados)}` (${cobrado_usd:,.2f} USD)\n"
        f"🟡 *En Taquilla para Retiro:* `{len(en_taquilla)}` (${taquilla_usd:,.2f} USD)\n"
        f"🚚 *En Valija / Tránsito:* `{len(en_transito)}` (${transito_usd:,.2f} USD)\n"
        f"💰 *Facturación Bruta Acumulada:* `${total_usd:,.2f} USD`\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🛡️ *CONTROL DE FLUJO META ADS:*\n"
        f"💳 Gasto Acumulado: `${gasto_meta:.2f} USD`\n"
        f"⚙️ Presupuesto Diario Actual: `${presupuesto_diario:.2f}/día`\n"
        f"🛑 Umbral de Cobro Meta: `${umbral_meta:.2f} USD`\n"
        f"🛡️ *Días de Oxígeno Restantes:* `~{dias_oxigeno:.1f} días`\n"
        "*(Margen de tiempo seguro antes del próximo cobro de tarjeta mientras Dropanas libera fondos)*"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def cmd_dropanas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔄 *Consultando API oficial de Dropanas en tiempo real...*", parse_mode="Markdown")
    res = obtener_resumen_dropanas()
    if not res or res.get("total_ordenes", 0) == 0:
        await update.message.reply_text("⚠️ No se pudieron obtener órdenes de Dropanas. Verifica la conexión o API Key.", parse_mode="Markdown")
        return

    msg = (
        "📦 *ESTADO EN VIVO DROPANAS (API REST)*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    )

    en_oficina = res.get("en_oficina", [])
    msg += f"🏢 *EN TAQUILLA / LISTOS PARA COBRAR ({len(en_oficina)}):*\n"
    for o in en_oficina:
        cli = o["cliente"] or "Cliente"
        msg += f"  • {cli} (`{o['guia']}`)\n"
    msg += "\n"

    en_camino = res.get("en_camino", [])
    msg += f"🚚 *EN VALIJA / CAMINO ({len(en_camino)}):*\n"
    for o in en_camino:
        cli = o["cliente"] or "Cliente"
        msg += f"  • {cli} (`{o['guia']}`)\n"
    msg += "\n"

    generadas = res.get("generadas", [])
    if generadas:
        msg += f"📦 *EN PREPARACIÓN / GENERADAS ({len(generadas)}):*\n"
        for o in generadas:
            cli = o["cliente"] or "Cliente"
            msg += f"  • {cli} (`{o['guia']}`)\n"
        msg += "\n"

    pagados = res.get("pagados", [])
    msg += f"🟢 *ENTREGADOS / LIQUIDADOS ({len(pagados)}):*\n"
    for o in pagados:
        cli = o["cliente"] or "Cliente"
        msg += f"  • {cli} (`{o['guia']}`)\n"
    msg += "\n"

    msg += "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"📊 *Total Órdenes Registradas:* `{res.get('total_ordenes')}` pedidos\n"
    msg += f"💰 *Facturación Bruta:* `${res.get('total_usd', 0):,.2f} USD`\n\n"
    msg += "💡 *Usa `/sync` para actualizar automáticamente tu base de datos.*"

    await update.message.reply_text(msg, parse_mode="Markdown")

async def cmd_sync(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔄 *Sincronizando pedidos desde Dropanas API hacia la base de datos...*", parse_mode="Markdown")
    n = sincronizar_dropanas_crm(CRM_FILE)
    await update.message.reply_text(
        f"✅ *¡Sincronización Exitosa!*\n"
        f"Se sincronizaron `{n}` pedidos en tu CRM con los estados y guías oficiales de Dropanas.",
        parse_mode="Markdown"
    )

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

    await update.message.reply_text("📦 *Enviando fotos oficiales de recepción para WhatsApp:*", parse_mode="Markdown")

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

# --- FLUJO /nota INTERACTIVO ---

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
            InlineKeyboardButton("✨ Wart Remover ($29.99)", callback_data="prod_wart_remover"),
        ],
        [
            InlineKeyboardButton("🐌 Mucina Caracol ($26.99)", callback_data="prod_mucina_caracol"),
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
        "🏢 *Paso 5:* Envía la *Ciudad y Sede Tealca* donde retira (ej: `Punto Fijo Centro` o `Villa del Rosario`):",
        parse_mode="Markdown"
    )
    return INPUT_SEDE

async def sede_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sede_input = update.message.text.strip()
    
    # Auto-matching con base de datos Tealca
    matches = buscar_sede_tealca(sede_input)
    if matches:
        mejor = matches[0]
        cod = mejor.get("fields", {}).get("code", "")
        sede_resolvida = f"{mejor.get('city', sede_input)} (Sede {cod})" if cod else sede_input
    else:
        sede_resolvida = sede_input

    context.user_data["sede"] = sede_resolvida

    await update.message.reply_text(
        f"✅ Destino asignado: *Tealca {sede_resolvida}*\n\n"
        "🔢 *Paso 6:* Envía el código de orden Dropanas (ej: `DP74634` o guía `85110297`).\n"
        "*(Si aún no lo montas en Dropanas, escribe `0` para poner EN PREPARACIÓN)*:",
        parse_mode="Markdown"
    )
    return INPUT_GUIA

async def guia_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    guia_raw = update.message.text.strip().upper()
    if guia_raw in ["0", "NO", "PENDIENTE", "NONE"]:
        guia_tracking = "EN PREPARACIÓN / TEALCA"
        cod_dp = ""
    elif "TEALCA" not in guia_raw:
        guia_tracking = f"{guia_raw} / TEALCA"
        cod_dp = guia_raw
    else:
        guia_tracking = guia_raw
        cod_dp = guia_raw

    context.user_data["guia"] = guia_tracking
    context.user_data["codigo_dp"] = cod_dp

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
    codigo_dp = u.get("codigo_dp", "")

    info = get_dolar_oficial()
    tasa = info.get("tasa", 904.48)
    total_bs = total_usd * tasa

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

    # Registrar o actualizar en CRM
    crm = cargar_crm()
    pedido_existente = next((p for p in crm if p.get("cliente", "").strip().lower() == cliente.strip().lower() or (p.get("codigo_dropanas") and p.get("codigo_dropanas") == codigo_dp)), None)
    if pedido_existente:
        pedido_existente["total_usd"] = total_usd
        pedido_existente["total_bs"] = total_bs
        pedido_existente["tasa_bcv"] = tasa
        pedido_existente["cedula"] = f"V-{cedula}"
        pedido_existente["telefono"] = telefono
        pedido_existente["sede_tealca_asignada"] = f"Tealca {sede}"
        if productos:
            pedido_existente["combo"] = productos[0][0]
        if codigo_dp:
            pedido_existente["codigo_dropanas"] = codigo_dp
            pedido_existente["codigo_dp"] = codigo_dp
        if guia and "EN PREPARACIÓN" not in guia:
            pedido_existente["guia_tealca"] = guia.replace(" / TEALCA", "").strip()
        pedido_existente["comprobante_img"] = out_path
        guardar_crm(crm)
    else:
        nuevo_registro = {
            "id": f"ORD-{int(datetime.now().timestamp())}",
            "fecha": datetime.now().strftime("%d-%m-%Y %I:%M %p"),
            "cliente": cliente,
            "cedula": f"V-{cedula}",
            "telefono": telefono,
            "ubicacion_solicitada": sede,
            "sede_tealca_asignada": f"Tealca {sede}",
            "codigo_sede": "",
            "combo": productos[0][0] if productos else "Gummies Viking",
            "total_usd": total_usd,
            "total_bs": total_bs,
            "tasa_bcv": tasa,
            "codigo_dp": codigo_dp,
            "codigo_dropanas": codigo_dp,
            "guia_tealca": guia.replace(" / TEALCA", "").strip() if "EN PREPARACIÓN" not in guia else "",
            "estado": "3. Montado en Dropanas",
            "comprobante_img": out_path
        }
        crm.append(nuevo_registro)
        guardar_crm(crm)

    with open(out_path, "rb") as photo_file:
        await update.message.reply_photo(
            photo=photo_file,
            caption=(
                f"✅ *Comprobante Generado con Éxito*\n\n"
                f"👤 *Cliente:* {cliente}\n"
                f"🪪 *Cédula:* V-{cedula}\n"
                f"🏢 *Destino:* Tealca {sede}\n"
                f"💵 *Total:* ${total_usd:.2f} USD (Bs {total_bs:,.2f})\n"
                f"📦 *Guía:* `{guia}`"
            ),
            parse_mode="Markdown"
        )

    clean_tel = formatear_telefono_wa(telefono)
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
            "👉 *Ejemplo:*\n"
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
    sede_input = parts[3]

    matches = buscar_sede_tealca(sede_input)
    if matches:
        mejor = matches[0]
        cod = mejor.get("fields", {}).get("code", "")
        sede = f"{mejor.get('city', sede_input)} (Sede {cod})" if cod else sede_input
    else:
        sede = sede_input

    prod_name = parts[4] if len(parts) > 4 else "Combo 3 Pares + Gel Cherry"
    
    # Limpieza ultra robusta de total_usd (soporta '$49', '$49.13', '49,13', '$ 49.13', '49 USD')
    raw_usd = parts[5].replace("$", "").replace("USD", "").replace("usd", "").replace(",", ".").strip() if len(parts) > 5 else ""
    try:
        total_usd = float(raw_usd) if raw_usd else 28.99
    except ValueError:
        import re
        m = re.search(r"(\d+(?:\.\d+)?)", raw_usd)
        total_usd = float(m.group(1)) if m else 28.99

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
    context.user_data["codigo_dp"] = guia_raw if guia_raw != "EN PREPARACIÓN" else ""

    await update.message.reply_text("⏳ *Procesando nota rápida y generando imagen...*", parse_mode="Markdown")
    await render_and_send_nota(update, context)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚫 Operación cancelada.", parse_mode="Markdown")
    return ConversationHandler.END

def main():
    if not BOT_TOKEN:
        logger.error("FATAL: TELEGRAM_BOT_TOKEN no está configurada en las variables de entorno de Railway.")
        sys.exit(1)
    logger.info("Iniciando Bot de Telegram desde variables de entorno de Railway...")
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

    # Handlers de comandos principales
    app.add_handler(CommandHandler("start", cmd_info))
    app.add_handler(CommandHandler("help", cmd_info))
    app.add_handler(CommandHandler("info", cmd_info))
    app.add_handler(CommandHandler("sede", cmd_sede))
    app.add_handler(CommandHandler("guia", cmd_guia))
    app.add_handler(CommandHandler("taquilla", cmd_taquilla))
    app.add_handler(CommandHandler("dropanas", cmd_dropanas))
    app.add_handler(CommandHandler("sync", cmd_sync))
    app.add_handler(CommandHandler("dashboard", cmd_dashboard))
    app.add_handler(CommandHandler("tasa", cmd_tasa))
    app.add_handler(CommandHandler("bcv", cmd_tasa))
    app.add_handler(CommandHandler("recepcion", cmd_recepcion))
    app.add_handler(conv_handler)

    logger.info("Bot listo y escuchando en Telegram.")
    app.run_polling()

if __name__ == "__main__":
    main()
