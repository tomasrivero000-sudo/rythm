import pygame
import random
import numpy as np
import json

pygame.init()
pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
pygame.mixer.set_num_channels(32)

ANCHO, ALTO = 720, 640

# --- configuracion ajustable ---
RESOLUCIONES = [(720, 640), (900, 800), (1080, 960), (1280, 1138)]
config = {
    "brillo": 1.0,      # 0.3 a 1.0
    "volumen": 1.0,     # 0.0 a 1.0
    "res_idx": 0,       # indice en RESOLUCIONES
}

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
    1:  {"nombre": "FACIL",      "columnas": 3, "acordes": False},
    2:  {"nombre": "FACIL+",     "columnas": 3, "acordes": False},
    3:  {"nombre": "NORMAL",     "columnas": 4, "acordes": True},
    4:  {"nombre": "NORMAL+",    "columnas": 4, "acordes": True},
    5:  {"nombre": "DIFICIL",    "columnas": 5, "acordes": True},
    6:  {"nombre": "DIFICIL+",   "columnas": 5, "acordes": True},
    7:  {"nombre": "PRO",        "columnas": 6, "acordes": True},
    8:  {"nombre": "PRO+",       "columnas": 6, "acordes": True},
    9:  {"nombre": "MASTER",     "columnas": 7, "acordes": True},
    10: {"nombre": "MASTER+",    "columnas": 7, "acordes": True},
    11: {"nombre": "GOD",        "columnas": 7, "acordes": True},
    12: {"nombre": "CHAOS",      "columnas": 8, "acordes": True},
}

SEED_MAX       = 9999
SEED_VELOCIDAD = 9.0
ZONA_Y         = ALTO - 90
VELOCIDAD      = 5.5

fuente_grande = pygame.font.SysFont("courier", 48, bold=True)
fuente        = pygame.font.SysFont("courier", 24, bold=True)
fuente_chica  = pygame.font.SysFont("courier", 14, bold=True)

SR = 44100

def np_to_sound(samples_mono, vol=0.8, pan=0.0):
    """Convierte array numpy mono a pygame.Sound stereo.
    pan: -1.0 = todo izquierda, 0 = centro, 1.0 = todo derecha"""
    base = np.clip(samples_mono * vol * 32767, -32768, 32767)
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
}

