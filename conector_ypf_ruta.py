"""Conector Customer API Location World / YPF Ruta (autenticación de 3 pasos)."""

from __future__ import annotations

import json
import os
import re
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests
from dotenv import load_dotenv

from database import SessionLocal, engine, Base, ensure_columns
from models import Unidad, RegistroTelemetria

load_dotenv(override=True)

AUTH0_URL = "https://location-world.auth0.com/oauth/token"
YPF_TOKEN_URL = os.getenv("YPF_TOKEN_URL", "https://mag.ypf.com/auth/oauth/v2/token")
API_BASE = os.getenv("YPF_API_BASE", "https://customer-api.location-world.com")
API_DOMAIN = os.getenv("YPF_API_DOMAIN", "fleet")
API_SUBDOMAIN = os.getenv("YPF_API_SUBDOMAIN", "ypfruta")
AUDIENCE = os.getenv("LOCATIONWORLD_AUDIENCE", "https://customer-api.location-world.com")
TIMEOUT = (10, 90)
TOKEN_TTL_SEGUNDOS = 86400
RATE_LIMIT_MAX = 2
RATE_LIMIT_VENTANA = 1.0

REQUIRED_LW = ("LOCATIONWORLD_CLIENT_ID", "LOCATIONWORLD_CLIENT_SECRET")
REQUIRED_SESION = (
    "YPF_CLIENT_ID",
    "YPF_CLIENT_SECRET",
    "YPF_SCOPE",
    "YPF_USERNAME",
    "YPF_PASSWORD",
)
REQUIRED_ENV = REQUIRED_LW + REQUIRED_SESION

_rate_calls: deque[float] = deque()
_session_cache: dict[str, Any] = {}


def cache_path() -> Path:
    return Path(os.getenv("YPF_TOKEN_CACHE", str(Path(__file__).resolve().parent / ".ypf_token_cache.json")))


def normalizar_patente(valor: str | None) -> str:
    if not valor:
        return ""
    return re.sub(r"[^A-Z0-9]", "", str(valor).upper())


def credenciales_faltantes(grupo: tuple[str, ...] = REQUIRED_ENV) -> list[str]:
    return [nombre for nombre in grupo if not os.getenv(nombre, "").strip()]


def _leer_cache() -> dict[str, Any] | None:
    ruta = cache_path()
    if not ruta.exists():
        return None
    try:
        data = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _guardar_cache(data: dict[str, Any]) -> None:
    ruta = cache_path()
    ruta.write_text(json.dumps(data, indent=2), encoding="utf-8")


def token_lw_vigente(cache: dict[str, Any] | None = None, ahora: float | None = None) -> bool:
    data = cache if cache is not None else _leer_cache()
    if not data or not data.get("access_token"):
        return False
    instante = time.time() if ahora is None else ahora
    return float(data.get("expira_en") or 0) > instante + 60


def estado_configuracion() -> dict[str, Any]:
    faltan_lw = credenciales_faltantes(REQUIRED_LW)
    faltan_sesion = credenciales_faltantes(REQUIRED_SESION)
    cache = _leer_cache()
    sesion_en_cache = bool(cache and cache.get("user_id") and cache.get("client_id") and token_lw_vigente(cache))
    configurado = len(faltan_lw) == 0 and (len(faltan_sesion) == 0 or sesion_en_cache)
    return {
        "configurado": configurado,
        "token_lw_configurado": len(faltan_lw) == 0,
        "sesion_configurada": len(faltan_sesion) == 0 or sesion_en_cache,
        "faltantes": faltan_lw + ([] if sesion_en_cache else faltan_sesion),
        "token_en_cache": token_lw_vigente(cache),
        "token_expira_en": cache.get("expira_en") if cache else None,
        "api_base": API_BASE,
        "token_url": YPF_TOKEN_URL,
        "dominio": API_DOMAIN,
        "subdominio": API_SUBDOMAIN,
        "lineamiento_token": "No generar más de un token Auth0 cada 24 horas",
        "rate_limit": f"{RATE_LIMIT_MAX} requests / {int(RATE_LIMIT_VENTANA)}s",
    }


