import os
import random
from PIL import Image, ImageDraw, ImageFont

FONTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")

def get_font_path(font_name):
    local_p = os.path.join(FONTS_DIR, font_name)
    if os.path.exists(local_p):
        return local_p
    win_p = os.path.join("C:/Windows/Fonts", font_name)
    if os.path.exists(win_p):
        return win_p
    return font_name

def generar_nota_pedido(
    cliente,
    cedula,
    telefono,
    ciudad_agencia,
    productos,
    total_usd,
    tasa_bcv,
    guia_tracking,
    out_path
):
    W, H = 800, 1100
    bg_color = (15, 23, 42)       # Slate 900
    card_bg = (30, 41, 59)        # Slate 800
    border_color = (51, 65, 85)   # Slate 700
    gold_color = (245, 158, 11)   # Amber 500
    text_white = (248, 250, 252)  # Slate 50
    text_muted = (148, 163, 184)  # Slate 400
    accent_green = (34, 197, 94)  # Emerald 500

    img = Image.new("RGB", (W, H), bg_color)
    draw = ImageDraw.Draw(img)

    f_bold = get_font_path("segoeuib.ttf")
    f_reg = get_font_path("segoeui.ttf")
    f_mono = get_font_path("consola.ttf")

    f_title = ImageFont.truetype(f_bold, 28)
    f_subtitle = ImageFont.truetype(f_reg, 16)
    f_h2 = ImageFont.truetype(f_bold, 18)
    f_body = ImageFont.truetype(f_reg, 17)
    f_body_b = ImageFont.truetype(f_bold, 17)
    f_small = ImageFont.truetype(f_reg, 14)
    f_total_usd = ImageFont.truetype(f_bold, 36)

    margin = 35
    draw.rounded_rectangle(
        [margin, margin, W - margin, H - margin],
        radius=20,
        fill=card_bg,
        outline=border_color,
        width=2
    )

    y = margin + 30
    draw.text((W / 2, y), "GUMMIES VIKING VENEZUELA", fill=gold_color, font=f_title, anchor="mt")
    y += 40
    draw.text((W / 2, y), "COMPROBANTE OFICIAL DE DESPACHO", fill=text_muted, font=f_subtitle, anchor="mt")
    y += 28
    draw.text((W / 2, y), "Envío Nacional Asegurado · Pago al Recibir en Taquilla", fill=accent_green, font=f_small, anchor="mt")
    y += 35

    draw.line([margin + 25, y, W - margin - 25, y], fill=border_color, width=1)
    y += 25

    draw.text((margin + 35, y), "DATOS DEL DESTINATARIO", fill=gold_color, font=f_h2)
    y += 32

    campos_cliente = [
        ("Cliente:", cliente),
        ("Cédula de Identidad:", f"V-{cedula}"),
        ("Teléfono:", telefono),
        ("Destino de Entrega:", f"Agencia Tealca - {ciudad_agencia}"),
        ("Estatus de Envío:", "En preparación de valija nacional"),
    ]

    for label, val in campos_cliente:
        draw.text((margin + 35, y), label, fill=text_muted, font=f_body)
        draw.text((margin + 230, y), val, fill=text_white, font=f_body_b)
        y += 28

    y += 15
    draw.line([margin + 25, y, W - margin - 25, y], fill=border_color, width=1)
    y += 25

    draw.text((margin + 35, y), "DETALLE DE LA ORDEN", fill=gold_color, font=f_h2)
    y += 35

    total_bs = total_usd * tasa_bcv

    for prod, cant, precio in productos:
        draw.text((margin + 35, y), f"• {prod}", fill=text_white, font=f_body_b)
        draw.text((margin + 530, y), f"x{cant}", fill=text_muted, font=f_body)
        draw.text((W - margin - 35, y), precio, fill=text_white, font=f_body_b, anchor="ra")
        y += 32

    draw.text((margin + 35, y), "• Costo de Flete Nacional Tealca", fill=text_muted, font=f_body)
    draw.text((W - margin - 35, y), "GRATIS ($0.00)", fill=accent_green, font=f_body_b, anchor="ra")
    y += 40

    draw.line([margin + 25, y, W - margin - 25, y], fill=border_color, width=1)
    y += 25

    total_box_top = y
    total_box_h = 135
    draw.rounded_rectangle(
        [margin + 25, total_box_top, W - margin - 25, total_box_top + total_box_h],
        radius=14,
        fill=(15, 23, 42),
        outline=gold_color,
        width=2
    )

    draw.text((margin + 50, total_box_top + 20), "TOTAL A CANCELAR AL RETIRAR:", fill=text_muted, font=f_small)
    draw.text((margin + 50, total_box_top + 45), f"${total_usd:.2f} USD", fill=gold_color, font=f_total_usd)
    draw.text((margin + 50, total_box_top + 95), "Cancelas en Bs a Tasa Oficial BCV del día al retirar", fill=accent_green, font=f_body_b)
    draw.text((W - margin - 50, total_box_top + 55), "PAGO EN TAQUILLA\nPago Móvil / Divisas", fill=text_muted, font=f_small, anchor="ra")

    y = total_box_top + total_box_h + 30

    draw.text((W / 2, y), f"CÓDIGO DE ORDEN / GUÍA: {guia_tracking}", fill=gold_color, font=f_h2, anchor="mt")
    y += 32
    draw.text((W / 2, y), "Rastreo oficial en vivo: https://tealca.com/rastrear-envio/", fill=text_muted, font=f_small, anchor="mt")
    y += 35

    barcode_x = margin + 120
    barcode_w = W - 2 * (margin + 120)
    barcode_y = y
    barcode_h = 42

    random.seed(42)
    bx = barcode_x
    while bx < barcode_x + barcode_w:
        bar_w = random.choice([2, 3, 5, 6])
        space_w = random.choice([2, 3, 4])
        draw.rectangle([bx, barcode_y, bx + bar_w, barcode_y + barcode_h], fill=text_muted)
        bx += bar_w + space_w

    y += barcode_h + 10
    draw.text((W / 2, y), f"* {guia_tracking} *  PAQUETE SELLADO 100% CONFIDENCIAL", fill=text_muted, font=f_small, anchor="mt")

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    img.save(out_path, quality=95)
    return out_path
