# ==========================================================================
#  RHYTHM — BUILD PC PARA TESTERS
#
#  Lanzador de la version de escritorio: el juego COMPLETO sin el hardware
#  de la instalacion (modo instrumento / teclado musical por line-in).
#  Se juega con teclado de PC (A-S-D-F-G-H-J-K) y gamepad.
#
#  rhythm.py sigue siendo la unica fuente de verdad: este archivo NO es un
#  fork — solo setea el flag de build y arranca el juego. Cualquier cambio
#  al juego se hace siempre en rhythm.py.
#
#  Correr en desarrollo:   python rhythm_pc.py
#  Compilar el exe:        pyinstaller rhythm_pc.spec --noconfirm
#                          (queda en dist/rhythm_testers.exe)
# ==========================================================================
import os

os.environ["RHYTHM_BUILD"] = "pc"

import rhythm  # noqa: F401  — el juego corre al importarse