def _respetar_rate_limit() -> None:
    """Customer API: máximo 2 requests por segundo."""
    ahora = time.monotonic()
    while _rate_calls and ahora - _rate_calls[0] >= RATE_LIMIT_VENTANA:
        _rate_calls.popleft()
    if len(_rate_calls) >= RATE_LIMIT_MAX:
        espera = RATE_LIMIT_VENTANA - (ahora - _rate_calls[0]) + 0.05
        if espera > 0:
            time.sleep(espera)
        ahora = time.monotonic()
        while _rate_calls and ahora - _rate_calls[0] >= RATE_LIMIT_VENTANA:
            _rate_calls.popleft()
    _rate_calls.append(time.monotonic())


def _request(method: str, url: str, **kwargs) -> requests.Response:
    kwargs.setdefault("timeout", TIMEOUT)
    intentos = 3 if method.upper() == "GET" else 1
    ultima = None
    for intento in range(intentos):
        _respetar_rate_limit()
        respuesta = requests.request(method, url, **kwargs)
        ultima = respuesta
        if respuesta.status_code in (502, 503, 504) and intento < intentos - 1:
            time.sleep(5 * (intento + 1))
            continue
        if respuesta.status_code >= 400:
            detalle = (respuesta.text or "")[:400]
            raise RuntimeError(f"YPF Ruta {method} {url} → HTTP {respuesta.status_code}: {detalle}")
        return respuesta
    detalle = (ultima.text if ultima is not None else "")[:400]
    raise RuntimeError(f"YPF Ruta {method} {url} → sin respuesta válida: {detalle}")


def _enc(valor: str) -> str:
    return quote(valor, safe="")


def obtener_token_location_world() -> str:
    """Reutiliza el Bearer 24 h. Auth0 no debe emitir más de un token por día."""
    ahora = time.time()
    cache = _leer_cache()
    if token_lw_vigente(cache, ahora):
        return str(cache["access_token"])

    if cache and cache.get("obtenido_en") and (ahora - float(cache["obtenido_en"])) < TOKEN_TTL_SEGUNDOS - 60:
        raise RuntimeError(
            "Hay un token Auth0 pedido en las últimas 24 h y ya no está vigente. "
            "Location World pide no generar más de uno por día; esperá a que se cumpla el plazo."
        )

    faltan = credenciales_faltantes(REQUIRED_LW)
    if faltan:
        raise RuntimeError("Faltan credenciales Location World en .env: " + ", ".join(faltan))

    lw = _request(
        "POST",
        AUTH0_URL,
        headers={"Content-Type": "application/json"},
        json={
            "client_id": os.environ["LOCATIONWORLD_CLIENT_ID"].strip(),
            "client_secret": os.environ["LOCATIONWORLD_CLIENT_SECRET"].strip(),
            "audience": AUDIENCE,
            "grant_type": "client_credentials",
        },
    ).json()
    token = lw.get("access_token")
    if not token:
        raise RuntimeError("Auth0 no devolvió access_token")
    ttl = int(lw.get("expires_in") or TOKEN_TTL_SEGUNDOS)
    nuevo = {
        "access_token": token,
        "token_type": lw.get("token_type") or "Bearer",
        "obtenido_en": ahora,
        "expira_en": ahora + ttl,
        "user_id": (cache or {}).get("user_id"),
        "client_id": (cache or {}).get("client_id"),
    }
    _guardar_cache(nuevo)
    return token


