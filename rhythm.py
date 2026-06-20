import pygame
import random
import numpy as np
import json
import wave
import os
import sys
import threading

# directorio base: donde esta el .exe (compilado) o el .py (desarrollo)
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

pygame.init()

# --- dispositivos de audio ---
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

pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
pygame.mixer.set_num_channels(32)

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

# la ventana real puede cambiar de tamaño; el juego siempre dibuja en 720x640 y se escala
_w, _h = RESOLUCIONES[config["res_idx"]]
ventana = pygame.display.set_mode((_w, _h))
pygame.display.set_caption("Rhythm Game")
pantalla = pygame.Surface((ANCHO, ALTO))
clock = pygame.time.Clock()

def aplicar_volumen():
    pygame.mixer.set_num_channels(32)

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

# progresiones armónicas reales (indices de grado en la escala)
PROGRESIONES = [
    [0, 3, 4, 0],    # I - IV - V - I
    [0, 3, 4, 3],    # I - IV - V - IV
    [0, 5, 3, 4],    # I - vi - IV - V
    [0, 4, 5, 3],    # I - V - vi - IV
    [0, 3, 0, 4],    # I - IV - I - V
    [0, 2, 3, 4],    # I - iii - IV - V
    [0, 5, 3, 0],    # I - vi - IV - I
    [0, 3, 5, 4],    # I - IV - vi - V
    [0, 0, 3, 4],    # I - I - IV - V
    [0, 4, 3, 3],    # I - V - IV - IV
]

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
    {"id": "sudden",     "nombre": "SUDDEN DEATH","desc": "1 error = game over",     "mult": 2.0},
]
mods_activos = set()   # ids de modificadores seleccionados (modo libre)

# mods "faciles" que pueden salir en el dado de los stages 2 y 3
MODS_FACILES = ["espejo", "inverso", "veloz", "acelerando"]

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
    # soft clipping con tanh: comprime picos suavemente en vez de cortarlos
    # esto previene distorsion cuando varios sonidos se superponen en el mixer
    scaled = np.tanh(scaled * 1.5) * 0.75
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
    "BITCRUSH":  "bitcrush",
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
    "RING MOD":   "ring_mod",
    "SYNC LEAD":  "sync_lead",
    "PLUCK SOFT": "pluck_soft",
    "VOX PAD":    "vox_pad",
    "DIST GTR":   "dist_gtr",
    "WAVEFOLD":   "wavefold",
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
    "ALIEN":      "alien",
    "BROKEN":     "broken",
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
HOLD_MAX = 4000  # maximo absoluto (= duracion del sample largo)

# --- identidad visual: cada instrumento tiene una "forma" para su icono y notas ---
# formas: square, saw, sine, triangle, bell, pluck, pad, metal, noise, glass,
#         brass, choir, atmos, alien
INST_FORMA = {
    "SQUARE": "square", "CHIPTUNE": "square", "BITCRUSH": "square", "PWM LEAD": "square",
    "SAW": "saw", "SUPERSAW": "saw", "SAW STACK": "saw", "HOOVER": "saw",
    "ACID": "saw", "SYNC LEAD": "saw", "DETUNE": "saw", "ANALOG STR": "saw",
    "SINE": "sine", "FM EP": "sine", "SUB PLUCK": "sine", "SYNTHBASS": "sine", "BASS": "sine",
    "TRIANGLE": "triangle", "LEAD": "triangle", "FLUTE": "triangle",
    "FM BELL": "bell", "BELL FM": "bell", "BELLPAD": "bell", "VIBRAPHONE": "bell", "KALIMBA": "bell",
    "PLUCK": "pluck", "PLUCK SOFT": "pluck", "HARP": "pluck", "SITAR": "pluck",
    "PAD": "pad", "PHASE PAD": "pad", "VOX PAD": "pad", "DREAM PAD": "pad", "FROZEN STR": "pad",
    "METALLIC": "metal", "RING MOD": "metal", "RESO": "metal", "WAVEFOLD": "metal", "NOISE PITCH": "metal",
    "GLASS": "glass", "GLASS HARM": "glass",
    "ORGAN": "organ", "ORGAN FULL": "organ",
    "TRUMPET": "brass", "FM BRASS": "brass", "GROWL": "brass", "DIST GTR": "brass",
    "CHOIR": "choir", "SPACE CHOIR": "choir", "FORMANT": "choir",
    "WOBBLE": "wobble", "FM 3OP": "wobble",
    "SHIMMER": "atmos", "ATMOS NOISE": "atmos",
    "ALIEN": "alien", "BROKEN": "alien",
}

