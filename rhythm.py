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

ESCALAS = {
    "mayor":       [0, 2, 4, 5, 7, 9, 11, 12],
    "menor":       [0, 2, 3, 5, 7, 8, 10, 12],
    "pentatonica": [0, 2, 4, 7, 9, 12, 14, 16],
    "arm_menor":   [0, 2, 3, 5, 7, 8, 11, 12],
    "blues":       [0, 3, 5, 7, 10, 12, 15, 17],
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
    1:  {"nombre": "FACIL",      "columnas": 3, "acordes": False, "dens": 0.30, "bpm_mult": 0.75, "vel_mult": 0.60},
    2:  {"nombre": "FACIL+",     "columnas": 3, "acordes": False, "dens": 0.40, "bpm_mult": 0.80, "vel_mult": 0.70},
    3:  {"nombre": "NORMAL",     "columnas": 3, "acordes": True,  "dens": 0.50, "bpm_mult": 0.85, "vel_mult": 0.75},
    4:  {"nombre": "NORMAL+",    "columnas": 4, "acordes": False, "dens": 0.45, "bpm_mult": 0.85, "vel_mult": 0.80},
    5:  {"nombre": "NORMAL++",   "columnas": 4, "acordes": True,  "dens": 0.55, "bpm_mult": 0.90, "vel_mult": 0.85},
    6:  {"nombre": "INTERMEDIO", "columnas": 4, "acordes": True,  "dens": 0.65, "bpm_mult": 0.90, "vel_mult": 0.90},
    7:  {"nombre": "INTERMEDIO+","columnas": 4, "acordes": True,  "dens": 0.80, "bpm_mult": 0.95, "vel_mult": 0.95},
    8:  {"nombre": "DIFICIL",    "columnas": 5, "acordes": True,  "dens": 0.85, "bpm_mult": 1.0,  "vel_mult": 1.0},
    9:  {"nombre": "DIFICIL+",   "columnas": 5, "acordes": True,  "dens": 1.00, "bpm_mult": 1.0,  "vel_mult": 1.0},
    10: {"nombre": "PRO",        "columnas": 6, "acordes": True,  "dens": 1.00, "bpm_mult": 1.0,  "vel_mult": 1.0},
    11: {"nombre": "PRO+",       "columnas": 6, "acordes": True,  "dens": 1.15, "bpm_mult": 1.0,  "vel_mult": 1.05},
    12: {"nombre": "MASTER",     "columnas": 7, "acordes": True,  "dens": 1.10, "bpm_mult": 1.0,  "vel_mult": 1.05},
    13: {"nombre": "MASTER+",    "columnas": 7, "acordes": True,  "dens": 1.25, "bpm_mult": 1.0,  "vel_mult": 1.10},
    14: {"nombre": "GOD",        "columnas": 7, "acordes": True,  "dens": 1.40, "bpm_mult": 1.0,  "vel_mult": 1.15},
    15: {"nombre": "CHAOS",      "columnas": 8, "acordes": True,  "dens": 1.60, "bpm_mult": 1.0,  "vel_mult": 1.20},
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
]
mods_activos = set()   # ids de modificadores seleccionados (modo libre)

# mods "faciles" que pueden salir en el dado de los stages 2 y 3
MODS_FACILES = ["espejo", "inverso", "veloz", "acelerando", "niebla", "rafagas"]