def autenticar() -> dict[str, Any]:
    """Token Auth0 (cache 24 h) + session 3party-jwt si hace falta."""
    ahora = time.time()
    memoria = _session_cache.get("data")
    if memoria and memoria.get("expira_en", 0) > ahora + 60 and memoria.get("user_id") and memoria.get("client_id"):
        return memoria

    bearer = obtener_token_location_world()
    cache = _leer_cache() or {}
    if cache.get("user_id") and cache.get("client_id") and token_lw_vigente(cache, ahora):
        data = {
            "bearer": bearer,
            "client_id": cache["client_id"],
            "user_id": cache["user_id"],
            "expira_en": float(cache.get("expira_en") or ahora + 3600),
        }
        _session_cache["data"] = data
        return data

    faltan = credenciales_faltantes(REQUIRED_SESION)
    if faltan:
        raise RuntimeError(
            "El token Location World está listo. Faltan credenciales MAG YPF para abrir la session: "
            + ", ".join(faltan)
        )

    ypf = _request(
        "POST",
        YPF_TOKEN_URL,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "grant_type": "password",
            "client_id": os.environ["YPF_CLIENT_ID"].strip(),
            "client_secret": os.environ["YPF_CLIENT_SECRET"].strip(),
            "scope": os.environ["YPF_SCOPE"].strip(),
            "username": os.environ["YPF_USERNAME"].strip(),
            "password": os.environ["YPF_PASSWORD"].strip(),
        },
    ).json()

    session = _request(
        "POST",
        f"{API_BASE}/v1/{API_DOMAIN}/{API_SUBDOMAIN}/sessions/3party-jwt",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {bearer}",
        },
        json={
            "thirdPartyAccessToken": ypf["access_token"],
            "username": os.environ["YPF_USERNAME"].strip(),
        },
    ).json()

    data = {
        "bearer": bearer,
        "client_id": session["clientId"],
        "user_id": session["userId"],
        "expira_en": float(cache.get("expira_en") or ahora + TOKEN_TTL_SEGUNDOS),
    }
    _session_cache["data"] = data
    cache["access_token"] = bearer
    cache["user_id"] = session["userId"]
    cache["client_id"] = session["clientId"]
    cache["expira_en"] = data["expira_en"]
    cache["obtenido_en"] = cache.get("obtenido_en") or ahora
    _guardar_cache(cache)
    return data


def _headers(auth: dict[str, Any]) -> dict[str, str]:
    return {"Authorization": f"Bearer {auth['bearer']}"}


