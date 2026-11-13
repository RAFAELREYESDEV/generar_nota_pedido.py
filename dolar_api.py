"""
Utilidad oficial para consultar la tasa del Dólar Oficial en Venezuela (BCV)
Vía DolarAPI (https://ve.dolarapi.com/v1/dolares/oficial)
"""

import urllib.request
import json
from datetime import datetime

API_URL = "https://ve.dolarapi.com/v1/dolares/oficial"

def get_dolar_oficial():
    try:
        req = urllib.request.Request(API_URL, headers={"User-Agent": "EcommApp/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            promedio = data.get("promedio")
            fecha = data.get("fechaActualizacion")
            return {
                "tasa": promedio,
                "moneda": data.get("moneda", "USD"),
                "fecha": fecha,
                "status": "success"
            }
    except Exception as e:
        return {
            "tasa": 896.12,  # Fallback tasa Dropanas
            "status": "fallback",
            "error": str(e)
        }

def calc_conversion(monto_usd: float):
    info = get_dolar_oficial()
    tasa = info["tasa"]
    monto_bs = round(monto_usd * tasa, 2)
    return {
        "usd": monto_usd,
        "tasa": tasa,
        "bs": monto_bs,
        "fecha": info.get("fecha")
    }

if __name__ == "__main__":
    res = calc_conversion(25.0)
    print(f"Tasa Dólar Oficial BCV: {res['tasa']} Bs/USD")
    print(f"25 USD = {res['bs']:.2f} Bs")
