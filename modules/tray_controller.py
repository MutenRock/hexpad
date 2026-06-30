"""
modules/tray_controller.py — Alias de compatibilité vers tray_icon.TrayController

gui.py v2.5.0+ importe depuis ce module.
L'implémentation complète reste dans modules/tray_icon.py.
"""
from modules.tray_icon import TrayController  # noqa: F401

__all__ = ["TrayController"]