def _paginar(auth: dict[str, Any], path: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    page = 0
    while True:
        url = f"{API_BASE}{path}"
        resp = _request(
            "GET",
            url,
            headers=_headers(auth),
            params={"page": page, "pageSize": 50},
        ).json()
        lote = resp.get("content") or []
        items.extend(lote)
        if not lote or len(lote) < 50:
            break
        page += 1
        if page > 200:
            break
    return items


def listar_automotores(auth: dict[str, Any]) -> list[dict[str, Any]]:
    client_id = _enc(auth["client_id"])
    return _paginar(auth, f"/v1/{API_DOMAIN}/{API_SUBDOMAIN}/clients/{client_id}/automotors")


def listar_dispositivos(auth: dict[str, Any]) -> list[dict[str, Any]]:
    user_id = _enc(auth["user_id"])
    return _paginar(auth, f"/v1/{API_DOMAIN}/{API_SUBDOMAIN}/users/{user_id}/devices")


def ultima_ubicacion(auth: dict[str, Any], device_id: str) -> dict[str, Any] | None:
    user_id = _enc(auth["user_id"])
    dev = _enc(device_id)
    try:
        return _request(
            "GET",
            f"{API_BASE}/v1/{API_DOMAIN}/{API_SUBDOMAIN}/users/{user_id}/devices/{dev}/last-location",
            headers=_headers(auth),
        ).json()
    except RuntimeError:
        return None


def odometro_actual(auth: dict[str, Any], device_id: str) -> float | None:
    user_id = _enc(auth["user_id"])
    dev = _enc(device_id)
    try:
        data = _request(
            "GET",
            f"{API_BASE}/v1/{API_DOMAIN}/{API_SUBDOMAIN}/users/{user_id}/devices/{dev}/current-odometer",
            headers=_headers(auth),
        ).json()
        valor = data.get("value")
        return float(valor) if valor is not None else None
    except (RuntimeError, TypeError, ValueError):
        return None


def indicadores_dia(auth: dict[str, Any], device_ids: list[str]) -> list[dict[str, Any]]:
    if not device_ids:
        return []
    user_id = _enc(auth["user_id"])
    hoy = datetime.now(timezone.utc).date()
    try:
        data = _request(
            "POST",
            f"{API_BASE}/v1/{API_DOMAIN}/{API_SUBDOMAIN}/users/{user_id}/devices/trips/operation-indicators",
            headers={**_headers(auth), "Content-Type": "application/json"},
            params={"from": hoy.isoformat(), "to": hoy.isoformat(), "page": 0, "pageSize": 50},
            json={"deviceIds": device_ids},
        ).json()
    except RuntimeError:
        return []
    if isinstance(data, list):
        return data
    return data.get("content") or data.get("items") or []


def _campos_match_dispositivo(dispositivo: dict[str, Any]) -> list[str]:
    return [
        normalizar_patente(dispositivo.get("alias")),
        normalizar_patente(dispositivo.get("externalId")),
        normalizar_patente(dispositivo.get("notes")),
        normalizar_patente(dispositivo.get("imei")),
    ]


def emparejar_dispositivo(patente: str, dispositivos: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not patente:
        return None
    exactos = []
    parciales = []
    for dispositivo in dispositivos:
        campos = [c for c in _campos_match_dispositivo(dispositivo) if c]
        if patente in campos:
            exactos.append(dispositivo)
        elif any(patente in campo or campo in patente for campo in campos):
            parciales.append(dispositivo)
    if len(exactos) == 1:
        return exactos[0]
    if len(exactos) > 1:
        return exactos[0]
    if len(parciales) == 1:
        return parciales[0]
    return None


def _parse_fecha(valor: str | None) -> datetime:
    if not valor:
        return datetime.now(timezone.utc)
    texto = valor.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(texto)
    except ValueError:
        return datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def sincronizar_ypf_ruta() -> dict[str, Any]:
    Base.metadata.create_all(bind=engine)
    ensure_columns()
    auth = autenticar()
    try:
        automotores = listar_automotores(auth)
    except RuntimeError:
        automotores = []
    try:
        dispositivos = listar_dispositivos(auth)
    except RuntimeError:
        if not automotores:
            raise
        dispositivos = []

    filas: list[dict[str, Any]] = []
    omitidas = 0
    if automotores:
        for auto in automotores:
            patente = normalizar_patente(auto.get("plate") or auto.get("alias"))
            if not patente:
                omitidas += 1
                continue
            dispositivo = emparejar_dispositivo(patente, dispositivos)
            filas.append({"patente": patente, "auto": auto, "dispositivo": dispositivo})
    else:
        for dispositivo in dispositivos:
            patente = next((c for c in _campos_match_dispositivo(dispositivo) if c), "")
            if not patente:
                continue
            filas.append({"patente": patente, "auto": {}, "dispositivo": dispositivo})

    por_imei = {str(d.get("imei") or ""): d for d in dispositivos if d.get("imei")}
    for fila in filas:
        auto = fila.get("auto") or {}
        if not fila.get("dispositivo") and auto.get("imei"):
            fila["dispositivo"] = por_imei.get(str(auto["imei"]))

    extras: list[dict[str, Any]] = []
    indicadores: dict[str, Any] = {}
    indicadores_imei: dict[str, Any] = {}

    db = SessionLocal()
    creadas = 0
    actualizadas = 0
    con_gps = 0

    try:
        for fila in filas:
            patente = fila["patente"]
            auto = fila["auto"] or {}
            dispositivo = fila["dispositivo"]
            unidad = db.query(Unidad).filter(Unidad.patente_normalizada == patente).first()
            if not unidad:
                unidad = Unidad(
                    patente_normalizada=patente,
                    empresa="YPF Ruta",
                )
                db.add(unidad)
                db.flush()
                creadas += 1
            else:
                actualizadas += 1

            if auto.get("brand") and not unidad.marca:
                unidad.marca = str(auto["brand"])[:50]
            if auto.get("model") and not unidad.modelo:
                unidad.modelo = str(auto["model"])[:50]
            if auto.get("imei") and not unidad.ypf_imei:
                unidad.ypf_imei = str(auto["imei"])[:40]
            if dispositivo:
                unidad.ypf_device_id = dispositivo.get("id")
                unidad.ypf_imei = dispositivo.get("imei") or unidad.ypf_imei
            if auto.get("id"):
                unidad.ypf_automotor_id = auto.get("id")

            lat = lon = None
            odo = None
            try:
                if auto.get("originalMileage") is not None:
                    odo = float(auto["originalMileage"])
            except (TypeError, ValueError):
                odo = None
            fecha = datetime.now(timezone.utc)
            limite_gps = int(os.getenv("YPF_GPS_LIMITE", "25"))
            if dispositivo and dispositivo.get("id") and con_gps < limite_gps:
                loc = ultima_ubicacion(auth, dispositivo["id"])
                if loc:
                    lat = loc.get("latitude")
                    lon = loc.get("longitude")
                    fecha = _parse_fecha(loc.get("messageTime") or loc.get("generatedTime"))
                    con_gps += 1
                odo_gps = odometro_actual(auth, dispositivo["id"])
                if odo_gps is not None:
                    odo = odo_gps

            extra = indicadores.get(patente) or indicadores_imei.get(str((dispositivo or {}).get("imei") or ""))
            km_mes = extra.get("distanceTraveled") if extra else None
            litros = extra.get("fuelConsumptionQty") if extra else None
            consumo = extra.get("fuelEconomy") if extra else None

            db.add(RegistroTelemetria(
                unidad_id=unidad.id,
                odometro_gps=odo,
                km_recorridos_mes=km_mes,
                consumo_l100km=consumo,
                litros_combustible=litros,
                latitud=lat,
                longitud=lon,
                fuente="YPF_Ruta",
                fecha_lectura=fecha,
            ))

        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    return {
        "ok": True,
        "fuente": "YPF_Ruta",
        "automotores": len(automotores),
        "dispositivos": len(dispositivos),
        "unidades_nuevas": creadas,
        "unidades_actualizadas": actualizadas,
        "con_gps": con_gps,
        "omitidas": omitidas,
        "gps_limite": int(os.getenv("YPF_GPS_LIMITE", "25")),
        "sincronizado_en": datetime.now(timezone.utc).isoformat(),
    }


def actualizar_gps_odometros() -> dict[str, Any]:
    """Baja last-location y current-odometer de todas las unidades con device YPF."""
    Base.metadata.create_all(bind=engine)
    ensure_columns()
    auth = autenticar()
    db = SessionLocal()
    unidades = (
        db.query(Unidad)
        .filter(Unidad.ypf_device_id.isnot(None))
        .order_by(Unidad.patente_normalizada)
        .all()
    )
    con_gps = 0
    con_odo = 0
    errores = 0
    try:
        for i, unidad in enumerate(unidades, start=1):
            lat = lon = odo = None
            fecha = datetime.now(timezone.utc)
            loc = ultima_ubicacion(auth, unidad.ypf_device_id)
            if loc:
                lat = loc.get("latitude")
                lon = loc.get("longitude")
                if lat is not None and lon is not None:
                    con_gps += 1
            odo = odometro_actual(auth, unidad.ypf_device_id)
            if odo is None or odo == 0:
                previo = (
                    db.query(RegistroTelemetria)
                    .filter(
                        RegistroTelemetria.unidad_id == unidad.id,
                        RegistroTelemetria.odometro_gps > 0,
                    )
                    .order_by(RegistroTelemetria.fecha_lectura.desc())
                    .first()
                )
                if previo:
                    odo = previo.odometro_gps
            if odo is not None:
                con_odo += 1
            if loc is None and odo is None:
                errores += 1
                continue
            db.add(RegistroTelemetria(
                unidad_id=unidad.id,
                odometro_gps=odo,
                latitud=lat,
                longitud=lon,
                fuente="YPF_Ruta",
                fecha_lectura=datetime.now(timezone.utc),
            ))
            if i % 10 == 0:
                db.commit()
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    return {
        "ok": True,
        "fuente": "YPF_Ruta",
        "unidades": len(unidades),
        "con_gps": con_gps,
        "con_odometro": con_odo,
        "sin_datos": errores,
        "sincronizado_en": datetime.now(timezone.utc).isoformat(),
    }


if __name__ == "__main__":
    if credenciales_faltantes(REQUIRED_LW):
        print("Configuración:", estado_configuracion())
        raise SystemExit(1)
    modo = os.getenv("YPF_MODO", "padron")
    if modo == "gps":
        print(actualizar_gps_odometros())
    else:
        print(sincronizar_ypf_ruta())
