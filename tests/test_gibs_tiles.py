import importlib
import os
import sys
import tempfile
import types
import unittest
from flask import Blueprint
from unittest import mock


def _install_app_stubs():
    core = types.ModuleType("core")
    core.CoupangPartners = object
    core.is_valid_coupang_url = lambda *args, **kwargs: True
    core.make_blog_draft = lambda *args, **kwargs: "draft"
    core.COUPANG_DISCLOSURE = ""
    core.unshorten_coupang = lambda *args, **kwargs: None
    core.is_short_coupang_link = lambda *args, **kwargs: False
    core.extract_coupang_url = lambda *args, **kwargs: None
    core.build_naver_html = lambda *args, **kwargs: ""
    core.zernio_publish = lambda *args, **kwargs: {"ok": True}
    core.warm_radar = lambda: None
    sys.modules["core"] = core

    store = types.ModuleType("store")
    store.init_db = lambda: None
    store.boim_init = lambda: None
    store.boim_kit_init = lambda: None
    sys.modules["store"] = store

    for mod_name, attrs in {
        "spinads_api_v2": {"spinads_bp": Blueprint("spinads", __name__)},
        "radar_api_v1": {"radar_bp": Blueprint("radar", __name__)},
        "borderrx_v1": {"rx_bp": Blueprint("rx", __name__)},
        "gottago_v1": {"gg_bp": Blueprint("gg", __name__)},
        "eats_v1": {"ea_bp": Blueprint("ea", __name__)},
        "next_v1": {"nx_bp": Blueprint("nx", __name__)},
        "duty_v1": {"dt_bp": Blueprint("dt", __name__)},
        "threads_v1": {"th_bp": Blueprint("th", __name__)},
        "canibring_v1": {
            "cb_bp": Blueprint("cb", __name__),
            "cb_home": lambda: "",
            "INDEXNOW_KEY": "test-key",
        },
        "parking_v1": {"pk_bp": Blueprint("pk", __name__)},
    }.items():
        mod = types.ModuleType(mod_name)
        for attr_name, value in attrs.items():
            setattr(mod, attr_name, value)
        sys.modules[mod_name] = mod


def _load_app_module():
    sys.modules.pop("app", None)
    return importlib.import_module("app")


_install_app_stubs()
app_module = _load_app_module()


class GibsTileRouteTests(unittest.TestCase):
    def setUp(self):
        self.client = app_module.app.test_client()
        self.tmpdir = tempfile.TemporaryDirectory()
        self.old_cache_dir = os.environ.get("GIBS_CACHE_DIR")
        os.environ["GIBS_CACHE_DIR"] = self.tmpdir.name

    def tearDown(self):
        if self.old_cache_dir is None:
            os.environ.pop("GIBS_CACHE_DIR", None)
        else:
            os.environ["GIBS_CACHE_DIR"] = self.old_cache_dir
        self.tmpdir.cleanup()

    def test_whitelist_rejects_unknown_layer(self):
        resp = self.client.get("/fly/tiles/Foo/0/0/0.jpeg")
        self.assertEqual(resp.status_code, 404)

    def test_z_and_xy_bounds_are_rejected(self):
        bad_paths = [
            "/fly/tiles/BlueMarble_ShadedRelief_Bathymetry/9/0/0.jpeg",
            "/fly/tiles/BlueMarble_ShadedRelief_Bathymetry/8/0/256.jpeg",
            "/fly/tiles/BlueMarble_ShadedRelief_Bathymetry/8/256/0.jpeg",
            "/fly/tiles/VIIRS_Black_Marble/8/0/256.png",
            "/fly/tiles/VIIRS_Black_Marble/0/0/1.png",
        ]
        for path in bad_paths:
            resp = self.client.get(path)
            self.assertEqual(resp.status_code, 404, msg=f"{path} should be rejected")

    def test_second_request_uses_cache_after_mocked_upstream(self):
        with mock.patch.object(app_module, "fetch_upstream_tile", return_value=b"tile-bytes") as fetch_mock:
            path = "/fly/tiles/BlueMarble_ShadedRelief_Bathymetry/2/1/1.jpeg"
            first = self.client.get(path)
            second = self.client.get(path)

            self.assertEqual(first.status_code, 200)
            self.assertEqual(first.headers.get("Content-Type"), "image/jpeg")
            self.assertEqual(first.headers.get("X-Cache"), "MISS")
            self.assertEqual(second.status_code, 200)
            self.assertEqual(second.headers.get("X-Cache"), "HIT")
            self.assertEqual(fetch_mock.call_count, 1)


if __name__ == "__main__":
    unittest.main()