# instrumentos raros: baja probabilidad de aparecer
INSTRUMENTOS_RAROS = {
    "ALIEN":      "alien",
    "BROKEN":     "broken",
}

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
    vol_tipo = {
        "square": 0.5, "saw": 0.5, "chiptune": 0.45,
        "organ": 0.6, "fm_bell": 0.65,
        "sine": 0.75, "triangle": 0.7, "pluck": 0.7,
        "supersaw": 0.45, "acid": 0.55, "bitcrush": 0.5, "lead": 0.5,
        "wobble": 0.55, "glass": 0.65, "pad": 0.6,
        "metallic": 0.55, "bass": 0.55, "flute": 0.65,
        "reso": 0.5, "choir": 0.6,
        "vibraphone": 0.6, "sitar": 0.5, "kalimba": 0.65,
        "trumpet": 0.55, "harp": 0.65, "synthbass": 0.5,
        "bellpad": 0.55, "detune": 0.5,
        "pwm_lead": 0.5, "fm_ep": 0.7, "formant": 0.55,
        "hoover": 0.4, "bell_fm": 0.6, "growl": 0.5,
        "saw_stack": 0.4, "fm_3op": 0.6, "ring_mod": 0.55,
        "sync_lead": 0.5, "pluck_soft": 0.7, "vox_pad": 0.55,
        "dist_gtr": 0.45, "wavefold": 0.55, "phase_pad": 0.6,
        "fm_brass": 0.6, "glass_harm": 0.6, "sub_pluck": 0.6,
        "noise_pitch": 0.5, "organ_full": 0.55,
        "alien": 0.5, "broken": 0.45,
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

def renderizar_instrumento(nombre, tipo, dibujar_progreso=False):
    """Renderiza un instrumento completo (60 notas x 2 duraciones)"""
    inst_rng = random.Random(hash(nombre))
    params = generar_params_instrumento(inst_rng, tipo)
    inst_eq = inst_rng.choice(EQ_TIPOS)
    inst_eq_int = inst_rng.uniform(0.1, 0.35)
    c_cortas = {}
    c_largas = {}
    idx = 0
    for midi in range(36, 96):
        idx += 1
        if dibujar_progreso and midi % 4 == 0:
            dibujar_carga_seed_inst(idx / 60, nombre)
        freq = midi_a_freq(midi)
        snd = synth_nota(tipo, freq, 0.3, params)
        arr = pygame.sndarray.array(snd).astype(np.float64) / 32767
        c_cortas[midi] = np_to_sound(aplicar_eq(arr[:, 0], inst_eq, inst_eq_int))
        params_hold = dict(params)
        params_hold["vibrato"] = params.get("vibrato", 0) + 0.4
        params_hold["vib_speed"] = params.get("vib_speed", 5) * 0.8
        snd_l = synth_nota(tipo, freq, 2.0, params_hold)
        arr_l = pygame.sndarray.array(snd_l).astype(np.float64) / 32767
        c_largas[midi] = np_to_sound(aplicar_eq(arr_l[:, 0], inst_eq, inst_eq_int))
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
    return tonica + escala[grado % len(escala)]

NOMBRES_NOTAS = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
def midi_a_nombre(midi):
    return NOMBRES_NOTAS[midi % 12] + str(midi // 12 - 1)

NOMBRES_NOTAS = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

def midi_a_nombre(midi):
    return NOMBRES_NOTAS[midi % 12] + str(midi // 12 - 1)

# --- leaderboard ---
LEADERBOARD_FILE = "F:\\VIDEOGAMEEE\\leaderboard.json"
TOP_SCORES = 10

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
    tramos = [500, 1000, 1500, 2000, 3000, 4000, 5000, 6000, 7000, 8000, 9000, 9999]
    for i, tope in enumerate(tramos):
        if seed <= tope:
            return DIFICULTADES[i + 1]
    return DIFICULTADES[12]

def elegir_kit(rng):
    return sintetizar_kit(rng)

def generar_patrones_drums(rng):
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
                      c_intro, c_nudo, c_desenlace, kit):
    paso = beat // 4
    pats  = generar_patrones_drums(rng)
    pats2 = generar_patrones_drums(rng)
    pats3 = generar_patrones_drums(rng)
    tercio1 = t_intro_fin + 8 * 4 * beat
    tercio2 = t_intro_fin + 16 * 4 * beat

    # decidir modo de tempo: 30% half-time, 20% double-time, 50% normal
    roll = rng.random()
    if roll < 0.30:
        modo_tempo = "half"
        tempo_tercio = rng.choice([1, 2])   # half-time en un tercio posterior
    elif roll < 0.50:
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
    bpm_por_cols = {3: (80, 100), 4: (95, 110), 5: (105, 120), 6: (115, 130), 7: (125, 145)}
    bpm_min, bpm_max = bpm_por_cols.get(num_columnas, (110, 130))
    BPM          = rng.randint(bpm_min, bpm_max)
    beat         = 60000 // BPM
    paso16       = beat // 4
    tonica       = rng.choice([36, 38, 40, 41, 43, 45, 47, 48, 50, 52, 53, 55])
    nombre_escala= rng.choice(list(ESCALAS.keys()))
    escala       = ESCALAS[nombre_escala]
    patron_acordes = ACORDES_PATRON.get(nombre_escala, ACORDES_PATRON["mayor"])
    base_prog = rng.choice(PROGRESIONES)
    # repetir la progresion de 4 acordes para cubrir 8 compases
    progresion = base_prog * 2

    notas_columnas = [nota_midi(tonica + 12, escala, i) for i in range(num_columnas)]
    kit = elegir_kit(rng)
    # 8% de probabilidad de que toque un instrumento raro
    if rng.random() < 0.08:
        instrumento = rng.choice(list(INSTRUMENTOS_RAROS.keys()))
    else:
        instrumento = rng.choice(list(INSTRUMENTOS_JUGADOR.keys()))

    C_INTRO     = 4
    C_NUDO      = 24
    C_DESENLACE = 4
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

    for rep in range(6):
        if rep < 2:
            bloque = bloque_a
        elif rep < 4:
            bloque = bloque_b
        else:
            bloque = bloque_c
        for c in range(4):
            compas_real = rep * 4 + c
            compas = bloque[c]
            for s in range(16):
                if compas[s] is None:
                    continue
                t   = t_intro_fin + compas_real * 4 * beat + (s // 4) * beat
                col = compas[s]["col"]
                hd  = compas[s]["hold"]
                segunda_mitad = rep >= 3
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
                            "midis": [notas_columnas[cx] for cx in cols_ac],
                            "tiempo": t, "es_acorde": True, "parte": "nudo", "hold": 0,
                        })
                        continue
                notas_jugador.append({
                    "cols": [col], "midis": [notas_columnas[col]],
                    "tiempo": t, "es_acorde": False, "parte": "nudo", "hold": hd,
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
                                  C_INTRO, C_NUDO, C_DESENLACE, kit)

    # --- linea de bajo procedural ---
    estilo_bajo = rng.choice(["round", "pluck", "sub", "reese"])
    # patrones ritmicos de bajo (16avos por compas)
    patrones_bajo = [
        [1,0,0,0,1,0,0,0,1,0,0,0,1,0,0,0],   # negras
        [1,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0],   # blancas
        [1,0,0,1,0,0,1,0,1,0,0,1,0,0,1,0],   # sincopado
        [1,0,1,0,1,0,1,0,1,0,1,0,1,0,1,0],   # corcheas
        [1,0,0,0,1,0,1,0,1,0,0,0,1,0,1,0],   # groove
    ]
    pat_bajo = rng.choice(patrones_bajo)
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

    return {
        "bpm":            BPM,
        "beat":           beat,
        "paso16":         paso16,
        "escala":         nombre_escala,
        "duracion_loop":  t_desenlace_fin,
        "notas_jugador":  sorted(notas_jugador, key=lambda n: n["tiempo"]),
        "percusion":      percusion,
        "bajo":           cancion_bajo,
        "kit":            kit,
        "instrumento":    instrumento,
        "notas_columnas": notas_columnas,
        "lissajous":      lissajous,
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

def iniciar_partida(seed):
    global cache_notas, cache_notas_largas
    dif     = get_dificultad(seed)
    cancion = generar_cancion(int(seed * 23819), dif)
    inst = cancion["instrumento"]
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
    }

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
    while partida["indice_perc"] < len(c["percusion"]) and ahora >= c["percusion"][partida["indice_perc"]]["tiempo"]:
        p = c["percusion"][partida["indice_perc"]]
        sample = kit.get(p["sample"])
        if sample:
            vol = min(1.0, p["vol"] * 1.2) * config["volumen"]
            gl, gr = pan_perc.get(p["sample"], (1.0, 1.0))
            ch = sample.play()
            if ch:
                ch.set_volume(vol * gl, vol * gr)
        partida["indice_perc"] += 1

    # reproducir linea de bajo
    bajo = c["bajo"]["eventos"]
    cache_bajo = c.get("cache_bajo", {})
    while partida["indice_bajo"] < len(bajo) and ahora >= bajo[partida["indice_bajo"]]["tiempo"]:
        ev = bajo[partida["indice_bajo"]]
        snd_b = cache_bajo.get(ev["midi"])
        if snd_b:
            ch_b = snd_b.play()
            if ch_b:
                ch_b.set_volume(config["volumen"])
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

    cx_c = ANCHO / 2
    cy_c = (ZONA_Y) / 2 + 20
    rx = (ANCHO * 0.42) * escala
    ry = (ZONA_Y * 0.40) * escala

    boost = 50 + (30 if hay_hold else 0)
    color = (min(140, int(GRIS_FONDO[0] + pulso * boost)),
             min(140, int(GRIS_FONDO[1] + pulso * boost)),
             min(140, int(GRIS_FONDO[2] + pulso * boost)))

    puntos = _curva_fondo(tipo, liss, npts, t_anim, cx_c, cy_c, rx, ry, jitter=jitter)
    clip_ant = pantalla.get_clip()
    pantalla.set_clip(pygame.Rect(0, 0, ANCHO, ZONA_Y + 54))
    if len(puntos) > 1:
        pygame.draw.lines(pantalla, color, False, puntos, 1)
        puntos2 = _curva_fondo(tipo, liss, npts, -t_anim * 0.6,
                               cx_c, cy_c, rx * 0.7, ry * 0.7, fase_extra=1.0, jitter=jitter)
        pygame.draw.lines(pantalla, GRIS_FONDO, False, puntos2, 1)
    pantalla.set_clip(clip_ant)

def dibujar_juego(partida, ahora):
    num_cols  = partida["dificultad"]["columnas"]
    ancho_col = ANCHO // num_cols
    parte     = get_parte(partida, ahora)
    sx, sy    = shake_dx, shake_dy

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
        flash_surf.fill(BLANCO)
        pantalla.blit(flash_surf, (col_x, 0))

    pygame.draw.line(pantalla, BLANCO, (sx, ZONA_Y + sy), (ANCHO + sx, ZONA_Y + sy), 2)
    pygame.draw.line(pantalla, BLANCO, (sx, ZONA_Y + 54 + sy), (ANCHO + sx, ZONA_Y + 54 + sy), 1)

    # nota actual de cada columna (puede cambiar de octava en el desenlace)
    notas_label = list(partida["cancion"]["notas_columnas"])
    for grupo in partida["notas_cayendo"]:
        if abs(grupo["y"] - ZONA_Y) < 200:
            for idx_c, c in enumerate(grupo["cols"]):
                if idx_c < len(grupo.get("midis", [])) and c < len(notas_label):
                    notas_label[c] = grupo["midis"][idx_c]

    for i in range(num_cols):
        x = i * ancho_col + sx
        if i in teclas_sostenidas:
            pygame.draw.rect(pantalla, GRIS, (x + 2, ZONA_Y + 2 + sy, ancho_col - 4, 50))
        col_activa = BLANCO if i in teclas_sostenidas else GRIS_MED
        label = fuente_chica.render(LABELS[i], True, col_activa)
        pantalla.blit(label, (x + ancho_col // 2 - label.get_width() // 2, ZONA_Y + 10 + sy))
        if i < len(notas_label):
            nota_name = midi_a_nombre(notas_label[i])
            nota_txt = fuente_chica.render(nota_name, True, col_activa)
            pantalla.blit(nota_txt, (x + ancho_col // 2 - nota_txt.get_width() // 2, ZONA_Y + 28 + sy))

    # limite inferior donde se cortan las notas (justo encima del teclado)
    limite_notas = ZONA_Y + 54
    clip_anterior = pantalla.get_clip()
    pantalla.set_clip(pygame.Rect(0, 0, ANCHO, limite_notas + sy))

    for grupo in partida["notas_cayendo"]:
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
                bar_y = gy - hold_h
                bar_h = hold_h
                if col in partida["holds_activos"]:
                    # barra que oscila: dibujada por segmentos con desplazamiento senoidal
                    fase = pygame.time.get_ticks() * 0.012
                    seg = 6
                    cx_bar = x + ancho_col // 2
                    pasos = max(2, bar_h // seg)
                    for k in range(pasos):
                        yy = bar_y + k * seg
                        prog = k / pasos
                        # mas amplitud arriba (lejos de la zona), se calma al llegar
                        amp = 7 * prog
                        ox = math.sin(fase + k * 0.5) * amp
                        pygame.draw.rect(pantalla, GRIS_MED, (int(cx_bar + ox - 8), yy, 16, seg + 1))
                        pygame.draw.rect(pantalla, BLANCO, (int(cx_bar + ox - 5), yy, 10, seg + 1))
                else:
                    pygame.draw.rect(pantalla, GRIS_MED, (bar_x, bar_y, 12, bar_h))
                    pygame.draw.rect(pantalla, BLANCO, (bar_x, bar_y, 12, bar_h), 1)
            if col in pendientes:
                if grupo.get("es_acorde"):
                    pygame.draw.rect(pantalla, BLANCO, (x + 6,  gy,     ancho_col - 12, 28))
                    pygame.draw.rect(pantalla, NEGRO,  (x + 9,  gy + 3, ancho_col - 18, 22))
                    pygame.draw.rect(pantalla, BLANCO, (x + 11, gy + 5, ancho_col - 22, 18))
                else:
                    pygame.draw.rect(pantalla, BLANCO, (x + 6, gy, ancho_col - 12, 28))
            xs.append(x + ancho_col // 2)
        if len(xs) > 1:
            pygame.draw.line(pantalla, BLANCO, (xs[0], gy + 14), (xs[-1], gy + 14), 2)

    pantalla.set_clip(clip_anterior)

    pts = fuente.render(str(partida["puntos"]).zfill(6), True, BLANCO)
    pantalla.blit(pts, (ANCHO // 2 - pts.get_width() // 2, 10))

    # combo
    if partida["combo"] >= 5:
        combo_txt = fuente.render(f"{partida['combo']}x COMBO", True, BLANCO)
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
    parte_txt = fuente_chica.render(parte, True, GRIS)
    pantalla.blit(parte_txt, (10, 28))
    info = fuente_chica.render(f"{partida['cancion']['instrumento']}  {partida['cancion']['escala'].upper()}  {partida['cancion']['bpm']}BPM", True, GRIS)
    pantalla.blit(info, (ANCHO - info.get_width() - 10, 10))
    esc_txt = fuente_chica.render("ESC", True, GRIS)
    pantalla.blit(esc_txt, (10, ALTO - 20))

    # --- mini teclado de piano (refleja las notas actuales) ---
    notas_base = partida["cancion"]["notas_columnas"]
    # determinar la nota actual de cada columna segun las notas que estan sonando
    notas_actuales = list(notas_base)
    for grupo in partida["notas_cayendo"]:
        # notas cerca de la zona de golpe definen la tonalidad actual
        if abs(grupo["y"] - ZONA_Y) < 200:
            for idx_c, c in enumerate(grupo["cols"]):
                if idx_c < len(grupo.get("midis", [])) and c < len(notas_actuales):
                    notas_actuales[c] = grupo["midis"][idx_c]
    notas_cols = notas_actuales
    tecl_y = ZONA_Y + 56 + sy
    tecl_h = ALTO - tecl_y - 4
    if tecl_h > 8:
        tecl_h = min(tecl_h, 28)
        midi_min = min(notas_cols) - 2
        midi_max = max(notas_cols) + 2
        midi_min = (midi_min // 12) * 12
        midi_max = ((midi_max // 12) + 1) * 12
        es_negra = [1, 3, 6, 8, 10]
        blancas = [m for m in range(midi_min, midi_max) if (m % 12) not in es_negra]
        n_blancas = len(blancas)
        if n_blancas > 0:
            tw = ANCHO // n_blancas
            for idx, m in enumerate(blancas):
                kx = idx * tw + sx
                activa = m in notas_cols
                presionada = activa and any(
                    notas_cols[c] == m and c in teclas_sostenidas
                    for c in range(len(notas_cols))
                )
                if presionada:
                    pygame.draw.rect(pantalla, BLANCO, (kx + 1, tecl_y, tw - 2, tecl_h))
                elif activa:
                    pygame.draw.rect(pantalla, GRIS_MED, (kx + 1, tecl_y, tw - 2, tecl_h))
                else:
                    pygame.draw.rect(pantalla, GRIS, (kx + 1, tecl_y, tw - 2, tecl_h), 1)
            for idx, m in enumerate(blancas):
                if m + 1 < midi_max and (m + 1) % 12 in es_negra:
                    mn = m + 1
                    kx = idx * tw + tw // 2 + tw // 4 + sx
                    bw = tw // 2
                    bh = tecl_h * 2 // 3
                    activa = mn in notas_cols
                    presionada = activa and any(
                        notas_cols[c] == mn and c in teclas_sostenidas
                        for c in range(len(notas_cols))
                    )
                    if presionada:
                        pygame.draw.rect(pantalla, BLANCO, (kx, tecl_y, bw, bh))
                    elif activa:
                        pygame.draw.rect(pantalla, GRIS_MED, (kx, tecl_y, bw, bh))
                    else:
                        pygame.draw.rect(pantalla, NEGRO, (kx, tecl_y, bw, bh))
                        pygame.draw.rect(pantalla, GRIS, (kx, tecl_y, bw, bh), 1)

    hit = partida.get("ultimo_hit")
    if hit and pygame.time.get_ticks() - hit["tiempo"] < 500:
        color = BLANCO if hit["texto"] in ["PERFECTO", "BIEN"] else GRIS_MED
        hit_txt = fuente.render(hit["texto"], True, color)
        pantalla.blit(hit_txt, (ANCHO // 2 - hit_txt.get_width() // 2, ZONA_Y - 60))

    if partida.get("game_over"):
        go_txt = fuente_grande.render("GAME OVER", True, BLANCO)
        pantalla.blit(go_txt, (ANCHO // 2 - go_txt.get_width() // 2, ALTO // 2 - 50))
        sc_txt = fuente.render(f"PUNTOS: {partida['puntos']}  MAX COMBO: {partida['max_combo']}x", True, GRIS_MED)
        pantalla.blit(sc_txt, (ANCHO // 2 - sc_txt.get_width() // 2, ALTO // 2 + 10))
        esc2 = fuente_chica.render("ESC PARA VOLVER", True, GRIS)
        pantalla.blit(esc2, (ANCHO // 2 - esc2.get_width() // 2, ALTO // 2 + 50))

    elif partida["terminada"] and not partida["notas_cayendo"]:
        fin = fuente.render("FIN", True, BLANCO)
        pantalla.blit(fin, (ANCHO // 2 - fin.get_width() // 2, ALTO // 2 - 40))
        sc_txt = fuente.render(f"PUNTOS: {partida['puntos']}  MAX COMBO: {partida['max_combo']}x", True, GRIS_MED)
        pantalla.blit(sc_txt, (ANCHO // 2 - sc_txt.get_width() // 2, ALTO // 2))
        esc2 = fuente_chica.render("ESC PARA VOLVER", True, GRIS)
        pantalla.blit(esc2, (ANCHO // 2 - esc2.get_width() // 2, ALTO // 2 + 40))

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
        enter = fuente_chica.render("ENTER = JUGAR     R = RESET", True, GRIS_MED)
        pantalla.blit(enter, (ANCHO // 2 - enter.get_width() // 2, 460))

    if seed_actual == 0:
        if (pygame.time.get_ticks() // 500) % 2 == 0:
            coin = fuente.render("INSERT COIN", True, BLANCO)
            pantalla.blit(coin, (ANCHO // 2 - coin.get_width() // 2, 460))

    lb_txt = fuente_chica.render("L = LEADERBOARD     C = CONFIG", True, GRIS)
    pantalla.blit(lb_txt, (ANCHO // 2 - lb_txt.get_width() // 2, 510))

config_opcion = 0  # 0=brillo, 1=volumen, 2=resolucion

def dibujar_config():
    pantalla.fill(NEGRO)
    titulo = fuente_grande.render("CONFIG", True, BLANCO)
    pantalla.blit(titulo, (ANCHO // 2 - titulo.get_width() // 2, 60))
    pygame.draw.line(pantalla, BLANCO, (60, 120), (ANCHO - 60, 120), 2)

    opciones = [
        ("BRILLO", config["brillo"], "barra"),
        ("VOLUMEN", config["volumen"], "barra"),
        ("RESOLUCION", config["res_idx"], "res"),
    ]
    y0 = 190
    for i, (nombre, valor, tipo) in enumerate(opciones):
        y = y0 + i * 90
        sel = (i == config_opcion)
        marca = "> " if sel else "  "
        color = BLANCO if sel else GRIS_MED
        etq = fuente.render(f"{marca}{nombre}", True, color)
        pantalla.blit(etq, (100, y))

        if tipo == "barra":
            barra_w = 300
            barra_x = ANCHO - barra_w - 100
            pygame.draw.rect(pantalla, GRIS, (barra_x, y + 4, barra_w, 16))
            relleno = int(barra_w * valor)
            pygame.draw.rect(pantalla, color, (barra_x, y + 4, relleno, 16))
            pygame.draw.rect(pantalla, BLANCO, (barra_x, y + 4, barra_w, 16), 1)
            pct = fuente_chica.render(f"{int(valor * 100)}%", True, color)
            pantalla.blit(pct, (barra_x + barra_w + 12, y + 4))
        else:
            w, h = RESOLUCIONES[valor]
            res_txt = fuente.render(f"{w}x{h}", True, color)
            pantalla.blit(res_txt, (ANCHO - 300, y))

    ayuda1 = fuente_chica.render("FLECHAS ARRIBA/ABAJO = ELEGIR", True, GRIS)
    pantalla.blit(ayuda1, (ANCHO // 2 - ayuda1.get_width() // 2, 480))
    ayuda2 = fuente_chica.render("FLECHAS IZQ/DER = AJUSTAR", True, GRIS)
    pantalla.blit(ayuda2, (ANCHO // 2 - ayuda2.get_width() // 2, 505))
    ayuda3 = fuente_chica.render("ESC PARA VOLVER", True, GRIS)
    pantalla.blit(ayuda3, (ANCHO // 2 - ayuda3.get_width() // 2, 540))

def aplicar_resolucion():
    global ventana
    w, h = RESOLUCIONES[config["res_idx"]]
    ventana = pygame.display.set_mode((w, h))

ESTADO         = "menu"
partida        = None
seed_acumulada = 0.0
cargando_seed  = False
teclas_sostenidas = set()
nombre_input   = ""
score_guardado = False

corriendo = True
while corriendo:
    pantalla.fill(NEGRO)
    ahora_ms = pygame.time.get_ticks()

    for evento in pygame.event.get():
        if evento.type == pygame.QUIT:
            corriendo = False

        if ESTADO == "menu":
            if evento.type == pygame.KEYDOWN:
                if evento.key == pygame.K_SPACE:
                    cargando_seed = True
                if evento.key == pygame.K_RETURN and seed_acumulada > 0:
                    dibujar_carga_seed(seed_acumulada)
                    partida = iniciar_partida(int(seed_acumulada))
                    score_guardado = False
                    ESTADO  = "jugando"
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

        elif ESTADO == "leaderboard":
            if evento.type == pygame.KEYDOWN:
                if evento.key == pygame.K_ESCAPE:
                    ESTADO = "menu"

        elif ESTADO == "config":
            if evento.type == pygame.KEYDOWN:
                if evento.key == pygame.K_ESCAPE:
                    ESTADO = "menu"
                elif evento.key == pygame.K_UP:
                    config_opcion = (config_opcion - 1) % 3
                elif evento.key == pygame.K_DOWN:
                    config_opcion = (config_opcion + 1) % 3
                elif evento.key == pygame.K_LEFT:
                    if config_opcion == 0:
                        config["brillo"] = max(0.3, round(config["brillo"] - 0.1, 1))
                    elif config_opcion == 1:
                        config["volumen"] = max(0.0, round(config["volumen"] - 0.1, 1))
                    elif config_opcion == 2:
                        config["res_idx"] = max(0, config["res_idx"] - 1)
                        aplicar_resolucion()
                elif evento.key == pygame.K_RIGHT:
                    if config_opcion == 0:
                        config["brillo"] = min(1.0, round(config["brillo"] + 0.1, 1))
                    elif config_opcion == 1:
                        config["volumen"] = min(1.0, round(config["volumen"] + 0.1, 1))
                    elif config_opcion == 2:
                        config["res_idx"] = min(len(RESOLUCIONES) - 1, config["res_idx"] + 1)
                        aplicar_resolucion()

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

        elif ESTADO == "jugando":
            if evento.type == pygame.KEYDOWN:
                if evento.key == pygame.K_ESCAPE:
                    pygame.mixer.stop()
                    teclas_sostenidas.clear()
                    if not score_guardado and partida["puntos"] > 0 and es_highscore(partida["puntos"]):
                        nombre_input = ""
                        ESTADO = "input_nombre"
                    else:
                        ESTADO = "menu"
                elif evento.key in COLUMNAS:
                    col = COLUMNAS[evento.key]
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
                                        if distancia < 30:
                                            pts = 5
                                            partida["combo"] += 1
                                            # potencia crece con el combo (1.0 a 2.5)
                                            pot = min(1.0 + partida["combo"] * 0.05, 2.5)
                                            partida["ultimo_hit"] = {"texto": "PERFECTO", "tiempo": ahora_ms}
                                            combo_particulas = min(100 + partida["combo"] * 8, 500)
                                            crear_explosion(cx, ZONA_Y, combo_particulas, potencia=pot)
                                            crear_onda(cx, ZONA_Y, 1.0)
                                            crear_onda(cx, ZONA_Y, 0.6, r0=int(4 + partida["combo"] * 0.5))
                                            if partida["combo"] >= 20:
                                                crear_onda(cx, ZONA_Y, 0.8, r0=int(20 + partida["combo"]))
                                            crear_flash(col, min(1.0, 0.7 + partida["combo"] * 0.02))
                                            crear_shake(min(8 + partida["combo"] * 0.3, 22))
                                        elif distancia < 60:
                                            pts = 3
                                            partida["combo"] += 1
                                            pot = min(1.0 + partida["combo"] * 0.035, 2.0)
                                            partida["ultimo_hit"] = {"texto": "BIEN", "tiempo": ahora_ms}
                                            crear_explosion(cx, ZONA_Y, min(60 + partida["combo"] * 4, 280), potencia=pot)
                                            crear_onda(cx, ZONA_Y, 0.7)
                                            crear_flash(col, 0.6)
                                            crear_shake(min(4 + partida["combo"] * 0.2, 14))
                                        elif distancia < 100:
                                            pts = 1
                                            partida["combo"] += 1
                                            partida["ultimo_hit"] = {"texto": "OK", "tiempo": ahora_ms}
                                            crear_explosion(cx, ZONA_Y, 20)
                                            crear_onda(cx, ZONA_Y, 0.4)
                                            crear_flash(col, 0.3)
                                        else:
                                            pts = 0
                                            partida["combo"] = 0
                                            partida["ultimo_hit"] = {"texto": "MAL", "tiempo": ahora_ms}
                                            crear_explosion(cx, ZONA_Y, 8, GRIS_MED)
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
                                                total_pts = pts * combo_mult
                                                partida["puntos"] += total_pts
                                                txt = f"+{total_pts}"
                                                if combo_mult > 1:
                                                    txt += f" x{combo_mult}"
                                                crear_texto_flotante(cx, ZONA_Y - 20, txt, BLANCO, combo_mult > 2)
                                        else:
                                            if pts > 0:
                                                total_pts = pts * len(grupo["cols"]) * combo_mult
                                                txt_pts = f"+{total_pts}"
                                                if combo_mult > 1:
                                                    txt_pts += f" x{combo_mult}"
                                                es_grande = combo_mult > 2
                                                crear_texto_flotante(cx, ZONA_Y - 20, txt_pts, BLANCO, es_grande)
                                                partida["puntos"] += total_pts
                                            else:
                                                partida["puntos"] = max(0, partida["puntos"] - 2)
                                                crear_texto_flotante(cx, ZONA_Y - 20, "-2", GRIS_MED)
                                            if partida["combo"] > 0 and partida["combo"] % 5 == 0:
                                                crear_texto_flotante(ANCHO // 2, ZONA_Y - 80, f"{partida['combo']}x COMBO!", BLANCO, True)
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
                            crear_texto_flotante(cx, ZONA_Y - 20, "-1", GRIS_MED)
                            crear_explosion(cx, ZONA_Y, 6, GRIS_MED)
                            crear_shake(3)
                            SND_ERROR.set_volume(0.35 * config["volumen"])
                            SND_ERROR.play()

            if evento.type == pygame.KEYUP:
                if evento.key in COLUMNAS:
                    col = COLUMNAS[evento.key]
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
                        crear_texto_flotante(cx, ZONA_Y - 40, "+5", BLANCO)
                        if grupo in partida["notas_cayendo"]:
                            partida["notas_cayendo"].remove(grupo)
                        del partida["holds_activos"][col]

    if ESTADO == "menu":
        if cargando_seed:
            seed_acumulada = min(seed_acumulada + SEED_VELOCIDAD, SEED_MAX)
        dibujar_menu(seed_acumulada, cargando_seed)

    elif ESTADO == "leaderboard":
        dibujar_leaderboard()

    elif ESTADO == "config":
        dibujar_config()

    elif ESTADO == "input_nombre":
        dibujar_input_nombre(nombre_input)

    elif ESTADO == "jugando":
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

            PIXELES_POR_MS = VELOCIDAD / (1000 / 60)
            ANTICIPACION   = (ZONA_Y + 40) / PIXELES_POR_MS

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
                        "hold_px":   hold_pixels(hold_ms, VELOCIDAD),
                    })
                    partida["indice_jugador"] += 1

            for grupo in partida["notas_cayendo"]:
                ms_hasta = grupo["tiempo_ms"] - ahora
                grupo["y"] = ZONA_Y - (ms_hasta * PIXELES_POR_MS)

            notas_vivas = []
            for n in partida["notas_cayendo"]:
                if n["y"] >= ALTO + 50:
                    es_hold_activo = any(c in partida["holds_activos"] for c in n["cols"])
                    if not es_hold_activo:
                        partida["ultimo_hit"] = {"texto": "MISS", "tiempo": ahora_ms}
                        partida["combo"] = 0
                        partida["puntos"] = max(0, partida["puntos"] - 5)
                        partida["vida"] = max(0, partida["vida"] - 2)
                        num_cols = partida["dificultad"]["columnas"]
                        ancho_col = ANCHO // num_cols
                        miss_x = n["cols"][0] * ancho_col + ancho_col // 2
                        crear_texto_flotante(miss_x, ALTO - 30, "-5", GRIS_MED)
                        crear_shake(4)
                        SND_ERROR.set_volume(0.3 * config["volumen"])
                        SND_ERROR.play()
                        if partida["vida"] <= 0:
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
