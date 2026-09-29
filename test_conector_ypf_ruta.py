import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from conector_ypf_ruta import (
    TOKEN_TTL_SEGUNDOS,
    credenciales_faltantes,
    emparejar_dispositivo,
    estado_configuracion,
    normalizar_patente,
    obtener_token_location_world,
    token_lw_vigente,
)


class TestYpfRuta(unittest.TestCase):
    def test_normalizar_patente(self):
        self.assertEqual(normalizar_patente("GPV-408"), "GPV408")
        self.assertEqual(normalizar_patente("gpv 408"), "GPV408")
        self.assertEqual(normalizar_patente(None), "")

    def test_emparejar_por_alias(self):
        dispositivos = [
            {"id": "dev-1", "alias": "GPV-408", "externalId": "", "notes": "", "imei": "111"},
            {"id": "dev-2", "alias": "AB123CD", "externalId": "", "notes": "", "imei": "222"},
        ]
        encontrado = emparejar_dispositivo("GPV408", dispositivos)
        self.assertIsNotNone(encontrado)
        self.assertEqual(encontrado["id"], "dev-1")

    def test_emparejar_sin_match(self):
        self.assertIsNone(emparejar_dispositivo("ZZZ999", [{"id": "x", "alias": "AAA111"}]))

    def test_faltan_credenciales(self):
        env = {clave: "" for clave in (
            "LOCATIONWORLD_CLIENT_ID",
            "LOCATIONWORLD_CLIENT_SECRET",
            "YPF_CLIENT_ID",
            "YPF_CLIENT_SECRET",
            "YPF_SCOPE",
            "YPF_USERNAME",
            "YPF_PASSWORD",
        )}
        with tempfile.TemporaryDirectory() as tmp:
            cache = str(Path(tmp) / "token.json")
            with patch.dict(os.environ, {**env, "YPF_TOKEN_CACHE": cache}, clear=False):
                faltantes = credenciales_faltantes()
                self.assertTrue(faltantes)
                self.assertFalse(estado_configuracion()["configurado"])

    def test_token_vigente_y_reutilizado(self):
        ahora = time.time()
        cache = {
            "access_token": "token-cacheado",
            "obtenido_en": ahora,
            "expira_en": ahora + TOKEN_TTL_SEGUNDOS,
        }
        self.assertTrue(token_lw_vigente(cache, ahora))
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "token.json"
            ruta.write_text(json.dumps(cache), encoding="utf-8")
            with patch.dict(os.environ, {"YPF_TOKEN_CACHE": str(ruta)}, clear=False):
                with patch("conector_ypf_ruta._request") as mock_req:
                    token = obtener_token_location_world()
                    self.assertEqual(token, "token-cacheado")
                    mock_req.assert_not_called()

    def test_no_pide_otro_token_dentro_de_24h_si_expiro(self):
        ahora = time.time()
        cache = {
            "access_token": "viejo",
            "obtenido_en": ahora - 100,
            "expira_en": ahora - 10,
        }
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "token.json"
            ruta.write_text(json.dumps(cache), encoding="utf-8")
            with patch.dict(os.environ, {"YPF_TOKEN_CACHE": str(ruta)}, clear=False):
                with self.assertRaises(RuntimeError) as ctx:
                    obtener_token_location_world()
                self.assertIn("24 h", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
