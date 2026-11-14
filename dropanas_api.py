"""
Módulo de Integración Oficial Dropanas API REST (v1)
Conecta el Bot de Telegram y el CRM con Dropanas para:
- Consultar pedidos y recaudos en tiempo real
- Rastrear estados de despacho (Generada, En camino, En oficina, Pagado)
- Sincronizar automáticamente el CRM local con la nube
"""

import os
import json
import logging
import urllib.request
import ssl

logger = logging.getLogger(__name__)

DROPANAS_API_KEY = os.getenv("DROPANAS_API_KEY", "")
BASE_URL = "https://app.dropanas.com/api/v1"
SSL_CTX = ssl.create_default_context()

def _hacer_peticion(endpoint, method="GET", body=None):
    if not DROPANAS_API_KEY:
        logger.error("DROPANAS_API_KEY no está configurada en las variables de entorno de Railway.")
        return {"error": True, "message": "DROPANAS_API_KEY no configurada."}

    url = f"{BASE_URL}{endpoint}"
    headers = {
        "Authorization": f"Bearer {DROPANAS_API_KEY}",
        "Accept": "application/json",
        "User-Agent": "EcommViking/1.0"
    }
    
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")
        
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, context=SSL_CTX) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw)
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8", errors="ignore")
        logger.error(f"Error HTTP Dropanas API ({e.code}) en {endpoint}: {err_msg}")
        return {"error": True, "code": e.code, "message": err_msg}
    except Exception as e:
        logger.error(f"Error inesperado Dropanas API en {endpoint}: {e}")
        return {"error": True, "message": str(e)}

def listar_ordenes_dropanas(per_page=50):
    """Obtiene el listado completo de pedidos desde Dropanas API."""
    res = _hacer_peticion(f"/ordenes?per_page={per_page}")
    if isinstance(res, dict) and "data" in res:
        return res.get("data", [])
    return []

def obtener_tracking_dropanas(orden_id):
    """Consulta el historial de tracking y estado actual de una orden."""
    res = _hacer_peticion(f"/ordenes/{orden_id}/tracking")
    if isinstance(res, dict) and "data" in res:
        return res.get("data", {})
    return {}

def obtener_resumen_dropanas():
    """Genera un resumen analítico agrupado por estado desde la API."""
    ordenes = listar_ordenes_dropanas(per_page=100)
    
    en_oficina = []
    en_camino = []
    pagados = []
    generadas = []
    cancelados = []
    
    total_usd = 0.0
    
    for o in ordenes:
        cli = o.get("cliente", {})
        nombre = f"{cli.get('nombre', '').strip()} {cli.get('apellido', '').strip()}".strip()
        tel = cli.get("telefono", "")
        tracking = o.get("tracking", {})
        status = tracking.get("status", "Pendiente")
        guia = tracking.get("numero_guia", f"DP{o.get('id')}")
        
        try:
            monto = float(o.get("precio_venta_usd", 0) or 0)
        except (ValueError, TypeError):
            monto = 0.0
            
        item = {
            "id": o.get("id"),
            "cliente": nombre,
            "telefono": tel,
            "guia": guia,
            "status": status,
            "monto": monto
        }
        
        if status.lower() in ["cancelado", "rechazado"]:
            cancelados.append(item)
            continue
            
        total_usd += monto
        
        if status.lower() == "en oficina":
            en_oficina.append(item)
        elif status.lower() == "en camino":
            en_camino.append(item)
        elif status.lower() in ["pagado", "entregado"]:
            pagados.append(item)
        elif status.lower() == "generada":
            generadas.append(item)
            
    return {
        "total_ordenes": len(ordenes),
        "total_usd": total_usd,
        "en_oficina": en_oficina,
        "en_camino": en_camino,
        "pagados": pagados,
        "generadas": generadas,
        "cancelados": cancelados
    }

def sincronizar_dropanas_crm(crm_path):
    """
    Sincroniza los estados oficiales de Dropanas API hacia el archivo crm_pedidos.json.
    """
    if not os.path.exists(crm_path):
        return 0
        
    try:
        with open(crm_path, "r", encoding="utf-8") as f:
            crm = json.load(f)
    except Exception as e:
        logger.error(f"Error leyendo CRM para sync: {e}")
        return 0
        
    ordenes_dropanas = listar_ordenes_dropanas(per_page=100)
    actualizados = 0
    
    for o in ordenes_dropanas:
        oid = str(o.get("id"))
        tracking = o.get("tracking", {})
        status_dp = tracking.get("status", "")
        guia_dp = tracking.get("numero_guia", "")
        
        cli = o.get("cliente", {})
        nom_cli = f"{cli.get('nombre', '')} {cli.get('apellido', '')}".lower()
        
        for p in crm:
            id_match = oid in p.get("id", "") or oid in p.get("codigo_dp", "")
            nom_match = nom_cli and nom_cli in p.get("cliente", "").lower()
            
            if id_match or nom_match:
                if status_dp == "En oficina":
                    p["estado"] = "5. En Taquilla para Retiro"
                elif status_dp == "En camino":
                    p["estado"] = "4. En Tránsito / Valija"
                elif status_dp in ["Pagado", "Entregado"]:
                    p["estado"] = "6. Entregado y Cobrado"
                elif status_dp == "Generada":
                    p["estado"] = "3. Montado en Dropanas"
                    
                if guia_dp and "DP" not in guia_dp:
                    p["guia_tealca"] = guia_dp
                    
                actualizados += 1
                break
                
    try:
        with open(crm_path, "w", encoding="utf-8") as f:
            json.dump(crm, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Error guardando CRM post-sync: {e}")
        
    return actualizados