def dibujar_icono_inst(surf, forma, cx, cy, r, color):
    """Dibuja el icono de un instrumento centrado en (cx, cy) con radio r."""
    import math as _m
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
        pts = [(cx - r + i, cy - int(_m.sin(i / r * _m.pi * 2) * r)) for i in range(0, 2 * r, 2)]
        if len(pts) > 1:
            pygame.draw.lines(surf, color, False, pts, 2)
    elif forma == "triangle":
        pygame.draw.polygon(surf, color, [(cx, cy - r), (cx - r, cy + r), (cx + r, cy + r)], 2)
    elif forma == "bell":
        pygame.draw.arc(surf, color, (cx - r, cy - r, 2 * r, 2 * r), _m.pi, 2 * _m.pi, 2)
        pygame.draw.line(surf, color, (cx - r, cy), (cx + r, cy), 2)
        pygame.draw.circle(surf, color, (cx, cy + r), 2)
    elif forma == "pluck":
        pygame.draw.line(surf, color, (cx, cy - r), (cx, cy + r), 2)
        pygame.draw.circle(surf, color, (cx, cy - r), 3)
        pygame.draw.arc(surf, color, (cx, cy - r//2, r, r), -_m.pi/2, _m.pi/2, 2)
    elif forma == "pad":
        pygame.draw.ellipse(surf, color, (cx - r, cy - r//2, 2 * r, r), 2)
        pygame.draw.ellipse(surf, color, (cx - r//2, cy - r, r, 2 * r), 1)
    elif forma == "metal":
        for a in range(0, 360, 60):
            x = cx + int(_m.cos(_m.radians(a)) * r)
            y = cy + int(_m.sin(_m.radians(a)) * r)
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
            pygame.draw.arc(surf, color, (cx + dx - r//2, cy - r, r, 2 * r), _m.pi/2, 3*_m.pi/2, 2)
    elif forma == "wobble":
        pts = [(cx - r + i, cy - int(_m.sin(i / r * _m.pi * 3) * r * (0.4 + 0.6 * i / (2*r)))) for i in range(0, 2 * r, 2)]
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
        lfo_speed = rng_params.get("lfo_speed", 6)
        lfo_depth = rng_params.get("lfo_depth", 0.8)
        lfo = (1 + lfo_depth * np.sin(2 * np.pi * lfo_speed * t)) * 0.5
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
        sweep = 1 + 0.06 * np.exp(-t * 8)
        wave = np.zeros(n)
        for d in [-0.4, -0.1, 0, 0.1, 0.4]:
            f = freq * sweep * (1 + d * 0.012)
            wave += (2.0 * (t * f % 1) - 1.0) * 0.2
    elif tipo == "bell_fm":
        ratio = rng_params.get("bell_ratio", 1.414)
        idx = rng_params.get("bell_index", 5.0)
        mod_env = np.exp(-t * 3)
        wave = np.sin(phase + idx * mod_env * np.sin(2 * np.pi * freq * ratio * t))
    elif tipo == "growl":
        lfo = 0.5 + 0.5 * np.sin(2 * np.pi * rng_params.get("growl_rate", 7) * t)
        idx = rng_params.get("growl_index", 4) * lfo
        wave = np.sin(phase + idx * np.sin(2 * np.pi * freq * 1.0 * t))
        wave = np.tanh(wave * 1.5)
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
        np_rng = np.random.RandomState(int(freq) % 999999)
        raw = np_rng.uniform(-1, 1, n)
        res = 0.96
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
        # trémolo con LFO lento y sinusoide tonal mezclada
        lfo_mod = 0.6 + 0.4 * np.sin(2 * np.pi * rng_params.get("lfo_spd", 0.3) * t)
        tonal = np.sin(phase) * 0.3
        wave = wave * lfo_mod * 0.7 + tonal
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

import math

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

def renderizar_instrumento(nombre, tipo, dibujar_progreso=False, display=None):
    """Renderiza un instrumento completo (60 notas x 2 duraciones)"""
    texto_carga = display if display else nombre
    inst_rng = random.Random(hash(nombre))
    params = generar_params_instrumento(inst_rng, tipo)
    inst_eq = inst_rng.choice(EQ_TIPOS)
    inst_eq_int = inst_rng.uniform(0.1, 0.35)
    c_cortas = {}
    c_largas = {}
    idx = 0
    for midi in range(38, 91):
        idx += 1
        if dibujar_progreso and midi % 4 == 0:
            dibujar_carga_seed_inst(idx / 53, texto_carga)
        freq = midi_a_freq(midi)
        snd = synth_nota(tipo, freq, 0.3, params)
        arr = pygame.sndarray.array(snd).astype(np.float64) / 32767
        c_cortas[midi] = np_to_sound(aplicar_eq(arr[:, 0], inst_eq, inst_eq_int), lpf=True)
        params_hold = dict(params)
        params_hold["vibrato"] = params.get("vibrato", 0) + 0.4
        params_hold["vib_speed"] = params.get("vib_speed", 5) * 0.8
        params_hold["sustain"] = max(params.get("sustain", 0.6), 0.5)
        params_hold["decay"] = min(params.get("decay", 5.0), 1.5)
        snd_l = synth_nota(tipo, freq, 4.0, params_hold)
        arr_l = pygame.sndarray.array(snd_l).astype(np.float64) / 32767
        mono_l = aplicar_eq(arr_l[:, 0], inst_eq, inst_eq_int)
        # crossfade para loop suave: mezclar final con inicio
        cf = min(4000, len(mono_l) // 4)
        fade_out = np.linspace(1, 0, cf)
        fade_in  = np.linspace(0, 1, cf)
        mono_l[-cf:] = mono_l[-cf:] * fade_out + mono_l[:cf] * fade_in
        c_largas[midi] = np_to_sound(mono_l, lpf=True)
    cache_por_instrumento[nombre] = c_cortas
    cache_largas_por_instrumento[nombre] = c_largas
    print(f"  {nombre} OK (EQ: {inst_eq} {inst_eq_int:.1f})")

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

# rango de seeds para la musica del menu: de DIFICIL en adelante
SEED_MENU_MIN = 4901   # primer tramo de DIFICIL en get_dificultad

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
    except Exception as e:
        print(f"Error pre-render background: {e}")
    finally:
        _menu_preparando = False

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

def crear_explosion(x, y, cantidad, color=BLANCO, potencia=1.0):
    for _ in range(cantidad):
        angulo = random.uniform(0, 6.28)
        fuerza = random.uniform(2, 14) * potencia
        dx = math.cos(angulo) * fuerza
        dy = math.sin(angulo) * fuerza - 5 * potencia
        vida = random.randint(25, 65) + int((potencia - 1) * 15)
        tam = int(random.randint(3, 12) * (0.8 + potencia * 0.4))
        forma = random.choice(["rect", "rect", "linea"])
        particulas.append({"x": x, "y": y, "dx": dx, "dy": dy, "vida": vida,
                           "vida_max": vida, "tam": tam, "color": color, "forma": forma,
                           "spin": random.uniform(-0.3, 0.3)})

def crear_onda(x, y, intensidad=1.0, r0=4):
    ondas.append({"x": x, "y": y, "r": r0, "vida": 20, "vida_max": 20, "intensidad": intensidad})

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
        alpha = int(200 * pct * o["intensidad"])
        col = (alpha, alpha, alpha)
        grosor = max(1, int(3 * pct))
        pygame.draw.circle(pantalla, col, (int(o["x"]) + shake_dx, int(o["y"]) + shake_dy), int(o["r"]), grosor)
    for p in particulas:
        pct = p["vida"] / p["vida_max"]
        alpha = int(255 * pct)
        color = (min(p["color"][0], alpha), min(p["color"][1], alpha), min(p["color"][2], alpha))
        tam = max(1, int(p["tam"] * pct))
        px = int(p["x"]) + shake_dx
        py = int(p["y"]) + shake_dy
        if p["forma"] == "linea":
            ex = int(px - p["dx"] * 1.5)
            ey = int(py - p["dy"] * 1.5)
            pygame.draw.line(pantalla, color, (px, py), (ex, ey), max(1, tam // 2))
        else:
            pygame.draw.rect(pantalla, color, (px, py, tam, tam))
    for t in textos_flotantes:
        pct = t["vida"] / t["vida_max"]
        alpha = int(255 * pct)
        color = (min(t["color"][0], alpha), min(t["color"][1], alpha), min(t["color"][2], alpha))
        f = fuente if t["grande"] else fuente_chica
        txt = f.render(t["texto"], True, color)
        pantalla.blit(txt, (int(t["x"]) - txt.get_width() // 2 + shake_dx, int(t["y"]) + shake_dy))
def nota_midi(tonica, escala, grado):
    octava = grado // len(escala)
    return tonica + escala[grado % len(escala)] + octava * 12

NOMBRES_NOTAS = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
def midi_a_nombre(midi):
    return NOMBRES_NOTAS[midi % 12] + str(midi // 12 - 1)

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
        return DIFICULTADES[1]
    # mas tramos (y mas anchos) en la zona facil/normal/intermedia
    tramos = [400, 900, 1500, 2200, 3000, 3900, 4900, 5700, 6400,
              7100, 7800, 8400, 9000, 9500, 9999]
    for i, tope in enumerate(tramos):
        if seed <= tope:
            return DIFICULTADES[i + 1]
    return DIFICULTADES[15]

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
                         "VIBRAPHONE", "PLUCK SOFT", "RING MOD", "DIST GTR",
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

def mezclar_color(c, blanco_pct):
    """Mezcla un color con blanco. blanco_pct=0 -> color puro, 1 -> blanco"""
    return (
        int(c[0] + (255 - c[0]) * blanco_pct),
        int(c[1] + (255 - c[1]) * blanco_pct),
        int(c[2] + (255 - c[2]) * blanco_pct),
    )

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

def generar_cancion(seed, dif):
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

    # notas por columna: saltar de a 2 grados para cubrir acordes y rango amplio
    # 3 cols → root, 3ra, 5ta (triada) | 4 cols → +7ma | 5+ cols → octava+
    notas_columnas = [nota_midi(tonica + 12, escala, i * 2) for i in range(num_columnas)]
    kit = elegir_kit(rng)
    # instrumento: 6% raro, si no del pool del genero (con fallback a la lista global)
    if rng.random() < 0.02:
        instrumento = rng.choice(list(INSTRUMENTOS_RAROS.keys()))
    else:
        pool = [i for i in gdef.get("instrumentos", []) if i in INSTRUMENTOS_JUGADOR]
        if not pool:
            pool = list(INSTRUMENTOS_JUGADOR.keys())
        instrumento = rng.choice(pool)
        # RESO suena agresivo, re-roll 75% de las veces
        if instrumento == "RESO" and len(pool) > 1 and rng.random() < 0.75:
            instrumento = rng.choice([p for p in pool if p != "RESO"])

    # --- CAPA 1: estructura variable por seed ---
    C_INTRO     = rng.choice([2, 4, 4, 6])
    num_reps    = rng.choice([4, 5, 6, 6, 7, 8])   # repeticiones de 4 compases en el nudo
    C_NUDO      = num_reps * 4
    C_DESENLACE = rng.choice([2, 4, 4, 6])
    t_intro_fin     = C_INTRO * 4 * beat
    t_nudo_fin      = t_intro_fin + C_NUDO * 4 * beat
    t_desenlace_fin = t_nudo_fin + C_DESENLACE * 4 * beat

    prob_acorde = {3: 0.2, 4: 0.3, 5: 0.4, 6: 0.5, 7: 0.6}.get(num_columnas, 0.2)

    # frases melódicas con contornos musicales
    # 0=bajo(tónica), 1=medio(tercera/cuarta), 2=alto(quinta+)
    frases_subir = [
        [0, 0, 1, 2],    # reposo -> ascenso gradual
        [0, 1, 1, 2],    # paso a paso
        [0, 1, 2, 1],    # arco: sube y baja
        [0, 0, 0, 2],    # pedal con salto
        [0, 1, 0, 2],    # zigzag ascendente
        [1, 0, 1, 2],    # bordadura + ascenso
        [0, 1, 2, 2],    # ascenso con reposo arriba
    ]
    frases_bajar = [
        [2, 2, 1, 0],    # descenso gradual
        [2, 1, 1, 0],    # paso a paso
        [2, 1, 0, 1],    # arco invertido
        [2, 2, 2, 0],    # pedal con caída
        [2, 1, 2, 0],    # zigzag descendente
        [1, 2, 1, 0],    # bordadura + descenso
        [2, 1, 0, 0],    # descenso con reposo abajo
    ]
    frases_medio = [
        [1, 0, 1, 2],    # desde medio explora
        [1, 2, 1, 0],    # arco desde medio
        [1, 1, 0, 1],    # bordadura inferior
        [1, 1, 2, 1],    # bordadura superior
        [0, 2, 1, 1],    # salto + resolución
        [2, 0, 1, 1],    # salto inverso + resolución
        [1, 0, 2, 0],    # péndulo
    ]

    def escalar_frase(frase):
        """Mapea niveles 0,1,2 a columnas usando grados de la escala"""
        if num_columnas <= 3:
            return [min(g, num_columnas - 1) for g in frase]
        # mapear a posiciones musicales: tónica, mediante, dominante
        tonica = 0
        mediante = num_columnas // 3
        dominante = num_columnas * 2 // 3
        # agregar variación por la seed
        tonica = max(0, tonica + rng.randint(0, 1))
        mediante = min(num_columnas - 1, mediante + rng.randint(-1, 1))
        dominante = min(num_columnas - 1, max(mediante + 1, dominante + rng.randint(-1, 0)))
        mapa = {0: tonica, 1: mediante, 2: dominante}
        return [mapa[g] for g in frase]

    motivos_a = [escalar_frase(rng.choice(frases_subir)) for _ in range(4)]
    motivos_b = [escalar_frase(rng.choice(frases_bajar)) for _ in range(4)]

    pat_jugador_simples = [
        [1,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0],
        [1,0,0,0,0,0,0,0,0,0,0,0,1,0,0,0],
        [0,0,0,0,1,0,0,0,0,0,0,0,1,0,0,0],
        [1,0,0,0,1,0,0,0,0,0,0,0,0,0,0,0],
        [0,0,0,0,0,0,0,0,1,0,0,0,1,0,0,0],
        [1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
        [0,0,0,0,1,0,0,0,0,0,0,0,0,0,0,0],
    ]
    pat_jugador_complejos = [
        [1,0,0,0,1,0,0,0,1,0,0,0,0,0,0,0],
        [1,0,0,0,0,0,0,0,1,0,0,0,1,0,0,0],
        [1,0,0,0,1,0,0,0,0,0,0,0,1,0,0,0],
        [0,0,0,0,1,0,0,0,1,0,0,0,1,0,0,0],
        [1,0,0,0,1,0,0,0,1,0,0,0,1,0,0,0],
        [1,0,0,0,0,0,1,0,0,0,0,0,1,0,0,0],
        [1,0,0,0,1,0,0,0,0,0,1,0,0,0,0,0],
    ]

    notas_jugador = []

    nota_intro = motivos_a[0][0]
    for c in range(C_INTRO):
        if c % 2 == 0:
            notas_jugador.append({
                "cols": [nota_intro], "midis": [notas_columnas[nota_intro]],
                "tiempo": (c + 1) * 4 * beat,
                "es_acorde": False, "parte": "intro", "hold": beat * 3,
            })

    def crear_bloque(motivos_bloque, complejo=False):
        bloque = []
        pats = pat_jugador_complejos if complejo else pat_jugador_simples
        pat1 = pats[rng.randint(0, len(pats) - 1)]
        pat2 = pats[rng.randint(0, len(pats) - 1)]
        mot  = motivos_bloque[0]
        for c in range(4):
            pat      = pat1 if c % 2 == 0 else pat2
            nota_idx = 0
            compas   = []
            for s in range(16):
                if pat[s] == 0:
                    compas.append(None)
                    continue
                col = mot[nota_idx % len(mot)]
                nota_idx += 1
                compas.append({"col": col, "hold": 0})
            activas = [i for i, n in enumerate(compas) if n is not None]
            for idx, pos in enumerate(activas):
                if rng.random() < 0.45:
                    if idx + 1 < len(activas):
                        dur_beats = (activas[idx + 1] - pos) // 4
                        dur = dur_beats * beat
                    else:
                        dur_beats = (16 - pos) // 4
                        dur = dur_beats * beat
                    if dur >= beat:
                        compas[pos]["hold"] = dur
            bloque.append(compas)
        return bloque

    bloque_a = crear_bloque(motivos_a)
    bloque_b = crear_bloque(motivos_b, complejo=True)

    motivos_c = [escalar_frase(rng.choice(frases_medio))]
    bloque_c = crear_bloque(motivos_c, complejo=True)

    # bloques adicionales para mas variedad estructural
    bloques_disponibles = [bloque_a, bloque_b, bloque_c]
    # plan de bloques: que seccion usa cada repeticion (varia por seed)
    plan_bloques = []
    for rep in range(num_reps):
        if rep < num_reps // 3:
            plan_bloques.append(0)   # A
        elif rep < 2 * num_reps // 3:
            plan_bloques.append(1)   # B
        else:
            plan_bloques.append(2)   # C
    # a veces intercambia algun bloque para romper la simetria
    if num_reps >= 5 and rng.random() < 0.5:
        idx_swap = rng.randint(1, num_reps - 2)
        plan_bloques[idx_swap] = rng.randint(0, 2)

    # CAPA 2: preparar mutacion de timbre (se decide antes del loop)
    mut_activa = rng.random() < 0.6
    mut_octava = rng.choice([-12, 0, 12])
    mut_desde = rng.randint(num_reps // 2, max(num_reps // 2, num_reps - 1))

    for rep in range(num_reps):
        bloque = bloques_disponibles[plan_bloques[rep]]
        # CAPA 2: offset de octava si la mutacion esta activa en esta rep
        oct_off = mut_octava if (mut_activa and rep >= mut_desde) else 0
        # CAPA 4: intensidad de adornos crece con la repeticion
        prob_adorno = (0.1 + (rep / max(1, num_reps)) * 0.35) * densidad
        for c in range(4):
            compas_real = rep * 4 + c
            compas = bloque[c]
            for s in range(16):
                if compas[s] is None:
                    continue
                t   = t_intro_fin + compas_real * 4 * beat + s * paso16
                col = compas[s]["col"]
                hd  = compas[s]["hold"]
                segunda_mitad = rep >= num_reps // 2
                if (usar_acordes or segunda_mitad) and s == 0 and rng.random() < prob_acorde:
                    grado   = progresion[compas_real % len(progresion)]
                    cols_ac = []
                    for g in patron_acordes[grado % len(patron_acordes)][:3]:
                        col_ac = g % num_columnas
                        if col_ac not in cols_ac:
                            cols_ac.append(col_ac)
                    if len(cols_ac) >= 2:
                        notas_jugador.append({
                            "cols": cols_ac,
                            "midis": [notas_columnas[cx] + oct_off for cx in cols_ac],
                            "tiempo": t, "es_acorde": True, "parte": "nudo", "hold": 0,
                        })
                        continue
                # densidad < 1: saltear notas (nunca el down-beat del compas)
                if densidad < 1.0 and s != 0 and rng.random() > densidad:
                    continue
                notas_jugador.append({
                    "cols": [col], "midis": [notas_columnas[col] + oct_off],
                    "tiempo": t, "es_acorde": False, "parte": "nudo", "hold": hd,
                })
                # CAPA 4: adorno (nota de paso) entre esta nota y la siguiente
                if hd == 0 and s % 4 == 0 and rng.random() < prob_adorno:
                    col_adorno = (col + rng.choice([-1, 1, 2])) % num_columnas
                    t_adorno = t + paso16 * 2
                    notas_jugador.append({
                        "cols": [col_adorno], "midis": [notas_columnas[col_adorno] + oct_off],
                        "tiempo": t_adorno, "es_acorde": False, "parte": "nudo", "hold": 0,
                    })

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
    for c in range(C_NUDO):
        compas_t = t_intro_fin + c * 4 * beat
        grado = progresion[c % len(progresion)]
        # fundamental del acorde segun el grado en la escala
        midi_nota = midi_bajo_base + escala[grado % len(escala)]
        for s in range(16):
            if pat_bajo[s] == 0:
                continue
            t = compas_t + s * paso16
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

def iniciar_partida(seed, mods=None, stage_info=None):
    global cache_notas, cache_notas_largas
    # mods: set de ids; si es None usa mods_activos (modo libre)
    mods_partida = set(mods) if mods is not None else set(mods_activos)
    dif     = get_dificultad(seed)
    cancion = generar_cancion(int(seed * 23819), dif)
    inst = cancion["instrumento"]
    # limitar holds: percusivos max 800ms, todos max 4s (duracion del sample)
    hold_max = HOLD_MAX_PERCUSIVO if inst not in INST_SUSTAIN else HOLD_MAX
    for n in cancion["notas_jugador"]:
        if n.get("hold", 0) > hold_max:
            n["hold"] = hold_max
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
    pygame.time.delay(900)

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

    return {
        "seed":           seed,
        "dificultad":     dif,
        "cancion":        cancion,
        "indice_jugador": 0,
        "indice_perc":    0,
        "indice_bajo":    0,
        "inicio":         pygame.time.get_ticks(),
        "notas_cayendo":  [],
        "puntos":         0,
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
    }

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

    if ahora >= c["duracion_loop"] and not partida["terminada"]:
        partida["terminada"] = True

    # paneo por tipo de elemento de percusión
    pan_perc = {
        "kick": (1.0, 1.0), "snare": (1.0, 1.0), "clap": (0.95, 0.95),
        "hihat": (0.7, 1.0), "hihat_o": (0.7, 1.0),
        "clave": (1.0, 0.7), "agogo": (1.0, 0.65),
        "crash": (0.9, 0.9), "tom1": (1.0, 0.8), "tom2": (0.8, 1.0),
    }
    # CAPA 3: determinar si hay un evento activo ahora
    evento_activo = None
    for ev in c.get("eventos", []):
        if ev["tiempo"] <= ahora < ev["tiempo"] + ev["dur"]:
            evento_activo = ev["tipo"]
            break
    partida["evento_activo"] = evento_activo

    while partida["indice_perc"] < len(c["percusion"]) and ahora >= c["percusion"][partida["indice_perc"]]["tiempo"]:
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
    while partida["indice_bajo"] < len(bajo) and ahora >= bajo[partida["indice_bajo"]]["tiempo"]:
        ev = bajo[partida["indice_bajo"]]
        snd_b = cache_bajo.get(ev["midi"])
        if snd_b:
            ch_b = snd_b.play()
            if ch_b:
                ch_b.set_volume(min(1.0, config["volumen"] * vol_bajo))
        partida["indice_bajo"] += 1

def get_parte(partida, ahora):
    e = partida["cancion"]["estructura"]
    if ahora < e["intro_fin"]:       return "INTRO"
    elif ahora < e["nudo_fin"]:      return "NUDO"
    elif ahora < e["desenlace_fin"]: return "FIN"
    return "FIN"

GRIS_FONDO = (28, 28, 28)
GRIS_FONDO2 = (45, 45, 45)

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
    """Dibuja la figura procedural de fondo. Late con el kick y las notas, vibra en holds."""
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

    # vibracion extra mientras hay holds activos
    hay_hold = len(partida.get("holds_activos", {})) > 0
    jitter = 0.0
    if hay_hold:
        # mas holds = mas vibracion
        jitter = 2.0 + len(partida["holds_activos"]) * 1.5

    # brillo extra segun el combo: la figura se ilumina con la racha
    combo = partida.get("combo", 0)
    brillo_combo = min(combo / 30.0, 1.0)   # 0 a 1 entre combo 0 y 30
    # un pulso de fondo constante crece con el combo
    pulso = max(pulso, brillo_combo * 0.5)

    cx_c = ANCHO / 2
    cy_c = (ZONA_Y) / 2 + 20
    rx = (ANCHO * 0.42) * escala
    ry = (ZONA_Y * 0.40) * escala

    # techo de brillo y boost suben con el combo
    techo = int(140 + brillo_combo * 90)        # hasta 230 con combo alto
    boost = 50 + (30 if hay_hold else 0) + int(brillo_combo * 80)
    color = (min(techo, int(GRIS_FONDO[0] + pulso * boost)),
             min(techo, int(GRIS_FONDO[1] + pulso * boost)),
             min(techo, int(GRIS_FONDO[2] + pulso * boost)))
    # color de la segunda figura tambien se aviva con el combo
    base2 = int(GRIS_FONDO[0] + brillo_combo * 40)
    color2 = (base2, base2, base2)

    puntos = _curva_fondo(tipo, liss, npts, t_anim, cx_c, cy_c, rx, ry, jitter=jitter)
    clip_ant = pantalla.get_clip()
    pantalla.set_clip(pygame.Rect(0, 0, ANCHO, ZONA_Y + 54))
    if len(puntos) > 1:
        # con combo muy alto, la linea se engrosa
        grosor = 2 if brillo_combo >= 0.8 else 1
        pygame.draw.lines(pantalla, color, False, puntos, grosor)
        puntos2 = _curva_fondo(tipo, liss, npts, -t_anim * 0.6,
                               cx_c, cy_c, rx * 0.7, ry * 0.7, fase_extra=1.0, jitter=jitter)
        pygame.draw.lines(pantalla, color2, False, puntos2, 1)
    pantalla.set_clip(clip_ant)

def dibujar_juego(partida, ahora):
    num_cols  = partida["dificultad"]["columnas"]
    ancho_col = ANCHO // num_cols
    parte     = get_parte(partida, ahora)
    sx, sy    = shake_dx, shake_dy
    col_nota  = color_genero(partida)   # color de acento del genero
    zy        = partida.get("zona_y", ZONA_Y)  # zona de golpe (arriba si inverso)
    es_inv    = partida.get("es_inverso", False)

    # fondo procedural (figura de lissajous tenue)
    if not partida.get("game_over"):
        dibujar_fondo_lissajous(partida, ahora)

    for i in range(1, num_cols):
        pygame.draw.line(pantalla, GRIS, (i * ancho_col + sx, 0), (i * ancho_col + sx, ALTO), 1)

    # dibujar flashes de columna
    for f in flashes:
        pct = f["vida"] / f["vida_max"]
        alpha = int(40 * pct * f["intensidad"])
        col_x = f["col"] * ancho_col + sx
        flash_surf = pygame.Surface((ancho_col, ALTO))
        flash_surf.set_alpha(alpha)
        flash_surf.fill(col_nota)
        pantalla.blit(flash_surf, (col_x, 0))

    # linea de hit (se mueve con inverso)
    pygame.draw.line(pantalla, col_nota, (sx, zy + sy), (ANCHO + sx, zy + sy), 2)

    # CLIP: las notas se cortan justo en la linea de hit (zy)
    clip_anterior = pantalla.get_clip()
    if es_inv:
        pantalla.set_clip(pygame.Rect(0, zy + 2, ANCHO, ALTO - zy))
    else:
        pantalla.set_clip(pygame.Rect(0, 0, ANCHO, zy))

    es_invisible = "invisible" in partida.get("mods", set())
    for grupo in partida["notas_cayendo"]:
        # modificador INVISIBLE: las notas desaparecen cerca de la zona
        if es_invisible:
            if es_inv and grupo["y"] < zy + (ALTO - zy) * 0.45:
                continue
            elif not es_inv and grupo["y"] > zy * 0.45:
                continue
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
                if grupo.get("es_acorde"):
                    pygame.draw.rect(pantalla, col_nota, (x + 6,  gy,     ancho_col - 12, 28))
                    pygame.draw.rect(pantalla, NEGRO,  (x + 9,  gy + 3, ancho_col - 18, 22))
                    pygame.draw.rect(pantalla, col_nota, (x + 11, gy + 5, ancho_col - 22, 18))
                else:
                    pygame.draw.rect(pantalla, col_nota, (x + 6, gy, ancho_col - 12, 28))
            xs.append(x + ancho_col // 2)
        if len(xs) > 1:
            pygame.draw.line(pantalla, col_nota, (xs[0], gy + 14), (xs[-1], gy + 14), 2)

    pantalla.set_clip(clip_anterior)

    # labels del jugador (encima de las notas)
    pygame.draw.line(pantalla, BLANCO, (sx, zy + 34 + sy), (ANCHO + sx, zy + 34 + sy), 1)
    mt = partida.get("mapa_teclas", {})
    inv_teclas = {}
    for tecla_pos, col_dest in mt.items():
        inv_teclas[col_dest] = tecla_pos
    for i in range(num_cols):
        x = i * ancho_col + sx
        if i in teclas_sostenidas:
            pygame.draw.rect(pantalla, GRIS, (x + 2, zy + 2 + sy, ancho_col - 4, 32))
        col_activa = BLANCO if i in teclas_sostenidas else GRIS_MED
        tecla_idx = inv_teclas.get(i, i)
        label = fuente_chica.render(LABELS[tecla_idx], True, col_activa)
        pantalla.blit(label, (x + ancho_col // 2 - label.get_width() // 2, zy + 8 + sy))

    pts = fuente.render(str(partida["puntos"]).zfill(6), True, BLANCO)
    pantalla.blit(pts, (ANCHO // 2 - pts.get_width() // 2, 10))

    # combo
    if partida["combo"] >= 5:
        combo_txt = fuente.render(f"{partida['combo']}x COMBO", True, col_nota)
        pantalla.blit(combo_txt, (ANCHO // 2 - combo_txt.get_width() // 2, 38))

    # barra de vida
    vida_w = 200
    vida_x = ANCHO - vida_w - 10
    vida_y = 28
    vida_pct = partida["vida"] / partida["vida_max"]
    pygame.draw.rect(pantalla, GRIS, (vida_x, vida_y, vida_w, 8))
    if vida_pct > 0:
        color_vida = BLANCO if vida_pct > 0.3 else GRIS_MED
        pygame.draw.rect(pantalla, color_vida, (vida_x, vida_y, int(vida_w * vida_pct), 8))
    pygame.draw.rect(pantalla, BLANCO, (vida_x, vida_y, vida_w, 8), 1)

    dif_txt = fuente_chica.render(partida["dificultad"]["nombre"], True, GRIS_MED)
    pantalla.blit(dif_txt, (10, 10))
    # indicador de stage si estamos en un run
    si = partida.get("stage_info")
    if si:
        st_txt = fuente_chica.render(f"STAGE {si['n']}/{NUM_STAGES}", True, col_nota)
        pantalla.blit(st_txt, (10, 46))
    # CAPA 3: mostrar evento activo
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
        pantalla.blit(ev_txt, (ANCHO // 2 - ev_txt.get_width() // 2, 50))
    # info del instrumento (mas grande, sin escala)
    info = fuente.render(f"{partida['cancion']['instrumento']}  {partida['cancion']['bpm']}BPM", True, GRIS_MED)
    pantalla.blit(info, (ANCHO - info.get_width() - 10, 8))
    # icono del instrumento a la izquierda del texto (mas grande)
    forma_inst = forma_de_instrumento(partida['cancion']['instrumento'])
    icono_x = ANCHO - info.get_width() - 34
    dibujar_icono_inst(pantalla, forma_inst, icono_x, 18, 12, col_nota)
    # multiplicador de mods activos
    if partida.get("mult_mods", 1.0) > 1.0:
        mult_txt = fuente_chica.render(f"MODS x{partida['mult_mods']:.2f}", True, col_nota)
        pantalla.blit(mult_txt, (ANCHO - mult_txt.get_width() - 10, 50))
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
        fin = fuente.render("FIN", True, BLANCO)
        pantalla.blit(fin, (ANCHO // 2 - fin.get_width() // 2, ALTO // 2 - 40))
        sc_txt = fuente.render(f"PUNTOS: {partida['puntos']}  MAX COMBO: {partida['max_combo']}x", True, GRIS_MED)
        pantalla.blit(sc_txt, (ANCHO // 2 - sc_txt.get_width() // 2, ALTO // 2))
        if run_actual is not None:
            stage_n = run_actual["stage"]
            if stage_n < NUM_STAGES:
                esc2 = fuente_chica.render(f"ESPACIO = SIGUIENTE STAGE ({stage_n + 1}/{NUM_STAGES})", True, GRIS)
            else:
                esc2 = fuente_chica.render("ESPACIO = COMPLETAR RUN!", True, GRIS)
        else:
            esc2 = fuente_chica.render("ESC PARA VOLVER", True, GRIS)
        pantalla.blit(esc2, (ANCHO // 2 - esc2.get_width() // 2, ALTO // 2 + 40))
        ruta = partida.get("export_ruta")
        if ruta:
            ok_txt = fuente_chica.render("GUARDADA EN export/", True, BLANCO)
            pantalla.blit(ok_txt, (ANCHO // 2 - ok_txt.get_width() // 2, ALTO // 2 + 65))
        elif partida.get("exportando"):
            ex_txt = fuente_chica.render("GUARDANDO...", True, GRIS_MED)
            pantalla.blit(ex_txt, (ANCHO // 2 - ex_txt.get_width() // 2, ALTO // 2 + 65))
        else:
            dl_txt = fuente_chica.render("D = DESCARGAR CANCION", True, BLANCO)
            pantalla.blit(dl_txt, (ANCHO // 2 - dl_txt.get_width() // 2, ALTO // 2 + 65))

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

    lb_txt = fuente_chica.render("L = LEADERBOARD     C = CONFIG", True, GRIS)
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
    """Devuelve el set de mods para el stage n (1..4)."""
    if n == 1:
        return set()
    elif n in (2, 3):
        return {rng.choice(MODS_FACILES)}
    else:  # stage 4
        return {"sudden"}

def crear_run(seed_inicial):
    """Crea un run de stages a partir de la seed cargada."""
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
    return {
        "genero": genero,
        "nivel": nivel,
        "stage": 1,            # stage actual (1..4)
        "seeds": seeds,        # seed por stage
        "mods": mods_stages,   # set de mods por stage
        "puntos_total": 0,
    }

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

    cont = fuente_chica.render("ESPACIO = JUGAR STAGE     ESC = ABANDONAR RUN", True, GRIS_MED)
    pantalla.blit(cont, (ANCHO // 2 - cont.get_width() // 2, ALTO - 50))

# --- animacion de dado para revelar el mod del siguiente stage ---
dado_inicio = 0
DADO_DURACION = 2500  # ms que dura la animacion del dado

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
    sub = fuente.render("TIRANDO DADO...", True, GRIS_MED)
    if progreso >= 1.0:
        sub = fuente.render("MOD REVELADO!", True, BLANCO)
    pantalla.blit(sub, (ANCHO // 2 - sub.get_width() // 2, 180))

    # dado girando: cicla entre mods cada vez mas lento
    if progreso < 1.0:
        # velocidad decrece exponencialmente: rapido al inicio, lento al final
        freq = 20.0 * (1.0 - progreso * 0.9)  # ciclos por segundo
        fase = int(ahora * freq / 1000)
        # elegir un mod del pool para mostrar (cycling)
        todos_mods = MODS_FACILES + ["sudden"]
        mod_mostrar = todos_mods[fase % len(todos_mods)]
    else:
        # parado en el mod real
        mod_mostrar = list(mod_real)[0] if mod_real else ""

    # dibujar el "dado" (cuadro grande con el nombre del mod)
    dado_w, dado_h = 400, 120
    dado_x = ANCHO // 2 - dado_w // 2
    dado_y = 240
    # temblor mientras gira
    if progreso < 1.0:
        shake = int((1.0 - progreso) * 6)
        dado_x += random.randint(-shake, shake)
        dado_y += random.randint(-shake, shake)
    # borde
    borde_color = col_g if progreso >= 1.0 else BLANCO
    pygame.draw.rect(pantalla, borde_color, (dado_x, dado_y, dado_w, dado_h), 3)
    # puntos decorativos en las esquinas (como un dado)
    for dx, dy in [(20, 20), (dado_w - 20, 20), (20, dado_h - 20), (dado_w - 20, dado_h - 20)]:
        pygame.draw.circle(pantalla, GRIS, (dado_x + dx, dado_y + dy), 5)
    # nombre del mod
    nombre_mod = ""
    for m in MODIFICADORES:
        if m["id"] == mod_mostrar:
            nombre_mod = m["nombre"]
            break
    color_mod = col_g if progreso >= 1.0 else BLANCO
    mod_txt = fuente_grande.render(nombre_mod, True, color_mod)
    pantalla.blit(mod_txt, (ANCHO // 2 - mod_txt.get_width() // 2, dado_y + dado_h // 2 - mod_txt.get_height() // 2))

    # descripcion del mod (solo cuando se revelo)
    if progreso >= 1.0:
        for m in MODIFICADORES:
            if m["id"] == mod_mostrar:
                desc = fuente_chica.render(m["desc"], True, GRIS_MED)
                pantalla.blit(desc, (ANCHO // 2 - desc.get_width() // 2, dado_y + dado_h + 20))
                mult = fuente_chica.render(f"MULTIPLICADOR: x{m['mult']}", True, GRIS_MED)
                pantalla.blit(mult, (ANCHO // 2 - mult.get_width() // 2, dado_y + dado_h + 45))
                break
        cont = fuente_chica.render("ESPACIO = CONTINUAR", True, GRIS)
        pantalla.blit(cont, (ANCHO // 2 - cont.get_width() // 2, ALTO - 50))

run_completado_inicio = 0
run_completado_particulas = []
run_completado_fuegos = []

def _spawn_notas_celebracion(col_g):
    """Genera la primera oleada de particulas."""
    run_completado_particulas.clear()
    run_completado_fuegos.clear()
    global run_completado_inicio
    run_completado_inicio = pygame.time.get_ticks()
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
    pantalla.fill(NEGRO)
    col_g = COLOR_GENERO.get(run_actual["genero"], BLANCO)
    ahora = pygame.time.get_ticks()
    t_total = (ahora - run_completado_inicio) / 1000.0
    dt = 1.0 / 60

    # spawns periodicos de fuegos artificiales
    if t_total < 8.0 and random.random() < 0.08:
        _spawn_fuego(col_g)

    # lluvia de chispas desde arriba
    if t_total < 6.0 and random.random() < 0.3:
        run_completado_particulas.append({
            "x": random.randint(0, ANCHO), "y": -5,
            "vx": random.uniform(-0.5, 0.5), "vy": random.uniform(1, 3),
            "vida": random.uniform(3.0, 6.0), "t": 0,
            "color": col_g if random.random() > 0.5 else BLANCO,
            "tam": random.randint(1, 4),
        })

    # barras de fondo pulsantes
    pulso = math.sin(t_total * 4) * 0.5 + 0.5
    for i in range(0, ANCHO, 60):
        alpha = int(12 * pulso)
        bar = pygame.Surface((30, ALTO))
        bar.fill(col_g)
        bar.set_alpha(alpha)
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

    y0 = 160
    for i, m in enumerate(MODIFICADORES):
        y = y0 + i * 56
        sel = (i == mods_opcion)
        activo = m["id"] in mods_activos
        # checkbox
        box_x = 90
        pygame.draw.rect(pantalla, GRIS, (box_x, y, 22, 22), 2)
        if activo:
            pygame.draw.rect(pantalla, BLANCO, (box_x + 4, y + 4, 14, 14))
        # nombre + descripcion
        color = BLANCO if sel else GRIS_MED
        marca = "> " if sel else "  "
        nom = fuente.render(f"{marca}{m['nombre']}", True, color)
        pantalla.blit(nom, (box_x + 40, y - 2))
        desc = fuente_chica.render(m["desc"], True, GRIS)
        pantalla.blit(desc, (box_x + 40, y + 24))
        # multiplicador
        mult_txt = fuente_chica.render(f"x{m['mult']}", True, color)
        pantalla.blit(mult_txt, (ANCHO - 120, y + 4))

    # multiplicador total
    mult_total = calcular_mult_mods()
    pygame.draw.line(pantalla, GRIS, (60, 470), (ANCHO - 60, 470), 1)
    total_txt = fuente.render(f"MULTIPLICADOR TOTAL: x{mult_total:.2f}", True, BLANCO)
    pantalla.blit(total_txt, (ANCHO // 2 - total_txt.get_width() // 2, 485))

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
    global SND_ERROR, cache_por_instrumento, cache_largas_por_instrumento
    config["audio_idx"] = idx
    try:
        pygame.mixer.quit()
        if idx == 0:
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
        else:
            nombre = AUDIO_DEVICES[idx]
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512, devicename=nombre)
        pygame.mixer.set_num_channels(32)
        # reconstruir sonidos globales
        SND_ERROR = synth_error()
        # limpiar caches de instrumentos (se re-renderizan al jugar)
        cache_por_instrumento.clear()
        cache_largas_por_instrumento.clear()
    except Exception as e:
        print(f"Error cambiando audio: {e}")
        pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
        pygame.mixer.set_num_channels(32)
        SND_ERROR = synth_error()
        config["audio_idx"] = 0

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
                    run_actual = crear_run(int(seed_acumulada))
                    ESTADO = "run_overview"
                if evento.key == pygame.K_m and seed_acumulada > 0:
                    # modo libre de mods (sin stages)
                    mods_opcion = 0
                    ESTADO = "mods"
                if evento.key == pygame.K_r:
                    seed_acumulada = 0.0
                    cargando_seed  = False
                if evento.key == pygame.K_l:
                    ESTADO = "leaderboard"
                if evento.key == pygame.K_c:
                    config_opcion = 0
                    ESTADO = "config"
            if evento.type == pygame.KEYUP:
                if evento.key == pygame.K_SPACE:
                    cargando_seed = False

        elif ESTADO == "run_overview":
            if evento.type == pygame.KEYDOWN:
                if evento.key == pygame.K_ESCAPE:
                    run_actual = None
                    ESTADO = "menu"
                    nueva_musica_menu_aleatoria()
                elif evento.key == pygame.K_SPACE:
                    detener_musica_menu()
                    pygame.mixer.stop()
                    idx = run_actual["stage"] - 1
                    seed_stage = run_actual["seeds"][idx]
                    mods_stage = run_actual["mods"][idx]
                    dibujar_carga_seed(seed_stage)
                    partida = iniciar_partida(
                        seed_stage, mods=mods_stage,
                        stage_info={"n": run_actual["stage"]})
                    score_guardado = False
                    ESTADO = "jugando"

        elif ESTADO == "run_dado":
            if evento.type == pygame.KEYDOWN:
                # solo avanzar cuando la animacion termino
                dado_elapsed = pygame.time.get_ticks() - dado_inicio
                if dado_elapsed >= DADO_DURACION:
                    if evento.key == pygame.K_SPACE:
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
                    pts_run = run_actual.get("puntos_total", 0) + partida.get("puntos", 0)
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
                elif evento.key == pygame.K_DOWN:
                    mods_opcion = (mods_opcion + 1) % len(MODIFICADORES)
                elif evento.key == pygame.K_SPACE:
                    mid = MODIFICADORES[mods_opcion]["id"]
                    if mid in mods_activos:
                        mods_activos.discard(mid)
                    else:
                        mods_activos.add(mid)
                elif evento.key == pygame.K_RETURN:
                    detener_musica_menu()
                    pygame.mixer.stop()
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
                elif evento.key == pygame.K_DOWN:
                    config_opcion = (config_opcion + 1) % 5
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
                elif evento.key == pygame.K_DOWN:
                    pausa_opcion = (pausa_opcion + 1) % 5
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
                            partida = iniciar_partida(
                                run_actual["seeds"][idx],
                                mods=run_actual["mods"][idx],
                                stage_info={"n": run_actual["stage"]})
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
                if evento.key in (pygame.K_ESCAPE, pygame.K_SPACE):
                    if partida.get("game_over") or (partida["terminada"] and not partida["notas_cayendo"]):
                        # FIN / GAME OVER
                        pygame.mixer.stop()
                        teclas_sostenidas.clear()
                        canal_hold.clear()
                        if run_actual is not None:
                            # --- en modo RUN de stages ---
                            if partida.get("game_over"):
                                # perdio el stage -> run fallido
                                ESTADO = "run_fallido"
                                nueva_musica_menu_aleatoria()
                            else:
                                # paso el stage: sumar puntos y avanzar
                                run_actual["puntos_total"] += partida["puntos"]
                                if run_actual["stage"] >= NUM_STAGES:
                                    # run completo!
                                    marcar_completado(run_actual["genero"], run_actual["nivel"])
                                    col_g = COLOR_GENERO.get(run_actual["genero"], BLANCO)
                                    _spawn_notas_celebracion(col_g)
                                    ESTADO = "run_completado"
                                    nueva_musica_menu_aleatoria()
                                else:
                                    run_actual["stage"] += 1
                                    idx_next = run_actual["stage"] - 1
                                    print(f"[DEBUG] Avanzando a stage {run_actual['stage']}, mods[{idx_next}]={run_actual['mods'][idx_next]}")
                                    if run_actual["mods"][idx_next]:
                                        # tiene mods -> animacion de dado
                                        dado_inicio = pygame.time.get_ticks()
                                        ESTADO = "run_dado"
                                        print(f"[DEBUG] -> run_dado (dado_inicio={dado_inicio})")
                                    else:
                                        ESTADO = "run_overview"
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
                        ahora_rel = ahora_ms - partida["inicio"]
                        midi_a_tocar = midi_fijo
                        mejor_dist = 99999
                        for g in partida["notas_cayendo"]:
                            if col in g["cols"]:
                                d = abs(g["tiempo_ms"] - ahora_rel)
                                if d < mejor_dist:
                                    mejor_dist = d
                                    idx_col = g["cols"].index(col)
                                    if idx_col < len(g.get("midis", [])):
                                        midi_a_tocar = g["midis"][idx_col]

                        # volumen segun cercania: cerca del beat suena pleno, lejos mas suave
                        if mejor_dist < 80:
                            vol_nota = 1.0
                        elif mejor_dist < 200:
                            vol_nota = 0.85
                        else:
                            vol_nota = 0.6

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
                        for grupo in partida["notas_cayendo"]:
                            if col in grupo["cols"]:
                                distancia = abs(grupo["tiempo_ms"] - (ahora_ms - partida["inicio"]))
                                if distancia < 150:
                                    acerto_algo = True
                                    if "acertadas" not in grupo:
                                        grupo["acertadas"] = set()
                                    if col not in grupo["acertadas"]:
                                        grupo["acertadas"].add(col)
                                        num_cols = partida["dificultad"]["columnas"]
                                        ancho_col = ANCHO // num_cols
                                        cx = col * ancho_col + ancho_col // 2
                                        col_g = COLOR_GENERO.get(partida["cancion"].get("genero",""), BLANCO)
                                        if distancia < 30:
                                            pts = 5
                                            partida["combo"] += 1
                                            # potencia crece con el combo (1.0 a 2.5)
                                            pot = min(1.0 + partida["combo"] * 0.03, 1.8)
                                            partida["ultimo_hit"] = {"texto": "PERFECTO", "tiempo": ahora_ms}
                                            combo_particulas = min(50 + partida["combo"] * 4, 250)
                                            crear_explosion(cx, zy_p, combo_particulas, color=col_g, potencia=pot)
                                            crear_onda(cx, zy_p, 0.7)
                                            crear_onda(cx, zy_p, 0.4, r0=int(4 + partida["combo"] * 0.3))
                                            if partida["combo"] >= 30:
                                                crear_onda(cx, zy_p, 0.5, r0=int(15 + partida["combo"] * 0.5))
                                            crear_flash(col, min(0.8, 0.5 + partida["combo"] * 0.01))
                                            crear_shake(min(5 + partida["combo"] * 0.15, 12))
                                        elif distancia < 60:
                                            pts = 3
                                            partida["combo"] += 1
                                            pot = min(1.0 + partida["combo"] * 0.02, 1.5)
                                            partida["ultimo_hit"] = {"texto": "BIEN", "tiempo": ahora_ms}
                                            crear_explosion(cx, zy_p, min(30 + partida["combo"] * 2, 150), color=col_g, potencia=pot)
                                            crear_onda(cx, zy_p, 0.5)
                                            crear_flash(col, 0.4)
                                            crear_shake(min(3 + partida["combo"] * 0.1, 8))
                                        elif distancia < 100:
                                            pts = 1
                                            partida["combo"] += 1
                                            partida["ultimo_hit"] = {"texto": "OK", "tiempo": ahora_ms}
                                            crear_explosion(cx, zy_p, 20, color=col_g)
                                            crear_onda(cx, zy_p, 0.4)
                                            crear_flash(col, 0.3)
                                        else:
                                            pts = 0
                                            partida["combo"] = 0
                                            partida["ultimo_hit"] = {"texto": "MAL", "tiempo": ahora_ms}
                                            crear_explosion(cx, zy_p, 8, GRIS_MED)
                                            crear_shake(8)
                                        if partida["combo"] > partida["max_combo"]:
                                            partida["max_combo"] = partida["combo"]
                                        combo_mult = 1 + partida["combo"] // 5
                                        if grupo.get("hold", 0) > 0 and not grupo.get("es_acorde"):
                                            if midi_fijo in cache_notas_largas:
                                                ch = cache_notas_largas[midi_fijo].play()
                                                if ch:
                                                    ch.set_volume(config["volumen"])
                                                    canal_hold[col] = ch
                                            partida["holds_activos"][col] = {
                                                "grupo": grupo,
                                                "midi":  midi_fijo,
                                            }
                                            if pts > 0:
                                                total_pts = int(pts * combo_mult * partida.get("mult_mods", 1.0))
                                                partida["puntos"] += total_pts
                                                txt = f"+{total_pts}"
                                                if combo_mult > 1:
                                                    txt += f" x{combo_mult}"
                                                crear_texto_flotante(cx, zy_p - 20, txt, BLANCO, combo_mult > 2)
                                        else:
                                            if pts > 0:
                                                total_pts = int(pts * len(grupo["cols"]) * combo_mult * partida.get("mult_mods", 1.0))
                                                txt_pts = f"+{total_pts}"
                                                if combo_mult > 1:
                                                    txt_pts += f" x{combo_mult}"
                                                es_grande = combo_mult > 2
                                                crear_texto_flotante(cx, zy_p - 20, txt_pts, BLANCO, es_grande)
                                                partida["puntos"] += total_pts
                                            else:
                                                partida["puntos"] = max(0, partida["puntos"] - 2)
                                                crear_texto_flotante(cx, zy_p - 20, "-2", GRIS_MED)
                                            if partida["combo"] > 0 and partida["combo"] % 5 == 0:
                                                crear_texto_flotante(ANCHO // 2, zy_p - 80, f"{partida['combo']}x COMBO!", BLANCO, True)
                                                crear_shake(4)
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

    elif ESTADO == "config":
        tick_musica_menu()
        dibujar_config()

    elif ESTADO == "mods":
        tick_musica_menu()
        dibujar_mods()

    elif ESTADO == "run_overview":
        tick_musica_menu()
        dibujar_run_overview()

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
        ahora = ahora_ms - partida["inicio"]

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
            # ACELERANDO: velocidad sube de 1x a 2x a lo largo de la cancion
            if "acelerando" in partida.get("mods", set()):
                duracion = partida["cancion"]["duracion_loop"]
                progreso = min(ahora / max(1, duracion), 1.0)
                vel_p *= (1.0 + progreso)  # 1x al inicio, 2x al final
            PIXELES_POR_MS = vel_p / (1000 / 60)
            es_inv = partida.get("es_inverso", False)
            if es_inv:
                ANTICIPACION = (ALTO - zy_p + 40) / PIXELES_POR_MS
            else:
                ANTICIPACION = (zy_p + 40) / PIXELES_POR_MS

            if not partida["terminada"]:
                while partida["indice_jugador"] < len(partida["cancion"]["notas_jugador"]) and ahora >= partida["cancion"]["notas_jugador"][partida["indice_jugador"]]["tiempo"] - ANTICIPACION:
                    n = partida["cancion"]["notas_jugador"][partida["indice_jugador"]]
                    hold_ms = n.get("hold", 0)
                    partida["notas_cayendo"].append({
                        "cols":      n["cols"],
                        "midis":     n["midis"],
                        "tiempo_ms": n["tiempo"],
                        "acertadas": set(),
                        "es_acorde": n.get("es_acorde", False),
                        "hold":      hold_ms,
                        "hold_px":   hold_pixels(hold_ms, vel_p),
                    })
                    partida["indice_jugador"] += 1

            for grupo in partida["notas_cayendo"]:
                ms_hasta = grupo["tiempo_ms"] - ahora
                if es_inv:
                    grupo["y"] = zy_p + (ms_hasta * PIXELES_POR_MS)
                else:
                    grupo["y"] = zy_p - (ms_hasta * PIXELES_POR_MS)

            notas_vivas = []
            for n in partida["notas_cayendo"]:
                # MISS: la nota se fue de la pantalla
                nota_perdida = n["y"] <= -50 if es_inv else n["y"] >= ALTO + 50
                if nota_perdida:
                    es_hold_activo = any(c in partida["holds_activos"] for c in n["cols"])
                    if not es_hold_activo:
                        partida["ultimo_hit"] = {"texto": "MISS", "tiempo": ahora_ms}
                        partida["combo"] = 0
                        partida["puntos"] = max(0, partida["puntos"] - 5)
                        if not dev_mode:
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
