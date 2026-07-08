import pygame
import random
import numpy as np
import json
import wave
import os
import sys
import threading
import math
import traceback
import queue

# ╔══════════════════════════════════════════════════════════════════════╗
# ║  RHYTHM - Juego ritmico procedural                                     ║
# ║  Musica, graficos y audio 100% generados por codigo (sin assets).     ║
# ╠══════════════════════════════════════════════════════════════════════╣
# ║  INDICE DE SECCIONES (buscar el texto entre >> << para saltar)        ║
# ║                                                                        ║
# ║  >>SETUP<<        Imports, BASE_DIR, crash handler, init de pygame     ║
# ║  >>AUDIO_DEV<<    Deteccion de dispositivos de audio                   ║
# ║  >>CONFIG<<       config.json: guardar/cargar preferencias            ║
# ║  >>VENTANA<<      Resolucion, escalado, brillo, fuentes                ║
# ║  >>CONSTANTES<<   Colores, teclas, escalas, acordes, dificultades,    ║
# ║                   mods, generos, instrumentos (datos puros)           ║
# ║  >>SYNTH_SFX<<    Sintesis de efectos de sonido (UI, hit, combo...)   ║
# ║  >>SYNTH_INST<<   Sintesis de instrumentos jugables                    ║
# ║  >>SYNTH_DRUMS<<  Sintesis de bateria y bajo                           ║
# ║  >>RENDER_INST<<  Renderizado/cache de instrumentos por nota          ║
# ║  >>MUSICA_MENU<<  Musica de fondo del menu (streaming + crossfade)    ║
# ║  >>PARTICULAS<<   Sistema de particulas, ondas, flashes, shake        ║
# ║  >>MUSIC_GEN<<    Generacion procedural de canciones                   ║
# ║  >>GAME_STATE<<   iniciar_partida, runs, stages, mods                  ║
# ║  >>RENDER_JUEGO<< Dibujo del gameplay, HUD, fondo enemigo             ║
# ║  >>PANTALLAS<<    Menu, leaderboard, config, dado, run overview       ║
# ║  >>MAIN_LOOP<<    Bucle principal y manejo de eventos                  ║
# ╚══════════════════════════════════════════════════════════════════════╝

# ═══════════════════════════════════════════════════════ >>SETUP<< ═══

# directorio base: donde esta el .exe (compilado) o el .py (desarrollo)
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --- crash handler: guarda cualquier error no manejado a un archivo ---
def _crash_handler(exc_type, exc_value, exc_tb):
    try:
        ruta = os.path.join(BASE_DIR, "crash_log.txt")
        with open(ruta, "w", encoding="utf-8") as f:
            f.write("RHYTHM crash log\n")
            f.write("=" * 40 + "\n")
            traceback.print_exception(exc_type, exc_value, exc_tb, file=f)
        print(f"Error guardado en {ruta}")
    except Exception:
        pass
    # tambien imprimir a consola si hay
    traceback.print_exception(exc_type, exc_value, exc_tb)

sys.excepthook = _crash_handler

pygame.init()

# --- dispositivos de audio ---
# ═══════════════════════════════════════════════════ >>AUDIO_DEV<< ═══

def listar_dispositivos_audio():
    """Lista dispositivos de salida usando SDL2 (nombres compatibles con mixer)."""
    dispositivos = ["Default"]
    # buscar SDL2 DLL en el directorio de pygame
    import ctypes
    sdl2 = None
    for ruta in [
        os.path.join(os.path.dirname(pygame.__file__), "SDL2.dll"),
        "SDL2.dll", "SDL2",
    ]:
        try:
            sdl2 = ctypes.CDLL(ruta)
            break
        except OSError:
            continue
    if sdl2 is not None:
        try:
            sdl2.SDL_GetNumAudioDevices.restype = ctypes.c_int
            sdl2.SDL_GetNumAudioDevices.argtypes = [ctypes.c_int]
            sdl2.SDL_GetAudioDeviceName.restype = ctypes.c_char_p
            sdl2.SDL_GetAudioDeviceName.argtypes = [ctypes.c_int, ctypes.c_int]
            n = sdl2.SDL_GetNumAudioDevices(0)
            for i in range(n):
                nombre = sdl2.SDL_GetAudioDeviceName(i, 0)
                if nombre:
                    dispositivos.append(nombre.decode("utf-8", errors="replace"))
        except Exception as e:
            print(f"  SDL2 enum fallo: {e}")
    # fallback: winmm (solo si SDL2 no encontro nada)
    if len(dispositivos) <= 1:
        try:
            from ctypes import wintypes
            class WAVEOUTCAPS(ctypes.Structure):
                _fields_ = [
                    ("wMid", wintypes.WORD), ("wPid", wintypes.WORD),
                    ("vDriverVersion", wintypes.UINT),
                    ("szPname", ctypes.c_wchar * 32),
                    ("dwFormats", wintypes.DWORD), ("wChannels", wintypes.WORD),
                    ("wReserved1", wintypes.WORD), ("dwSupport", wintypes.DWORD),
                ]
            winmm = ctypes.WinDLL('winmm')
            n = winmm.waveOutGetNumDevs()
            for i in range(n):
                caps = WAVEOUTCAPS()
                if winmm.waveOutGetDevCapsW(i, ctypes.byref(caps), ctypes.sizeof(caps)) == 0:
                    dispositivos.append(caps.szPname)
        except Exception:
            pass
    return dispositivos

AUDIO_DEVICES = listar_dispositivos_audio()
print(f"Dispositivos de audio ({len(AUDIO_DEVICES)}): {AUDIO_DEVICES}")

# buffer 1024: mas margen contra underruns (clicks) durante las cargas pesadas.
# 1024 samples @ 44100Hz = ~23ms de latencia, imperceptible en un rhythm game.
AUDIO_BUFFER = 1024
AUDIO_CANALES = 32
pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=AUDIO_BUFFER)
pygame.mixer.set_num_channels(AUDIO_CANALES)

ANCHO, ALTO = 720, 640

# --- configuracion ajustable ---
RESOLUCIONES = [(720, 640), (900, 800), (1080, 960), (1280, 1138)]
config = {
    "brillo": 1.0,      # 0.3 a 1.0
    "volumen": 1.0,     # 0.0 a 1.0
    "vol_menu": 0.5,    # 0.0 a 1.0 (volumen de la musica del menu)
    "res_idx": 2,       # indice en RESOLUCIONES (1080x960)
    "audio_idx": 0,     # 0 = default, 1+ = dispositivo especifico
}

CONFIG_FILE = os.path.join(BASE_DIR, "config.json")

# ══════════════════════════════════════════════════════ >>CONFIG<< ═══

def guardar_config():
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=2)
    except Exception:
        pass

def cargar_config():
    try:
        with open(CONFIG_FILE, "r") as f:
            guardado = json.load(f)
        for k, v in guardado.items():
            if k in config:
                config[k] = v
        # validar rangos
        config["brillo"] = max(0.3, min(1.0, config["brillo"]))
        config["volumen"] = max(0.0, min(1.0, config["volumen"]))
        config["vol_menu"] = max(0.0, min(1.0, config["vol_menu"]))
        config["res_idx"] = max(0, min(len(RESOLUCIONES) - 1, config["res_idx"]))
        config["audio_idx"] = max(0, min(len(AUDIO_DEVICES) - 1, config["audio_idx"]))
    except Exception:
        pass

cargar_config()

# si la config guardo un dispositivo de audio especifico, reabrir el mixer con el
if config.get("audio_idx", 0) != 0 and config["audio_idx"] < len(AUDIO_DEVICES):
    try:
        pygame.mixer.quit()
        nombre_dev = AUDIO_DEVICES[config["audio_idx"]]
        pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=AUDIO_BUFFER, devicename=nombre_dev)
        pygame.mixer.set_num_channels(AUDIO_CANALES)
        print(f"Audio en dispositivo guardado: {nombre_dev}")
    except Exception as e:
        print(f"No se pudo abrir dispositivo guardado, usando default: {e}")
        pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=AUDIO_BUFFER)
        pygame.mixer.set_num_channels(AUDIO_CANALES)
        config["audio_idx"] = 0

# la ventana real puede cambiar de tamaño; el juego siempre dibuja en 720x640 y se escala
_w, _h = RESOLUCIONES[config["res_idx"]]
ventana = pygame.display.set_mode((_w, _h))
pygame.display.set_caption("Rhythm Game")
pantalla = pygame.Surface((ANCHO, ALTO))
clock = pygame.time.Clock()

# ══════════════════════════════════════════════════════ >>VENTANA<< ═══

def presentar():
    """Escala la superficie interna a la ventana, aplica brillo y muestra"""
    w, h = ventana.get_size()
    if (w, h) != (ANCHO, ALTO):
        escalada = pygame.transform.scale(pantalla, (w, h))
    else:
        escalada = pantalla
    ventana.blit(escalada, (0, 0))
    # overlay de brillo (oscurece si brillo < 1)
    if config["brillo"] < 1.0:
        oscuro = pygame.Surface((w, h))
        oscuro.fill((0, 0, 0))
        oscuro.set_alpha(int((1.0 - config["brillo"]) * 255))
        ventana.blit(oscuro, (0, 0))
    pygame.display.flip()

# splash inmediato para que no se vea negro
pantalla.fill((0, 0, 0))
_splash_f = pygame.font.SysFont("courier", 48, bold=True)
_splash_t = _splash_f.render("* RHYTHM *", True, (255, 255, 255))
pantalla.blit(_splash_t, (ANCHO // 2 - _splash_t.get_width() // 2, 200))
_splash_f2 = pygame.font.SysFont("courier", 24, bold=True)
_splash_t2 = _splash_f2.render("PREPARANDO...", True, (140, 140, 140))
pantalla.blit(_splash_t2, (ANCHO // 2 - _splash_t2.get_width() // 2, 300))
presentar()
del _splash_f, _splash_t, _splash_f2, _splash_t2

# ═══════════════════════════════════════════════════ >>CONSTANTES<< ═══
# Datos puros: colores, teclas, escalas, acordes, dificultades, mods.

NEGRO    = (0,   0,   0)
BLANCO   = (255, 255, 255)
GRIS     = (80,  80,  80)
GRIS_MED = (140, 140, 140)

COLUMNAS = {
    pygame.K_a: 0,
    pygame.K_s: 1,
    pygame.K_d: 2,
    pygame.K_f: 3,
    pygame.K_g: 4,
    pygame.K_h: 5,
    pygame.K_j: 6,
    pygame.K_k: 7,
}

LABELS = ["A", "S", "D", "F", "G", "H", "J", "K"]

# --- SOPORTE DE CONTROLADOR (GAMEPAD) ---
# Inicializa el primer joystick disponible. Los botones se mapean a columnas
# de juego y a navegacion de menus. Compatible con Xbox, PlayStation, y
# genericos. El mapeo es configurable abajo.
pygame.joystick.init()
joystick = None
if pygame.joystick.get_count() > 0:
    joystick = pygame.joystick.Joystick(0)
    joystick.init()
    print(f"Controlador detectado: {joystick.get_name()}")
    print(f"  Botones: {joystick.get_numbuttons()}, Ejes: {joystick.get_numaxes()}, Hats: {joystick.get_numhats()}")
else:
    print("No se detecto controlador (solo teclado)")

# Mapeo de botones del gamepad a columnas de juego.
# Orden pensado para Xbox/PS: las 4 caras (A/B/X/Y o Cross/Circle/Square/Triangle)
# + bumpers + triggers para 6-8 columnas.
# Xbox:  A=0 B=1 X=2 Y=3 LB=4 RB=5 LT_btn=6 RT_btn=7
# PS:    X=0 O=1 Sq=2 Tri=3 L1=4 R1=5 L2_btn=6 R2_btn=7
# Los ejes analogicos (triggers) se tratan aparte si es necesario.
PAD_COLUMNAS = {
    0: 0,   # A / Cross       -> col 0
    1: 1,   # B / Circle      -> col 1
    2: 2,   # X / Square      -> col 2
    3: 3,   # Y / Triangle    -> col 3
    4: 4,   # LB / L1         -> col 4
    5: 5,   # RB / R1         -> col 5
    6: 6,   # Back/Select/L2  -> col 6
    7: 7,   # Start/R2        -> col 7
}
# Botones de navegacion (para menus). Estos NO mapean a columnas.
PAD_CONFIRM = {0}       # A / Cross = confirmar
PAD_BACK    = {1}       # B / Circle = atras/ESC
PAD_START   = {7, 11}   # Start / Options = pausar (varía por controlador)
# Umbral del eje digital del hat/dpad
PAD_AXIS_THRESHOLD = 0.5

def pad_col_down(button):
    """Devuelve la columna (0-7) si el boton mapea a una, o None."""
    return PAD_COLUMNAS.get(button)

def pad_es_confirm(button):
    return button in PAD_CONFIRM

def pad_es_back(button):
    return button in PAD_BACK

def pad_es_start(button):
    return button in PAD_START

ESCALAS = {
    "mayor":       [0, 2, 4, 5, 7, 9, 11, 12],
    "menor":       [0, 2, 3, 5, 7, 8, 10, 12],
    "pentatonica": [0, 2, 4, 7, 9, 12, 14, 16],
    "arm_menor":   [0, 2, 3, 5, 7, 8, 11, 12],
    "blues":       [0, 3, 5, 7, 10, 12, 15, 17],
}

# Grados pentatonicos derivados de cada escala. Cuando el jugador pega notas,
# las columnas se mapean a estos grados para que CUALQUIER combinacion de
# columnas suene consonante entre si (la pentatonica no tiene intervalos de
# segunda menor). El bajo y los acordes siguen usando la escala completa para
# mantener estructura armonica, pero el jugador siempre toca "notas seguras".
PENTA_GRADOS = {
    "mayor":       [0, 1, 2, 4, 5],   # C D E G A (penta mayor clasica)
    "menor":       [0, 2, 3, 4, 6],   # C Eb F G Bb (penta menor clasica)
    "arm_menor":   [0, 2, 3, 4, 6],   # C Eb F G B (penta con sensible, sin choque)
    "pentatonica": [0, 1, 2, 3, 4],   # ya es pentatonica, primeros 5 grados
    "blues":       [0, 1, 2, 3, 4],   # los 5 grados clasicos del blues
}

ACORDES_PATRON = {
    "mayor":       [[0, 2, 4], [3, 5, 7], [4, 6, 8], [0, 2, 4]],
    "menor":       [[0, 2, 4], [3, 5, 7], [4, 6, 8], [0, 2, 4]],
    "pentatonica": [[0, 2, 4], [1, 3, 5], [2, 4, 6], [0, 2, 4]],
    "arm_menor":   [[0, 2, 4], [3, 5, 7], [4, 6, 8], [0, 2, 4]],
    "blues":       [[0, 2, 4], [3, 5, 7], [0, 2, 4], [2, 4, 6]],
}

# progresiones armónicas reales (indices de grado en la escala).
# Todas resuelven correctamente: terminan en I o preparan el retorno a I.
# Muchas incluyen la cadencia autentica V->I (la resolucion mas fuerte).
PROGRESIONES = [
    [0, 3, 4, 0],    # I - IV - V - I   (cadencia autentica clasica)
    [0, 5, 3, 4],    # I - vi - IV - V  (progresion pop, semicadencia en V)
    [0, 4, 5, 3],    # I - V - vi - IV  (pop "axis")
    [0, 3, 0, 4],    # I - IV - I - V   (blues-ish, abre a dominante)
    [0, 5, 1, 4],    # I - vi - ii - V  (circulo de quintas, muy fuerte)
    [0, 1, 4, 0],    # I - ii - V - I   (ii-V-I, el mas jazzistico)
    [0, 5, 3, 0],    # I - vi - IV - I  (plagal, "amen")
    [0, 3, 5, 4],    # I - IV - vi - V
    [0, 4, 3, 4],    # I - V - IV - V   (rock, oscilacion)
    [0, 2, 3, 4],    # I - iii - IV - V (mediante ascendente)
]

# grados que funcionan como dominante (crean tension que pide resolver a I).
# En estos grados, si la escala es menor, se sube la tercera para tener sensible.
GRADOS_DOMINANTE = {4}   # el V

DIFICULTADES = {
    1:  {"nombre": "FACIL",      "columnas": 3, "acordes": False, "dens": 0.20, "bpm_mult": 0.70, "vel_mult": 0.60},
    2:  {"nombre": "FACIL+",     "columnas": 3, "acordes": False, "dens": 0.26, "bpm_mult": 0.75, "vel_mult": 0.70},
    3:  {"nombre": "NORMAL",     "columnas": 3, "acordes": True,  "dens": 0.38, "bpm_mult": 0.85, "vel_mult": 0.75},
    4:  {"nombre": "NORMAL+",    "columnas": 4, "acordes": False, "dens": 0.65, "bpm_mult": 0.85, "vel_mult": 0.80},
    5:  {"nombre": "NORMAL++",   "columnas": 4, "acordes": True,  "dens": 0.75, "bpm_mult": 0.90, "vel_mult": 0.85},
    6:  {"nombre": "INTERMEDIO", "columnas": 4, "acordes": True,  "dens": 0.85, "bpm_mult": 0.90, "vel_mult": 0.90},
    7:  {"nombre": "INTERMEDIO+","columnas": 4, "acordes": True,  "dens": 0.92, "bpm_mult": 0.95, "vel_mult": 0.95},
    8:  {"nombre": "DIFICIL",    "columnas": 5, "acordes": True,  "dens": 1.00, "bpm_mult": 1.0,  "vel_mult": 1.0},
    9:  {"nombre": "DIFICIL+",   "columnas": 5, "acordes": True,  "dens": 1.10, "bpm_mult": 1.0,  "vel_mult": 1.0},
    10: {"nombre": "PRO",        "columnas": 6, "acordes": True,  "dens": 1.20, "bpm_mult": 1.0,  "vel_mult": 1.0},
    11: {"nombre": "PRO+",       "columnas": 6, "acordes": True,  "dens": 1.30, "bpm_mult": 1.0,  "vel_mult": 1.05},
    12: {"nombre": "MASTER",     "columnas": 7, "acordes": True,  "dens": 1.40, "bpm_mult": 1.0,  "vel_mult": 1.05},
    13: {"nombre": "MASTER+",    "columnas": 7, "acordes": True,  "dens": 1.50, "bpm_mult": 1.0,  "vel_mult": 1.10},
    14: {"nombre": "GOD",        "columnas": 7, "acordes": True,  "dens": 1.60, "bpm_mult": 1.0,  "vel_mult": 1.15},
    15: {"nombre": "CHAOS",      "columnas": 8, "acordes": True,  "dens": 1.80, "bpm_mult": 1.0,  "vel_mult": 1.20},
}

SEED_MAX       = 9999
SEED_VELOCIDAD = 9.0
ZONA_Y         = ALTO - 90
VELOCIDAD      = 5.5

# --- modificadores de partida (suben el multiplicador de puntos) ---
MODIFICADORES = [
    {"id": "espejo",     "nombre": "ESPEJO",      "desc": "columnas invertidas",    "mult": 1.2},
    {"id": "veloz",      "nombre": "VELOCIDAD x2", "desc": "notas el doble de rapido", "mult": 1.5},
    {"id": "invisible",  "nombre": "INVISIBLES",  "desc": "notas desaparecen al caer", "mult": 1.8},
    {"id": "inverso",    "nombre": "INVERSO",     "desc": "notas suben en vez de caer", "mult": 1.4},
    {"id": "acelerando", "nombre": "ACELERANDO",  "desc": "velocidad sube gradualmente", "mult": 1.3},
    {"id": "niebla",     "nombre": "NIEBLA",      "desc": "notas aparecen desde la mitad", "mult": 1.6},
    {"id": "rafagas",    "nombre": "RAFAGAS",     "desc": "tramos densos y silencios", "mult": 1.3},
    {"id": "sudden",     "nombre": "SUDDEN DEATH","desc": "1 error = game over",     "mult": 2.0},
    {"id": "monocromo",  "nombre": "MONOCROMO",   "desc": "power-ups y acordes sin marca distintiva", "mult": 1.25},
    {"id": "apagon",     "nombre": "APAGON",      "desc": "las notas se desvanecen por momentos", "mult": 1.7},
]
mods_activos = set()   # ids de modificadores seleccionados (modo libre)

# mods "faciles" que pueden salir en el dado de los stages 2 y 3
MODS_FACILES = ["espejo", "inverso", "veloz", "acelerando", "niebla", "rafagas", "monocromo", "apagon"]

# --- perks roguelike: se eligen entre stages y se acumulan ---
# categorias: def = defensivo (proteccion), ofe = ofensivo (puntos),
#             mec = mecanico (facilita el juego)
PERKS = [
    {"id": "escudo",     "nombre": "ESCUDO",     "desc": "3 misses no te bajan vida", "cat": "def"},
    {"id": "corazon",    "nombre": "CORAZON",    "desc": "vida maxima +5",            "cat": "def"},
    {"id": "ventana",    "nombre": "VENTANA",    "desc": "ventana de acierto 25% mas grande", "cat": "def"},
    {"id": "resurreccion","nombre": "RESURRECCION","desc": "al morir, revives con 5 de vida (1 vez)", "cat": "def"},
    {"id": "regen",      "nombre": "REGENERACION","desc": "+1 vida cada 20 de combo", "cat": "def"},
    {"id": "multi",      "nombre": "MULTI",      "desc": "todos los puntos x1.5",     "cat": "ofe"},
    {"id": "combo_save", "nombre": "COMBO SAVE", "desc": "el 1er miss no rompe combo (cd 15s)", "cat": "ofe"},
    {"id": "perfecto",   "nombre": "PERFECTO+",  "desc": "cada PERFECT vale doble puntos", "cat": "ofe"},
    {"id": "racha",      "nombre": "RACHA",      "desc": "el multiplicador de combo sube mas rapido", "cat": "ofe"},
    {"id": "hold_master","nombre": "HOLD MASTER","desc": "las notas largas dan puntos x2", "cat": "ofe"},
    {"id": "cazador",    "nombre": "CAZADOR",    "desc": "power-ups temporales duran el doble", "cat": "ofe"},
    {"id": "lento",      "nombre": "LENTO",      "desc": "las notas bajan 15% mas lento", "cat": "mec"},
    {"id": "iman",       "nombre": "IMAN",       "desc": "zona PERFECT mas amplia (mas facil clavar)", "cat": "mec"},
]

# color de cada categoria de perk, usado en la pantalla de seleccion y HUD.
# def = cyan (proteccion), ofe = naranja (dano/puntos), mec = verde (utilidad)
COLOR_CAT = {
    "def": (100, 200, 255),
    "ofe": (255, 150, 60),
    "mec": (140, 230, 100),
}

# power-ups: notas especiales durante el gameplay que dan efectos temporales
POWER_UPS = [
    {"id": "estrella", "nombre": "AUTO",  "dur": 6000,  "color": (255, 255, 100)},
    {"id": "vida",     "nombre": "VIDA",  "dur": 0,     "color": (255, 100, 100)},
    {"id": "reloj",    "nombre": "LENTO", "dur": 8000,  "color": (100, 200, 255)},
    {"id": "doble",    "nombre": "x2",    "dur": 10000, "color": (100, 255, 100)},
]

def generar_ofertas_perks(rng, perks_actuales):
    """Elige 3 perks distintos para ofrecer, excluyendo los que ya tiene
    (excepto 'multi' que es acumulable)."""
    ids_tiene = {p["id"] for p in perks_actuales if p["id"] != "multi"}
    pool = [p for p in PERKS if p["id"] not in ids_tiene]
    if len(pool) < 3:
        pool = list(PERKS)  # fallback si ya tiene casi todos
    return rng.sample(pool, min(3, len(pool)))

# --- modo STAGES (tipo roguelike): completar generos en cada dificultad ---
# cada run son 4 stages del mismo genero+dificultad:
#   stage 1: sin mods | stage 2: 1 mod facil | stage 3: 1 mod facil | stage 4: sudden death
NUM_STAGES = 4
run_actual = None   # dict con estado del run, o None

fuente_grande = pygame.font.SysFont("courier", 48, bold=True)
fuente        = pygame.font.SysFont("courier", 24, bold=True)
fuente_chica  = pygame.font.SysFont("courier", 14, bold=True)

SR = 44100

def np_to_sound(samples_mono, vol=0.7, pan=0.0, lpf=False):
    """Convierte array numpy mono a pygame.Sound stereo.
    pan: -1.0 = todo izquierda, 0 = centro, 1.0 = todo derecha
    lpf: aplica filtro pasa-bajos para domar agudos"""
    if lpf:
        n = len(samples_mono)
        if n > 64:
            # LPF FIR vectorizado (promedio movil ponderado) - rapido con numpy
            k = 9  # taps; mas = corte mas bajo
            kernel = np.hanning(k)
            kernel /= kernel.sum()
            samples_mono = np.convolve(samples_mono, kernel, mode="same")
    scaled = samples_mono * vol
    # soft clipping con tanh: comprime picos suavemente en vez de cortarlos.
    # techo en 0.68 (antes 0.75) para dejar headroom cuando varios sonidos
    # se superponen en el mixer y evitar el clipeo de la suma.
    scaled = np.tanh(scaled * 1.5) * 0.68
    base = scaled * 32767
    # ganancia por canal con ley de paneo de potencia constante
    ang = (pan + 1) * 0.25 * np.pi  # 0..pi/2
    gL = np.cos(ang)
    gR = np.sin(ang)
    left  = np.clip(base * gL, -32768, 32767).astype(np.int16)
    right = np.clip(base * gR, -32768, 32767).astype(np.int16)
    stereo = np.column_stack((left, right))
    return pygame.sndarray.make_sound(stereo)

EQ_TIPOS = ["bright", "warm", "dark", "crisp", "hollow", "nasal"]
def aplicar_eq(wave, eq_type, intensity=0.5):
    """Aplica EQ sutil al array de audio"""
    original_peak = np.max(np.abs(wave))
    if original_peak == 0:
        return wave
    if eq_type == "bright":
        lp = np.zeros(len(wave))
        coef = 0.6
        lp[0] = wave[0]
        for i in range(1, len(wave)):
            lp[i] = coef * lp[i-1] + (1 - coef) * wave[i]
        wave = wave + (wave - lp) * intensity * 0.3
    elif eq_type == "warm":
        coef = 0.5 + intensity * 0.15
        out = np.zeros(len(wave))
        out[0] = wave[0]
        for i in range(1, len(wave)):
            out[i] = coef * out[i-1] + (1 - coef) * wave[i]
        wave = wave * (1 - intensity * 0.4) + out * intensity * 0.4
    elif eq_type == "dark":
        coef = 0.5 + intensity * 0.2
        out = np.zeros(len(wave))
        out[0] = wave[0]
        for i in range(1, len(wave)):
            out[i] = coef * out[i-1] + (1 - coef) * wave[i]
        wave = wave * (1 - intensity * 0.5) + out * intensity * 0.5
    elif eq_type == "crisp":
        diff = np.zeros(len(wave))
        diff[1:] = wave[1:] - wave[:-1]
        wave = wave + diff * intensity * 1.5
    elif eq_type == "hollow":
        lp = np.zeros(len(wave))
        coef = 0.75
        lp[0] = wave[0]
        for i in range(1, len(wave)):
            lp[i] = coef * lp[i-1] + (1 - coef) * wave[i]
        hp = wave - lp
        wave = lp * 0.7 + hp * 0.9
    elif eq_type == "nasal":
        freq_res = 1000 + intensity * 1500
        coef = freq_res / SR
        bp = 0.0
        lp = 0.0
        out = np.zeros(len(wave))
        for i in range(len(wave)):
            hp = wave[i] - lp - 0.4 * bp
            bp += coef * hp
            lp += coef * bp
            out[i] = wave[i] + bp * intensity * 0.5
        wave = out
    peak = np.max(np.abs(wave))
    if peak > 0:
        wave = wave / peak * original_peak
    return np.clip(wave, -1, 1)

# ═══════════════════════════════════════════════════ >>SYNTH_DRUMS<< ═══

def synth_kick(rng):
    dur = rng.uniform(0.15, 0.4)
    freq_start = rng.uniform(120, 300)
    freq_end = rng.uniform(30, 60)
    drive = rng.uniform(0.0, 0.5)
    n = int(SR * dur)
    t = np.linspace(0, dur, n)
    env = np.exp(-t * rng.uniform(5, 15))
    freq = freq_start * np.exp(-t * np.log(freq_start / freq_end) / dur)
    phase = np.cumsum(freq / SR) * 2 * np.pi
    wave = np.sin(phase) * env
    if drive > 0:
        wave = np.tanh(wave * (1 + drive * 5))
    return np_to_sound(wave, vol=0.9)

def synth_snare(rng):
    dur = rng.uniform(0.1, 0.3)
    tone_freq = rng.uniform(150, 280)
    n = int(SR * dur)
    t = np.linspace(0, dur, n)
    tone_env = np.exp(-t * rng.uniform(20, 50))
    tone = np.sin(2 * np.pi * tone_freq * t) * tone_env * 0.6
    noise_env = np.exp(-t * rng.uniform(8, 20))
    np_rng = np.random.RandomState(rng.randint(0, 999999))
    noise = np_rng.uniform(-1, 1, n) * noise_env * 0.7
    return np_to_sound(tone + noise, vol=0.9)

def synth_hihat(rng, abierto=False):
    dur = rng.uniform(0.08, 0.25) if abierto else rng.uniform(0.02, 0.08)
    n = int(SR * dur)
    t = np.linspace(0, dur, n)
    env = np.exp(-t * rng.uniform(10, 40))
    np_rng = np.random.RandomState(rng.randint(0, 999999))
    noise = np_rng.uniform(-1, 1, n)
    hp = rng.uniform(0.85, 0.98)
    filtered = np.zeros(n)
    filtered[0] = noise[0]
    for i in range(1, n):
        filtered[i] = hp * (filtered[i-1] + noise[i] - noise[i-1])
    return np_to_sound(filtered * env)

def synth_clap(rng):
    dur = rng.uniform(0.12, 0.25)
    n_bursts = rng.randint(2, 5)
    n = int(SR * dur)
    t = np.linspace(0, dur, n)
    np_rng = np.random.RandomState(rng.randint(0, 999999))
    wave = np.zeros(n)
    for b in range(n_bursts):
        offset = int(b * SR * rng.uniform(0.008, 0.02))
        burst_len = int(SR * rng.uniform(0.005, 0.015))
        if offset + burst_len < n:
            noise = np_rng.uniform(-1, 1, burst_len)
            wave[offset:offset+burst_len] += noise * 0.5
    env = np.exp(-t * rng.uniform(8, 18))
    tail_noise = np_rng.uniform(-1, 1, n)
    wave += tail_noise * env * 0.4
    return np_to_sound(wave)

def synth_clave(rng):
    # rango de frecuencia realista para clave (antes 800-2500 Hz llegaba a un
    # "bing" agudo de campanilla; una clave real esta entre 1000-1800 Hz)
    dur = rng.uniform(0.03, 0.07)
    freq = rng.uniform(1000, 1800)
    n = int(SR * dur)
    t = np.linspace(0, dur, n)
    env = np.exp(-t * rng.uniform(35, 70))
    # fade-out corto para evitar click al cortar
    fade = min(int(SR * 0.003), n // 4)
    if fade > 0:
        env[-fade:] *= np.linspace(1, 0, fade)
    wave = np.sin(2 * np.pi * freq * t) * env
    return np_to_sound(wave)

def synth_crash(rng):
    dur = rng.uniform(0.5, 1.5)
    n = int(SR * dur)
    t = np.linspace(0, dur, n)
    env = np.exp(-t * rng.uniform(1.5, 4))
    np_rng = np.random.RandomState(rng.randint(0, 999999))
    noise = np_rng.uniform(-1, 1, n)
    bp = rng.uniform(0.6, 0.9)
    filtered = np.zeros(n)
    for i in range(1, n):
        filtered[i] = bp * filtered[i-1] + (1-bp) * noise[i]
    return np_to_sound(filtered * env * 0.6)

def synth_agogo(rng):
    # agogo realista: campana grave 700-1100 Hz, segundo parcial max x1.5
    # (antes freq2 llegaba a 2700 Hz con decay lento = "biiing" agudo molesto)
    dur = rng.uniform(0.08, 0.2)
    freq1 = rng.uniform(700, 1100)
    freq2 = freq1 * rng.uniform(1.25, 1.5)
    n = int(SR * dur)
    t = np.linspace(0, dur, n)
    env = np.exp(-t * rng.uniform(20, 40))
    # fade-out anti-click
    fade = min(int(SR * 0.004), n // 4)
    if fade > 0:
        env[-fade:] *= np.linspace(1, 0, fade)
    # el parcial agudo decae mas rapido que el fundamental (campana real)
    env2 = np.exp(-t * rng.uniform(35, 60))
    if fade > 0:
        env2[-fade:] *= np.linspace(1, 0, fade)
    wave = (np.sin(2 * np.pi * freq1 * t) * 0.6 * env
            + np.sin(2 * np.pi * freq2 * t) * 0.35 * env2)
    return np_to_sound(wave)

def synth_tom(rng):
    dur = rng.uniform(0.1, 0.35)
    freq_start = rng.uniform(180, 400)
    freq_end = rng.uniform(60, 150)
    n = int(SR * dur)
    t = np.linspace(0, dur, n)
    env = np.exp(-t * rng.uniform(6, 18))
    freq = freq_start * np.exp(-t * np.log(freq_start / freq_end) / dur)
    phase = np.cumsum(freq / SR) * 2 * np.pi
    wave = np.sin(phase) * env
    return np_to_sound(wave)

def sintetizar_kit(rng):
    """Genera un kit de batería completo proceduralmente"""
    print("  Sintetizando kit...")
    kit_eq = rng.choice(EQ_TIPOS)
    # intensidad bajada de 0.15-0.40 a 0.08-0.22: el kit sigue teniendo caracter
    # pero deja de correr riesgo de quedar en franja espectral opuesta al
    # instrumento del jugador (que tambien vamos a bajar). Mejor mezcla total.
    kit_intensity = rng.uniform(0.08, 0.22)
    kit = {}
    kit["kick"]    = synth_kick(rng)
    kit["snare"]   = synth_snare(rng)
    kit["hihat"]   = synth_hihat(rng, abierto=False)
    kit["hihat_o"] = synth_hihat(rng, abierto=True)
    kit["clap"]    = synth_clap(rng)
    kit["clave"]   = synth_clave(rng)
    kit["crash"]   = synth_crash(rng)
    kit["agogo"]   = synth_agogo(rng)
    kit["tom1"]    = synth_tom(rng)
    kit["tom2"]    = synth_tom(rng)
    for key in kit:
        if kit[key]:
            arr = pygame.sndarray.array(kit[key]).astype(np.float64) / 32767
            mono = arr[:, 0]
            mono = aplicar_eq(mono, kit_eq, kit_intensity)
            kit[key] = np_to_sound(mono)
    print(f"    EQ: {kit_eq} ({kit_intensity:.1f})")
    return kit

print("Renderizando notas...")

# ═════════════════════════════════════════════════════ >>SYNTH_SFX<< ═══

def synth_error():
    """Sonido de error: buzz grave descendente, disonante"""
    dur = 0.18
    n = int(SR * dur)
    t = np.linspace(0, dur, n)
    # dos tonos disonantes que bajan de pitch
    f1 = 180 * np.exp(-t * 3)
    f2 = 190 * np.exp(-t * 3)
    ph1 = np.cumsum(f1 / SR) * 2 * np.pi
    ph2 = np.cumsum(f2 / SR) * 2 * np.pi
    wave = np.sign(np.sin(ph1)) * 0.5 + np.sign(np.sin(ph2)) * 0.5
    env = np.exp(-t * 8)
    fade = min(int(SR * 0.005), n)
    env[-fade:] *= np.linspace(1, 0, fade)
    return np_to_sound(wave * env, vol=0.35)

SND_ERROR = synth_error()

def synth_explosion(potencia=1.0):
    """Sonido de explosion: ruido filtrado con boom grave y cola."""
    dur = 0.5 + potencia * 0.3
    n = int(SR * dur)
    t = np.linspace(0, dur, n)
    f_boom = (90 + potencia * 30) * np.exp(-t * 4)
    ph = np.cumsum(f_boom / SR) * 2 * np.pi
    boom = np.sin(ph) * np.exp(-t * 5)
    np_rng = np.random.RandomState(int(potencia * 1000) % 99999)
    noise = np_rng.uniform(-1, 1, n)
    lp = np.zeros(n); s = 0.0
    co = 0.08
    for i in range(n):
        s += co * (noise[i] - s)
        lp[i] = s
    noise_env = np.exp(-t * 7)
    wave = boom * 0.7 + lp * noise_env * 0.5
    fade = min(int(SR * 0.02), n)
    wave[-fade:] *= np.linspace(1, 0, fade)
    return np_to_sound(wave, vol=0.5)

def synth_fanfarria_win():
    """Fanfarria de victoria: arpegio ascendente mayor + acorde final brillante."""
    notas_arp = [523, 659, 784, 1047]  # C5 E5 G5 C6
    dur_nota = 0.12
    dur_final = 0.9
    partes = []
    for f in notas_arp:
        n = int(SR * dur_nota)
        t = np.linspace(0, dur_nota, n)
        ph = 2 * np.pi * f * t
        w = np.sin(ph) * 0.5 + np.sin(ph * 2) * 0.25 + np.sin(ph * 3) * 0.12
        env = np.minimum(1.0, np.exp(-t * 2) + 0.5)
        partes.append(w * env)
    n_f = int(SR * dur_final)
    t_f = np.linspace(0, dur_final, n_f)
    acorde = np.zeros(n_f)
    for f in [523, 659, 784, 1047]:
        ph = 2 * np.pi * f * t_f
        acorde += np.sin(ph) * 0.4 + np.sin(ph * 2) * 0.15 + np.sin(ph * 3) * 0.06
    acorde /= 4
    vib = 1 + 0.01 * np.sin(2 * np.pi * 5 * t_f)
    acorde *= vib
    env_f = np.minimum(1.0, np.exp(-t_f * 1.2) + 0.4)
    fade = min(int(SR * 0.05), n_f)
    env_f[-fade:] *= np.linspace(1, 0, fade)
    partes.append(acorde * env_f)
    wave = np.concatenate(partes)
    return np_to_sound(wave, vol=0.45)

def synth_ui_select():
    """Beep corto de navegacion de menu."""
    dur = 0.06
    n = int(SR * dur)
    t = np.linspace(0, dur, n)
    wave = np.sin(2 * np.pi * 660 * t) * 0.5 + np.sin(2 * np.pi * 1320 * t) * 0.2
    env = np.exp(-t * 30)
    fade = min(int(SR * 0.005), n)
    env[-fade:] *= np.linspace(1, 0, fade)
    return np_to_sound(wave * env, vol=0.3)

def synth_ui_confirm():
    """Sonido de confirmacion: dos tonos ascendentes."""
    dur = 0.18
    n = int(SR * dur)
    t = np.linspace(0, dur, n)
    mitad = n // 2
    f = np.ones(n) * 660
    f[mitad:] = 880
    ph = np.cumsum(f / SR) * 2 * np.pi
    wave = np.sin(ph) * 0.5 + np.sin(ph * 2) * 0.15
    env = np.minimum(1.0, np.exp(-t * 6) + 0.3)
    fade = min(int(SR * 0.01), n)
    env[-fade:] *= np.linspace(1, 0, fade)
    return np_to_sound(wave * env, vol=0.32)

# ─── SFX de power-ups: uno unico por tipo, comunican el efecto ───

def synth_pu_estrella():
    """AUTO: arpegio ascendente shimmer + campana metalica = invencibilidad."""
    dur = 0.55
    n = int(SR * dur)
    t = np.linspace(0, dur, n)
    # arpegio muy rapido: 4 notas ascendentes
    notas_f = [880, 1108, 1318, 1760]   # A5 C#6 E6 A6 (mayor)
    seg = n // len(notas_f)
    wave = np.zeros(n)
    for i, f in enumerate(notas_f):
        s0 = i * seg
        s1 = min(n, s0 + int(seg * 1.6))
        tseg = t[s0:s1] - t[s0]
        # cada nota es una senoide + su octava (brillo) + campana (5x)
        w = (np.sin(2 * np.pi * f * tseg) * 0.5
             + np.sin(2 * np.pi * f * 2 * tseg) * 0.25
             + np.sin(2 * np.pi * f * 5.4 * tseg) * 0.10)
        env_seg = np.exp(-tseg * 4)
        wave[s0:s1] += w * env_seg
    # shimmer general
    wave *= (1.0 + 0.2 * np.sin(2 * np.pi * 12 * t))
    env = np.exp(-t * 1.8)
    fade = min(int(SR * 0.01), n)
    env[-fade:] *= np.linspace(1, 0, fade)
    return np_to_sound(wave * env, vol=0.42)

def synth_pu_vida():
    """+HP: dos pitidos ascendentes rapidos = health up (clasico de arcade)."""
    dur = 0.32
    n = int(SR * dur)
    t = np.linspace(0, dur, n)
    m1 = int(n * 0.35)
    m2 = int(n * 0.45)
    # dos pitidos con silencio breve entre ellos
    f = np.ones(n) * 660  # E5
    f[m1:m2] = 0          # silencio
    f[m2:] = 990          # B5 (arriba)
    ph = np.cumsum(f / SR) * 2 * np.pi
    wave = np.sin(ph) * 0.5 + np.sin(ph * 2) * 0.15
    # envolvente de dos golpes
    env = np.zeros(n)
    for s0, s1 in [(0, m1), (m2, n)]:
        seg_t = np.linspace(0, 1, s1 - s0)
        env[s0:s1] = np.exp(-seg_t * 8)
    fade = min(int(SR * 0.008), n)
    env[-fade:] *= np.linspace(1, 0, fade)
    return np_to_sound(wave * env, vol=0.4)

def synth_pu_reloj():
    """SLOW: sweep descendente con vibrato lento = el tiempo se estira."""
    dur = 0.55
    n = int(SR * dur)
    t = np.linspace(0, dur, n)
    # freq baja de 700Hz a 250Hz con curva exponencial
    f_base = 700 * np.exp(-t * 1.8) + 200
    # vibrato lento (5Hz) creciente = sensacion de "estirarse"
    vibrato = 1.0 + 0.05 * np.sin(2 * np.pi * 5 * t) * (t / dur)
    f = f_base * vibrato
    ph = np.cumsum(f / SR) * 2 * np.pi
    wave = np.sin(ph) * 0.5 + np.sin(ph * 1.5) * 0.2   # 1.5x = disonancia suave
    env = np.exp(-t * 2.5) * (1.0 - 0.3 * t / dur)
    fade = min(int(SR * 0.015), n)
    env[-fade:] *= np.linspace(1, 0, fade)
    return np_to_sound(wave * env, vol=0.4)

def synth_pu_doble():
    """x2: dos notas separadas por octava sonando juntas = duplicacion."""
    dur = 0.4
    n = int(SR * dur)
    t = np.linspace(0, dur, n)
    f_grave = 440    # A4
    f_agudo = 880    # A5 (octava exacta)
    ph1 = 2 * np.pi * f_grave * t
    ph2 = 2 * np.pi * f_agudo * t
    # ambas ondas juntas + un tremolo lento que las "separa" ritmicamente
    trem = 0.75 + 0.25 * np.sin(2 * np.pi * 6 * t)
    wave = (np.sin(ph1) * 0.4 + np.sin(ph1 * 2) * 0.12
            + (np.sin(ph2) * 0.4 + np.sin(ph2 * 2) * 0.12) * trem)
    env = np.exp(-t * 3.5)
    fade = min(int(SR * 0.012), n)
    env[-fade:] *= np.linspace(1, 0, fade)
    return np_to_sound(wave * env, vol=0.42)

SND_PU = {
    "estrella": synth_pu_estrella(),
    "vida":     synth_pu_vida(),
    "reloj":    synth_pu_reloj(),
    "doble":    synth_pu_doble(),
}

def sfx_power_up(pu_id):
    snd = SND_PU.get(pu_id)
    if snd:
        snd.set_volume(0.55 * config["volumen"])
        snd.play()

def synth_game_over():
    """Sonido de game over: acorde menor descendente, sombrio."""
    notas = [392, 311, 233]  # G4 Eb4 Bb3 descendente
    dur_nota = 0.28
    dur_final = 1.2
    partes = []
    for f in notas:
        n = int(SR * dur_nota)
        t = np.linspace(0, dur_nota, n)
        ph = 2 * np.pi * f * t
        w = np.sin(ph) * 0.5 + np.sin(ph * 1.005) * 0.3 + np.sin(ph * 2) * 0.1
        env = np.minimum(1.0, np.exp(-t * 3) + 0.4)
        partes.append(w * env)
    n_f = int(SR * dur_final)
    t_f = np.linspace(0, dur_final, n_f)
    acorde = np.zeros(n_f)
    for f in [233, 277, 349]:  # acorde grave menor
        ph = 2 * np.pi * f * t_f
        acorde += np.sin(ph) * 0.4 + np.sin(ph * 1.006) * 0.2
    acorde /= 3
    env_f = np.exp(-t_f * 1.5)
    fade = min(int(SR * 0.05), n_f)
    env_f[-fade:] *= np.linspace(1, 0, fade)
    partes.append(acorde * env_f)
    wave = np.concatenate(partes)
    return np_to_sound(wave, vol=0.42)

def synth_dado_tick():
    """Tick corto y seco para el dado girando (estilo clic de ruleta)."""
    dur = 0.04
    n = int(SR * dur)
    t = np.linspace(0, dur, n)
    # click: pulso de ruido + tono corto agudo
    np_rng = np.random.RandomState(7)
    noise = np_rng.uniform(-1, 1, n) * np.exp(-t * 120)
    tono = np.sin(2 * np.pi * 1200 * t) * np.exp(-t * 80)
    wave = noise * 0.4 + tono * 0.5
    return np_to_sound(wave, vol=0.25)

def synth_hit(freq_base=900, brillo=1.0):
    """Ping cristalino ascendente para un acierto perfecto."""
    dur = 0.14
    n = int(SR * dur)
    t = np.linspace(0, dur, n)
    # pitch sube levemente durante la nota (sensacion de 'lift')
    f = freq_base * (1 + 0.15 * t / dur)
    ph = np.cumsum(f / SR) * 2 * np.pi
    # fundamental + armonicos brillantes (campana cristalina)
    wave = (np.sin(ph) * 0.5
            + np.sin(ph * 2) * 0.25 * brillo
            + np.sin(ph * 3) * 0.12 * brillo
            + np.sin(ph * 4.2) * 0.06 * brillo)
    env = np.exp(-t * 22)
    fade = min(int(SR * 0.006), n)
    env[-fade:] *= np.linspace(1, 0, fade)
    return np_to_sound(wave * env, vol=0.3)

def synth_hit_soft(freq_base=600):
    """Click suave y redondo para un acierto BIEN/OK."""
    dur = 0.09
    n = int(SR * dur)
    t = np.linspace(0, dur, n)
    ph = 2 * np.pi * freq_base * t
    wave = np.sin(ph) * 0.6 + np.sin(ph * 2) * 0.15
    env = np.exp(-t * 30)
    fade = min(int(SR * 0.005), n)
    env[-fade:] *= np.linspace(1, 0, fade)
    return np_to_sound(wave * env, vol=0.25)

def synth_combo(nivel=1):
    """Arpegio ascendente para un milestone de combo. Sube de tono con el nivel."""
    # base sube con el nivel de milestone (10x, 20x, ...)
    semis = min((nivel - 1) * 2, 12)   # cada milestone +2 semitonos, tope +1 octava
    base = 523 * (2 ** (semis / 12.0))  # desde C5
    notas = [base, base * 1.26, base * 1.5, base * 2.0]  # mayor + octava
    dur_nota = 0.07
    partes = []
    for f in notas:
        n = int(SR * dur_nota)
        t = np.linspace(0, dur_nota, n)
        ph = 2 * np.pi * f * t
        w = np.sin(ph) * 0.5 + np.sin(ph * 2) * 0.2
        env = np.exp(-t * 12)
        partes.append(w * env)
    wave = np.concatenate(partes)
    return np_to_sound(wave, vol=0.35)

SND_SELECT = synth_ui_select()
SND_CONFIRM = synth_ui_confirm()
SND_DADO = synth_dado_tick()
SND_EXPLOSION = synth_explosion(1.0)
SND_EXPLOSION_BIG = synth_explosion(2.0)
SND_WIN = synth_fanfarria_win()
SND_GAMEOVER = synth_game_over()
# hits: variantes de pitch para que suba con el combo (cacheadas)
SND_HIT_PERFECT = [synth_hit(900 * (2 ** (i / 12.0)), brillo=1.0) for i in range(8)]
SND_HIT_GOOD = synth_hit_soft(600)
# combos: un sonido por milestone (10x..80x)
SND_COMBO = [synth_combo(i) for i in range(1, 9)]

def sfx_hit_perfect(combo):
    # el pitch sube por tramos de combo
    idx = min(combo // 8, len(SND_HIT_PERFECT) - 1)
    s = SND_HIT_PERFECT[idx]
    s.set_volume(0.35 * config["volumen"])
    s.play()

def sfx_hit_good():
    SND_HIT_GOOD.set_volume(0.28 * config["volumen"])
    SND_HIT_GOOD.play()

def sfx_combo(combo):
    nivel = combo // 10   # 1 para 10x, 2 para 20x...
    idx = min(nivel - 1, len(SND_COMBO) - 1)
    if idx >= 0:
        s = SND_COMBO[idx]
        s.set_volume(0.4 * config["volumen"])
        s.play()

def sfx_select():
    SND_SELECT.set_volume(0.4 * config["volumen"])
    SND_SELECT.play()

def sfx_confirm():
    SND_CONFIRM.set_volume(0.45 * config["volumen"])
    SND_CONFIRM.play()

INSTRUMENTOS_JUGADOR = {
    "SQUARE":    "square",
    "SAW":       "saw",
    "SINE":      "sine",
    "TRIANGLE":  "triangle",
    "FM BELL":   "fm_bell",
    "PLUCK":     "pluck",
    "ORGAN":     "organ",
    "CHIPTUNE":  "chiptune",
    "SUPERSAW":  "supersaw",
    "ACID":      "acid",
    "LEAD":      "lead",
    "WOBBLE":    "wobble",
    "GLASS":     "glass",
    "PAD":       "pad",
    "METALLIC":  "metallic",
    "BASS":      "bass",
    "FLUTE":     "flute",
    "RESO":      "reso",
    "CHOIR":     "choir",
    "VIBRAPHONE": "vibraphone",
    "SITAR":      "sitar",
    "KALIMBA":    "kalimba",
    "TRUMPET":    "trumpet",
    "HARP":       "harp",
    "SYNTHBASS":  "synthbass",
    "BELLPAD":    "bellpad",
    "DETUNE":     "detune",
    "PWM LEAD":   "pwm_lead",
    "FM EP":      "fm_ep",
    "FORMANT":    "formant",
    "HOOVER":     "hoover",
    "BELL FM":    "bell_fm",
    "GROWL":      "growl",
    "SAW STACK":  "saw_stack",
    "FM 3OP":     "fm_3op",
    "SYNC LEAD":  "sync_lead",
    "PLUCK SOFT": "pluck_soft",
    "VOX PAD":    "vox_pad",
    "DIST GTR":   "dist_gtr",
    "PHASE PAD":  "phase_pad",
    "FM BRASS":   "fm_brass",
    "GLASS HARM": "glass_harm",
    "SUB PLUCK":  "sub_pluck",
    "NOISE PITCH":"noise_pitch",
    "ORGAN FULL": "organ_full",
    "ATMOS NOISE":"atmos_noise",
    "FROZEN STR": "frozen_strings",
    "DREAM PAD":  "dream_pad",
    "SPACE CHOIR":"space_choir",
    "ANALOG STR": "analog_string",
}

# instrumentos raros: baja probabilidad de aparecer
INSTRUMENTOS_RAROS = {
}

# instrumentos que sostienen bien (se pueden loopear en holds)
# los demas tienen decay natural y se cortan antes de repetirse
INST_SUSTAIN = {
    "SAW", "ORGAN", "PAD", "SUPERSAW", "CHOIR", "SAW STACK", "HOOVER",
    "VOX PAD", "PHASE PAD", "BELLPAD", "PWM LEAD", "LEAD", "WOBBLE",
    "ORGAN FULL", "FM BRASS", "DETUNE", "SINE", "TRIANGLE", "GROWL",
    "SYNTHBASS", "DIST GTR",
    "ATMOS NOISE", "FROZEN STR", "DREAM PAD", "SPACE CHOIR", "ANALOG STR",
}
# hold maximo para instrumentos percusivos (ms)
HOLD_MAX_PERCUSIVO = 800
HOLD_MAX = 6000  # holds largos: la nota de 1.6s loopea para cubrirlos

# --- identidad visual: cada instrumento tiene una "forma" para su icono y notas ---
# formas: square, saw, sine, triangle, bell, pluck, pad, metal, noise, glass,
#         brass, choir, atmos, alien
INST_FORMA = {
    "SQUARE": "square", "CHIPTUNE": "square", "PWM LEAD": "square",
    "SAW": "saw", "SUPERSAW": "saw", "SAW STACK": "saw", "HOOVER": "saw",
    "ACID": "saw", "SYNC LEAD": "saw", "DETUNE": "saw", "ANALOG STR": "saw",
    "SINE": "sine", "FM EP": "sine", "SUB PLUCK": "sine", "SYNTHBASS": "sine", "BASS": "sine",
    "TRIANGLE": "triangle", "LEAD": "triangle", "FLUTE": "triangle",
    "FM BELL": "bell", "BELL FM": "bell", "BELLPAD": "bell", "VIBRAPHONE": "bell", "KALIMBA": "bell",
    "PLUCK": "pluck", "PLUCK SOFT": "pluck", "HARP": "pluck", "SITAR": "pluck",
    "PAD": "pad", "PHASE PAD": "pad", "VOX PAD": "pad", "DREAM PAD": "pad", "FROZEN STR": "pad",
    "METALLIC": "metal", "RESO": "metal", "NOISE PITCH": "metal",
    "GLASS": "glass", "GLASS HARM": "glass",
    "ORGAN": "organ", "ORGAN FULL": "organ",
    "TRUMPET": "brass", "FM BRASS": "brass", "GROWL": "brass", "DIST GTR": "brass",
    "CHOIR": "choir", "SPACE CHOIR": "choir", "FORMANT": "choir",
    "WOBBLE": "wobble", "FM 3OP": "wobble",
    "ATMOS NOISE": "atmos",
}

def dibujar_icono_inst(surf, forma, cx, cy, r, color):
    """Dibuja el icono de un instrumento centrado en (cx, cy) con radio r."""
    if forma == "square":
        pygame.draw.rect(surf, color, (cx - r, cy - r, r * 2, r * 2), 2)
        pygame.draw.rect(surf, color, (cx - r//2, cy - r//2, r, r))
    elif forma == "saw":
        pts = []
        for i in range(5):
            x = cx - r + (i / 4) * 2 * r
            y = cy + r if i % 2 == 0 else cy - r
            pts.append((x, y))
        pygame.draw.lines(surf, color, False, pts, 2)
    elif forma == "sine":
        pts = [(cx - r + i, cy - int(math.sin(i / r * math.pi * 2) * r)) for i in range(0, 2 * r, 2)]
        if len(pts) > 1:
            pygame.draw.lines(surf, color, False, pts, 2)
    elif forma == "triangle":
        pygame.draw.polygon(surf, color, [(cx, cy - r), (cx - r, cy + r), (cx + r, cy + r)], 2)
    elif forma == "bell":
        pygame.draw.arc(surf, color, (cx - r, cy - r, 2 * r, 2 * r), math.pi, 2 * math.pi, 2)
        pygame.draw.line(surf, color, (cx - r, cy), (cx + r, cy), 2)
        pygame.draw.circle(surf, color, (cx, cy + r), 2)
    elif forma == "pluck":
        pygame.draw.line(surf, color, (cx, cy - r), (cx, cy + r), 2)
        pygame.draw.circle(surf, color, (cx, cy - r), 3)
        pygame.draw.arc(surf, color, (cx, cy - r//2, r, r), -math.pi/2, math.pi/2, 2)
    elif forma == "pad":
        pygame.draw.ellipse(surf, color, (cx - r, cy - r//2, 2 * r, r), 2)
        pygame.draw.ellipse(surf, color, (cx - r//2, cy - r, r, 2 * r), 1)
    elif forma == "metal":
        for a in range(0, 360, 60):
            x = cx + int(math.cos(math.radians(a)) * r)
            y = cy + int(math.sin(math.radians(a)) * r)
            pygame.draw.line(surf, color, (cx, cy), (x, y), 2)
        pygame.draw.circle(surf, color, (cx, cy), 3)
    elif forma == "glass":
        pygame.draw.polygon(surf, color, [(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)], 2)
        pygame.draw.line(surf, color, (cx, cy - r), (cx, cy + r), 1)
    elif forma == "organ":
        for i, h in enumerate([r, int(r*1.5), r]):
            x = cx - r + i * r
            pygame.draw.line(surf, color, (x, cy + r), (x, cy + r - h), 3)
    elif forma == "brass":
        pygame.draw.circle(surf, color, (cx + r//2, cy), r, 2)
        pygame.draw.line(surf, color, (cx - r, cy), (cx, cy), 2)
        pygame.draw.line(surf, color, (cx - r, cy - 3), (cx - r, cy + 3), 2)
    elif forma == "choir":
        for dx in (-r, 0, r):
            pygame.draw.arc(surf, color, (cx + dx - r//2, cy - r, r, 2 * r), math.pi/2, 3*math.pi/2, 2)
    elif forma == "wobble":
        pts = [(cx - r + i, cy - int(math.sin(i / r * math.pi * 3) * r * (0.4 + 0.6 * i / (2*r)))) for i in range(0, 2 * r, 2)]
        if len(pts) > 1:
            pygame.draw.lines(surf, color, False, pts, 2)
    elif forma == "atmos":
        for rad in (r, int(r*0.6), int(r*0.3)):
            pygame.draw.circle(surf, color, (cx, cy), rad, 1)
    elif forma == "alien":
        pygame.draw.ellipse(surf, color, (cx - r, cy - r//2, 2*r, r), 2)
        pygame.draw.circle(surf, color, (cx - r//3, cy), 2)
        pygame.draw.circle(surf, color, (cx + r//3, cy), 2)
    else:
        pygame.draw.circle(surf, color, (cx, cy), r, 2)

def forma_de_instrumento(inst):
    return INST_FORMA.get(inst, "sine")


# ═══════════════════════════════════════════════════ >>SYNTH_INST<< ═══

def midi_a_freq(midi):
    return 440.0 * (2.0 ** ((midi - 69) / 12.0))

_hpf_mask_cache = {}
def filtro_hpf(wave, cutoff_hz=130):
    """HPF (filtro pasa-altos) que quita el rumor sub-grave del sample
    melodico del jugador. En electronica el rango debajo de ~130Hz es
    territorio del kick y del bajo: cualquier contenido melodico ahi genera
    lodo espectral que enturbia la mezcla. Al filtrarlo, las notas del jugador
    ocupan claramente el rango medio-agudo, el bajo el rango grave, y ambos
    dejan de competir por el mismo espacio.

    Implementacion: HPF en dominio frecuencia via rfft (O(n log n), preciso).
    Un HPF FIR con pocos taps no corta bien a 130Hz (necesitaria cientos de
    taps); esta version es exacta y mas rapida. Usa una rampa suave de 60Hz
    alrededor del cutoff para evitar ringing/pre-echo del corte brickwall.
    La mascara se cachea por (n, cutoff) para no recalcularla en cada llamada."""
    n = len(wave)
    if n < 100:
        return wave
    key = (n, cutoff_hz)
    if key not in _hpf_mask_cache:
        freqs = np.fft.rfftfreq(n, 1.0 / SR)
        fade = 60.0
        _hpf_mask_cache[key] = np.clip(
            (freqs - (cutoff_hz - fade / 2)) / fade, 0.0, 1.0)
    mask = _hpf_mask_cache[key]
    W = np.fft.rfft(wave)
    return np.fft.irfft(W * mask, n)

def reverb_ambiente(wave, mezcla=0.20):
    """Aplica una reverb corta de sala compartida (early reflections).
    3 taps con LPF suave (absorcion en agudos, como en una sala real). Se usa
    con los mismos parametros sobre bajo y notas del jugador para que ambos
    'vivan' en el mismo espacio virtual: eso los pega perceptualmente y hace
    que dejen de sonar como capas aisladas."""
    n = len(wave)
    if n < 400:
        return wave
    # 3 delays cortos (early reflections). Los tiempos NO son multiplos entre
    # si para evitar comb-filtering audible. Ganancia decreciente en el
    # tiempo, como el decay natural de una sala.
    delays_ms = [27, 45, 75]
    ganancias = [0.32, 0.20, 0.12]
    # LPF una sola vez sobre toda la wave (mas rapido que uno por tap):
    # simula la absorcion de agudos que hacen las paredes.
    kernel = np.hanning(7)
    kernel /= kernel.sum()
    dark = np.convolve(wave, kernel, mode="same")
    tail = np.zeros(n)
    for d_ms, g in zip(delays_ms, ganancias):
        d = int(SR * d_ms / 1000)
        if d < n:
            tail[d:] += dark[:n - d] * g
    return wave * (1 - mezcla) + tail * mezcla

def synth_bajo(freq, duracion, estilo="round"):
    """Sintetiza una nota de bajo. estilo: round, pluck, sub, reese"""
    n = int(SR * duracion)
    t = np.linspace(0, duracion, n)
    phase = 2 * np.pi * freq * t
    if estilo == "round":
        # sine + 2do armonico suave
        wave = np.sin(phase) * 0.8 + np.sin(phase * 2) * 0.15
        env = np.minimum(1.0, np.exp(-t * 1.5) + 0.3)
    elif estilo == "pluck":
        # ataque rapido con decay
        wave = np.sign(np.sin(phase)) * 0.4 + np.sin(phase) * 0.6
        env = np.exp(-t * 4)
    elif estilo == "sub":
        # casi pura sub-frecuencia
        wave = np.sin(phase)
        env = np.minimum(1.0, np.exp(-t * 1.0) + 0.5)
    else:  # reese
        # dos saws detuned graves
        wave = (2.0 * (t * freq % 1) - 1.0) * 0.4 + (2.0 * (t * freq * 1.01 % 1) - 1.0) * 0.4
        env = np.minimum(1.0, np.exp(-t * 1.2) + 0.4)
    # fade in/out corto
    fade = min(int(SR * 0.005), n)
    if fade > 0:
        env[:fade] *= np.linspace(0, 1, fade)
        env[-fade:] *= np.linspace(1, 0, fade)
    wave = wave * env
    # filtro pasa-bajos para redondear
    out = np.zeros(n)
    coef = 0.4
    out[0] = wave[0]
    for i in range(1, n):
        out[i] = coef * out[i-1] + (1 - coef) * wave[i]
    # reverb ambiente compartida con las notas del jugador: los ubica en el
    # mismo espacio virtual asi bajo y melodia dejan de sonar como capas
    # aisladas y se sienten como parte de un mismo mix.
    out = reverb_ambiente(out, mezcla=0.14)
    return out

def synth_nota(tipo, freq, duracion, rng_params):
    """Sintetiza una nota con el tipo de onda y parámetros dados"""
    n = int(SR * duracion)
    t = np.linspace(0, duracion, n)
    phase = 2 * np.pi * freq * t

    # envelope ADSR simple
    atk = rng_params.get("attack", 0.01)
    dec = rng_params.get("decay", 5.0)
    sustain = rng_params.get("sustain", 0.6)
    env = np.ones(n)
    # fade-in mínimo para suavizar el ataque (evita click)
    atk = max(atk, 0.008)
    atk_samples = min(int(SR * atk), n)
    if atk_samples > 0:
        # curva suave (ease-in) en vez de lineal
        ramp = np.linspace(0, 1, atk_samples)
        env[:atk_samples] = ramp * ramp
    decay_curve = np.exp(-t * dec) * (1 - sustain) + sustain
    env *= decay_curve
    # release al final
    rel_samples = min(int(SR * 0.02), n)
    if rel_samples > 0:
        env[-rel_samples:] *= np.linspace(1, 0, rel_samples)

    # vibrato
    vib_amt = rng_params.get("vibrato", 0)
    vib_speed = rng_params.get("vib_speed", 5.0)
    if vib_amt > 0:
        phase = phase + vib_amt * np.sin(2 * np.pi * vib_speed * t)

    if tipo == "square":
        wave = np.sign(np.sin(phase))
        # suavizar un poco
        pw = rng_params.get("pulse_width", 0.5)
        wave = np.where((np.sin(phase) / (2 * np.pi)) % 1 < pw, 1.0, -1.0)
    elif tipo == "saw":
        wave = 2.0 * (t * freq % 1) - 1.0
    elif tipo == "sine":
        wave = np.sin(phase)
    elif tipo == "triangle":
        wave = 2.0 * np.abs(2.0 * (t * freq % 1) - 1.0) - 1.0
    elif tipo == "fm_bell":
        mod_ratio = rng_params.get("mod_ratio", 3.5)
        mod_depth = rng_params.get("mod_depth", 4.0)
        mod_env = np.exp(-t * rng_params.get("mod_decay", 8.0))
        wave = np.sin(phase + mod_depth * mod_env * np.sin(2 * np.pi * freq * mod_ratio * t))
    elif tipo == "pluck":
        # karplus-strong simplificado
        np_rng = np.random.RandomState(int(freq * 100) % 999999)
        wave_len = max(int(SR / freq), 2)
        buf = np_rng.uniform(-1, 1, wave_len).astype(np.float64)
        wave = np.zeros(n)
        damp = rng_params.get("damp", 0.496)
        for i in range(n):
            idx = i % wave_len
            wave[i] = buf[idx]
            next_idx = (idx + 1) % wave_len
            buf[idx] = (buf[idx] + buf[next_idx]) * damp
    elif tipo == "organ":
        # suma de armónicos
        h1 = rng_params.get("h1", 1.0)
        h2 = rng_params.get("h2", 0.5)
        h3 = rng_params.get("h3", 0.3)
        h4 = rng_params.get("h4", 0.1)
        wave = (np.sin(phase) * h1 +
                np.sin(phase * 2) * h2 +
                np.sin(phase * 3) * h3 +
                np.sin(phase * 4) * h4) / (h1 + h2 + h3 + h4)
    elif tipo == "chiptune":
        # square con arpeggio rápido entre octavas
        arp_speed = rng_params.get("arp_speed", 20)
        arp = np.where((t * arp_speed % 3).astype(int) == 0, 1.0,
              np.where((t * arp_speed % 3).astype(int) == 1, 2.0, 1.5))
        wave = np.sign(np.sin(2 * np.pi * freq * arp * t))
    elif tipo == "supersaw":
        # 5 saws detuned
        detune = rng_params.get("detune", 0.008)
        wave = np.zeros(n)
        for d in [-2, -1, 0, 1, 2]:
            wave += (2.0 * (t * freq * (1 + d * detune) % 1) - 1.0) * 0.25
    elif tipo == "acid":
        # saw con filter sweep (TB-303)
        raw = 2.0 * (t * freq % 1) - 1.0
        cutoff = rng_params.get("cutoff", 0.3)
        resonance = rng_params.get("resonance", 0.7)
        sweep = np.exp(-t * rng_params.get("sweep_speed", 6)) * cutoff + 0.05
        wave = np.zeros(n)
        lp = 0.0
        bp = 0.0
        for i in range(n):
            f = sweep[i]
            lp += f * bp
            hp = raw[i] - lp - resonance * bp
            bp += f * hp
            wave[i] = lp
    elif tipo == "bitcrush":
        # onda con reduccion de bits
        bits = rng_params.get("bits", 4)
        base = np.sin(phase) + np.sin(phase * 2) * 0.3
        levels = 2 ** bits
        wave = np.round(base * levels / 2) / (levels / 2)
    elif tipo == "lead":
        mix = rng_params.get("mix", 0.5)
        sq = np.sign(np.sin(phase))
        sw = 2.0 * (t * freq % 1) - 1.0
        wave = sq * mix + sw * (1 - mix)
    elif tipo == "wobble":
        # antes: profundidad 0.8 hacia que el sonido "desapareciera" a la mitad
        # ahora: 0.55 con offset -> siempre audible, wobble sigue notorio
        lfo_speed = rng_params.get("lfo_speed", 6)
        lfo_depth = rng_params.get("lfo_depth", 0.55)
        lfo = 0.45 + lfo_depth * (0.5 + 0.5 * np.sin(2 * np.pi * lfo_speed * t))
        raw = 2.0 * (t * freq % 1) - 1.0
        wave = raw * lfo
    elif tipo == "glass":
        h_count = rng_params.get("harmonics", 6)
        wave = np.zeros(n)
        for h in range(1, h_count + 1):
            amp = 1.0 / (h * h)
            dec = np.exp(-t * h * rng_params.get("h_decay", 3))
            wave += np.sin(phase * h) * amp * dec
    elif tipo == "pad":
        num_voices = 4
        detune = rng_params.get("detune", 0.006)
        wave = np.zeros(n)
        for v in range(num_voices):
            d = (v - num_voices / 2) * detune
            wave += np.sin(2 * np.pi * freq * (1 + d) * t + v * 1.5) * 0.3
    elif tipo == "bellpad":
        # campana calida + capa pad. El parcial de campana (x2.76, inarmonico
        # clasico) decae 4x mas rapido que el cuerpo: da el "ataque de campana"
        # sin dejar un "bing" agudo sostenido. Sin parciales por encima de x3.
        camp = np.exp(-t * 8)
        wave = (np.sin(phase) * 0.45
                + np.sin(phase * 2) * 0.15
                + np.sin(phase * 2.76) * 0.22 * camp)
        # capa pad: 2 voces con detune suave
        for d in (-0.005, 0.005):
            wave += np.sin(2 * np.pi * freq * (1 + d) * t) * 0.14
    elif tipo == "metallic":
        mod_freq = freq * rng_params.get("ring_ratio", 1.7)
        carrier = np.sin(phase)
        modulator = np.sin(2 * np.pi * mod_freq * t)
        wave = carrier * modulator
    elif tipo == "bass":
        sub = np.sin(2 * np.pi * freq * 0.5 * t) * 0.6
        mid = np.sign(np.sin(phase)) * 0.4
        wave = sub + mid
    elif tipo == "flute":
        breath = rng_params.get("breath", 0.15)
        np_rng = np.random.RandomState(int(freq * 100) % 999999)
        noise = np_rng.uniform(-1, 1, n) * breath
        tri = 2.0 * np.abs(2.0 * (t * freq % 1) - 1.0) - 1.0
        wave = tri * 0.7 + noise * np.exp(-t * 2)
    elif tipo == "reso":
        np_rng = np.random.RandomState(rng_params.get("seed", 42))
        raw = np_rng.uniform(-1, 1, n)
        res = rng_params.get("resonance", 0.9)
        center = freq / SR
        wave = np.zeros(n)
        bp = 0.0
        lp = 0.0
        for i in range(n):
            hp = raw[i] - lp - res * bp
            bp += center * hp
            lp += center * bp
            wave[i] = bp
    elif tipo == "choir":
        num_v = 5
        wave = np.zeros(n)
        for v in range(num_v):
            vib = rng_params.get("choir_vib", 0.3)
            spd = 4 + v * 0.7
            detune = 1 + (v - 2) * 0.004
            p = 2 * np.pi * freq * detune * t + vib * np.sin(2 * np.pi * spd * t)
            wave += np.sin(p) * 0.25
    elif tipo == "pwm_lead":
        lfo = 0.5 + 0.35 * np.sin(2 * np.pi * rng_params.get("pwm_rate", 2) * t)
        fase_norm = (t * freq) % 1.0
        wave = np.where(fase_norm < lfo, 1.0, -1.0)
        wave = wave * 0.7 + np.sin(phase) * 0.3
    elif tipo == "fm_ep":
        mod_env = np.exp(-t * rng_params.get("fm_decay", 4))
        ratio = rng_params.get("fm_ratio", 2.0)
        idx = rng_params.get("fm_index", 3.0)
        op2 = np.sin(2 * np.pi * freq * ratio * t) * idx * mod_env
        wave = np.sin(phase + op2)
        wave = wave * 0.8 + np.sin(phase) * 0.2
    elif tipo == "formant":
        # vocal con formantes vectorizado (filtros pasa-banda de un polo)
        carrier = 2.0 * (t * freq % 1) - 1.0
        vocal = rng_params.get("vocal", "ah")
        formantes = {
            "ah": [(700, 1.0), (1220, 0.5), (2600, 0.25)],
            "ee": [(300, 1.0), (2300, 0.6), (3000, 0.25)],
            "oh": [(500, 1.0), (1000, 0.4), (2400, 0.2)],
        }.get(vocal, [(700, 1.0), (1220, 0.5), (2600, 0.25)])
        out = np.zeros(n)
        for fc, amp in formantes:
            coef = math.exp(-2 * math.pi * (fc * 0.15) / SR)
            sin_w = math.sin(2 * math.pi * fc / SR)
            cos_w = math.cos(2 * math.pi * fc / SR)
            # resonador de 2 polos vectorizado via lfilter manual ligero
            b0 = (1 - coef)
            y = np.zeros(n)
            y1 = 0.0; y2 = 0.0
            a1 = -2 * coef * cos_w
            a2 = coef * coef
            for k in range(n):
                yk = b0 * carrier[k] - a1 * y1 - a2 * y2
                y[k] = yk
                y2 = y1; y1 = yk
            out += y * amp
        wave = out * 0.4
    elif tipo == "hoover":
        # antes: 5 saws sin filtro -> aliasing feo en agudos
        # ahora: pasa-bajos suave posterior para domar los armonicos duros
        sweep = 1 + 0.06 * np.exp(-t * 8)
        wave = np.zeros(n)
        for d in [-0.4, -0.1, 0, 0.1, 0.4]:
            f = freq * sweep * (1 + d * 0.012)
            wave += (2.0 * (t * f % 1) - 1.0) * 0.2
        # pasa-bajos 1er orden: corta armonicos altos que hacen aliasing
        # cutoff proporcional a la freq (mantiene brillo relativo)
        coef = min(0.35, 8 * freq / SR)
        lp_val = 0.0
        for i in range(n):
            lp_val += coef * (wave[i] - lp_val)
            wave[i] = lp_val * 1.4    # compensar perdida de nivel
    elif tipo == "bell_fm":
        ratio = rng_params.get("bell_ratio", 1.414)
        idx = rng_params.get("bell_index", 5.0)
        mod_env = np.exp(-t * 3)
        wave = np.sin(phase + idx * mod_env * np.sin(2 * np.pi * freq * ratio * t))
    elif tipo == "growl":
        # antes: idx=4 con tanh(x*1.5) = distorsion sobre distorsion embarrada
        # ahora: idx=2.2 con tanh(x*1.1) -> gruñido reconocible sin barro
        lfo = 0.5 + 0.5 * np.sin(2 * np.pi * rng_params.get("growl_rate", 7) * t)
        idx = rng_params.get("growl_index", 2.2) * lfo
        wave = np.sin(phase + idx * np.sin(2 * np.pi * freq * 1.0 * t))
        wave = np.tanh(wave * 1.1)
    elif tipo == "saw_stack":
        # 7 saws apilados con detune variable: muro de sonido
        wave = np.zeros(n)
        spread = rng_params.get("spread", 0.015)
        for k in range(7):
            d = (k - 3) / 3.0
            f = freq * (1 + d * spread)
            wave += (2.0 * (t * f % 1) - 1.0) * (0.16 - abs(d) * 0.03)
    elif tipo == "fm_3op":
        # FM de 3 operadores en cascada
        r2 = rng_params.get("r2", 2.0); r3 = rng_params.get("r3", 3.0)
        i2 = rng_params.get("i2", 2.0); i3 = rng_params.get("i3", 1.5)
        e2 = np.exp(-t * rng_params.get("d2", 3))
        e3 = np.exp(-t * rng_params.get("d3", 5))
        op3 = np.sin(2 * np.pi * freq * r3 * t) * i3 * e3
        op2 = np.sin(2 * np.pi * freq * r2 * t + op3) * i2 * e2
        wave = np.sin(phase + op2)
    elif tipo == "ring_mod":
        # modulacion en anillo: dos tonos multiplicados
        rm = rng_params.get("rm_ratio", 1.5)
        wave = np.sin(phase) * np.sin(2 * np.pi * freq * rm * t)
        wave = wave * 0.7 + np.sin(phase) * 0.3
    elif tipo == "sync_lead":
        # oscilador sincronizado (hard sync): timbre brillante y agresivo
        slave_ratio = rng_params.get("sync_ratio", 1.5)
        master_phase = (t * freq) % 1.0
        slave = (t * freq * slave_ratio) % 1.0
        # reset del slave cuando el master cicla
        ciclo = np.floor(t * freq)
        slave_sync = (t * freq * slave_ratio - ciclo * slave_ratio) % 1.0
        wave = 2.0 * slave_sync - 1.0
    elif tipo == "pluck_soft":
        # cuerda pulsada con cuerpo y armonicos pares
        np_rng = np.random.RandomState(int(freq * 100) % 999999)
        wl = max(int(SR / freq), 2)
        buf = np_rng.uniform(-1, 1, wl).astype(np.float64)
        ks = np.zeros(n)
        for k in range(n):
            idx = k % wl
            ks[k] = buf[idx]
            nx = (idx + 1) % wl
            buf[idx] = (buf[idx] + buf[nx]) * 0.4975
        wave = ks * 0.7 + np.sin(phase) * 0.3
    elif tipo == "vox_pad":
        # pad coral con formantes suaves y muchas voces
        wave = np.zeros(n)
        for v in range(6):
            det = 1 + (v - 2.5) * 0.005
            vib = 0.15 * np.sin(2 * np.pi * (3 + v * 0.5) * t)
            wave += np.sin(2 * np.pi * freq * det * t + vib) * 0.16
        # leve enfasis de formante
        lp = np.zeros(n); coef = 0.5
        for k in range(1, n):
            lp[k] = coef * lp[k-1] + (1 - coef) * wave[k]
        wave = wave * 0.6 + lp * 0.4
    elif tipo == "dist_gtr":
        # "guitarra" distorsionada: saw saturado con armonicos
        raw = 2.0 * (t * freq % 1) - 1.0
        raw += np.sin(phase * 2) * 0.3
        wave = np.tanh(raw * rng_params.get("drive", 3))
    elif tipo == "wavefold":
        # wavefolding: sine doblada sobre si misma, timbre rico
        amt = rng_params.get("fold", 2.5)
        x = np.sin(phase) * amt
        wave = np.sin(x * np.pi / 2)
    elif tipo == "phase_pad":
        # pad con phasing: dos capas con corrimiento de fase lento
        ph2 = phase + 2 * np.sin(2 * np.pi * 0.3 * t)
        wave = (np.sin(phase) + np.sin(ph2)) * 0.5
        wave += np.sin(phase * 2) * 0.15
    elif tipo == "fm_brass":
        # metales FM: ataque con barrido de indice
        idx_env = (1 - np.exp(-t * 20)) * np.exp(-t * 1.5)
        idx = rng_params.get("brass_index", 4) * idx_env
        wave = np.sin(phase + idx * np.sin(phase))
    elif tipo == "glass_harm":
        # armonica de cristal: armonicos impares altos
        wave = np.zeros(n)
        for h in [1, 3, 5, 7, 9]:
            wave += np.sin(phase * h) * (1.0 / h) * np.exp(-t * h * 0.5)
        wave *= 0.6
    elif tipo == "sub_pluck":
        # pluck sub-grave con click: bajo percusivo moderno
        click = np.exp(-t * 60) * np.sin(2 * np.pi * freq * 4 * t) * 0.4
        body = np.sin(phase) + np.sin(2 * np.pi * freq * 0.5 * t) * 0.5
        wave = body * np.exp(-t * 2) + click
    elif tipo == "noise_pitch":
        # tono de ruido filtrado con pitch: a medio camino entre tono y percusion
        # resonancia bajada de 0.96 -> 0.85 para evitar silbidos asperos
        np_rng = np.random.RandomState(int(freq) % 999999)
        raw = np_rng.uniform(-1, 1, n)
        res = 0.85
        center = freq / SR
        wave = np.zeros(n)
        bp = 0.0; lp = 0.0
        for k in range(n):
            hp = raw[k] - lp - res * bp
            bp += center * hp
            lp += center * bp
            wave[k] = bp
        wave = wave * 0.6 + np.sin(phase) * 0.2
    elif tipo == "organ_full":
        # organo completo estilo drawbars: muchos armonicos + click de tecla
        wave = np.zeros(n)
        for h, a in [(1, 0.8), (2, 0.6), (3, 0.4), (4, 0.3), (6, 0.2), (8, 0.15)]:
            wave += np.sin(phase * h) * a
        wave /= 2.5
        click = np.exp(-t * 100) * 0.3
        wave += click
    elif tipo == "atmos_noise":
        # ruido filtrado que evoluciona con un LFO lento (viento / espacio)
        np_rng2 = np.random.RandomState(int(freq * 100) % 999999)
        noise = np_rng2.uniform(-1, 1, n).astype(np.float64)
        # filtro pasa-banda alrededor de la frecuencia
        bw = rng_params.get("bandwidth", 0.008)
        center = min(freq / SR, 0.49)
        wave = np.zeros(n)
        bp = 0.0; lp_n = 0.0
        for i in range(n):
            hp = noise[i] - lp_n - bp
            bp += bw * hp * 6
            lp_n += bw * bp * 6
            wave[i] = bp
        # trémolo con LFO lento y sinusoide tonal reforzada
        # antes: ruido 70% + tonal 30% -> el pitch no se identificaba.
        # ahora: tonal 55% con octava, ruido de fondo mas suave.
        lfo_mod = 0.6 + 0.4 * np.sin(2 * np.pi * rng_params.get("lfo_spd", 0.3) * t)
        tonal = np.sin(phase) * 0.4 + np.sin(phase * 2) * 0.15
        wave = wave * lfo_mod * 0.35 + tonal
    elif tipo == "frozen_strings":
        # cuerdas "congeladas": muchos armonicos con ataque lentísimo y movimiento leve
        num_v = rng_params.get("num_voices", 6)
        wave = np.zeros(n)
        for v in range(num_v):
            d = (v - num_v / 2) * rng_params.get("detune", 0.007)
            # leve flutter por voz
            flutter_spd = 3.0 + v * 0.9
            flutter_d = 0.003 * np.sin(2 * np.pi * flutter_spd * t + v)
            p = 2 * np.pi * freq * (1 + d + flutter_d) * t
            h_wave = np.sin(p) * 0.6 + np.sin(p * 2) * 0.25 + np.sin(p * 3) * 0.1 + np.sin(p * 4) * 0.05
            wave += h_wave
        wave /= num_v
        # filtro low-pass suave
        co = rng_params.get("cutoff_lp", 0.06)
        sm = np.zeros(n); s = 0.0
        for i in range(n):
            s += co * (wave[i] - s)
            sm[i] = s
        wave = sm
    elif tipo == "dream_pad":
        # pad onírico: sines con desfase que crean interferencias lentas
        num_v = rng_params.get("num_voices", 6)
        wave = np.zeros(n)
        for v in range(num_v):
            ratio = 1.0 + (v - num_v / 2) * rng_params.get("detune", 0.005)
            slow_mod = np.sin(2 * np.pi * rng_params.get("lfo_spd", 0.15) * t + v * 1.1)
            freq_mod = freq * ratio * (1 + 0.004 * slow_mod)
            wave += np.sin(2 * np.pi * np.cumsum(freq_mod / SR) + v * 0.9)
            # armonico superior tenue
            wave += np.sin(4 * np.pi * np.cumsum(freq_mod / SR) + v) * 0.15
        wave /= num_v
    elif tipo == "space_choir":
        # coro espacial: voces formánticas desafinadas con reverb sintética
        num_v = rng_params.get("num_voices", 7)
        wave = np.zeros(n)
        for v in range(num_v):
            d = (v - num_v / 2) * rng_params.get("detune", 0.006)
            vib_spd = 2.5 + v * 0.4
            vib_d = rng_params.get("vibrato", 0.25) * np.sin(2 * np.pi * vib_spd * t + v * 1.3)
            p = 2 * np.pi * freq * (1 + d) * t + vib_d
            # formantes simuladas con armonicos ponderados
            fo = np.sin(p) * 0.6 + np.sin(p * 2) * 0.25 + np.sin(p * 3) * 0.1
            wave += fo * (0.5 + 0.5 * np.sin(2 * np.pi * 0.1 * t + v))  # amplitude breathing
        wave /= num_v
        # "reverb" simulada: ecos ponderados
        eco_ms = rng_params.get("eco_ms", 80)
        eco_samples = int(SR * eco_ms / 1000)
        if eco_samples < n:
            wave[eco_samples:] += wave[:-eco_samples] * 0.35
            wave[eco_samples*2:] += wave[:-eco_samples*2] * 0.15 if eco_samples*2 < n else 0
    elif tipo == "analog_string":
        # cuerdas analógicas estilo string machine vintage
        wave = np.zeros(n)
        saw1 = 2.0 * (t * freq % 1) - 1.0
        saw2 = 2.0 * (t * freq * (1 + rng_params.get("detune", 0.012)) % 1) - 1.0
        saw3 = 2.0 * (t * freq * (1 - rng_params.get("detune", 0.012) * 0.7) % 1) - 1.0
        wave = saw1 * 0.5 + saw2 * 0.3 + saw3 * 0.2
        # filtro pasa-bajos suave para el sonido vintage
        co = rng_params.get("cutoff_lp", 0.05)
        sm = np.zeros(n); s = 0.0
        for i in range(n):
            s += co * (wave[i] - s)
            sm[i] = s
        wave = sm
        # chorus leve
        chorus_d = int(SR * 0.015)
        if chorus_d < n:
            wave[chorus_d:] += wave[:-chorus_d] * 0.4
    # --- instrumentos raros (baja probabilidad) ---
    elif tipo == "alien":
        # barrido inarmonico con modulacion caotica
        m1 = np.sin(2 * np.pi * freq * 1.37 * t) * 3 * np.exp(-t * 2)
        m2 = np.sin(2 * np.pi * freq * 0.51 * t + m1) * 4
        wave = np.sin(phase + m2)
        # tremolo irregular
        wave *= 0.6 + 0.4 * np.sin(2 * np.pi * 11 * t) * np.sin(2 * np.pi * 3.3 * t)
    elif tipo == "broken":
        # sonido "roto": bitcrush extremo + sample&hold de pitch
        base = np.sin(phase) + (2.0 * (t * freq % 1) - 1.0) * 0.5
        # sample and hold
        sh_rate = max(1, int(SR / rng_params.get("sh_freq", 800)))
        held = base.copy()
        for k in range(0, n, sh_rate):
            held[k:k+sh_rate] = base[k] if k < n else 0
        bits = 3
        levels = 2 ** bits
        wave = np.round(held * levels / 2) / (levels / 2)
    else:
        wave = np.sin(phase)

    wave = wave * env * 0.7
    # normalizar al pico para que todos los instrumentos arranquen igual
    peak = np.max(np.abs(wave))
    if peak > 0:
        wave = wave / peak
    vol_tipo = {
        "square": 0.6, "saw": 0.6, "chiptune": 0.55,
        "organ": 0.65, "fm_bell": 0.7,
        "sine": 0.75, "triangle": 0.7, "pluck": 0.7,
        "supersaw": 0.55, "acid": 0.6, "bitcrush": 0.6, "lead": 0.6,
        "wobble": 0.6, "glass": 0.7, "pad": 0.65,
        "metallic": 0.6, "bass": 0.6, "flute": 0.65,
        "reso": 0.6, "choir": 0.65,
        "vibraphone": 0.65, "sitar": 0.6, "kalimba": 0.65,
        "trumpet": 0.6, "harp": 0.65, "synthbass": 0.6,
        "bellpad": 0.6, "detune": 0.6,
        "pwm_lead": 0.6, "fm_ep": 0.7, "formant": 0.6,
        "hoover": 0.55, "bell_fm": 0.65, "growl": 0.6,
        "saw_stack": 0.55, "fm_3op": 0.65, "ring_mod": 0.6,
        "sync_lead": 0.6, "pluck_soft": 0.7, "vox_pad": 0.6,
        "dist_gtr": 0.55, "wavefold": 0.6, "phase_pad": 0.65,
        "fm_brass": 0.65, "glass_harm": 0.65, "sub_pluck": 0.65,
        "noise_pitch": 0.6, "organ_full": 0.6,
        "atmos_noise": 0.55, "frozen_strings": 0.65,
        "dream_pad": 0.65, "space_choir": 0.60, "analog_string": 0.62,
        "alien": 0.55, "broken": 0.55,
    }
    
    return np_to_sound(wave, vol=vol_tipo.get(tipo, 0.5))

def generar_params_instrumento(rng, tipo):
    """Genera parámetros aleatorios para un tipo de instrumento"""
    params = {}
    if tipo == "square":
        params["attack"] = rng.uniform(0.001, 0.02)
        params["decay"] = rng.uniform(3, 8)
        params["sustain"] = rng.uniform(0.3, 0.7)
        params["pulse_width"] = rng.uniform(0.2, 0.8)
        params["vibrato"] = rng.uniform(0, 0.3)
        params["vib_speed"] = rng.uniform(4, 7)
    elif tipo == "saw":
        params["attack"] = rng.uniform(0.001, 0.01)
        params["decay"] = rng.uniform(4, 10)
        params["sustain"] = rng.uniform(0.4, 0.8)
        params["vibrato"] = rng.uniform(0, 0.2)
        params["vib_speed"] = rng.uniform(4, 6)
    elif tipo == "sine":
        params["attack"] = rng.uniform(0.01, 0.05)
        params["decay"] = rng.uniform(2, 6)
        params["sustain"] = rng.uniform(0.5, 0.9)
        params["vibrato"] = rng.uniform(0.1, 0.5)
        params["vib_speed"] = rng.uniform(4, 8)
    elif tipo == "triangle":
        params["attack"] = rng.uniform(0.005, 0.03)
        params["decay"] = rng.uniform(3, 7)
        params["sustain"] = rng.uniform(0.4, 0.7)
        params["vibrato"] = rng.uniform(0, 0.4)
        params["vib_speed"] = rng.uniform(3, 6)
    elif tipo == "fm_bell":
        params["attack"] = rng.uniform(0.001, 0.005)
        params["decay"] = rng.uniform(5, 15)
        params["sustain"] = rng.uniform(0.0, 0.2)
        params["mod_ratio"] = rng.choice([1.5, 2.0, 3.0, 3.5, 4.0, 5.0, 7.0])
        params["mod_depth"] = rng.uniform(2, 8)
        params["mod_decay"] = rng.uniform(4, 12)
    elif tipo == "pluck":
        params["attack"] = 0.001
        params["decay"] = rng.uniform(3, 8)
        params["sustain"] = 0.0
        params["damp"] = rng.uniform(0.490, 0.499)
    elif tipo == "organ":
        params["attack"] = rng.uniform(0.005, 0.02)
        params["decay"] = rng.uniform(1, 3)
        params["sustain"] = rng.uniform(0.7, 0.95)
        params["h1"] = 1.0
        params["h2"] = rng.uniform(0.2, 0.8)
        params["h3"] = rng.uniform(0.1, 0.5)
        params["h4"] = rng.uniform(0.0, 0.3)
        params["vibrato"] = rng.uniform(0.1, 0.4)
        params["vib_speed"] = rng.uniform(5, 8)
    elif tipo == "chiptune":
        params["attack"] = 0.001
        params["decay"] = rng.uniform(4, 10)
        params["sustain"] = rng.uniform(0.3, 0.6)
        params["arp_speed"] = rng.choice([15, 20, 25, 30])
    elif tipo == "supersaw":
        params["attack"] = rng.uniform(0.005, 0.02)
        params["decay"] = rng.uniform(3, 8)
        params["sustain"] = rng.uniform(0.5, 0.8)
        params["detune"] = rng.uniform(0.003, 0.015)
        params["vibrato"] = rng.uniform(0, 0.2)
        params["vib_speed"] = rng.uniform(3, 6)
    elif tipo == "acid":
        params["attack"] = 0.001
        params["decay"] = rng.uniform(4, 10)
        params["sustain"] = rng.uniform(0.2, 0.5)
        params["cutoff"] = rng.uniform(0.15, 0.5)
        params["resonance"] = rng.uniform(0.5, 0.95)
        params["sweep_speed"] = rng.uniform(3, 10)
    elif tipo == "bitcrush":
        params["attack"] = rng.uniform(0.001, 0.01)
        params["decay"] = rng.uniform(3, 8)
        params["sustain"] = rng.uniform(0.3, 0.6)
        params["bits"] = rng.choice([2, 3, 4, 5, 6])
        params["vibrato"] = rng.uniform(0, 0.3)
        params["vib_speed"] = rng.uniform(4, 7)
    elif tipo == "lead":
        params["attack"] = rng.uniform(0.001, 0.01)
        params["decay"] = rng.uniform(4, 8)
        params["sustain"] = rng.uniform(0.4, 0.7)
        params["mix"] = rng.uniform(0.2, 0.8)
        params["vibrato"] = rng.uniform(0.1, 0.4)
        params["vib_speed"] = rng.uniform(4, 7)
    elif tipo == "wobble":
        params["attack"] = rng.uniform(0.001, 0.01)
        params["decay"] = rng.uniform(3, 7)
        params["sustain"] = rng.uniform(0.4, 0.7)
        params["lfo_speed"] = rng.uniform(3, 12)
        params["lfo_depth"] = rng.uniform(0.4, 0.95)
    elif tipo == "glass":
        params["attack"] = rng.uniform(0.001, 0.005)
        params["decay"] = rng.uniform(6, 15)
        params["sustain"] = rng.uniform(0.0, 0.15)
        params["harmonics"] = rng.randint(4, 10)
        params["h_decay"] = rng.uniform(2, 6)
    elif tipo == "pad":
        params["attack"] = rng.uniform(0.05, 0.2)
        params["decay"] = rng.uniform(1, 3)
        params["sustain"] = rng.uniform(0.7, 0.95)
        params["detune"] = rng.uniform(0.003, 0.01)
        params["vibrato"] = rng.uniform(0.2, 0.5)
        params["vib_speed"] = rng.uniform(3, 6)
    elif tipo == "metallic":
        params["attack"] = rng.uniform(0.001, 0.01)
        params["decay"] = rng.uniform(5, 12)
        params["sustain"] = rng.uniform(0.0, 0.2)
        params["ring_ratio"] = rng.choice([1.2, 1.5, 1.7, 2.1, 2.5, 3.0, 3.7])
    elif tipo == "bass":
        params["attack"] = rng.uniform(0.001, 0.01)
        params["decay"] = rng.uniform(3, 8)
        params["sustain"] = rng.uniform(0.3, 0.6)
    elif tipo == "flute":
        params["attack"] = rng.uniform(0.02, 0.08)
        params["decay"] = rng.uniform(2, 5)
        params["sustain"] = rng.uniform(0.5, 0.8)
        params["breath"] = rng.uniform(0.08, 0.25)
        params["vibrato"] = rng.uniform(0.2, 0.6)
        params["vib_speed"] = rng.uniform(4, 7)
    elif tipo == "reso":
        params["attack"] = rng.uniform(0.001, 0.01)
        params["decay"] = rng.uniform(4, 10)
        params["sustain"] = rng.uniform(0.2, 0.5)
        params["resonance"] = rng.uniform(0.7, 0.98)
        params["seed"] = rng.randint(0, 999999)
    elif tipo == "choir":
        params["attack"] = rng.uniform(0.05, 0.15)
        params["decay"] = rng.uniform(1, 3)
        params["sustain"] = rng.uniform(0.7, 0.9)
        params["choir_vib"] = rng.uniform(0.15, 0.5)
        params["vibrato"] = rng.uniform(0.1, 0.3)
        params["vib_speed"] = rng.uniform(4, 6)
    elif tipo == "vibraphone":
        params["attack"] = rng.uniform(0.001, 0.005)
        params["decay"] = rng.uniform(4, 9)
        params["sustain"] = rng.uniform(0.2, 0.4)
    elif tipo == "sitar":
        params["attack"] = rng.uniform(0.001, 0.01)
        params["decay"] = rng.uniform(3, 7)
        params["sustain"] = rng.uniform(0.3, 0.6)
        params["vibrato"] = rng.uniform(0.2, 0.5)
        params["vib_speed"] = rng.uniform(5, 9)
    elif tipo == "kalimba":
        params["attack"] = 0.001
        params["decay"] = rng.uniform(5, 10)
        params["sustain"] = rng.uniform(0.1, 0.3)
    elif tipo == "trumpet":
        params["attack"] = rng.uniform(0.01, 0.04)
        params["decay"] = rng.uniform(2, 5)
        params["sustain"] = rng.uniform(0.6, 0.85)
        params["vibrato"] = rng.uniform(0.15, 0.4)
        params["vib_speed"] = rng.uniform(5, 7)
    elif tipo == "harp":
        params["attack"] = 0.001
        params["decay"] = rng.uniform(4, 9)
        params["sustain"] = 0.0
    elif tipo == "synthbass":
        params["attack"] = rng.uniform(0.001, 0.008)
        params["decay"] = rng.uniform(3, 7)
        params["sustain"] = rng.uniform(0.4, 0.7)
    elif tipo == "bellpad":
        params["attack"] = rng.uniform(0.02, 0.08)
        params["decay"] = rng.uniform(3, 7)
        params["sustain"] = rng.uniform(0.4, 0.7)
        params["vibrato"] = rng.uniform(0.1, 0.3)
        params["vib_speed"] = rng.uniform(3, 5)
    elif tipo == "detune":
        params["attack"] = rng.uniform(0.005, 0.02)
        params["decay"] = rng.uniform(3, 7)
        params["sustain"] = rng.uniform(0.4, 0.7)
        params["detune_amt"] = rng.uniform(0.01, 0.03)
    elif tipo == "pwm_lead":
        params["attack"] = rng.uniform(0.005, 0.02); params["decay"] = rng.uniform(3, 7)
        params["sustain"] = rng.uniform(0.5, 0.8); params["pwm_rate"] = rng.uniform(0.5, 4)
        params["vibrato"] = rng.uniform(0.1, 0.3); params["vib_speed"] = rng.uniform(4, 6)
    elif tipo == "fm_ep":
        params["attack"] = 0.001; params["decay"] = rng.uniform(3, 6)
        params["sustain"] = rng.uniform(0.2, 0.4); params["fm_decay"] = rng.uniform(3, 7)
        params["fm_ratio"] = rng.choice([1.0, 2.0, 3.0, 4.0]); params["fm_index"] = rng.uniform(2, 5)
    elif tipo == "formant":
        params["attack"] = rng.uniform(0.02, 0.06); params["decay"] = rng.uniform(2, 4)
        params["sustain"] = rng.uniform(0.6, 0.85); params["vibrato"] = rng.uniform(0.3, 0.6)
        params["vib_speed"] = rng.uniform(5, 7); params["vocal"] = rng.choice(["ah", "ee", "oh"])
    elif tipo == "hoover":
        params["attack"] = rng.uniform(0.005, 0.02); params["decay"] = rng.uniform(3, 6)
        params["sustain"] = rng.uniform(0.5, 0.8)
    elif tipo == "bell_fm":
        params["attack"] = 0.001; params["decay"] = rng.uniform(5, 12)
        params["sustain"] = rng.uniform(0.0, 0.15); params["bell_ratio"] = rng.choice([1.414, 1.732, 2.236, 2.5])
        params["bell_index"] = rng.uniform(3, 7)
    elif tipo == "growl":
        params["attack"] = rng.uniform(0.001, 0.01); params["decay"] = rng.uniform(3, 6)
        params["sustain"] = rng.uniform(0.4, 0.7); params["growl_rate"] = rng.uniform(4, 10)
        params["growl_index"] = rng.uniform(3, 6)
    elif tipo == "saw_stack":
        params["attack"] = rng.uniform(0.005, 0.03); params["decay"] = rng.uniform(3, 8)
        params["sustain"] = rng.uniform(0.5, 0.8); params["spread"] = rng.uniform(0.008, 0.025)
    elif tipo == "fm_3op":
        params["attack"] = 0.001; params["decay"] = rng.uniform(3, 7)
        params["sustain"] = rng.uniform(0.2, 0.5)
        params["r2"] = rng.choice([1.0, 2.0, 3.0]); params["r3"] = rng.choice([2.0, 3.0, 5.0])
        params["i2"] = rng.uniform(1.5, 3); params["i3"] = rng.uniform(1, 2)
        params["d2"] = rng.uniform(2, 4); params["d3"] = rng.uniform(4, 7)
    elif tipo == "ring_mod":
        params["attack"] = rng.uniform(0.001, 0.01); params["decay"] = rng.uniform(3, 7)
        params["sustain"] = rng.uniform(0.3, 0.6); params["rm_ratio"] = rng.uniform(1.2, 2.5)
    elif tipo == "sync_lead":
        params["attack"] = rng.uniform(0.001, 0.01); params["decay"] = rng.uniform(3, 6)
        params["sustain"] = rng.uniform(0.4, 0.7); params["sync_ratio"] = rng.uniform(1.5, 3.0)
        params["vibrato"] = rng.uniform(0.1, 0.3); params["vib_speed"] = rng.uniform(4, 6)
    elif tipo == "pluck_soft":
        params["attack"] = 0.001; params["decay"] = rng.uniform(3, 7); params["sustain"] = 0.0
    elif tipo == "vox_pad":
        params["attack"] = rng.uniform(0.05, 0.15); params["decay"] = rng.uniform(1, 3)
        params["sustain"] = rng.uniform(0.7, 0.9); params["vibrato"] = rng.uniform(0.1, 0.3)
        params["vib_speed"] = rng.uniform(3, 5)
    elif tipo == "dist_gtr":
        params["attack"] = rng.uniform(0.001, 0.01); params["decay"] = rng.uniform(3, 7)
        params["sustain"] = rng.uniform(0.4, 0.7); params["drive"] = rng.uniform(2, 5)
    elif tipo == "wavefold":
        params["attack"] = rng.uniform(0.005, 0.02); params["decay"] = rng.uniform(3, 7)
        params["sustain"] = rng.uniform(0.4, 0.7); params["fold"] = rng.uniform(1.5, 4)
    elif tipo == "phase_pad":
        params["attack"] = rng.uniform(0.05, 0.2); params["decay"] = rng.uniform(1, 3)
        params["sustain"] = rng.uniform(0.6, 0.9)
    elif tipo == "fm_brass":
        params["attack"] = rng.uniform(0.01, 0.04); params["decay"] = rng.uniform(2, 5)
        params["sustain"] = rng.uniform(0.6, 0.85); params["brass_index"] = rng.uniform(3, 6)
        params["vibrato"] = rng.uniform(0.1, 0.3); params["vib_speed"] = rng.uniform(4, 6)
    elif tipo == "glass_harm":
        params["attack"] = rng.uniform(0.001, 0.005); params["decay"] = rng.uniform(5, 12)
        params["sustain"] = rng.uniform(0.0, 0.15)
    elif tipo == "sub_pluck":
        params["attack"] = 0.001; params["decay"] = rng.uniform(3, 7); params["sustain"] = rng.uniform(0.1, 0.3)
    elif tipo == "noise_pitch":
        params["attack"] = rng.uniform(0.001, 0.01); params["decay"] = rng.uniform(3, 6)
        params["sustain"] = rng.uniform(0.3, 0.6)
    elif tipo == "organ_full":
        params["attack"] = rng.uniform(0.001, 0.01); params["decay"] = rng.uniform(1, 3)
        params["sustain"] = rng.uniform(0.7, 0.95); params["vibrato"] = rng.uniform(0.1, 0.3)
        params["vib_speed"] = rng.uniform(5, 7)
    elif tipo == "alien":
        params["attack"] = rng.uniform(0.01, 0.05); params["decay"] = rng.uniform(2, 5)
        params["sustain"] = rng.uniform(0.3, 0.6)
    elif tipo == "atmos_noise":
        params["attack"] = rng.uniform(0.15, 0.5); params["decay"] = rng.uniform(0.5, 1.5)
        params["sustain"] = rng.uniform(0.7, 0.95)
        params["bandwidth"] = rng.uniform(0.004, 0.012); params["lfo_spd"] = rng.uniform(0.2, 0.6)
    elif tipo == "frozen_strings":
        params["attack"] = rng.uniform(0.15, 0.5); params["decay"] = rng.uniform(0.5, 1.5)
        params["sustain"] = rng.uniform(0.75, 0.95)
        params["num_voices"] = rng.randint(5, 8); params["detune"] = rng.uniform(0.004, 0.012)
        params["cutoff_lp"] = rng.uniform(0.04, 0.09)
    elif tipo == "dream_pad":
        params["attack"] = rng.uniform(0.2, 0.6); params["decay"] = rng.uniform(0.5, 1.5)
        params["sustain"] = rng.uniform(0.8, 0.98)
        params["num_voices"] = rng.randint(5, 7); params["detune"] = rng.uniform(0.003, 0.009)
        params["lfo_spd"] = rng.uniform(0.1, 0.3)
    elif tipo == "space_choir":
        params["attack"] = rng.uniform(0.1, 0.4); params["decay"] = rng.uniform(0.6, 1.5)
        params["sustain"] = rng.uniform(0.75, 0.95)
        params["num_voices"] = rng.randint(6, 9); params["detune"] = rng.uniform(0.004, 0.01)
        params["vibrato"] = rng.uniform(0.15, 0.4); params["eco_ms"] = rng.randint(60, 120)
    elif tipo == "analog_string":
        params["attack"] = rng.uniform(0.05, 0.2); params["decay"] = rng.uniform(0.8, 2)
        params["sustain"] = rng.uniform(0.7, 0.92)
        params["detune"] = rng.uniform(0.007, 0.018); params["cutoff_lp"] = rng.uniform(0.04, 0.08)
        params["vibrato"] = rng.uniform(0.1, 0.3); params["vib_speed"] = rng.uniform(3, 5)
    elif tipo == "broken":
        params["attack"] = rng.uniform(0.001, 0.01); params["decay"] = rng.uniform(3, 6)
        params["sustain"] = rng.uniform(0.3, 0.6); params["sh_freq"] = rng.uniform(400, 1500)

    return params

cache_por_instrumento = {}
cache_largas_por_instrumento = {}

# --- pantalla de carga con burbujas musicales ---
burbujas_carga = []

def dibujar_nota_musical(surface, x, y, size, color):
    """Dibuja una nota musical con circulo y palito"""
    r = max(2, size // 4)
    pygame.draw.ellipse(surface, color, (int(x) - r, int(y), r * 2, int(r * 1.4)))
    pygame.draw.line(surface, color, (int(x) + r, int(y) + r // 2), (int(x) + r, int(y) - size), 2)
    if size > 16:
        pygame.draw.line(surface, color, (int(x) + r, int(y) - size), (int(x) + r + r, int(y) - size + r), 2)

def spawn_burbuja():
    burbujas_carga.append({
        "x": random.uniform(40, ANCHO - 40),
        "y": float(random.uniform(ALTO * 0.3, ALTO + 10)),
        "dx": random.uniform(-0.5, 0.5),
        "dy": random.uniform(-3.0, -1.0),
        "wobble": random.uniform(1.0, 3.0),
        "wobble_speed": random.uniform(1.5, 4.0),
        "size": random.choice([12, 16, 22, 28, 34]),
        "alpha": random.randint(80, 240),
        "t": random.uniform(0, 6.28),
    })

# pre-poblar burbujas para que no arranque vacío
for _ in range(25):
    spawn_burbuja()

def dibujar_pantalla_carga(progreso, texto_inst, total_inst, inst_actual):
    pantalla.fill(NEGRO)

    # spawn y actualizar burbujas
    for _ in range(3):
        if random.random() < 0.6:
            spawn_burbuja()
    for b in burbujas_carga:
        b["t"] += 0.04
        b["x"] += b["dx"] + math.sin(b["t"] * b["wobble_speed"]) * b["wobble"]
        b["y"] += b["dy"]
    burbujas_carga[:] = [b for b in burbujas_carga if b["y"] > -50]

    # dibujar burbujas como notas musicales
    for b in burbujas_carga:
        pct_y = max(0, min(1, b["y"] / ALTO))
        alpha = int(b["alpha"] * (0.2 + 0.8 * pct_y))
        color = (min(255, alpha), min(255, alpha), min(255, alpha))
        dibujar_nota_musical(pantalla, b["x"], b["y"], b["size"], color)

    # titulo
    titulo = fuente_grande.render("* RHYTHM *", True, BLANCO)
    pantalla.blit(titulo, (ANCHO // 2 - titulo.get_width() // 2, 120))

    # texto cargando
    carg = fuente.render("CARGANDO...", True, GRIS_MED)
    pantalla.blit(carg, (ANCHO // 2 - carg.get_width() // 2, 220))

    # instrumento actual
    inst_txt = fuente.render(texto_inst, True, BLANCO)
    pantalla.blit(inst_txt, (ANCHO // 2 - inst_txt.get_width() // 2, 270))

    # progreso texto
    prog_txt = fuente_chica.render(f"{inst_actual}/{total_inst}", True, GRIS)
    pantalla.blit(prog_txt, (ANCHO // 2 - prog_txt.get_width() // 2, 310))

    # barra de progreso
    barra_w = 300
    barra_x = ANCHO // 2 - barra_w // 2
    barra_y = 340
    pygame.draw.rect(pantalla, GRIS, (barra_x, barra_y, barra_w, 16))
    bloques = int(barra_w * progreso) // 8
    for bl in range(bloques):
        pygame.draw.rect(pantalla, BLANCO, (barra_x + bl * 8 + 1, barra_y + 2, 6, 12))
    pygame.draw.rect(pantalla, BLANCO, (barra_x, barra_y, barra_w, 16), 2)

    presentar()
    for ev in pygame.event.get():
        if ev.type == pygame.QUIT:
            pygame.quit()
            exit()

def dibujar_carga_seed(seed):
    """Pantalla breve mientras se genera la canción de la seed"""
    pantalla.fill(NEGRO)
    for _ in range(8):
        spawn_burbuja()
    for b in burbujas_carga:
        b["t"] += 0.06
        b["x"] += b["dx"] + math.sin(b["t"] * b["wobble_speed"]) * b["wobble"]
        b["y"] += b["dy"]
    burbujas_carga[:] = [b for b in burbujas_carga if b["y"] > -50]
    for b in burbujas_carga:
        pct_y = max(0, min(1, b["y"] / ALTO))
        alpha = int(b["alpha"] * (0.2 + 0.8 * pct_y))
        color = (min(255, alpha), min(255, alpha), min(255, alpha))
        dibujar_nota_musical(pantalla, b["x"], b["y"], b["size"], color)
    titulo = fuente_grande.render("* RHYTHM *", True, BLANCO)
    pantalla.blit(titulo, (ANCHO // 2 - titulo.get_width() // 2, 120))
    gen_txt = fuente.render("GENERANDO SEED...", True, GRIS_MED)
    pantalla.blit(gen_txt, (ANCHO // 2 - gen_txt.get_width() // 2, 250))
    seed_txt = fuente_grande.render(str(int(seed)).zfill(6), True, BLANCO)
    pantalla.blit(seed_txt, (ANCHO // 2 - seed_txt.get_width() // 2, 300))
    presentar()
    for ev in pygame.event.get():
        if ev.type == pygame.QUIT:
            pygame.quit()
            exit()

# ════════════════════════════════════════════════════ >>RENDER_INST<< ═══

def renderizar_instrumento(nombre, tipo, dibujar_progreso=False, display=None):
    """Renderiza un instrumento. Notas cortas 0.3s, largas 1.6s con loop."""
    texto_carga = display if display else nombre
    inst_rng = random.Random(hash(nombre))
    params = generar_params_instrumento(inst_rng, tipo)
    inst_eq = inst_rng.choice(EQ_TIPOS)
    # intensidad bajada de 0.10-0.35 a 0.05-0.18: sin exagerar la personalidad
    # espectral evitamos que el instrumento y el kit queden en franjas opuestas
    # (por ejemplo bright vs dark) y se sientan disociados.
    inst_eq_int = inst_rng.uniform(0.05, 0.18)
    # familias con textura espacial propia (pads, atmos, coros, cristales)
    # NO llevan reverb ambiente: al ser sostenidas, las copias retardadas de
    # los taps se superponen a la nota base y crean resonancias/artefactos
    # audibles como "bings" o filtros de peine. Estos instrumentos ya suenan
    # ambient de por si, no necesitan pegamento espacial.
    familia = INST_FORMA.get(nombre, "")
    aplicar_reverb = familia not in ("pad", "atmos", "choir", "glass")
    c_cortas = {}
    c_largas = {}
    # solo renderizar el rango de notas que las canciones usan
    # (45-97 tipico, mas margen grave por octavas de mods)
    MIDI_MIN, MIDI_MAX = 36, 98
    total = MIDI_MAX - MIDI_MIN
    idx = 0
    for midi in range(MIDI_MIN, MIDI_MAX):
        idx += 1
        if dibujar_progreso and midi % 5 == 0:
            dibujar_carga_seed_inst(idx / total, texto_carga)
        freq = midi_a_freq(midi)
        snd = synth_nota(tipo, freq, 0.3, params)
        arr = pygame.sndarray.array(snd).astype(np.float64) / 32767
        # aplicar EQ + HPF + (opcionalmente) reverb ambiente. HPF quita el
        # rumor sub-grave (<130Hz) para que el jugador no compita con el bajo
        # por el mismo rango espectral. La reverb solo va a instrumentos
        # "puntuales" (plucks, bells, leads cortos): en pads y atmos crea
        # colas superpuestas que suenan como bings metalicos.
        nota_c = aplicar_eq(arr[:, 0], inst_eq, inst_eq_int)
        nota_c = filtro_hpf(nota_c, cutoff_hz=130)
        if aplicar_reverb:
            nota_c = reverb_ambiente(nota_c, mezcla=0.14)
        c_cortas[midi] = np_to_sound(nota_c, lpf=True)
        params_hold = dict(params)
        # holds: envolvente casi plana para eliminar el pumping ciclico del loop.
        # antes: sustain=0.5, decay=1.5 -> la amplitud caia de 1.0 a 0.55 dentro
        # del sample de 1.6s y saltaba al reiniciar el loop = "wah-wah" audible.
        # ahora: sustain=1.0 (sin caida) y decay chico. El ataque real ya lo hace
        # la nota corta que suena al tocar la tecla; el hold es solo el sostenido.
        params_hold["sustain"] = 1.0
        params_hold["decay"] = 0.3
        # vibrato mas suave para que no salte de fase entre loops
        params_hold["vibrato"] = params.get("vibrato", 0) * 0.7
        params_hold["vib_speed"] = params.get("vib_speed", 5) * 0.8
        # ataque corto: no importa el click porque despues lo cortamos
        params_hold["attack"] = 0.005
        # renderizar 1.9s: los primeros 300ms se DESCARTAN (ataque + estabilizacion),
        # y solo la parte 100% estable (~1.6s) queda como material del loop.
        # asi el pumping desaparece: el sample loopea solo sobre steady state.
        snd_l = synth_nota(tipo, freq, 1.9, params_hold)
        arr_l = pygame.sndarray.array(snd_l).astype(np.float64) / 32767
        mono_l = aplicar_eq(arr_l[:, 0], inst_eq, inst_eq_int)
        # mismo HPF que en la nota corta: el sostenido tambien deja el rango
        # sub-grave libre al bajo. Se aplica ANTES del skip/crossfade para
        # que el filtro no introduzca artefactos en la costura del loop.
        mono_l = filtro_hpf(mono_l, cutoff_hz=130)
        # descartar ataque + zona de estabilizacion
        skip = int(SR * 0.30)
        mono_l = mono_l[skip:].copy()
        # crossfade LARGO (150ms) con curva coseno igual-potencia para
        # que la costura del loop sea inaudible. Antes: 68ms con rampa lineal.
        cf = min(int(SR * 0.15), len(mono_l) // 3)
        if cf > 100:
            xs = np.linspace(0, np.pi / 2, cf)
            fade_out = np.cos(xs)   # 1 -> 0 con curva coseno
            fade_in  = np.sin(xs)   # 0 -> 1 con curva seno (suma cuadratica = 1)
            mono_l[-cf:] = mono_l[-cf:] * fade_out + mono_l[:cf] * fade_in
        # fade-in muy corto al principio del sample para arrancar limpio
        # (por si el hold suena antes que la nota corta)
        fi = min(int(SR * 0.008), len(mono_l) // 8)
        if fi > 10:
            mono_l[:fi] *= np.linspace(0, 1, fi)
        c_largas[midi] = np_to_sound(mono_l, lpf=True)
    cache_por_instrumento[nombre] = c_cortas
    cache_largas_por_instrumento[nombre] = c_largas

def dibujar_carga_seed_inst(progreso, nombre):
    """Pantalla de carga mientras se renderiza el instrumento de la seed"""
    pantalla.fill(NEGRO)
    for _ in range(3):
        if random.random() < 0.6:
            spawn_burbuja()
    for b in burbujas_carga:
        b["t"] += 0.06
        b["x"] += b["dx"] + math.sin(b["t"] * b["wobble_speed"]) * b["wobble"]
        b["y"] += b["dy"]
    burbujas_carga[:] = [b for b in burbujas_carga if b["y"] > -50]
    for b in burbujas_carga:
        pct_y = max(0, min(1, b["y"] / ALTO))
        alpha = int(b["alpha"] * (0.2 + 0.8 * pct_y))
        color = (min(255, alpha), min(255, alpha), min(255, alpha))
        dibujar_nota_musical(pantalla, b["x"], b["y"], b["size"], color)
    titulo = fuente_grande.render("* RHYTHM *", True, BLANCO)
    pantalla.blit(titulo, (ANCHO // 2 - titulo.get_width() // 2, 120))
    gen_txt = fuente.render("GENERANDO SEED...", True, GRIS_MED)
    pantalla.blit(gen_txt, (ANCHO // 2 - gen_txt.get_width() // 2, 230))
    inst_txt = fuente.render(nombre, True, BLANCO)
    pantalla.blit(inst_txt, (ANCHO // 2 - inst_txt.get_width() // 2, 270))
    barra_w = 300
    barra_x = ANCHO // 2 - barra_w // 2
    barra_y = 330
    pygame.draw.rect(pantalla, GRIS, (barra_x, barra_y, barra_w, 16))
    bloques = int(barra_w * progreso) // 8
    for bl in range(bloques):
        pygame.draw.rect(pantalla, BLANCO, (barra_x + bl * 8 + 1, barra_y + 2, 6, 12))
    pygame.draw.rect(pantalla, BLANCO, (barra_x, barra_y, barra_w, 16), 2)
    presentar()
    for ev in pygame.event.get():
        if ev.type == pygame.QUIT:
            pygame.quit()
            exit()

# carga inicial: solo SQUARE para arrancar rápido
print("Carga inicial...")
dibujar_pantalla_carga(0.5, "SQUARE", 1, 1)
renderizar_instrumento("SQUARE", "square")
dibujar_pantalla_carga(1.0, "SQUARE", 1, 1)

cache_notas = cache_por_instrumento["SQUARE"]
cache_notas_largas = cache_largas_por_instrumento["SQUARE"]

print("Notas OK")

canal_hold = {}
particulas = []
textos_flotantes = []
flashes = []         # {col, vida, vida_max}
ondas = []           # anillos de choque expansivos
indicadores_hit = [] # {col_idx, color, vida, vida_max} semaforo de precision
shake_amt = 0.0      # intensidad del shake actual
shake_dx = 0
shake_dy = 0

# --- musica de fondo en el menu (seeds aleatorias DIFICIL+, crossfade) ---
musica_menu = None          # stream principal
_menu_fadeout = None        # stream anterior (fading out durante crossfade)
_menu_siguiente = None      # (cancion, dif) pre-renderizada lista para usar
_menu_preparando = False    # True mientras el thread de background esta trabajando
CROSSFADE_MS = 3000         # duracion del crossfade en ms
PREPARAR_DESPUES_MS = 3000  # empezar a preparar la sig. 3s despues de arrancar la actual

def iniciar_musica_menu(cancion, dificultad):
    """Prepara la reproduccion completa de fondo para el menu"""
    global musica_menu
    try:
        inst = cancion["instrumento"]
        if inst not in cache_por_instrumento:
            return
        pan_perc = {
            "kick": (1.0, 1.0), "snare": (1.0, 1.0), "clap": (0.95, 0.95),
            "hihat": (0.7, 1.0), "hihat_o": (0.7, 1.0),
            "clave": (1.0, 0.7), "agogo": (1.0, 0.65),
            "crash": (0.9, 0.9), "tom1": (1.0, 0.8), "tom2": (0.8, 1.0),
        }
        musica_menu = {
            "notas": cancion["notas_jugador"],
            "percusion": cancion["percusion"],
            "bajo_eventos": cancion["bajo"]["eventos"],
            "kit": cancion["kit"],
            "cache_bajo": cancion.get("cache_bajo", {}),
            "pan_perc": pan_perc,
            "duracion": cancion["duracion_loop"],
            "num_cols": dificultad["columnas"],
            "inst": inst,
            "idx_notas": 0,
            "idx_perc": 0,
            "idx_bajo": 0,
            "inicio": pygame.time.get_ticks(),
        }
    except Exception as e:
        print(f"Error iniciando musica menu: {e}")
        musica_menu = None

def detener_musica_menu():
    global musica_menu, _menu_fadeout, _menu_siguiente
    musica_menu = None
    _menu_fadeout = None
    _menu_siguiente = None

def cortar_audio_suave(ms=200):
    """Apaga todos los canales con un fade corto en vez de stop() abrupto.
    Cortar el audio de golpe deja la onda a mitad de ciclo y produce un
    'pop'/click. El fade lleva la señal a cero suavemente. Se usa al arrancar
    una cancion (mientras se muestra la pantalla de carga, no se nota la espera)."""
    try:
        pygame.mixer.fadeout(ms)
    except Exception:
        pygame.mixer.stop()

# rango de seeds para la musica del menu: de DIFICIL en adelante
SEED_MENU_MIN = 4901   # primer tramo de DIFICIL en get_dificultad

# ════════════════════════════════════════════════════ >>MUSICA_MENU<< ═══

def _preparar_cancion_menu(seed):
    """Genera una cancion para el menu, renderizando instrumento y bajo si faltan."""
    dif = get_dificultad(seed)
    cancion = generar_cancion(int(seed * 23819), dif)
    inst = cancion["instrumento"]
    if inst not in cache_por_instrumento:
        tipo = INSTRUMENTOS_JUGADOR.get(inst) or INSTRUMENTOS_RAROS.get(inst)
        if tipo:
            renderizar_instrumento(inst, tipo, dibujar_progreso=False)
    # pre-renderizar bajo
    estilo_b = cancion["bajo"]["estilo"]
    cache_bajo = {}
    for mb in set(e["midi"] for e in cancion["bajo"]["eventos"]):
        wave_b = synth_bajo(midi_a_freq(mb), 0.5, estilo_b)
        cache_bajo[mb] = np_to_sound(wave_b, vol=0.3, pan=0.0)
    cancion["cache_bajo"] = cache_bajo
    return cancion, dif

def _preparar_en_background():
    """Thread de background: genera la siguiente cancion sin trabar el juego."""
    global _menu_siguiente, _menu_preparando
    try:
        seed = random.randint(SEED_MENU_MIN, SEED_MAX)
        resultado = _preparar_cancion_menu(seed)
        _menu_siguiente = resultado
    except Exception:
        try:
            ruta = os.path.join(BASE_DIR, "crash_log.txt")
            with open(ruta, "a", encoding="utf-8") as f:
                f.write("\n[thread pre-render background]\n")
                traceback.print_exc(file=f)
        except Exception:
            pass
        traceback.print_exc()
    finally:
        _menu_preparando = False

_prerender_stage_activo = False

def prerender_instrumento_seed(seed, instrumento=None):
    """Renderiza en background un instrumento (proximo stage).
    Si se pasa 'instrumento', lo usa directo; si no, lo deriva de la seed.
    Asi cuando llegas a ese stage, ya esta en cache y la carga es instantanea."""
    global _prerender_stage_activo
    if _prerender_stage_activo:
        return
    def _worker():
        global _prerender_stage_activo
        _prerender_stage_activo = True
        try:
            if instrumento:
                inst = instrumento
            else:
                dif = get_dificultad(seed)
                cancion = generar_cancion(int(seed * 23819), dif)
                inst = cancion["instrumento"]
            if inst not in cache_por_instrumento:
                tipo = INSTRUMENTOS_JUGADOR.get(inst) or INSTRUMENTOS_RAROS.get(inst)
                if tipo:
                    renderizar_instrumento(inst, tipo, dibujar_progreso=False)
        except Exception:
            pass
        finally:
            _prerender_stage_activo = False
    t = threading.Thread(target=_worker, daemon=True)
    t.start()

def nueva_musica_menu_aleatoria():
    """Arranca musica de menu. Usa la cancion pre-renderizada en background
    si esta lista (instantaneo); si no, renderiza una rapida sincrona."""
    global _menu_siguiente, _menu_fadeout, _menu_preparando
    try:
        # si el thread ya preparo una cancion, usarla (instantaneo)
        if _menu_siguiente is not None:
            cancion, dif = _menu_siguiente
            _menu_siguiente = None
        else:
            seed = random.randint(SEED_MENU_MIN, SEED_MAX)
            cancion, dif = _preparar_cancion_menu(seed)
        iniciar_musica_menu(cancion, dif)
        _menu_fadeout = None
        # arrancar pre-render de la proxima en background para la siguiente transicion
        if not _menu_preparando:
            _menu_preparando = True
            t = threading.Thread(target=_preparar_en_background, daemon=True)
            t.start()
    except Exception as e:
        print(f"Error generando musica de menu aleatoria: {e}")

def _tick_stream(mm, vol_mult):
    """Reproduce un frame de un stream de musica (melodia+perc+bajo)."""
    ahora = pygame.time.get_ticks() - mm["inicio"]
    if ahora < 0 or ahora >= mm["duracion"]:
        return
    vol_base = config["vol_menu"] * config["volumen"] * vol_mult
    if vol_base < 0.01:
        return
    # --- melodia ---
    c_notas = cache_por_instrumento.get(mm["inst"])
    if c_notas:
        notas = mm["notas"]
        num_cols = mm["num_cols"]
        while mm["idx_notas"] < len(notas) and ahora >= notas[mm["idx_notas"]]["tiempo"]:
            n = notas[mm["idx_notas"]]
            mm["idx_notas"] += 1
            if not n.get("midis"):
                continue
            midi = n["midis"][0]
            snd = c_notas.get(midi)
            if not snd:
                continue
            col = n["cols"][0] if n["cols"] else 0
            pan = col / max(1, num_cols - 1)
            vol_l = vol_base * (1.0 - pan * 0.6)
            vol_r = vol_base * (0.4 + pan * 0.6)
            ch = snd.play()
            if ch:
                ch.set_volume(vol_l, vol_r)
    # --- percusion ---
    perc = mm["percusion"]
    kit = mm["kit"]
    pan_p = mm["pan_perc"]
    vol_perc = vol_base * 0.7
    while mm["idx_perc"] < len(perc) and ahora >= perc[mm["idx_perc"]]["tiempo"]:
        p = perc[mm["idx_perc"]]
        mm["idx_perc"] += 1
        sample = kit.get(p["sample"])
        if not sample:
            continue
        vol = min(1.0, p["vol"]) * vol_perc
        gl, gr = pan_p.get(p["sample"], (1.0, 1.0))
        ch = sample.play()
        if ch:
            ch.set_volume(vol * gl, vol * gr)
    # --- bajo ---
    bajo = mm["bajo_eventos"]
    cache_b = mm["cache_bajo"]
    vol_bajo = vol_base * 0.8
    while mm["idx_bajo"] < len(bajo) and ahora >= bajo[mm["idx_bajo"]]["tiempo"]:
        ev = bajo[mm["idx_bajo"]]
        mm["idx_bajo"] += 1
        snd_b = cache_b.get(ev["midi"])
        if not snd_b:
            continue
        ch = snd_b.play()
        if ch:
            ch.set_volume(vol_bajo)

def tick_musica_menu():
    """Reproduce musica en el menu con crossfade entre canciones.
    La siguiente cancion se pre-renderiza en un thread de background
    para que la transicion sea imperceptible."""
    global musica_menu, _menu_fadeout, _menu_siguiente, _menu_preparando
    # tick del stream que esta fading out (si hay crossfade activo)
    if _menu_fadeout is not None:
        ahora_fo = pygame.time.get_ticks() - _menu_fadeout["fade_start"]
        fade_out = max(0.0, 1.0 - ahora_fo / CROSSFADE_MS)
        if fade_out <= 0.0:
            _menu_fadeout = None
        else:
            _tick_stream(_menu_fadeout, fade_out)
    if musica_menu is None:
        return
    mm = musica_menu
    ahora = pygame.time.get_ticks() - mm["inicio"]
    restante = mm["duracion"] - ahora
    # 1) lanzar thread para pre-renderizar la siguiente (3s despues de arrancar)
    #    el thread tiene toda la duracion de la cancion (~30s+) para terminar
    if ahora > PREPARAR_DESPUES_MS and _menu_siguiente is None and not _menu_preparando:
        _menu_preparando = True
        t = threading.Thread(target=_preparar_en_background, daemon=True)
        t.start()
    # 2) iniciar crossfade cuando quedan CROSSFADE_MS y la siguiente esta lista
    if restante <= CROSSFADE_MS and not mm.get("crossfading"):
        if _menu_siguiente is not None:
            mm["crossfading"] = True
            mm["fade_start"] = pygame.time.get_ticks()
            _menu_fadeout = mm
            cancion, dif = _menu_siguiente
            _menu_siguiente = None
            iniciar_musica_menu(cancion, dif)
            if musica_menu is not None:
                musica_menu["fade_in_start"] = pygame.time.get_ticks()
            return
        # si el thread no termino aun, esperar (la cancion seguira en silencio
        # unos instantes hasta que el thread termine y el proximo frame haga crossfade)
    # 3) si la cancion ya paso y no hubo crossfade (thread llego tarde),
    #    arrancar la siguiente apenas este lista
    if ahora >= mm["duracion"] and not mm.get("crossfading"):
        if _menu_siguiente is not None:
            cancion, dif = _menu_siguiente
            _menu_siguiente = None
            _menu_fadeout = None
            iniciar_musica_menu(cancion, dif)
            if musica_menu is not None:
                musica_menu["fade_in_start"] = pygame.time.get_ticks()
        return
    # 4) calcular volumen con fade-in si recien arranco
    vol_mult = 1.0
    if mm.get("fade_in_start"):
        elapsed = pygame.time.get_ticks() - mm["fade_in_start"]
        vol_mult = min(1.0, elapsed / CROSSFADE_MS)
        if vol_mult >= 1.0:
            del mm["fade_in_start"]
    # 5) reproducir stream principal
    _tick_stream(mm, vol_mult)

def _color_vivo(base, combo=0):
    """Devuelve un color variado a partir del color base del genero.
    Con combos altos, mas probabilidad de colores brillantes/arcoiris."""
    prob_arcoiris = min(combo / 40.0, 0.6)
    if random.random() < prob_arcoiris:
        # color arcoiris vibrante (HSV -> RGB simplificado)
        h = random.random()
        i = int(h * 6)
        f = h * 6 - i
        v, p, q, tt = 255, 40, int(255 * (1 - f)), int(255 * f)
        return [(v,tt,p),(q,v,p),(p,v,tt),(p,q,v),(tt,p,v),(v,p,q)][i % 6]
    r = random.random()
    if r < 0.4:
        return base
    elif r < 0.7:
        # mezcla con blanco (mas brillante)
        return tuple(min(255, int(c + (255 - c) * 0.6)) for c in base)
    else:
        # version saturada del base
        return tuple(min(255, int(c * 1.3 + 30)) for c in base)

# ══════════════════════════════════════════════════════ >>PARTICULAS<< ═══

def crear_explosion(x, y, cantidad, color=BLANCO, potencia=1.0, combo=0):
    for _ in range(cantidad):
        angulo = random.uniform(0, 6.28)
        fuerza = random.uniform(2, 14) * potencia
        dx = math.cos(angulo) * fuerza
        dy = math.sin(angulo) * fuerza - 5 * potencia
        vida = random.randint(25, 65) + int((potencia - 1) * 15)
        tam = int(random.randint(3, 12) * (0.8 + potencia * 0.4))
        forma = random.choice(["rect", "rect", "linea", "estrella"])
        # color destino: la particula nace blanca y vira a este color con el tiempo
        col_destino = _color_vivo(color, combo)
        particulas.append({"x": x, "y": y, "dx": dx, "dy": dy, "vida": vida,
                           "vida_max": vida, "tam": tam, "color": col_destino, "forma": forma,
                           "spin": random.uniform(-0.4, 0.4)})

def crear_onda(x, y, intensidad=1.0, r0=4):
    ondas.append({"x": x, "y": y, "r": r0, "vida": 20, "vida_max": 20, "intensidad": intensidad})

# colores del semaforo de precision
COL_HIT_PERFECTO = (60, 230, 90)    # verde
COL_HIT_CERCA    = (240, 210, 40)   # amarillo
COL_HIT_ERROR    = (235, 55, 55)    # rojo

def crear_indicador_hit(col_idx, calidad):
    """Enciende el indicador de una columna. calidad: 'perfecto', 'cerca', 'error'."""
    color = {"perfecto": COL_HIT_PERFECTO,
             "cerca": COL_HIT_CERCA,
             "error": COL_HIT_ERROR}.get(calidad, COL_HIT_ERROR)
    # reemplazar indicador previo de esa columna si existe
    indicadores_hit[:] = [i for i in indicadores_hit if i["col_idx"] != col_idx]
    indicadores_hit.append({"col_idx": col_idx, "color": color,
                            "vida": 22, "vida_max": 22})

def crear_flash(col, intensidad=1.0):
    flashes.append({"col": col, "vida": 14, "vida_max": 14, "intensidad": intensidad})

def crear_shake(intensidad):
    global shake_amt
    shake_amt = max(shake_amt, intensidad)

def crear_texto_flotante(x, y, texto, color=BLANCO, grande=False):
    textos_flotantes.append({
        "x": x, "y": y, "texto": texto, "color": color,
        "vida": 60, "vida_max": 60, "grande": grande,
    })

def actualizar_particulas():
    global shake_amt, shake_dx, shake_dy
    for p in particulas:
        p["x"] += p["dx"]
        p["y"] += p["dy"]
        p["dy"] += 0.18
        p["dx"] *= 0.97
        p["vida"] -= 1
    particulas[:] = [p for p in particulas if p["vida"] > 0]
    for t in textos_flotantes:
        t["y"] -= 1.5
        t["vida"] -= 1
    textos_flotantes[:] = [t for t in textos_flotantes if t["vida"] > 0]
    for f in flashes:
        f["vida"] -= 1
    flashes[:] = [f for f in flashes if f["vida"] > 0]
    for o in ondas:
        o["r"] += 6
        o["vida"] -= 1
    ondas[:] = [o for o in ondas if o["vida"] > 0]
    for ind in indicadores_hit:
        ind["vida"] -= 1
    indicadores_hit[:] = [i for i in indicadores_hit if i["vida"] > 0]
    # shake decay
    if shake_amt > 0:
        shake_dx = random.randint(int(-shake_amt), int(shake_amt))
        shake_dy = random.randint(int(-shake_amt), int(shake_amt))
        shake_amt *= 0.85
        if shake_amt < 0.5:
            shake_amt = 0
            shake_dx = 0
            shake_dy = 0

def dibujar_particulas():
    # anillos de choque
    for o in ondas:
        pct = o["vida"] / o["vida_max"]
        alpha = pct * o["intensidad"]
        c = int(200 * alpha)
        col = (c, c, c)
        grosor = max(1, int(3 * pct))
        pygame.draw.circle(pantalla, col, (int(o["x"]) + shake_dx, int(o["y"]) + shake_dy), int(o["r"]), grosor)
    for p in particulas:
        pct = p["vida"] / p["vida_max"]
        base = p["color"]
        # edad: 0 = recien nacida, 1 = a punto de morir
        edad = 1.0 - pct
        # la particula nace blanca y toma su color destino gradualmente
        # (mezcla mas rapido al principio para que el blanco sea un destello)
        tinte = min(1.0, edad * 1.8)
        r = int(255 + (base[0] - 255) * tinte)
        g = int(255 + (base[1] - 255) * tinte)
        b = int(255 + (base[2] - 255) * tinte)
        # atenuar al final de la vida (fade out)
        atenua = min(1.0, pct * 1.6)
        color = (int(r * atenua), int(g * atenua), int(b * atenua))
        tam = max(1, int(p["tam"] * pct))
        px = int(p["x"]) + shake_dx
        py = int(p["y"]) + shake_dy
        if p["forma"] == "linea":
            ex = int(px - p["dx"] * 1.5)
            ey = int(py - p["dy"] * 1.5)
            pygame.draw.line(pantalla, color, (px, py), (ex, ey), max(1, tam // 2))
        elif p["forma"] == "estrella":
            # estrella de 4 puntas (cruz + diagonal tenue)
            r = tam
            pygame.draw.line(pantalla, color, (px - r, py), (px + r, py), 2)
            pygame.draw.line(pantalla, color, (px, py - r), (px, py + r), 2)
            h = max(1, r // 2)
            pygame.draw.line(pantalla, color, (px - h, py - h), (px + h, py + h), 1)
            pygame.draw.line(pantalla, color, (px - h, py + h), (px + h, py - h), 1)
        else:
            pygame.draw.rect(pantalla, color, (px, py, tam, tam))
    for t in textos_flotantes:
        pct = t["vida"] / t["vida_max"]
        base = t["color"]
        color = (int(base[0] * pct), int(base[1] * pct), int(base[2] * pct))
        f = fuente if t["grande"] else fuente_chica
        txt = f.render(t["texto"], True, color)
        pantalla.blit(txt, (int(t["x"]) - txt.get_width() // 2 + shake_dx, int(t["y"]) + shake_dy))

def nota_midi(tonica, escala, grado):
    octava = grado // len(escala)
    return tonica + escala[grado % len(escala)] + octava * 12

def _escala_es_menor(escala):
    """Detecta si una escala es menor: la tercera (grado 2) esta a 3 semitonos."""
    return len(escala) >= 3 and escala[2] == 3

def tonos_acorde(tonica_midi, escala, grado):
    """Devuelve los 3 tonos (triada) de un acorde sobre 'grado' de la escala:
    fundamental, tercera y quinta (grados +2 y +4).
    En escalas menores, el acorde de dominante (V) recibe la tercera mayor
    (nota sensible) para crear la tension-resolucion caracteristica de la
    musica tonal: la sensible sube un semitono para resolver a la tonica."""
    fund = nota_midi(tonica_midi, escala, grado)
    terc = nota_midi(tonica_midi, escala, grado + 2)
    quin = nota_midi(tonica_midi, escala, grado + 4)
    if grado in GRADOS_DOMINANTE and _escala_es_menor(escala):
        # subir la tercera del V medio tono -> sensible (dominante mayor)
        terc += 1
    return [fund, terc, quin]

def tonos_septima(tonica_midi, escala, grado):
    """Como tonos_acorde pero agrega la septima (grado +6) para acordes de 4 notas.
    Enriquece la armonia en acordes tocados por el jugador."""
    base = tonos_acorde(tonica_midi, escala, grado)
    sept = nota_midi(tonica_midi, escala, grado + 6)
    return base + [sept]

def ajustar_a_acorde(midi, tonos_ac, escala, tonica_midi, fuerza=1.0):
    """Corrige una nota MIDI hacia el tono de acorde mas cercano.
    fuerza=1.0 -> siempre al tono de acorde; 0.0 -> sin cambio.
    Preserva la octava original para no romper el contorno melodico."""
    if not tonos_ac:
        return midi
    # normalizar a clases de altura (0-11) para comparar
    pc = midi % 12
    mejor = None
    mejor_dist = 99
    for ta in tonos_ac:
        d = abs((ta % 12) - pc)
        d = min(d, 12 - d)
        if d < mejor_dist:
            mejor_dist = d
            mejor = ta
    if mejor is None:
        return midi
    # mover la nota a la clase del tono de acorde, en la octava original
    octava_orig = midi // 12
    nuevo = (mejor % 12) + octava_orig * 12
    # elegir la octava mas cercana a la nota original
    for cand in (nuevo, nuevo + 12, nuevo - 12):
        if abs(cand - midi) < abs(nuevo - midi):
            nuevo = cand
    return nuevo

def resolver_disonancia(midi, tonos_ac, escala, tonica_midi):
    """Resuelve una nota disonante por grado conjunto descendente al tono de
    acorde mas cercano hacia abajo (convencion: las tensiones bajan para
    resolver). Si ya es tono de acorde, la deja igual."""
    if not tonos_ac:
        return midi
    pc = midi % 12
    clases_ac = {t % 12 for t in tonos_ac}
    if pc in clases_ac:
        return midi  # ya es consonante
    # buscar el tono de acorde mas cercano hacia abajo (resolucion descendente)
    for baja in range(1, 4):
        cand_pc = (pc - baja) % 12
        if cand_pc in clases_ac:
            return midi - baja
    # si no encuentra abajo, usar el ajuste normal
    return ajustar_a_acorde(midi, tonos_ac, escala, tonica_midi)

NOMBRES_NOTAS = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
def midi_a_nombre(midi):
    return NOMBRES_NOTAS[midi % 12] + str(midi // 12 - 1)

# --- leaderboard ---
LEADERBOARD_FILE = os.path.join(BASE_DIR, "leaderboard.json")
TOP_SCORES = 10

# --- progreso de runs completados (genero x dificultad) ---
PROGRESO_FILE = os.path.join(BASE_DIR, "progreso.json")

# --- MODO CARRERA: desbloqueo progresivo de dificultades ---
CARRERA_FILE = os.path.join(BASE_DIR, "carrera.json")

def cargar_carrera():
    """Carga el progreso del modo carrera. Devuelve dict con:
      nivel_max: mayor nivel desbloqueado (1-15, empieza en 1)
      ranks: {str(nivel): "S"/"A"/... } mejor rank por nivel
      intentos: {str(nivel): int} veces que lo intentaste"""
    try:
        with open(CARRERA_FILE, "r") as f:
            return json.load(f)
    except:
        return {"nivel_max": 1, "ranks": {}, "intentos": {}}

def guardar_carrera(data):
    try:
        with open(CARRERA_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Error guardando carrera: {e}")

def carrera_completar_nivel(nivel, rank):
    """Registra que se completo un nivel de la carrera. Desbloquea el
    siguiente y guarda el mejor rank."""
    c = cargar_carrera()
    nk = str(nivel)
    # guardar mejor rank (S > A > B > C > D)
    orden = {"S": 5, "A": 4, "B": 3, "C": 2, "D": 1, "?": 0}
    viejo = c.get("ranks", {}).get(nk, "?")
    if orden.get(rank, 0) > orden.get(viejo, 0):
        c.setdefault("ranks", {})[nk] = rank
    # desbloquear siguiente
    if nivel >= c.get("nivel_max", 1) and nivel < 15:
        c["nivel_max"] = nivel + 1
    guardar_carrera(c)
    return c

def carrera_registrar_intento(nivel):
    c = cargar_carrera()
    nk = str(nivel)
    c.setdefault("intentos", {})[nk] = c.get("intentos", {}).get(nk, 0) + 1
    guardar_carrera(c)

def cargar_progreso():
    """Devuelve un set de claves 'GENERO|nivel' completadas."""
    try:
        with open(PROGRESO_FILE, "r") as f:
            return set(json.load(f))
    except:
        return set()

def guardar_progreso(completados):
    try:
        with open(PROGRESO_FILE, "w") as f:
            json.dump(sorted(completados), f, indent=2)
    except Exception as e:
        print(f"Error guardando progreso: {e}")

def calcular_rank_stage(partida):
    """Rank de performance del stage segun precision ponderada, estilo
    rhythm game clasico. PERFECTO=1.0, BIEN=0.7, OK=0.4, MAL/MISS=0.
      S: >=95% | A: >=85% | B: >=70% | C: >=50% | D: <50%"""
    p = partida.get("n_perfecto", 0)
    b = partida.get("n_bien", 0)
    o = partida.get("n_ok", 0)
    m = partida.get("n_mal", 0)
    mi = partida.get("n_miss", 0)
    total = p + b + o + m + mi
    if total == 0:
        return "?"
    acc = (p * 1.0 + b * 0.7 + o * 0.4) / total
    if acc >= 0.95:
        return "S"
    elif acc >= 0.85:
        return "A"
    elif acc >= 0.70:
        return "B"
    elif acc >= 0.50:
        return "C"
    return "D"

def clave_run(genero, nivel):
    return f"{genero}|{nivel}"

def marcar_completado(genero, nivel):
    comp = cargar_progreso()
    comp.add(clave_run(genero, nivel))
    guardar_progreso(comp)
    return comp

def cargar_leaderboard():
    try:
        with open(LEADERBOARD_FILE, "r") as f:
            return json.load(f)
    except:
        return []

def guardar_leaderboard(lb):
    with open(LEADERBOARD_FILE, "w") as f:
        json.dump(lb, f, indent=2)

def es_highscore(puntos):
    lb = cargar_leaderboard()
    if len(lb) < TOP_SCORES:
        return True
    return puntos > lb[-1]["puntos"]

def agregar_score(nombre, puntos, seed, dificultad, max_combo):
    lb = cargar_leaderboard()
    lb.append({
        "nombre": nombre,
        "puntos": puntos,
        "seed": seed,
        "dificultad": dificultad,
        "max_combo": max_combo,
    })
    lb.sort(key=lambda x: x["puntos"], reverse=True)
    lb = lb[:TOP_SCORES]
    guardar_leaderboard(lb)
    return lb

def dibujar_leaderboard():
    pantalla.fill(NEGRO)
    titulo = fuente_grande.render("LEADERBOARD", True, BLANCO)
    pantalla.blit(titulo, (ANCHO // 2 - titulo.get_width() // 2, 30))
    pygame.draw.line(pantalla, BLANCO, (60, 90), (ANCHO - 60, 90), 2)

    lb = cargar_leaderboard()
    if not lb:
        vacio = fuente_chica.render("NO HAY SCORES TODAVIA", True, GRIS_MED)
        pantalla.blit(vacio, (ANCHO // 2 - vacio.get_width() // 2, 200))
    else:
        header = fuente_chica.render("  #   NOMBRE         PUNTOS   COMBO  SEED    DIF", True, GRIS_MED)
        pantalla.blit(header, (40, 110))
        pygame.draw.line(pantalla, GRIS, (40, 128), (ANCHO - 40, 128), 1)
        for i, sc in enumerate(lb):
            color = BLANCO if i < 3 else GRIS_MED
            nom = sc["nombre"][:12].ljust(12)
            linea = f"  {i+1:>2}   {nom}   {sc['puntos']:>6}   {sc['max_combo']:>4}x  {sc['seed']:>5}   {sc['dificultad']}"
            txt = fuente_chica.render(linea, True, color)
            pantalla.blit(txt, (40, 140 + i * 28))

    volver = fuente_chica.render("ESC PARA VOLVER", True, GRIS)
    pantalla.blit(volver, (ANCHO // 2 - volver.get_width() // 2, ALTO - 30))

def dibujar_input_nombre(nombre_actual):
    pantalla.fill(NEGRO)
    titulo = fuente_grande.render("HIGH SCORE!", True, BLANCO)
    pantalla.blit(titulo, (ANCHO // 2 - titulo.get_width() // 2, 150))

    inst = fuente.render("INGRESA TU NOMBRE:", True, GRIS_MED)
    pantalla.blit(inst, (ANCHO // 2 - inst.get_width() // 2, 250))

    nombre_txt = fuente_grande.render(nombre_actual + "_", True, BLANCO)
    pantalla.blit(nombre_txt, (ANCHO // 2 - nombre_txt.get_width() // 2, 310))

    enter = fuente_chica.render("ENTER PARA CONFIRMAR", True, GRIS)
    pantalla.blit(enter, (ANCHO // 2 - enter.get_width() // 2, 400))

def get_dificultad(seed):
    if seed <= 0:
        d = dict(DIFICULTADES[1]); d["nivel"] = 1; return d
    # FACIL y FACIL+ ocupan el 25% inicial del selector (antes 9%) para que
    # el jugador nuevo tenga mas seeds jugables. Los tramos medios y altos
    # se comprimen proporcionalmente, manteniendo GOD y CHAOS al final.
    tramos = [1500, 2500, 3200, 3800, 4400, 5000, 5600, 6200, 6800,
              7300, 7800, 8300, 8800, 9400, 9999]
    for i, tope in enumerate(tramos):
        if seed <= tope:
            d = dict(DIFICULTADES[i + 1]); d["nivel"] = i + 1; return d
    d = dict(DIFICULTADES[15]); d["nivel"] = 15; return d

# --- meta de puntuacion por stage (objetivo roguelike) ---
# la meta base escala con el nivel de dificultad; stages sucesivos piden mas
META_BASE = {
    # niveles mas largos en general, y progresivamente MAS largos a partir
    # de NORMAL (nivel 3): el factor de escala sube ~x1.2 en facil hasta
    # ~x2.5 en GOD/CHAOS. La meta controla la duracion real del stage
    # (la cancion loopea hasta alcanzarla).
    1: 150,   2: 220,   3: 420,   4: 680,   5: 950,
    6: 1350,  7: 2000,  8: 2850,  9: 4000,  10: 5900,
    11: 7700, 12: 10500, 13: 14500, 14: 20000, 15: 25000,
}
META_MULT_STAGE = {1: 1.0, 2: 1.3, 3: 1.6, 4: 2.0}

def calcular_meta(nivel_dif, stage_n):
    """Devuelve la meta de puntos para un stage (puntos a ganar EN ese stage)."""
    base = META_BASE.get(nivel_dif, 1000)
    mult = META_MULT_STAGE.get(stage_n, 1.0)
    return int(base * mult)

def elegir_kit(rng):
    return sintetizar_kit(rng)

# =========================================================================
# GENEROS MUSICALES
# Cada genero define su personalidad completa: BPM, escalas, drums, bajo,
# instrumentos que encajan, tendencia a half/double-time y densidad.
# Los patrones de drums son listas de 16 pasos (16avos por compas).
# =========================================================================
GENEROS = {
    "TECHNO": {
        "bpm": (124, 138),
        "escalas": ["menor", "arm_menor", "pentatonica"],
        "drums": {
            "kick":  [[1,0,0,0,1,0,0,0,1,0,0,0,1,0,0,0]],   # 4-on-the-floor
            "snare": [[0,0,0,0,1,0,0,0,0,0,0,0,1,0,0,0],
                      [0,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0]],
            "hihat": [[0,0,1,0,0,0,1,0,0,0,1,0,0,0,1,0],
                      [1,0,1,0,1,0,1,0,1,0,1,0,1,0,1,0]],
            "hihat_o":[0,0,0,0,0,0,1,0,0,0,0,0,0,0,1,0],
            "clap":  [0,0,0,0,1,0,0,0,0,0,0,0,1,0,0,0],
        },
        "bajo_estilos": ["reese", "sub", "round"],
        "bajo_patrones": [[1,0,1,0,1,0,1,0,1,0,1,0,1,0,1,0],
                          [1,0,0,0,1,0,0,0,1,0,0,0,1,0,0,0]],
        "instrumentos": ["SAW", "SUPERSAW", "ACID", "RESO", "HOOVER", "SAW STACK",
                         "PWM LEAD", "SYNC LEAD", "DETUNE", "GROWL", "WOBBLE"],
        "tempo_mod": {"half": 0.15, "double": 0.15},
        "densidad": 1.0,
        "swing": 0.0,
        "registro": 0,
        # minimal repetitivo: pocas notas, siempre en el mismo lugar (hipnotico)
        "pat_melodia": [
            [1,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0],   # 1, 3 (estable, maquinal)
            [1,0,0,0,0,0,1,0,1,0,0,0,0,0,1,0],   # 1, &2, 3, &4 (loop tipico)
            [0,0,1,0,0,0,1,0,0,0,1,0,0,0,1,0],   # puro offbeat (stab tipico)
        ],
    },
    "HOUSE": {
        "bpm": (120, 128),
        "escalas": ["mayor", "menor", "arm_menor"],
        "drums": {
            "kick":  [[1,0,0,0,1,0,0,0,1,0,0,0,1,0,0,0]],   # 4-on-the-floor
            "snare": [[0,0,0,0,1,0,0,0,0,0,0,0,1,0,0,0]],
            "hihat": [[0,0,1,0,0,0,1,0,0,0,1,0,0,0,1,0],
                      [1,0,1,0,1,0,1,0,1,0,1,0,1,0,1,0]],
            "hihat_o":[0,0,1,0,0,0,1,0,0,0,1,0,0,0,1,0],   # abierto en offbeats
            "clap":  [0,0,0,0,1,0,0,0,0,0,0,0,1,0,0,0],
        },
        "bajo_estilos": ["round", "pluck", "sub"],
        "bajo_patrones": [[1,0,0,0,1,0,0,0,1,0,0,0,1,0,0,0],
                          [0,0,1,0,0,0,1,0,0,0,1,0,0,0,1,0]],   # offbeat clasico
        "instrumentos": ["ORGAN", "FM EP", "PLUCK", "VOX PAD", "BELLPAD",
                         "SUB PLUCK", "PLUCK SOFT", "DREAM PAD"],
        "tempo_mod": {"half": 0.10, "double": 0.10},
        "densidad": 0.9,
        "swing": 0.03,
        "registro": 0,
        # groove offbeat: notas en los "y" (stabs de organo clasicos de house)
        "pat_melodia": [
            [0,0,1,0,0,0,1,0,0,0,1,0,0,0,1,0],   # todos los offbeats (stab)
            [0,0,1,0,0,0,0,0,0,0,1,0,0,0,1,0],   # &1, &3, &4
            [1,0,0,0,0,0,1,0,0,0,1,0,0,0,0,0],   # 1, &2, &3 (groovy)
        ],
    },
    "DNB": {
        "bpm": (160, 178),
        "escalas": ["menor", "arm_menor", "pentatonica"],
        "drums": {
            "kick":  [[1,0,0,0,0,0,0,0,0,0,1,0,0,0,0,0],   # breakbeat
                      [1,0,0,0,0,0,0,0,0,0,1,0,0,1,0,0]],
            "snare": [[0,0,0,0,1,0,0,0,0,0,0,1,1,0,0,0],
                      [0,0,0,0,1,0,0,0,0,0,0,0,1,0,1,0]],
            "hihat": [[1,0,1,1,1,0,1,0,1,1,1,0,1,0,1,1]],
            "hihat_o":[0,0,1,0,0,0,0,0,0,0,1,0,0,0,0,0],
            "clap":  [0,0,0,0,1,0,0,0,0,0,0,0,1,0,0,0],
        },
        "bajo_estilos": ["reese", "sub"],
        "bajo_patrones": [[1,0,0,0,0,0,0,0,1,0,0,0,1,0,0,0],
                          [1,0,0,0,1,0,0,0,0,0,0,0,1,0,0,0]],
        "instrumentos": ["GROWL", "SAW STACK", "WOBBLE",
                         "SUPERSAW", "HOOVER", "RESO", "ACID", "SYNC LEAD"],
        "tempo_mod": {"half": 0.25, "double": 0.0},
        "densidad": 1.1,
        "swing": 0.0,
        "registro": -12,
        # fragmentado agresivo: rafagas cortas con silencios (estilo neurofunk)
        "pat_melodia": [
            [1,0,1,0,0,0,0,0,1,0,1,0,0,0,0,0],   # doble golpe 1-&1, 3-&3
            [1,0,0,1,0,0,1,0,0,0,0,0,1,0,0,0],   # sincopa 16avo
            [0,0,0,0,1,0,1,0,0,0,0,0,1,0,1,0],   # rafagas en 2 y 4
        ],
    },
    "SYNTHWAVE": {
        "bpm": (100, 118),
        "escalas": ["menor", "mayor", "arm_menor"],
        "drums": {
            "kick":  [[1,0,0,0,1,0,0,0,1,0,0,0,1,0,0,0]],
            "snare": [[0,0,0,0,1,0,0,0,0,0,0,0,1,0,0,0]],
            "hihat": [[1,0,1,0,1,0,1,0,1,0,1,0,1,0,1,0],
                      [0,0,1,0,0,0,1,0,0,0,1,0,0,0,1,0]],
            "hihat_o":[0,0,0,0,0,0,1,0,0,0,0,0,0,0,1,0],
            "clap":  [0,0,0,0,1,0,0,0,0,0,0,0,1,0,0,0],
        },
        "bajo_estilos": ["round", "pluck", "reese"],
        "bajo_patrones": [[1,0,1,0,1,0,1,0,1,0,1,0,1,0,1,0],
                          [1,0,0,1,0,0,1,0,1,0,0,1,0,0,1,0]],
        "instrumentos": ["SUPERSAW", "PAD", "PWM LEAD", "DETUNE", "FM BRASS",
                         "PHASE PAD", "LEAD", "BELLPAD", "SAW", "VOX PAD",
                         "ANALOG STR", "DREAM PAD"],
        "tempo_mod": {"half": 0.10, "double": 0.10},
        "densidad": 0.95,
        "swing": 0.0,
        "arpegios": True,
        "registro": 0,
        # lineas sostenidas y amplias (lead melodico retro)
        "pat_melodia": [
            [1,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0],   # notas largas 1, 3
            [1,0,0,0,0,0,1,0,0,0,0,0,1,0,0,0],   # 1, &2, 4
            [1,0,0,0,1,0,0,0,1,0,0,0,1,0,0,0],   # negras constantes (drive)
        ],
    },
    "TECH HOUSE": {
        "bpm": (122, 128),
        "escalas": ["menor", "arm_menor", "pentatonica"],
        "drums": {
            "kick":  [[1,0,0,0,1,0,0,0,1,0,0,0,1,0,0,0]],   # 4x4 percusivo
            "snare": [[0,0,0,0,1,0,0,0,0,0,0,0,1,0,0,0],
                      [0,0,0,0,1,0,0,1,0,0,0,0,1,0,0,0]],   # con ghost
            "hihat": [[1,1,1,0,1,1,1,0,1,1,1,0,1,1,1,0],   # denso y sincopado
                      [0,1,1,0,1,0,1,1,0,1,1,0,1,0,1,1]],
            "hihat_o":[0,0,1,0,0,0,1,0,0,0,1,0,0,0,1,0],
            "clap":  [0,0,0,0,1,0,0,0,0,0,0,0,1,0,0,0],
        },
        "bajo_estilos": ["sub", "reese", "round"],
        "bajo_patrones": [[1,0,0,0,1,0,1,0,1,0,0,0,1,0,1,0],
                          [1,0,0,1,0,0,1,0,1,0,0,1,0,0,1,0]],
        "instrumentos": ["ACID", "RESO", "SYNTHBASS", "METALLIC", "NOISE PITCH",
                         "PLUCK SOFT", "SUB PLUCK", "PLUCK", "SAW"],
        "tempo_mod": {"half": 0.10, "double": 0.10},
        "densidad": 1.0,
        "swing": 0.0,
        "registro": 0,
        # percusivo repetitivo: la melodia funciona como otro elemento del groove
        "pat_melodia": [
            [1,0,0,1,0,0,1,0,1,0,0,1,0,0,1,0],   # sincopa constante (rolling)
            [0,0,1,0,1,0,0,0,0,0,1,0,1,0,0,0],   # &1-2, &3-4
            [1,0,0,0,0,0,1,0,0,1,0,0,1,0,0,0],   # groove con 16avo
        ],
    },
    "JUNGLE": {
        "bpm": (155, 172),
        "escalas": ["menor", "arm_menor"],
        "drums": {
            # amen break picado: kick + variaciones, snare con ghost notes irregulares
            "kick":  [[1,0,0,0,0,0,1,0,0,1,0,0,1,0,0,0],
                      [1,0,0,1,0,0,0,0,1,0,0,0,0,1,0,0]],
            "snare": [[0,0,0,0,1,0,0,1,0,0,1,0,1,0,0,1],   # denso con ghosts
                      [0,0,1,0,1,0,0,0,0,1,0,1,1,0,1,0]],
            "hihat": [[1,1,0,1,1,0,1,1,1,0,1,1,1,1,0,1]],
            "hihat_o":[0,0,1,0,0,0,0,0,0,0,1,0,0,0,0,0],
            "clap":  [0,0,0,0,1,0,0,0,0,0,0,0,1,0,0,0],
        },
        "bajo_estilos": ["reese", "sub"],
        "bajo_patrones": [[1,0,0,0,0,0,0,0,1,0,0,0,1,0,0,0],
                          [1,0,0,0,1,0,0,0,0,0,0,0,1,0,0,1]],
        "instrumentos": ["HOOVER", "GROWL", "SUB PLUCK", "RESO", "ATMOS NOISE",
                         "FORMANT", "ACID", "SYNC LEAD"],
        "tempo_mod": {"half": 0.25, "double": 0.0},
        "densidad": 1.15,
        "swing": 0.08,
        "registro": -12,
        # fragmentado estilo ragga: rafagas irregulares con huecos
        "pat_melodia": [
            [1,0,1,0,0,0,0,0,0,1,0,1,0,0,0,0],   # doblete + doblete corrido
            [1,0,0,0,0,1,0,0,1,0,0,0,0,1,0,0],   # sincopa irregular
            [0,0,1,0,1,0,1,0,0,0,0,0,1,0,0,0],   # rafaga &1-2-&2, 4
        ],
    },
    "TRANCE": {
        "bpm": (132, 140),
        "escalas": ["menor", "arm_menor", "mayor"],
        "drums": {
            "kick":  [[1,0,0,0,1,0,0,0,1,0,0,0,1,0,0,0]],   # 4x4 limpio
            "snare": [[0,0,0,0,1,0,0,0,0,0,0,0,1,0,0,0]],
            "hihat": [[0,0,1,0,0,0,1,0,0,0,1,0,0,0,1,0],
                      [1,0,1,0,1,0,1,0,1,0,1,0,1,0,1,0]],
            "hihat_o":[0,0,1,0,0,0,1,0,0,0,1,0,0,0,1,0],   # abierto offbeats
            "clap":  [0,0,0,0,1,0,0,0,0,0,0,0,1,0,0,0],
        },
        "bajo_estilos": ["pluck", "sub", "round"],
        "bajo_patrones": [[0,0,1,0,0,0,1,0,0,0,1,0,0,0,1,0],   # offbeat entre kicks
                          [1,0,1,0,1,0,1,0,1,0,1,0,1,0,1,0]],
        "instrumentos": ["SUPERSAW", "DETUNE", "SAW STACK", "PWM LEAD",
                         "DREAM PAD", "BELLPAD", "VOX PAD", "SYNC LEAD", "PAD"],
        "tempo_mod": {"half": 0.15, "double": 0.10},
        "densidad": 1.0,
        "swing": 0.0,
        "arpegios": True,
        "registro": 12,
        # etereo sostenido: notas largas que flotan (el arpegio pone el movimiento)
        "pat_melodia": [
            [1,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0],   # 1, 3 (colchon)
            [1,0,0,0,0,0,0,0,0,0,0,0,1,0,0,0],   # 1, 4 (espacioso)
            [0,0,1,0,0,0,1,0,0,0,1,0,0,0,1,0],   # offbeat (rolling trance)
        ],
    },
    "UK GARAGE": {
        "bpm": (130, 138),
        "escalas": ["menor", "arm_menor", "pentatonica"],
        "drums": {
            # 2-step: kick sincopado (NO 4x4), snare/clap en 2 y 4
            "kick":  [[1,0,0,0,0,0,0,0,0,0,1,0,0,0,0,0],
                      [1,0,0,0,0,0,0,1,0,0,1,0,0,0,0,0]],
            "snare": [[0,0,0,0,1,0,0,0,0,0,0,0,1,0,0,0]],
            "hihat": [[1,0,1,1,1,0,1,0,1,1,1,0,1,0,1,1]],   # shuffleado
            "hihat_o":[0,0,0,1,0,0,0,0,0,0,0,1,0,0,0,0],
            "clap":  [0,0,0,0,1,0,0,0,0,0,0,0,1,0,0,0],
        },
        "bajo_estilos": ["sub", "pluck", "round"],
        "bajo_patrones": [[1,0,0,0,0,0,0,0,0,0,1,0,0,0,0,0],
                          [1,0,0,1,0,0,0,0,1,0,0,0,0,0,1,0]],
        "instrumentos": ["SUB PLUCK", "ORGAN", "FM EP", "PLUCK SOFT", "VOX PAD",
                         "FORMANT", "BELLPAD", "PLUCK"],
        "tempo_mod": {"half": 0.10, "double": 0.05},
        "densidad": 0.85,
        "swing": 0.15,
        "registro": 0,
        # 2-step melodico: sincopa shuffleada, huecos ritmicos marcados
        "pat_melodia": [
            [1,0,0,1,0,0,0,0,1,0,0,1,0,0,0,0],   # 2-step clasico
            [0,0,1,0,0,1,0,0,0,0,1,0,0,0,1,0],   # sincopa desplazada
            [1,0,0,0,0,1,0,0,0,0,1,0,0,1,0,0],   # skippy (saltarin)
        ],
    },
}

# paletas de color por genero (color de acento, se mezcla con blanco/gris)
COLOR_GENERO = {
    "TECHNO":     (0, 220, 255),    # cyan electrico
    "HOUSE":      (255, 200, 80),   # dorado calido
    "TECH HOUSE": (100, 220, 100),  # verde electrico
    "DNB":        (180, 60, 255),   # violeta neon
    "JUNGLE":     (140, 220, 80),   # verde selva/lima
    "SYNTHWAVE":  (255, 60, 180),   # rosa magenta retro
    "TRANCE":     (140, 220, 255),  # celeste luminoso
    "UK GARAGE":  (80, 220, 200),   # turquesa aqua
}
COLOR_DEFECTO = (255, 255, 255)

def color_genero(partida):
    g = partida["cancion"].get("genero", "")
    return COLOR_GENERO.get(g, COLOR_DEFECTO)

def elegir_genero(rng):
    # 8 generos de electronica, reparto uniforme (~12.5% cada uno)
    pesos = {
        "TECHNO": 10, "HOUSE": 10, "TECH HOUSE": 10,
        "DNB": 10, "JUNGLE": 10, "SYNTHWAVE": 10,
        "TRANCE": 10, "UK GARAGE": 10,
    }
    generos = list(pesos.keys())
    weights = [pesos[g] for g in generos]
    total = sum(weights)
    r = rng.uniform(0, total)
    acum = 0
    for g, w in zip(generos, weights):
        acum += w
        if r <= acum:
            return g
    return generos[-1]

def genero_de_seed(seed):
    """Calcula el genero que produciria una seed, sin generar la cancion completa."""
    return elegir_genero(random.Random(int(seed * 23819)))

def num_dificultad(seed):
    """Devuelve el numero de nivel (1-15) de una seed."""
    if seed <= 0:
        return 1
    tramos = [400, 900, 1500, 2200, 3000, 3900, 4900, 5700, 6400,
              7100, 7800, 8400, 9000, 9500, 9999]
    for i, tope in enumerate(tramos):
        if seed <= tope:
            return i + 1
    return 15

def rango_seeds_dificultad(nivel):
    """Devuelve (seed_min, seed_max) para un nivel de dificultad."""
    tramos = [400, 900, 1500, 2200, 3000, 3900, 4900, 5700, 6400,
              7100, 7800, 8400, 9000, 9500, 9999]
    lo = 1 if nivel == 1 else tramos[nivel - 2] + 1
    hi = tramos[nivel - 1]
    return lo, hi

def buscar_seed_genero(genero, nivel, rng, evitar=None):
    """Busca una seed que produzca el genero y nivel dados. Devuelve None si no encuentra."""
    lo, hi = rango_seeds_dificultad(nivel)
    evitar = evitar or set()
    for _ in range(400):
        s = rng.randint(lo, hi)
        if s in evitar:
            continue
        if genero_de_seed(s) == genero:
            return s
    # fallback: escaneo lineal
    for s in range(lo, hi + 1):
        if s not in evitar and genero_de_seed(s) == genero:
            return s
    return None

def generar_patrones_drums(rng, genero=None):
    if genero is not None and genero in GENEROS:
        g = GENEROS[genero]["drums"]
        pats = {}
        pats["kick"]    = list(rng.choice(g["kick"]))
        pats["snare"]   = list(rng.choice(g["snare"]))
        pats["hihat"]   = list(rng.choice(g["hihat"]))
        pats["hihat_o"] = list(g["hihat_o"])
        pats["clap"]    = list(g["clap"])
        pats["clave"]   = [0] * 16
        pats["agogo"]   = [0] * 16
        # (clave/agogo se dejan en 0: los 9 generos actuales son todos de
        # electronica y no usan percusion latina auxiliar)
        pats["fill"]    = [0,0,0,0,0,0,0,0,0,0,1,0,1,1,1,1]
        return pats
    return _generar_patrones_drums_legacy(rng)

def _generar_patrones_drums_legacy(rng):
    pat_kick_all = [
        [1,0,0,0,1,0,0,0,1,0,0,0,1,0,0,0],
        [1,0,0,0,1,0,0,0,1,0,0,1,1,0,0,0],
        [1,0,0,1,0,0,1,0,0,0,1,0,0,0,1,0],
        [1,0,0,0,1,0,1,0,1,0,0,0,1,0,0,0],
        [1,0,0,0,1,0,0,0,1,0,0,0,1,0,1,0],
        [1,0,1,0,0,0,1,0,1,0,0,0,1,0,0,0],
        [1,0,0,0,0,0,1,0,0,0,1,0,0,0,0,0],
        [1,0,0,0,1,0,0,1,0,0,1,0,0,0,1,0],
        [1,0,0,1,0,0,0,0,1,0,0,1,0,0,0,0],
        [1,0,0,0,0,0,0,0,1,0,0,0,0,0,1,0],
    ]
    pat_hh_all = [
        [1,0,1,0,1,0,1,0,1,0,1,0,1,0,1,0],
        [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],
        [1,0,1,1,1,0,1,1,1,0,1,1,1,0,1,1],
        [0,0,1,0,0,0,1,0,0,0,1,0,0,0,1,0],
        [1,0,1,0,1,0,1,1,1,0,1,0,1,0,1,1],
        [1,0,0,1,0,0,1,0,1,0,0,1,0,0,1,0],
        [0,1,0,1,0,1,0,1,0,1,0,1,0,1,0,1],
        [1,0,1,0,0,1,0,1,1,0,1,0,0,1,0,1],
    ]
    pat_snare_all = [
        [0,0,0,0,1,0,0,0,0,0,0,0,1,0,0,0],
        [0,0,0,0,1,0,0,0,0,0,0,0,1,0,0,1],
        [0,0,0,0,1,0,0,1,0,0,0,0,1,0,0,0],
        [0,0,0,0,1,0,0,0,0,0,1,0,1,0,0,0],
        [0,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0],
    ]
    pats = {}
    pats["kick"]    = rng.choice(pat_kick_all)
    pats["snare"]   = rng.choice(pat_snare_all)
    pats["hihat"]   = rng.choice(pat_hh_all)
    pats["hihat_o"] = [0,0,0,0,0,0,1,0,0,0,0,0,0,0,1,0]
    pats["clap"]    = [0,0,0,0,1,0,0,0,0,0,0,0,1,0,0,0]
    pats["clave"]   = [0] * 16
    for p in rng.sample(range(16), rng.randint(2, 4)):
        pats["clave"][p] = 1
    pats["agogo"]   = [0] * 16
    for p in rng.sample(range(16), rng.randint(1, 3)):
        pats["agogo"][p] = 1
    pats["fill"]    = [0,0,0,0,0,0,0,0,0,0,1,0,1,1,1,1]
    return pats

def generar_percusion(rng, beat, t_intro_fin, t_nudo_fin, t_desenlace_fin,
                      c_intro, c_nudo, c_desenlace, kit, genero=None, pats_pre=None):
    paso = beat // 4
    # pats_pre: patrones pre-generados (para anclar la melodia del jugador
    # al kick). Si vienen, son el set principal; los otros 2 varian.
    pats  = pats_pre if pats_pre is not None else generar_patrones_drums(rng, genero)
    pats2 = generar_patrones_drums(rng, genero)
    pats3 = generar_patrones_drums(rng, genero)
    tercio1 = t_intro_fin + 8 * 4 * beat
    tercio2 = t_intro_fin + 16 * 4 * beat

    # probabilidades de half/double-time segun el genero
    if genero is not None and genero in GENEROS:
        tm = GENEROS[genero].get("tempo_mod", {"half": 0.30, "double": 0.20})
        p_half = tm.get("half", 0.0)
        p_double = tm.get("double", 0.0)
        swing_amt = GENEROS[genero].get("swing", 0.0)
    else:
        p_half, p_double = 0.30, 0.20
        swing_amt = 0.0

    roll = rng.random()
    if roll < p_half:
        modo_tempo = "half"
        tempo_tercio = rng.choice([1, 2])   # half-time en un tercio posterior
    elif roll < p_half + p_double:
        modo_tempo = "double"
        tempo_tercio = 0                    # empieza lento, luego acelera
    else:
        modo_tempo = "normal"
        tempo_tercio = -1

    # patron half-time: kick en el 1, snare/clap en el 3 (medio compas)
    ht_kick  = [1,0,0,0, 0,0,0,0, 1,0,0,0, 0,0,0,0]
    ht_snare = [0,0,0,0, 0,0,0,0, 1,0,0,0, 0,0,0,0]
    ht_hihat = [1,0,0,0, 1,0,0,0, 1,0,0,0, 1,0,0,0]

    # patron double-time: todo al doble de densidad
    dt_kick  = [1,0,1,0, 1,0,1,0, 1,0,1,0, 1,0,1,0]
    dt_snare = [0,0,1,0, 0,0,1,0, 0,0,1,0, 0,0,1,0]
    dt_hihat = [1,1,1,1, 1,1,1,1, 1,1,1,1, 1,1,1,1]

    percusion = []
    total = c_intro + c_nudo + c_desenlace
    for c in range(total):
        tc = c * 4 * beat
        if tc >= t_desenlace_fin:
            break
        es_fill = (c > 0) and (c % 4 == 3)
        if tc < tercio1:
            p = pats
            tercio_actual = 0
        elif tc < tercio2:
            p = pats2
            tercio_actual = 1
        else:
            p = pats3
            tercio_actual = 2

        en_tempo_mod = (tercio_actual == tempo_tercio) and (t_intro_fin <= tc < t_nudo_fin)
        en_half_time = en_tempo_mod and modo_tempo == "half"
        en_double_time = en_tempo_mod and modo_tempo == "double"

        for i in range(16):
            t = tc + i * paso
            # swing: retrasa los 16avos impares para dar groove (hip hop, reggaeton)
            if swing_amt > 0 and (i % 2 == 1):
                t += int(paso * swing_amt)
            if t < t_intro_fin:
                if p["hihat"][i] and kit["hihat"]:
                    percusion.append({"tiempo": t, "sample": "hihat", "vol": 0.04})
                continue
            if t >= t_nudo_fin:
                if p["kick"][i] and kit["kick"]:
                    percusion.append({"tiempo": t, "sample": "kick", "vol": 0.15})
                if p["clap"][i] and kit["clap"]:
                    percusion.append({"tiempo": t, "sample": "clap", "vol": 0.09})
                continue

            if en_half_time:
                # bateria a mitad de tempo: patron fijo espaciado, mas peso
                if ht_kick[i] and kit["kick"]:
                    percusion.append({"tiempo": t, "sample": "kick", "vol": 0.22})
                if ht_snare[i] and kit["snare"]:
                    percusion.append({"tiempo": t, "sample": "snare", "vol": 0.14})
                if ht_snare[i] and kit["clap"]:
                    percusion.append({"tiempo": t, "sample": "clap", "vol": 0.11})
                if ht_hihat[i] and kit["hihat"]:
                    percusion.append({"tiempo": t, "sample": "hihat", "vol": 0.05})
                if i == 0 and kit["crash"]:
                    percusion.append({"tiempo": t, "sample": "crash", "vol": 0.05})
                continue
            if en_double_time:
                # bateria al doble de tempo: todo mas denso y rapido
                if dt_kick[i] and kit["kick"]:
                    percusion.append({"tiempo": t, "sample": "kick", "vol": 0.16})
                if dt_snare[i] and kit["snare"]:
                    percusion.append({"tiempo": t, "sample": "snare", "vol": 0.10})
                if dt_hihat[i] and kit["hihat"]:
                    percusion.append({"tiempo": t, "sample": "hihat", "vol": 0.04})
                if i == 0 and kit["crash"]:
                    percusion.append({"tiempo": t, "sample": "crash", "vol": 0.05})
                continue

            if p["kick"][i] and kit["kick"]:
                percusion.append({"tiempo": t, "sample": "kick", "vol": 0.18})
            if p["snare"][i] and kit["snare"]:
                percusion.append({"tiempo": t, "sample": "snare", "vol": 0.11})
            if p["hihat"][i] and kit["hihat"]:
                percusion.append({"tiempo": t, "sample": "hihat", "vol": 0.05})
            if p["hihat_o"][i] and kit["hihat_o"]:
                percusion.append({"tiempo": t, "sample": "hihat_o", "vol": 0.06})
            if p["clap"][i] and kit["clap"]:
                percusion.append({"tiempo": t, "sample": "clap", "vol": 0.10})
            if p["clave"][i] and kit["clave"]:
                percusion.append({"tiempo": t, "sample": "clave", "vol": 0.03})
            if p["agogo"][i] and kit["agogo"]:
                percusion.append({"tiempo": t, "sample": "agogo", "vol": 0.03})
            if es_fill and p["fill"][i]:
                tk = rng.choice(["tom1", "tom2"])
                if kit[tk]:
                    percusion.append({"tiempo": t, "sample": tk, "vol": 0.07})
            if i == 0 and c % 8 == 0 and kit["crash"]:
                percusion.append({"tiempo": t, "sample": "crash", "vol": 0.06})
    return sorted(percusion, key=lambda n: n["tiempo"])

# ═══════════════════════════════════════════════════════ >>MUSIC_GEN<< ═══

# --- FORMA MUSICAL: vocabulario de secciones tipo cancion popular ---
# Cada seccion tiene una FUNCION y un PERFIL propio (energia, densidad, registro,
# que material melodico usa). El estribillo repite un motivo memorable; el verso
# desarrolla; el puente contrasta. Esto reemplaza el viejo INTRO->NUDO->DESENLACE
# plano por una estructura con arco de tension real.
#
# perfil de cada seccion:
#   energia:   0..1  -> afecta densidad de notas y probabilidad de adornos
#   registro:  offset de octava tipico (-12, 0, +12)
#   material:  que banco de motivos usa ("A"=verso, "B"=estribillo, "C"=puente)
#   densidad_mult: multiplicador extra de densidad sobre la del genero
PERFILES_SECCION = {
    "intro":      {"energia": 0.25, "registro":  0,  "material": "A", "densidad_mult": 0.5},
    "verso":      {"energia": 0.55, "registro":  0,  "material": "A", "densidad_mult": 0.85},
    "preestribillo":{"energia":0.7, "registro":  0,  "material": "A", "densidad_mult": 1.0},
    "estribillo": {"energia": 1.0,  "registro": 12,  "material": "B", "densidad_mult": 1.15},
    "puente":     {"energia": 0.6,  "registro":  0,  "material": "C", "densidad_mult": 0.9},
    "outro":      {"energia": 0.3,  "registro":  0,  "material": "B", "densidad_mult": 0.55},
}

# arquetipos de forma: listas de secciones. Se elige uno por seed (o se arma uno
# dinamico). Van de simples (pocas secciones) a complejos (con puente y pre).
# Cada arquetipo es una lista de (nombre_seccion, num_compases).
FORMAS_CANCION = {
    "simple":     ["intro", "verso", "estribillo", "verso", "estribillo", "outro"],
    "pop":        ["intro", "verso", "estribillo", "verso", "estribillo", "puente", "estribillo", "outro"],
    "con_pre":    ["intro", "verso", "preestribillo", "estribillo", "verso", "preestribillo", "estribillo", "outro"],
    "corta":      ["intro", "verso", "estribillo", "outro"],
    "minima":     ["verso", "estribillo", "verso", "estribillo"],
    "epica":      ["intro", "verso", "estribillo", "verso", "estribillo", "puente", "estribillo", "estribillo", "outro"],
    "maraton":    ["intro", "verso", "estribillo", "verso", "estribillo", "puente",
                   "verso", "estribillo", "estribillo", "outro"],
}

def elegir_forma(rng, nivel_dif):
    """Elige un arquetipo de forma segun la seed y el nivel de dificultad.
    Niveles bajos -> formas mas simples y cortas; altos -> mas elaboradas.
    A partir de NORMAL (nivel 3) las formas crecen progresivamente: como los
    niveles ahora duran mas (metas mas altas), la cancion base mas larga hace
    que el loop se repita menos veces y la repeticion se note menos."""
    if nivel_dif <= 2:
        pool = ["corta", "minima", "simple", "simple"]
    elif nivel_dif <= 5:
        pool = ["simple", "simple", "pop", "con_pre"]
    elif nivel_dif <= 9:
        pool = ["pop", "pop", "con_pre", "epica", "epica"]
    else:
        pool = ["epica", "epica", "maraton", "maraton", "pop"]
    return FORMAS_CANCION[rng.choice(pool)]

def compases_por_seccion(nombre, rng, nivel_dif):
    """Cuantos compases dura cada tipo de seccion (variable por seed).
    Escala progresivamente con el nivel desde NORMAL."""
    if nombre in ("intro", "outro"):
        return rng.choice([2, 2, 4]) if nivel_dif <= 6 else rng.choice([2, 4, 4])
    if nombre == "preestribillo":
        return rng.choice([2, 2, 4])
    if nombre == "puente":
        return rng.choice([4, 4, 8]) if nivel_dif <= 9 else rng.choice([4, 8, 8])
    # verso y estribillo: bloques que crecen con el nivel
    if nivel_dif <= 2:
        return rng.choice([4, 4])
    elif nivel_dif <= 5:
        return rng.choice([4, 4, 8])
    elif nivel_dif <= 9:
        return rng.choice([4, 8, 8])
    return rng.choice([8, 8])


def generar_cancion(seed, dif, instrumento_forzado=None):
    num_columnas = dif["columnas"]
    usar_acordes = dif["acordes"]
    rng          = random.Random(seed)

    # --- elegir GENERO musical por seed ---
    genero       = elegir_genero(rng)
    gdef         = GENEROS[genero]

    bpm_min, bpm_max = gdef["bpm"]
    bpm_mult = dif.get("bpm_mult", 1.0)
    BPM          = int(rng.randint(bpm_min, bpm_max) * bpm_mult)
    BPM          = max(50, BPM)   # piso minimo
    beat         = 60000 // BPM
    paso16       = beat // 4
    tonica       = rng.choice([36, 38, 40, 41, 43, 45, 47, 48, 50, 52, 53, 55])
    # escala restringida al pool del genero (cae en cualquiera valida si falta)
    escalas_genero = [e for e in gdef["escalas"] if e in ESCALAS] or list(ESCALAS.keys())
    nombre_escala= rng.choice(escalas_genero)
    escala       = ESCALAS[nombre_escala]
    patron_acordes = ACORDES_PATRON.get(nombre_escala, ACORDES_PATRON["mayor"])
    base_prog = rng.choice(PROGRESIONES)
    # repetir la progresion de 4 acordes para cubrir 8 compases
    progresion = base_prog * 2

    densidad = gdef.get("densidad", 1.0) * dif.get("dens", 1.0)
    swing    = gdef.get("swing", 0.0)

    # notas por columna: grados PENTATONICOS de la escala en vez de grados
    # consecutivos. Esto garantiza que cualquier combinacion de columnas que
    # apreta el jugador suene consonante (no hay intervalos de segunda menor
    # entre columnas adyacentes). El bajo y los acordes siguen usando la
    # escala completa (menor/mayor/blues/etc), asi la estructura armonica de
    # la cancion se mantiene, pero el jugador siempre toca "notas seguras".
    penta = PENTA_GRADOS.get(nombre_escala, [0, 1, 2, 4, 5])
    def _grado_pent(i):
        # extender la penta a mas de 5 columnas subiendo por octavas
        octava_dg = 7  # 7 grados diatonicos por octava en la escala completa
        return penta[i % 5] + (i // 5) * octava_dg
    notas_columnas = [nota_midi(tonica + 12, escala, _grado_pent(i)) for i in range(num_columnas)]
    kit = elegir_kit(rng)
    # instrumento: si viene forzado (runs, para garantizar variedad) se respeta.
    # si no: 2% raro (si hay raros), si no del pool del genero
    if instrumento_forzado and (instrumento_forzado in INSTRUMENTOS_JUGADOR
                                or instrumento_forzado in INSTRUMENTOS_RAROS):
        instrumento = instrumento_forzado
    elif INSTRUMENTOS_RAROS and rng.random() < 0.02:
        instrumento = rng.choice(list(INSTRUMENTOS_RAROS.keys()))
    else:
        pool = [i for i in gdef.get("instrumentos", []) if i in INSTRUMENTOS_JUGADOR]
        if not pool:
            pool = list(INSTRUMENTOS_JUGADOR.keys())
        instrumento = rng.choice(pool)
        # RESO suena agresivo, re-roll 75% de las veces
        if instrumento == "RESO" and len(pool) > 1 and rng.random() < 0.75:
            instrumento = rng.choice([p for p in pool if p != "RESO"])

    # --- ESTRUCTURA: forma musical con secciones (verso/estribillo/puente) ---
    # Se elige un arquetipo de forma por seed (variable: simple o complejo) y se
    # asigna una duracion a cada seccion. La duracion total sigue escalando con
    # la dificultad ajustando cuantos compases dura cada seccion.
    nivel_dif = dif.get("nivel", 5)
    dur_total_min, dur_total_max = 26.0, 115.0
    dur_total_obj = dur_total_min + (nivel_dif - 1) / 14 * (dur_total_max - dur_total_min)
    dur_total_obj *= rng.uniform(0.9, 1.1)
    seg_por_compas = (4 * beat) / 1000.0

    forma = elegir_forma(rng, nivel_dif)
    # asignar compases a cada seccion de la forma
    plan_secciones = []   # lista de dicts: {nombre, compases, inicio_compas, perfil}
    compas_cursor = 0
    for nombre in forma:
        nc = compases_por_seccion(nombre, rng, nivel_dif)
        plan_secciones.append({
            "nombre": nombre,
            "compases": nc,
            "inicio_compas": compas_cursor,
            "perfil": PERFILES_SECCION[nombre],
        })
        compas_cursor += nc
    compases_forma = compas_cursor

    # ajustar la duracion: si la forma base es mas corta que el objetivo, se
    # repite el nucleo (verso+estribillo) hasta acercarse; si es mas larga en
    # niveles bajos, se recorta. Esto mantiene el escalado por dificultad.
    compases_obj = max(4, round(dur_total_obj / seg_por_compas))
    # repetir el ciclo verso->estribillo si falta duracion (solo formas con nucleo)
    idx_nucleo = [i for i, s in enumerate(plan_secciones)
                  if s["nombre"] in ("verso", "estribillo")]
    guard = 0
    while compases_forma < compases_obj * 0.85 and idx_nucleo and guard < 8:
        # insertar una repeticion de verso+estribillo antes del outro
        pos_outro = next((i for i, s in enumerate(plan_secciones)
                          if s["nombre"] == "outro"), len(plan_secciones))
        nuevas = []
        for nombre in ("verso", "estribillo"):
            nc = compases_por_seccion(nombre, rng, nivel_dif)
            nuevas.append({"nombre": nombre, "compases": nc, "inicio_compas": 0,
                           "perfil": PERFILES_SECCION[nombre]})
        plan_secciones[pos_outro:pos_outro] = nuevas
        # recomputar inicios y total
        compas_cursor = 0
        for s in plan_secciones:
            s["inicio_compas"] = compas_cursor
            compas_cursor += s["compases"]
        compases_forma = compas_cursor
        guard += 1

    # tiempos clave (en ms). La "intro" es la primera seccion; el "desenlace" es
    # la ultima (outro). Se conservan estos nombres por compatibilidad con el
    # resto del juego (percusion, estructura de retorno).
    C_INTRO = plan_secciones[0]["compases"] if plan_secciones[0]["nombre"] == "intro" else 0
    C_DESENLACE = plan_secciones[-1]["compases"] if plan_secciones[-1]["nombre"] == "outro" else 0
    C_NUDO = compases_forma - C_INTRO - C_DESENLACE
    C_NUDO = max(4, C_NUDO)
    num_reps = max(1, C_NUDO // 4)   # compat: el resto del codigo usa num_reps
    t_intro_fin     = C_INTRO * 4 * beat
    t_nudo_fin      = t_intro_fin + C_NUDO * 4 * beat
    t_desenlace_fin = t_nudo_fin + C_DESENLACE * 4 * beat

    prob_acorde = {3: 0.2, 4: 0.3, 5: 0.4, 6: 0.5, 7: 0.6, 8: 0.65}.get(num_columnas, 0.4)

    # frases melodicas: contornos que se mueven mayormente por GRADO CONJUNTO
    # (pasos de a 1), con algun salto ocasional. Los valores son grados de la
    # escala relativos (0=tonica). El movimiento paso a paso es lo que hace que
    # una melodia suene cantable y no como un arpegio.
    frases_subir = [
        [0, 1, 2, 3],    # escala ascendente
        [0, 1, 2, 1],    # sube y vuelve (bordadura superior)
        [0, 2, 1, 3],    # onda ascendente
        [0, 1, 3, 2],    # paso, salto, resolucion descendente
        [2, 1, 2, 4],    # bordadura + impulso
        [0, 2, 3, 4],    # ascenso con un salto inicial
        [1, 2, 3, 2],    # tramo medio ascendente
    ]
    frases_bajar = [
        [4, 3, 2, 1],    # escala descendente
        [4, 3, 4, 2],    # baja con bordadura
        [3, 4, 2, 0],    # onda descendente
        [4, 2, 3, 1],    # salto y resolucion
        [3, 2, 1, 2],    # descenso con reposo
        [4, 3, 1, 0],    # descenso hacia tonica
        [2, 3, 1, 0],    # cierra en tonica
    ]
    frases_medio = [
        [2, 3, 2, 1],    # ondulacion media
        [1, 2, 1, 0],    # paso a paso hacia tonica
        [2, 1, 2, 3],    # vaiven ascendente
        [3, 2, 1, 2],    # vaiven descendente
        [1, 3, 2, 1],    # arco con salto
        [2, 1, 0, 1],    # bordadura inferior
        [0, 1, 2, 1],    # arco simple
    ]

    def escalar_frase(frase):
        """Mapea grados de escala (0..4) a columnas. Con columnas consecutivas,
        cada grado es una columna, preservando el movimiento por grado conjunto.
        Con pocas columnas, comprime el rango sin romper el contorno."""
        maxg = max(frase)
        if maxg < num_columnas:
            # entra directo: cada grado -> su columna (movimiento conjunto real)
            base = rng.randint(0, max(0, num_columnas - 1 - maxg))
            return [min(num_columnas - 1, g + base) for g in frase]
        # el contorno excede las columnas: comprimir proporcionalmente
        return [min(num_columnas - 1, int(round(g * (num_columnas - 1) / max(1, maxg))))
                for g in frase]

    # --- DESARROLLO DEL MOTIVO: transformaciones clasicas de composicion ---
    # En vez de repetir el motivo identico (aburrido) o sortear otro random
    # (incoherente), las repeticiones usan variaciones que el oido reconoce
    # como "parientes" del original: misma identidad, nuevo interes.
    def _clamp_cols(m):
        return [max(0, min(num_columnas - 1, c)) for c in m]

    def transponer_motivo(m, delta):
        """El mismo contorno, movido delta columnas arriba/abajo."""
        return _clamp_cols([c + delta for c in m])

    def invertir_motivo(m):
        """Espejo del contorno: donde subia, baja (inversion clasica)."""
        pivote = m[0]
        return _clamp_cols([pivote - (c - pivote) for c in m])

    # --- MOTIVOS MEMORABLES por material ---
    # Cada "material" (A=verso, B=estribillo, C=puente) tiene su propio motivo
    # generado UNA vez. El del estribillo (B) es el "gancho": se reutiliza
    # identico cada vez que vuelve el estribillo, por eso suena reconocible.
    motivos_a = [escalar_frase(rng.choice(frases_subir)) for _ in range(2)]
    motivos_b = [escalar_frase(rng.choice(frases_bajar))]     # gancho del estribillo
    motivos_c = [escalar_frase(rng.choice(frases_medio))]

    # --- pools de patrones ritmicos escalados por dificultad ---
    # posiciones: 0=1er negra, 2=octavo, 4=2da negra, 6=octavo, etc.
    # los octavos (pos 2,6,10,14) dan groove y sincopa.
    # PRINCIPIO: groove = DONDE caen las notas, no CUANTAS hay.
    pat_basicos = [
        # 2-3 notas, algun octavo para que no sea solo negras
        [1,0,0,0,0,0,1,0,0,0,0,0,0,0,0,0],  # 1, &2
        [1,0,0,0,0,0,0,0,0,0,1,0,0,0,0,0],  # 1, &3
        [0,0,1,0,0,0,0,0,1,0,0,0,0,0,0,0],  # &1, 3
        [1,0,0,0,0,0,0,0,1,0,0,0,1,0,0,0],  # 1, 3, 4
        [1,0,0,0,1,0,0,0,0,0,1,0,0,0,0,0],  # 1, 2, &3
        [0,0,0,0,1,0,0,0,0,0,0,0,0,0,1,0],  # 2, &4
        [1,0,0,0,0,0,0,0,0,0,0,0,1,0,0,0],  # 1, 4
        [0,0,1,0,0,0,0,0,0,0,0,0,1,0,0,0],  # &1, 4
    ]
    pat_intermedios = [
        # 2-3 notas, sincopas y anticipaciones (groove sin densidad)
        [1,0,0,0,0,0,1,0,0,0,0,0,1,0,0,0],  # 1, &2, 4
        [0,0,1,0,0,0,0,0,1,0,0,0,0,0,0,0],  # &1, 3
        [1,0,0,0,0,0,0,0,0,0,1,0,0,0,1,0],  # 1, &3, &4
        [0,0,0,0,1,0,1,0,0,0,0,0,0,0,0,0],  # 2, &2
        [1,0,0,0,0,0,1,0,0,0,0,0,0,0,0,0],  # 1, &2
        [0,0,1,0,0,0,0,0,0,0,1,0,0,0,0,0],  # &1, &3
        [1,0,0,0,1,0,0,0,0,0,0,0,0,0,1,0],  # 1, 2, &4
        [0,0,0,0,0,0,1,0,1,0,0,0,0,0,0,0],  # &2, 3
    ]
    pat_avanzados = [
        # 3-4 notas, mas sincopas, algun dieciseisavo
        [1,0,0,0,0,0,1,0,1,0,0,0,0,0,0,0],  # 1, &2, 3
        [0,0,1,0,1,0,0,0,0,0,0,0,1,0,0,0],  # &1, 2, 4
        [1,0,0,0,0,0,1,0,0,0,0,0,0,0,1,0],  # 1, &2, &4
        [1,0,0,0,1,0,0,0,0,0,1,0,0,0,0,0],  # 1, 2, &3
        [0,0,1,0,0,0,0,0,1,0,0,0,0,0,1,0],  # &1, 3, &4
        [1,0,0,0,0,0,1,0,0,0,1,0,0,0,0,0],  # 1, &2, &3
        [0,0,0,0,1,0,0,0,0,0,1,0,1,0,0,0],  # 2, &3, 4
        [1,0,0,1,0,0,0,0,1,0,0,0,0,0,1,0],  # 1, 16avo, 3, &4
    ]
    # elegir pool segun NIVEL (progresion fina en 5 tramos)
    _niv_pat = dif.get("nivel", 1)
    if _niv_pat <= 3:
        pat_jugador_simples = pat_basicos
        pat_jugador_complejos = pat_basicos + pat_intermedios
    elif _niv_pat <= 6:
        pat_jugador_simples = pat_basicos + pat_intermedios
        pat_jugador_complejos = pat_intermedios
    elif _niv_pat <= 9:
        pat_jugador_simples = pat_intermedios
        pat_jugador_complejos = pat_intermedios + pat_avanzados
    elif _niv_pat <= 12:
        pat_jugador_simples = pat_intermedios + pat_avanzados
        pat_jugador_complejos = pat_avanzados
    else:
        pat_jugador_simples = pat_avanzados
        pat_jugador_complejos = pat_avanzados

    # PERFILES RITMICOS POR GENERO: cada genero define patrones melodicos
    # caracteristicos (offbeat de house, rolling de tech house, 2-step de
    # garage, etc). Se DUPLICAN dentro del pool para que salgan con mucha
    # frecuencia (~50-60% de las veces) sin eliminar la variedad del pool
    # base por dificultad. Asi la melodia "suena al genero" ademas de la
    # bateria y el bajo.
    pat_genero = gdef.get("pat_melodia", [])
    if pat_genero:
        pat_jugador_simples = pat_jugador_simples + pat_genero * 2
        pat_jugador_complejos = pat_jugador_complejos + pat_genero * 2

    # REGISTRO POR GENERO: dnb/jungle tocan una octava abajo (agresivo,
    # cerca del bajo), trance una octava arriba (etereo), el resto al medio.
    registro_genero = gdef.get("registro", 0)

    notas_jugador = []

    # --- D: ANCLA CON EL KICK ---
    # los patrones de drums se generan ANTES de la melodia (con rng propio,
    # determinista por seed) para que el patron ritmico del jugador pueda
    # elegirse maximizando coincidencias con el kick -> tocas "con la banda".
    _rng_drums = random.Random(int(seed * 13) + 7)
    pats_drums_ancla = generar_patrones_drums(_rng_drums, genero)
    _kick_ancla = pats_drums_ancla["kick"]

    def _score_kick(pat):
        """Fraccion de notas del patron que coinciden con el kick (downbeat x2).
        Normalizado por cantidad de notas: alinea con el kick SIN sesgar la
        seleccion hacia patrones mas densos."""
        sc = 0
        notas = 0
        for s in range(16):
            if pat[s]:
                notas += 1
                if _kick_ancla[s]:
                    sc += 2 if s == 0 else 1
        return sc / max(1, notas)

    def _elegir_pat(pool):
        """Muestrea 3 candidatos y devuelve el de mayor overlap con el kick."""
        candidatos = [pool[rng.randint(0, len(pool) - 1)] for _ in range(3)]
        return max(candidatos, key=_score_kick)

    def crear_compas(motivo, pat, permitir_hold=True, cierre=None):
        """Genera un compas (16 pasos) colocando las notas del motivo en las
        posiciones activas del patron ritmico. Devuelve lista de 16 (None o dict).

        cierre: ajusta la ULTIMA nota real del compas (importante: el motivo
        cicla, asi que la ultima nota del compas no es la ultima del motivo):
          'pregunta'      -> termina en columna inestable (>=2), frase abierta
          'semicadencia'  -> termina en la 5ta (columna 3): pausa SIN cerrar,
                             como una coma. Para respuestas intermedias.
          'respuesta'     -> termina en columna 0 (tonica): cierre real, como
                             un punto final. SOLO la ultima frase de la seccion."""
        nota_idx = 0
        compas = []
        for s in range(16):
            if pat[s] == 0:
                compas.append(None)
                continue
            col = motivo[nota_idx % len(motivo)]
            nota_idx += 1
            compas.append({"col": col, "hold": 0})
        # pregunta/semicadencia/respuesta: ajustar la ultima nota activa
        activas_pr = [i for i, n in enumerate(compas) if n is not None]
        if cierre and activas_pr:
            ult = activas_pr[-1]
            if cierre == "respuesta":
                compas[ult]["col"] = 0
                # la anteultima se acerca (aproximacion por grado conjunto)
                if len(activas_pr) >= 2:
                    ant = activas_pr[-2]
                    if compas[ant]["col"] > 1:
                        compas[ant]["col"] = 1
                # ECO de cierre: si el final del compas quedo vacio, un eco
                # suave de la ultima nota una octava arriba contesta la frase
                # (call-and-response entre registros, clasico de electronica
                # melodica). Solo si hay hueco real: no ensucia compases densos.
                if ult <= 11 and all(compas[s] is None for s in range(ult + 1, 16)):
                    s_eco = ult + 4 if ult + 4 <= 14 else 14
                    compas[s_eco] = {"col": 0, "hold": 0, "eco": True}
            elif cierre == "semicadencia":
                # 5ta pentatonica (columna 3 si existe): reposo sin cierre
                compas[ult]["col"] = min(num_columnas - 1, 3)
            elif cierre == "pregunta" and compas[ult]["col"] <= 1:
                compas[ult]["col"] = min(num_columnas - 1, 2)
        if permitir_hold:
            # prob de hold escala con el nivel: 0.32 (facil) -> 0.55 (chaos)
            # holds escalados por nivel: en fácil casi no hay (el principiante
            # aprende primero a tapear). nivel 1: 5% | nivel 15: 55%
            _niv_h = dif.get("nivel", 1)
            if _niv_h <= 2:
                prob_hold = 0.05 + (_niv_h - 1) * 0.05    # 0.05 (n1) -> 0.10 (n2)
            else:
                prob_hold = 0.3 + min(0.25, _niv_h * 0.017)
            activas = [i for i, n in enumerate(compas) if n is not None]
            for idx, pos in enumerate(activas):
                if rng.random() < prob_hold:
                    if idx + 1 < len(activas):
                        dur = ((activas[idx + 1] - pos) // 4) * beat
                    else:
                        dur = ((16 - pos) // 4) * beat
                    if dur >= beat:
                        compas[pos]["hold"] = dur
        return compas

    def crear_bloque_seccion(material, num_compases, complejo):
        """Crea el contenido melodico (lista de compases) de una seccion.

        ESTRUCTURA DE FRASE (pregunta/respuesta): los compases se organizan
        en pares antecedente/consecuente. El compas impar plantea el motivo
        terminando en nota inestable (pregunta, queda 'abierta'); el par lo
        repite variado terminando en la tonica (respuesta, 'cierra'). Es la
        estructura de frase mas universal de la musica tonal.

        DESARROLLO DEL MOTIVO: en frases sucesivas el motivo no se repite
        literal: se transforma (transposicion / inversion / retrogradacion).
        El oido reconoce el parentesco -> cohesion; no es identico -> interes.

        El estribillo (B) usa SIEMPRE la misma pregunta/respuesta y el mismo
        patron ritmico, para que el gancho sea reconocible cada vez."""
        if material == "B":
            motivo = motivos_b[0]
        elif material == "C":
            motivo = motivos_c[0]
        else:
            motivo = motivos_a[rng.randint(0, len(motivos_a) - 1)]
        pats = pat_jugador_complejos if complejo else pat_jugador_simples
        # el estribillo fija sus patrones (memorable); verso/puente varian mas
        # ambos se eligen maximizando el overlap con el kick (D: anclas)
        if material == "B":
            pat1 = _elegir_pat(pats)
            pat2 = pat1   # mismo patron los 2 compases -> mas pegadizo
        else:
            pat1 = _elegir_pat(pats)
            pat2 = _elegir_pat(pats)
        bloque = []
        # PLAN DIRECCIONAL de desarrollo: en vez del ciclo mecanico
        # literal/transposicion-aleatoria/inversion/retrogradacion, cada
        # seccion sortea UN plan con direccion narrativa. La SECUENCIA
        # (repetir el motivo un grado mas arriba) es el recurso clasico
        # para construir tension; el descenso o el literal la sueltan.
        #   ascenso: sube por secuencia hasta el climax y vuelve (trance!)
        #   arco:    sube, invierte en el pico (sorpresa), baja
        #   vaiven:  balancea abajo/arriba (hipnotico, para techno/house)
        planes = [
            ["lit", "sec+1", "sec+2", "lit"],     # ascenso y retorno
            ["lit", "sec+1", "inv",   "sec-1"],   # arco con inversion
            ["lit", "sec-1", "sec+1", "lit"],     # vaiven
        ]
        plan = rng.choice(planes)

        def _aplicar(m, paso):
            if paso == "sec+1":
                return transponer_motivo(m, 1)
            if paso == "sec+2":
                return transponer_motivo(m, 2)
            if paso == "sec-1":
                return transponer_motivo(m, -1)
            if paso == "inv":
                return invertir_motivo(m)
            return list(m)   # "lit"

        num_frases = max(1, num_compases // 2)
        for c in range(num_compases):
            frase_idx = c // 2          # que frase (par de compases) es
            es_respuesta = (c % 2 == 1)  # impar del par = consecuente
            es_ultima_frase = (frase_idx == num_frases - 1)
            if material == "B":
                m_base = motivo          # gancho: sin desarrollo
            else:
                m_base = _aplicar(motivo, plan[frase_idx % len(plan)])
            pat = pat1 if c % 2 == 0 else pat2
            # JERARQUIA DE CADENCIAS: las respuestas intermedias hacen
            # SEMICADENCIA (reposo en la 5ta, la frase respira pero sigue);
            # solo la ULTIMA respuesta de la seccion cierra en tonica.
            # Asi la seccion tiene direccion de largo plazo en vez de
            # "terminar" cada 2 compases.
            if not es_respuesta:
                cierre = "pregunta"
            elif es_ultima_frase:
                cierre = "respuesta"
            else:
                cierre = "semicadencia"
            bloque.append(crear_compas(m_base, pat, cierre=cierre))
        return bloque

    # pre-generar el bloque del estribillo UNA vez (gancho memorable reutilizable)
    estribillo_compases = None

    # helper: procesa un compas de contenido melodico y agrega las notas.
    # 'perfil' trae energia/registro de la seccion; 'es_cierre_seccion' fuerza
    # resolucion a tonica en el ultimo compas de la seccion.
    def emitir_compas(contenido, compas_global, perfil, parte, es_cierre_seccion,
                      prob_adorno_local, compas_armonico=None, det=False):
        # compas_armonico: si se pasa, fija el grado de la progresion (para que el
        #   estribillo suene armonicamente identico en cada retorno = gancho memorable)
        # det: modo determinista (sin rng), refuerza que el gancho sea reconocible
        oct_off = perfil["registro"] + registro_genero
        # clamp real: el cache renderiza midi 36-97. En el peor caso (trance
        # +12, estribillo +12, 8 columnas con tonica alta) la nota mas aguda
        # llega a ~105 y no estaria renderizada -> silencio. Si el offset
        # empuja la columna mas aguda fuera del cache, bajar una octava.
        _midi_max_col = max(notas_columnas) + oct_off
        while _midi_max_col > 97 and oct_off >= -12:
            oct_off -= 12
            _midi_max_col -= 12
        _midi_min_col = min(notas_columnas) + oct_off
        while _midi_min_col < 36:
            oct_off += 12
            _midi_min_col += 12
        energia = perfil["energia"]
        dens_local = densidad * perfil["densidad_mult"]
        # compensacion por columnas: al sumar una columna, la densidad efectiva
        # se reparte en mas teclas y el jugador percibe menos notas por tecla.
        # cada columna extra sube dens 25% (compensa el reparto proporcional).
        num_cols_e = num_columnas - 3
        if num_cols_e > 0:
            dens_local *= (1 + 0.25 * num_cols_e)
        dens_local = min(dens_local, 1.0)  # techo: nunca subir mas que "todas las notas"
        # piso minimo por nivel
        _niv_d = dif.get("nivel", 1)
        dens_local = max(dens_local, 0.15 + _niv_d * 0.055)
        # cap absoluto en niveles faciles: elimina el peor caso de canciones
        # densas por genero (antes maximo 1.39 notas/s en nivel 1, muy alto).
        # nivel 1: cap 0.32   nivel 2: cap 0.38
        if _niv_d == 1:
            dens_local = min(dens_local, 0.32)
        elif _niv_d == 2:
            dens_local = min(dens_local, 0.38)
        ca = compas_armonico if compas_armonico is not None else compas_global
        grado_actual = progresion[ca % len(progresion)]
        tonos_ac = tonos_acorde(tonica + 12, escala, grado_actual)
        clases_ac = {ta % 12 for ta in tonos_ac}
        _nivel_gc = dif.get("nivel", 1)
        # STREAM de 16avos (nivel 11+): el compas de cierre de seccion termina
        # con una rafaga de 4 notas consecutivas en columnas adyacentes (el
        # "fill" clasico de dificultad alta).
        es_stream = es_cierre_seccion and _nivel_gc >= 11 and not det
        stream_len = 6 if _nivel_gc >= 14 else 4
        stream_ini = 16 - stream_len

        # ARPEGIO (trance/synthwave): en el estribillo, un compas entero se
        # reemplaza por una corrida de corcheas subiendo y bajando por las
        # columnas (el sello sonoro del genero). Como las columnas ya son
        # pentatonicas, cualquier corrida suena musical. Solo en energia alta
        # (estribillo), nunca en el compas determinista del gancho (det), y
        # con densidad jugable: corcheas (8 notas/compas), no 16avos.
        if (gdef.get("arpegios") and energia >= 0.9 and not det
                and not es_cierre_seccion and rng.random() < 0.45):
            n_pasos = 8   # corcheas
            col_a = rng.randint(0, max(0, num_columnas - 1))
            dir_a = 1 if col_a < num_columnas // 2 else -1
            for k in range(n_pasos):
                s_a = k * 2
                t_a = t_intro_fin + compas_global * 4 * beat + s_a * paso16
                # (sin swing: el arpegio de trance/synthwave es recto por definicion)
                # rebotar en los bordes (sube hasta el tope, baja, vuelve)
                col_k = col_a + k * dir_a
                ciclo = max(1, 2 * (num_columnas - 1))
                col_k = col_k % ciclo
                if col_k >= num_columnas:
                    col_k = ciclo - col_k
                midi_a = notas_columnas[col_k] + oct_off
                notas_jugador.append({
                    "cols": [col_k], "midis": [midi_a],
                    "tiempo": t_a, "es_acorde": False, "parte": parte, "hold": 0,
                })
            return  # el compas ya esta lleno con el arpegio
        # B: estado del salto expresivo (si la nota anterior salto, esta resuelve)
        _salto = {"resolver": 0, "desde": None}
        for s in range(16):
            if contenido[s] is None:
                continue
            if es_stream and s >= stream_ini:
                continue  # los ultimos pasos los cubre el stream
            t   = t_intro_fin + compas_global * 4 * beat + s * paso16
            # swing: retrasa octavos (posiciones impares) para groove
            if swing > 0 and (s % 2 == 1):
                t += int(paso16 * swing)
            col = contenido[s]["col"]
            hd  = contenido[s]["hold"]
            # acordes: mas probables en estribillo (energia alta) y con dif acordes
            prob_ac_local = prob_acorde * (0.6 + 0.6 * energia)
            # en modo determinista (estribillo) la decision no depende del rng, asi
            # el gancho pone acorde SIEMPRE en el mismo lugar en cada retorno
            pone_acorde = (compas_global % 2 == 0) if det else (rng.random() < prob_ac_local)
            # en niveles altos los acordes tambien pueden caer en el beat 3
            s_acorde_ok = (s == 0) or (_nivel_gc >= 9 and s == 8)
            # en niveles faciles (1-2) NUNCA hay acordes, ni siquiera en el
            # estribillo (energia alta). Si la tabla dice "acordes: False",
            # se respeta estrictamente para no sobrecargar al principiante.
            energia_permite = energia >= 0.9 and _nivel_gc >= 3
            if (usar_acordes or energia_permite) and s_acorde_ok and pone_acorde:
                cols_ac = []
                for g in patron_acordes[grado_actual % len(patron_acordes)][:3]:
                    col_ac = g % num_columnas
                    if col_ac not in cols_ac:
                        cols_ac.append(col_ac)
                if len(cols_ac) >= 2:
                    midis_ac = []
                    for cx in cols_ac:
                        m = notas_columnas[cx] + oct_off
                        m = ajustar_a_acorde(m, tonos_ac, escala, tonica + 12)
                        midis_ac.append(m)
                    notas_jugador.append({
                        "cols": cols_ac, "midis": midis_ac,
                        "tiempo": t, "es_acorde": True, "parte": parte, "hold": 0,
                    })
                    continue
            # densidad segun energia de la seccion (nunca saltea el downbeat
            # ni las notas ECO, que son el remate de la frase)
            # en estribillo NO se saltean notas por rng: el patron es fijo y completo
            _es_eco = bool(contenido[s].get("eco"))
            if (not det and dens_local < 1.0 and s != 0 and not _es_eco
                    and rng.random() > dens_local):
                continue
            # eco de fin de frase: la misma nota una octava arriba (contesta
            # la frase desde el registro agudo, call-and-response)
            _oct_eco = 12 if _es_eco else 0
            midi_nota = notas_columnas[col] + oct_off + _oct_eco
            # proteger el eco del rango del cache (36-97)
            if midi_nota > 97:
                midi_nota -= 12
            # --- B: SALTOS EXPRESIVOS con resolucion conjunta contraria ---
            # regla clasica de contrapunto: un salto grande (4a/5a/8va) se
            # resuelve moviendose por grado conjunto en direccion CONTRARIA.
            # crea momentos memorables sin perder cohesion melodica.
            # (las notas ECO quedan afuera: son el remate fijo de la frase)
            if _salto["resolver"] != 0 and not det and not _es_eco:
                # esta nota RESUELVE el salto anterior: grado conjunto contrario
                base = _salto["desde"]
                _clases_esc = {(tonica + g) % 12 for g in escala}
                paso_res = 2 if (base + 2 * _salto["resolver"]) % 12 in _clases_esc else 1
                midi_nota = base + paso_res * _salto["resolver"]
                col = max(0, min(num_columnas - 1, col + _salto["resolver"]))
                _salto["resolver"] = 0
            elif (not det and not _es_eco and s % 4 == 2 and s <= 10 and hd == 0
                    and rng.random() < 0.12):
                # salto expresivo: 4a, 5a u 8va
                arriba = midi_nota < tonica + 24
                intervalo = rng.choice([5, 7, 12])
                midi_nota = midi_nota + (intervalo if arriba else -intervalo)
                col = max(0, min(num_columnas - 1, col + (2 if arriba else -2)))
                _salto["resolver"] = -1 if arriba else 1
                _salto["desde"] = midi_nota
            en_tiempo_fuerte = (s % 8 == 0)
            pc = midi_nota % 12
            es_consonante = pc in clases_ac
            if es_cierre_seccion and s == 0:
                midi_nota = ajustar_a_acorde(midi_nota, [tonos_ac[0], tonos_ac[2]],
                                             escala, tonica + 12)
            elif s == 0 and not es_consonante:
                # correccion armonica SOLO en el downbeat del compas: ahi el
                # choque con el cambio de acorde es audible. En el resto del
                # compas las notas de paso no-del-acorde son musicales y
                # preservan la identidad del motivo.
                midi_nota = resolver_disonancia(midi_nota, tonos_ac, escala, tonica + 12)
            # anti-repeticion SUAVE: la repeticion es parte de las melodias
            # pegadizas (mi-mi-mi), solo evitamos la TERCERA consecutiva.
            if len(notas_jugador) >= 2 and not en_tiempo_fuerte:
                u1 = notas_jugador[-1]
                u2 = notas_jugador[-2]
                if (not u1.get("es_acorde") and not u2.get("es_acorde")
                        and u1["midis"] and u2["midis"]
                        and u1["midis"][0] == midi_nota and u2["midis"][0] == midi_nota):
                    grados_esc = escala[:-1] if escala[-1] == 12 else escala
                    pc_rel = (midi_nota - (tonica % 12)) % 12
                    if pc_rel in grados_esc:
                        gi = grados_esc.index(pc_rel)
                        # reflejar en el borde: nunca wrap de octava
                        if gi >= len(grados_esc) - 1:
                            gi_nuevo = gi - 1
                        elif gi <= 0:
                            gi_nuevo = 1
                        else:
                            gi_nuevo = gi + (1 if det else rng.choice([-1, 1]))
                        midi_nota += grados_esc[gi_nuevo] - grados_esc[gi]
                    else:
                        midi_nota += -2 if midi_nota % 12 > 6 else 2
            notas_jugador.append({
                "cols": [col], "midis": [midi_nota],
                "tiempo": t, "es_acorde": False, "parte": parte, "hold": hd,
            })
            # adorno: mas frecuente cuanto mayor la energia de la seccion
            # en estribillo el adorno es fijo (no rng) para no ensuciar el gancho
            pone_adorno = (s % 8 == 4) if det else (rng.random() < prob_adorno_local)
            if hd == 0 and s % 4 == 0 and pone_adorno:
                col_adorno = (col + (2 if det else rng.choice([-1, 1, 2]))) % num_columnas
                t_adorno = t + paso16 * 2
                midi_adorno = notas_columnas[col_adorno] + oct_off
                notas_jugador.append({
                    "cols": [col_adorno], "midis": [midi_adorno],
                    "tiempo": t_adorno, "es_acorde": False, "parte": parte, "hold": 0,
                })
            # densidad ALTA (>1.0, niveles dificiles): nota ECO en el paso +2,
            # solo si el patron no tiene ya una nota ahi. Asi dens>1 agrega
            # notas de verdad en vez de no hacer nada.
            elif (not det and hd == 0 and s + 2 < 16
                    and contenido[s + 2] is None
                    and rng.random() < (max(0.0, dens_local - 1.0) * 0.7
                                        + max(0, _nivel_gc - 8) * 0.06)):
                col_eco = (col + rng.choice([-1, 1])) % num_columnas
                midi_eco = notas_columnas[col_eco] + oct_off
                notas_jugador.append({
                    "cols": [col_eco], "midis": [midi_eco],
                    "tiempo": t + paso16 * 2, "es_acorde": False,
                    "parte": parte, "hold": 0,
                })

        # STREAM de cierre (nivel 11+): 4 notas en 16avos consecutivos,
        # columnas adyacentes ascendentes o descendentes.
        if es_stream:
            col_base = rng.randint(0, max(0, num_columnas - stream_len))
            direccion = rng.choice([1, -1])
            if direccion == -1:
                col_base = min(num_columnas - 1, col_base + stream_len - 1)
            for k in range(stream_len):
                col_s = min(num_columnas - 1, max(0, col_base + k * direccion))
                t_s = t_intro_fin + compas_global * 4 * beat + (stream_ini + k) * paso16
                midi_s = notas_columnas[col_s] + oct_off
                notas_jugador.append({
                    "cols": [col_s], "midis": [midi_s],
                    "tiempo": t_s, "es_acorde": False, "parte": parte, "hold": 0,
                })

        _t_compas_ini = t_intro_fin + compas_global * 4 * beat
        _t_compas_fin = _t_compas_ini + 4 * beat

        # --- A: CADENCIA RESOLUTIVA al final de cada frase de 4 compases ---
        # la ultima nota de la frase se ajusta a un tono estable del acorde
        # (tonica o 5a): las frases "cierran" y la melodia suena intencional.
        # Es determinista (sin rng) asi aplica tambien al estribillo sin
        # alterar su identidad entre repeticiones.
        if compas_global % 4 == 3:
            for _n in reversed(notas_jugador):
                if _n["tiempo"] < _t_compas_ini:
                    break
                if not _n["es_acorde"] and _n["tiempo"] < _t_compas_fin:
                    _n["midis"][0] = ajustar_a_acorde(
                        _n["midis"][0], [tonos_ac[0], tonos_ac[2]],
                        escala, tonica + 12)
                    break

        # --- C: ANACRUSA (pickup): nota que anticipa el compas siguiente ---
        # ~20% de los compases ganan una nota en el paso 15 que "empuja" hacia
        # el proximo downbeat. Solo en niveles 3+ (los principiantes no la
        # necesitan) y fuera del estribillo (no ensuciar el gancho).
        if (not det and _nivel_gc >= 3 and not es_stream
                and contenido[15] is None and contenido[14] is None
                and rng.random() < 0.20):
            # verificar que haya aire: ultima nota del compas antes del paso 12
            _ok_aire = True
            for _n in reversed(notas_jugador):
                if _n["tiempo"] < _t_compas_ini:
                    break
                if _n["tiempo"] >= _t_compas_ini + 12 * paso16:
                    _ok_aire = False
                break
            if _ok_aire:
                _col_ana = contenido[0]["col"] if contenido[0] else rng.randint(0, num_columnas - 1)
                _col_ana = max(0, min(num_columnas - 1, _col_ana + rng.choice([-1, 0, 1])))
                notas_jugador.append({
                    "cols": [_col_ana],
                    "midis": [notas_columnas[_col_ana] + oct_off],
                    "tiempo": _t_compas_ini + 15 * paso16,
                    "es_acorde": False, "parte": parte, "hold": 0,
                })

    # --- recorrer las secciones de la forma en orden ---
    # el arco de tension emerge de los perfiles: intro baja, versos medios,
    # estribillos altos, puente contrastante. El estribillo reusa su bloque.
    for si, seccion in enumerate(plan_secciones):
        nombre = seccion["nombre"]
        perfil = seccion["perfil"]
        nc = seccion["compases"]
        material = perfil["material"]
        complejo = perfil["energia"] >= 0.7
        # la intro es escasa: notas largas espaciadas, no bloque completo
        if nombre == "intro":
            nota_intro = motivos_a[0][0]
            for c in range(nc):
                if c % 2 == 0:
                    notas_jugador.append({
                        "cols": [nota_intro], "midis": [notas_columnas[nota_intro]],
                        "tiempo": (c + 1) * 4 * beat,
                        "es_acorde": False, "parte": "intro", "hold": beat * 3,
                    })
            continue
        # generar (o reusar) el contenido de la seccion
        if nombre == "outro":
            # el outro melodico lo cubre el "desenlace estilizado" de abajo
            # (ascenso/cascada/redoble/etc.), que da un cierre mas expresivo.
            continue
        if nombre == "estribillo":
            if estribillo_compases is None:
                estribillo_compases = crear_bloque_seccion("B", nc, complejo)
            bloque = estribillo_compases
        else:
            bloque = crear_bloque_seccion(material, nc, complejo)
        # emitir los compases de la seccion
        prob_adorno_local = (0.08 + perfil["energia"] * 0.4) * densidad
        inicio = seccion["inicio_compas"]
        for c in range(nc):
            # compas global relativo al inicio del nudo (despues de la intro)
            compas_global = inicio - C_INTRO + c
            if compas_global < 0:
                continue
            contenido = bloque[c % len(bloque)]
            es_cierre_seccion = (c == nc - 1)
            # parte: mapear a nudo/desenlace por compat con el resto del juego
            if nombre == "outro":
                parte = "desenlace"
            else:
                parte = "nudo"
            # ESTRIBILLO = gancho memorable: se ancla a un offset armonico fijo
            #   (c, no compas_global) y se emite en modo determinista, de modo que
            #   la melodia suene identica en cada retorno del estribillo.
            if nombre == "estribillo":
                emitir_compas(contenido, compas_global, perfil, parte,
                              es_cierre_seccion, prob_adorno_local,
                              compas_armonico=c, det=True)
            else:
                emitir_compas(contenido, compas_global, perfil, parte,
                              es_cierre_seccion, prob_adorno_local)

    # --- desenlace con estilos variados ---
    estilo_des = rng.choice([
        "ascenso", "descenso", "acorde_final", "eco",
        "cascada", "redoble", "pregunta_respuesta"
    ])
    pat_des_opciones = [
        [1,0,0,0,0,0,0,0,0,0,0,0,1,0,0,0],   # 2 por compas
        [1,0,0,0,1,0,0,0,1,0,0,0,1,0,0,0],   # negras
        [1,0,0,0,0,0,1,0,0,0,0,0,1,0,0,0],   # sincopado
        [1,0,0,0,1,0,0,0,0,0,0,0,1,0,1,0],   # con remate
    ]
    pat_des = rng.choice(pat_des_opciones)
    octava_des = rng.choice([0, 12, 12])  # a veces misma octava, a veces arriba

    for c in range(C_DESENLACE):
        for s in range(16):
            if pat_des[s] == 0:
                continue
            t        = t_nudo_fin + c * 4 * beat + s * paso16
            progreso = (c * 16 + s) / (C_DESENLACE * 16)
            es_ultima = (c == C_DESENLACE - 1)

            if estilo_des == "ascenso":
                col = min(int(progreso * num_columnas), num_columnas - 1)
                midi = notas_columnas[col] + octava_des
            elif estilo_des == "descenso":
                col = max(0, num_columnas - 1 - int(progreso * num_columnas))
                midi = notas_columnas[col] + octava_des
            elif estilo_des == "acorde_final":
                if es_ultima and s == 0:
                    cols_ac = sorted(set([0, num_columnas // 2, num_columnas - 1]))
                    notas_jugador.append({
                        "cols": cols_ac,
                        "midis": [notas_columnas[cx] + octava_des for cx in cols_ac],
                        "tiempo": t, "es_acorde": True, "parte": "desenlace",
                        "hold": 4 * beat,
                    })
                    continue
                col = max(0, num_columnas - 1 - int(progreso * num_columnas))
                midi = notas_columnas[col] + octava_des
            elif estilo_des == "eco":
                col = 0 if (c * 16 + s) % 8 < 4 else num_columnas - 1
                midi = notas_columnas[col] + octava_des
            elif estilo_des == "cascada":
                col = (c * 4 + s // 4) % num_columnas
                midi = notas_columnas[col] + octava_des
            elif estilo_des == "redoble":
                # alterna rapido entre dos notas, acelera al final
                col = (s // 2) % num_columnas
                midi = notas_columnas[col] + octava_des
            else:  # pregunta_respuesta
                # primera mitad sube, segunda baja
                if c < C_DESENLACE // 2:
                    col = min(int((c / (C_DESENLACE / 2)) * num_columnas), num_columnas - 1)
                else:
                    p2 = (c - C_DESENLACE // 2) / (C_DESENLACE / 2)
                    col = max(0, num_columnas - 1 - int(p2 * num_columnas))
                midi = notas_columnas[col] + octava_des

            # holds mas largos al final del tema
            if es_ultima:
                es_hold = rng.random() < 0.85
                hold_dur = rng.choice([3, 4, 6]) * beat if es_hold else 0
            else:
                es_hold = rng.random() < 0.5
                hold_dur = rng.choice([2, 3]) * beat if es_hold else 0
            notas_jugador.append({
                "cols": [col], "midis": [midi],
                "tiempo": t, "es_acorde": False, "parte": "desenlace", "hold": hold_dur,
            })

    percusion = generar_percusion(rng, beat, t_intro_fin, t_nudo_fin, t_desenlace_fin,
                                  C_INTRO, C_NUDO, C_DESENLACE, kit, genero,
                                  pats_pre=pats_drums_ancla)

    # --- linea de bajo procedural (estilo y patron segun genero) ---
    estilos_g = [e for e in gdef.get("bajo_estilos", []) if e in ("round","pluck","sub","reese")]
    estilo_bajo = rng.choice(estilos_g) if estilos_g else rng.choice(["round", "pluck", "sub", "reese"])
    patrones_bajo = gdef.get("bajo_patrones") or [
        [1,0,0,0,1,0,0,0,1,0,0,0,1,0,0,0],   # negras
        [1,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0],   # blancas
        [1,0,0,1,0,0,1,0,1,0,0,1,0,0,1,0],   # sincopado
        [1,0,1,0,1,0,1,0,1,0,1,0,1,0,1,0],   # corcheas
        [1,0,0,0,1,0,1,0,1,0,0,0,1,0,1,0],   # groove
    ]
    pat_bajo = list(rng.choice(patrones_bajo))
    bajo_eventos = []
    # nota fundamental de cada grado de la progresion, una octava abajo de la tonica
    midi_bajo_base = tonica - 12
    # estilo de bajo mas musical: a veces usa la quinta del acorde y notas de
    # aproximacion (walking) hacia el acorde del compas siguiente.
    usar_walking = rng.random() < 0.5
    for c in range(C_NUDO):
        compas_t = t_intro_fin + c * 4 * beat
        grado = progresion[c % len(progresion)]
        grado_sig = progresion[(c + 1) % len(progresion)]
        # fundamental y quinta del acorde
        fund = midi_bajo_base + escala[grado % len(escala)]
        quinta = midi_bajo_base + nota_midi(0, escala, grado + 4) % 12
        # ajustar quinta a la octava del bajo (cerca de la fundamental)
        while quinta < fund:
            quinta += 12
        if quinta - fund > 7:
            quinta -= 12
        # nota fundamental del acorde siguiente (destino de la aproximacion)
        fund_sig = midi_bajo_base + escala[grado_sig % len(escala)]
        # posiciones activas del patron en este compas
        activos = [s for s in range(16) if pat_bajo[s] != 0]
        for i, s in enumerate(activos):
            t = compas_t + s * paso16
            midi_nota = fund  # por defecto, la fundamental (lo mas estable)
            es_ultimo_del_compas = (i == len(activos) - 1)
            if es_ultimo_del_compas and usar_walking and grado_sig != grado:
                # nota de aproximacion: un semitono/tono hacia la fundamental
                # del acorde siguiente (walking bass, convencion del jazz/funk)
                if fund_sig > fund:
                    midi_nota = fund_sig - 1   # aproximacion cromatica ascendente
                else:
                    midi_nota = fund_sig + 1   # aproximacion descendente
            elif i > 0 and s % 8 == 4 and rng.random() < 0.35:
                # en tiempos intermedios, a veces la quinta (da movimiento)
                midi_nota = quinta
            bajo_eventos.append({
                "tiempo": t,
                "midi": midi_nota,
                "dur": beat / 1000.0 * 0.9,
            })
    cancion_bajo = {
        "estilo": estilo_bajo,
        "eventos": sorted(bajo_eventos, key=lambda e: e["tiempo"]),
    }

    # parametros de la figura de lissajous de fondo (unica por seed)
    # NOMBRES DEL ENEMIGO: generados por seed para que cada cancion tenga
    # "su" antagonista con identidad. Se muestra en el HUD y en las
    # pantallas de stage/game over para reforzar la narrativa.
    _prefijos = ["NULL", "VOID", "ECHO", "STATIC", "PHASE", "GLITCH",
                 "PULSE", "FLUX", "DRIFT", "NOISE", "SHADE", "SINE",
                 "WARP", "SURGE", "DECAY", "LOOP", "FRAY", "HAZE"]
    _sufijos = ["CORE", "WAVE", "NODE", "FORM", "MIND", "FEED",
                "SYNC", "GRID", "BYTE", "CELL", "LINK", "TONE"]
    _nombre_enemigo = rng.choice(_prefijos) + "-" + rng.choice(_sufijos)
    lissajous = {
        "tipo": rng.choice(["lissajous", "lissajous", "rosa", "espiro", "mariposa"]),
        "a": rng.randint(1, 9),         # frecuencia horizontal
        "b": rng.randint(1, 9),         # frecuencia vertical
        "delta": rng.uniform(0, 6.28),  # desfase
        "vel": rng.uniform(0.1, 0.6),   # velocidad de animacion
        "puntos": rng.choice([160, 200, 240, 300]),
        "k": rng.randint(2, 7),         # parametro para rosa/espiro
        "ratio": rng.uniform(0.3, 0.8), # parametro para espiro
        "nombre": _nombre_enemigo,
    }

    # --- CAPA 3: eventos sorpresa en vivo ---
    # se disparan en momentos del nudo, elegidos por la seed
    eventos = []
    tipos_evento = ["silencio_drums", "solo_drums", "stutter", "boost_bajo", "freeze_mel"]
    n_eventos = rng.choice([0, 1, 1, 2, 2, 3])
    momentos_posibles = list(range(2, num_reps - 1))
    rng.shuffle(momentos_posibles)
    for k in range(min(n_eventos, len(momentos_posibles))):
        rep_ev = momentos_posibles[k]
        t_ev = t_intro_fin + rep_ev * 4 * 4 * beat
        eventos.append({
            "tiempo": t_ev,
            "tipo": rng.choice(tipos_evento),
            "dur": 4 * beat,  # dura un compas
        })
    eventos.sort(key=lambda e: e["tiempo"])

    # --- CAPA 2: mutacion de timbre ya aplicada a las notas del nudo ---

    # --- anti-simultaneas en niveles faciles ---
    # nivel 1-2: eliminar notas que caen muy juntas (< 250ms). En facil,
    # ninguna nota deberia caer antes de que el jugador pueda reaccionar
    # a la anterior. Mantenemos la primera del par y descartamos las
    # siguientes hasta que haya un gap suficiente.
    _niv_f = dif.get("nivel", 1)
    if _niv_f <= 2 and notas_jugador:
        gap_min = 400 if _niv_f == 1 else 300
        notas_jugador.sort(key=lambda n: n["tiempo"])
        filtradas = [notas_jugador[0]]
        for n in notas_jugador[1:]:
            if n["tiempo"] - filtradas[-1]["tiempo"] >= gap_min:
                filtradas.append(n)
        notas_jugador = filtradas

    # --- power-ups: cantidad variable por cancion (decidida por seed) ---
    #   ~25% ninguno   ~50% uno solo   ~20% dos o tres   ~5% varios (4-5)
    # Asi la aparicion se siente organica: a veces la cancion no trae nada,
    # a veces un premio, y ocasionalmente una lluvia.
    _roll_pu = rng.random()
    if _roll_pu < 0.25:
        cantidad_pu = 0
    elif _roll_pu < 0.75:
        cantidad_pu = 1
    elif _roll_pu < 0.95:
        cantidad_pu = rng.randint(2, 3)
    else:
        cantidad_pu = rng.randint(4, 5)
    if cantidad_pu > 0:
        # distribuir en la duracion util del nudo, con un jitter aleatorio
        margen_ini = 8000
        margen_fin = 5000
        dur_util = max(1, (t_nudo_fin - margen_fin) - (t_intro_fin + margen_ini))
        for i in range(cantidad_pu):
            # posicion base equiespaciada + jitter de +/- 20% del segmento
            base = (t_intro_fin + margen_ini
                    + int(dur_util * (i + 0.5) / cantidad_pu))
            jitter = rng.randint(-int(dur_util / cantidad_pu * 0.2),
                                  int(dur_util / cantidad_pu * 0.2))
            t_pu = max(t_intro_fin + margen_ini,
                       min(t_nudo_fin - margen_fin, base + jitter))
            col_pu = rng.randint(0, num_columnas - 1)
            tipo_pu = rng.choice(POWER_UPS)
            notas_jugador.append({
                "cols": [col_pu], "midis": [notas_columnas[col_pu]],
                "tiempo": int(t_pu), "es_acorde": False,
                "parte": "nudo", "hold": 0,
                "power_up": tipo_pu["id"],
            })

    # BOMBAS: notas rojas que NO deben tocarse. Si el jugador las pega,
    # explotan y pierde vida. Si las esquiva, no pasa nada (no cuentan como
    # miss). Solo aparecen a partir de NORMAL+ (nivel 4) porque en niveles
    # faciles el jugador se apoya en pegar todo, y castigarlo por eso seria
    # frustrante. Cada bomba se aisla temporalmente SOLO de otras notas en
    # SU MISMA columna (250ms). En otras columnas puede haber notas al mismo
    # tiempo — la bomba se distingue por su color rojo parpadeante, no por
    # estar aislada de todo (en canciones densas eso era casi imposible).
    nivel_dif = dif.get("nivel", 1)
    if nivel_dif >= 4:
        cant_bombas = rng.randint(3, 5) + max(0, (nivel_dif - 4) // 3)
        t_min = t_intro_fin + 800
        t_max = max(t_min + 800, t_desenlace_fin - 1200)
        GAP_COL = 250
        # indexar notas existentes por columna para busqueda O(k) por intento
        notas_por_col = {}
        for _n in notas_jugador:
            for _c in _n["cols"]:
                notas_por_col.setdefault(_c, []).append(_n["tiempo"])
        colocadas = 0
        intentos = 0
        while colocadas < cant_bombas and intentos < 60:
            intentos += 1
            col_b = rng.randint(0, num_columnas - 1)
            t_b = rng.randint(t_min, t_max)
            # solo mira la MISMA columna: la bomba tiene que estar sola en su
            # carril durante 250ms alrededor, para que el jugador tenga tiempo
            # de reaccionar y NO apretar esa tecla justo cuando pasa.
            if any(abs(t - t_b) < GAP_COL for t in notas_por_col.get(col_b, [])):
                continue
            notas_jugador.append({
                "cols": [col_b], "midis": [notas_columnas[col_b]],
                "tiempo": int(t_b), "es_acorde": False,
                "parte": "nudo", "hold": 0,
                "es_bomba": True,
            })
            # registrar la bomba tambien, asi otras bombas no caen juntas
            notas_por_col.setdefault(col_b, []).append(t_b)
            colocadas += 1

    # SIDECHAIN AL KICK: pre-calcular que eventos del bajo caen dentro de la
    # ventana de sidechain de un kick. En electronica, el bajo se atenua
    # brevemente cuando pega el kick, creando el "pompeo" caracteristico que
    # une percusion y bajo en una sola sensacion ritmica. Aca marcamos con
    # duckea=True los eventos del bajo cuyo tiempo cae en [t_kick, t_kick+90ms]
    # asi el dispatch en runtime aplica volumen atenuado sin CPU extra.
    SIDECHAIN_MS = 90
    kicks_tiempos = sorted(pe["tiempo"] for pe in percusion if pe["sample"] == "kick")
    if kicks_tiempos and cancion_bajo.get("eventos"):
        j = 0  # puntero al kick candidato
        for ev in cancion_bajo["eventos"]:
            t_ev = ev["tiempo"]
            # avanzar j mientras el kick actual sea muy anterior a ev
            while j + 1 < len(kicks_tiempos) and kicks_tiempos[j + 1] <= t_ev:
                j += 1
            # ev cae en ventana si el kick j esta antes y a menos de SIDECHAIN_MS
            if kicks_tiempos[j] <= t_ev <= kicks_tiempos[j] + SIDECHAIN_MS:
                ev["duckea"] = True

    return {
        "bpm":            BPM,
        "beat":           beat,
        "paso16":         paso16,
        "escala":         nombre_escala,
        "genero":         genero,
        "duracion_loop":  t_desenlace_fin,
        "notas_jugador":  sorted(notas_jugador, key=lambda n: n["tiempo"]),
        "percusion":      percusion,
        "bajo":           cancion_bajo,
        "kit":            kit,
        "instrumento":    instrumento,
        "notas_columnas": notas_columnas,
        "lissajous":      lissajous,
        "eventos":        eventos,
        "estructura": {
            "intro_fin":     t_intro_fin,
            "nudo_fin":      t_nudo_fin,
            "desenlace_fin": t_desenlace_fin,
        }
    }

def hold_pixels(hold_ms, vel, fps=60):
    if hold_ms <= 0:
        return 0
    return int((hold_ms / (1000 / fps)) * vel)

# ══════════════════════════════════════════════════════ >>GAME_STATE<< ═══

def iniciar_partida(seed, mods=None, stage_info=None, puntos_iniciales=0,
                    instrumento_forzado=None, perks=None, tutorial=False):
    global cache_notas, cache_notas_largas
    # limpiar efectos visuales de una partida anterior
    particulas.clear()
    textos_flotantes.clear()
    flashes.clear()
    ondas.clear()
    indicadores_hit.clear()
    # mods: set de ids; si es None usa mods_activos (modo libre)
    mods_partida = set(mods) if mods is not None else set(mods_activos)
    dif     = get_dificultad(seed)
    # modo instrumento: forzar max 4 columnas y sin acordes
    if modo_instrumento and dif["columnas"] > 4:
        dif = dict(dif)
        dif["columnas"] = 4
        dif["acordes"] = False
    cancion = generar_cancion(int(seed * 23819), dif, instrumento_forzado=instrumento_forzado)
    # modo instrumento: simplificar la cancion para line-in
    if modo_instrumento:
        simplificar_para_instrumento(cancion)
    inst = cancion["instrumento"]
    # limitar holds: percusivos max 800ms, todos max 4s (duracion del sample)
    hold_max = HOLD_MAX_PERCUSIVO if inst not in INST_SUSTAIN else HOLD_MAX
    for n in cancion["notas_jugador"]:
        if n.get("hold", 0) > hold_max:
            n["hold"] = hold_max

    # RAFAGAS: la cancion pulsa fuerte entre AVALANCHA y RESPIRO.
    # - fase avalancha (2 compases): todas las notas + notas extra duplicadas
    #   en columnas vecinas -> un muro de notas denso e intenso.
    # - fase respiro (1 compas): solo el downbeat -> casi silencio de notas.
    # El contraste es marcado (~4-5x) para que se sienta de verdad.
    if "rafagas" in mods_partida:
        beat = cancion["beat"]
        compas_ms = beat * 4
        num_cols_raf = dif["columnas"]
        # las notas EXTRA de la avalancha escalan con el nivel:
        #   nivel <=4: SIN extras (el contraste viene del respiro casi vacio)
        #   nivel 5-8: 50% de extras
        #   nivel 9+:  todas las extras (muro de notas completo)
        _nivel_raf = dif.get("nivel", 1)
        if _nivel_raf <= 4:
            prob_extra = 0.0
        elif _nivel_raf <= 8:
            prob_extra = 0.5
        else:
            prob_extra = 1.0
        _rng_raf = random.Random(int(seed * 31) + 7)
        if compas_ms > 0:
            # ciclo de 3 compases: 2 de avalancha + 1 de respiro
            ciclo_ms = compas_ms * 3
            notas_filtradas = []
            extras = []
            for n in cancion["notas_jugador"]:
                pos_ciclo = n["tiempo"] % ciclo_ms
                en_avalancha = pos_ciclo < compas_ms * 2
                if en_avalancha:
                    # fase AVALANCHA: mantener la nota
                    n["fase_rafaga"] = True
                    notas_filtradas.append(n)
                    # duplicar en columna vecina segun el nivel (muro de notas)
                    if (prob_extra > 0 and not n.get("es_acorde")
                            and num_cols_raf > 1 and n.get("cols")
                            and _rng_raf.random() < prob_extra):
                        col0 = n["cols"][0]
                        col_vec = (col0 + 1) % num_cols_raf
                        if col_vec != col0:
                            extras.append({
                                "cols": [col_vec],
                                "midis": [n["midis"][0]] if n.get("midis") else [],
                                "tiempo": n["tiempo"] + beat // 2,  # medio tiempo despues
                                "es_acorde": False,
                                "parte": n.get("parte", "nudo"),
                                "hold": 0,
                                "fase_rafaga": True,
                            })
                else:
                    # fase RESPIRO: solo el downbeat del compas (casi silencio)
                    pos_en_compas = n["tiempo"] % compas_ms
                    es_downbeat = pos_en_compas < beat * 0.5
                    if es_downbeat:
                        n["fase_rafaga"] = False
                        notas_filtradas.append(n)
            notas_filtradas += extras
            notas_filtradas.sort(key=lambda x: x["tiempo"])
            if len(notas_filtradas) >= max(4, len(cancion["notas_jugador"]) // 3):
                cancion["notas_jugador"] = notas_filtradas
                cancion["tiene_rafagas"] = True
                cancion["rafaga_ciclo_ms"] = ciclo_ms
                cancion["rafaga_compas_ms"] = compas_ms
    # mostrar el tag de la partida antes de arrancar
    pantalla.fill(NEGRO)
    titulo = fuente_grande.render("* RHYTHM *", True, BLANCO)
    pantalla.blit(titulo, (ANCHO // 2 - titulo.get_width() // 2, 130))
    if stage_info:
        st_txt = fuente.render(f"STAGE {stage_info['n']}/{NUM_STAGES}", True, BLANCO)
        pantalla.blit(st_txt, (ANCHO // 2 - st_txt.get_width() // 2, 195))
    gen_txt = fuente.render(f"SEED {seed}", True, COLOR_GENERO.get(cancion.get('genero',''), BLANCO))
    pantalla.blit(gen_txt, (ANCHO // 2 - gen_txt.get_width() // 2, 235))
    modo_txt = fuente.render(f"INSTRUMENTO: {inst}", True, GRIS_MED)
    pantalla.blit(modo_txt, (ANCHO // 2 - modo_txt.get_width() // 2, 285))
    esc_txt = fuente_chica.render(f"ESCALA: {cancion['escala'].upper()}   {cancion['bpm']} BPM", True, GRIS)
    pantalla.blit(esc_txt, (ANCHO // 2 - esc_txt.get_width() // 2, 325))
    if mods_partida:
        nombres = [m["nombre"] for m in MODIFICADORES if m["id"] in mods_partida]
        mod_txt = fuente_chica.render("MODS: " + ", ".join(nombres), True, BLANCO)
        pantalla.blit(mod_txt, (ANCHO // 2 - mod_txt.get_width() // 2, 360))
    presentar()
    pygame.time.delay(500)

    # renderizar el instrumento si no está en cache
    if inst not in cache_por_instrumento:
        tipo = INSTRUMENTOS_JUGADOR.get(inst) or INSTRUMENTOS_RAROS.get(inst)
        renderizar_instrumento(inst, tipo, dibujar_progreso=True)
    cache_notas = cache_por_instrumento[inst]
    cache_notas_largas = cache_largas_por_instrumento[inst]

    # pre-renderizar sonidos de bajo (uno por midi único usado)
    estilo_b = cancion["bajo"]["estilo"]
    cache_bajo = {}
    midis_bajo = set(e["midi"] for e in cancion["bajo"]["eventos"])
    for mb in midis_bajo:
        fb = midi_a_freq(mb)
        wave_b = synth_bajo(fb, 0.5, estilo_b)
        cache_bajo[mb] = np_to_sound(wave_b, vol=0.3, pan=0.0)
    cancion["cache_bajo"] = cache_bajo

    # --- aplicar modificadores de columnas ---
    num_cols_p = dif["columnas"]
    # ESPEJO: invierte el mapeo de teclas
    mapa_teclas = {c: c for c in range(num_cols_p)}
    if "espejo" in mods_partida:
        mapa_teclas = {c: (num_cols_p - 1 - c) for c in range(num_cols_p)}

    mult_mods = 1.0
    for m in MODIFICADORES:
        if m["id"] in mods_partida:
            mult_mods *= m["mult"]

    # --- WARM-UP PROFUNDO: asegurar que TODO este listo antes del reloj ---
    # Tres fuentes de lag en los primeros segundos que eliminamos aca,
    # mientras la pantalla de carga sigue visible:
    # 1) GC: la sintesis creo cientos de arrays temporales -> collect() ahora
    #    (y no en medio del gameplay).
    import gc
    gc.collect()
    # 2) MIXER FRIO: el primer play() de cada Sound inicializa el canal y
    #    causa micro-stutter. Pre-tocamos todo a volumen 0.
    _sonidos_warmup = []
    for _k, _snd in cancion["kit"].items():
        if _snd:
            _sonidos_warmup.append(_snd)
    _sonidos_warmup.extend(list(cache_bajo.values())[:4])
    _midis_usados = set()
    for _n in cancion["notas_jugador"][:12]:
        for _m in _n["midis"]:
            _midis_usados.add(_m)
    for _m in list(_midis_usados)[:8]:
        if _m in cache_notas:
            _sonidos_warmup.append(cache_notas[_m])
    for _snd in _sonidos_warmup:
        _ch = _snd.play()
        if _ch:
            _ch.set_volume(0.0, 0.0)
    pygame.time.delay(80)     # dejar que suenen "en silencio"
    pygame.mixer.stop()       # cortar todos los warmups
    # 3) RENDER FRIO: pre-renderizar textos tipicos del HUD para calentar
    #    el cache de la fuente (el primer render de cada glifo es lento).
    for _f in (fuente_grande, fuente, fuente_chica):
        _f.render("0123456789xCOMBO PERFECTO BIEN MISS", True, BLANCO)
    gc.collect()              # segunda pasada: limpiar los warmups
    # drenar eventos de teclado acumulados durante la carga
    pygame.event.pump()
    pygame.event.clear()
    pygame.time.delay(40)
    pygame.event.pump()
    inicio_partida = pygame.time.get_ticks()

    result = {
        "seed":           seed,
        "dificultad":     dif,
        "cancion":        cancion,
        "indice_jugador": 0,
        "indice_perc":    0,
        "indice_bajo":    0,
        "_arranco_audio": False,
        "_arranco_notas": False,
        "inicio":         inicio_partida,
        "notas_cayendo":  [],
        "puntos":         puntos_iniciales,
        "puntos_stage_inicio": puntos_iniciales,  # puntos con los que arranco este stage
        "meta_puntos":   0,    # meta del stage (se calcula abajo con perks)
        "loop_offset":   0,    # offset temporal para loop de cancion (ms)
        "terminada":      False,
        "holds_activos":  {},
        "ultimo_hit":     None,
        "combo":          0,
        "max_combo":      0,
        # contadores de precision para el rank de performance del stage
        "n_perfecto": 0, "n_bien": 0, "n_ok": 0, "n_mal": 0, "n_miss": 0,
        "vida":           20,
        "vida_max":       20,
        "game_over":      False,
        "liss_pulso":     0.0,
        "mods":           set(mods_partida),
        "mult_mods":      mult_mods,
        "velocidad":      VELOCIDAD * dif.get("vel_mult", 1.0) * (2.0 if "veloz" in mods_partida else 1.0),
        "stage_info":     stage_info,
        "mapa_teclas":    mapa_teclas,
        "es_inverso":     "inverso" in mods_partida,
        "zona_y":         90 if "inverso" in mods_partida else ZONA_Y,
        # --- perks roguelike ---
        "perks":          list(perks) if perks else [],
        "escudo_cargas":  0,
        "combo_save_cd":  0,       # cooldown en ms (0 = listo)
        "efectos_activos": {},     # {id: tiempo_fin_ms} para power-ups temporales
        # cola de samples del jugador para cuantizar el disparo al beat.
        # Cuando el jugador pega TEMPRANO (dentro de una ventana pequena de
        # ~45ms), el sample no se toca inmediatamente sino en el tiempo
        # target de la nota. Asi las notas melodicas caen en grid con la
        # percusion/bajo y se integran a la cancion en vez de sentirse
        # como una capa aparte. Formato: [(t_target_ms, snd, volL, volR), ...]
        "snd_pendientes": [],
    }
    # aplicar perks al estado de la partida
    perks_ids = [p["id"] for p in (perks or [])]
    p = result  # alias
    for pid in perks_ids:
        if pid == "escudo":
            p["escudo_cargas"] += 3
        elif pid == "corazon":
            p["vida_max"] += 5
            p["vida"] = p["vida_max"]
        elif pid == "ventana":
            p["perk_ventana"] = True  # flag: hit window 150 -> 187
        elif pid == "multi":
            p["mult_mods"] *= 1.5
        elif pid == "combo_save":
            p["perk_combo_save"] = True
        elif pid == "perfecto":
            p["perk_perfecto"] = True  # perfectos valen doble
        elif pid == "lento":
            p["velocidad"] *= 0.85
        elif pid == "iman":
            p["perk_iman"] = True  # perfecto window 30 -> 50ms
        elif pid == "resurreccion":
            p["perk_resurreccion"] = True  # revive 1 vez con 5 de vida (se consume)
        elif pid == "regen":
            p["perk_regen"] = True         # +1 vida cada 20 de combo
        elif pid == "racha":
            p["combo_div"] = 4             # multiplicador de combo cada 4 (vs 5)
        elif pid == "hold_master":
            p["hold_bonus"] = 10           # holds completos +10 (vs +5)
        elif pid == "cazador":
            p["perk_cazador"] = True       # power-ups duran el doble
    # calcular meta del stage (en modo run; en modo libre meta=0 = sin limite)
    if stage_info:
        nivel = dif.get("nivel", 1)
        p["meta_puntos"] = calcular_meta(nivel, stage_info.get("n", 1))
    # modo TUTORIAL: meta chica, imposible morir
    if tutorial:
        p["es_tutorial"] = True
        p["meta_puntos"] = 60

    # --- ventanas de timing escaladas por dificultad ---
    # niveles faciles perdonan mas; niveles altos exigen precision.
    _nivel = dif.get("nivel", 1)
    w_hit = 210 - _nivel * 5      # nivel 1: 205ms ... nivel 15: 135ms
    w_perf = 48 - _nivel          # nivel 1: 47ms  ... nivel 15: 33ms
    if p.get("perk_ventana"):
        w_hit = int(w_hit * 1.25)
    if p.get("perk_iman"):
        w_perf += 18
    p["w_hit"] = w_hit
    p["w_perf"] = w_perf

    # --- BUFFER DE ARRANQUE ---
    # garantizar que la primera nota empiece fuera de pantalla.
    # usamos la velocidad real de esta partida (ya incluye vel_mult, veloz, lento).
    vel_real = p["velocidad"]
    _px_ms = vel_real / (1000 / 60)
    es_inv = p.get("es_inverso", False)
    if es_inv:
        _antic = (ALTO - p.get("zona_y", ZONA_Y) + 60) / max(0.01, _px_ms)
    else:
        _antic = (p.get("zona_y", ZONA_Y) + 60) / max(0.01, _px_ms)
    c = p["cancion"]
    _primer_nota = min((n["tiempo"] for n in c["notas_jugador"]), default=999999)
    _buffer = max(0, int(_antic - _primer_nota + 300))  # +300ms margen
    if _buffer > 0:
        for n in c["notas_jugador"]:
            n["tiempo"] += _buffer
        for pe in c["percusion"]:
            pe["tiempo"] += _buffer
        for ev in c["bajo"]["eventos"]:
            ev["tiempo"] += _buffer
        for ev in c.get("eventos", []):
            ev["tiempo"] += _buffer
        c["estructura"]["intro_fin"]     += _buffer
        c["estructura"]["nudo_fin"]      += _buffer
        c["estructura"]["desenlace_fin"] += _buffer
        c["duracion_loop"]               += _buffer

    # --- WARM-UP DE RENDER: ejecutar frames completos ANTES de arrancar ---
    # El primer frame real de dibujar_juego construye todo el pipeline en frio
    # (fondo lissajous, clip rects, superficies alpha, paths de notas) y puede
    # tardar >16ms, causando saltos visibles. Lo ejecutamos 3 veces ACA, con
    # notas fake que cubren todos los paths de dibujo (normal, acorde, hold,
    # power-up). Nada se presenta en pantalla: solo calienta caches y JIT de
    # pygame. Al final re-tomamos 'inicio' como ULTIMA operacion.
    _zy_w = p.get("zona_y", ZONA_Y)
    _fake_notas = [
        {"cols": [0], "midis": [c["notas_columnas"][0]], "tiempo_ms": 99999,
         "acertadas": set(), "es_acorde": False, "hold": 0, "hold_px": 0, "y": _zy_w - 200},
        {"cols": [0, 1], "midis": [c["notas_columnas"][0], c["notas_columnas"][-1]],
         "tiempo_ms": 99999, "acertadas": set(), "es_acorde": True,
         "hold": 0, "hold_px": 0, "y": _zy_w - 300},
        {"cols": [0], "midis": [c["notas_columnas"][0]], "tiempo_ms": 99999,
         "acertadas": set(), "es_acorde": False, "hold": 800, "hold_px": 60, "y": _zy_w - 120},
        {"cols": [0], "midis": [c["notas_columnas"][0]], "tiempo_ms": 99999,
         "acertadas": set(), "es_acorde": False, "hold": 0, "hold_px": 0,
         "power_up": "estrella", "y": _zy_w - 400},
    ]
    try:
        p["notas_cayendo"] = _fake_notas
        for _wf in range(3):
            dibujar_juego(p, _wf * 16)
    except Exception:
        pass  # el warm-up nunca debe romper el arranque
    p["notas_cayendo"] = []
    gc.collect()
    pygame.event.pump()
    pygame.event.clear()
    p["inicio"] = pygame.time.get_ticks()   # ULTIMA operacion: reloj en cero real

    return p

def _mezclar_sample(buffer, sample_arr, pos_sample, vol_l=1.0, vol_r=1.0):
    """Mezcla un sample stereo en el buffer global en la posicion dada"""
    if pos_sample < 0:
        return
    n_buf = buffer.shape[0]
    n_smp = sample_arr.shape[0]
    fin = min(pos_sample + n_smp, n_buf)
    if fin <= pos_sample:
        return
    largo = fin - pos_sample
    buffer[pos_sample:fin, 0] += sample_arr[:largo, 0] * vol_l
    buffer[pos_sample:fin, 1] += sample_arr[:largo, 1] * vol_r

def _sound_to_array(snd):
    """Convierte un pygame.Sound a array stereo float64 normalizado"""
    arr = pygame.sndarray.array(snd).astype(np.float64) / 32767.0
    if arr.ndim == 1:
        arr = np.column_stack((arr, arr))
    return arr

def exportar_cancion(partida):
    """Renderiza la cancion completa (melodia + percusion + bajo) a un WAV."""
    try:
        c = partida["cancion"]
        dur_ms = c["duracion_loop"] + 3000
        n_total = int(SR * dur_ms / 1000)
        buffer = np.zeros((n_total, 2), dtype=np.float64)
        num_cols_t = partida["dificultad"]["columnas"]
        # 1) MELODIA
        for nota in c["notas_jugador"]:
            t_ms = nota["tiempo"]
            pos = int(SR * t_ms / 1000)
            es_hold = nota.get("hold", 0) > 0 and not nota.get("es_acorde")
            for idx_c, col in enumerate(nota["cols"]):
                if idx_c >= len(nota.get("midis", [])):
                    continue
                midi = nota["midis"][idx_c]
                if es_hold:
                    snd = cache_notas_largas.get(midi) or cache_notas.get(midi)
                else:
                    snd = cache_notas.get(midi)
                if snd is None:
                    continue
                arr = _sound_to_array(snd)
                if num_cols_t > 1:
                    pan = col / (num_cols_t - 1)
                else:
                    pan = 0.5
                vol = 0.85
                vol_l = vol * (1.0 - pan * 0.6)
                vol_r = vol * (0.4 + pan * 0.6)
                _mezclar_sample(buffer, arr, pos, vol_l, vol_r)
        # 2) PERCUSION
        pan_perc = {
            "kick": (1.0, 1.0), "snare": (1.0, 1.0), "clap": (0.95, 0.95),
            "hihat": (0.7, 1.0), "hihat_o": (0.7, 1.0),
            "clave": (1.0, 0.7), "agogo": (1.0, 0.65),
            "crash": (0.9, 0.9), "tom1": (1.0, 0.8), "tom2": (0.8, 1.0),
        }
        kit = c["kit"]
        kit_arr = {}
        for k, snd in kit.items():
            if snd is not None:
                kit_arr[k] = _sound_to_array(snd)
        for ev in c["percusion"]:
            sname = ev["sample"]
            if sname not in kit_arr:
                continue
            pos = int(SR * ev["tiempo"] / 1000)
            vol = min(1.0, ev["vol"] * 1.2)
            gl, gr = pan_perc.get(sname, (1.0, 1.0))
            _mezclar_sample(buffer, kit_arr[sname], pos, vol * gl, vol * gr)
        # 3) BAJO
        cache_bajo = c.get("cache_bajo", {})
        for ev in c["bajo"]["eventos"]:
            snd = cache_bajo.get(ev["midi"])
            if snd is None:
                continue
            arr = _sound_to_array(snd)
            pos = int(SR * ev["tiempo"] / 1000)
            _mezclar_sample(buffer, arr, pos, 1.0, 1.0)
        # normalizar
        pico = np.max(np.abs(buffer))
        if pico > 0:
            buffer = buffer / pico * 0.95
        salida = np.clip(buffer * 32767, -32768, 32767).astype(np.int16)
        carpeta = os.path.join(BASE_DIR, "export")
        try:
            os.makedirs(carpeta, exist_ok=True)
        except Exception:
            carpeta = "."
        seed_str = str(int(partida["seed"])).zfill(4)
        inst_safe = "".join(ch if ch.isalnum() else "_" for ch in c["instrumento"])
        ruta = os.path.join(carpeta, f"rhythm_seed{seed_str}_{inst_safe}.wav")
        with wave.open(ruta, "wb") as wf:
            wf.setnchannels(2)
            wf.setsampwidth(2)
            wf.setframerate(SR)
            wf.writeframes(salida.tobytes())
        print(f"Cancion exportada a: {ruta}")
        return ruta
    except Exception as e:
        print(f"Error exportando: {e}")
        return None

def tick_background(partida, ahora):
    c = partida["cancion"]
    kit = c["kit"]
    loop_off = partida.get("loop_offset", 0)

    # --- WIN CONDITION: alcanzar la meta de puntos del stage ---
    meta = partida.get("meta_puntos", 0)
    if meta > 0 and not partida["terminada"]:
        ganado = partida["puntos"] - partida.get("puntos_stage_inicio", 0)
        if ganado >= meta:
            partida["terminada"] = True
            partida["terminada_t"] = pygame.time.get_ticks()
            pygame.mixer.stop()  # parar la musica al ganar
            # si es el ultimo stage del run, el enemigo (figura) explota
            si = partida.get("stage_info")
            if si and si["n"] >= NUM_STAGES:
                _explotar_figura(partida)
    # modo libre (sin meta): la cancion termina al acabarse
    if meta == 0 and ahora >= c["duracion_loop"] and not partida["terminada"]:
        partida["terminada"] = True

    # --- LOOP: cuando se agotan perc/bajo/jugador, resetear y avanzar offset ---
    perc_done = partida["indice_perc"] >= len(c["percusion"])
    bajo_done = partida["indice_bajo"] >= len(c["bajo"]["eventos"])
    jug_done  = partida["indice_jugador"] >= len(c["notas_jugador"])
    if perc_done and bajo_done and not partida["terminada"]:
        partida["loop_offset"] = loop_off + c["duracion_loop"]
        partida["indice_perc"] = 0
        partida["indice_bajo"] = 0
        if jug_done:
            partida["indice_jugador"] = 0
        partida["_arranco_audio"] = False   # re-aplicar anti-avalancha en el nuevo loop
        partida["_arranco_notas"] = False  # re-aplicar anti-avalancha de notas
        loop_off = partida["loop_offset"]

    # anti-avalancha: si hubo un hueco de timing (lag de carga), muchos eventos
    # quedaron atrasados. Reproducirlos todos de golpe suma amplitudes y clipea.
    # En ese caso, avanzamos los indices al presente SIN reproducir el atraso.
    UMBRAL_ATRASO = 120   # ms; un frame normal es ~16ms
    if not partida.get("_arranco_audio"):
        # primer tick de audio: descartar cualquier evento con tiempo < ahora
        # (evita el golpe inicial de eventos acumulados durante la carga)
        while (partida["indice_perc"] < len(c["percusion"])
               and c["percusion"][partida["indice_perc"]]["tiempo"] + loop_off < ahora - UMBRAL_ATRASO):
            partida["indice_perc"] += 1
        bajo0 = c["bajo"]["eventos"]
        while (partida["indice_bajo"] < len(bajo0)
               and bajo0[partida["indice_bajo"]]["tiempo"] + loop_off < ahora - UMBRAL_ATRASO):
            partida["indice_bajo"] += 1
        partida["_arranco_audio"] = True

    # paneo por tipo de elemento de percusión
    pan_perc = {
        "kick": (1.0, 1.0), "snare": (1.0, 1.0), "clap": (0.95, 0.95),
        "hihat": (0.7, 1.0), "hihat_o": (0.7, 1.0),
        "clave": (1.0, 0.7), "agogo": (1.0, 0.65),
        "crash": (0.9, 0.9), "tom1": (1.0, 0.8), "tom2": (0.8, 1.0),
    }
    # CAPA 3: determinar si hay un evento activo ahora
    evento_activo = None
    ahora_en_loop = ahora - loop_off
    for ev in c.get("eventos", []):
        if ev["tiempo"] <= ahora_en_loop < ev["tiempo"] + ev["dur"]:
            evento_activo = ev["tipo"]
            break
    partida["evento_activo"] = evento_activo

    while partida["indice_perc"] < len(c["percusion"]) and ahora >= c["percusion"][partida["indice_perc"]]["tiempo"] + loop_off:
        p = c["percusion"][partida["indice_perc"]]
        sample = kit.get(p["sample"])
        # silencio_drums: saltear toda la percusion en ese tramo
        saltar = (evento_activo == "silencio_drums")
        # boost de percusion: bajado de 1.8/2.4 a 1.5/2.0 en conjunto con la
        # bajada del volumen del jugador (0.80 -> 0.62 arriba). El ratio
        # jugador/percu queda mas favorable a la percu, y baja el nivel absoluto
        # (mas headroom, mezcla mas "de estudio" y menos saturada).
        boost = 2.0 if evento_activo == "solo_drums" else 1.5
        if sample and not saltar:
            vol = min(1.0, p["vol"] * boost) * config["volumen"]
            gl, gr = pan_perc.get(p["sample"], (1.0, 1.0))
            ch = sample.play()
            if ch:
                ch.set_volume(vol * gl, vol * gr)
        partida["indice_perc"] += 1

    # reproducir linea de bajo (boost_bajo lo sube)
    bajo = c["bajo"]["eventos"]
    cache_bajo = c.get("cache_bajo", {})
    # bajado de 1.2/1.8 a 1.05/1.5 en linea con el resto del rebalanceo
    vol_bajo = 1.5 if evento_activo == "boost_bajo" else 1.05
    while partida["indice_bajo"] < len(bajo) and ahora >= bajo[partida["indice_bajo"]]["tiempo"] + loop_off:
        ev = bajo[partida["indice_bajo"]]
        snd_b = cache_bajo.get(ev["midi"])
        if snd_b:
            ch_b = snd_b.play()
            if ch_b:
                # sidechain: si este evento del bajo cae en la ventana de un
                # kick (pre-marcado en generar_cancion), atenuar 40% para el
                # efecto de "pompeo" clasico de electronica. Une bajo y kick
                # en una sola sensacion ritmica en vez de dos capas separadas.
                duck = 0.60 if ev.get("duckea") else 1.0
                ch_b.set_volume(min(1.0, config["volumen"] * vol_bajo * duck))
        partida["indice_bajo"] += 1

def _explotar_notas_muerte(partida):
    """Al morir, todas las notas que estaban cayendo explotan en particulas
    rojas — el tablero 'colapsa' visualmente en vez de congelarse."""
    num_cols = partida["dificultad"]["columnas"]
    ancho_col = ANCHO // num_cols
    for grupo in partida["notas_cayendo"]:
        gy = grupo.get("y")
        if gy is None or gy < -40 or gy > ALTO + 40:
            continue
        for c in grupo["cols"]:
            cx = c * ancho_col + ancho_col // 2
            crear_explosion(cx, int(gy) + 14, 22, color=(255, 70, 70), potencia=1.3)
    partida["notas_cayendo"] = []

def _explotar_figura(partida):
    """Genera una explosion de particulas a partir de la figura de fondo."""
    liss = partida["cancion"].get("lissajous")
    if not liss:
        return
    col = color_genero(partida)
    cx_c = ANCHO / 2
    cy_c = (ZONA_Y) / 2 + 20
    rx = ANCHO * 0.42
    ry = ZONA_Y * 0.40
    tipo = liss.get("tipo", "lissajous")
    puntos = _curva_fondo(tipo, liss, liss["puntos"], 0, cx_c, cy_c, rx, ry)
    # emitir particulas desde puntos de la figura
    for px, py in puntos[::2]:
        ang = math.atan2(py - cy_c, px - cx_c)
        vel = random.uniform(3, 9)
        particulas.append({
            "x": float(px), "y": float(py),
            "dx": math.cos(ang) * vel + random.uniform(-2, 2),
            "dy": math.sin(ang) * vel + random.uniform(-2, 2),
            "vida": random.randint(40, 90), "vida_max": 90,
            "tam": random.randint(2, 5), "color": col,
            "forma": "rect", "spin": random.uniform(-0.3, 0.3),
        })
    crear_shake(20)
    SND_EXPLOSION_BIG.set_volume(0.6 * config["volumen"])
    SND_EXPLOSION_BIG.play()

def get_parte(partida, ahora):
    e = partida["cancion"]["estructura"]
    # usar tiempo dentro del loop actual
    t = ahora - partida.get("loop_offset", 0)
    dur = partida["cancion"]["duracion_loop"]
    if dur > 0:
        t = t % dur
    if t < e["intro_fin"]:       return "INTRO"
    elif t < e["nudo_fin"]:      return "NUDO"
    elif t < e["desenlace_fin"]: return "FIN"
    return "FIN"

GRIS_FONDO = (28, 28, 28)

def _curva_fondo(tipo, liss, npts, t_anim, cx_c, cy_c, rx, ry, fase_extra=0.0, jitter=0.0):
    """Genera los puntos de la figura segun el tipo"""
    a = liss["a"]; b = liss["b"]; delta = liss["delta"]
    k = liss.get("k", 3); ratio = liss.get("ratio", 0.5)
    pts = []
    for i in range(npts + 1):
        tt = (i / npts) * 2 * math.pi
        if tipo == "rosa":
            # curva rosa: r = cos(k*theta)
            r = math.cos(k * tt + t_anim * 0.5)
            x = cx_c + rx * r * math.cos(tt + fase_extra)
            y = cy_c + ry * r * math.sin(tt + fase_extra)
        elif tipo == "espiro":
            # espirógrafo: suma de dos circulos
            x = cx_c + rx * (ratio * math.cos(tt) + (1 - ratio) * math.cos(k * tt + t_anim))
            y = cy_c + ry * (ratio * math.sin(tt) - (1 - ratio) * math.sin(k * tt + t_anim))
        elif tipo == "mariposa":
            # curva mariposa simplificada
            e = math.exp(math.cos(tt)) - 2 * math.cos(4 * tt + t_anim * 0.3)
            x = cx_c + rx * 0.28 * math.sin(tt * a) * e
            y = cy_c + ry * 0.28 * math.cos(tt * b + fase_extra) * e
        else:  # lissajous
            x = cx_c + rx * math.sin(a * tt + t_anim + delta + fase_extra)
            y = cy_c + ry * math.sin(b * tt)
        if jitter > 0:
            x += random.uniform(-jitter, jitter)
            y += random.uniform(-jitter, jitter)
        pts.append((int(x), int(y)))
    return pts

def dibujar_fondo_lissajous(partida, ahora):
    """Dibuja la figura procedural de fondo (el 'enemigo').
    Late con el kick y las notas, vibra en holds, y se desmorona por stage."""
    liss = partida["cancion"].get("lissajous")
    if not liss:
        return
    tipo = liss.get("tipo", "lissajous")
    vel = liss["vel"]; npts = liss["puntos"]
    t_anim = ahora * 0.001 * vel
    beat = partida["cancion"]["beat"]
    fase_beat = (ahora % beat) / beat
    pulso_beat = math.exp(-fase_beat * 4)
    pulso_jug = partida.get("liss_pulso", 0.0)
    partida["liss_pulso"] = pulso_jug * 0.90
    pulso = max(pulso_beat * 0.7, pulso_jug)
    escala = 0.92 + pulso * 0.12

    # --- DAÑO DEL ENEMIGO segun el stage del run ---
    # stage 1 = intacto, stage 4 = casi destruido
    si = partida.get("stage_info")
    stage_n = si["n"] if si else 1
    dano = (stage_n - 1) / max(1, NUM_STAGES - 1)  # 0.0 a 1.0
    # progreso dentro del stage actual: el daño aumenta a medida que se juega
    dur_total = partida["cancion"].get("duracion_loop", 1)
    meta = partida.get("meta_puntos", 0)
    if meta > 0:
        ganado = partida["puntos"] - partida.get("puntos_stage_inicio", 0)
        prog_stage = min(ganado / max(1, meta), 1.0)
    else:
        prog_stage = min(ahora / max(1, dur_total), 1.0)
    # daño efectivo: base del stage + algo de progreso del stage actual
    dano_ef = min(1.0, dano + prog_stage * (1.0 / max(1, NUM_STAGES - 1)) * 0.8)

    # vibracion extra mientras hay holds activos + temblor por daño
    hay_hold = len(partida.get("holds_activos", {})) > 0
    jitter = 0.0
    if hay_hold:
        jitter = 2.0 + len(partida["holds_activos"]) * 1.5
    # el enemigo dañado tiembla mas
    jitter += dano_ef * 6.0

    # brillo extra segun el combo: la figura se ilumina con la racha
    combo = partida.get("combo", 0)
    brillo_combo = min(combo / 30.0, 1.0)
    pulso = max(pulso, brillo_combo * 0.5)

    # REACCION DEL ENEMIGO: cuando el jugador falla, la figura se recupera
    # brevemente (brilla mas fuerte y deja de temblar por un instante).
    # Refuerza la idea de que los misses le dan fuerza al enemigo.
    ultimo_hit = partida.get("ultimo_hit") or {}
    _hit_texto = ultimo_hit.get("texto", "")
    _hit_age = ahora - ultimo_hit.get("tiempo", 0)
    if _hit_texto in ("MAL", "BOMBA") and _hit_age < 600:
        # el enemigo se fortalece cuando fallas: brilla fuerte y deja de temblar
        recuperacion = 1.0 - (_hit_age / 600.0)
        pulso = max(pulso, recuperacion * 0.9)
        jitter *= max(0.1, 1.0 - recuperacion)  # deja de temblar
        dano_ef *= max(0.3, 1.0 - recuperacion * 0.5)  # se "repara" visualmente

    cx_c = ANCHO / 2
    cy_c = (ZONA_Y) / 2 + 20
    rx = (ANCHO * 0.42) * escala
    ry = (ZONA_Y * 0.40) * escala

    techo = int(140 + brillo_combo * 90)
    boost = 50 + (30 if hay_hold else 0) + int(brillo_combo * 80)
    # el enemigo dañado vira hacia el rojo
    rojo_dano = int(dano_ef * 80)
    r = min(255, min(techo + rojo_dano, int(GRIS_FONDO[0] + pulso * boost) + rojo_dano))
    g = min(255, min(techo, max(0, int(GRIS_FONDO[1] + pulso * boost) - int(dano_ef * 20))))
    b = min(255, min(techo, max(0, int(GRIS_FONDO[2] + pulso * boost) - int(dano_ef * 20))))
    color = (max(0, r), max(0, g), max(0, b))
    base2 = min(255, max(0, int(GRIS_FONDO[0] + brillo_combo * 40)))
    color2 = (base2, base2, base2)

    puntos = _curva_fondo(tipo, liss, npts, t_anim, cx_c, cy_c, rx, ry, jitter=jitter)
    clip_ant = pantalla.get_clip()
    pantalla.set_clip(pygame.Rect(0, 0, ANCHO, ZONA_Y + 54))
    if len(puntos) > 1:
        grosor = 2 if brillo_combo >= 0.8 else 1
        if dano_ef < 0.15:
            # intacto: linea continua
            pygame.draw.lines(pantalla, color, False, puntos, grosor)
        else:
            # dañado: la linea se fragmenta, faltan segmentos (huecos crecientes)
            seg = max(2, int(8 - dano_ef * 6))   # segmentos mas cortos con mas daño
            i = 0
            rng_frag = random.Random(int(ahora / 80))  # fragmentacion que titila
            while i < len(puntos) - 1:
                # probabilidad de dibujar el segmento baja con el daño
                if rng_frag.random() > dano_ef * 0.55:
                    fin = min(i + seg, len(puntos))
                    if fin - i > 1:
                        pygame.draw.lines(pantalla, color, False, puntos[i:fin], grosor)
                i += seg
            # esquirlas que se desprenden con daño alto
            if dano_ef > 0.5:
                n_esquirlas = int(dano_ef * 12)
                for _ in range(n_esquirlas):
                    idx_p = rng_frag.randint(0, len(puntos) - 1)
                    px, py = puntos[idx_p]
                    off = int(dano_ef * 30)
                    ex = px + rng_frag.randint(-off, off)
                    ey = py + rng_frag.randint(-off, off)
                    pygame.draw.circle(pantalla, color, (ex, ey), 1)
        # figura interior (se rompe primero)
        if dano_ef < 0.6:
            puntos2 = _curva_fondo(tipo, liss, npts, -t_anim * 0.6,
                                   cx_c, cy_c, rx * 0.7, ry * 0.7, fase_extra=1.0, jitter=jitter)
            if dano_ef < 0.3:
                pygame.draw.lines(pantalla, color2, False, puntos2, 1)
            else:
                # interior fragmentado
                for i in range(0, len(puntos2) - 4, 6):
                    pygame.draw.lines(pantalla, color2, False, puntos2[i:i+4], 1)
    pantalla.set_clip(clip_ant)

# ════════════════════════════════════════════════════ >>RENDER_JUEGO<< ═══

# caches de superficies reusables (evita crear Surface por frame → GC pressure)
_flash_surf_cache = {}
_relleno_surf_cache = {}

def dibujar_juego(partida, ahora):
    num_cols  = partida["dificultad"]["columnas"]
    ancho_col = ANCHO // num_cols
    parte     = get_parte(partida, ahora)
    sx, sy    = shake_dx, shake_dy
    col_nota  = color_genero(partida)   # color de acento del genero
    zy        = partida.get("zona_y", ZONA_Y)  # zona de golpe (arriba si inverso)
    es_inv    = partida.get("es_inverso", False)

    # APAGON: fade de las NOTAS (solo notas, no fondo ni HUD) hacia negro por
    # ~500ms, cada 2-4s. La opacidad se calcula abajo antes de dibujar los
    # grupos; aca solo se actualiza el estado y se guarda el alpha en partida.
    if ("apagon" in partida.get("mods", set())
            and not partida.get("terminada") and not partida.get("game_over")):
        if "apagon_fin" not in partida:
            partida["apagon_fin"] = 0
            partida["apagon_inicio"] = 0
            partida["apagon_prox"] = ahora + random.randint(1500, 3000)
        # arrancar uno nuevo?
        if ahora >= partida["apagon_prox"] and ahora >= partida["apagon_fin"]:
            dur = random.randint(450, 700)
            partida["apagon_inicio"] = ahora
            partida["apagon_fin"] = ahora + dur
            partida["apagon_prox"] = ahora + dur + random.randint(2000, 4000)
        # calcular opacidad de las notas: fade-in ~120ms, fade-out ~180ms
        # (0.0 = totalmente invisibles, 1.0 = normales). Se lee en el loop
        # de dibujo de notas mas abajo.
        _ai = partida.get("apagon_inicio", 0)
        _af = partida.get("apagon_fin", 0)
        if ahora < _af:
            _dur_ap = max(1, _af - _ai)
            _pct = (ahora - _ai) / _dur_ap
            fade_in_pct = 120.0 / _dur_ap
            fade_out_pct = 180.0 / _dur_ap
            if _pct < fade_in_pct:
                _alpha = 1.0 - (_pct / fade_in_pct)
            elif _pct > (1.0 - fade_out_pct):
                _alpha = 1.0 - ((1.0 - _pct) / fade_out_pct)
            else:
                _alpha = 0.0
            partida["_apagon_alpha_notas"] = max(0.0, min(1.0, _alpha))
        else:
            partida["_apagon_alpha_notas"] = 1.0
    else:
        partida["_apagon_alpha_notas"] = 1.0

    # fondo procedural (figura de lissajous tenue) - el "enemigo"
    si_fondo = partida.get("stage_info")
    figura_explotada = (si_fondo and si_fondo["n"] >= NUM_STAGES and partida.get("terminada"))
    if not partida.get("game_over") and not figura_explotada:
        dibujar_fondo_lissajous(partida, ahora)

    for i in range(1, num_cols):
        pygame.draw.line(pantalla, GRIS, (i * ancho_col + sx, 0), (i * ancho_col + sx, ALTO), 1)

    # dibujar flashes de columna (surface cacheada, no crear por frame)
    global _flash_surf_cache
    for f in flashes:
        pct = f["vida"] / f["vida_max"]
        alpha = int(40 * pct * f["intensidad"])
        col_x = f["col"] * ancho_col + sx
        _key_fs = ancho_col
        if _flash_surf_cache.get("w") != _key_fs:
            _flash_surf_cache = {"w": _key_fs, "surf": pygame.Surface((ancho_col, ALTO))}
        flash_surf = _flash_surf_cache["surf"]
        flash_surf.set_alpha(alpha)
        flash_surf.fill(col_nota)
        pantalla.blit(flash_surf, (col_x, 0))

    # linea de hit (se mueve con inverso)
    pygame.draw.line(pantalla, col_nota, (sx, zy + sy), (ANCHO + sx, zy + sy), 2)

    # CLIP: las notas se cortan al pasar la zona de hit.
    # En normal: notas vienen de arriba, se clipean ARRIBA de la zona de labels.
    # En inverso: notas vienen de abajo, se clipean DEBAJO de la zona de labels
    #   (les damos 36px extra para que crucen la linea y entren a la zona,
    #    así el jugador las ve "llegar" antes de desaparecer).
    clip_anterior = pantalla.get_clip()
    if es_inv:
        pantalla.set_clip(pygame.Rect(0, zy - 36, ANCHO, ALTO - zy + 36))
    else:
        pantalla.set_clip(pygame.Rect(0, 0, ANCHO, zy))

    es_invisible = "invisible" in partida.get("mods", set())
    es_niebla = "niebla" in partida.get("mods", set())
    es_monocromo = "monocromo" in partida.get("mods", set())
    # alpha del apagon (0..1, aplicado como multiplicador al color de las notas)
    apagon_a = partida.get("_apagon_alpha_notas", 1.0)
    for grupo in partida["notas_cayendo"]:
        # modificador INVISIBLE: las notas se ven al principio y desaparecen al caer
        if es_invisible:
            if es_inv and grupo["y"] < zy + (ALTO - zy) * 0.45:
                continue
            elif not es_inv and grupo["y"] > zy * 0.45:
                continue
        # modificador NIEBLA: las notas aparecen GRADUALMENTE (fade-in) desde la
        # mitad de la pantalla hacia la zona de golpe. Antes de la mitad son
        # invisibles; entre la mitad y la zona su opacidad sube de 0 a 1.
        alpha_niebla = 1.0
        if es_niebla:
            if es_inv:
                # notas suben: mitad de la zona inferior -> zona de golpe (arriba)
                mitad = zy + (ALTO - zy) * 0.5
                if grupo["y"] > mitad:
                    continue  # aun por debajo de la mitad: invisible
                # fade de 0 (en la mitad) a 1 (en la zona de golpe)
                rango = mitad - zy
                alpha_niebla = 1.0 - max(0.0, (grupo["y"] - zy) / max(1, rango))
            else:
                # notas caen: mitad de la pantalla -> zona de golpe (abajo)
                mitad = zy * 0.5
                if grupo["y"] < mitad:
                    continue  # aun por encima de la mitad: invisible
                # fade de 0 (en la mitad) a 1 (en la zona de golpe)
                rango = zy - mitad
                alpha_niebla = min(1.0, (grupo["y"] - mitad) / max(1, rango))
        pendientes = [c for c in grupo["cols"] if c not in grupo.get("acertadas", set())]
        cols_hold_activo = [c for c in grupo["cols"] if c in partida["holds_activos"]]
        cols_a_dibujar = list(set(pendientes + cols_hold_activo))
        xs = []
        hold_h = grupo.get("hold_px", 0)
        gy = grupo["y"] + sy
        for col in cols_a_dibujar:
            x = col * ancho_col + sx
            if hold_h > 0:
                bar_x = x + ancho_col // 2 - 6
                if es_inv:
                    bar_y = gy + 28   # barra se extiende hacia abajo
                    # recortar: no dibujar por encima de la zona de labels
                    limite_sup = zy + 2
                    bar_end = bar_y + hold_h
                    if bar_y < limite_sup:
                        bar_y = limite_sup
                    bar_h = max(0, bar_end - bar_y)
                else:
                    bar_y = gy - hold_h  # barra se extiende hacia arriba
                    bar_h = hold_h
                if bar_h <= 0:
                    pass  # cola ya consumida, no dibujar
                elif col in partida["holds_activos"]:
                    # barra que oscila: dibujada por segmentos con desplazamiento senoidal
                    fase = pygame.time.get_ticks() * 0.012
                    seg = 6
                    cx_bar = x + ancho_col // 2
                    pasos = max(2, int(bar_h) // seg)
                    for k in range(pasos):
                        yy = bar_y + k * seg
                        prog = k / pasos
                        amp = 7 * prog
                        ox = math.sin(fase + k * 0.5) * amp
                        pygame.draw.rect(pantalla, GRIS_MED, (int(cx_bar + ox - 8), yy, 16, seg + 1))
                        pygame.draw.rect(pantalla, BLANCO, (int(cx_bar + ox - 5), yy, 10, seg + 1))
                else:
                    pygame.draw.rect(pantalla, GRIS_MED, (bar_x, bar_y, 12, bar_h))
                    pygame.draw.rect(pantalla, BLANCO, (bar_x, bar_y, 12, bar_h), 1)
            if col in pendientes:
                # aplicar fade combinado: niebla (distancia) + apagon (tiempo)
                alpha_total = alpha_niebla * apagon_a
                if alpha_total < 1.0:
                    cn = (int(col_nota[0] * alpha_total),
                          int(col_nota[1] * alpha_total),
                          int(col_nota[2] * alpha_total))
                else:
                    cn = col_nota
                # power-up: nota especial con animacion propia por tipo
                pu_id = grupo.get("power_up")
                if pu_id and es_monocromo:
                    # MONOCROMO: el power-up se disfraza de nota comun, sin
                    # pista visual de que tipo es (ni siquiera de que ES uno)
                    pygame.draw.rect(pantalla, cn, (x + 6, gy, ancho_col - 12, 28))
                elif pu_id:
                    _mt = math
                    pu_def = next((p for p in POWER_UPS if p["id"] == pu_id), None)
                    pc = pu_def["color"] if pu_def else BLANCO
                    t_anim = ahora_ms / 1000.0
                    nota_h = 40
                    ny = gy - 6
                    ccx = x + ancho_col // 2          # centro X de la nota
                    ccy = int(ny + nota_h // 2)       # centro Y
                    brill = (0.75 + 0.25 * _mt.sin(t_anim * 6.0)) * apagon_a
                    cn = (int(pc[0] * brill), int(pc[1] * brill), int(pc[2] * brill))
                    # borde blanco tambien se atenua con el apagon
                    borde_pu = (int(255 * apagon_a),) * 3

                    if pu_id == "estrella":
                        # AUTO: rayos giratorios (aura de invencibilidad)
                        for ri in range(6):
                            ang = t_anim * 3.0 + ri * (6.2832 / 6)
                            x1 = ccx + _mt.cos(ang) * (ancho_col // 2 - 2)
                            y1 = ccy + _mt.sin(ang) * (nota_h // 2 + 6)
                            x2 = ccx + _mt.cos(ang) * (ancho_col // 2 + 10)
                            y2 = ccy + _mt.sin(ang) * (nota_h // 2 + 18)
                            pygame.draw.line(pantalla, cn, (x1, y1), (x2, y2), 3)
                        pygame.draw.rect(pantalla, cn, (x + 2, ny, ancho_col - 4, nota_h))
                        pygame.draw.rect(pantalla, borde_pu, (x + 2, ny, ancho_col - 4, nota_h), 2)

                    elif pu_id == "vida":
                        # +HP: latido de corazon (doble pulso ritmico "tu-tum")
                        fase = (t_anim * 1.4) % 1.0
                        pulso = 0.0
                        if fase < 0.12:
                            pulso = _mt.sin(fase / 0.12 * 3.1416)
                        elif 0.20 <= fase < 0.32:
                            pulso = 0.7 * _mt.sin((fase - 0.20) / 0.12 * 3.1416)
                        exp = int(6 * pulso)
                        pygame.draw.rect(pantalla, cn,
                                         (x + 2 - exp, ny - exp,
                                          ancho_col - 4 + exp * 2, nota_h + exp * 2))
                        pygame.draw.rect(pantalla, borde_pu,
                                         (x + 2 - exp, ny - exp,
                                          ancho_col - 4 + exp * 2, nota_h + exp * 2), 2)

                    elif pu_id == "reloj":
                        # SLOW: aguja de reloj girando LENTA + anillo
                        pygame.draw.rect(pantalla, cn, (x + 2, ny, ancho_col - 4, nota_h))
                        pygame.draw.rect(pantalla, borde_pu, (x + 2, ny, ancho_col - 4, nota_h), 2)
                        rad = min(ancho_col // 2 - 8, nota_h // 2 + 8)
                        pygame.draw.circle(pantalla, borde_pu, (ccx, ccy), rad, 2)
                        ang_ag = t_anim * 1.2  # giro lento = el efecto que da
                        ax = ccx + _mt.cos(ang_ag - 1.5708) * (rad - 3)
                        ay = ccy + _mt.sin(ang_ag - 1.5708) * (rad - 3)
                        pygame.draw.line(pantalla, NEGRO, (ccx, ccy), (ax, ay), 3)

                    elif pu_id == "doble":
                        # x2: nota fantasma que se separa y vuelve (duplicacion)
                        sep = int(abs(_mt.sin(t_anim * 2.5)) * 14)
                        # fantasma desplazado (mas oscuro)
                        cf = (pc[0] // 2, pc[1] // 2, pc[2] // 2)
                        pygame.draw.rect(pantalla, cf,
                                         (x + 2 + sep, ny - sep // 2, ancho_col - 4, nota_h))
                        # nota principal
                        pygame.draw.rect(pantalla, cn, (x + 2, ny, ancho_col - 4, nota_h))
                        pygame.draw.rect(pantalla, borde_pu, (x + 2, ny, ancho_col - 4, nota_h), 2)

                    else:
                        pygame.draw.rect(pantalla, cn, (x + 2, ny, ancho_col - 4, nota_h))
                        pygame.draw.rect(pantalla, borde_pu, (x + 2, ny, ancho_col - 4, nota_h), 2)

                    # label centrado (comun a todos)
                    iconos_pu = {"estrella": "AUTO", "vida": "+HP", "reloj": "SLOW", "doble": "x2"}
                    pu_lbl = fuente.render(iconos_pu.get(pu_id, "?"), True, NEGRO)
                    pantalla.blit(pu_lbl, (ccx - pu_lbl.get_width() // 2,
                                           ccy - pu_lbl.get_height() // 2))
                elif grupo.get("es_bomba"):
                    # BOMBA: rojo intenso con parpadeo y simbolo X centrado.
                    # Bajo MONOCROMO: se disfraza el CUERPO (color normal, sin
                    # parpadeo ni borde blanco alarmante) pero la X blanca
                    # centrada se mantiene: la X es la unica pista de peligro
                    # y sin eso el jugador no tendria forma de evitarla.
                    _blco_ap = (int(255 * apagon_a),) * 3
                    _cx = x + ancho_col // 2
                    _cy = gy + 14
                    _r = 8
                    if es_monocromo:
                        # cuerpo como nota comun (color del genero, sin marca)
                        pygame.draw.rect(pantalla, cn, (x + 6, gy, ancho_col - 12, 28))
                    else:
                        _tb = ahora_ms / 1000.0
                        _pulso = (0.6 + 0.4 * math.sin(_tb * 10.0)) * apagon_a
                        _rojo = (int(255 * _pulso), int(40 * _pulso), int(40 * _pulso))
                        pygame.draw.rect(pantalla, _rojo, (x + 4, gy - 4, ancho_col - 8, 36))
                        _grosor = 2 if _pulso > 0.75 else 3
                        pygame.draw.rect(pantalla, _blco_ap, (x + 4, gy - 4, ancho_col - 8, 36), _grosor)
                    # X central (siempre visible, con o sin MONOCROMO)
                    pygame.draw.line(pantalla, _blco_ap, (_cx - _r, _cy - _r), (_cx + _r, _cy + _r), 3)
                    pygame.draw.line(pantalla, _blco_ap, (_cx + _r, _cy - _r), (_cx - _r, _cy + _r), 3)
                elif grupo.get("es_acorde") and not es_monocromo:
                    pygame.draw.rect(pantalla, cn, (x + 6,  gy,     ancho_col - 12, 28))
                    pygame.draw.rect(pantalla, NEGRO,  (x + 9,  gy + 3, ancho_col - 18, 22))
                    pygame.draw.rect(pantalla, cn, (x + 11, gy + 5, ancho_col - 22, 18))
                else:
                    pygame.draw.rect(pantalla, cn, (x + 6, gy, ancho_col - 12, 28))
            xs.append(x + ancho_col // 2)
        if len(xs) > 1:
            _col_link = (int(col_nota[0] * apagon_a),
                         int(col_nota[1] * apagon_a),
                         int(col_nota[2] * apagon_a)) if apagon_a < 1.0 else col_nota
            pygame.draw.line(pantalla, _col_link, (xs[0], gy + 14), (xs[-1], gy + 14), 2)

    pantalla.set_clip(clip_anterior)

    # labels del jugador — en inverso van ARRIBA de la linea (notas vienen de abajo)
    if es_inv:
        label_y0 = zy - 36  # labels arriba de la linea
    else:
        label_y0 = zy + 2   # labels debajo de la linea (normal)
    pygame.draw.line(pantalla, BLANCO, (sx, label_y0 + 32 + sy), (ANCHO + sx, label_y0 + 32 + sy), 1)
    mt = partida.get("mapa_teclas", {})
    inv_teclas = {}
    for tecla_pos, col_dest in mt.items():
        inv_teclas[col_dest] = tecla_pos

    # AUTO activo: el juego toca solo, no hace falta tocar nada
    auto_activo = ahora < partida.get("efectos_activos", {}).get("estrella", 0)

    # ASISTENCIA VISUAL (niveles faciles): iluminar la tecla segun la POSICION
    # VISUAL de la nota (grupo["y"]), no su tiempo — asi queda perfectamente
    # sincronizada con lo que se ve, con cualquier velocidad o mod.
    asistencia = partida["dificultad"].get("nivel", 1) <= 2 and not auto_activo
    asist_cols = {}   # col -> intensidad 0..1 (1 = apreta ya)
    if asistencia:
        RANGO_PX = 140.0   # px antes de la linea donde empieza a iluminarse
        for grupo in partida["notas_cayendo"]:
            gy_a = grupo.get("y")
            if gy_a is None:
                continue
            # distancia visual a la linea de golpe (positiva = todavia no llego)
            # en inverso el borde delantero es el bottom del rect (+28)
            dist_px = (gy_a + 28 - zy) if es_inv else (zy - gy_a)
            if -30 < dist_px <= RANGO_PX:
                inten = 1.0 - max(0, dist_px) / RANGO_PX
                for c_a in grupo["cols"]:
                    asist_cols[c_a] = max(asist_cols.get(c_a, 0), inten)

    for i in range(num_cols):
        x = i * ancho_col + sx
        if auto_activo:
            # tecla BLANCA = no hace falta tocarla (el juego toca solo)
            pygame.draw.rect(pantalla, BLANCO, (x + 2, label_y0 + sy, ancho_col - 4, 32))
        elif i in asist_cols:
            # asistencia: relleno del color del genero con intensidad creciente
            inten = asist_cols[i]
            ca = (int(col_nota[0] * inten), int(col_nota[1] * inten), int(col_nota[2] * inten))
            pygame.draw.rect(pantalla, ca, (x + 2, label_y0 + sy, ancho_col - 4, 32))
            if inten > 0.85:
                # "AHORA": borde blanco fuerte
                pygame.draw.rect(pantalla, BLANCO, (x + 2, label_y0 + sy, ancho_col - 4, 32), 3)
        if i in teclas_sostenidas and not auto_activo:
            pygame.draw.rect(pantalla, GRIS, (x + 2, label_y0 + sy, ancho_col - 4, 32))
        if auto_activo:
            col_activa = NEGRO   # label negro sobre tecla blanca
        elif i in teclas_sostenidas:
            col_activa = BLANCO
        elif i in asist_cols and asist_cols[i] > 0.5:
            col_activa = BLANCO  # label visible sobre el relleno de asistencia
        else:
            col_activa = GRIS_MED
        tecla_idx = inv_teclas.get(i, i)
        label = fuente_chica.render(LABELS[tecla_idx], True, col_activa)
        pantalla.blit(label, (x + ancho_col // 2 - label.get_width() // 2, label_y0 + 8 + sy))

    # indicador de precision (semaforo): borde de color en la columna tocada
    for ind in indicadores_hit:
        pct = ind["vida"] / ind["vida_max"]
        col_idx = ind["col_idx"]
        if col_idx >= num_cols:
            continue
        x = col_idx * ancho_col + sx
        cbase = ind["color"]
        # el color arranca pleno y se atenua
        cy = (int(cbase[0] * pct), int(cbase[1] * pct), int(cbase[2] * pct))
        # relleno tenue + borde brillante alrededor de la celda de la tecla
        # (surface cacheada por tamaño, no crear por frame)
        global _relleno_surf_cache
        rect_cel = (x + 2, label_y0 + sy, ancho_col - 4, 32)
        _key_rs = ancho_col - 4
        if _relleno_surf_cache.get("w") != _key_rs:
            _relleno_surf_cache = {"w": _key_rs, "surf": pygame.Surface((_key_rs, 32))}
        relleno = _relleno_surf_cache["surf"]
        relleno.set_alpha(int(90 * pct))
        relleno.fill(cbase)
        pantalla.blit(relleno, (x + 2, label_y0 + sy))
        grosor = max(2, int(4 * pct))
        pygame.draw.rect(pantalla, cy, rect_cel, grosor)

    # === HUD MINIMALISTA: solo lo esencial de gameplay ===
    # IZQUIERDA: nombre del enemigo (la figura del fondo)
    _liss = partida["cancion"].get("lissajous", {})
    _nombre_enem = _liss.get("nombre", "???")
    _si_hud = partida.get("stage_info")
    _st_n = _si_hud["n"] if _si_hud else 1
    _dano_hud = (_st_n - 1) / max(1, NUM_STAGES - 1)
    # el nombre tiembla y se opaca conforme se daña
    _ne_alpha = max(80, int(255 * (1.0 - _dano_hud * 0.6)))
    _ne_col = (min(255, 100 + int(_dano_hud * 155)), max(0, 100 - int(_dano_hud * 60)),
               max(0, 100 - int(_dano_hud * 60)))
    _ne_txt = fuente_chica.render(_nombre_enem, True, _ne_col)
    _ne_txt.set_alpha(_ne_alpha)
    _ne_x = 12
    _ne_y = 8
    if _dano_hud > 0.5:
        _ne_x += random.randint(-1, 1)
        _ne_y += random.randint(-1, 1)
    pantalla.blit(_ne_txt, (_ne_x, _ne_y))

    # CENTRO: puntos + combo
    pts = fuente.render(str(partida["puntos"]).zfill(6), True, BLANCO)
    pantalla.blit(pts, (ANCHO // 2 - pts.get_width() // 2, 10))
    if partida["combo"] >= 5:
        combo_txt = fuente.render(f"{partida['combo']}x", True, col_nota)
        pantalla.blit(combo_txt, (ANCHO // 2 - combo_txt.get_width() // 2, 36))

    # DERECHA: barra de vida + barra de meta
    vida_w = 160
    vida_x = ANCHO - vida_w - 10
    vida_y = 14
    vida_pct = partida["vida"] / partida["vida_max"]
    pygame.draw.rect(pantalla, GRIS, (vida_x, vida_y, vida_w, 8))
    if vida_pct > 0:
        color_vida = BLANCO if vida_pct > 0.3 else GRIS_MED
        pygame.draw.rect(pantalla, color_vida, (vida_x, vida_y, int(vida_w * vida_pct), 8))
    pygame.draw.rect(pantalla, BLANCO, (vida_x, vida_y, vida_w, 8), 1)
    vida_lbl = fuente_chica.render("HP", True, GRIS)
    pantalla.blit(vida_lbl, (vida_x - vida_lbl.get_width() - 4, vida_y - 2))

    meta = partida.get("meta_puntos", 0)
    if meta > 0:
        ganado = partida["puntos"] - partida.get("puntos_stage_inicio", 0)
        meta_pct = min(1.0, ganado / max(1, meta))
        meta_y = 28
        pygame.draw.rect(pantalla, GRIS, (vida_x, meta_y, vida_w, 8))
        if meta_pct > 0:
            pygame.draw.rect(pantalla, col_nota, (vida_x, meta_y, int(vida_w * meta_pct), 8))
        pygame.draw.rect(pantalla, BLANCO, (vida_x, meta_y, vida_w, 8), 1)
        meta_txt = fuente_chica.render(f"{ganado}/{meta}", True, GRIS_MED)
        pantalla.blit(meta_txt, (vida_x - meta_txt.get_width() - 4, meta_y - 2))

    # instrumento actual: icono identitario + nombre (discreto, derecha)
    inst_nombre = partida["cancion"].get("instrumento", "")
    if inst_nombre:
        inst_txt = fuente_chica.render(inst_nombre, True, GRIS_MED)
        inst_y = 44
        pantalla.blit(inst_txt, (ANCHO - inst_txt.get_width() - 10, inst_y))
        forma_inst = forma_de_instrumento(inst_nombre)
        dibujar_icono_inst(pantalla, forma_inst,
                           ANCHO - inst_txt.get_width() - 26, inst_y + 7, 8, col_nota)

    # IZQUIERDA: stage + escudo + efectos temporales
    si = partida.get("stage_info")
    if si:
        st_txt = fuente_chica.render(f"STAGE {si['n']}/{NUM_STAGES}", True, col_nota)
        pantalla.blit(st_txt, (10, 12))
    cargas = partida.get("escudo_cargas", 0)
    if cargas > 0:
        esc_c = fuente_chica.render(f"ESCUDO x{cargas}", True, (100, 200, 255))
        pantalla.blit(esc_c, (10, 30))
    efectos = partida.get("efectos_activos", {})
    ey = 50
    for eid, t_fin in list(efectos.items()):
        restante = max(0, t_fin - ahora)
        if restante <= 0:
            continue
        pu_def = next((pu for pu in POWER_UPS if pu["id"] == eid), None)
        if not pu_def:
            continue
        colr = pu_def["color"]
        if restante < 2000 and (pygame.time.get_ticks() // 200) % 2 == 0:
            colr = GRIS
        etxt = fuente_chica.render(f"{pu_def['nombre']} {restante/1000:.1f}s", True, colr)
        pantalla.blit(etxt, (10, ey))
        ey += 18

    # evento activo (aviso puntual, centro)
    ev_act = partida.get("evento_activo")
    if ev_act:
        nombres_ev = {
            "silencio_drums": "! SILENCIO !",
            "solo_drums": "! SOLO DRUMS !",
            "stutter": "! STUTTER !",
            "boost_bajo": "! BASS DROP !",
            "freeze_mel": "! FREEZE !",
        }
        ev_txt = fuente_chica.render(nombres_ev.get(ev_act, ""), True, BLANCO)
        pantalla.blit(ev_txt, (ANCHO // 2 - ev_txt.get_width() // 2, 58))
    # texto guia durante la practica del tutorial
    if partida.get("es_tutorial") and not partida.get("terminada"):
        guia = fuente_chica.render("PRACTICA: TOCA LA TECLA CUANDO LA NOTA CRUZA LA LINEA", True, (255, 180, 60))
        pantalla.blit(guia, (ANCHO // 2 - guia.get_width() // 2, 70))
        guia2 = fuente_chica.render("NO PODES PERDER - LLEGA A 60 PUNTOS", True, GRIS_MED)
        pantalla.blit(guia2, (ANCHO // 2 - guia2.get_width() // 2, 90))
    esc_txt = fuente_chica.render("ESC", True, GRIS)
    pantalla.blit(esc_txt, (10, ALTO - 20))

    if dev_mode:
        dev_txt = fuente_chica.render("DEV x2  |  NO DMG", True, BLANCO)
        pantalla.blit(dev_txt, (ANCHO // 2 - dev_txt.get_width() // 2, ALTO - 20))

    hit = partida.get("ultimo_hit")
    if hit and pygame.time.get_ticks() - hit["tiempo"] < 500:
        color = BLANCO if hit["texto"] in ["PERFECTO", "BIEN"] else GRIS_MED
        hit_txt = fuente.render(hit["texto"], True, color)
        hit_y = zy + 10 if es_inv else zy - 60
        pantalla.blit(hit_txt, (ANCHO // 2 - hit_txt.get_width() // 2, hit_y))

    if partida.get("game_over"):
        # --- ANIMACION DE MUERTE ---
        # t=0: flash rojo fuerte que se desvanece en 500ms
        # t=200-700: "GAME OVER" cae desde arriba con rebote (ease-out-bounce)
        # t=700+: stats y controles aparecen con fade-in escalonado
        go_t = pygame.time.get_ticks() - partida.get("game_over_t", 0)

        # flash rojo inicial (500ms de decaimiento)
        if go_t < 500:
            alpha_flash = int(110 * (1.0 - go_t / 500.0))
            flash_s = pygame.Surface((ANCHO, ALTO))
            flash_s.set_alpha(alpha_flash)
            flash_s.fill((255, 30, 30))
            pantalla.blit(flash_s, (0, 0))

        # GAME OVER cae desde arriba con rebote
        y_final = ALTO // 2 - 50
        t_caida = max(0.0, min(1.0, (go_t - 200) / 500.0))
        if t_caida <= 0:
            go_y = -80
        else:
            # ease-out-bounce simplificado: cae, rebota una vez, asienta
            n1, d1 = 7.5625, 2.75
            tb = t_caida
            if tb < 1 / d1:
                b = n1 * tb * tb
            elif tb < 2 / d1:
                tb -= 1.5 / d1
                b = n1 * tb * tb + 0.75
            elif tb < 2.5 / d1:
                tb -= 2.25 / d1
                b = n1 * tb * tb + 0.9375
            else:
                tb -= 2.625 / d1
                b = n1 * tb * tb + 0.984375
            go_y = int(-80 + (y_final + 80) * b)
        # temblor sutil los primeros 800ms (la pantalla "acusa el golpe")
        gx_shake = random.randint(-2, 2) if go_t < 800 else 0
        go_txt = fuente_grande.render("GAME OVER", True, (255, 80, 80) if go_t < 800 else BLANCO)
        pantalla.blit(go_txt, (ANCHO // 2 - go_txt.get_width() // 2 + gx_shake, go_y))

        # nombre del enemigo que te mato (aparece con fade despues del titulo)
        _enem_n = partida["cancion"].get("lissajous", {}).get("nombre", "???")
        _enem_txt = fuente_chica.render(f"DERROTADO POR {_enem_n}", True, (255, 100, 100))
        if go_t > 500:
            _ea = min(255, int(255 * (go_t - 500) / 400.0))
            _enem_txt.set_alpha(_ea)
            pantalla.blit(_enem_txt, (ANCHO // 2 - _enem_txt.get_width() // 2, go_y + 55))

        # stats y controles: fade-in escalonado despues de que aterriza el texto
        def _blit_fade(surf, x, y, t_aparece):
            if go_t < t_aparece:
                return
            alpha = min(255, int(255 * (go_t - t_aparece) / 300.0))
            surf.set_alpha(alpha)
            pantalla.blit(surf, (x, y))
        sc_txt = fuente.render(f"PUNTOS: {partida['puntos']}  MAX COMBO: {partida['max_combo']}x", True, GRIS_MED)
        _blit_fade(sc_txt, ANCHO // 2 - sc_txt.get_width() // 2, ALTO // 2 + 30, 750)
        if run_actual is not None:
            esc2 = fuente_chica.render("ESPACIO = RESULTADO DEL RUN", True, GRIS)
        else:
            esc2 = fuente_chica.render("ESC PARA VOLVER", True, GRIS)
        _blit_fade(esc2, ANCHO // 2 - esc2.get_width() // 2, ALTO // 2 + 70, 950)
        ruta = partida.get("export_ruta")
        if ruta:
            ok_txt = fuente_chica.render("GUARDADA EN export/", True, BLANCO)
            _blit_fade(ok_txt, ANCHO // 2 - ok_txt.get_width() // 2, ALTO // 2 + 95, 950)
        elif partida.get("exportando"):
            ex_txt = fuente_chica.render("GUARDANDO...", True, GRIS_MED)
            _blit_fade(ex_txt, ANCHO // 2 - ex_txt.get_width() // 2, ALTO // 2 + 95, 950)
        else:
            dl_txt = fuente_chica.render("D = DESCARGAR CANCION", True, BLANCO)
            _blit_fade(dl_txt, ANCHO // 2 - dl_txt.get_width() // 2, ALTO // 2 + 95, 950)

    elif partida["terminada"] and not partida["notas_cayendo"]:
        col_g = COLOR_GENERO.get(partida["cancion"].get("genero", ""), BLANCO)
        meta = partida.get("meta_puntos", 0)
        if partida.get("es_tutorial"):
            fin = fuente.render("TUTORIAL COMPLETADO!", True, col_g)
        elif meta > 0:
            _enem_n_fin = partida["cancion"].get("lissajous", {}).get("nombre", "???")
            _si_fin = partida.get("stage_info")
            _st_fin = _si_fin["n"] if _si_fin else 1
            if _st_fin >= NUM_STAGES and run_actual is not None:
                fin = fuente.render(f"{_enem_n_fin} DESTRUIDO!", True, col_g)
            else:
                fin = fuente.render(f"{_enem_n_fin} DAÑADO!", True, col_g)
        else:
            fin = fuente.render("FIN", True, BLANCO)
        pantalla.blit(fin, (ANCHO // 2 - fin.get_width() // 2, ALTO // 2 - 40))
        if run_actual is not None:
            ganado = partida["puntos"] - partida.get("puntos_stage_inicio", 0)
            sc_txt = fuente.render(f"STAGE: +{ganado}   TOTAL: {partida['puntos']}", True, GRIS_MED)
            pantalla.blit(sc_txt, (ANCHO // 2 - sc_txt.get_width() // 2, ALTO // 2))
            cb_txt = fuente_chica.render(f"MAX COMBO: {partida['max_combo']}x", True, GRIS)
            pantalla.blit(cb_txt, (ANCHO // 2 - cb_txt.get_width() // 2, ALTO // 2 + 30))
        else:
            sc_txt = fuente.render(f"PUNTOS: {partida['puntos']}  MAX COMBO: {partida['max_combo']}x", True, GRIS_MED)
            pantalla.blit(sc_txt, (ANCHO // 2 - sc_txt.get_width() // 2, ALTO // 2))
        # texto de accion: ESPACIO O auto-avance
        if run_actual is not None:
            stage_n = run_actual["stage"]
            _t_win = pygame.time.get_ticks() - partida.get("terminada_t", 0)
            _auto_en = max(0, 5 - _t_win // 1000)
            if stage_n < NUM_STAGES:
                esc2 = fuente.render(f"ESPACIO = SIGUIENTE STAGE  ({_auto_en}s)", True, BLANCO)
            else:
                esc2 = fuente.render(f"ESPACIO = COMPLETAR RUN!  ({_auto_en}s)", True, BLANCO)
        else:
            esc2 = fuente.render("ESC PARA VOLVER", True, BLANCO)
        pantalla.blit(esc2, (ANCHO // 2 - esc2.get_width() // 2, ALTO // 2 + 62))
        # estado de exportacion (debajo, con margen suficiente)
        ruta = partida.get("export_ruta")
        if ruta:
            ok_txt = fuente_chica.render("GUARDADA EN export/", True, BLANCO)
            pantalla.blit(ok_txt, (ANCHO // 2 - ok_txt.get_width() // 2, ALTO // 2 + 92))
        elif partida.get("exportando"):
            ex_txt = fuente_chica.render("GUARDANDO...", True, GRIS_MED)
            pantalla.blit(ex_txt, (ANCHO // 2 - ex_txt.get_width() // 2, ALTO // 2 + 92))
        else:
            dl_txt = fuente_chica.render("D = DESCARGAR CANCION", True, BLANCO)
            pantalla.blit(dl_txt, (ANCHO // 2 - dl_txt.get_width() // 2, ALTO // 2 + 92))

# ═══════════════════════════════════════════════════════ >>PANTALLAS<< ═══

TUTORIAL_NUM_PAGINAS = 9
tutorial_pagina = 0

def dibujar_tutorial(pagina):
    """Tutorial de 9 paginas con graficos en vivo."""
    pantalla.fill(NEGRO)
    t_anim = pygame.time.get_ticks() / 1000.0
    cx = ANCHO // 2

    titulos = ["COMO JUGAR", "NOTAS", "HOLDS Y ACORDES", "VIDA Y COMBO",
               "POWER-UPS", "BOMBAS", "PERKS", "MODIFICADORES", "MODOS DE JUEGO"]
    titulo = fuente_grande.render(titulos[pagina], True, BLANCO)
    pantalla.blit(titulo, (cx - titulo.get_width() // 2, 36))
    pygame.draw.line(pantalla, GRIS, (60, 96), (ANCHO - 60, 96), 1)

    def linea(texto, y, color=GRIS_MED, f=None):
        f = f or fuente_chica
        txt = f.render(texto, True, color)
        pantalla.blit(txt, (cx - txt.get_width() // 2, y))

    if pagina == 0:
        # COMO JUGAR
        linea("CADA STAGE TIENE UNA META DE PUNTOS", 125, BLANCO, fuente)
        linea("LA CANCION SE REPITE HASTA QUE LA ALCANCES", 160)
        linea("(O HASTA QUE TE QUEDES SIN VIDA)", 180)
        bar_w, bar_x, bar_y = 360, cx - 180, 235
        prog = (math.sin(t_anim * 0.8) * 0.5 + 0.5)
        pygame.draw.rect(pantalla, GRIS, (bar_x, bar_y, bar_w, 16))
        pygame.draw.rect(pantalla, (255, 180, 60), (bar_x, bar_y, int(bar_w * prog), 16))
        pygame.draw.rect(pantalla, BLANCO, (bar_x, bar_y, bar_w, 16), 1)
        linea(f"{int(prog*325)}/325", 260, GRIS_MED)
        linea("LA FIGURA DEL FONDO ES TU ENEMIGO", 310, BLANCO)
        linea("SE DANA CON TU COMBO Y SE RECUPERA SI FALLAS", 335)
        linea("UN RUN SON 4 STAGES: LA META CRECE EN CADA UNO", 375, (255, 180, 60))
        linea("TECLAS: A S D F G H J K (SEGUN COLUMNAS)", 420, BLANCO)
        linea("ESC = PAUSAR DURANTE EL JUEGO", 445)

    elif pagina == 1:
        # NOTAS
        linea("LAS NOTAS CAEN POR COLUMNAS", 125, BLANCO, fuente)
        linea("APRETA LA TECLA CUANDO LA NOTA CRUZA LA LINEA", 160)
        demo_x, demo_y, demo_w, demo_h = cx - 150, 195, 300, 190
        col_w = demo_w // 3
        for i in range(1, 3):
            pygame.draw.line(pantalla, GRIS, (demo_x + i * col_w, demo_y), (demo_x + i * col_w, demo_y + demo_h), 1)
        pygame.draw.rect(pantalla, GRIS, (demo_x, demo_y, demo_w, demo_h), 1)
        linea_y = demo_y + demo_h - 40
        pygame.draw.line(pantalla, (255, 180, 60), (demo_x, linea_y), (demo_x + demo_w, linea_y), 2)
        fall = (t_anim * 0.5) % 1.0
        ny = demo_y + 10 + fall * (linea_y - demo_y - 20)
        pygame.draw.rect(pantalla, BLANCO, (demo_x + col_w + 8, ny, col_w - 16, 20))
        for i, lbl in enumerate(["A", "S", "D"]):
            l = fuente_chica.render(lbl, True, GRIS_MED)
            pantalla.blit(l, (demo_x + i * col_w + col_w // 2 - l.get_width() // 2, linea_y + 12))
        linea("PRECISION:", 395, BLANCO)
        linea("PERFECTO > BIEN > OK > MAL (rompe combo)", 417)
        linea("APRETAR SIN NOTA CERCA: -1 PUNTO", 439, GRIS)
        linea("EN FACIL LA TECLA SE ILUMINA CUANDO HAY QUE APRETAR", 465, (255, 180, 60))

    elif pagina == 2:
        # HOLDS Y ACORDES
        linea("NOTA LARGA (HOLD): MANTENE LA TECLA APRETADA", 130, BLANCO, fuente)
        hx = cx - 130
        pygame.draw.rect(pantalla, GRIS_MED, (hx - 6, 170, 12, 90))
        pygame.draw.rect(pantalla, BLANCO, (hx - 6, 170, 12, 90), 1)
        pygame.draw.rect(pantalla, BLANCO, (hx - 30, 260, 60, 22))
        linea2 = fuente_chica.render("MANTENE HASTA QUE LA BARRA TERMINE (+3 PTS)", True, GRIS_MED)
        pantalla.blit(linea2, (cx - 60, 215))
        linea("ACORDE: VARIAS COLUMNAS AL MISMO TIEMPO", 320, BLANCO, fuente)
        ax = cx - 110
        for i in range(3):
            x = ax + i * 80
            pygame.draw.rect(pantalla, BLANCO, (x, 360, 56, 22))
            pygame.draw.rect(pantalla, NEGRO, (x + 4, 364, 48, 14))
            pygame.draw.rect(pantalla, BLANCO, (x + 7, 367, 42, 8))
        pygame.draw.line(pantalla, BLANCO, (ax + 28, 371), (ax + 188, 371), 2)
        linea("APRETA TODAS LAS TECLAS CONECTADAS A LA VEZ", 400)
        linea("LOS ACORDES DAN PUNTOS POR CADA NOTA", 425)

    elif pagina == 3:
        # VIDA Y COMBO
        linea("VIDA: CADA NOTA QUE SE PASA TE RESTA 2 DE VIDA", 130, BLANCO, fuente)
        pygame.draw.rect(pantalla, GRIS, (cx - 100, 165, 200, 10))
        hp = (math.sin(t_anim) * 0.3 + 0.6)
        pygame.draw.rect(pantalla, BLANCO, (cx - 100, 165, int(200 * hp), 10))
        pygame.draw.rect(pantalla, BLANCO, (cx - 100, 165, 200, 10), 1)
        linea("MISS = -2 VIDA (NO RESTA PUNTOS)", 190, GRIS_MED)
        linea("SI LA VIDA LLEGA A CERO: GAME OVER", 210)
        linea("COMBO: HITS SEGUIDOS SIN FALLAR", 270, BLANCO, fuente)
        combo_n = int((t_anim * 4) % 30) + 1
        ctxt = fuente.render(f"{combo_n}x COMBO", True, (255, 180, 60))
        pantalla.blit(ctxt, (cx - ctxt.get_width() // 2, 305))
        linea("CADA 5 DE COMBO SUBE EL MULTIPLICADOR DE PUNTOS", 345)
        linea("UN MISS ROMPE EL COMBO (SALVO CON EL PERK COMBO SAVE)", 370)
        linea("TU COMBO DANA AL ENEMIGO: CUANTO MAS ALTO, MAS SUFRE", 415, (255, 180, 60))

    elif pagina == 4:
        # POWER-UPS
        linea("NOTAS ESPECIALES QUE APARECEN EN LA CANCION", 125, BLANCO, fuente)
        linea("ATRAPALAS TOCANDO LA NOTA COMO CUALQUIER OTRA", 155)
        pu_info = [
            ("AUTO", (255, 255, 100), "EL JUEGO TOCA SOLO 6s"),
            ("+HP",  (255, 100, 100), "RECUPERA 4 DE VIDA"),
            ("SLOW", (100, 200, 255), "NOTAS 25% MAS LENTAS POR 8s"),
            ("x2",   (100, 255, 100), "PUNTOS DOBLES POR 10s"),
        ]
        y0 = 200
        for i, (nom, colr, desc) in enumerate(pu_info):
            y = y0 + i * 58
            brill = 0.75 + 0.25 * math.sin(t_anim * 6 + i)
            cc = (int(colr[0] * brill), int(colr[1] * brill), int(colr[2] * brill))
            pygame.draw.rect(pantalla, cc, (cx - 240, y, 90, 36))
            pygame.draw.rect(pantalla, BLANCO, (cx - 240, y, 90, 36), 2)
            nlbl = fuente.render(nom, True, NEGRO)
            pantalla.blit(nlbl, (cx - 240 + 45 - nlbl.get_width() // 2, y + 18 - nlbl.get_height() // 2))
            dlbl = fuente_chica.render(desc, True, GRIS_MED)
            pantalla.blit(dlbl, (cx - 130, y + 10))
        linea("CON MONOCROMO ACTIVO, SE VEN COMO NOTAS NORMALES", 445, GRIS)

    elif pagina == 5:
        # BOMBAS
        linea("APARECEN DESDE NIVEL 4 (NORMAL+)", 125, BLANCO, fuente)
        linea("SON NOTAS ROJAS CON UNA X: NO LAS TOQUES", 158)
        _bx, _by = cx, 230
        pulso = 0.6 + 0.4 * math.sin(t_anim * 10.0)
        _rojo = (int(255 * pulso), int(40 * pulso), int(40 * pulso))
        _bw, _bh = 70, 44
        pygame.draw.rect(pantalla, _rojo, (_bx - _bw // 2, _by, _bw, _bh))
        _gr = 2 if pulso > 0.75 else 3
        pygame.draw.rect(pantalla, BLANCO, (_bx - _bw // 2, _by, _bw, _bh), _gr)
        _r = 10
        _cy_b = _by + _bh // 2
        pygame.draw.line(pantalla, BLANCO, (_bx - _r, _cy_b - _r), (_bx + _r, _cy_b + _r), 3)
        pygame.draw.line(pantalla, BLANCO, (_bx + _r, _cy_b - _r), (_bx - _r, _cy_b + _r), 3)
        linea("SI LA TOCAS: PIERDES 4 DE VIDA + ROMPE COMBO", 305, BLANCO)
        linea("SI LA ESQUIVAS: NO PASA NADA (NO ES UN MISS)", 330, GRIS_MED)
        linea("EL PERK ESCUDO ABSORBE LA EXPLOSION", 360, (100, 200, 255))
        linea("CON MONOCROMO: SE DISFRAZAN PERO MANTIENEN LA X", 395, GRIS)
        linea("SUDDEN DEATH + BOMBA = MUERTE INSTANTANEA", 425, (255, 100, 100))

    elif pagina == 6:
        # PERKS
        linea("AL COMPLETAR UN STAGE ELEGIS 1 DE 3 MEJORAS", 125, BLANCO, fuente)
        linea("SE ACUMULAN DURANTE TODO EL RUN (4 STAGES)", 155)
        linea("NAVEGA CON FLECHAS O TECLAS 1/2/3, CONFIRMA CON ENTER", 180, GRIS)
        cat_col = {"def": (100, 200, 255), "ofe": (255, 150, 60), "mec": (140, 230, 100)}
        perk_info = [
            ("DEFENSIVOS", cat_col["def"], "ESCUDO  CORAZON  VENTANA  RESURRECCION  REGEN"),
            ("OFENSIVOS",  cat_col["ofe"], "MULTI  COMBO SAVE  PERFECTO+  RACHA  CAZADOR"),
            ("MECANICOS",  cat_col["mec"], "LENTO (notas lentas)  IMAN (perfecto amplio)"),
        ]
        y0 = 220
        for i, (cat, col_c, lista) in enumerate(perk_info):
            y = y0 + i * 70
            ctxt = fuente.render(cat, True, col_c)
            pantalla.blit(ctxt, (cx - ctxt.get_width() // 2, y))
            ltxt = fuente_chica.render(lista, True, GRIS_MED)
            pantalla.blit(ltxt, (cx - ltxt.get_width() // 2, y + 28))
        linea("ELEGI SEGUN TU ESTILO: SOBREVIVIR O PUNTUAR", 445, BLANCO)

    elif pagina == 7:
        # MODS
        linea("DESDE EL STAGE 2 SE AGREGAN MODIFICADORES", 120, BLANCO, fuente)
        linea("HACEN EL JUEGO MAS DIFICIL PERO MULTIPLICAN PUNTOS", 148)
        mods_info = [
            ("ESPEJO",     "las teclas se invierten"),
            ("INVERSO",    "las notas suben desde abajo"),
            ("VELOZ",      "todo cae al doble de velocidad"),
            ("ACELERANDO", "la velocidad sube gradualmente"),
            ("NIEBLA",     "las notas aparecen desde la mitad"),
            ("RAFAGAS",    "tramos densos alternados con silencios"),
            ("MONOCROMO",  "power-ups, acordes y bombas sin marca"),
            ("APAGON",     "las notas se desvanecen por momentos"),
            ("SUDDEN",     "un solo error = game over (x2.0!)"),
        ]
        y0 = 185
        for i, (nom, desc) in enumerate(mods_info):
            y = y0 + i * 24
            ntxt = fuente_chica.render(nom, True, BLANCO)
            pantalla.blit(ntxt, (cx - 260, y))
            dtxt = fuente_chica.render(desc, True, GRIS_MED)
            pantalla.blit(dtxt, (cx - 130, y))
        linea("EL DADO REVELA EL MOD ANTES DE CADA STAGE", 445, (255, 180, 60))

    elif pagina == 8:
        # MODOS DE JUEGO
        linea("MENU PRINCIPAL: NAVEGA CON FLECHAS + ENTER", 120, BLANCO, fuente)
        modos = [
            ("JUGAR",       "Elegi una seed con ESPACIO, carga con ENTER"),
            ("CARRERA",     "Desbloquea niveles completando el anterior"),
            ("TUTORIAL",    "Esta pantalla (donde estas ahora)"),
            ("LEADERBOARD", "Top 10 de puntajes locales"),
            ("CONFIG",      "Volumen, brillo, resolucion, audio"),
        ]
        y0 = 175
        for i, (modo, desc) in enumerate(modos):
            y = y0 + i * 44
            mtxt = fuente.render(modo, True, BLANCO)
            pantalla.blit(mtxt, (120, y))
            dtxt = fuente_chica.render(desc, True, GRIS_MED)
            pantalla.blit(dtxt, (120, y + 24))
        linea("DURANTE EL JUEGO: ESC = PAUSA", 410, GRIS)
        linea("EN LA PAUSA: REINICIAR, AJUSTAR VOLUMEN, O SALIR", 435, GRIS)

    # pie de pagina: navegacion + indicador
    pag_txt = fuente_chica.render(f"{pagina + 1}/{TUTORIAL_NUM_PAGINAS}", True, GRIS)
    pantalla.blit(pag_txt, (cx - pag_txt.get_width() // 2, ALTO - 90))
    if pagina < TUTORIAL_NUM_PAGINAS - 1:
        nav = fuente_chica.render("< >  NAVEGAR     ESPACIO = SIGUIENTE     ESC = SALIR", True, GRIS)
    else:
        if (pygame.time.get_ticks() // 500) % 2 == 0:
            nav = fuente.render("ESPACIO = PRACTICAR!", True, (255, 180, 60))
        else:
            nav = fuente.render("ESPACIO = PRACTICAR!", True, GRIS_MED)
    pantalla.blit(nav, (cx - nav.get_width() // 2, ALTO - 60))

menu_opcion = 0   # opcion seleccionada del menu principal
MENU_OPCIONES = ["JUGAR", "INSTRUMENTO", "CARRERA", "TUTORIAL", "LEADERBOARD", "CONFIG"]

def dibujar_menu():
    """Menu principal navegable con flechas y ENTER."""
    pantalla.fill(NEGRO)
    t_anim = pygame.time.get_ticks() / 1000.0
    cx = ANCHO // 2

    # colores por opcion del menu
    MENU_COLORES = [
        (0, 220, 255),    # JUGAR: cyan
        (255, 180, 60),   # INSTRUMENTO: dorado
        (255, 140, 80),   # CARRERA: naranja
        (140, 230, 100),  # TUTORIAL: verde
        (180, 120, 255),  # LEADERBOARD: violeta
        (255, 100, 140),  # CONFIG: rosa
    ]
    col_sel = MENU_COLORES[menu_opcion]

    # visualizador de barras tipo ecualizador (con tinte del color seleccionado)
    tms = t_anim * 3
    n_barras = 32
    bw = ANCHO // n_barras
    for i in range(n_barras):
        h = (math.sin(tms + i * 0.4) * 0.5 + 0.5)
        h *= (math.sin(tms * 1.7 + i * 0.9) * 0.3 + 0.7)
        altura = int(h * 160) + 4
        bx = i * bw
        by = ALTO - altura
        # tinte sutil del color seleccionado en las barras
        _mix = 0.25
        br = int(20 + col_sel[0] * _mix * h * 0.4)
        bg = int(20 + col_sel[1] * _mix * h * 0.4)
        bb = int(20 + col_sel[2] * _mix * h * 0.4)
        pygame.draw.rect(pantalla, (min(255, br), min(255, bg), min(255, bb)),
                         (bx, by, bw - 2, altura))

    # notas musicales flotando (con tinte)
    for j in range(6):
        nx = (j * 137 + int(tms * 20)) % (ANCHO + 60) - 30
        ny = 200 + int(math.sin(tms * 0.27 + j) * 80) + j * 30
        ny = ny % ALTO
        _nc = (int(col_sel[0] * 0.15), int(col_sel[1] * 0.15), int(col_sel[2] * 0.15))
        dibujar_nota_musical(pantalla, nx, ny, 16 + (j % 3) * 6, _nc)

    # titulo con pulso de color
    _tp = 0.7 + 0.3 * math.sin(t_anim * 1.5)
    _tc = (int(col_sel[0] * _tp), int(col_sel[1] * _tp), int(col_sel[2] * _tp))
    titulo = fuente_grande.render("* RHYTHM *", True, _tc)
    pantalla.blit(titulo, (cx - titulo.get_width() // 2, 70))
    # linea bajo titulo con gradiente del color
    pygame.draw.line(pantalla, col_sel, (60, 140), (ANCHO - 60, 140), 2)

    # opciones del menu
    y0 = 200
    gap = 55
    for i, opcion in enumerate(MENU_OPCIONES):
        sel = (i == menu_opcion)
        mc = MENU_COLORES[i]
        if sel:
            # fondo con tinte del color de la opcion
            ow = 280
            _bg = (int(mc[0] * 0.08), int(mc[1] * 0.08), int(mc[2] * 0.08))
            pygame.draw.rect(pantalla, _bg, (cx - ow // 2, y0 + i * gap - 4, ow, 40))
            pygame.draw.rect(pantalla, mc, (cx - ow // 2, y0 + i * gap - 4, ow, 40), 2)
            # flechas animadas con el color
            wave = int(math.sin(t_anim * 4) * 4)
            flecha_l = fuente.render(">", True, mc)
            flecha_r = fuente.render("<", True, mc)
            pantalla.blit(flecha_l, (cx - 130 + wave, y0 + i * gap + 2))
            pantalla.blit(flecha_r, (cx + 115 - wave, y0 + i * gap + 2))
            col_txt = BLANCO
        else:
            # opciones no seleccionadas con su color tenue
            col_txt = (int(mc[0] * 0.45), int(mc[1] * 0.45), int(mc[2] * 0.45))
        txt = fuente.render(opcion, True, col_txt)
        pantalla.blit(txt, (cx - txt.get_width() // 2, y0 + i * gap + 2))

    # progreso de carrera
    c_data = cargar_carrera()
    nivel_max = c_data.get("nivel_max", 1)
    if nivel_max > 1:
        dif_nom = DIFICULTADES.get(nivel_max, {}).get("nombre", "?")
        prog = fuente_chica.render(f"CARRERA: {dif_nom}", True, MENU_COLORES[1])
        pantalla.blit(prog, (cx - prog.get_width() // 2, y0 + len(MENU_OPCIONES) * gap + 20))

    # controles
    ver = fuente_chica.render("FLECHAS + ENTER", True, GRIS)
    pantalla.blit(ver, (cx - ver.get_width() // 2, ALTO - 35))

def simplificar_para_instrumento(cancion):
    """Post-procesa una cancion generada para hacerla jugable con el
    teclado musical por line-in:
    - Sin acordes (una sola nota por beat)
    - Sin holds (el line-in no detecta sustain)
    - Sin bombas (sin forma de esquivarlas con instrumento)
    - Notas mas espaciadas (minimo 300ms entre notas)
    - Maximo 4 columnas"""
    notas = cancion["notas_jugador"]
    filtradas = []
    ultimo_t = -9999
    for n in notas:
        # saltar acordes
        if n.get("es_acorde"):
            # convertir a nota simple: solo la primera columna
            n = dict(n)
            n["cols"] = [n["cols"][0]]
            n["midis"] = [n["midis"][0]]
            n["es_acorde"] = False
        # saltar bombas
        if n.get("es_bomba"):
            continue
        # quitar holds
        n = dict(n)
        n["hold"] = 0
        # limitar a 4 columnas
        if any(c >= 4 for c in n["cols"]):
            n["cols"] = [c % 4 for c in n["cols"]]
            if n["midis"]:
                n["midis"] = [n["midis"][0]]
        # espaciado minimo 300ms
        if n["tiempo"] - ultimo_t < 300:
            continue
        ultimo_t = n["tiempo"]
        filtradas.append(n)
    cancion["notas_jugador"] = filtradas
    return cancion

def dibujar_selector_seed_inst(seed_actual, cargando):
    """Selector de seed para modo instrumento."""
    pantalla.fill(NEGRO)
    cx = ANCHO // 2
    t_anim = pygame.time.get_ticks() / 1000.0
    col_ac = (255, 180, 60)

    titulo = fuente.render("MODO INSTRUMENTO", True, col_ac)
    pantalla.blit(titulo, (cx - titulo.get_width() // 2, 30))
    pygame.draw.line(pantalla, col_ac, (60, 65), (ANCHO - 60, 65), 1)

    # info del modo
    info_lineas = [
        "OPTIMIZADO PARA TECLADO MUSICAL POR LINE-IN",
        "SIN ACORDES  ·  SIN HOLDS  ·  SIN BOMBAS",
        "NOTAS ESPACIADAS  ·  MAX 4 COLUMNAS",
    ]
    for i, txt in enumerate(info_lineas):
        c = GRIS_MED if i > 0 else BLANCO
        t = fuente_chica.render(txt, True, c)
        pantalla.blit(t, (cx - t.get_width() // 2, 80 + i * 20))

    # estado del line-in
    if linein_activo:
        li_st = fuente_chica.render("LINE-IN: ACTIVO", True, (140, 230, 100))
    elif linein_notas_cal:
        li_st = fuente_chica.render("LINE-IN: CALIBRADO (ACTIVAR EN CONFIG)", True, (255, 180, 60))
    else:
        li_st = fuente_chica.render("LINE-IN: NO CONFIGURADO (CONFIG > TECLADO MUSICAL)", True, (255, 100, 100))
    pantalla.blit(li_st, (cx - li_st.get_width() // 2, 145))

    pygame.draw.line(pantalla, GRIS, (60, 170), (ANCHO - 60, 170), 1)

    # selector de seed (misma mecanica)
    ins = fuente_chica.render("MANTENE ESPACIO PARA CARGAR", True, GRIS_MED)
    pantalla.blit(ins, (cx - ins.get_width() // 2, 185))
    barra_w = 400
    barra_x = cx - barra_w // 2
    barra_y = 215
    progreso = min(seed_actual / SEED_MAX, 1.0)
    pygame.draw.rect(pantalla, GRIS, (barra_x, barra_y, barra_w, 20))
    if seed_actual > 0:
        bloques = int(barra_w * progreso) // 10
        for b in range(bloques):
            pygame.draw.rect(pantalla, col_ac, (barra_x + b * 10 + 1, barra_y + 2, 8, 16))
    pygame.draw.rect(pantalla, col_ac, (barra_x, barra_y, barra_w, 20), 2)

    seed_str = str(int(seed_actual)).zfill(6) if seed_actual > 0 else "000000"
    seed_col = col_ac if seed_actual > 0 else GRIS
    seed_texto = fuente_grande.render(seed_str, True, seed_col)
    pantalla.blit(seed_texto, (cx - seed_texto.get_width() // 2, 250))

    dif = get_dificultad(max(seed_actual, 1))
    dif_texto = fuente.render(f"> {dif['nombre']} <", True, col_ac)
    pantalla.blit(dif_texto, (cx - dif_texto.get_width() // 2, 340))

    if seed_actual > 0:
        ctrl = fuente_chica.render("ENTER = JUGAR     R = RESET", True, GRIS_MED)
        pantalla.blit(ctrl, (cx - ctrl.get_width() // 2, 400))
    else:
        if (pygame.time.get_ticks() // 500) % 2 == 0:
            coin = fuente.render("INSERT COIN", True, col_ac)
            pantalla.blit(coin, (cx - coin.get_width() // 2, 400))

    esc = fuente_chica.render("ESC = VOLVER AL MENU", True, GRIS)
    pantalla.blit(esc, (cx - esc.get_width() // 2, ALTO - 40))

# flag global para saber si la partida es modo instrumento
modo_instrumento = False

def dibujar_selector_seed(seed_actual, cargando):
    """Pantalla de selector de seed: mantene espacio para cargar."""
    pantalla.fill(NEGRO)
    cx = ANCHO // 2
    t_anim = pygame.time.get_ticks() / 1000.0
    dif = get_dificultad(max(seed_actual, 1))
    progreso = min(seed_actual / SEED_MAX, 1.0)

    # color de acento segun la dificultad actual (cambia mientras cargás)
    niv = dif.get("nivel", 1)
    # gradiente de facil (cyan) a chaos (rojo) pasando por amarillo
    _t = min(1.0, (niv - 1) / 14.0)
    if _t < 0.5:
        _p = _t * 2
        col_ac = (int(0 + 255 * _p), int(220 - 40 * _p), int(255 - 200 * _p))
    else:
        _p = (_t - 0.5) * 2
        col_ac = (255, int(180 - 140 * _p), int(55 - 55 * _p))

    # ecualizador de fondo (como el menu, con tinte de dificultad)
    tms = t_anim * 3
    n_barras = 32
    bw = ANCHO // n_barras
    for i in range(n_barras):
        h = (math.sin(tms + i * 0.4) * 0.5 + 0.5)
        h *= (math.sin(tms * 1.7 + i * 0.9) * 0.3 + 0.7)
        altura = int(h * 140) + 4
        bx = i * bw
        by = ALTO - altura
        _mix = 0.2
        br = int(15 + col_ac[0] * _mix * h * 0.4)
        bg = int(15 + col_ac[1] * _mix * h * 0.4)
        bb = int(15 + col_ac[2] * _mix * h * 0.4)
        pygame.draw.rect(pantalla, (min(255, br), min(255, bg), min(255, bb)),
                         (bx, by, bw - 2, altura))

    titulo = fuente.render("SELECTOR DE SEED", True, col_ac)
    pantalla.blit(titulo, (cx - titulo.get_width() // 2, 40))
    pygame.draw.line(pantalla, col_ac, (60, 75), (ANCHO - 60, 75), 1)

    ins = fuente_chica.render("MANTENE ESPACIO PARA CARGAR", True, GRIS_MED)
    pantalla.blit(ins, (cx - ins.get_width() // 2, 100))

    # barra de progreso con color de dificultad
    barra_w = 400
    barra_x = cx - barra_w // 2
    barra_y = 140
    pygame.draw.rect(pantalla, GRIS, (barra_x, barra_y, barra_w, 20))
    if seed_actual > 0:
        bloques = int(barra_w * progreso) // 10
        for b in range(bloques):
            # color interpolado por posicion en la barra
            _bp = b / max(1, (barra_w // 10))
            if _bp < 0.5:
                _pp = _bp * 2
                _bc = (int(0 + 255 * _pp), int(220 - 40 * _pp), int(255 - 200 * _pp))
            else:
                _pp = (_bp - 0.5) * 2
                _bc = (255, int(180 - 140 * _pp), int(55 - 55 * _pp))
            pygame.draw.rect(pantalla, _bc, (barra_x + b * 10 + 1, barra_y + 2, 8, 16))
    pygame.draw.rect(pantalla, col_ac, (barra_x, barra_y, barra_w, 20), 2)

    # seed grande con color
    seed_str = str(int(seed_actual)).zfill(6) if seed_actual > 0 else "000000"
    seed_col = col_ac if seed_actual > 0 else GRIS
    seed_texto = fuente_grande.render(seed_str, True, seed_col)
    pantalla.blit(seed_texto, (cx - seed_texto.get_width() // 2, 185))

    pygame.draw.line(pantalla, col_ac, (60, 270), (ANCHO - 60, 270), 1)
    dif_texto = fuente.render(f"> {dif['nombre']} <", True, col_ac)
    pantalla.blit(dif_texto, (cx - dif_texto.get_width() // 2, 290))
    cols_texto = fuente_chica.render(f"{dif['columnas']} COLUMNAS  {'ACORDES ON' if dif['acordes'] else 'ACORDES OFF'}", True, GRIS_MED)
    pantalla.blit(cols_texto, (cx - cols_texto.get_width() // 2, 330))
    pygame.draw.line(pantalla, GRIS, (60, 360), (ANCHO - 60, 360), 1)

    if seed_actual > 0:
        gen_seed = genero_de_seed(int(seed_actual))
        niv_seed = num_dificultad(int(seed_actual))
        comp = cargar_progreso()
        ya = clave_run(gen_seed, niv_seed) in comp
        marca_ok = "  [COMPLETADO]" if ya else ""
        col_gs = COLOR_GENERO.get(gen_seed, col_ac)
        run_txt = fuente_chica.render(f"{DIFICULTADES[niv_seed]['nombre']}{marca_ok}", True, col_gs)
        pantalla.blit(run_txt, (cx - run_txt.get_width() // 2, 375))

    if seed_actual > 0:
        ctrl = fuente_chica.render("ENTER = RUN     M = MODS LIBRE     R = RESET", True, GRIS_MED)
        pantalla.blit(ctrl, (cx - ctrl.get_width() // 2, 410))
    else:
        if (pygame.time.get_ticks() // 500) % 2 == 0:
            coin = fuente.render("INSERT COIN", True, col_ac)
            pantalla.blit(coin, (cx - coin.get_width() // 2, 410))

    esc = fuente_chica.render("ESC = VOLVER AL MENU", True, GRIS)
    pantalla.blit(esc, (cx - esc.get_width() // 2, ALTO - 40))

config_opcion = 0  # 0=brillo, 1=volumen, 2=vol_menu, 3=resolucion, 4=audio
pausa_opcion = 0   # 0=continuar, 1=reiniciar, 2=salir
mods_opcion = 0    # opcion seleccionada en pantalla de modificadores
carrera_cursor = 0 # nivel seleccionado en la pantalla de carrera (0-indexed)
carrera_activa = False  # True si el run actual viene del modo carrera

RANK_COLOR_CARR = {
    "S": (255, 215, 60), "A": (120, 255, 120), "B": (100, 200, 255),
    "C": (255, 180, 60), "D": (255, 100, 100), "?": GRIS,
}

def dibujar_carrera():
    """Pantalla de seleccion de nivel del modo CARRERA."""
    pantalla.fill(NEGRO)
    t_anim = pygame.time.get_ticks() / 1000.0
    cx = ANCHO // 2

    titulo = fuente_grande.render("CARRERA", True, BLANCO)
    pantalla.blit(titulo, (cx - titulo.get_width() // 2, 30))
    sub = fuente_chica.render("COMPLETA CADA NIVEL PARA DESBLOQUEAR EL SIGUIENTE", True, GRIS_MED)
    pantalla.blit(sub, (cx - sub.get_width() // 2, 80))
    pygame.draw.line(pantalla, GRIS, (60, 100), (ANCHO - 60, 100), 1)

    c = cargar_carrera()
    nivel_max = c.get("nivel_max", 1)
    ranks = c.get("ranks", {})
    intentos = c.get("intentos", {})

    # lista de niveles (scroll si hay muchos)
    vis_start = max(0, carrera_cursor - 5)
    vis_end = min(15, vis_start + 11)
    if vis_end - vis_start < 11 and vis_start > 0:
        vis_start = max(0, vis_end - 11)

    y0 = 115
    fila_h = 42
    for i in range(vis_start, vis_end):
        nivel = i + 1
        y = y0 + (i - vis_start) * fila_h
        sel = (i == carrera_cursor)
        desbloqueado = (nivel <= nivel_max)
        completado = str(nivel) in ranks
        dif_info = DIFICULTADES.get(nivel, {})
        nombre = dif_info.get("nombre", f"NIVEL {nivel}")

        # fondo de seleccion
        if sel:
            pygame.draw.rect(pantalla, (40, 40, 50), (80, y, ANCHO - 160, fila_h - 4))
            pygame.draw.rect(pantalla, BLANCO, (80, y, ANCHO - 160, fila_h - 4), 2)

        # numero
        num_col = BLANCO if desbloqueado else GRIS
        num_txt = fuente.render(f"{nivel:2d}", True, num_col)
        pantalla.blit(num_txt, (100, y + 6))

        if desbloqueado:
            # nombre de la dificultad
            nom_txt = fuente.render(nombre, True, BLANCO if sel else GRIS_MED)
            pantalla.blit(nom_txt, (160, y + 6))
            # columnas
            cols = dif_info.get("columnas", 3)
            cols_txt = fuente_chica.render(f"{cols}COL", True, GRIS)
            pantalla.blit(cols_txt, (420, y + 12))
            # rank si completado
            if completado:
                rk = ranks[str(nivel)]
                rk_col = RANK_COLOR_CARR.get(rk, GRIS)
                rk_txt = fuente.render(rk, True, rk_col)
                pantalla.blit(rk_txt, (500, y + 4))
            # intentos
            n_int = intentos.get(str(nivel), 0)
            if n_int > 0:
                int_txt = fuente_chica.render(f"{n_int}x", True, GRIS)
                pantalla.blit(int_txt, (550, y + 12))
        else:
            # bloqueado: candado
            lock = fuente.render("BLOQUEADO", True, GRIS)
            pantalla.blit(lock, (160, y + 6))
            # candado visual
            lx, ly = 530, y + 8
            pygame.draw.rect(pantalla, GRIS, (lx, ly + 6, 16, 12))
            pygame.draw.arc(pantalla, GRIS, (lx + 2, ly - 2, 12, 14), 0, 3.14, 2)

    # instrucciones
    inst_y = ALTO - 55
    pygame.draw.line(pantalla, GRIS, (60, inst_y - 10), (ANCHO - 60, inst_y - 10), 1)
    nivel_sel = carrera_cursor + 1
    if nivel_sel <= nivel_max:
        inst = fuente_chica.render("ENTER = JUGAR     ESC = VOLVER", True, GRIS_MED)
    else:
        inst = fuente_chica.render("NIVEL BLOQUEADO     ESC = VOLVER", True, GRIS)
    pantalla.blit(inst, (cx - inst.get_width() // 2, inst_y))

    # progreso total
    completados = sum(1 for k in ranks)
    prog = fuente_chica.render(f"PROGRESO: {completados}/15 NIVELES", True, GRIS)
    pantalla.blit(prog, (cx - prog.get_width() // 2, inst_y + 22))

def calcular_mult_mods():
    """Multiplicador total de puntos segun modificadores activos"""
    mult = 1.0
    for m in MODIFICADORES:
        if m["id"] in mods_activos:
            mult *= m["mult"]
    return mult

# ---------------- SISTEMA DE STAGES (modo roguelike) ----------------
def mods_de_stage(n, rng):
    """Devuelve el set de mods para el stage n (1..4).
    Los mods se escalonan por dificultad:
      - suaves (stage 2+): inverso, acelerando, rafagas, monocromo
      - medios (stage 3+): niebla, veloz, apagon, + espejo con 30%
      - duros  (stage 4):  espejo con 35%, sudden death 10%
    ESPEJO: nunca en stages 1-2, 30% en stage 3, 35% en stage 4."""
    suaves = ["inverso", "acelerando", "rafagas", "monocromo"]
    medios = ["niebla", "veloz", "apagon"]
    if n == 1:
        return set()
    elif n == 2:
        # stage 2: solo un mod suave (nada que desoriente demasiado tan temprano)
        return {rng.choice(suaves)}
    elif n == 3:
        # stage 3: espejo con 30%; si no, un mod suave o medio
        if rng.random() < 0.30:
            return {"espejo"}
        return {rng.choice(suaves + medios)}
    else:  # stage 4: espejo con 35% + otro mod (incluye los duros) + sudden 10%
        mods = set()
        if rng.random() < 0.35:
            mods.add("espejo")
        # pool completo de movimiento para el stage final
        otros = suaves + medios
        if not mods:
            mods.add(rng.choice(otros))
            if rng.random() < 0.5:
                mods.add(rng.choice(otros))
        elif rng.random() < 0.5:
            mods.add(rng.choice(otros))
        if rng.random() < 0.10:
            mods.add("sudden")
        return mods

def crear_run(seed_inicial):
    """Crea un run de stages a partir de la seed cargada.
    Garantiza un instrumento distinto en cada stage para dar variedad."""
    nivel = num_dificultad(seed_inicial)
    genero = genero_de_seed(seed_inicial)
    rng = random.Random(int(seed_inicial) * 31 + 7)
    seeds = [int(seed_inicial)]   # stage 1 usa la seed cargada
    usadas = {int(seed_inicial)}
    mods_stages = [set()]
    for n in range(2, NUM_STAGES + 1):
        s = buscar_seed_genero(genero, nivel, rng, evitar=usadas)
        if s is None:
            s = int(seed_inicial)   # fallback: reusar
        usadas.add(s)
        seeds.append(s)
        mods_stages.append(mods_de_stage(n, rng))

    # --- asignar un instrumento distinto a cada stage ---
    gdef = GENEROS.get(genero, {})
    pool = [i for i in gdef.get("instrumentos", []) if i in INSTRUMENTOS_JUGADOR]
    if not pool:
        pool = list(INSTRUMENTOS_JUGADOR.keys())
    # quitar RESO del pool de runs (suena agresivo, se re-rollea siempre)
    pool_sin_reso = [p for p in pool if p != "RESO"] or pool
    pool_barajado = pool_sin_reso[:]
    rng.shuffle(pool_barajado)
    instrumentos_stage = []
    for n in range(NUM_STAGES):
        if n < len(pool_barajado):
            instrumentos_stage.append(pool_barajado[n])
        else:
            # pool mas chico que la cantidad de stages: reusar sin repetir consecutivo
            instrumentos_stage.append(rng.choice(pool_sin_reso))
    # 15% de chance de que un stage al azar (no el primero) traiga un instrumento raro
    # (solo si hay raros disponibles: puede quedar vacio si se eliminaron)
    if INSTRUMENTOS_RAROS and rng.random() < 0.15 and NUM_STAGES > 1:
        idx_raro = rng.randint(1, NUM_STAGES - 1)
        instrumentos_stage[idx_raro] = rng.choice(list(INSTRUMENTOS_RAROS.keys()))

    return {
        "genero": genero,
        "nivel": nivel,
        "stage": 1,            # stage actual (1..4)
        "seeds": seeds,        # seed por stage
        "mods": mods_stages,   # set de mods por stage
        "instrumentos": instrumentos_stage,  # instrumento forzado por stage
        "puntos_total": 0,
        "puntos_por_stage": [0] * NUM_STAGES,  # puntos ganados en cada stage
        "perks": [],           # perks acumulados (roguelike)
    }

perk_ofertas = []      # 3 perks ofrecidos en la pantalla de seleccion
perk_seleccion = 0     # indice seleccionado (0..2)
perk_anim_inicio = 0   # timestamp (ms) del inicio de la animacion de entrada
PERK_ANIM_MS = 700     # duracion total de la animacion de entrada
PERK_ANIM_STAGGER = 120  # delay entre cartas (escalonado)
PERK_ANIM_CARTA = 380  # duracion de la animacion de una carta individual

def dibujar_perk_select():
    """Pantalla de seleccion de perk entre stages.
    Cada carta tiene el color de su categoria (def=cyan, ofe=naranja, mec=verde)
    y entra desde abajo con overshoot suave, escalonada."""
    pantalla.fill(NEGRO)
    col_g = COLOR_GENERO.get(run_actual["genero"], BLANCO) if run_actual else BLANCO
    titulo = fuente_grande.render("NUEVO PERK", True, col_g)
    pantalla.blit(titulo, (ANCHO // 2 - titulo.get_width() // 2, 50))
    sub = fuente_chica.render("ELEGI UNA MEJORA PARA TU RUN", True, GRIS_MED)
    pantalla.blit(sub, (ANCHO // 2 - sub.get_width() // 2, 110))
    pygame.draw.line(pantalla, GRIS, (60, 135), (ANCHO - 60, 135), 1)
    # categorias visuales
    cat_label = {"def": "DEFENSIVO", "ofe": "OFENSIVO", "mec": "MECANICO"}
    # dibujar las 3 opciones
    card_w = 180
    card_h = 260
    gap = 30
    total_w = card_w * len(perk_ofertas) + gap * (len(perk_ofertas) - 1)
    x0 = ANCHO // 2 - total_w // 2
    y_final = 180
    # animacion de entrada: cada carta hace slide desde abajo con overshoot
    elapsed = pygame.time.get_ticks() - perk_anim_inicio
    for i, perk in enumerate(perk_ofertas):
        # progreso de esta carta (escalonada)
        t_local = max(0, elapsed - i * PERK_ANIM_STAGGER)
        t_norm = min(1.0, t_local / PERK_ANIM_CARTA)
        # ease-out back: overshoot suave al aterrizar
        c1 = 1.70158
        c3 = c1 + 1
        u = t_norm - 1
        ease = 1 + c3 * u ** 3 + c1 * u ** 2  # va de 0 a ~1.1 y baja a 1
        # antes de aparecer, la carta esta abajo y fuera de pantalla
        offset_y = int((1.0 - ease) * 200)  # 200px abajo -> 0
        # antes de que arranque su animacion, no dibujar nada
        if t_local <= 0:
            continue
        x = x0 + i * (card_w + gap)
        y = y_final + offset_y
        seleccionado = (i == perk_seleccion) and t_norm >= 1.0
        # color de la categoria de este perk
        cat_col = COLOR_CAT.get(perk["cat"], BLANCO)
        # borde: color de categoria; cuando esta seleccionado, mas grueso
        borde_color = cat_col if seleccionado else tuple(int(c * 0.5) for c in cat_col)
        grosor = 3 if seleccionado else 2
        pygame.draw.rect(pantalla, borde_color, (x, y, card_w, card_h), grosor)
        if seleccionado:
            # relleno tenue con tinte de categoria
            fondo = tuple(int(c * 0.12) for c in cat_col)
            pygame.draw.rect(pantalla, fondo, (x + 3, y + 3, card_w - 6, card_h - 6))
        # numero (grande, tinte de categoria)
        num_col = cat_col if seleccionado else tuple(int(c * 0.55) for c in cat_col)
        num = fuente_grande.render(str(i + 1), True, num_col)
        pantalla.blit(num, (x + card_w // 2 - num.get_width() // 2, y + 10))
        # nombre del perk
        nombre = fuente.render(perk["nombre"], True, BLANCO if seleccionado else GRIS_MED)
        pantalla.blit(nombre, (x + card_w // 2 - nombre.get_width() // 2, y + 70))
        # categoria: con color de categoria (mas visible que el gris de antes)
        cat = fuente_chica.render(cat_label.get(perk["cat"], ""), True, cat_col)
        pantalla.blit(cat, (x + card_w // 2 - cat.get_width() // 2, y + 100))
        # linea separadora chica bajo la categoria
        pygame.draw.line(pantalla, tuple(int(c * 0.35) for c in cat_col),
                         (x + 30, y + 120), (x + card_w - 30, y + 120), 1)
        # descripcion (word wrap manual simple)
        desc = perk["desc"]
        dy = 135
        palabras = desc.split()
        linea = ""
        desc_col = BLANCO if seleccionado else GRIS_MED
        for pal in palabras:
            test = (linea + " " + pal).strip()
            if fuente_chica.size(test)[0] > card_w - 20:
                txt = fuente_chica.render(linea, True, desc_col)
                pantalla.blit(txt, (x + card_w // 2 - txt.get_width() // 2, y + dy))
                dy += 18
                linea = pal
            else:
                linea = test
        if linea:
            txt = fuente_chica.render(linea, True, desc_col)
            pantalla.blit(txt, (x + card_w // 2 - txt.get_width() // 2, y + dy))
    # perks acumulados (solo cuando la animacion termino)
    anim_lista = i * PERK_ANIM_STAGGER + PERK_ANIM_CARTA if perk_ofertas else 0
    if elapsed >= anim_lista and run_actual and run_actual["perks"]:
        acum_y = 470
        acum_txt = fuente_chica.render("PERKS ACTIVOS:", True, GRIS)
        pantalla.blit(acum_txt, (ANCHO // 2 - acum_txt.get_width() // 2, acum_y))
        # cada perk activo con el color de su categoria (mas informativo)
        px_acum = 0
        anchos = [fuente_chica.size(p["nombre"])[0] + 20 for p in run_actual["perks"]]
        total_activos_w = sum(anchos) - 20 if anchos else 0
        px_acum = ANCHO // 2 - total_activos_w // 2
        for p in run_actual["perks"]:
            pcol = COLOR_CAT.get(p["cat"], col_g)
            ptxt = fuente_chica.render(p["nombre"], True, pcol)
            pantalla.blit(ptxt, (px_acum, acum_y + 20))
            px_acum += ptxt.get_width() + 20
    # instrucciones (solo cuando la animacion termino)
    if elapsed >= anim_lista:
        inst = fuente_chica.render("1 / 2 / 3  O  FLECHAS + ENTER", True, GRIS)
        pantalla.blit(inst, (ANCHO // 2 - inst.get_width() // 2, ALTO - 40))

def dibujar_perks_hud(partida):
    """Dibuja los perks activos y efectos temporales en el HUD del juego."""
    # perks permanentes: linea debajo del stage (izquierda, Y=58)
    perks = partida.get("perks", [])
    px = 10
    py = 58
    for p in perks:
        txt = fuente_chica.render(p["nombre"][:3], True, GRIS)
        pantalla.blit(txt, (px, py))
        px += txt.get_width() + 6
    # escudo: mostrar cargas (izquierda, debajo de perks)
    cargas = partida.get("escudo_cargas", 0)
    if cargas > 0:
        esc_txt = fuente_chica.render(f"ESCUDO x{cargas}", True, (100, 200, 255))
        pantalla.blit(esc_txt, (10, py + 16))
    # efectos temporales activos: borde izquierdo a media altura
    efectos = partida.get("efectos_activos", {})
    ahora = int(partida.get("t_musical", pygame.time.get_ticks() - partida["inicio"]))
    ey = 90
    for eid, t_fin in list(efectos.items()):
        restante = max(0, t_fin - ahora)
        if restante <= 0:
            continue
        pu_def = next((pu for pu in POWER_UPS if pu["id"] == eid), None)
        if not pu_def:
            continue
        color = pu_def["color"]
        if restante < 2000 and (pygame.time.get_ticks() // 200) % 2 == 0:
            color = GRIS
        seg = f"{restante / 1000:.1f}s"
        etxt = fuente_chica.render(f"{pu_def['nombre']} {seg}", True, color)
        pantalla.blit(etxt, (10, ey))
        ey += 18

def dibujar_run_overview():
    """Pantalla entre stages: mapa de camino horizontal (estilo roguelike)
    + panel de detalle del stage actual."""
    pantalla.fill(NEGRO)
    col_g = COLOR_GENERO.get(run_actual["genero"], BLANCO)
    t_anim = pygame.time.get_ticks() / 1000.0

    # ── HEADER: dificultad + puntos acumulados ──
    dif_nom = DIFICULTADES[run_actual["nivel"]]["nombre"]
    titulo = fuente_grande.render(dif_nom, True, col_g)
    pantalla.blit(titulo, (ANCHO // 2 - titulo.get_width() // 2, 36))
    pts_tot = run_actual.get("puntos_total", 0)
    sub_txt = f"{pts_tot} PTS" if pts_tot > 0 else f"SEED {run_actual['seeds'][0] if run_actual.get('seeds') else '?'}"
    sub = fuente.render(sub_txt, True, GRIS_MED)
    pantalla.blit(sub, (ANCHO // 2 - sub.get_width() // 2, 92))
    pygame.draw.line(pantalla, GRIS, (60, 130), (ANCHO - 60, 130), 1)

    # ── CAMINO DE NODOS: 4 stages conectados horizontalmente ──
    nodo_y = 195
    margen = 110
    paso_x = (ANCHO - margen * 2) / (NUM_STAGES - 1)
    stage_act = run_actual["stage"]

    # linea conectora: color genero hasta el nodo actual, gris punteada despues
    for i in range(NUM_STAGES - 1):
        x0 = int(margen + i * paso_x) + 16
        x1 = int(margen + (i + 1) * paso_x) - 16
        if i + 1 < stage_act:
            pygame.draw.line(pantalla, col_g, (x0, nodo_y), (x1, nodo_y), 3)
        elif i + 1 == stage_act:
            pygame.draw.line(pantalla, GRIS_MED, (x0, nodo_y), (x1, nodo_y), 2)
        else:
            # punteada para lo desconocido
            seg = 8
            x = x0
            while x < x1:
                pygame.draw.line(pantalla, GRIS, (x, nodo_y), (min(x + seg, x1), nodo_y), 1)
                x += seg * 2

    nombres_mod = {m["id"]: m["nombre"] for m in MODIFICADORES}
    for i in range(NUM_STAGES):
        st = i + 1
        cx = int(margen + i * paso_x)
        completado = st < stage_act
        actual = st == stage_act
        es_final = st == NUM_STAGES

        # ── nodo ──
        if es_final:
            # rombo: el stage final (sudden death) es visualmente distinto
            r = 15 if actual else 12
            pts_rombo = [(cx, nodo_y - r), (cx + r, nodo_y), (cx, nodo_y + r), (cx - r, nodo_y)]
            if completado:
                pygame.draw.polygon(pantalla, col_g, pts_rombo)
            elif actual:
                pulso = 0.7 + 0.3 * math.sin(t_anim * 5)
                cp = (int(255 * pulso),) * 3
                pygame.draw.polygon(pantalla, cp, pts_rombo, 0)
                pygame.draw.polygon(pantalla, BLANCO, [(cx, nodo_y - r - 5), (cx + r + 5, nodo_y),
                                                        (cx, nodo_y + r + 5), (cx - r - 5, nodo_y)], 2)
            else:
                pygame.draw.polygon(pantalla, GRIS, pts_rombo, 2)
        else:
            if completado:
                pygame.draw.circle(pantalla, col_g, (cx, nodo_y), 13)
                # check
                pygame.draw.lines(pantalla, NEGRO, False,
                                  [(cx - 5, nodo_y), (cx - 1, nodo_y + 4), (cx + 6, nodo_y - 4)], 3)
            elif actual:
                # anillo pulsante blanco
                pulso = 0.7 + 0.3 * math.sin(t_anim * 5)
                pygame.draw.circle(pantalla, (int(255 * pulso),) * 3, (cx, nodo_y), 13)
                pygame.draw.circle(pantalla, BLANCO, (cx, nodo_y), 18, 2)
            else:
                pygame.draw.circle(pantalla, GRIS, (cx, nodo_y), 11, 2)

        # ── etiquetas bajo el nodo ──
        num_c = BLANCO if actual else (col_g if completado else GRIS)
        num_txt = fuente.render(str(st), True, num_c)
        pantalla.blit(num_txt, (cx - num_txt.get_width() // 2, nodo_y + 26))

        # mod del stage (oculto si es futuro)
        mods_st = run_actual["mods"][i]
        if not mods_st:
            mod_str = "BASE"
        elif completado or actual:
            mod_str = "+".join(nombres_mod.get(mid, mid.upper()) for mid in mods_st)
            # si el join no entra en el nodo, mostrar contador en vez de
            # truncar silenciosamente (el [:14] anterior ocultaba mods)
            if len(mod_str) > 14:
                if len(mods_st) > 1:
                    mod_str = f"{len(mods_st)} MODS"
                else:
                    mod_str = mod_str[:13] + "…"
        else:
            mod_str = "???"
        mod_c = BLANCO if actual else (col_g if completado else GRIS)
        mod_txt = fuente_chica.render(mod_str, True, mod_c)
        pantalla.blit(mod_txt, (cx - mod_txt.get_width() // 2, nodo_y + 52))

        # puntos ganados (solo completados)
        if completado:
            gan = run_actual.get("puntos_por_stage", [0] * NUM_STAGES)[i]
            if gan > 0:
                g_txt = fuente_chica.render(f"+{gan}", True, GRIS_MED)
                pantalla.blit(g_txt, (cx - g_txt.get_width() // 2, nodo_y + 70))

    # ── PANEL DE DETALLE del stage actual ──
    panel_y = 320
    panel_h = 118
    panel_x = 80
    panel_w = ANCHO - panel_x * 2
    pygame.draw.rect(pantalla, col_g, (panel_x, panel_y, panel_w, panel_h), 2)

    idx_act = stage_act - 1
    mods_act = run_actual["mods"][idx_act]
    if not mods_act:
        p_titulo = f"STAGE {stage_act} · SIN MODIFICADOR"
        p_desc = "cancion base, sin sorpresas"
        p_mult = ""
    else:
        defs = [m for m in MODIFICADORES if m["id"] in mods_act]
        p_titulo = f"STAGE {stage_act} · " + " + ".join(m["nombre"] for m in defs)
        p_desc = " / ".join(m["desc"] for m in defs)
        mult_total = 1.0
        for m in defs:
            mult_total *= m["mult"]
        p_mult = f"PUNTOS x{mult_total:.1f}"

    # titulo del panel: si con la fuente normal desborda el ancho util
    # (dejando lugar al icono del instrumento a la derecha), cae a la fuente
    # chica. Con 3 mods el titulo largo se superponia al icono y se salia
    # de pantalla. Margen de 90px: el icono ocupa desde panel_w-46, y las
    # metricas de courier varian entre sistemas (Windows vs Linux), asi que
    # el umbral tiene que tener holgura real, no quedar al borde.
    ancho_util = panel_w - 90
    pt = fuente.render(p_titulo, True, BLANCO)
    if pt.get_width() > ancho_util:
        pt = fuente_chica.render(p_titulo, True, BLANCO)
        if pt.get_width() > ancho_util:
            # ultimo recurso: truncar con elipsis
            while len(p_titulo) > 8 and fuente_chica.size(p_titulo + "…")[0] > ancho_util:
                p_titulo = p_titulo[:-1]
            pt = fuente_chica.render(p_titulo + "…", True, BLANCO)
    pantalla.blit(pt, (panel_x + 18, panel_y + 14))
    # descripcion con word-wrap a max 2 lineas (con 3 mods desbordaba)
    _desc_max_w = panel_w - 36
    _lineas_desc = []
    _linea_act = ""
    for _pal in p_desc.split():
        _test = (_linea_act + " " + _pal).strip()
        if fuente_chica.size(_test)[0] > _desc_max_w and _linea_act:
            _lineas_desc.append(_linea_act)
            _linea_act = _pal
            if len(_lineas_desc) == 2:
                break
        else:
            _linea_act = _test
    if _linea_act and len(_lineas_desc) < 2:
        _lineas_desc.append(_linea_act)
    elif len(_lineas_desc) == 2:
        # quedo texto afuera: marcar con elipsis la 2da linea
        _lineas_desc[1] = _lineas_desc[1][:max(1, len(_lineas_desc[1]) - 1)] + "…"
    for _i, _ld in enumerate(_lineas_desc):
        pd = fuente_chica.render(_ld, True, GRIS_MED)
        pantalla.blit(pd, (panel_x + 18, panel_y + 42 + _i * 16))

    meta_st = calcular_meta(run_actual["nivel"], stage_act)
    inst_st = run_actual.get("instrumentos", [""] * NUM_STAGES)[idx_act]
    info_str = f"META: {meta_st} PTS"
    if inst_st:
        info_str += f" · {inst_st}"
    if p_mult:
        info_str += f" · {p_mult}"
    pi = fuente_chica.render(info_str, True, col_g)
    pantalla.blit(pi, (panel_x + 18, panel_y + 82))
    # icono del instrumento del stage
    if inst_st:
        forma_i = forma_de_instrumento(inst_st)
        dibujar_icono_inst(pantalla, forma_i, panel_x + panel_w - 34, panel_y + 30, 12, col_g)

    # ── PERKS acumulados ──
    perks_run = run_actual.get("perks", [])
    pk_y = panel_y + panel_h + 26
    if perks_run:
        pk_label = fuente_chica.render("PERKS:", True, GRIS)
        pantalla.blit(pk_label, (panel_x, pk_y))
        pk_nombres = " · ".join(p["nombre"] for p in perks_run)
        pk_txt = fuente_chica.render(pk_nombres, True, col_g)
        pantalla.blit(pk_txt, (panel_x + pk_label.get_width() + 10, pk_y))

    # ── CONTROLES ──
    if (pygame.time.get_ticks() // 600) % 2 == 0:
        cont = fuente.render("ESPACIO = JUGAR", True, BLANCO)
    else:
        cont = fuente.render("ESPACIO = JUGAR", True, GRIS_MED)
    pantalla.blit(cont, (ANCHO // 2 - cont.get_width() // 2, ALTO - 78))
    esc = fuente_chica.render("ESC = ABANDONAR RUN", True, GRIS)
    pantalla.blit(esc, (ANCHO // 2 - esc.get_width() // 2, ALTO - 42))

# --- animacion de dado para revelar el mod del siguiente stage ---
dado_inicio = 0
DADO_DURACION = 2500  # ms que dura la animacion del dado
_dado_ultima_fase = -2  # para detectar cambios y reproducir tick

def dibujar_dado():
    """Animacion de dado que revela el mod del siguiente stage."""
    pantalla.fill(NEGRO)
    col_g = COLOR_GENERO.get(run_actual["genero"], BLANCO)
    ahora = pygame.time.get_ticks() - dado_inicio
    progreso = min(ahora / DADO_DURACION, 1.0)
    idx_stage = run_actual["stage"] - 1   # stage actual (el que se va a jugar)
    mod_real = run_actual["mods"][idx_stage]

    titulo = fuente_grande.render(f"STAGE {run_actual['stage']}", True, col_g)
    pantalla.blit(titulo, (ANCHO // 2 - titulo.get_width() // 2, 100))

    # subtitulo
    es_multi = len(mod_real) > 1
    sub = fuente.render("TIRANDO DADO..." if progreso < 1.0 else
                        ("MODS REVELADOS!" if es_multi else "MOD REVELADO!"),
                        True, GRIS_MED if progreso < 1.0 else BLANCO)
    pantalla.blit(sub, (ANCHO // 2 - sub.get_width() // 2, 180))

    # dado girando: cicla entre mods cada vez mas lento
    global _dado_ultima_fase
    if progreso < 1.0:
        freq = 20.0 * (1.0 - progreso * 0.9)
        fase = int(ahora * freq / 1000)
        todos_mods = MODS_FACILES + ["sudden"]
        mod_mostrar = todos_mods[fase % len(todos_mods)]
        # tick cada vez que cambia el mod mostrado
        if fase != _dado_ultima_fase:
            _dado_ultima_fase = fase
            SND_DADO.set_volume(0.35 * config["volumen"])
            SND_DADO.play()
    else:
        mod_mostrar = list(mod_real)[0] if mod_real else ""
        if _dado_ultima_fase != -1:
            # sonido de confirmacion al detenerse
            _dado_ultima_fase = -1
            sfx_confirm()

    # dibujar el "dado"
    dado_w = 400
    dado_h = 160 if es_multi else 120
    dado_x = ANCHO // 2 - dado_w // 2
    dado_y = 240
    if progreso < 1.0:
        shake = int((1.0 - progreso) * 6)
        dado_x += random.randint(-shake, shake)
        dado_y += random.randint(-shake, shake)
    borde_color = col_g if progreso >= 1.0 else BLANCO
    pygame.draw.rect(pantalla, borde_color, (dado_x, dado_y, dado_w, dado_h), 3)
    for dx, dy in [(20, 20), (dado_w - 20, 20), (20, dado_h - 20), (dado_w - 20, dado_h - 20)]:
        pygame.draw.circle(pantalla, GRIS, (dado_x + dx, dado_y + dy), 5)

    if progreso < 1.0 or not es_multi:
        # un solo mod: nombre grande centrado
        nombre_mod = ""
        for m in MODIFICADORES:
            if m["id"] == mod_mostrar:
                nombre_mod = m["nombre"]
                break
        color_mod = col_g if progreso >= 1.0 else BLANCO
        mod_txt = fuente_grande.render(nombre_mod, True, color_mod)
        pantalla.blit(mod_txt, (ANCHO // 2 - mod_txt.get_width() // 2, dado_y + dado_h // 2 - mod_txt.get_height() // 2))
        if progreso >= 1.0 and not es_multi:
            for m in MODIFICADORES:
                if m["id"] == mod_mostrar:
                    desc = fuente_chica.render(m["desc"], True, GRIS_MED)
                    pantalla.blit(desc, (ANCHO // 2 - desc.get_width() // 2, dado_y + dado_h + 20))
                    mult = fuente_chica.render(f"MULTIPLICADOR: x{m['mult']}", True, GRIS_MED)
                    pantalla.blit(mult, (ANCHO // 2 - mult.get_width() // 2, dado_y + dado_h + 45))
                    break
    else:
        # multiples mods: listarlos dentro del dado
        nombres = [m["nombre"] for m in MODIFICADORES if m["id"] in mod_real]
        mult_total = 1.0
        for m in MODIFICADORES:
            if m["id"] in mod_real:
                mult_total *= m["mult"]
        n_mods = len(nombres)
        y_start = dado_y + dado_h // 2 - (n_mods * 14)
        for i, nom in enumerate(nombres):
            color_m = (255, 80, 80) if "SUDDEN" in nom else col_g
            mt = fuente.render(nom, True, color_m)
            pantalla.blit(mt, (ANCHO // 2 - mt.get_width() // 2, y_start + i * 28))
        mult = fuente_chica.render(f"MULTIPLICADOR TOTAL: x{mult_total:.2f}", True, GRIS_MED)
        pantalla.blit(mult, (ANCHO // 2 - mult.get_width() // 2, dado_y + dado_h + 25))

    if progreso >= 1.0:
        cont = fuente_chica.render("ESPACIO = CONTINUAR", True, GRIS)
        pantalla.blit(cont, (ANCHO // 2 - cont.get_width() // 2, ALTO - 50))

run_completado_inicio = 0
run_completado_particulas = []
_ultimo_fuego_t = 0

def _spawn_notas_celebracion(col_g):
    """Genera la primera oleada de particulas."""
    run_completado_particulas.clear()
    global run_completado_inicio, _ultimo_fuego_t
    run_completado_inicio = pygame.time.get_ticks()
    _ultimo_fuego_t = 0
    # fanfarria de victoria
    SND_WIN.set_volume(0.6 * config["volumen"])
    SND_WIN.play()
    # explosion central grande
    for _ in range(120):
        ang = random.uniform(0, 2 * math.pi)
        vel = random.uniform(2, 10)
        run_completado_particulas.append({
            "x": ANCHO // 2, "y": ALTO // 2 - 40,
            "vx": math.cos(ang) * vel, "vy": math.sin(ang) * vel - 3,
            "vida": random.uniform(2.5, 6.0), "t": 0,
            "color": col_g if random.random() > 0.25 else BLANCO,
            "tam": random.randint(3, 10),
        })

def _spawn_fuego(col_g):
    """Spawns un fuego artificial en posicion aleatoria."""
    fx = random.randint(60, ANCHO - 60)
    fy = random.randint(80, ALTO // 2)
    n = random.randint(25, 50)
    for _ in range(n):
        ang = random.uniform(0, 2 * math.pi)
        vel = random.uniform(1, 6)
        run_completado_particulas.append({
            "x": fx, "y": fy,
            "vx": math.cos(ang) * vel, "vy": math.sin(ang) * vel - 2,
            "vida": random.uniform(1.5, 4.0), "t": 0,
            "color": col_g if random.random() > 0.3 else BLANCO,
            "tam": random.randint(2, 7),
        })

def dibujar_run_completado():
    """Pantalla de run completado con fuegos artificiales."""
    global _ultimo_fuego_t
    pantalla.fill(NEGRO)
    col_g = COLOR_GENERO.get(run_actual["genero"], BLANCO)
    ahora = pygame.time.get_ticks()
    t_total = (ahora - run_completado_inicio) / 1000.0
    dt = 1.0 / 60

    # spawns periodicos de fuegos: maximo uno cada ~0.6s durante 7s
    if t_total < 7.0 and (ahora - _ultimo_fuego_t) > 600 and len(run_completado_particulas) < 400:
        _ultimo_fuego_t = ahora
        _spawn_fuego(col_g)
        SND_EXPLOSION.set_volume(0.3 * config["volumen"])
        SND_EXPLOSION.play()

    # lluvia de chispas desde arriba (con cap de particulas)
    if t_total < 6.0 and random.random() < 0.2 and len(run_completado_particulas) < 400:
        run_completado_particulas.append({
            "x": random.randint(0, ANCHO), "y": -5,
            "vx": random.uniform(-0.5, 0.5), "vy": random.uniform(1, 3),
            "vida": random.uniform(3.0, 6.0), "t": 0,
            "color": col_g if random.random() > 0.5 else BLANCO,
            "tam": random.randint(1, 4),
        })

    # barras de fondo pulsantes (una sola surface reusada)
    pulso = math.sin(t_total * 4) * 0.5 + 0.5
    alpha = int(12 * pulso)
    if alpha > 0:
        bar = pygame.Surface((30, ALTO))
        bar.fill(col_g)
        bar.set_alpha(alpha)
        for i in range(0, ANCHO, 60):
            pantalla.blit(bar, (i, 0))

    # actualizar y dibujar particulas
    vivas = []
    for p in run_completado_particulas:
        p["t"] += dt
        if p["t"] < p["vida"]:
            p["x"] += p["vx"]
            p["y"] += p["vy"]
            p["vy"] += 0.08
            p["vx"] *= 0.995
            alpha = max(0, 1.0 - p["t"] / p["vida"])
            c = tuple(min(255, int(v * alpha)) for v in p["color"])
            tam = max(1, int(p["tam"] * (0.5 + alpha * 0.5)))
            px, py = int(p["x"]), int(p["y"])
            pygame.draw.rect(pantalla, c, (px - tam//2, py - tam//2, tam, tam))
            # cola (estela)
            if tam > 2:
                trail_c = tuple(min(255, int(v * alpha * 0.4)) for v in p["color"])
                pygame.draw.line(pantalla, trail_c,
                    (px, py), (px - int(p["vx"] * 3), py - int(p["vy"] * 3)), max(1, tam // 2))
            # nota musical decorativa en particulas grandes
            if p["tam"] >= 7 and alpha > 0.5:
                pygame.draw.line(pantalla, c,
                    (px + tam//2, py - tam//2), (px + tam//2, py - tam - 8), 1)
            vivas.append(p)
    run_completado_particulas[:] = vivas

    # titulo con efecto de escala pulsante
    escala_t = 1.0 + math.sin(t_total * 3) * 0.05
    titulo_txt = "RUN COMPLETO!"
    titulo = fuente_grande.render(titulo_txt, True, col_g)
    tw, th = titulo.get_size()
    scaled = pygame.transform.scale(titulo, (int(tw * escala_t), int(th * escala_t)))
    pantalla.blit(scaled, (ANCHO // 2 - scaled.get_width() // 2, 140 - (scaled.get_height() - th) // 2))

    # lineas decorativas
    line_w = int(200 + pulso * 80)
    pygame.draw.line(pantalla, col_g, (ANCHO//2 - line_w, 200), (ANCHO//2 + line_w, 200), 2)

    dif_nom = DIFICULTADES[run_actual["nivel"]]["nombre"]
    sub = fuente.render(dif_nom, True, BLANCO)
    pantalla.blit(sub, (ANCHO // 2 - sub.get_width() // 2, 230))
    pts = fuente.render(f"PUNTOS TOTALES: {run_actual['puntos_total']}", True, GRIS_MED)
    pantalla.blit(pts, (ANCHO // 2 - pts.get_width() // 2, 290))

    # stages completados con rank de performance (S/A/B/C/D)
    RANK_COLOR = {
        "S": (255, 215, 60),    # dorado
        "A": (120, 255, 120),   # verde
        "B": (100, 200, 255),   # celeste
        "C": (255, 180, 60),    # naranja
        "D": (255, 100, 100),   # rojo
        "?": GRIS,
    }
    ranks = run_actual.get("rank_por_stage", ["?"] * NUM_STAGES)
    y_st = 340
    for i in range(NUM_STAGES):
        visible = t_total > 0.5 + i * 0.4
        st_col = col_g if visible else GRIS
        rk = ranks[i] if i < len(ranks) else "?"
        st = fuente_chica.render(f"STAGE {i+1}  ", True, st_col)
        rk_col = RANK_COLOR.get(rk, GRIS) if visible else GRIS
        rk_txt = fuente.render(rk, True, rk_col)
        total_w = st.get_width() + rk_txt.get_width()
        x0 = ANCHO // 2 - total_w // 2
        pantalla.blit(st, (x0, y_st + i * 26 + 3))
        pantalla.blit(rk_txt, (x0 + st.get_width(), y_st + i * 26 - 3))

    cont = fuente_chica.render("ESPACIO = CONTINUAR", True, GRIS)
    pantalla.blit(cont, (ANCHO // 2 - cont.get_width() // 2, ALTO - 50))

def dibujar_run_fallido():
    """Pantalla cuando perdes un stage — con la figura del enemigo triunfante."""
    pantalla.fill(NEGRO)
    cx = ANCHO // 2
    t = pygame.time.get_ticks() - run_fallido_t
    t_anim = pygame.time.get_ticks() / 1000.0

    # flash rojo sutil al entrar (300ms)
    if t < 300:
        alpha_f = int(60 * (1.0 - t / 300.0))
        flash_s = pygame.Surface((ANCHO, ALTO))
        flash_s.set_alpha(alpha_f)
        flash_s.fill((255, 30, 30))
        pantalla.blit(flash_s, (0, 0))

    # FIGURA DEL ENEMIGO: se dibuja grande y roja, pulsando (triunfante)
    # Usa los mismos parámetros de la canción que se estaba jugando.
    if partida and partida.get("cancion"):
        liss = partida["cancion"].get("lissajous")
        if liss and t > 200:
            _fa = min(1.0, (t - 200) / 800.0)  # fade in de la figura
            tipo = liss.get("tipo", "lissajous")
            npts = liss["puntos"]
            vel = liss["vel"]
            _t_fig = t_anim * vel
            # pulso amenazante (late lento y fuerte)
            pulso = 0.7 + 0.3 * math.sin(t_anim * 2.5)
            esc = 0.85 + pulso * 0.15
            _fcx = cx
            _fcy = 280
            _frx = 160 * esc
            _fry = 120 * esc
            puntos_fig = _curva_fondo(tipo, liss, npts, _t_fig,
                                      _fcx, _fcy, _frx, _fry, jitter=1.5)
            if len(puntos_fig) > 1:
                _r = int(min(255, 180 * pulso * _fa))
                _g = int(min(255, 40 * pulso * _fa))
                _b = int(min(255, 40 * pulso * _fa))
                pygame.draw.lines(pantalla, (_r, _g, _b), False, puntos_fig, 2)
                # interior mas tenue
                puntos_int = _curva_fondo(tipo, liss, npts, -_t_fig * 0.6,
                                          _fcx, _fcy, _frx * 0.6, _fry * 0.6,
                                          fase_extra=1.0, jitter=0.5)
                if len(puntos_int) > 1:
                    _ri = int(_r * 0.4)
                    _gi = int(_g * 0.4)
                    _bi = int(_b * 0.4)
                    pygame.draw.lines(pantalla, (_ri, _gi, _bi), False, puntos_int, 1)

    # titulo "RUN FALLIDO" con efecto glitch (tiembla los primeros 800ms)
    y_titulo = 60
    if t < 800:
        gx = random.randint(-4, 4)
        gy = random.randint(-2, 2)
        for _ in range(3):
            sl_y = random.randint(y_titulo - 10, y_titulo + 50)
            sl_w = random.randint(60, 200)
            sl_x = random.randint(0, ANCHO)
            pygame.draw.rect(pantalla, (255, 40, 40), (sl_x, sl_y, sl_w, 2))
    else:
        gx, gy = 0, 0
    titulo = fuente_grande.render("RUN FALLIDO", True, BLANCO)
    pantalla.blit(titulo, (cx - titulo.get_width() // 2 + gx, y_titulo + gy))

    # linea separadora (wipe)
    line_y = 125
    if t > 400:
        line_prog = min(1.0, (t - 400) / 300.0)
        lw = int((ANCHO - 120) * line_prog)
        pygame.draw.line(pantalla, GRIS, (60, line_y), (60 + lw, line_y), 1)

    # helper fade
    def _fade(surf, x, y, t_aparece):
        if t < t_aparece:
            return
        a = min(255, int(255 * (t - t_aparece) / 300.0))
        surf.set_alpha(a)
        pantalla.blit(surf, (x, y))

    # nombre del enemigo que te derroto
    if partida and partida.get("cancion"):
        _enem_n = partida["cancion"].get("lissajous", {}).get("nombre", "???")
        _en_txt = fuente.render(_enem_n, True, (255, 100, 100))
        _fade(_en_txt, cx - _en_txt.get_width() // 2, 145, 600)

    # subtitulo con stage donde caiste
    stage_n = run_actual["stage"] if run_actual else 1
    sub = fuente_chica.render(f"CAISTE EN STAGE {stage_n}/{NUM_STAGES}", True, GRIS_MED)
    _fade(sub, cx - sub.get_width() // 2, 185, 800)

    # dificultad
    if run_actual:
        dif_nom = DIFICULTADES.get(run_actual["nivel"], {}).get("nombre", "?")
        dif_txt = fuente_chica.render(dif_nom, True, GRIS)
        _fade(dif_txt, cx - dif_txt.get_width() // 2, 210, 900)

    # barra visual de stages
    if run_actual and t > 1000:
        bar_y = 420
        bar_w = 50
        bar_gap = 16
        total_w = NUM_STAGES * bar_w + (NUM_STAGES - 1) * bar_gap
        bx0 = cx - total_w // 2
        for i in range(NUM_STAGES):
            bx = bx0 + i * (bar_w + bar_gap)
            st_delay = 1000 + i * 150
            if t < st_delay:
                continue
            a_st = min(255, int(255 * (t - st_delay) / 200.0))
            if i + 1 < stage_n:
                col_st = (60, 200, 80)
            elif i + 1 == stage_n:
                blink = 0.6 + 0.4 * math.sin(t_anim * 6)
                col_st = (int(255 * blink), int(50 * blink), int(50 * blink))
            else:
                col_st = (50, 50, 55)
            s_surf = pygame.Surface((bar_w, 30))
            s_surf.set_alpha(a_st)
            s_surf.fill(col_st)
            pantalla.blit(s_surf, (bx, bar_y))
            sn = fuente_chica.render(str(i + 1), True, BLANCO)
            sn.set_alpha(a_st)
            pantalla.blit(sn, (bx + bar_w // 2 - sn.get_width() // 2, bar_y + 6))

    # puntos
    if run_actual and t > 1600:
        pts = partida.get("puntos", 0) if partida else run_actual.get("puntos_total", 0)
        pts_txt = fuente_chica.render(f"PUNTOS: {pts}", True, GRIS_MED)
        _fade(pts_txt, cx - pts_txt.get_width() // 2, 470, 1600)

    # controles (visibles y claros)
    if t > 1800:
        ctrl = fuente.render("ESPACIO = CONTINUAR", True, BLANCO)
        _fade(ctrl, cx - ctrl.get_width() // 2, 510, 1800)
        esc = fuente_chica.render("ESC = VOLVER AL MENU", True, GRIS)
        _fade(esc, cx - esc.get_width() // 2, 545, 1900)

def dibujar_mods():
    pantalla.fill(NEGRO)
    titulo = fuente_grande.render("MODIFICADORES", True, BLANCO)
    pantalla.blit(titulo, (ANCHO // 2 - titulo.get_width() // 2, 40))
    pygame.draw.line(pantalla, BLANCO, (60, 100), (ANCHO - 60, 100), 2)

    sub = fuente_chica.render("SUBEN EL MULTIPLICADOR DE PUNTOS", True, GRIS_MED)
    pantalla.blit(sub, (ANCHO // 2 - sub.get_width() // 2, 115))

    y0 = 145
    fila_h = 38   # achicado de 42 a 38: con 11 mods (antes 8) no entraba el total
    for i, m in enumerate(MODIFICADORES):
        y = y0 + i * fila_h
        sel = (i == mods_opcion)
        activo = m["id"] in mods_activos
        # checkbox
        box_x = 90
        pygame.draw.rect(pantalla, GRIS, (box_x, y, 20, 20), 2)
        if activo:
            pygame.draw.rect(pantalla, BLANCO, (box_x + 4, y + 4, 12, 12))
        # nombre + descripcion
        color = BLANCO if sel else GRIS_MED
        marca = "> " if sel else "  "
        nom = fuente.render(f"{marca}{m['nombre']}", True, color)
        pantalla.blit(nom, (box_x + 40, y - 4))
        desc = fuente_chica.render(m["desc"], True, GRIS)
        pantalla.blit(desc, (box_x + 40, y + 20))
        # multiplicador
        mult_txt = fuente_chica.render(f"x{m['mult']}", True, color)
        pantalla.blit(mult_txt, (ANCHO - 120, y + 2))

    # multiplicador total
    mult_total = calcular_mult_mods()
    linea_y = y0 + len(MODIFICADORES) * fila_h + 8
    pygame.draw.line(pantalla, GRIS, (60, linea_y), (ANCHO - 60, linea_y), 1)
    total_txt = fuente.render(f"MULTIPLICADOR TOTAL: x{mult_total:.2f}", True, BLANCO)
    pantalla.blit(total_txt, (ANCHO // 2 - total_txt.get_width() // 2, linea_y + 12))

    ayuda1 = fuente_chica.render("ARRIBA/ABAJO = ELEGIR   ESPACIO = ACTIVAR", True, GRIS)
    pantalla.blit(ayuda1, (ANCHO // 2 - ayuda1.get_width() // 2, 540))
    ayuda2 = fuente_chica.render("ENTER = JUGAR   ESC = VOLVER", True, GRIS)
    pantalla.blit(ayuda2, (ANCHO // 2 - ayuda2.get_width() // 2, 565))

def dibujar_pausa(partida):
    """Dibuja overlay de pausa sobre el juego congelado"""
    # fondo semi-transparente
    overlay = pygame.Surface((ANCHO, ALTO))
    overlay.fill(NEGRO)
    overlay.set_alpha(180)
    pantalla.blit(overlay, (0, 0))
    # titulo
    titulo = fuente_grande.render("PAUSA", True, BLANCO)
    pantalla.blit(titulo, (ANCHO // 2 - titulo.get_width() // 2, 160))
    pygame.draw.line(pantalla, BLANCO, (200, 220), (ANCHO - 200, 220), 2)
    # info de partida
    info = fuente_chica.render(
        f"{partida['cancion'].get('genero','')}  {partida['cancion']['instrumento']}  "
        f"{partida['cancion']['bpm']}BPM  SEED {int(partida['seed'])}",
        True, GRIS_MED)
    pantalla.blit(info, (ANCHO // 2 - info.get_width() // 2, 240))
    # opciones: 0=continuar, 1=volumen, 2=audio, 3=reiniciar, 4=salir
    opciones = ["CONTINUAR", "VOLUMEN", "AUDIO", "REINICIAR", "SALIR"]
    for i, txt in enumerate(opciones):
        y = 275 + i * 42
        sel = (i == pausa_opcion)
        marca = "> " if sel else "  "
        color = BLANCO if sel else GRIS_MED
        if i == 1:
            # barra de volumen
            t = fuente.render(f"{marca}{txt}", True, color)
            pantalla.blit(t, (100, y))
            barra_w = 160
            barra_x = 390
            pygame.draw.rect(pantalla, GRIS, (barra_x, y + 6, barra_w, 14))
            relleno = int(barra_w * config["volumen"])
            pygame.draw.rect(pantalla, color, (barra_x, y + 6, relleno, 14))
            pygame.draw.rect(pantalla, BLANCO, (barra_x, y + 6, barra_w, 14), 1)
            pct = fuente_chica.render(f"{int(config['volumen'] * 100)}%", True, color)
            pantalla.blit(pct, (barra_x + barra_w + 10, y + 6))
        elif i == 2:
            # selector de dispositivo de audio
            t = fuente.render(f"{marca}{txt}", True, color)
            pantalla.blit(t, (100, y))
            dev_name = AUDIO_DEVICES[config["audio_idx"]] if config["audio_idx"] < len(AUDIO_DEVICES) else "Default"
            if len(dev_name) > 20:
                dev_name = dev_name[:18] + ".."
            dev_txt = fuente_chica.render(dev_name, True, color)
            pantalla.blit(dev_txt, (390, y + 6))
        else:
            t = fuente.render(f"{marca}{txt}", True, color)
            pantalla.blit(t, (ANCHO // 2 - t.get_width() // 2, y))
    # ayuda
    ayuda = fuente_chica.render("ESC = CONTINUAR     FLECHAS + ENTER", True, GRIS)
    pantalla.blit(ayuda, (ANCHO // 2 - ayuda.get_width() // 2, 500))

def dibujar_config():
    pantalla.fill(NEGRO)
    titulo = fuente_grande.render("CONFIG", True, BLANCO)
    pantalla.blit(titulo, (ANCHO // 2 - titulo.get_width() // 2, 60))
    pygame.draw.line(pantalla, BLANCO, (60, 120), (ANCHO - 60, 120), 2)

    opciones = [
        ("BRILLO", config["brillo"], "barra"),
        ("VOLUMEN", config["volumen"], "barra"),
        ("VOL. MENU", config["vol_menu"], "barra"),
        ("RESOLUCION", config["res_idx"], "res"),
        ("AUDIO", config["audio_idx"], "audio"),
        ("TECLAS", 0, "teclas"),
        ("TECLADO MUSICAL", 0, "linein"),
    ]
    y0 = 145
    for i, (nombre, valor, tipo) in enumerate(opciones):
        y = y0 + i * 48
        sel = (i == config_opcion)
        marca = "> " if sel else "  "
        color = BLANCO if sel else GRIS_MED
        etq = fuente.render(f"{marca}{nombre}", True, color)
        pantalla.blit(etq, (80, y))

        if tipo == "barra":
            barra_w = 250
            barra_x = ANCHO - barra_w - 80
            pygame.draw.rect(pantalla, GRIS, (barra_x, y + 4, barra_w, 16))
            relleno = int(barra_w * valor)
            pygame.draw.rect(pantalla, color, (barra_x, y + 4, relleno, 16))
            pygame.draw.rect(pantalla, BLANCO, (barra_x, y + 4, barra_w, 16), 1)
            pct = fuente_chica.render(f"{int(valor * 100)}%", True, color)
            pantalla.blit(pct, (barra_x + barra_w + 12, y + 4))
        elif tipo == "res":
            w, h = RESOLUCIONES[valor]
            res_txt = fuente.render(f"{w}x{h}", True, color)
            pantalla.blit(res_txt, (ANCHO - 300, y))
        elif tipo == "audio":
            dev_name = AUDIO_DEVICES[valor] if valor < len(AUDIO_DEVICES) else "Default"
            if len(dev_name) > 24:
                dev_name = dev_name[:22] + ".."
            dev_txt = fuente_chica.render(dev_name, True, color)
            pantalla.blit(dev_txt, (ANCHO - 300, y + 6))
        elif tipo == "teclas":
            keys_str = " ".join(LABELS[:min(8, len(LABELS))])
            keys_txt = fuente_chica.render(keys_str, True, color)
            pantalla.blit(keys_txt, (ANCHO - 300, y + 6))
        elif tipo == "linein":
            estado_li = "ACTIVO" if linein_activo else ("CALIBRADO" if linein_notas_cal else "ENTER PARA CONFIGURAR")
            li_col = (140, 230, 100) if linein_activo else ((255, 180, 60) if linein_notas_cal else GRIS)
            li_txt = fuente_chica.render(estado_li, True, li_col if sel else color)
            pantalla.blit(li_txt, (ANCHO - 300, y + 6))

    ayuda1 = fuente_chica.render("ARRIBA/ABAJO = ELEGIR   IZQ/DER = AJUSTAR", True, GRIS)
    pantalla.blit(ayuda1, (ANCHO // 2 - ayuda1.get_width() // 2, 500))
    ayuda2 = fuente_chica.render("ENTER = ABRIR SUBMENU   ESC = VOLVER", True, GRIS)
    pantalla.blit(ayuda2, (ANCHO // 2 - ayuda2.get_width() // 2, 520))

def aplicar_resolucion():
    global ventana
    w, h = RESOLUCIONES[config["res_idx"]]
    ventana = pygame.display.set_mode((w, h))

def cambiar_audio_device(idx):
    """Reinicializa el mixer con el dispositivo seleccionado."""
    global SND_ERROR, SND_EXPLOSION, SND_EXPLOSION_BIG, SND_WIN
    global SND_SELECT, SND_CONFIRM, SND_GAMEOVER, SND_DADO
    global SND_HIT_PERFECT, SND_HIT_GOOD, SND_COMBO
    global cache_por_instrumento, cache_largas_por_instrumento
    config["audio_idx"] = idx
    try:
        pygame.mixer.quit()
        if idx == 0:
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=AUDIO_BUFFER)
        else:
            nombre = AUDIO_DEVICES[idx]
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=AUDIO_BUFFER, devicename=nombre)
        pygame.mixer.set_num_channels(AUDIO_CANALES)
        # reconstruir sonidos globales
        SND_ERROR = synth_error()
        SND_EXPLOSION = synth_explosion(1.0)
        SND_EXPLOSION_BIG = synth_explosion(2.0)
        SND_WIN = synth_fanfarria_win()
        SND_SELECT = synth_ui_select()
        SND_CONFIRM = synth_ui_confirm()
        SND_GAMEOVER = synth_game_over()
        SND_DADO = synth_dado_tick()
        SND_HIT_PERFECT = [synth_hit(900 * (2 ** (i / 12.0)), brillo=1.0) for i in range(8)]
        SND_HIT_GOOD = synth_hit_soft(600)
        SND_COMBO = [synth_combo(i) for i in range(1, 9)]
        cache_por_instrumento.clear()
        cache_largas_por_instrumento.clear()
    except Exception as e:
        print(f"Error cambiando audio: {e}")
        pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=AUDIO_BUFFER)
        pygame.mixer.set_num_channels(AUDIO_CANALES)
        SND_ERROR = synth_error()
        config["audio_idx"] = 0

# --- SISTEMA DE REBIND DE TECLAS (para controlador custom / arcade) ---
# Las teclas se guardan en bindings.json. Si no existe, usa el default
# A-S-D-F-G-H-J-K. La pantalla de rebind se accede desde CONFIG.
BINDINGS_FILE = os.path.join(BASE_DIR, "bindings.json")

def cargar_bindings():
    """Carga el mapeo tecla->columna desde bindings.json."""
    try:
        with open(BINDINGS_FILE, "r") as f:
            data = json.load(f)
            # data es {str(keycode): col_index, ...}
            return {int(k): v for k, v in data.items()}
    except:
        # default: A=0, S=1, D=2, F=3, G=4, H=5, J=6, K=7
        return dict(COLUMNAS)

def guardar_bindings(bindings):
    """Guarda el mapeo tecla->columna."""
    try:
        with open(BINDINGS_FILE, "w") as f:
            json.dump({str(k): v for k, v in bindings.items()}, f, indent=2)
    except Exception as e:
        print(f"Error guardando bindings: {e}")

def nombre_tecla(keycode):
    """Nombre legible de una tecla de pygame."""
    return pygame.key.name(keycode).upper()

def aplicar_bindings():
    """Copia los bindings cargados al dict COLUMNAS global."""
    global COLUMNAS, LABELS
    bindings = cargar_bindings()
    COLUMNAS.clear()
    COLUMNAS.update(bindings)
    # reconstruir labels en orden de columna
    por_col = sorted(bindings.items(), key=lambda x: x[1])
    LABELS = [nombre_tecla(k) for k, _ in por_col]

# aplicar al arrancar
aplicar_bindings()

# estado del rebind
rebind_col = 0       # columna que estamos asignando (0-7)
rebind_esperando = False  # True = esperando que el usuario aprete una tecla
rebind_bindings = {}  # bindings temporales mientras se configura

def dibujar_rebind():
    """Pantalla de reasignacion de teclas."""
    pantalla.fill(NEGRO)
    cx = ANCHO // 2
    t_anim = pygame.time.get_ticks() / 1000.0

    titulo = fuente_grande.render("ASIGNAR TECLAS", True, (0, 220, 255))
    pantalla.blit(titulo, (cx - titulo.get_width() // 2, 40))
    pygame.draw.line(pantalla, (0, 220, 255), (60, 100), (ANCHO - 60, 100), 1)

    sub = fuente_chica.render("ASIGNA UNA TECLA A CADA COLUMNA DEL JUEGO", True, GRIS_MED)
    pantalla.blit(sub, (cx - sub.get_width() // 2, 115))

    # mostrar las 8 columnas con su tecla asignada
    y0 = 160
    fila_h = 45
    for i in range(8):
        y = y0 + i * fila_h
        es_actual = (i == rebind_col)
        ya_asignada = i in rebind_bindings.values()

        # buscar qué tecla tiene asignada esta columna
        tecla_asignada = None
        for k, v in rebind_bindings.items():
            if v == i:
                tecla_asignada = k
                break

        if es_actual and rebind_esperando:
            # parpadeante: esperando input
            blink = (int(t_anim * 4) % 2 == 0)
            col_fondo = (60, 60, 20) if blink else (30, 30, 10)
            pygame.draw.rect(pantalla, col_fondo, (100, y, ANCHO - 200, fila_h - 6))
            pygame.draw.rect(pantalla, (255, 220, 60), (100, y, ANCHO - 200, fila_h - 6), 2)
            col_txt = (255, 220, 60)
            tecla_str = "APRETA UNA TECLA..."
        elif es_actual:
            pygame.draw.rect(pantalla, (30, 40, 50), (100, y, ANCHO - 200, fila_h - 6))
            pygame.draw.rect(pantalla, BLANCO, (100, y, ANCHO - 200, fila_h - 6), 2)
            col_txt = BLANCO
            tecla_str = nombre_tecla(tecla_asignada) if tecla_asignada else "---"
        else:
            col_txt = GRIS_MED if ya_asignada else GRIS
            tecla_str = nombre_tecla(tecla_asignada) if tecla_asignada else "---"

        # columna numero
        num = fuente.render(f"COL {i + 1}", True, col_txt)
        pantalla.blit(num, (120, y + 6))

        # tecla asignada
        tk = fuente.render(tecla_str, True, col_txt)
        pantalla.blit(tk, (350, y + 6))

    # instrucciones
    inst_y = y0 + 8 * fila_h + 10
    if rebind_esperando:
        inst = fuente_chica.render("APRETA LA TECLA QUE QUIERAS PARA ESTA COLUMNA", True, (255, 220, 60))
    elif rebind_col >= 8:
        inst = fuente_chica.render("ENTER = GUARDAR Y SALIR     ESC = CANCELAR", True, (140, 230, 100))
    else:
        inst = fuente_chica.render("ENTER = ASIGNAR TECLA     ESC = CANCELAR", True, GRIS_MED)
    pantalla.blit(inst, (cx - inst.get_width() // 2, inst_y))

    if rebind_col >= 8:
        listo = fuente.render("LISTO!", True, (140, 230, 100))
        pantalla.blit(listo, (cx - listo.get_width() // 2, inst_y + 30))

# --- TECLADO MUSICAL POR LINE-IN (deteccion de pitch) ---
try:
    import sounddevice as sd
    LINEIN_DISPONIBLE = True
    print("sounddevice disponible: teclado musical por line-in habilitado")
except ImportError:
    LINEIN_DISPONIBLE = False
    print("sounddevice no disponible: solo teclado (pip install sounddevice)")

LINEIN_FILE = os.path.join(BASE_DIR, "linein_notas.json")
LINEIN_SR = 22050
LINEIN_BLOCK = 512
LINEIN_THRESHOLD_ON = 0.035   # umbral para onset (subido: ignora colas de piano)
LINEIN_THRESHOLD_OFF = 0.008  # umbral para silencio
LINEIN_DEBOUNCE_MS = 80       # ms minimo entre triggers DE LA MISMA COLUMNA
LINEIN_SILENCIO_MS = 80       # ms de silencio para resetear (bajado: resetea mas rapido)
LINEIN_OFFSET_MS = 80
LINEIN_AUTO_RELEASE_MS = 120  # ms despues del onset, soltar la tecla automaticamente          # compensacion de latencia (ms). Ajustable en config.

linein_activo = False
linein_stream = None
linein_queue = queue.Queue(maxsize=32)
linein_notas_cal = {}
linein_last_col = -1
linein_last_time = 0
linein_last_time_per_col = {}  # {col: timestamp} debounce por columna
linein_energy = 0.0
linein_freq_actual = 0.0
linein_nota_activa = -1   # columna que esta sonando AHORA (-1 = silencio)
linein_en_silencio = True  # True = no hay nota sonando (esperando onset)
linein_silencio_desde = 0  # timestamp de cuando empezó el silencio
linein_energy_prev = 0.0   # energia del bloque anterior (para detectar ataque)
LINEIN_ATTACK_RATIO = 1.4  # ratio de energia actual/anterior para detectar ataque (bajado para notas rapidas)
linein_monitor = False     # True = reproducir el audio de entrada por los parlantes

def _detectar_pitch(data):
    """Detecta LA frecuencia fundamental del audio (una sola nota).
    Devuelve (freq, energia_rms). freq=0 si no hay señal clara."""
    mono = data[:, 0] if data.ndim > 1 else data
    rms = float(np.sqrt(np.mean(mono ** 2)))
    if rms < LINEIN_THRESHOLD_OFF:
        return 0.0, rms
    ventana = mono * np.hanning(len(mono))
    espectro = np.abs(np.fft.rfft(ventana))
    freqs = np.fft.rfftfreq(len(ventana), 1.0 / LINEIN_SR)
    mask = (freqs >= 60) & (freqs <= 2000)
    if not np.any(mask):
        return 0.0, rms
    espectro_m = espectro[mask]
    freqs_m = freqs[mask]
    promedio = np.mean(espectro_m)
    if promedio < 1e-10:
        return 0.0, rms
    idx1 = np.argmax(espectro_m)
    if espectro_m[idx1] < promedio * 2.5:
        return 0.0, rms
    freq = float(freqs_m[idx1])
    # si el pico mas alto es un armonico (>400Hz), verificar si hay un
    # sub-armonico fuerte (la fundamental real). Algunos instrumentos
    # tienen el 2do armonico mas fuerte que la fundamental.
    if freq > 400:
        sub = freq / 2.0
        idx_sub = np.argmin(np.abs(freqs_m - sub))
        if espectro_m[idx_sub] > promedio * 1.5:
            freq = float(freqs_m[idx_sub])
    return freq, rms

def _nota_mas_cercana(freq, notas_cal):
    if freq <= 0 or not notas_cal:
        return -1
    mejor_col, mejor_dist = -1, 999
    for col, freq_cal in notas_cal.items():
        if freq_cal <= 0:
            continue
        semitonos = abs(12 * math.log2(freq / freq_cal))
        if semitonos < mejor_dist:
            mejor_dist = semitonos
            mejor_col = col
    return mejor_col if mejor_dist <= 1.5 else -1

def _linein_callback_duplex(indata, outdata, frames, time_info, status):
    """Callback para stream duplex: detecta pitch + monitorea audio."""
    # monitoreo: copiar entrada a salida para que el jugador escuche
    if linein_monitor:
        outdata[:] = indata
    else:
        outdata[:] = 0
    # deteccion de pitch (misma logica que antes)
    _linein_callback_proceso(indata)

def _linein_callback_solo(indata, frames, time_info, status):
    """Callback para stream solo input (sin monitoreo)."""
    _linein_callback_proceso(indata)

def _linein_callback_proceso(indata):
    """Logica compartida de deteccion de pitch."""
    global linein_last_col, linein_last_time, linein_energy, linein_freq_actual
    global linein_nota_activa, linein_en_silencio, linein_silencio_desde
    global linein_energy_prev
    freq, rms = _detectar_pitch(indata)
    linein_energy = rms
    linein_freq_actual = freq
    ahora = pygame.time.get_ticks()

    es_ataque = (rms >= LINEIN_THRESHOLD_ON
                 and linein_energy_prev > 0.001
                 and rms / linein_energy_prev >= LINEIN_ATTACK_RATIO)
    linein_energy_prev = rms

    if rms < LINEIN_THRESHOLD_OFF:
        if linein_silencio_desde == 0:
            linein_silencio_desde = ahora
        if (ahora - linein_silencio_desde) >= LINEIN_SILENCIO_MS:
            if not linein_en_silencio:
                linein_en_silencio = True
                linein_nota_activa = -1
        return

    linein_silencio_desde = 0
    if freq <= 0:
        return

    col = _nota_mas_cercana(freq, linein_notas_cal)
    if col < 0:
        return

    disparar = False
    if linein_en_silencio and rms >= LINEIN_THRESHOLD_ON:
        disparar = True
        linein_en_silencio = False
    elif es_ataque:
        disparar = True
    elif not linein_en_silencio and col != linein_nota_activa:
        disparar = True

    if disparar:
        # debounce PER-COLUMNA: solo bloquea la misma columna, no las demas.
        # Asi podes tocar col 0 y col 1 rapido sin que se bloqueen entre si.
        t_ultima = linein_last_time_per_col.get(col, 0)
        if (ahora - t_ultima) < LINEIN_DEBOUNCE_MS:
            return
        linein_nota_activa = col
        linein_last_col = col
        linein_last_time = ahora
        linein_last_time_per_col[col] = ahora
        try:
            linein_queue.put_nowait(("down", col, ahora))
        except queue.Full:
            pass

def linein_abrir(device_idx, con_monitor=False):
    """Abre el stream de line-in. Si con_monitor=True, usa stream duplex
    para que el audio de entrada se reproduzca por los parlantes."""
    global linein_stream, linein_activo, linein_monitor
    linein_detener()
    linein_monitor = con_monitor
    try:
        if con_monitor:
            linein_stream = sd.Stream(
                device=(device_idx, None),  # input=device, output=default
                samplerate=LINEIN_SR, channels=1,
                blocksize=LINEIN_BLOCK, dtype="float32",
                callback=_linein_callback_duplex)
        else:
            linein_stream = sd.InputStream(
                device=device_idx,
                samplerate=LINEIN_SR, channels=1,
                blocksize=LINEIN_BLOCK, dtype="float32",
                callback=_linein_callback_solo)
        linein_stream.start()
        linein_activo = True
        print(f"Line-in abierto {'con' if con_monitor else 'sin'} monitoreo")
        return True
    except Exception as e:
        print(f"Error abriendo line-in: {e}")
        return False

def linein_detener():
    global linein_stream, linein_activo
    if linein_stream:
        try:
            linein_stream.stop()
            linein_stream.close()
        except:
            pass
    linein_stream = None
    linein_activo = False

linein_release_pendientes = []  # [(timestamp_release, col)]

def linein_procesar_eventos(partida_ref):
    """Drena la cola de eventos del line-in, inyecta DOWN y programa
    auto-release (UP) para que teclas_sostenidas no se quede pegada."""
    global linein_release_pendientes
    ahora = pygame.time.get_ticks()
    # procesar releases pendientes
    nuevos = []
    for t_rel, col_rel in linein_release_pendientes:
        if ahora >= t_rel:
            ev = pygame.event.Event(pygame.KEYUP, key=None, _linein_col_up=col_rel)
            pygame.event.post(ev)
        else:
            nuevos.append((t_rel, col_rel))
    linein_release_pendientes = nuevos
    # procesar nuevos downs
    while not linein_queue.empty():
        try:
            tipo, col, ts = linein_queue.get_nowait()
            if tipo == "down":
                if partida_ref:
                    col_mapeada = partida_ref.get("mapa_teclas", {}).get(col, col)
                    if col_mapeada < partida_ref["dificultad"]["columnas"]:
                        ev = pygame.event.Event(pygame.KEYDOWN, key=None,
                                                _linein_col=col_mapeada,
                                                _linein_offset=LINEIN_OFFSET_MS)
                        pygame.event.post(ev)
                        linein_release_pendientes.append(
                            (ahora + LINEIN_AUTO_RELEASE_MS, col_mapeada))
                else:
                    ev = pygame.event.Event(pygame.KEYDOWN, key=None,
                                            _linein_col=col,
                                            _linein_offset=LINEIN_OFFSET_MS)
                    pygame.event.post(ev)
        except queue.Empty:
            break

def cargar_linein_notas():
    global linein_notas_cal, LINEIN_OFFSET_MS
    try:
        with open(LINEIN_FILE, "r") as f:
            data = json.load(f)
            if "notas" in data:
                # formato nuevo: {notas: {col: freq}, offset: ms, device: nombre}
                linein_notas_cal = {int(k): v for k, v in data["notas"].items()}
                LINEIN_OFFSET_MS = data.get("offset", 80)
            else:
                # formato viejo: {col: freq} directo
                linein_notas_cal = {int(k): v for k, v in data.items()}
    except:
        linein_notas_cal = {}

def guardar_linein_notas():
    try:
        # buscar nombre del dispositivo activo
        dev_nombre = ""
        if linein_devices and linein_dev_idx < len(linein_devices):
            dev_nombre = linein_devices[linein_dev_idx].get("nombre", "")
        data = {
            "notas": {str(k): v for k, v in linein_notas_cal.items()},
            "offset": LINEIN_OFFSET_MS,
            "device": dev_nombre,
        }
        with open(LINEIN_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Error guardando calibracion: {e}")

NOTAS_NOMBRE = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
def freq_a_nota(freq):
    if freq <= 0:
        return "---"
    midi = 69 + 12 * math.log2(freq / 440.0)
    midi_r = round(midi)
    nombre = NOTAS_NOMBRE[midi_r % 12]
    octava = (midi_r // 12) - 1
    cents = int((midi - midi_r) * 100)
    return f"{nombre}{octava}" + (f" {cents:+d}c" if abs(cents) > 5 else "")

linein_cal_col = 0
linein_cal_estado = "idle"
linein_cal_muestras = []
linein_dev_idx = 0        # dispositivo de entrada seleccionado
linein_devices = []       # lista de dispositivos de entrada disponibles

def listar_dispositivos_entrada():
    """Lista los dispositivos de entrada de audio disponibles."""
    global linein_devices
    linein_devices = []
    if not LINEIN_DISPONIBLE:
        return
    try:
        devs = sd.query_devices()
        for i, d in enumerate(devs):
            if d["max_input_channels"] > 0:
                linein_devices.append({"idx": i, "nombre": d["name"]})
    except Exception as e:
        print(f"Error listando dispositivos: {e}")

def dibujar_linein_setup():
    """Pantalla de selección de dispositivo de entrada + opción de calibrar."""
    pantalla.fill(NEGRO)
    cx = ANCHO // 2

    titulo = fuente_grande.render("TECLADO MUSICAL", True, (255, 180, 60))
    pantalla.blit(titulo, (cx - titulo.get_width() // 2, 40))
    pygame.draw.line(pantalla, (255, 180, 60), (60, 100), (ANCHO - 60, 100), 1)

    if not LINEIN_DISPONIBLE:
        # sounddevice no instalado: mostrar instrucciones
        msg1 = fuente.render("REQUIERE SOUNDDEVICE", True, (255, 100, 100))
        pantalla.blit(msg1, (cx - msg1.get_width() // 2, 180))
        msg2 = fuente_chica.render("INSTALAR DESDE LA TERMINAL:", True, GRIS_MED)
        pantalla.blit(msg2, (cx - msg2.get_width() // 2, 240))
        cmd = fuente.render("pip install sounddevice", True, BLANCO)
        pantalla.blit(cmd, (cx - cmd.get_width() // 2, 280))
        msg3 = fuente_chica.render("EN LINUX/RPi TAMBIEN:", True, GRIS_MED)
        pantalla.blit(msg3, (cx - msg3.get_width() // 2, 340))
        cmd2 = fuente.render("sudo apt install libportaudio2", True, BLANCO)
        pantalla.blit(cmd2, (cx - cmd2.get_width() // 2, 370))
        msg4 = fuente_chica.render("REINICIAR EL JUEGO DESPUES DE INSTALAR", True, (255, 180, 60))
        pantalla.blit(msg4, (cx - msg4.get_width() // 2, 430))
        esc = fuente_chica.render("ESC = VOLVER", True, GRIS)
        pantalla.blit(esc, (cx - esc.get_width() // 2, ALTO - 40))
        return

    # estado actual
    if linein_activo:
        est = fuente.render("ESTADO: ACTIVO", True, (140, 230, 100))
    elif linein_notas_cal:
        est = fuente.render("ESTADO: CALIBRADO (INACTIVO)", True, (255, 180, 60))
    else:
        est = fuente.render("ESTADO: NO CONFIGURADO", True, GRIS_MED)
    pantalla.blit(est, (cx - est.get_width() // 2, 120))

    # dispositivos de entrada
    sub = fuente.render("DISPOSITIVO DE ENTRADA:", True, BLANCO)
    pantalla.blit(sub, (100, 175))

    if not linein_devices:
        no_dev = fuente_chica.render("NO SE ENCONTRARON DISPOSITIVOS DE ENTRADA", True, (255, 100, 100))
        pantalla.blit(no_dev, (cx - no_dev.get_width() // 2, 220))
    else:
        y0 = 215
        for i, dev in enumerate(linein_devices):
            y = y0 + i * 30
            if y > 420:
                mas = fuente_chica.render(f"... y {len(linein_devices) - i} mas", True, GRIS)
                pantalla.blit(mas, (120, y))
                break
            sel = (i == linein_dev_idx)
            nombre = dev["nombre"]
            if len(nombre) > 45:
                nombre = nombre[:43] + ".."
            marca = "> " if sel else "  "
            col = BLANCO if sel else GRIS_MED
            if sel:
                pygame.draw.rect(pantalla, (30, 30, 40), (90, y - 2, ANCHO - 180, 26))
            txt = fuente_chica.render(f"{marca}{nombre}", True, col)
            pantalla.blit(txt, (100, y))

    # opciones al pie
    pygame.draw.line(pantalla, GRIS, (60, 440), (ANCHO - 60, 440), 1)

    # control de offset
    off_txt = fuente.render(f"COMPENSACION: {LINEIN_OFFSET_MS}ms", True, BLANCO)
    pantalla.blit(off_txt, (cx - off_txt.get_width() // 2, 455))
    off_help = fuente_chica.render("IZQ/DER = AJUSTAR (+ = MENOS DELAY)", True, GRIS)
    pantalla.blit(off_help, (cx - off_help.get_width() // 2, 485))

    opciones_txt = []
    if linein_devices:
        opciones_txt.append("ENTER = CALIBRAR NOTAS")
    if linein_activo or linein_notas_cal:
        opciones_txt.append("D = MEDIR LATENCIA (RECOMENDADO)")
    if linein_notas_cal and not linein_activo:
        opciones_txt.append("A = ACTIVAR LINE-IN")
    if linein_activo:
        opciones_txt.append("A = DESACTIVAR LINE-IN")
    opciones_txt.append("ESC = VOLVER")

    for i, txt in enumerate(opciones_txt):
        col = (255, 180, 60) if "LATENCIA" in txt else ((140, 230, 100) if "ACTIVAR" in txt else GRIS_MED)
        t = fuente_chica.render(txt, True, col)
        pantalla.blit(t, (cx - t.get_width() // 2, 515 + i * 20))

def dibujar_calibracion_linein():
    pantalla.fill(NEGRO)
    cx = ANCHO // 2
    t_anim = pygame.time.get_ticks() / 1000.0
    titulo = fuente_grande.render("CALIBRAR TECLADO", True, (255, 180, 60))
    pantalla.blit(titulo, (cx - titulo.get_width() // 2, 30))
    pygame.draw.line(pantalla, (255, 180, 60), (60, 90), (ANCHO - 60, 90), 1)
    # VU meter
    vu_w, vu_x, vu_y = 300, cx - 150, 105
    pygame.draw.rect(pantalla, GRIS, (vu_x, vu_y, vu_w, 10))
    vu_level = min(1.0, linein_energy / 0.15)
    if vu_level > 0.01:
        vu_col = (100, 255, 100) if vu_level < 0.7 else (255, 200, 60) if vu_level < 0.9 else (255, 80, 80)
        pygame.draw.rect(pantalla, vu_col, (vu_x, vu_y, int(vu_w * vu_level), 10))
    pygame.draw.rect(pantalla, GRIS_MED, (vu_x, vu_y, vu_w, 10), 1)
    vu_lbl = fuente_chica.render("ENTRADA", True, GRIS)
    pantalla.blit(vu_lbl, (vu_x - 75, vu_y - 2))
    # indicador de monitoreo
    if linein_monitor:
        mon = fuente_chica.render("MONITOR ON (M)", True, (140, 230, 100))
    else:
        mon = fuente_chica.render("MONITOR OFF (M)", True, GRIS)
    pantalla.blit(mon, (vu_x + vu_w + 15, vu_y - 2))
    # columnas
    y0, fila_h = 135, 42
    for i in range(8):
        y = y0 + i * fila_h
        es_actual = (i == linein_cal_col and linein_cal_col < 8)
        ya_cal = i in linein_notas_cal
        if es_actual and linein_cal_estado == "escuchando":
            blink = (int(t_anim * 3) % 2 == 0)
            pygame.draw.rect(pantalla, (50, 30, 10) if blink else (30, 20, 5), (80, y, ANCHO - 160, fila_h - 4))
            pygame.draw.rect(pantalla, (255, 180, 60), (80, y, ANCHO - 160, fila_h - 4), 2)
            col_txt = (255, 180, 60)
        elif es_actual:
            pygame.draw.rect(pantalla, (30, 30, 40), (80, y, ANCHO - 160, fila_h - 4))
            pygame.draw.rect(pantalla, BLANCO, (80, y, ANCHO - 160, fila_h - 4), 2)
            col_txt = BLANCO
        else:
            col_txt = GRIS_MED if ya_cal else GRIS
        num = fuente.render(f"COL {i + 1}", True, col_txt)
        pantalla.blit(num, (100, y + 6))
        if ya_cal:
            freq = linein_notas_cal[i]
            info = fuente.render(f"{freq_a_nota(freq)}  ({freq:.0f}Hz)", True, col_txt)
            pantalla.blit(info, (280, y + 6))
        elif es_actual and linein_cal_estado == "escuchando":
            if linein_freq_actual > 0:
                live = fuente.render(f"{freq_a_nota(linein_freq_actual)}  ({linein_freq_actual:.0f}Hz)", True, (255, 220, 100))
                pantalla.blit(live, (280, y + 6))
            else:
                pantalla.blit(fuente_chica.render("TOCA UNA NOTA...", True, (255, 180, 60)), (280, y + 12))
        else:
            pantalla.blit(fuente_chica.render("---", True, GRIS), (280, y + 12))
    inst_y = y0 + 8 * fila_h + 10
    if linein_cal_estado == "escuchando":
        inst = fuente_chica.render("TOCA Y MANTENE LA NOTA     ENTER = CONFIRMAR     ESC = CANCELAR", True, (255, 180, 60))
    elif linein_cal_col >= 8:
        inst = fuente_chica.render("ENTER = GUARDAR     ESC = CANCELAR     R = RECALIBRAR", True, (140, 230, 100))
        listo = fuente.render("CALIBRACION COMPLETA!", True, (140, 230, 100))
        pantalla.blit(listo, (cx - listo.get_width() // 2, inst_y + 25))
    else:
        inst = fuente_chica.render("ENTER = ESCUCHAR NOTA     ESC = CANCELAR", True, GRIS_MED)
    pantalla.blit(inst, (cx - inst.get_width() // 2, inst_y))

cargar_linein_notas()

# auto-activar line-in si hay calibracion guardada
if LINEIN_DISPONIBLE and linein_notas_cal:
    try:
        _saved_dev = ""
        try:
            with open(LINEIN_FILE, "r") as _f:
                _saved = json.load(_f)
                _saved_dev = _saved.get("device", "")
        except:
            pass
        listar_dispositivos_entrada()
        _dev_encontrado = None
        for _i, _d in enumerate(linein_devices):
            if _saved_dev and _saved_dev in _d["nombre"]:
                _dev_encontrado = _d
                linein_dev_idx = _i
                break
        if not _dev_encontrado and linein_devices:
            _dev_encontrado = linein_devices[0]
            linein_dev_idx = 0
        if _dev_encontrado:
            linein_abrir(_dev_encontrado["idx"], con_monitor=False)
            print(f"Line-in auto-activado: {_dev_encontrado['nombre']} (offset {LINEIN_OFFSET_MS}ms)")
    except Exception as e:
        print(f"No se pudo auto-activar line-in: {e}")


# --- MEDICION DE LATENCIA DEL LINE-IN ---
latencia_muestras = []
latencia_flash_time = 0
latencia_flash_activo = False
latencia_esperando = False
latencia_intervalo = 2200
latencia_resultado = -1
LATENCIA_NUM_MUESTRAS = 6

def dibujar_medir_latencia():
    pantalla.fill(NEGRO)
    cx = ANCHO // 2
    ahora = pygame.time.get_ticks()
    titulo = fuente.render("MEDIR LATENCIA", True, (255, 180, 60))
    pantalla.blit(titulo, (cx - titulo.get_width() // 2, 30))
    pygame.draw.line(pantalla, (255, 180, 60), (60, 65), (ANCHO - 60, 65), 1)
    n_hechas = len(latencia_muestras)
    if n_hechas < LATENCIA_NUM_MUESTRAS:
        inst = fuente_chica.render("TOCA CUALQUIER NOTA CUANDO APARECE  YA!", True, GRIS_MED)
        pantalla.blit(inst, (cx - inst.get_width() // 2, 80))
        prog = fuente_chica.render(f"MUESTRA {n_hechas + 1} DE {LATENCIA_NUM_MUESTRAS}", True, GRIS)
        pantalla.blit(prog, (cx - prog.get_width() // 2, 105))
        radio = 90
        cy = ALTO // 2 - 10
        t_desde = ahora - latencia_flash_time
        # countdown: 0-1000ms = "1", 1000-2000ms = "2", 2000-3000ms = "3", 3000+ = "YA!"
        if latencia_flash_activo:
            # YA! — circulo blanco grande
            pygame.draw.circle(pantalla, BLANCO, (cx, cy), radio)
            lbl = fuente_grande.render("YA!", True, NEGRO)
            pantalla.blit(lbl, (cx - lbl.get_width() // 2, cy - lbl.get_height() // 2))
        elif latencia_esperando:
            # ya paso el flash, esperando respuesta
            pygame.draw.circle(pantalla, (60, 60, 70), (cx, cy), radio)
            pygame.draw.circle(pantalla, GRIS, (cx, cy), radio, 2)
            wait = fuente_chica.render("ESPERANDO...", True, GRIS_MED)
            pantalla.blit(wait, (cx - wait.get_width() // 2, cy - 8))
        else:
            # countdown 1, 2, 3
            if t_desde < 1000:
                num = "1"
                p = t_desde / 1000.0
            elif t_desde < 2000:
                num = "2"
                p = (t_desde - 1000) / 1000.0
            elif t_desde < 3000:
                num = "3"
                p = (t_desde - 2000) / 1000.0
            else:
                num = ""
                p = 0
            # circulo que crece con el countdown
            r_show = int(radio * 0.4 + radio * 0.6 * p)
            brillo = int(30 + 50 * p)
            pygame.draw.circle(pantalla, (brillo, brillo, brillo + 10), (cx, cy), r_show)
            pygame.draw.circle(pantalla, GRIS_MED, (cx, cy), r_show, 2)
            if num:
                # numero grande con pulso de escala
                escala_pulso = 1.0 + 0.3 * (1.0 - p)
                num_txt = fuente_grande.render(num, True, BLANCO)
                nw = int(num_txt.get_width() * escala_pulso)
                nh = int(num_txt.get_height() * escala_pulso)
                num_scaled = pygame.transform.scale(num_txt, (nw, nh))
                pantalla.blit(num_scaled, (cx - nw // 2, cy - nh // 2))
        # muestras anteriores
        if latencia_muestras:
            y_m = ALTO // 2 + 120
            for i, ms in enumerate(latencia_muestras):
                col_m = (140, 230, 100) if ms < 150 else (255, 180, 60) if ms < 250 else (255, 100, 100)
                mt = fuente_chica.render(f"#{i+1}: {ms}ms", True, col_m)
                pantalla.blit(mt, (cx - 120 + (i % 3) * 100, y_m + (i // 3) * 20))
        esc = fuente_chica.render("ESC = CANCELAR", True, GRIS)
        pantalla.blit(esc, (cx - esc.get_width() // 2, ALTO - 35))
        # indicador del offset actual + promedio parcial
        off_actual = fuente_chica.render(f"OFFSET ACTUAL: {LINEIN_OFFSET_MS}ms", True, GRIS)
        pantalla.blit(off_actual, (cx - off_actual.get_width() // 2, ALTO - 60))
        if latencia_muestras:
            _prom_parcial = sum(latencia_muestras) // len(latencia_muestras)
            prom_txt = fuente.render(f"PROMEDIO: {_prom_parcial}ms", True, (255, 180, 60))
            pantalla.blit(prom_txt, (cx - prom_txt.get_width() // 2, ALTO // 2 + 95))
    else:
        promedio = sum(latencia_muestras) // len(latencia_muestras)
        res_titulo = fuente.render("RESULTADO", True, (140, 230, 100))
        pantalla.blit(res_titulo, (cx - res_titulo.get_width() // 2, 130))
        res_val = fuente_grande.render(f"{promedio}ms", True, BLANCO)
        pantalla.blit(res_val, (cx - res_val.get_width() // 2, 190))
        y_m = 280
        for i, ms in enumerate(latencia_muestras):
            col_m = (140, 230, 100) if ms < 150 else (255, 180, 60) if ms < 250 else (255, 100, 100)
            mt = fuente_chica.render(f"#{i+1}: {ms}ms", True, col_m)
            pantalla.blit(mt, (cx - 120 + (i % 3) * 100, y_m + (i // 3) * 22))
        _min, _max = min(latencia_muestras), max(latencia_muestras)
        rng_txt = fuente_chica.render(f"MIN: {_min}ms  MAX: {_max}ms  VARIANZA: {_max - _min}ms", True, GRIS)
        pantalla.blit(rng_txt, (cx - rng_txt.get_width() // 2, 350))
        aplicar = fuente_chica.render(f"ENTER = APLICAR {promedio}ms COMO COMPENSACION", True, (140, 230, 100))
        pantalla.blit(aplicar, (cx - aplicar.get_width() // 2, 420))
        reintentar = fuente_chica.render("R = REPETIR     ESC = CANCELAR", True, GRIS)
        pantalla.blit(reintentar, (cx - reintentar.get_width() // 2, 450))

ESTADO         = "menu"
partida        = None
seed_acumulada = 0.0
cargando_seed  = False
teclas_sostenidas = set()
nombre_input   = ""
score_guardado = False
run_actual     = None
run_fallido_t  = 0
dev_mode       = False

# arrancar la musica del menu con una seed aleatoria (DIFICIL+)
dibujar_pantalla_carga(1.0, "MUSICA", 1, 1)
nueva_musica_menu_aleatoria()

corriendo = True
while corriendo:
    pantalla.fill(NEGRO)
    ahora_ms = pygame.time.get_ticks()

    for evento in pygame.event.get():
        if evento.type == pygame.QUIT:
            corriendo = False

        # F12: toggle modo desarrollador
        if evento.type == pygame.KEYDOWN and evento.key == pygame.K_F12:
            dev_mode = not dev_mode
            print(f"[DEV MODE] {'ON' if dev_mode else 'OFF'}")

        if ESTADO == "menu":
            if evento.type == pygame.KEYDOWN:
                if evento.key == pygame.K_UP:
                    menu_opcion = (menu_opcion - 1) % len(MENU_OPCIONES)
                    sfx_select()
                elif evento.key == pygame.K_DOWN:
                    menu_opcion = (menu_opcion + 1) % len(MENU_OPCIONES)
                    sfx_select()
                elif evento.key in (pygame.K_RETURN, pygame.K_SPACE):
                    sfx_confirm()
                    op = MENU_OPCIONES[menu_opcion]
                    if op == "JUGAR":
                        seed_acumulada = 0.0
                        cargando_seed = False
                        ESTADO = "selector_seed"
                    elif op == "INSTRUMENTO":
                        seed_acumulada = 0.0
                        cargando_seed = False
                        ESTADO = "selector_seed_inst"
                    elif op == "CARRERA":
                        c = cargar_carrera()
                        carrera_cursor = max(0, c.get("nivel_max", 1) - 1)
                        ESTADO = "carrera"
                    elif op == "TUTORIAL":
                        tutorial_pagina = 0
                        ESTADO = "tutorial"
                    elif op == "LEADERBOARD":
                        ESTADO = "leaderboard"
                    elif op == "CONFIG":
                        config_opcion = 0
                        ESTADO = "config"

        elif ESTADO == "selector_seed":
            if evento.type == pygame.KEYDOWN:
                if evento.key == pygame.K_SPACE:
                    cargando_seed = True
                if evento.key == pygame.K_ESCAPE:
                    seed_acumulada = 0.0
                    cargando_seed = False
                    ESTADO = "menu"
                if evento.key == pygame.K_RETURN and seed_acumulada > 0:
                    sfx_confirm()
                    run_actual = crear_run(int(seed_acumulada))
                    carrera_activa = False
                    modo_instrumento = False
                    ESTADO = "run_overview"
                if evento.key == pygame.K_m and seed_acumulada > 0:
                    sfx_confirm()
                    mods_opcion = 0
                    ESTADO = "mods"
                if evento.key == pygame.K_r:
                    seed_acumulada = 0.0
                    cargando_seed = False
            if evento.type == pygame.KEYUP:
                if evento.key == pygame.K_SPACE:
                    cargando_seed = False

        elif ESTADO == "selector_seed_inst":
            if evento.type == pygame.KEYDOWN:
                if evento.key == pygame.K_SPACE:
                    cargando_seed = True
                if evento.key == pygame.K_ESCAPE:
                    seed_acumulada = 0.0
                    cargando_seed = False
                    ESTADO = "menu"
                if evento.key == pygame.K_RETURN and seed_acumulada > 0:
                    sfx_confirm()
                    run_actual = crear_run(int(seed_acumulada))
                    carrera_activa = False
                    modo_instrumento = True
                    ESTADO = "run_overview"
                if evento.key == pygame.K_r:
                    seed_acumulada = 0.0
                    cargando_seed = False
            if evento.type == pygame.KEYUP:
                if evento.key == pygame.K_SPACE:
                    cargando_seed = False

        elif ESTADO == "tutorial":
            if evento.type == pygame.KEYDOWN:
                if evento.key == pygame.K_ESCAPE:
                    ESTADO = "menu"
                elif evento.key == pygame.K_LEFT:
                    if tutorial_pagina > 0:
                        tutorial_pagina -= 1
                        sfx_select()
                elif evento.key == pygame.K_RIGHT:
                    if tutorial_pagina < TUTORIAL_NUM_PAGINAS - 1:
                        tutorial_pagina += 1
                        sfx_select()
                elif evento.key in (pygame.K_SPACE, pygame.K_RETURN):
                    if tutorial_pagina < TUTORIAL_NUM_PAGINAS - 1:
                        tutorial_pagina += 1
                        sfx_select()
                    else:
                        # ultima pagina: arrancar la PRACTICA
                        sfx_confirm()
                        cortar_audio_suave()
                        partida = iniciar_partida(150, mods=set(), tutorial=True)
                        score_guardado = True   # la practica no guarda score
                        ESTADO = "jugando"

        elif ESTADO == "carrera":
            if evento.type == pygame.KEYDOWN:
                if evento.key == pygame.K_ESCAPE:
                    ESTADO = "menu"
                elif evento.key == pygame.K_UP:
                    carrera_cursor = max(0, carrera_cursor - 1)
                    sfx_select()
                elif evento.key == pygame.K_DOWN:
                    carrera_cursor = min(14, carrera_cursor + 1)
                    sfx_select()
                elif evento.key in (pygame.K_RETURN, pygame.K_SPACE):
                    nivel_sel = carrera_cursor + 1
                    c_data = cargar_carrera()
                    if nivel_sel <= c_data.get("nivel_max", 1):
                        sfx_confirm()
                        # seed aleatoria para este nivel
                        tramos = [1500, 2500, 3200, 3800, 4400, 5000, 5600, 6200, 6800,
                                  7300, 7800, 8300, 8800, 9400, 9999]
                        s_min = tramos[nivel_sel - 2] + 1 if nivel_sel >= 2 else 1
                        s_max = tramos[nivel_sel - 1]
                        seed_carrera = random.randint(s_min, s_max)
                        carrera_registrar_intento(nivel_sel)
                        run_actual = crear_run(seed_carrera)
                        carrera_activa = True
                        ESTADO = "run_overview"

        elif ESTADO == "run_overview":
            if evento.type == pygame.KEYDOWN:
                if evento.key == pygame.K_ESCAPE:
                    run_actual = None
                    ESTADO = "menu"
                    nueva_musica_menu_aleatoria()
                elif evento.key in (pygame.K_SPACE, pygame.K_RETURN):
                    sfx_confirm()
                    detener_musica_menu()
                    cortar_audio_suave()
                    idx = run_actual["stage"] - 1
                    seed_stage = run_actual["seeds"][idx]
                    mods_stage = run_actual["mods"][idx]
                    inst_stage = run_actual.get("instrumentos", [None]*NUM_STAGES)[idx]
                    dibujar_carga_seed(seed_stage)
                    partida = iniciar_partida(
                        seed_stage, mods=mods_stage,
                        stage_info={"n": run_actual["stage"]},
                        puntos_iniciales=run_actual["puntos_total"],
                        instrumento_forzado=inst_stage,
                        perks=run_actual.get("perks"))
                    score_guardado = False
                    # pre-render del instrumento del proximo stage en background
                    if run_actual["stage"] < NUM_STAGES:
                        inst_next = run_actual.get("instrumentos", [None]*NUM_STAGES)[idx + 1]
                        prerender_instrumento_seed(run_actual["seeds"][idx + 1], instrumento=inst_next)
                    ESTADO = "jugando"

        elif ESTADO == "perk_select":
            if evento.type == pygame.KEYDOWN:
                # bloquear input mientras entra la animacion de las cartas
                _perk_elapsed = pygame.time.get_ticks() - perk_anim_inicio
                _perk_anim_total = (len(perk_ofertas) - 1) * PERK_ANIM_STAGGER + PERK_ANIM_CARTA
                if _perk_elapsed < _perk_anim_total and evento.key != pygame.K_ESCAPE:
                    continue
                _perk_confirmar = False
                if evento.key in (pygame.K_1, pygame.K_KP1):
                    perk_seleccion = 0
                    _perk_confirmar = True
                elif evento.key in (pygame.K_2, pygame.K_KP2):
                    perk_seleccion = min(1, len(perk_ofertas) - 1)
                    _perk_confirmar = True
                elif evento.key in (pygame.K_3, pygame.K_KP3):
                    perk_seleccion = min(2, len(perk_ofertas) - 1)
                    _perk_confirmar = True
                elif evento.key == pygame.K_LEFT:
                    perk_seleccion = max(0, perk_seleccion - 1)
                    sfx_select()
                elif evento.key == pygame.K_RIGHT:
                    perk_seleccion = min(len(perk_ofertas) - 1, perk_seleccion + 1)
                    sfx_select()
                elif evento.key in (pygame.K_RETURN, pygame.K_SPACE):
                    _perk_confirmar = True
                elif evento.key == pygame.K_ESCAPE:
                    run_actual = None
                    ESTADO = "menu"
                    nueva_musica_menu_aleatoria()
                if _perk_confirmar and ESTADO == "perk_select":
                    elegido = perk_ofertas[perk_seleccion]
                    run_actual["perks"].append(elegido)
                    sfx_confirm()
                    run_actual["stage"] += 1
                    idx_next = run_actual["stage"] - 1
                    if run_actual["mods"][idx_next]:
                        dado_inicio = pygame.time.get_ticks()
                        _dado_ultima_fase = -2
                        ESTADO = "run_dado"
                    else:
                        ESTADO = "run_overview"

        elif ESTADO == "run_dado":
            if evento.type == pygame.KEYDOWN:
                # solo avanzar cuando la animacion termino
                dado_elapsed = pygame.time.get_ticks() - dado_inicio
                if dado_elapsed >= DADO_DURACION:
                    if evento.key in (pygame.K_SPACE, pygame.K_RETURN):
                        sfx_confirm()
                        ESTADO = "run_overview"
                        nueva_musica_menu_aleatoria()
                    elif evento.key == pygame.K_ESCAPE:
                        run_actual = None
                        ESTADO = "menu"
                        nueva_musica_menu_aleatoria()

        elif ESTADO == "run_completado":
            if evento.type == pygame.KEYDOWN:
                if evento.key in (pygame.K_RETURN, pygame.K_ESCAPE, pygame.K_SPACE):
                    pts_run = run_actual.get("puntos_total", 0)
                    if not score_guardado and pts_run > 0 and es_highscore(pts_run):
                        nombre_input = ""
                        ESTADO = "input_nombre"
                    elif carrera_activa:
                        ESTADO = "carrera"
                    else:
                        ESTADO = "leaderboard"
                    run_actual = None
                    carrera_activa = False
                    nueva_musica_menu_aleatoria()

        elif ESTADO == "run_fallido":
            if evento.type == pygame.KEYDOWN:
                # bloquear input durante la animacion (1.8s)
                if pygame.time.get_ticks() - run_fallido_t < 1800:
                    continue
                if evento.key in (pygame.K_RETURN, pygame.K_ESCAPE, pygame.K_SPACE):
                    # partida["puntos"] ya incluye lo acumulado de stages previos
                    pts_run = partida.get("puntos", 0)
                    if not score_guardado and pts_run > 0 and es_highscore(pts_run):
                        partida["puntos"] = pts_run
                        nombre_input = ""
                        ESTADO = "input_nombre"
                    elif carrera_activa:
                        ESTADO = "carrera"
                    else:
                        ESTADO = "leaderboard"
                    run_actual = None
                    carrera_activa = False
                    nueva_musica_menu_aleatoria()

        elif ESTADO == "mods":
            if evento.type == pygame.KEYDOWN:
                if evento.key == pygame.K_ESCAPE:
                    ESTADO = "menu"
                elif evento.key == pygame.K_UP:
                    mods_opcion = (mods_opcion - 1) % len(MODIFICADORES)
                    sfx_select()
                elif evento.key == pygame.K_DOWN:
                    mods_opcion = (mods_opcion + 1) % len(MODIFICADORES)
                    sfx_select()
                elif evento.key == pygame.K_SPACE:
                    mid = MODIFICADORES[mods_opcion]["id"]
                    if mid in mods_activos:
                        mods_activos.discard(mid)
                    else:
                        mods_activos.add(mid)
                elif evento.key == pygame.K_RETURN:
                    detener_musica_menu()
                    cortar_audio_suave()
                    dibujar_carga_seed(seed_acumulada)
                    partida = iniciar_partida(int(seed_acumulada))
                    score_guardado = False
                    ESTADO = "jugando"

        elif ESTADO == "leaderboard":
            if evento.type == pygame.KEYDOWN:
                if evento.key == pygame.K_ESCAPE:
                    ESTADO = "menu"

        elif ESTADO == "config":
            if evento.type == pygame.KEYDOWN:
                if evento.key == pygame.K_ESCAPE:
                    guardar_config()
                    ESTADO = "menu"
                elif evento.key == pygame.K_UP:
                    config_opcion = (config_opcion - 1) % 7
                    sfx_select()
                elif evento.key == pygame.K_DOWN:
                    config_opcion = (config_opcion + 1) % 7
                    sfx_select()
                elif evento.key in (pygame.K_RETURN, pygame.K_SPACE):
                    if config_opcion == 5:
                        # abrir pantalla de rebind de teclas
                        sfx_confirm()
                        rebind_col = 0
                        rebind_esperando = False
                        rebind_bindings = dict(cargar_bindings())
                        ESTADO = "rebind"
                    elif config_opcion == 6:
                        # abrir setup de teclado musical (seleccion de dispositivo)
                        sfx_confirm()
                        if LINEIN_DISPONIBLE:
                            listar_dispositivos_entrada()
                            linein_dev_idx = 0
                            ESTADO = "linein_setup"
                        else:
                            # sounddevice no instalado: mostrar pantalla con instrucciones
                            ESTADO = "linein_setup"
                elif evento.key == pygame.K_LEFT:
                    if config_opcion == 0:
                        config["brillo"] = max(0.3, round(config["brillo"] - 0.1, 1))
                    elif config_opcion == 1:
                        config["volumen"] = max(0.0, round(config["volumen"] - 0.1, 1))
                    elif config_opcion == 2:
                        config["vol_menu"] = max(0.0, round(config["vol_menu"] - 0.1, 1))
                    elif config_opcion == 3:
                        config["res_idx"] = max(0, config["res_idx"] - 1)
                        aplicar_resolucion()
                    elif config_opcion == 4:
                        nuevo = max(0, config["audio_idx"] - 1)
                        if nuevo != config["audio_idx"]:
                            cambiar_audio_device(nuevo)
                elif evento.key == pygame.K_RIGHT:
                    if config_opcion == 0:
                        config["brillo"] = min(1.0, round(config["brillo"] + 0.1, 1))
                    elif config_opcion == 1:
                        config["volumen"] = min(1.0, round(config["volumen"] + 0.1, 1))
                    elif config_opcion == 2:
                        config["vol_menu"] = min(1.0, round(config["vol_menu"] + 0.1, 1))
                    elif config_opcion == 3:
                        config["res_idx"] = min(len(RESOLUCIONES) - 1, config["res_idx"] + 1)
                        aplicar_resolucion()
                    elif config_opcion == 4:
                        nuevo = min(len(AUDIO_DEVICES) - 1, config["audio_idx"] + 1)
                        if nuevo != config["audio_idx"]:
                            cambiar_audio_device(nuevo)

        elif ESTADO == "rebind":
            if evento.type == pygame.KEYDOWN:
                if rebind_esperando:
                    # el usuario apretó una tecla: asignarla a la columna actual
                    # (ignorar ESC y teclas de navegacion en este modo)
                    if evento.key == pygame.K_ESCAPE:
                        rebind_esperando = False
                    else:
                        # si la tecla ya estaba asignada a otra col, desasignarla
                        rebind_bindings = {k: v for k, v in rebind_bindings.items()
                                           if v != rebind_col}
                        # si la tecla estaba en otra col, sacarla de ahí
                        if evento.key in rebind_bindings:
                            del rebind_bindings[evento.key]
                        rebind_bindings[evento.key] = rebind_col
                        sfx_confirm()
                        rebind_esperando = False
                        rebind_col += 1
                else:
                    if evento.key == pygame.K_ESCAPE:
                        # cancelar sin guardar
                        ESTADO = "config"
                    elif evento.key in (pygame.K_RETURN, pygame.K_SPACE):
                        if rebind_col >= 8:
                            # guardar y salir
                            guardar_bindings(rebind_bindings)
                            aplicar_bindings()
                            sfx_confirm()
                            ESTADO = "config"
                        else:
                            # empezar a esperar tecla para esta columna
                            rebind_esperando = True
                            sfx_select()
                    elif evento.key == pygame.K_UP and rebind_col > 0:
                        rebind_col -= 1
                        sfx_select()
                    elif evento.key == pygame.K_DOWN and rebind_col < 8:
                        rebind_col += 1
                        sfx_select()

        elif ESTADO == "linein_setup":
            if evento.type == pygame.KEYDOWN:
                # ignorar eventos sinteticos del line-in
                if hasattr(evento, "_linein_col"):
                    continue
                if evento.key == pygame.K_ESCAPE:
                    ESTADO = "config"
                elif evento.key == pygame.K_LEFT:
                    LINEIN_OFFSET_MS = max(0, LINEIN_OFFSET_MS - 10)
                elif evento.key == pygame.K_RIGHT:
                    LINEIN_OFFSET_MS = min(300, LINEIN_OFFSET_MS + 10)
                elif evento.key == pygame.K_UP and linein_devices:
                    linein_dev_idx = max(0, linein_dev_idx - 1)
                    sfx_select()
                elif evento.key == pygame.K_DOWN and linein_devices:
                    linein_dev_idx = min(len(linein_devices) - 1, linein_dev_idx + 1)
                    sfx_select()
                elif evento.key in (pygame.K_RETURN, pygame.K_SPACE):
                    if linein_devices:
                        # abrir calibracion con el dispositivo seleccionado
                        sfx_confirm()
                        dev_info = linein_devices[linein_dev_idx]
                        linein_abrir(dev_info["idx"], con_monitor=True)
                        linein_cal_col = 0
                        linein_cal_estado = "idle"
                        linein_cal_muestras = []
                        linein_en_silencio = True
                        linein_nota_activa = -1
                        linein_silencio_desde = 0
                        ESTADO = "calibrar_linein"
                    else:
                        print("No hay dispositivos de entrada disponibles")
                elif evento.key == pygame.K_a:
                    # toggle activar/desactivar line-in
                    if linein_activo:
                        linein_detener()
                    elif linein_notas_cal and linein_devices:
                        dev_info = linein_devices[linein_dev_idx]
                        linein_abrir(dev_info["idx"], con_monitor=False)
                elif evento.key == pygame.K_d and (linein_activo or linein_notas_cal):
                    # medir latencia
                    sfx_confirm()
                    if not linein_activo and linein_devices:
                        dev_info = linein_devices[linein_dev_idx]
                        linein_abrir(dev_info["idx"], con_monitor=True)
                    latencia_muestras.clear()
                    latencia_flash_time = pygame.time.get_ticks()
                    latencia_flash_activo = False
                    latencia_esperando = False
                    ESTADO = "medir_latencia"

        elif ESTADO == "calibrar_linein":
            if evento.type == pygame.KEYDOWN:
                # ignorar eventos sinteticos del line-in durante calibracion
                if hasattr(evento, "_linein_col"):
                    continue
                if evento.key == pygame.K_ESCAPE:
                    if linein_cal_estado == "escuchando":
                        linein_cal_estado = "idle"
                    else:
                        linein_monitor = False  # apagar monitoreo al salir
                        ESTADO = "config"
                elif evento.key in (pygame.K_RETURN, pygame.K_SPACE):
                    if linein_cal_col >= 8:
                        guardar_linein_notas()
                        sfx_confirm()
                        linein_monitor = False  # apagar monitoreo al salir
                        ESTADO = "config"
                    elif linein_cal_estado == "idle":
                        linein_cal_estado = "escuchando"
                        linein_cal_muestras = []
                        sfx_select()
                    elif linein_cal_estado == "escuchando":
                        if linein_freq_actual > 0:
                            linein_notas_cal[linein_cal_col] = round(linein_freq_actual, 1)
                            sfx_confirm()
                            linein_cal_estado = "idle"
                            linein_cal_col += 1
                elif evento.key == pygame.K_r and linein_cal_col >= 8:
                    linein_notas_cal.clear()
                    linein_cal_col = 0
                    linein_cal_estado = "idle"
                elif evento.key == pygame.K_UP and linein_cal_col > 0 and linein_cal_estado == "idle":
                    linein_cal_col -= 1
                    sfx_select()
                elif evento.key == pygame.K_DOWN and linein_cal_col < 8 and linein_cal_estado == "idle":
                    linein_cal_col += 1
                    sfx_select()
                elif evento.key == pygame.K_m:
                    # toggle monitoreo
                    linein_monitor = not linein_monitor

        elif ESTADO == "medir_latencia":
            if evento.type == pygame.KEYDOWN:
                if hasattr(evento, "_linein_col"):
                    if latencia_esperando and latencia_flash_time > 0:
                        delay = pygame.time.get_ticks() - latencia_flash_time
                        if delay < 1500:
                            latencia_muestras.append(delay)
                            latencia_esperando = False
                            latencia_flash_activo = False
                            latencia_flash_time = pygame.time.get_ticks()
                    continue
                if evento.key == pygame.K_ESCAPE:
                    ESTADO = "linein_setup"
                elif evento.key in (pygame.K_RETURN, pygame.K_SPACE):
                    if len(latencia_muestras) >= LATENCIA_NUM_MUESTRAS:
                        LINEIN_OFFSET_MS = sum(latencia_muestras) // len(latencia_muestras)
                        sfx_confirm()
                        ESTADO = "linein_setup"
                elif evento.key == pygame.K_r:
                    latencia_muestras.clear()
                    latencia_flash_time = pygame.time.get_ticks()
                    latencia_flash_activo = False
                    latencia_esperando = False

        elif ESTADO == "input_nombre":
            if evento.type == pygame.KEYDOWN:
                if evento.key == pygame.K_RETURN and len(nombre_input) > 0:
                    agregar_score(
                        nombre_input,
                        partida["puntos"],
                        int(partida["seed"]),
                        partida["dificultad"]["nombre"],
                        partida["max_combo"],
                    )
                    score_guardado = True
                    ESTADO = "leaderboard"
                elif evento.key == pygame.K_BACKSPACE:
                    nombre_input = nombre_input[:-1]
                elif evento.key == pygame.K_ESCAPE:
                    ESTADO = "menu"
                else:
                    if len(nombre_input) < 10 and evento.unicode.isprintable() and evento.unicode.strip():
                        nombre_input += evento.unicode.upper()

        elif ESTADO == "pausado":
            if evento.type == pygame.KEYDOWN:
                if evento.key == pygame.K_ESCAPE or (evento.key == pygame.K_RETURN and pausa_opcion == 0):
                    # CONTINUAR
                    pausa_dur = pygame.time.get_ticks() - partida["pausa_inicio"]
                    partida["inicio"] += pausa_dur
                    del partida["pausa_inicio"]
                    guardar_config()
                    ESTADO = "jugando"
                elif evento.key == pygame.K_UP:
                    pausa_opcion = (pausa_opcion - 1) % 5
                    sfx_select()
                elif evento.key == pygame.K_DOWN:
                    pausa_opcion = (pausa_opcion + 1) % 5
                    sfx_select()
                elif evento.key == pygame.K_LEFT and pausa_opcion == 1:
                    config["volumen"] = max(0.0, round(config["volumen"] - 0.1, 1))
                elif evento.key == pygame.K_RIGHT and pausa_opcion == 1:
                    config["volumen"] = min(1.0, round(config["volumen"] + 0.1, 1))
                elif evento.key == pygame.K_LEFT and pausa_opcion == 2:
                    nuevo = max(0, config["audio_idx"] - 1)
                    if nuevo != config["audio_idx"]:
                        cambiar_audio_device(nuevo)
                        guardar_config()
                elif evento.key == pygame.K_RIGHT and pausa_opcion == 2:
                    nuevo = min(len(AUDIO_DEVICES) - 1, config["audio_idx"] + 1)
                    if nuevo != config["audio_idx"]:
                        cambiar_audio_device(nuevo)
                        guardar_config()
                elif evento.key == pygame.K_RETURN:
                    if pausa_opcion == 3:
                        # REINICIAR stage actual
                        pygame.mixer.stop()
                        teclas_sostenidas.clear()
                        canal_hold.clear()
                        if run_actual is not None:
                            idx = run_actual["stage"] - 1
                            inst_stage = run_actual.get("instrumentos", [None]*NUM_STAGES)[idx]
                            partida = iniciar_partida(
                                run_actual["seeds"][idx],
                                mods=run_actual["mods"][idx],
                                stage_info={"n": run_actual["stage"]},
                                puntos_iniciales=run_actual["puntos_total"],
                                instrumento_forzado=inst_stage,
                                perks=run_actual.get("perks"))
                            # modo instrumento: simplificar notas para line-in
                            if modo_instrumento:
                                simplificar_para_instrumento(partida["cancion"])
                        else:
                            partida = iniciar_partida(int(seed_acumulada))
                        score_guardado = False
                        pausa_opcion = 0
                        ESTADO = "jugando"
                    elif pausa_opcion == 4:
                        # SALIR
                        pygame.mixer.stop()
                        teclas_sostenidas.clear()
                        canal_hold.clear()
                        if run_actual is not None:
                            # abandonar el run
                            run_actual = None
                            ESTADO = "menu"
                            nueva_musica_menu_aleatoria()
                        elif not score_guardado and partida["puntos"] > 0 and es_highscore(partida["puntos"]):
                            nombre_input = ""
                            ESTADO = "input_nombre"
                        else:
                            ESTADO = "leaderboard"
                            nueva_musica_menu_aleatoria()
                        pausa_opcion = 0

        elif ESTADO == "jugando":
            zy_p = partida.get("zona_y", ZONA_Y)
            _col_hit = -1   # columna golpeada en este evento (-1 = ninguna)
            _es_linein = False  # True si el hit viene del line-in
            _avanzar_fin = False  # True si hay que transicionar al fin/siguiente stage
            if evento.type == pygame.KEYDOWN:
                if evento.key in (pygame.K_ESCAPE, pygame.K_SPACE, pygame.K_RETURN):
                    if partida.get("game_over") or (partida["terminada"] and not partida["notas_cayendo"]):
                        # durante la animacion de muerte (1er segundo) ignorar
                        if (partida.get("game_over")
                                and pygame.time.get_ticks() - partida.get("game_over_t", 0) < 1000):
                            continue
                        _avanzar_fin = True

            # AUTO-AVANCE: 5s después de terminada, avanzar sin esperar input
            if (partida.get("terminada") and not partida.get("game_over")
                    and not partida["notas_cayendo"]
                    and partida.get("terminada_t")
                    and pygame.time.get_ticks() - partida["terminada_t"] >= 5000):
                _avanzar_fin = True

            if _avanzar_fin:
                # FIN / GAME OVER
                sfx_confirm()
                pygame.mixer.stop()
                teclas_sostenidas.clear()
                canal_hold.clear()
                if partida.get("es_tutorial"):
                    # fin de la practica del tutorial -> volver al menu
                    ESTADO = "menu"
                    nueva_musica_menu_aleatoria()
                elif run_actual is not None:
                    # --- en modo RUN de stages ---
                    if partida.get("game_over"):
                        # perdio el stage -> run fallido
                        run_fallido_t = pygame.time.get_ticks()
                        ESTADO = "run_fallido"
                        nueva_musica_menu_aleatoria()
                    else:
                        # paso el stage: el total del run es el puntaje final
                        # de esta partida (que ya arranco desde el acumulado)
                        _ganado_st = partida["puntos"] - partida.get("puntos_stage_inicio", 0)
                        _idx_st = run_actual["stage"] - 1
                        if 0 <= _idx_st < len(run_actual.get("puntos_por_stage", [])):
                            run_actual["puntos_por_stage"][_idx_st] = _ganado_st
                        # rank de performance del stage (S/A/B/C/D)
                        run_actual.setdefault("rank_por_stage", ["?"] * NUM_STAGES)
                        if 0 <= _idx_st < NUM_STAGES:
                            run_actual["rank_por_stage"][_idx_st] = calcular_rank_stage(partida)
                        run_actual["puntos_total"] = partida["puntos"]
                        if run_actual["stage"] >= NUM_STAGES:
                            # run completo!
                            marcar_completado(run_actual["genero"], run_actual["nivel"])
                            col_g = COLOR_GENERO.get(run_actual["genero"], BLANCO)
                            _spawn_notas_celebracion(col_g)
                            # CARRERA: desbloquear siguiente nivel + guardar rank
                            if carrera_activa:
                                # calcular rank promedio de los 4 stages
                                rks = run_actual.get("rank_por_stage", ["?"] * NUM_STAGES)
                                _ord = {"S": 5, "A": 4, "B": 3, "C": 2, "D": 1, "?": 0}
                                _prom = sum(_ord.get(r, 0) for r in rks) / max(1, len(rks))
                                if _prom >= 4.5: _rk_final = "S"
                                elif _prom >= 3.5: _rk_final = "A"
                                elif _prom >= 2.5: _rk_final = "B"
                                elif _prom >= 1.5: _rk_final = "C"
                                else: _rk_final = "D"
                                carrera_completar_nivel(run_actual["nivel"], _rk_final)
                            ESTADO = "run_completado"
                            nueva_musica_menu_aleatoria()
                        else:
                            # ofrecer perk antes de avanzar al siguiente stage
                            _perk_rng = random.Random(run_actual["seeds"][run_actual["stage"] - 1] + 777)
                            perk_ofertas[:] = generar_ofertas_perks(_perk_rng, run_actual["perks"])
                            perk_seleccion = 0
                            perk_anim_inicio = pygame.time.get_ticks()
                            ESTADO = "perk_select"
                            nueva_musica_menu_aleatoria()
                else:
                    # modo libre normal
                    if not score_guardado and partida["puntos"] > 0 and es_highscore(partida["puntos"]):
                        nombre_input = ""
                        ESTADO = "input_nombre"
                    else:
                        ESTADO = "leaderboard"
                    nueva_musica_menu_aleatoria()

            if evento.type == pygame.KEYDOWN:
                if evento.key == pygame.K_ESCAPE and not partida.get("game_over") and not partida.get("terminada"):
                    # PAUSAR
                    pygame.mixer.stop()
                    teclas_sostenidas.clear()
                    for c in list(canal_hold.keys()):
                        canal_hold[c].stop()
                    canal_hold.clear()
                    partida["snd_pendientes"] = []
                    partida["pausa_inicio"] = pygame.time.get_ticks()
                    pausa_opcion = 0
                    ESTADO = "pausado"
                elif evento.key == pygame.K_d and (partida.get("game_over") or (partida["terminada"] and not partida["notas_cayendo"])) and not partida.get("export_ruta") and not partida.get("exportando"):
                    partida["exportando"] = True
                    pantalla.fill(NEGRO)
                    dibujar_juego(partida, ahora_ms - partida["inicio"])
                    presentar()
                    ruta = exportar_cancion(partida)
                    partida["exportando"] = False
                    if ruta:
                        partida["export_ruta"] = ruta
                elif evento.key in COLUMNAS:
                    col = COLUMNAS[evento.key]
                    # ESPEJO: la tecla fisica se mapea a otra columna
                    col = partida.get("mapa_teclas", {}).get(col, col)
                    if col < partida["dificultad"]["columnas"]:
                        teclas_sostenidas.add(col)
                        midi_fijo = partida["cancion"]["notas_columnas"][col]
                        _col_hit = col  # marcar para scoring abajo

            # GAMEPAD: botones del controlador -> misma lógica que teclado
            if evento.type == pygame.JOYBUTTONDOWN and not partida.get("game_over") and not partida.get("terminada"):
                _pad_col = pad_col_down(evento.button)
                if _pad_col is not None:
                    col = partida.get("mapa_teclas", {}).get(_pad_col, _pad_col)
                    if col < partida["dificultad"]["columnas"]:
                        teclas_sostenidas.add(col)
                        midi_fijo = partida["cancion"]["notas_columnas"][col]
                        _col_hit = col

            # LINE-IN: el teclado musical inyecta eventos con _linein_col
            # El offset compensa la latencia del audio: adelanta el tiempo
            # de comparación para que el scoring juzgue como si el jugador
            # hubiera tocado LINEIN_OFFSET_MS antes.
            if (evento.type == pygame.KEYDOWN and hasattr(evento, "_linein_col")
                    and not partida.get("game_over") and not partida.get("terminada")):
                col = evento._linein_col
                col = partida.get("mapa_teclas", {}).get(col, col)
                if col < partida["dificultad"]["columnas"]:
                    teclas_sostenidas.add(col)
                    midi_fijo = partida["cancion"]["notas_columnas"][col]
                    _col_hit = col
                    # marcar que este hit viene del line-in (para offset y skip cuantización)
                    _es_linein = True

            # SCORING: si alguna fuente de input (teclado/gamepad/line-in)
            # seteó _col_hit, procesar la nota en esa columna
            if _col_hit >= 0:
                col = _col_hit

                # buscar la nota objetivo más cercana en esta columna
                ahora_rel = int(partida.get("t_musical", ahora_ms - partida["inicio"]))
                # LINE-IN: compensar latencia adelantando el tiempo de comparacion
                # Esto hace que el scoring juzgue como si el jugador hubiera
                # tocado OFFSET ms antes (la nota le "llega" tarde al juego
                # por el buffer de audio, asi que lo corregimos aca).
                if _es_linein:
                    ahora_rel += LINEIN_OFFSET_MS
                midi_a_tocar = midi_fijo
                mejor_dist = 99999
                mejor_target = ahora_rel   # tiempo target de la mejor nota (para cuantizar)
                mejor_es_pu = False   # si la mejor nota es un power-up, no sonar melodica
                mejor_es_bomba = False  # si la mejor nota es una bomba, no sonar melodica
                for g in partida["notas_cayendo"]:
                    if col in g["cols"]:
                        d = abs(g["tiempo_ms"] - ahora_rel)
                        if d < mejor_dist:
                            mejor_dist = d
                            mejor_target = g["tiempo_ms"]
                            mejor_es_pu = bool(g.get("power_up"))
                            mejor_es_bomba = bool(g.get("es_bomba"))
                            idx_col = g["cols"].index(col)
                            if idx_col < len(g.get("midis", [])):
                                midi_a_tocar = g["midis"][idx_col]

                # volumen segun cercania: generoso, pifiar por poco suena pleno.
                # techo bajado de 0.80 -> 0.62 para que la nota del jugador
                # NO domine la mezcla (percusion y bajo tambien bajan sus
                # boosts abajo, asi el balance relativo se mantiene pero el
                # jugador deja de "flotar" arriba del resto de la cancion).
                if mejor_dist < 120:
                    vol_nota = 0.62
                elif mejor_dist < 250:
                    vol_nota = 0.55
                else:
                    vol_nota = 0.42

                # solo tocar la nota melodica si la mejor no es un power-up
                # ni una bomba (ambos tienen su propio SFX al acertar/detonar)
                snd_tocar = None
                if (not (mejor_es_pu and mejor_dist < partida.get("w_hit", 150))
                        and not (mejor_es_bomba and mejor_dist < partida.get("w_hit", 150))):
                    snd_tocar = cache_notas.get(midi_a_tocar) or cache_notas.get(midi_fijo)
                if snd_tocar:
                    # paneo segun posicion de la columna (izq a der)
                    num_cols_t = partida["dificultad"]["columnas"]
                    if num_cols_t > 1:
                        pan = col / (num_cols_t - 1)  # 0..1
                    else:
                        pan = 0.5
                    volL = vol_nota * (1.0 - pan * 0.6) * config["volumen"]
                    volR = vol_nota * (0.4 + pan * 0.6) * config["volumen"]
                    # CUANTIZACION AL GRID: si el jugador pego TEMPRANO
                    # (target > ahora) por entre 5 y 45ms, demorar el
                    # sample al tiempo target exacto asi cae en grid con
                    # percusion y bajo. LINE-IN: se saltea porque ya tiene
                    # su propia compensacion de latencia y agregar delay
                    # empeoraria la respuesta.
                    delta = mejor_target - ahora_rel
                    if not _es_linein and 5 < delta < 45:
                        partida["snd_pendientes"].append(
                            (mejor_target, snd_tocar, volL, volR))
                    else:
                        ch = snd_tocar.play()
                        if ch:
                            ch.set_volume(volL, volR)

                # pulso del fondo al tocar (reacciona a la nota del jugador)
                partida["liss_pulso"] = 1.0

                acerto_algo = False
                # ventanas de timing (ajustables por perks)
                # ventanas de timing escaladas por dificultad (con perks aplicados)
                w_hit = partida.get("w_hit", 150)
                w_perf = partida.get("w_perf", 30)
                # auto-perfecto por power-up estrella
                ahora_juego = int(partida.get("t_musical", ahora_ms - partida["inicio"]))
                auto_perf = ahora_juego < partida.get("efectos_activos", {}).get("estrella", 0)
                for grupo in partida["notas_cayendo"]:
                    if col in grupo["cols"]:
                        distancia = abs(grupo["tiempo_ms"] - ahora_juego)
                        if distancia < w_hit:
                            acerto_algo = True
                            if "acertadas" not in grupo:
                                grupo["acertadas"] = set()
                            if col not in grupo["acertadas"]:
                                grupo["acertadas"].add(col)
                                num_cols = partida["dificultad"]["columnas"]
                                ancho_col = ANCHO // num_cols
                                cx = col * ancho_col + ancho_col // 2
                                col_g = COLOR_GENERO.get(partida["cancion"].get("genero",""), BLANCO)
                                # --- BOMBA: nota que NO debe tocarse ---
                                if grupo.get("es_bomba") and distancia < w_hit:
                                    # explosion visual grande + daño + reset combo
                                    crear_explosion(cx, zy_p, 140, color=(255, 60, 60))
                                    crear_onda(cx, zy_p, 1.0)
                                    crear_shake(14)
                                    crear_texto_flotante(cx, zy_p - 30, "BOOM!", (255, 60, 60), True)
                                    partida["ultimo_hit"] = {"texto": "BOMBA", "tiempo": ahora_ms}
                                    partida["combo"] = 0
                                    # escudo absorbe la bomba
                                    if partida.get("escudo_cargas", 0) > 0:
                                        partida["escudo_cargas"] -= 1
                                        crear_texto_flotante(ANCHO // 2, zy_p - 60,
                                                             f"ESCUDO ({partida['escudo_cargas']})",
                                                             (100, 200, 255), True)
                                    elif not dev_mode and not partida.get("es_tutorial"):
                                        partida["vida"] = max(0, partida["vida"] - 4)
                                        if "sudden" in partida.get("mods", set()):
                                            partida["vida"] = 0
                                    SND_EXPLOSION_BIG.set_volume(0.6 * config["volumen"])
                                    SND_EXPLOSION_BIG.play()
                                    if grupo in partida["notas_cayendo"]:
                                        partida["notas_cayendo"].remove(grupo)
                                    if not dev_mode and partida["vida"] <= 0:
                                        if partida.get("perk_resurreccion"):
                                            partida["perk_resurreccion"] = False
                                            partida["vida"] = 5
                                            if run_actual is not None:
                                                run_actual["perks"] = [pk for pk in run_actual.get("perks", [])
                                                                       if pk.get("id") != "resurreccion"]
                                            crear_texto_flotante(ANCHO // 2, ALTO // 2, "RESURRECCION!", (255, 220, 100), True)
                                            crear_explosion(ANCHO // 2, zy_p, 120, color=(255, 220, 100))
                                            crear_shake(10)
                                        else:
                                            partida["game_over"] = True
                                            partida["game_over_t"] = pygame.time.get_ticks()
                                            _explotar_notas_muerte(partida)
                                            pygame.mixer.stop()
                                            crear_shake(15)
                                            SND_GAMEOVER.set_volume(0.6 * config["volumen"])
                                            SND_GAMEOVER.play()
                                    break
                                # --- POWER-UP: nota especial ---
                                pu_id = grupo.get("power_up")
                                if pu_id and distancia < w_hit:
                                    pu_def = next((p for p in POWER_UPS if p["id"] == pu_id), None)
                                    if pu_def:
                                        if pu_id == "vida":
                                            partida["vida"] = min(partida["vida_max"], partida["vida"] + 4)
                                            crear_texto_flotante(cx, zy_p - 30, "+4 VIDA", pu_def["color"], True)
                                        elif pu_def["dur"] > 0:
                                            partida["efectos_activos"][pu_id] = ahora_juego + pu_def["dur"] * (2 if partida.get("perk_cazador") else 1)
                                            crear_texto_flotante(cx, zy_p - 30, pu_def["nombre"], pu_def["color"], True)
                                        crear_explosion(cx, zy_p, 80, color=pu_def["color"])
                                        crear_shake(6)
                                        sfx_power_up(pu_id)
                                        partida["combo"] += 1
                                        if partida["combo"] > partida["max_combo"]:
                                            partida["max_combo"] = partida["combo"]
                                        if (partida.get("perk_regen") and partida["combo"] > 0
                                                and partida["combo"] % 20 == 0):
                                            partida["vida"] = min(partida["vida_max"], partida["vida"] + 1)
                                            crear_texto_flotante(ANCHO // 2, zy_p - 60, "+1 VIDA", (120, 255, 120))
                                        if grupo in partida["notas_cayendo"]:
                                            partida["notas_cayendo"].remove(grupo)
                                        break
                                if auto_perf or distancia < w_perf:
                                    pts = 10 if partida.get("perk_perfecto") else 5
                                    partida["combo"] += 1
                                    pot = min(1.0 + partida["combo"] * 0.03, 1.8)
                                    partida["ultimo_hit"] = {"texto": "PERFECTO", "tiempo": ahora_ms}
                                    partida["n_perfecto"] = partida.get("n_perfecto", 0) + 1
                                    combo_particulas = min(50 + partida["combo"] * 4, 250)
                                    crear_explosion(cx, zy_p, combo_particulas, color=col_g, potencia=pot, combo=partida["combo"])
                                    crear_onda(cx, zy_p, 0.7)
                                    crear_onda(cx, zy_p, 0.4, r0=int(4 + partida["combo"] * 0.3))
                                    if partida["combo"] >= 30:
                                        crear_onda(cx, zy_p, 0.5, r0=int(15 + partida["combo"] * 0.5))
                                    crear_flash(col, min(0.8, 0.5 + partida["combo"] * 0.01))
                                    crear_shake(min(5 + partida["combo"] * 0.15, 12))
                                    crear_indicador_hit(col, "perfecto")
                                    sfx_hit_perfect(partida["combo"])
                                elif distancia < w_hit * 0.4:
                                    pts = 3
                                    partida["combo"] += 1
                                    pot = min(1.0 + partida["combo"] * 0.02, 1.5)
                                    partida["ultimo_hit"] = {"texto": "BIEN", "tiempo": ahora_ms}
                                    partida["n_bien"] = partida.get("n_bien", 0) + 1
                                    crear_explosion(cx, zy_p, min(30 + partida["combo"] * 2, 150), color=col_g, potencia=pot, combo=partida["combo"])
                                    crear_onda(cx, zy_p, 0.5)
                                    crear_flash(col, 0.4)
                                    crear_shake(min(3 + partida["combo"] * 0.1, 8))
                                    crear_indicador_hit(col, "cerca")
                                    sfx_hit_good()
                                elif distancia < w_hit * 0.67:
                                    pts = 1
                                    partida["combo"] += 1
                                    partida["ultimo_hit"] = {"texto": "OK", "tiempo": ahora_ms}
                                    partida["n_ok"] = partida.get("n_ok", 0) + 1
                                    crear_explosion(cx, zy_p, 20, color=col_g, combo=partida["combo"])
                                    crear_onda(cx, zy_p, 0.4)
                                    crear_flash(col, 0.3)
                                    crear_indicador_hit(col, "cerca")
                                    sfx_hit_good()
                                else:
                                    pts = 0
                                    partida["combo"] = 0
                                    partida["ultimo_hit"] = {"texto": "MAL", "tiempo": ahora_ms}
                                    partida["n_mal"] = partida.get("n_mal", 0) + 1
                                    crear_explosion(cx, zy_p, 8, GRIS_MED)
                                    crear_shake(8)
                                    crear_indicador_hit(col, "error")
                                if partida["combo"] > partida["max_combo"]:
                                    partida["max_combo"] = partida["combo"]
                                if (partida.get("perk_regen") and partida["combo"] > 0
                                        and partida["combo"] % 20 == 0):
                                    partida["vida"] = min(partida["vida_max"], partida["vida"] + 1)
                                    crear_texto_flotante(ANCHO // 2, zy_p - 60, "+1 VIDA", (120, 255, 120))
                                # milestone de combo cada 10: sonido + confeti
                                if pts > 0 and partida["combo"] > 0 and partida["combo"] % 10 == 0:
                                    sfx_combo(partida["combo"])
                                    for _ in range(min(partida["combo"] * 2, 120)):
                                        px_c = random.randint(0, ANCHO)
                                        particulas.append({
                                            "x": px_c, "y": -5,
                                            "dx": random.uniform(-1.5, 1.5),
                                            "dy": random.uniform(2, 6),
                                            "vida": random.randint(50, 90), "vida_max": 90,
                                            "tam": random.randint(3, 7),
                                            "color": _color_vivo(col_g, partida["combo"]),
                                            "forma": random.choice(["rect", "estrella"]),
                                            "spin": random.uniform(-0.4, 0.4),
                                        })
                                    crear_texto_flotante(ANCHO // 2, zy_p - 120,
                                                         f"{partida['combo']}x COMBO!", col_g, grande=True)
                                combo_mult = 1 + partida["combo"] // partida.get("combo_div", 5)
                                if grupo.get("hold", 0) > 0 and not grupo.get("es_acorde"):
                                    # usar el midi REAL de la nota (con octava/armonia),
                                    # no la nota base de la columna: asi el hold suena
                                    # afinado con la melodia.
                                    _idx_c = grupo["cols"].index(col) if col in grupo["cols"] else 0
                                    _midi_hold = grupo.get("midis", [midi_fijo])[_idx_c] if _idx_c < len(grupo.get("midis", [])) else midi_fijo
                                    _snd_hold = cache_notas_largas.get(_midi_hold) or cache_notas_largas.get(midi_fijo)
                                    if _snd_hold:
                                        # loop si el hold dura mas que el sample (1.6s)
                                        loops = -1 if grupo["hold"] > 1500 else 0
                                        ch = _snd_hold.play(loops=loops)
                                        if ch:
                                            ch.set_volume(config["volumen"])
                                            canal_hold[col] = ch
                                    partida["holds_activos"][col] = {
                                        "grupo": grupo,
                                        "midi":  midi_fijo,
                                    }
                                    if pts > 0:
                                        _pu_doble = 2.0 if ahora_juego < partida.get("efectos_activos", {}).get("doble", 0) else 1.0
                                        total_pts = int(pts * combo_mult * partida.get("mult_mods", 1.0) * _pu_doble)
                                        partida["puntos"] += total_pts
                                        txt = f"+{total_pts}"
                                        if combo_mult > 1:
                                            txt += f" x{combo_mult}"
                                        crear_texto_flotante(cx, zy_p - 20, txt, BLANCO, combo_mult > 2)
                                else:
                                    if pts > 0:
                                        _pu_doble = 2.0 if ahora_juego < partida.get("efectos_activos", {}).get("doble", 0) else 1.0
                                        total_pts = int(pts * len(grupo["cols"]) * combo_mult * partida.get("mult_mods", 1.0) * _pu_doble)
                                        txt_pts = f"+{total_pts}"
                                        if combo_mult > 1:
                                            txt_pts += f" x{combo_mult}"
                                        es_grande = combo_mult > 2
                                        crear_texto_flotante(cx, zy_p - 20, txt_pts, BLANCO, es_grande)
                                        partida["puntos"] += total_pts
                                    else:
                                        # mal timing: rompe combo pero NO resta puntos
                                        crear_texto_flotante(cx, zy_p - 20, "MAL", GRIS_MED)
                                    if partida["combo"] > 0 and partida["combo"] % 5 == 0 and partida["combo"] % 10 != 0:
                                        crear_texto_flotante(ANCHO // 2, zy_p - 80, f"{partida['combo']}x", col_g, True)
                                    if grupo["acertadas"] == set(grupo["cols"]):
                                        partida["notas_cayendo"].remove(grupo)
                            break

                # tecla equivocada: ninguna nota cerca en esa columna
                if not acerto_algo:
                    partida["combo"] = 0
                    partida["puntos"] = max(0, partida["puntos"] - 1)
                    partida["ultimo_hit"] = {"texto": "ERROR", "tiempo": ahora_ms}
                    num_cols = partida["dificultad"]["columnas"]
                    ancho_col = ANCHO // num_cols
                    cx = col * ancho_col + ancho_col // 2
                    crear_texto_flotante(cx, zy_p - 20, "-1", GRIS_MED)
                    crear_explosion(cx, zy_p, 6, GRIS_MED)
                    crear_shake(3)
                    crear_indicador_hit(col, "error")
                    SND_ERROR.set_volume(0.35 * config["volumen"])
                    SND_ERROR.play()

            if evento.type == pygame.KEYUP:
                if evento.key in COLUMNAS:
                    col = COLUMNAS[evento.key]
                    col = partida.get("mapa_teclas", {}).get(col, col)
                    teclas_sostenidas.discard(col)
                    if col in partida.get("holds_activos", {}):
                        if col in canal_hold:
                            canal_hold[col].stop()
                            del canal_hold[col]
                        hold = partida["holds_activos"][col]
                        grupo = hold["grupo"]

            # LINE-IN auto-release: soltar columna después del delay
            if evento.type == pygame.KEYUP and hasattr(evento, "_linein_col_up"):
                col = evento._linein_col_up
                teclas_sostenidas.discard(col)

            # GAMEPAD: soltar boton = soltar hold
            if evento.type == pygame.JOYBUTTONUP:
                _pad_col = pad_col_down(evento.button)
                if _pad_col is not None:
                    col = partida.get("mapa_teclas", {}).get(_pad_col, _pad_col)
                    teclas_sostenidas.discard(col)
                    if col in partida.get("holds_activos", {}):
                        if col in canal_hold:
                            canal_hold[col].stop()
                            del canal_hold[col]
                        hold = partida["holds_activos"][col]
                        grupo = hold["grupo"]
                        # bonus por completar hold (HOLD MASTER lo duplica)
                        _hb = partida.get("hold_bonus", 5)
                        partida["puntos"] += _hb
                        num_cols = partida["dificultad"]["columnas"]
                        ancho_col = ANCHO // num_cols
                        cx = col * ancho_col + ancho_col // 2
                        crear_texto_flotante(cx, zy_p - 40, f"+{_hb}", BLANCO)
                        if grupo in partida["notas_cayendo"]:
                            partida["notas_cayendo"].remove(grupo)
                        del partida["holds_activos"][col]

    if ESTADO == "menu":
        tick_musica_menu()
        dibujar_menu()

    elif ESTADO == "selector_seed":
        if cargando_seed:
            seed_acumulada = min(seed_acumulada + SEED_VELOCIDAD, SEED_MAX)
        tick_musica_menu()
        dibujar_selector_seed(seed_acumulada, cargando_seed)

    elif ESTADO == "selector_seed_inst":
        if cargando_seed:
            seed_acumulada = min(seed_acumulada + SEED_VELOCIDAD, SEED_MAX)
        tick_musica_menu()
        dibujar_selector_seed_inst(seed_acumulada, cargando_seed)

    elif ESTADO == "leaderboard":
        tick_musica_menu()
        dibujar_leaderboard()

    elif ESTADO == "tutorial":
        tick_musica_menu()
        dibujar_tutorial(tutorial_pagina)

    elif ESTADO == "config":
        tick_musica_menu()
        dibujar_config()

    elif ESTADO == "rebind":
        tick_musica_menu()
        dibujar_rebind()

    elif ESTADO == "calibrar_linein":
        tick_musica_menu()
        dibujar_calibracion_linein()

    elif ESTADO == "medir_latencia":
        tick_musica_menu()
        if linein_activo:
            linein_procesar_eventos(None)
        _ahora_lat = pygame.time.get_ticks()
        if len(latencia_muestras) < LATENCIA_NUM_MUESTRAS:
            _t_desde = _ahora_lat - latencia_flash_time
            # arrancar flash cuando pasan 3s desde el ultimo evento
            if not latencia_flash_activo and not latencia_esperando and _t_desde >= 3000:
                latencia_flash_time = _ahora_lat
                latencia_flash_activo = True
                latencia_esperando = True
            # apagar el visual del flash 300ms despues (usa timer ACTUALIZADO)
            if latencia_flash_activo and (_ahora_lat - latencia_flash_time) >= 300:
                latencia_flash_activo = False
            # timeout: si no toco en 2s despues del flash, descartar
            if latencia_esperando and (_ahora_lat - latencia_flash_time) > 2000:
                latencia_esperando = False
                latencia_flash_activo = False
        dibujar_medir_latencia()

    elif ESTADO == "linein_setup":
        tick_musica_menu()
        dibujar_linein_setup()

    elif ESTADO == "mods":
        tick_musica_menu()
        dibujar_mods()

    elif ESTADO == "run_overview":
        tick_musica_menu()
        dibujar_run_overview()

    elif ESTADO == "perk_select":
        tick_musica_menu()
        dibujar_perk_select()

    elif ESTADO == "run_dado":
        tick_musica_menu()
        dibujar_dado()

    elif ESTADO == "run_completado":
        tick_musica_menu()
        dibujar_run_completado()

    elif ESTADO == "run_fallido":
        tick_musica_menu()
        dibujar_run_fallido()

    elif ESTADO == "carrera":
        tick_musica_menu()
        dibujar_carrera()

    elif ESTADO == "input_nombre":
        tick_musica_menu()
        dibujar_input_nombre(nombre_input)

    elif ESTADO == "pausado":
        ahora = partida["pausa_inicio"] - partida["inicio"]
        dibujar_juego(partida, ahora)
        dibujar_pausa(partida)

    elif ESTADO == "jugando":
        zy_p = partida.get("zona_y", ZONA_Y)
        # RESET DEL RELOJ: la primera vez que se entra a "jugando" despues
        # de crear la partida (o despues de una pausa), resincronizar el
        # inicio al momento actual. Asi el t_musical arranca en 0 y las
        # primeras notas no estan atrasadas por el tiempo de carga/warm-up.
        if not partida.get("_inicio_real"):
            _viejo = partida["inicio"]
            partida["inicio"] = pygame.time.get_ticks()
            _delta = partida["inicio"] - _viejo
            partida["t_musical"] = 0.0
            partida["_arranco_audio"] = False
            partida["_arranco_notas"] = False
            partida["indice_perc"] = 0
            partida["indice_bajo"] = 0
            partida["indice_jugador"] = 0
            partida["_inicio_real"] = True
            print(f"[RESET RELOJ] delta={_delta}ms (warm-up tardó {_delta}ms, notas resincronizadas a t=0)")
        # procesar eventos del teclado musical por line-in
        if linein_activo and partida and not partida.get("game_over") and not partida.get("terminada"):
            linein_procesar_eventos(partida)
        # dev mode: x2 speed (avanzar inicio hacia atras = tiempo pasa el doble)
        if dev_mode:
            partida["inicio"] -= 1000 // 60
        # --- RELOJ MUSICAL: el tiempo del juego puede correr mas lento ---
        # Durante el power-up SLOW, t_musical avanza a 0.75x del tiempo real
        # (con easing suave al entrar y salir). TODO usa este reloj: percusion,
        # bajo, emision de notas, posiciones y timing de hits — la cancion
        # entera se ralentiza de forma coherente y sin saltos de posicion.
        ahora_real = ahora_ms - partida["inicio"]
        # ahora_ms se tomo al INICIO del frame, pero si la partida se creo en
        # este mismo frame (la carga tarda segundos), 'inicio' es mas reciente
        # y ahora_real sale negativo -> el reloj arrancaria en el pasado
        # (sintoma: teclas blancas de AUTO, notas retrasadas). Clamp a 0.
        if ahora_real < 0:
            ahora_real = 0
        _dt_real = ahora_real - partida.get("_t_real_prev", ahora_real)
        partida["_t_real_prev"] = ahora_real
        _dt_real = max(0, min(_dt_real, 250))   # clamp por pausas/lag
        _reloj_on = partida.get("t_musical", 0) < partida.get("efectos_activos", {}).get("reloj", 0)
        _sf_obj = 0.75 if _reloj_on else 1.0
        _sf = partida.get("slow_factor", 1.0)
        _sf += (_sf_obj - _sf) * 0.08           # easing (~0.5s a 60fps)
        if abs(_sf - _sf_obj) < 0.002:
            _sf = _sf_obj
        partida["slow_factor"] = _sf
        partida["t_musical"] = partida.get("t_musical", float(ahora_real)) + _dt_real * _sf
        ahora = int(partida["t_musical"])

        # cuantizacion al grid: disparar los samples que ya llegaron a su
        # tiempo target. La lista tipicamente tiene 0-3 elementos, chico.
        _pend = partida.get("snd_pendientes", [])
        if _pend:
            _restantes = []
            for _t_target, _snd, _vL, _vR in _pend:
                if ahora >= _t_target:
                    _ch = _snd.play()
                    if _ch:
                        _ch.set_volume(_vL, _vR)
                else:
                    _restantes.append((_t_target, _snd, _vL, _vR))
            partida["snd_pendientes"] = _restantes

        # RAFAGAS: avisar al entrar en la avalancha (inicio de cada ciclo)
        if partida["cancion"].get("tiene_rafagas") and not partida.get("game_over"):
            ciclo_ms = partida["cancion"].get("rafaga_ciclo_ms", 0)
            comp_ms = partida["cancion"].get("rafaga_compas_ms", 0)
            if ciclo_ms > 0:
                ciclo_actual = int(ahora // ciclo_ms)
                pos_ciclo = ahora % ciclo_ms
                if ciclo_actual != partida.get("_rafaga_ciclo", -1):
                    partida["_rafaga_ciclo"] = ciclo_actual
                    if ahora > ciclo_ms * 0.5:
                        # arranca la avalancha: aviso grande + shake fuerte
                        col_g = color_genero(partida)
                        crear_texto_flotante(ANCHO // 2, zy_p - 110, "RAFAGA!", col_g, True)
                        crear_shake(9)
                        sfx_combo(20)   # sonido energico
                # avisar el respiro al entrar al 3er compas del ciclo
                en_respiro = pos_ciclo >= comp_ms * 2
                if en_respiro and not partida.get("_en_respiro", False):
                    partida["_en_respiro"] = True
                    if ahora > ciclo_ms:
                        crear_texto_flotante(ANCHO // 2, zy_p - 110, "respiro", GRIS_MED, False)
                elif not en_respiro:
                    partida["_en_respiro"] = False

        if not partida.get("game_over"):
            tick_background(partida, ahora)

        # AUTO-AVANCE: 3s después de alcanzar la meta, limpiar notas
        # restantes y forzar la pantalla de fin de stage. Antes el jugador
        # se quedaba clavado sin saber qué apretar.
        if (partida.get("terminada") and not partida.get("game_over")
                and partida.get("terminada_t")):
            _t_desde_win = pygame.time.get_ticks() - partida["terminada_t"]
            if _t_desde_win >= 3000:
                partida["notas_cayendo"] = []  # forzar limpieza

        if not partida.get("game_over"):
            holds_perdidos = []
            for col, hold in partida["holds_activos"].items():
                if hold["grupo"]["y"] > ALTO and col not in teclas_sostenidas:
                    if col in canal_hold:
                        canal_hold[col].stop()
                        del canal_hold[col]
                    holds_perdidos.append(col)
            for col in holds_perdidos:
                del partida["holds_activos"][col]

            vel_p = partida.get("velocidad", VELOCIDAD)
            # cooldown de combo_save: decrementar (16.67ms por frame a 60fps)
            if partida.get("combo_save_cd", 0) > 0:
                partida["combo_save_cd"] = max(0, partida["combo_save_cd"] - (1000 / 60))
            # limpiar efectos temporales expirados
            efectos = partida.get("efectos_activos", {})
            for eid in list(efectos.keys()):
                if ahora > efectos[eid]:
                    del efectos[eid]
            # ACELERANDO: velocidad sube de 1x a 2x dentro de cada loop
            if "acelerando" in partida.get("mods", set()):
                duracion = partida["cancion"]["duracion_loop"]
                ahora_en_loop = (ahora - partida.get("loop_offset", 0)) % max(1, duracion)
                progreso = min(ahora_en_loop / max(1, duracion), 1.0)
                vel_p *= (1.0 + progreso)  # 1x al inicio, 2x al final
            # (el power-up RELOJ frena via el reloj musical t_musical, arriba;
            #  vel_p queda constante y las posiciones no saltan jamas)
            PIXELES_POR_MS = vel_p / (1000 / 60)
            es_inv = partida.get("es_inverso", False)
            if es_inv:
                ANTICIPACION = (ALTO - zy_p + 40) / PIXELES_POR_MS
            else:
                ANTICIPACION = (zy_p + 40) / PIXELES_POR_MS

            if not partida["terminada"]:
                _lo = partida.get("loop_offset", 0)
                njug = partida["cancion"]["notas_jugador"]
                # anti-avalancha del jugador: al arrancar o al loopear,
                # saltar TODAS las notas cuyo tiempo ya paso. El warm-up
                # (carga de instrumentos, kit, etc) puede tardar segundos,
                # dejando muchas notas atrasadas que se perderian como MISS
                # instantaneo sin que el jugador pueda hacer nada.
                if not partida.get("_arranco_notas"):
                    while (partida["indice_jugador"] < len(njug)
                           and njug[partida["indice_jugador"]]["tiempo"] + _lo < ahora):
                        partida["indice_jugador"] += 1
                    partida["_arranco_notas"] = True
                while partida["indice_jugador"] < len(njug) and ahora >= njug[partida["indice_jugador"]]["tiempo"] + _lo - ANTICIPACION:
                    n = njug[partida["indice_jugador"]]
                    hold_ms = n.get("hold", 0)
                    nota_cae = {
                        "cols":      n["cols"],
                        "midis":     n["midis"],
                        "tiempo_ms": n["tiempo"] + _lo,
                        "acertadas": set(),
                        "es_acorde": n.get("es_acorde", False),
                        "hold":      hold_ms,
                        "hold_px":   hold_pixels(hold_ms, vel_p),
                    }
                    if n.get("power_up"):
                        nota_cae["power_up"] = n["power_up"]
                    if n.get("es_bomba"):
                        nota_cae["es_bomba"] = True
                    partida["notas_cayendo"].append(nota_cae)
                    partida["indice_jugador"] += 1

            for grupo in partida["notas_cayendo"]:
                ms_hasta = grupo["tiempo_ms"] - ahora
                if es_inv:
                    # -28 = alto de la nota: el borde DELANTERO (bottom del rect,
                    # que es el que el jugador ve llegar al subir) cruza la linea
                    # exactamente en el beat, espejando el modo normal.
                    grupo["y"] = zy_p + (ms_hasta * PIXELES_POR_MS) - 28
                else:
                    grupo["y"] = zy_p - (ms_hasta * PIXELES_POR_MS)

            # --- POWER-UP AUTO: el juego toca solo ---
            # toda nota que llega a su beat se acredita como PERFECTO
            # automaticamente, con sonido, puntos y efectos. El jugador
            # no necesita tocar nada (las teclas se pintan de blanco).
            if ahora < partida.get("efectos_activos", {}).get("estrella", 0):
                num_cols_a = partida["dificultad"]["columnas"]
                ancho_col_a = ANCHO // num_cols_a
                col_g_a = COLOR_GENERO.get(partida["cancion"].get("genero", ""), BLANCO)
                auto_restantes = []
                for grupo in partida["notas_cayendo"]:
                    if grupo["tiempo_ms"] <= ahora:
                        # AUTO no debe detonar bombas: las deja pasar (esquivarlas
                        # es lo correcto, y el jugador no controla nada bajo AUTO)
                        if grupo.get("es_bomba"):
                            continue
                        pu_id_a = grupo.get("power_up")
                        if pu_id_a:
                            # auto-atrapar power-ups tambien
                            pu_def_a = next((pu for pu in POWER_UPS if pu["id"] == pu_id_a), None)
                            cxa = grupo["cols"][0] * ancho_col_a + ancho_col_a // 2
                            if pu_def_a:
                                if pu_id_a == "vida":
                                    partida["vida"] = min(partida["vida_max"], partida["vida"] + 4)
                                    crear_texto_flotante(cxa, zy_p - 30, "+4 VIDA", pu_def_a["color"], True)
                                elif pu_def_a["dur"] > 0:
                                    partida["efectos_activos"][pu_id_a] = ahora + pu_def_a["dur"] * (2 if partida.get("perk_cazador") else 1)
                                    crear_texto_flotante(cxa, zy_p - 30, pu_def_a["nombre"], pu_def_a["color"], True)
                                crear_explosion(cxa, zy_p, 80, color=pu_def_a["color"])
                                sfx_power_up(pu_id_a)
                            continue  # power-up consumido, no vuelve a la lista
                        # acreditar como PERFECTO
                        partida["combo"] += 1
                        if partida["combo"] > partida["max_combo"]:
                            partida["max_combo"] = partida["combo"]
                        if (partida.get("perk_regen") and partida["combo"] > 0
                                and partida["combo"] % 20 == 0):
                            partida["vida"] = min(partida["vida_max"], partida["vida"] + 1)
                            crear_texto_flotante(ANCHO // 2, zy_p - 60, "+1 VIDA", (120, 255, 120))
                        pts_a = 10 if partida.get("perk_perfecto") else 5
                        combo_mult_a = 1 + partida["combo"] // partida.get("combo_div", 5)
                        _pu_doble_a = 2.0 if ahora < partida.get("efectos_activos", {}).get("doble", 0) else 1.0
                        bonus_hold = partida.get("hold_bonus", 5) if grupo.get("hold", 0) > 0 else 0
                        total_a = int((pts_a * len(grupo["cols"]) + bonus_hold) * combo_mult_a
                                      * partida.get("mult_mods", 1.0) * _pu_doble_a)
                        partida["puntos"] += total_a
                        # sonido de las notas (afinado con la melodia)
                        for _ma in grupo.get("midis", []):
                            _sa = cache_notas.get(_ma)
                            if _sa:
                                _cha = _sa.play()
                                if _cha:
                                    _cha.set_volume(config["volumen"])
                        # efectos visuales por columna
                        for _ca in grupo["cols"]:
                            cxa = _ca * ancho_col_a + ancho_col_a // 2
                            crear_explosion(cxa, zy_p, 40, color=(255, 255, 100))
                            crear_flash(_ca, 0.5)
                        partida["ultimo_hit"] = {"texto": "AUTO", "tiempo": ahora_ms}
                        crear_texto_flotante(grupo["cols"][0] * ancho_col_a + ancho_col_a // 2,
                                             zy_p - 20, f"+{total_a}", (255, 255, 100))
                    else:
                        auto_restantes.append(grupo)
                partida["notas_cayendo"] = auto_restantes

            notas_vivas = []
            for n in partida["notas_cayendo"]:
                # MISS: la nota se fue de la pantalla
                nota_perdida = n["y"] <= -50 if es_inv else n["y"] >= ALTO + 50
                if nota_perdida:
                    # BOMBA no tocada: se esquivo, NO cuenta como miss (deseado)
                    if n.get("es_bomba"):
                        continue
                    es_hold_activo = any(c in partida["holds_activos"] for c in n["cols"])
                    if not es_hold_activo:
                        partida["ultimo_hit"] = {"texto": "MISS", "tiempo": ahora_ms}
                        # combo_save: el primer miss no rompe combo (cooldown 15s)
                        if partida.get("perk_combo_save") and partida.get("combo_save_cd", 0) <= 0 and partida["combo"] > 0:
                            partida["combo_save_cd"] = 15000
                            crear_texto_flotante(ANCHO // 2, zy_p - 60, "COMBO SAVE!", (100, 200, 255), True)
                        else:
                            partida["combo"] = 0
                        partida["n_miss"] = partida.get("n_miss", 0) + 1
                        # nota que se pasa: NO resta puntos, solo vida.
                        # escudo: absorbe daño de vida
                        if partida.get("escudo_cargas", 0) > 0:
                            partida["escudo_cargas"] -= 1
                            crear_texto_flotante(ANCHO // 2, zy_p - 40, f"ESCUDO ({partida['escudo_cargas']})", (100, 200, 255))
                        elif not dev_mode and not partida.get("es_tutorial"):
                            partida["vida"] = max(0, partida["vida"] - 2)
                            if "sudden" in partida.get("mods", set()):
                                partida["vida"] = 0
                        num_cols = partida["dificultad"]["columnas"]
                        ancho_col = ANCHO // num_cols
                        miss_x = n["cols"][0] * ancho_col + ancho_col // 2
                        miss_y = 30 if es_inv else ALTO - 30
                        crear_shake(4)
                        SND_ERROR.set_volume(0.3 * config["volumen"])
                        SND_ERROR.play()
                        if not dev_mode and partida["vida"] <= 0:
                            if partida.get("perk_resurreccion"):
                                # RESURRECCION: revive UNA vez con 5 de vida.
                                # se consume tambien del run para no re-aplicarse
                                # en stages siguientes.
                                partida["perk_resurreccion"] = False
                                partida["vida"] = 5
                                if run_actual is not None:
                                    run_actual["perks"] = [pk for pk in run_actual.get("perks", [])
                                                           if pk.get("id") != "resurreccion"]
                                crear_texto_flotante(ANCHO // 2, ALTO // 2, "RESURRECCION!", (255, 220, 100), True)
                                crear_explosion(ANCHO // 2, zy_p, 120, color=(255, 220, 100))
                                crear_shake(10)
                            else:
                                partida["game_over"] = True
                                partida["game_over_t"] = pygame.time.get_ticks()
                                _explotar_notas_muerte(partida)
                                pygame.mixer.stop()
                                crear_shake(15)
                                SND_GAMEOVER.set_volume(0.6 * config["volumen"])
                                SND_GAMEOVER.play()
                    else:
                        notas_vivas.append(n)
                else:
                    notas_vivas.append(n)
            partida["notas_cayendo"] = notas_vivas

        actualizar_particulas()
        dibujar_juego(partida, ahora)
        dibujar_particulas()

    presentar()
    clock.tick(60)

pygame.quit()
