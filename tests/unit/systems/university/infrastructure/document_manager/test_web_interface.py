"""Tests for document_manager.web_interface (WebInterfaceMixin)"""
import sys
from unittest.mock import patch, MagicMock


def test_web_interface_menu_dispatch(doc_manager, feed_input):
    methods = ["start_web_server", "generate_mobile_interface",
               "web_interface_settings", "mobile_app_qr_code"]
    for i, m in enumerate(methods, start=1):
        if not hasattr(doc_manager, m):
            continue
        with patch.object(doc_manager, m, create=True) as p:
            feed_input(str(i))
            doc_manager.web_interface_menu()
            p.assert_called_once()


def test_web_interface_menu_invalid(doc_manager, feed_input):
    feed_input("99")
    doc_manager.web_interface_menu()


def test_start_web_server(doc_manager, capsys):
    doc_manager.start_web_server()
    out = capsys.readouterr().out
    assert "URL" in out


def test_generate_mobile_interface_yes(doc_manager, feed_input):
    feed_input("y")
    doc_manager.generate_mobile_interface()


def test_generate_mobile_interface_no(doc_manager, feed_input):
    feed_input("n")
    doc_manager.generate_mobile_interface()


def test_mobile_app_qr_code_no_lib(doc_manager, feed_input, monkeypatch, capsys):
    monkeypatch.setitem(sys.modules, "qrcode", None)
    feed_input("n")
    doc_manager.mobile_app_qr_code()


def test_mobile_app_qr_code_with_lib(doc_manager, feed_input, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    fake_qrcode = MagicMock()
    qr_inst = MagicMock()
    qr_inst.make_image.return_value.save = MagicMock()
    fake_qrcode.QRCode.return_value = qr_inst
    monkeypatch.setitem(sys.modules, "qrcode", fake_qrcode)
    feed_input("y")
    doc_manager.mobile_app_qr_code()