# --- perks roguelike: se eligen entre stages y se acumulan ---
PERKS = [
    {"id": "escudo",     "nombre": "ESCUDO",     "desc": "absorbe 3 misses",        "cat": "def"},
    {"id": "corazon",    "nombre": "CORAZON",    "desc": "+5 vida maxima",           "cat": "def"},
    {"id": "ventana",    "nombre": "VENTANA",    "desc": "timing 25% mas amplio",    "cat": "def"},
    {"id": "multi",      "nombre": "MULTI",      "desc": "puntos x1.5",             "cat": "ofe"},
    {"id": "combo_save", "nombre": "COMBO SAVE", "desc": "1er miss no rompe combo",  "cat": "ofe"},
    {"id": "perfecto",   "nombre": "PERFECTO+",  "desc": "perfectos valen doble",    "cat": "ofe"},
    {"id": "lento",      "nombre": "LENTO",      "desc": "notas 15% mas lentas",     "cat": "mec"},
    {"id": "iman",       "nombre": "IMAN",       "desc": "zona perfecto expandida",  "cat": "mec"},
]

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
    dur = rng.uniform(0.02, 0.06)
    freq = rng.uniform(800, 2500)
    n = int(SR * dur)
    t = np.linspace(0, dur, n)
    env = np.exp(-t * rng.uniform(40, 100))
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
    dur = rng.uniform(0.1, 0.3)
    freq1 = rng.uniform(800, 1500)
    freq2 = freq1 * rng.uniform(1.3, 1.8)
    n = int(SR * dur)
    t = np.linspace(0, dur, n)
    env = np.exp(-t * rng.uniform(10, 25))
    wave = (np.sin(2 * np.pi * freq1 * t) * 0.5 + np.sin(2 * np.pi * freq2 * t) * 0.5) * env
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
    kit_intensity = rng.uniform(0.15, 0.4)
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
    "SHIMMER":    "shimmer",
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
    "SHIMMER", "ATMOS NOISE", "FROZEN STR", "DREAM PAD", "SPACE CHOIR", "ANALOG STR",
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
    "SHIMMER": "atmos", "ATMOS NOISE": "atmos",
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
    elif tipo == "shimmer":
        # pad con chorus de altisimas voces que se mueven lentamente
        num_v = rng_params.get("num_voices", 8)
        wave = np.zeros(n)
        for v in range(num_v):
            d = (v - num_v / 2) * rng_params.get("detune_wide", 0.012)
            spd = rng_params.get("lfo_spd", 0.4) + v * 0.17
            ph_off = v * 0.73
            p = 2 * np.pi * freq * (1 + d) * t + np.sin(2 * np.pi * spd * t + ph_off) * 0.08
            # armonicos superiores suaves para el brillo
            wave += np.sin(p) * 0.25 + np.sin(p * 2) * 0.08 + np.sin(p * 3) * 0.03
        # filtro pasa-bajos en tiempo real (IIR simple)
        cutoff = rng_params.get("cutoff_lp", 0.04)
        filtered = np.zeros(n)
        prev = 0.0
        for i in range(n):
            prev = prev + cutoff * (wave[i] - prev)
            filtered[i] = prev
        wave = filtered
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
        "shimmer": 0.65, "atmos_noise": 0.55, "frozen_strings": 0.65,
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
    elif tipo == "shimmer":
        params["attack"] = rng.uniform(0.1, 0.4); params["decay"] = rng.uniform(0.8, 2)
        params["sustain"] = rng.uniform(0.7, 0.95)
        params["num_voices"] = rng.randint(6, 10); params["detune_wide"] = rng.uniform(0.008, 0.018)
        params["lfo_spd"] = rng.uniform(0.2, 0.7); params["cutoff_lp"] = rng.uniform(0.03, 0.07)
        params["vibrato"] = rng.uniform(0, 0.1)
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
    inst_eq_int = inst_rng.uniform(0.1, 0.35)
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
        c_cortas[midi] = np_to_sound(aplicar_eq(arr[:, 0], inst_eq, inst_eq_int), lpf=True)
        params_hold = dict(params)
        params_hold["vibrato"] = params.get("vibrato", 0) + 0.4
        params_hold["vib_speed"] = params.get("vib_speed", 5) * 0.8
        params_hold["sustain"] = max(params.get("sustain", 0.6), 0.5)
        params_hold["decay"] = min(params.get("decay", 5.0), 1.5)
        # nota larga de 1.6s (antes 4s): 2.5x mas rapido de renderizar
        snd_l = synth_nota(tipo, freq, 1.6, params_hold)
        arr_l = pygame.sndarray.array(snd_l).astype(np.float64) / 32767
        mono_l = aplicar_eq(arr_l[:, 0], inst_eq, inst_eq_int)
        # crossfade para loop suave: mezclar final con inicio
        cf = min(3000, len(mono_l) // 4)
        fade_out = np.linspace(1, 0, cf)
        fade_in  = np.linspace(0, 1, cf)
        mono_l[-cf:] = mono_l[-cf:] * fade_out + mono_l[:cf] * fade_in
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
    # mas tramos (y mas anchos) en la zona facil/normal/intermedia
    tramos = [400, 900, 1500, 2200, 3000, 3900, 4900, 5700, 6400,
              7100, 7800, 8400, 9000, 9500, 9999]
    for i, tope in enumerate(tramos):
        if seed <= tope:
            d = dict(DIFICULTADES[i + 1]); d["nivel"] = i + 1; return d
    d = dict(DIFICULTADES[15]); d["nivel"] = 15; return d

# --- meta de puntuacion por stage (objetivo roguelike) ---
# la meta base escala con el nivel de dificultad; stages sucesivos piden mas
META_BASE = {
    1: 200,  2: 250,  3: 350,  4: 450,  5: 600,
    6: 800,  7: 1100, 8: 1500, 9: 2000, 10: 2800,
    11: 3500, 12: 4500, 13: 6000, 14: 8000, 15: 10000,
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
    },
    "HIP HOP": {
        "bpm": (82, 96),
        "escalas": ["menor", "blues", "pentatonica"],
        "drums": {
            "kick":  [[1,0,0,0,0,0,1,0,0,0,1,0,0,0,0,0],   # boom-bap
                      [1,0,0,0,0,0,0,1,0,0,1,0,0,0,0,0]],
            "snare": [[0,0,0,0,1,0,0,0,0,0,0,0,1,0,0,0]],
            "hihat": [[1,0,1,0,1,0,1,0,1,0,1,0,1,0,1,1],
                      [1,0,1,0,1,0,1,1,1,0,1,0,1,0,1,0]],
            "hihat_o":[0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,0],
            "clap":  [0,0,0,0,1,0,0,0,0,0,0,0,1,0,0,0],
        },
        "bajo_estilos": ["sub", "round", "pluck"],
        "bajo_patrones": [[1,0,0,0,0,0,1,0,0,0,1,0,0,0,0,0],
                          [1,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0]],
        "instrumentos": ["FM EP", "BASS", "SYNTHBASS", "SUB PLUCK", "ORGAN",
                         "VIBRAPHONE", "PLUCK SOFT", "DIST GTR",
                         "ANALOG STR", "DREAM PAD"],
        "tempo_mod": {"half": 0.20, "double": 0.05},
        "densidad": 0.75,
        "swing": 0.12,
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
                         "SHIMMER", "ANALOG STR", "DREAM PAD"],
        "tempo_mod": {"half": 0.10, "double": 0.10},
        "densidad": 0.95,
        "swing": 0.0,
        "arpegios": True,
    },
    "AMBIENT": {
        "bpm": (62, 86),
        "escalas": ["mayor", "menor", "pentatonica"],
        "drums": {
            "kick":  [[1,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0],
                      [1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]],
            "snare": [[0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
                      [0,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0]],
            "hihat": [[0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
                      [1,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0]],
            "hihat_o":[0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
            "clap":  [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
        },
        "bajo_estilos": ["sub", "round"],
        "bajo_patrones": [[1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
                          [1,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0]],
        "instrumentos": ["PAD", "PHASE PAD", "VOX PAD", "GLASS", "BELLPAD",
                         "CHOIR", "GLASS HARM", "FLUTE", "HARP", "BELL FM",
                         "SHIMMER", "ATMOS NOISE", "FROZEN STR", "DREAM PAD", "SPACE CHOIR"],
        "tempo_mod": {"half": 0.40, "double": 0.0},
        "densidad": 0.4,
        "swing": 0.0,
    },
    "REGGAETON": {
        "bpm": (90, 100),
        "escalas": ["menor", "arm_menor", "pentatonica"],
        "drums": {
            "kick":  [[1,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0]],   # dembow base
            "snare": [[0,0,0,1,0,0,1,0,0,0,0,1,0,0,1,0]],    # dembow
            "hihat": [[1,0,1,0,1,0,1,0,1,0,1,0,1,0,1,0]],
            "hihat_o":[0,0,0,0,0,0,1,0,0,0,0,0,0,0,1,0],
            "clap":  [0,0,0,1,0,0,1,0,0,0,0,1,0,0,1,0],     # acompaña al snare
        },
        "bajo_estilos": ["sub", "round", "pluck"],
        "bajo_patrones": [[1,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0],
                          [1,0,0,0,1,0,0,0,1,0,0,0,1,0,0,0]],
        "instrumentos": ["SYNTHBASS", "SUB PLUCK", "PLUCK", "LEAD", "DETUNE",
                         "ACID", "SAW", "PWM LEAD", "KALIMBA"],
        "tempo_mod": {"half": 0.05, "double": 0.05},
        "densidad": 0.85,
        "swing": 0.0,
    },
}

# paletas de color por genero (color de acento, se mezcla con blanco/gris)
COLOR_GENERO = {
    "TECHNO":    (0, 220, 255),    # cyan electrico
    "HIP HOP":   (255, 160, 40),   # naranja calido
    "DNB":       (180, 60, 255),   # violeta neon
    "SYNTHWAVE": (255, 60, 180),   # rosa magenta retro
    "AMBIENT":   (120, 230, 180),  # verde agua suave
    "REGGAETON": (255, 220, 40),   # amarillo vibrante
}
COLOR_DEFECTO = (255, 255, 255)

def color_genero(partida):
    g = partida["cancion"].get("genero", "")
    return COLOR_GENERO.get(g, COLOR_DEFECTO)

def elegir_genero(rng):
    # pesos: AMBIENT sale mucho menos (~0.5% vs ~20% cada otro)
    pesos = {
        "TECHNO": 20, "HIP HOP": 20, "DNB": 20,
        "SYNTHWAVE": 20, "AMBIENT": 1, "REGGAETON": 20,
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
        # detalles percusivos extra solo en algunos generos
        if genero in ("REGGAETON", "HIP HOP"):
            for p in rng.sample(range(16), rng.randint(1, 3)):
                pats["clave"][p] = 1
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
                      c_intro, c_nudo, c_desenlace, kit, genero=None):
    paso = beat // 4
    pats  = generar_patrones_drums(rng, genero)
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
                percusion.append({"tiempo": t, "sample": "clave", "vol": 0.04})
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
}

def elegir_forma(rng, nivel_dif):
    """Elige un arquetipo de forma segun la seed y el nivel de dificultad.
    Niveles bajos -> formas mas simples y cortas; altos -> mas elaboradas.
    La seleccion es variable por seed: dos canciones del mismo nivel pueden
    tener formas distintas (una simple, otra con puente)."""
    if nivel_dif <= 3:
        pool = ["corta", "corta", "minima", "simple"]
    elif nivel_dif <= 7:
        pool = ["simple", "simple", "pop", "corta", "con_pre"]
    elif nivel_dif <= 11:
        pool = ["pop", "pop", "con_pre", "simple", "epica"]
    else:
        pool = ["pop", "con_pre", "epica", "epica"]
    return FORMAS_CANCION[rng.choice(pool)]

def compases_por_seccion(nombre, rng, nivel_dif):
    """Cuantos compases dura cada tipo de seccion (variable por seed)."""
    if nombre in ("intro", "outro"):
        return rng.choice([2, 2, 4]) if nivel_dif <= 6 else rng.choice([2, 4, 4])
    if nombre == "preestribillo":
        return rng.choice([2, 2, 4])
    if nombre == "puente":
        return rng.choice([4, 4, 8])
    # verso y estribillo: bloques de 4 u 8 compases
    return rng.choice([4, 4, 8]) if nivel_dif >= 6 else rng.choice([4, 4])


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

    # notas por columna: grados CONSECUTIVOS de la escala (no cada 2).
    # Esto es clave para la musicalidad: columnas vecinas = notas vecinas, lo
    # que permite el movimiento por grado conjunto (paso a paso), base de toda
    # melodia cantable. Antes se saltaba de a 2 grados (i*2) y la melodia salia
    # como un arpegio monotono tonica-tercera-quinta.
    notas_columnas = [nota_midi(tonica + 12, escala, i) for i in range(num_columnas)]
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

    notas_jugador = []

    def crear_compas(motivo, pat, permitir_hold=True):
        """Genera un compas (16 pasos) colocando las notas del motivo en las
        posiciones activas del patron ritmico. Devuelve lista de 16 (None o dict)."""
        nota_idx = 0
        compas = []
        for s in range(16):
            if pat[s] == 0:
                compas.append(None)
                continue
            col = motivo[nota_idx % len(motivo)]
            nota_idx += 1
            compas.append({"col": col, "hold": 0})
        if permitir_hold:
            # prob de hold escala con el nivel: 0.32 (facil) -> 0.55 (chaos)
            prob_hold = 0.3 + min(0.25, dif.get("nivel", 1) * 0.017)
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
        """Crea el contenido melodico (lista de compases) de una seccion segun
        su material. El estribillo (B) usa SIEMPRE el mismo patron ritmico y
        motivo, para que el gancho sea reconocible cada vez que vuelve."""
        if material == "B":
            motivo = motivos_b[0]
        elif material == "C":
            motivo = motivos_c[0]
        else:
            motivo = motivos_a[rng.randint(0, len(motivos_a) - 1)]
        pats = pat_jugador_complejos if complejo else pat_jugador_simples
        # el estribillo fija sus patrones (memorable); verso/puente varian mas
        if material == "B":
            pat1 = pats[rng.randint(0, len(pats) - 1)]
            pat2 = pat1   # mismo patron los 2 compases -> mas pegadizo
        else:
            pat1 = pats[rng.randint(0, len(pats) - 1)]
            pat2 = pats[rng.randint(0, len(pats) - 1)]
        bloque = []
        for c in range(num_compases):
            pat = pat1 if c % 2 == 0 else pat2
            bloque.append(crear_compas(motivo, pat))
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
        oct_off = perfil["registro"]
        energia = perfil["energia"]
        dens_local = densidad * perfil["densidad_mult"]
        # densidad acotada por nivel: piso creciente (nivel 15 nunca saltea
        # notas) y techo en los primeros niveles (el facil se mantiene amable)
        _niv_d = dif.get("nivel", 1)
        dens_local = max(dens_local, 0.15 + _niv_d * 0.057)
        if _niv_d <= 2:
            dens_local = min(dens_local, 0.45)
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
            if (usar_acordes or energia >= 0.9) and s_acorde_ok and pone_acorde:
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
            # densidad segun energia de la seccion (nunca saltea el downbeat)
            # en estribillo NO se saltean notas por rng: el patron es fijo y completo
            if not det and dens_local < 1.0 and s != 0 and rng.random() > dens_local:
                continue
            midi_nota = notas_columnas[col] + oct_off
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
                                  C_INTRO, C_NUDO, C_DESENLACE, kit, genero)

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
    lissajous = {
        "tipo": rng.choice(["lissajous", "lissajous", "rosa", "espiro", "mariposa"]),
        "a": rng.randint(1, 9),         # frecuencia horizontal
        "b": rng.randint(1, 9),         # frecuencia vertical
        "delta": rng.uniform(0, 6.28),  # desfase
        "vel": rng.uniform(0.1, 0.6),   # velocidad de animacion
        "puntos": rng.choice([160, 200, 240, 300]),
        "k": rng.randint(2, 7),         # parametro para rosa/espiro
        "ratio": rng.uniform(0.3, 0.8), # parametro para espiro
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
    cancion = generar_cancion(int(seed * 23819), dif, instrumento_forzado=instrumento_forzado)
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
    gen_txt = fuente.render(f"{cancion.get('genero', '')}", True, COLOR_GENERO.get(cancion.get('genero',''), BLANCO))
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
        # solo_drums: la percusion suena mas fuerte
        boost = 1.6 if evento_activo == "solo_drums" else 1.2
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
    vol_bajo = 1.5 if evento_activo == "boost_bajo" else 1.0
    while partida["indice_bajo"] < len(bajo) and ahora >= bajo[partida["indice_bajo"]]["tiempo"] + loop_off:
        ev = bajo[partida["indice_bajo"]]
        snd_b = cache_bajo.get(ev["midi"])
        if snd_b:
            ch_b = snd_b.play()
            if ch_b:
                ch_b.set_volume(min(1.0, config["volumen"] * vol_bajo))
        partida["indice_bajo"] += 1

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
                # aplicar fade de niebla al color de la nota
                if es_niebla and alpha_niebla < 1.0:
                    cn = (int(col_nota[0] * alpha_niebla),
                          int(col_nota[1] * alpha_niebla),
                          int(col_nota[2] * alpha_niebla))
                else:
                    cn = col_nota
                # power-up: nota especial con animacion propia por tipo
                pu_id = grupo.get("power_up")
                if pu_id:
                    _mt = math
                    pu_def = next((p for p in POWER_UPS if p["id"] == pu_id), None)
                    pc = pu_def["color"] if pu_def else BLANCO
                    t_anim = ahora_ms / 1000.0
                    nota_h = 40
                    ny = gy - 6
                    ccx = x + ancho_col // 2          # centro X de la nota
                    ccy = int(ny + nota_h // 2)       # centro Y
                    brill = 0.75 + 0.25 * _mt.sin(t_anim * 6.0)
                    cn = (int(pc[0] * brill), int(pc[1] * brill), int(pc[2] * brill))

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
                        pygame.draw.rect(pantalla, BLANCO, (x + 2, ny, ancho_col - 4, nota_h), 2)

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
                        pygame.draw.rect(pantalla, BLANCO,
                                         (x + 2 - exp, ny - exp,
                                          ancho_col - 4 + exp * 2, nota_h + exp * 2), 2)

                    elif pu_id == "reloj":
                        # SLOW: aguja de reloj girando LENTA + anillo
                        pygame.draw.rect(pantalla, cn, (x + 2, ny, ancho_col - 4, nota_h))
                        pygame.draw.rect(pantalla, BLANCO, (x + 2, ny, ancho_col - 4, nota_h), 2)
                        rad = min(ancho_col // 2 - 8, nota_h // 2 + 8)
                        pygame.draw.circle(pantalla, BLANCO, (ccx, ccy), rad, 2)
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
                        pygame.draw.rect(pantalla, BLANCO, (x + 2, ny, ancho_col - 4, nota_h), 2)

                    else:
                        pygame.draw.rect(pantalla, cn, (x + 2, ny, ancho_col - 4, nota_h))
                        pygame.draw.rect(pantalla, BLANCO, (x + 2, ny, ancho_col - 4, nota_h), 2)

                    # label centrado (comun a todos)
                    iconos_pu = {"estrella": "AUTO", "vida": "+HP", "reloj": "SLOW", "doble": "x2"}
                    pu_lbl = fuente.render(iconos_pu.get(pu_id, "?"), True, NEGRO)
                    pantalla.blit(pu_lbl, (ccx - pu_lbl.get_width() // 2,
                                           ccy - pu_lbl.get_height() // 2))
                elif grupo.get("es_acorde"):
                    pygame.draw.rect(pantalla, cn, (x + 6,  gy,     ancho_col - 12, 28))
                    pygame.draw.rect(pantalla, NEGRO,  (x + 9,  gy + 3, ancho_col - 18, 22))
                    pygame.draw.rect(pantalla, cn, (x + 11, gy + 5, ancho_col - 22, 18))
                else:
                    pygame.draw.rect(pantalla, cn, (x + 6, gy, ancho_col - 12, 28))
            xs.append(x + ancho_col // 2)
        if len(xs) > 1:
            pygame.draw.line(pantalla, col_nota, (xs[0], gy + 14), (xs[-1], gy + 14), 2)

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
        go_txt = fuente_grande.render("GAME OVER", True, BLANCO)
        pantalla.blit(go_txt, (ANCHO // 2 - go_txt.get_width() // 2, ALTO // 2 - 50))
        sc_txt = fuente.render(f"PUNTOS: {partida['puntos']}  MAX COMBO: {partida['max_combo']}x", True, GRIS_MED)
        pantalla.blit(sc_txt, (ANCHO // 2 - sc_txt.get_width() // 2, ALTO // 2 + 10))
        if run_actual is not None:
            esc2 = fuente_chica.render("ESPACIO = RESULTADO DEL RUN", True, GRIS)
        else:
            esc2 = fuente_chica.render("ESC PARA VOLVER", True, GRIS)
        pantalla.blit(esc2, (ANCHO // 2 - esc2.get_width() // 2, ALTO // 2 + 50))
        ruta = partida.get("export_ruta")
        if ruta:
            ok_txt = fuente_chica.render("GUARDADA EN export/", True, BLANCO)
            pantalla.blit(ok_txt, (ANCHO // 2 - ok_txt.get_width() // 2, ALTO // 2 + 75))
        elif partida.get("exportando"):
            ex_txt = fuente_chica.render("GUARDANDO...", True, GRIS_MED)
            pantalla.blit(ex_txt, (ANCHO // 2 - ex_txt.get_width() // 2, ALTO // 2 + 75))
        else:
            dl_txt = fuente_chica.render("D = DESCARGAR CANCION", True, BLANCO)
            pantalla.blit(dl_txt, (ANCHO // 2 - dl_txt.get_width() // 2, ALTO // 2 + 75))

    elif partida["terminada"] and not partida["notas_cayendo"]:
        col_g = COLOR_GENERO.get(partida["cancion"].get("genero", ""), BLANCO)
        meta = partida.get("meta_puntos", 0)
        if partida.get("es_tutorial"):
            fin = fuente.render("TUTORIAL COMPLETADO!", True, col_g)
        elif meta > 0:
            fin = fuente.render("META ALCANZADA!", True, col_g)
        else:
            fin = fuente.render("FIN", True, BLANCO)
        pantalla.blit(fin, (ANCHO // 2 - fin.get_width() // 2, ALTO // 2 - 40))
        if run_actual is not None:
            # en run: mostrar lo ganado en el stage y el total acumulado
            ganado = partida["puntos"] - partida.get("puntos_stage_inicio", 0)
            sc_txt = fuente.render(f"STAGE: +{ganado}   TOTAL: {partida['puntos']}", True, GRIS_MED)
            pantalla.blit(sc_txt, (ANCHO // 2 - sc_txt.get_width() // 2, ALTO // 2))
            cb_txt = fuente_chica.render(f"MAX COMBO: {partida['max_combo']}x", True, GRIS)
            pantalla.blit(cb_txt, (ANCHO // 2 - cb_txt.get_width() // 2, ALTO // 2 + 30))
        else:
            sc_txt = fuente.render(f"PUNTOS: {partida['puntos']}  MAX COMBO: {partida['max_combo']}x", True, GRIS_MED)
            pantalla.blit(sc_txt, (ANCHO // 2 - sc_txt.get_width() // 2, ALTO // 2))
        # texto de accion (siguiente stage / volver)
        if run_actual is not None:
            stage_n = run_actual["stage"]
            if stage_n < NUM_STAGES:
                esc2 = fuente_chica.render(f"ESPACIO = SIGUIENTE STAGE ({stage_n + 1}/{NUM_STAGES})", True, GRIS)
            else:
                esc2 = fuente_chica.render("ESPACIO = COMPLETAR RUN!", True, GRIS)
        else:
            esc2 = fuente_chica.render("ESC PARA VOLVER", True, GRIS)
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

TUTORIAL_NUM_PAGINAS = 7
tutorial_pagina = 0

def dibujar_tutorial(pagina):
    """Tutorial de 7 paginas con graficos en vivo. La ultima ofrece practica."""
    pantalla.fill(NEGRO)
    t_anim = pygame.time.get_ticks() / 1000.0
    cx = ANCHO // 2

    titulos = ["OBJETIVO", "NOTAS", "HOLDS Y ACORDES", "VIDA Y COMBO",
               "POWER-UPS", "PERKS", "MODIFICADORES"]
    titulo = fuente_grande.render(titulos[pagina], True, BLANCO)
    pantalla.blit(titulo, (cx - titulo.get_width() // 2, 36))
    pygame.draw.line(pantalla, GRIS, (60, 96), (ANCHO - 60, 96), 1)

    def linea(texto, y, color=GRIS_MED, f=None):
        f = f or fuente_chica
        txt = f.render(texto, True, color)
        pantalla.blit(txt, (cx - txt.get_width() // 2, y))

    if pagina == 0:
        # OBJETIVO
        linea("CADA STAGE TIENE UNA META DE PUNTOS", 130, BLANCO, fuente)
        linea("LA CANCION SE REPITE HASTA QUE LA ALCANCES", 165)
        linea("(O HASTA QUE TE QUEDES SIN VIDA)", 185)
        # barra de meta animada
        bar_w, bar_x, bar_y = 360, cx - 180, 250
        prog = (math.sin(t_anim * 0.8) * 0.5 + 0.5)
        pygame.draw.rect(pantalla, GRIS, (bar_x, bar_y, bar_w, 16))
        pygame.draw.rect(pantalla, (255, 180, 60), (bar_x, bar_y, int(bar_w * prog), 16))
        pygame.draw.rect(pantalla, BLANCO, (bar_x, bar_y, bar_w, 16), 1)
        linea(f"{int(prog*325)}/325", 275, GRIS_MED)
        linea("LA BARRA DE META ESTA ARRIBA A LA DERECHA", 320)
        linea("LOS MULTIPLICADORES TE AYUDAN A LLEGAR ANTES", 345)
        linea("UN RUN SON 4 STAGES: LA META CRECE EN CADA UNO", 385, BLANCO)

    elif pagina == 1:
        # NOTAS
        linea("LAS NOTAS CAEN POR COLUMNAS", 125, BLANCO, fuente)
        linea("APRETA LA TECLA CUANDO LA NOTA CRUZA LA LINEA", 160)
        # mini demo: 3 columnas, nota animada cayendo
        demo_x, demo_y, demo_w, demo_h = cx - 150, 195, 300, 190
        col_w = demo_w // 3
        for i in range(1, 3):
            pygame.draw.line(pantalla, GRIS, (demo_x + i * col_w, demo_y), (demo_x + i * col_w, demo_y + demo_h), 1)
        pygame.draw.rect(pantalla, GRIS, (demo_x, demo_y, demo_w, demo_h), 1)
        linea_y = demo_y + demo_h - 40
        pygame.draw.line(pantalla, (255, 180, 60), (demo_x, linea_y), (demo_x + demo_w, linea_y), 2)
        # nota cayendo en loop
        fall = (t_anim * 0.5) % 1.0
        ny = demo_y + 10 + fall * (linea_y - demo_y - 20)
        pygame.draw.rect(pantalla, BLANCO, (demo_x + col_w + 8, ny, col_w - 16, 20))
        for i, lbl in enumerate(["A", "S", "D"]):
            l = fuente_chica.render(lbl, True, GRIS_MED)
            pantalla.blit(l, (demo_x + i * col_w + col_w // 2 - l.get_width() // 2, linea_y + 12))
        # precision
        linea("PRECISION:", 400, BLANCO)
        linea("PERFECTO (justo) > BIEN > OK > MAL (resta puntos)", 422)
        linea("EN FACIL LA TECLA SE ILUMINA CUANDO HAY QUE APRETAR", 452, (255, 180, 60))

    elif pagina == 2:
        # HOLDS Y ACORDES
        linea("NOTA LARGA (HOLD): MANTENE LA TECLA APRETADA", 130, BLANCO, fuente)
        # dibujo de hold: barra vertical + nota
        hx = cx - 130
        pygame.draw.rect(pantalla, GRIS_MED, (hx - 6, 170, 12, 90))
        pygame.draw.rect(pantalla, BLANCO, (hx - 6, 170, 12, 90), 1)
        pygame.draw.rect(pantalla, BLANCO, (hx - 30, 260, 60, 22))
        linea2 = fuente_chica.render("MANTENE HASTA QUE LA BARRA TERMINE (+3 PTS)", True, GRIS_MED)
        pantalla.blit(linea2, (cx - 60, 215))
        # acorde
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
        linea("VIDA: CADA MISS TE RESTA 2 PUNTOS DE VIDA", 130, BLANCO, fuente)
        # barra HP
        pygame.draw.rect(pantalla, GRIS, (cx - 100, 165, 200, 10))
        hp = (math.sin(t_anim) * 0.3 + 0.6)
        pygame.draw.rect(pantalla, BLANCO, (cx - 100, 165, int(200 * hp), 10))
        pygame.draw.rect(pantalla, BLANCO, (cx - 100, 165, 200, 10), 1)
        linea("SI LLEGA A CERO: GAME OVER", 190)
        linea("COMBO: HITS SEGUIDOS SIN FALLAR", 250, BLANCO, fuente)
        combo_n = int((t_anim * 4) % 30) + 1
        ctxt = fuente.render(f"{combo_n}x COMBO", True, (255, 180, 60))
        pantalla.blit(ctxt, (cx - ctxt.get_width() // 2, 285))
        linea("CADA 5 DE COMBO SUBE EL MULTIPLICADOR DE PUNTOS", 325)
        linea("UN MISS ROMPE EL COMBO (SALVO CON EL PERK COMBO SAVE)", 350)
        linea("TOCA CON PRECISION PARA MANTENER LA RACHA", 395, (255, 180, 60))

    elif pagina == 4:
        # POWER-UPS
        linea("NOTAS ESPECIALES QUE APARECEN EN LA CANCION", 125, BLANCO, fuente)
        linea("ATRAPALAS PARA ACTIVAR EFECTOS TEMPORALES", 155)
        pu_info = [
            ("AUTO", (255, 255, 100), "EL JUEGO TOCA SOLO 6s (TECLAS BLANCAS)"),
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

    elif pagina == 5:
        # PERKS
        linea("AL COMPLETAR UN STAGE ELEGIS 1 DE 3 MEJORAS", 125, BLANCO, fuente)
        linea("SE ACUMULAN DURANTE TODO EL RUN", 155)
        perk_info = [
            ("DEFENSIVOS", "ESCUDO (absorbe misses)  CORAZON (+vida)  VENTANA (timing amplio)"),
            ("OFENSIVOS",  "MULTI (x1.5 pts)  COMBO SAVE  PERFECTO+ (doble)"),
            ("MECANICOS",  "LENTO (notas lentas)  IMAN (perfecto amplio)"),
        ]
        y0 = 210
        for i, (cat, lista) in enumerate(perk_info):
            y = y0 + i * 70
            ctxt = fuente.render(cat, True, (255, 180, 60))
            pantalla.blit(ctxt, (cx - ctxt.get_width() // 2, y))
            ltxt = fuente_chica.render(lista, True, GRIS_MED)
            pantalla.blit(ltxt, (cx - ltxt.get_width() // 2, y + 28))
        linea("ELEGI SEGUN TU ESTILO: SOBREVIVIR O PUNTUAR MAS RAPIDO", 445, BLANCO)

    elif pagina == 6:
        # MODS
        linea("DESDE EL STAGE 2 SE AGREGAN MODIFICADORES", 125, BLANCO, fuente)
        linea("HACEN EL JUEGO MAS DIFICIL PERO MULTIPLICAN TUS PUNTOS", 155)
        mods_info = [
            ("ESPEJO",     "las teclas se invierten (A toca la ultima columna)"),
            ("INVERSO",    "las notas suben desde abajo"),
            ("VELOZ",      "todo cae al doble de velocidad"),
            ("ACELERANDO", "la velocidad sube durante la cancion"),
            ("NIEBLA",     "las notas aparecen desde la mitad"),
            ("RAFAGAS",    "tramos densos alternados con silencios"),
            ("SUDDEN",     "un solo error = game over (x2.0 pts!)"),
        ]
        y0 = 200
        for i, (nom, desc) in enumerate(mods_info):
            y = y0 + i * 30
            ntxt = fuente_chica.render(nom, True, BLANCO)
            pantalla.blit(ntxt, (cx - 250, y))
            dtxt = fuente_chica.render(desc, True, GRIS_MED)
            pantalla.blit(dtxt, (cx - 110, y))
        linea("EL DADO REVELA EL MOD ANTES DE CADA STAGE", 430, (255, 180, 60))

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

def dibujar_menu(seed_actual, cargando):
    dif      = get_dificultad(max(seed_actual, 1))
    progreso = min(seed_actual / SEED_MAX, 1.0)

    # visualizador de barras tipo ecualizador (fondo animado)
    tms = pygame.time.get_ticks() * 0.003
    n_barras = 32
    bw = ANCHO // n_barras
    for i in range(n_barras):
        # cada barra oscila con una mezcla de senos para parecer musica
        h = (math.sin(tms + i * 0.4) * 0.5 + 0.5)
        h *= (math.sin(tms * 1.7 + i * 0.9) * 0.3 + 0.7)
        altura = int(h * 160) + 4
        bx = i * bw
        by = ALTO - altura
        gris = 18 + int(h * 30)
        pygame.draw.rect(pantalla, (gris, gris, gris), (bx, by, bw - 2, altura))

    # notas musicales flotando suave
    for j in range(6):
        nx = (j * 137 + int(tms * 20)) % (ANCHO + 60) - 30
        ny = 200 + int(math.sin(tms * 0.8 + j) * 80) + j * 30
        ny = ny % ALTO
        dibujar_nota_musical(pantalla, nx, ny, 16 + (j % 3) * 6, (30, 30, 30))

    titulo = fuente_grande.render("* RHYTHM *", True, BLANCO)
    pantalla.blit(titulo, (ANCHO // 2 - titulo.get_width() // 2, 70))
    pygame.draw.line(pantalla, BLANCO, (60, 140), (ANCHO - 60, 140), 2)

    ins = fuente_chica.render("MANTENE ESPACIO PARA CARGAR", True, GRIS_MED)
    pantalla.blit(ins, (ANCHO // 2 - ins.get_width() // 2, 170))

    barra_w = 400
    barra_x = ANCHO // 2 - barra_w // 2
    barra_y = 210
    pygame.draw.rect(pantalla, GRIS, (barra_x, barra_y, barra_w, 20))
    if seed_actual > 0:
        bloques = int(barra_w * progreso) // 10
        for b in range(bloques):
            pygame.draw.rect(pantalla, BLANCO, (barra_x + b * 10 + 1, barra_y + 2, 8, 16))
    pygame.draw.rect(pantalla, BLANCO, (barra_x, barra_y, barra_w, 20), 2)

    seed_str   = str(int(seed_actual)).zfill(6) if seed_actual > 0 else "000000"
    seed_texto = fuente_grande.render(seed_str, True, BLANCO)
    pantalla.blit(seed_texto, (ANCHO // 2 - seed_texto.get_width() // 2, 260))

    pygame.draw.line(pantalla, GRIS, (60, 340), (ANCHO - 60, 340), 1)
    dif_texto  = fuente.render(f"> {dif['nombre']} <", True, BLANCO)
    pantalla.blit(dif_texto, (ANCHO // 2 - dif_texto.get_width() // 2, 355))
    cols_texto = fuente_chica.render(f"{dif['columnas']} COLUMNAS  {'ACORDES ON' if dif['acordes'] else 'ACORDES OFF'}", True, GRIS_MED)
    pantalla.blit(cols_texto, (ANCHO // 2 - cols_texto.get_width() // 2, 395))
    pygame.draw.line(pantalla, GRIS, (60, 425), (ANCHO - 60, 425), 1)

    if seed_actual > 0:
        gen_seed = genero_de_seed(int(seed_actual))
        niv_seed = num_dificultad(int(seed_actual))
        comp = cargar_progreso()
        ya = clave_run(gen_seed, niv_seed) in comp
        marca_ok = "  [COMPLETADO]" if ya else ""
        col_gs = COLOR_GENERO.get(gen_seed, BLANCO)
        run_txt = fuente_chica.render(f"{gen_seed} - {DIFICULTADES[niv_seed]['nombre']}{marca_ok}", True, col_gs)
        pantalla.blit(run_txt, (ANCHO // 2 - run_txt.get_width() // 2, 432))
        enter = fuente_chica.render("ENTER = RUN     M = MODS LIBRE     R = RESET", True, GRIS_MED)
        pantalla.blit(enter, (ANCHO // 2 - enter.get_width() // 2, 460))

    if seed_actual == 0:
        if (pygame.time.get_ticks() // 500) % 2 == 0:
            coin = fuente.render("INSERT COIN", True, BLANCO)
            pantalla.blit(coin, (ANCHO // 2 - coin.get_width() // 2, 460))

    # contador de progreso global
    total_runs = len(GENEROS) * len(DIFICULTADES)
    comp_n = len(cargar_progreso())
    prog_txt = fuente_chica.render(f"COMPLETADOS: {comp_n}/{total_runs}", True, GRIS_MED)
    pantalla.blit(prog_txt, (ANCHO // 2 - prog_txt.get_width() // 2, 488))

    lb_txt = fuente_chica.render("L = LEADERBOARD     C = CONFIG     T = TUTORIAL", True, GRIS)
    pantalla.blit(lb_txt, (ANCHO // 2 - lb_txt.get_width() // 2, 512))

config_opcion = 0  # 0=brillo, 1=volumen, 2=vol_menu, 3=resolucion, 4=audio
pausa_opcion = 0   # 0=continuar, 1=reiniciar, 2=salir
mods_opcion = 0    # opcion seleccionada en pantalla de modificadores

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
      - suaves (stage 2+): inverso, acelerando, rafagas
      - medios (stage 3+): niebla, veloz, + espejo con 30%
      - duros  (stage 4):  espejo con 35%, sudden death
    ESPEJO: nunca en stages 1-2, 30% en stage 3, 35% en stage 4."""
    suaves = ["inverso", "acelerando", "rafagas"]
    medios = ["niebla", "veloz"]
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
    if rng.random() < 0.15 and NUM_STAGES > 1:
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
        "perks": [],           # perks acumulados (roguelike)
    }

perk_ofertas = []      # 3 perks ofrecidos en la pantalla de seleccion
perk_seleccion = 0     # indice seleccionado (0..2)

def dibujar_perk_select():
    """Pantalla de seleccion de perk entre stages."""
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
    gap = 30
    total_w = card_w * len(perk_ofertas) + gap * (len(perk_ofertas) - 1)
    x0 = ANCHO // 2 - total_w // 2
    for i, perk in enumerate(perk_ofertas):
        x = x0 + i * (card_w + gap)
        y = 180
        seleccionado = (i == perk_seleccion)
        # borde
        borde_color = col_g if seleccionado else GRIS
        grosor = 3 if seleccionado else 1
        pygame.draw.rect(pantalla, borde_color, (x, y, card_w, 260), grosor)
        if seleccionado:
            pygame.draw.rect(pantalla, (30, 30, 30), (x + 3, y + 3, card_w - 6, 254))
        # numero
        num = fuente_grande.render(str(i + 1), True, col_g if seleccionado else GRIS)
        pantalla.blit(num, (x + card_w // 2 - num.get_width() // 2, y + 10))
        # nombre
        nombre = fuente.render(perk["nombre"], True, BLANCO if seleccionado else GRIS_MED)
        pantalla.blit(nombre, (x + card_w // 2 - nombre.get_width() // 2, y + 70))
        # categoria
        cat = fuente_chica.render(cat_label.get(perk["cat"], ""), True, GRIS)
        pantalla.blit(cat, (x + card_w // 2 - cat.get_width() // 2, y + 100))
        # descripcion (word wrap manual simple)
        desc = perk["desc"]
        dy = 135
        palabras = desc.split()
        linea = ""
        for pal in palabras:
            test = (linea + " " + pal).strip()
            if fuente_chica.size(test)[0] > card_w - 20:
                txt = fuente_chica.render(linea, True, GRIS_MED)
                pantalla.blit(txt, (x + card_w // 2 - txt.get_width() // 2, y + dy))
                dy += 18
                linea = pal
            else:
                linea = test
        if linea:
            txt = fuente_chica.render(linea, True, GRIS_MED)
            pantalla.blit(txt, (x + card_w // 2 - txt.get_width() // 2, y + dy))
    # perks acumulados
    if run_actual and run_actual["perks"]:
        acum_y = 470
        acum_txt = fuente_chica.render("PERKS ACTIVOS:", True, GRIS)
        pantalla.blit(acum_txt, (ANCHO // 2 - acum_txt.get_width() // 2, acum_y))
        nombres = "  ".join(p["nombre"] for p in run_actual["perks"])
        activos = fuente_chica.render(nombres, True, col_g)
        pantalla.blit(activos, (ANCHO // 2 - activos.get_width() // 2, acum_y + 20))
    # instrucciones
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
    """Pantalla entre stages que muestra el progreso del run."""
    pantalla.fill(NEGRO)
    col_g = COLOR_GENERO.get(run_actual["genero"], BLANCO)
    titulo = fuente_grande.render(run_actual["genero"], True, col_g)
    pantalla.blit(titulo, (ANCHO // 2 - titulo.get_width() // 2, 50))
    dif_nom = DIFICULTADES[run_actual["nivel"]]["nombre"]
    sub = fuente.render(f"{dif_nom}", True, GRIS_MED)
    pantalla.blit(sub, (ANCHO // 2 - sub.get_width() // 2, 110))
    pygame.draw.line(pantalla, BLANCO, (60, 155), (ANCHO - 60, 155), 2)

    nombres_stage = ["NORMAL", "1 MOD", "1 MOD", "SUDDEN DEATH"]
    y0 = 190
    for i in range(NUM_STAGES):
        y = y0 + i * 70
        st = i + 1
        completado = st < run_actual["stage"]
        actual = st == run_actual["stage"]
        if completado:
            estado = "[OK]"
            color = col_g
        elif actual:
            estado = ">>>"
            color = BLANCO
        else:
            estado = "   "
            color = GRIS
        linea = fuente.render(f"{estado}  STAGE {st}: {nombres_stage[i]}", True, color)
        pantalla.blit(linea, (120, y))
        # mostrar mods solo de stages completados o el actual (ocultar futuros)
        mods_st = run_actual["mods"][i]
        if mods_st and (completado or actual):
            nombres = [m["nombre"] for m in MODIFICADORES if m["id"] in mods_st]
            mod_txt = fuente_chica.render("+ " + ", ".join(nombres), True, color)
            pantalla.blit(mod_txt, (160, y + 28))
        elif mods_st and not completado and not actual:
            mod_txt = fuente_chica.render("+ ???", True, GRIS)
            pantalla.blit(mod_txt, (160, y + 28))

    # perks acumulados
    perks_run = run_actual.get("perks", [])
    if perks_run:
        col_g = COLOR_GENERO.get(run_actual["genero"], BLANCO)
        pk_y = ALTO - 80
        pk_label = fuente_chica.render("PERKS:", True, GRIS)
        pantalla.blit(pk_label, (60, pk_y))
        pk_nombres = "  ".join(p["nombre"] for p in perks_run)
        pk_txt = fuente_chica.render(pk_nombres, True, col_g)
        pantalla.blit(pk_txt, (60 + pk_label.get_width() + 10, pk_y))

    cont = fuente_chica.render("ESPACIO = JUGAR STAGE     ESC = ABANDONAR RUN", True, GRIS_MED)
    pantalla.blit(cont, (ANCHO // 2 - cont.get_width() // 2, ALTO - 50))

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
            color_m = col_g if "SUDDEN" not in nom else (255, 80, 80)
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
    sub = fuente.render(f"{run_actual['genero']}  {dif_nom}", True, BLANCO)
    pantalla.blit(sub, (ANCHO // 2 - sub.get_width() // 2, 230))
    pts = fuente.render(f"PUNTOS TOTALES: {run_actual['puntos_total']}", True, GRIS_MED)
    pantalla.blit(pts, (ANCHO // 2 - pts.get_width() // 2, 290))

    # stages completados
    y_st = 340
    for i in range(NUM_STAGES):
        st_col = col_g if t_total > 0.5 + i * 0.4 else GRIS
        st = fuente_chica.render(f"STAGE {i+1}  [OK]", True, st_col)
        pantalla.blit(st, (ANCHO // 2 - st.get_width() // 2, y_st + i * 22))

    cont = fuente_chica.render("ESPACIO = CONTINUAR", True, GRIS)
    pantalla.blit(cont, (ANCHO // 2 - cont.get_width() // 2, ALTO - 50))

def dibujar_run_fallido():
    """Pantalla cuando perdes un stage."""
    pantalla.fill(NEGRO)
    titulo = fuente_grande.render("RUN FALLIDO", True, BLANCO)
    pantalla.blit(titulo, (ANCHO // 2 - titulo.get_width() // 2, 160))
    sub = fuente.render(f"CAISTE EN STAGE {run_actual['stage']}/{NUM_STAGES}", True, GRIS_MED)
    pantalla.blit(sub, (ANCHO // 2 - sub.get_width() // 2, 250))
    cont = fuente_chica.render("ENTER = VOLVER AL MENU", True, GRIS)
    pantalla.blit(cont, (ANCHO // 2 - cont.get_width() // 2, ALTO - 50))

def dibujar_mods():
    pantalla.fill(NEGRO)
    titulo = fuente_grande.render("MODIFICADORES", True, BLANCO)
    pantalla.blit(titulo, (ANCHO // 2 - titulo.get_width() // 2, 40))
    pygame.draw.line(pantalla, BLANCO, (60, 100), (ANCHO - 60, 100), 2)

    sub = fuente_chica.render("SUBEN EL MULTIPLICADOR DE PUNTOS", True, GRIS_MED)
    pantalla.blit(sub, (ANCHO // 2 - sub.get_width() // 2, 115))

    y0 = 145
    fila_h = 42
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
    ]
    y0 = 160
    for i, (nombre, valor, tipo) in enumerate(opciones):
        y = y0 + i * 60
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
            # truncar nombre largo
            if len(dev_name) > 24:
                dev_name = dev_name[:22] + ".."
            dev_txt = fuente_chica.render(dev_name, True, color)
            pantalla.blit(dev_txt, (ANCHO - 300, y + 6))

    ayuda1 = fuente_chica.render("FLECHAS ARRIBA/ABAJO = ELEGIR", True, GRIS)
    pantalla.blit(ayuda1, (ANCHO // 2 - ayuda1.get_width() // 2, 490))
    ayuda2 = fuente_chica.render("FLECHAS IZQ/DER = AJUSTAR", True, GRIS)
    pantalla.blit(ayuda2, (ANCHO // 2 - ayuda2.get_width() // 2, 515))
    ayuda3 = fuente_chica.render("ESC PARA VOLVER", True, GRIS)
    pantalla.blit(ayuda3, (ANCHO // 2 - ayuda3.get_width() // 2, 540))

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

# ═══════════════════════════════════════════════════════ >>MAIN_LOOP<< ═══

ESTADO         = "menu"
partida        = None
seed_acumulada = 0.0
cargando_seed  = False
teclas_sostenidas = set()
nombre_input   = ""
score_guardado = False
run_actual     = None
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
                if evento.key == pygame.K_SPACE:
                    cargando_seed = True
                if evento.key == pygame.K_RETURN and seed_acumulada > 0:
                    # arrancar un RUN de stages
                    sfx_confirm()
                    run_actual = crear_run(int(seed_acumulada))
                    ESTADO = "run_overview"
                if evento.key == pygame.K_m and seed_acumulada > 0:
                    # modo libre de mods (sin stages)
                    sfx_confirm()
                    mods_opcion = 0
                    ESTADO = "mods"
                if evento.key == pygame.K_r:
                    seed_acumulada = 0.0
                    cargando_seed  = False
                if evento.key == pygame.K_l:
                    sfx_confirm()
                    ESTADO = "leaderboard"
                if evento.key == pygame.K_c:
                    sfx_confirm()
                    config_opcion = 0
                    ESTADO = "config"
                if evento.key == pygame.K_t:
                    sfx_confirm()
                    tutorial_pagina = 0
                    ESTADO = "tutorial"
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
                    else:
                        ESTADO = "leaderboard"
                    run_actual = None
                    nueva_musica_menu_aleatoria()

        elif ESTADO == "run_fallido":
            if evento.type == pygame.KEYDOWN:
                if evento.key in (pygame.K_RETURN, pygame.K_ESCAPE, pygame.K_SPACE):
                    # partida["puntos"] ya incluye lo acumulado de stages previos
                    pts_run = partida.get("puntos", 0)
                    if not score_guardado and pts_run > 0 and es_highscore(pts_run):
                        partida["puntos"] = pts_run
                        nombre_input = ""
                        ESTADO = "input_nombre"
                    else:
                        ESTADO = "leaderboard"
                    run_actual = None
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
                    config_opcion = (config_opcion - 1) % 5
                    sfx_select()
                elif evento.key == pygame.K_DOWN:
                    config_opcion = (config_opcion + 1) % 5
                    sfx_select()
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
            if evento.type == pygame.KEYDOWN:
                if evento.key in (pygame.K_ESCAPE, pygame.K_SPACE, pygame.K_RETURN):
                    if partida.get("game_over") or (partida["terminada"] and not partida["notas_cayendo"]):
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
                                ESTADO = "run_fallido"
                                nueva_musica_menu_aleatoria()
                            else:
                                # paso el stage: el total del run es el puntaje final
                                # de esta partida (que ya arranco desde el acumulado)
                                run_actual["puntos_total"] = partida["puntos"]
                                if run_actual["stage"] >= NUM_STAGES:
                                    # run completo!
                                    marcar_completado(run_actual["genero"], run_actual["nivel"])
                                    col_g = COLOR_GENERO.get(run_actual["genero"], BLANCO)
                                    _spawn_notas_celebracion(col_g)
                                    ESTADO = "run_completado"
                                    nueva_musica_menu_aleatoria()
                                else:
                                    # ofrecer perk antes de avanzar al siguiente stage
                                    _perk_rng = random.Random(run_actual["seeds"][run_actual["stage"] - 1] + 777)
                                    perk_ofertas[:] = generar_ofertas_perks(_perk_rng, run_actual["perks"])
                                    perk_seleccion = 0
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
                    elif evento.key == pygame.K_ESCAPE:
                        # PAUSAR
                        pygame.mixer.stop()
                        teclas_sostenidas.clear()
                        for c in list(canal_hold.keys()):
                            canal_hold[c].stop()
                        canal_hold.clear()
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

                        # buscar la nota objetivo más cercana en esta columna
                        ahora_rel = int(partida.get("t_musical", ahora_ms - partida["inicio"]))
                        midi_a_tocar = midi_fijo
                        mejor_dist = 99999
                        mejor_es_pu = False   # si la mejor nota es un power-up, no sonar melodica
                        for g in partida["notas_cayendo"]:
                            if col in g["cols"]:
                                d = abs(g["tiempo_ms"] - ahora_rel)
                                if d < mejor_dist:
                                    mejor_dist = d
                                    mejor_es_pu = bool(g.get("power_up"))
                                    idx_col = g["cols"].index(col)
                                    if idx_col < len(g.get("midis", [])):
                                        midi_a_tocar = g["midis"][idx_col]

                        # volumen segun cercania: generoso, pifiar por poco suena pleno
                        if mejor_dist < 120:
                            vol_nota = 1.0
                        elif mejor_dist < 250:
                            vol_nota = 0.9
                        else:
                            vol_nota = 0.7

                        # solo tocar la nota melodica si la mejor no es un power-up
                        # (los power-ups tienen su propio SFX que se dispara al acertar)
                        snd_tocar = None
                        if not (mejor_es_pu and mejor_dist < partida.get("w_hit", 150)):
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
                                        # --- POWER-UP: nota especial ---
                                        pu_id = grupo.get("power_up")
                                        if pu_id and distancia < w_hit:
                                            pu_def = next((p for p in POWER_UPS if p["id"] == pu_id), None)
                                            if pu_def:
                                                if pu_id == "vida":
                                                    partida["vida"] = min(partida["vida_max"], partida["vida"] + 4)
                                                    crear_texto_flotante(cx, zy_p - 30, "+4 VIDA", pu_def["color"], True)
                                                elif pu_def["dur"] > 0:
                                                    partida["efectos_activos"][pu_id] = ahora_juego + pu_def["dur"]
                                                    crear_texto_flotante(cx, zy_p - 30, pu_def["nombre"], pu_def["color"], True)
                                                crear_explosion(cx, zy_p, 80, color=pu_def["color"])
                                                crear_shake(6)
                                                sfx_power_up(pu_id)
                                                partida["combo"] += 1
                                                if partida["combo"] > partida["max_combo"]:
                                                    partida["max_combo"] = partida["combo"]
                                                if grupo in partida["notas_cayendo"]:
                                                    partida["notas_cayendo"].remove(grupo)
                                                break
                                        if auto_perf or distancia < w_perf:
                                            pts = 10 if partida.get("perk_perfecto") else 5
                                            partida["combo"] += 1
                                            pot = min(1.0 + partida["combo"] * 0.03, 1.8)
                                            partida["ultimo_hit"] = {"texto": "PERFECTO", "tiempo": ahora_ms}
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
                                            crear_explosion(cx, zy_p, 20, color=col_g, combo=partida["combo"])
                                            crear_onda(cx, zy_p, 0.4)
                                            crear_flash(col, 0.3)
                                            crear_indicador_hit(col, "cerca")
                                            sfx_hit_good()
                                        else:
                                            pts = 0
                                            partida["combo"] = 0
                                            partida["ultimo_hit"] = {"texto": "MAL", "tiempo": ahora_ms}
                                            crear_explosion(cx, zy_p, 8, GRIS_MED)
                                            crear_shake(8)
                                            crear_indicador_hit(col, "error")
                                        if partida["combo"] > partida["max_combo"]:
                                            partida["max_combo"] = partida["combo"]
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
                                        combo_mult = 1 + partida["combo"] // 5
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
                                                partida["puntos"] = max(0, partida["puntos"] - 2)
                                                crear_texto_flotante(cx, zy_p - 20, "-2", GRIS_MED)
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
                        # bonus por completar hold
                        partida["puntos"] += 5
                        num_cols = partida["dificultad"]["columnas"]
                        ancho_col = ANCHO // num_cols
                        cx = col * ancho_col + ancho_col // 2
                        crear_texto_flotante(cx, zy_p - 40, "+5", BLANCO)
                        if grupo in partida["notas_cayendo"]:
                            partida["notas_cayendo"].remove(grupo)
                        del partida["holds_activos"][col]

    if ESTADO == "menu":
        if cargando_seed:
            seed_acumulada = min(seed_acumulada + SEED_VELOCIDAD, SEED_MAX)
        tick_musica_menu()
        dibujar_menu(seed_acumulada, cargando_seed)

    elif ESTADO == "leaderboard":
        tick_musica_menu()
        dibujar_leaderboard()

    elif ESTADO == "tutorial":
        tick_musica_menu()
        dibujar_tutorial(tutorial_pagina)

    elif ESTADO == "config":
        tick_musica_menu()
        dibujar_config()

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

    elif ESTADO == "input_nombre":
        tick_musica_menu()
        dibujar_input_nombre(nombre_input)

    elif ESTADO == "pausado":
        ahora = partida["pausa_inicio"] - partida["inicio"]
        dibujar_juego(partida, ahora)
        dibujar_pausa(partida)

    elif ESTADO == "jugando":
        zy_p = partida.get("zona_y", ZONA_Y)
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
                                    partida["efectos_activos"][pu_id_a] = ahora + pu_def_a["dur"]
                                    crear_texto_flotante(cxa, zy_p - 30, pu_def_a["nombre"], pu_def_a["color"], True)
                                crear_explosion(cxa, zy_p, 80, color=pu_def_a["color"])
                                sfx_power_up(pu_id_a)
                            continue  # power-up consumido, no vuelve a la lista
                        # acreditar como PERFECTO
                        partida["combo"] += 1
                        if partida["combo"] > partida["max_combo"]:
                            partida["max_combo"] = partida["combo"]
                        pts_a = 10 if partida.get("perk_perfecto") else 5
                        combo_mult_a = 1 + partida["combo"] // 5
                        _pu_doble_a = 2.0 if ahora < partida.get("efectos_activos", {}).get("doble", 0) else 1.0
                        bonus_hold = 3 if grupo.get("hold", 0) > 0 else 0
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
                    es_hold_activo = any(c in partida["holds_activos"] for c in n["cols"])
                    if not es_hold_activo:
                        partida["ultimo_hit"] = {"texto": "MISS", "tiempo": ahora_ms}
                        # combo_save: el primer miss no rompe combo (cooldown 15s)
                        if partida.get("perk_combo_save") and partida.get("combo_save_cd", 0) <= 0 and partida["combo"] > 0:
                            partida["combo_save_cd"] = 15000
                            crear_texto_flotante(ANCHO // 2, zy_p - 60, "COMBO SAVE!", (100, 200, 255), True)
                        else:
                            partida["combo"] = 0
                        partida["puntos"] = max(0, partida["puntos"] - 5)
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
                        crear_texto_flotante(miss_x, miss_y, "-5", GRIS_MED)
                        crear_shake(4)
                        SND_ERROR.set_volume(0.3 * config["volumen"])
                        SND_ERROR.play()
                        if not dev_mode and partida["vida"] <= 0:
                            partida["game_over"] = True
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
