import os
os.add_dll_directory("F:\\VIDEOGAMEEE")
import fluidsynth
import pygame
import random
import glob
import numpy as np
import json

pygame.init()
pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
pygame.mixer.set_num_channels(32)

ANCHO, ALTO = 720, 640
pantalla = pygame.display.set_mode((ANCHO, ALTO))
pygame.display.set_caption("Rhythm Game")
clock = pygame.time.Clock()

NEGRO    = (0,   0,   0)
BLANCO   = (255, 255, 255)
GRIS     = (80,  80,  80)
GRIS_MED = (140, 140, 140)

COLUMNAS = {
    pygame.K_a: 0,
    pygame.K_s: 1,
    pygame.K_d: 2,
    pygame.K_f: 3,
    pygame.K_j: 4,
    pygame.K_k: 5,
    pygame.K_l: 6,
    pygame.K_SEMICOLON: 7,
    pygame.K_PERIOD: 7,
}

LABELS = ["A", "S", "D", "F", "J", "K", "L", "N"]

ESCALAS = {
    "mayor":       [0, 2, 4, 5, 7, 9, 11, 12],
    "menor":       [0, 2, 3, 5, 7, 8, 10, 12],
    "pentatonica": [0, 2, 4, 7, 9, 12, 14, 16],
}

ACORDES_PATRON = {
    "mayor":       [[0, 2, 4], [1, 3, 5], [2, 4, 6], [4, 6, 7]],
    "menor":       [[0, 2, 4], [1, 3, 5], [2, 4, 6], [0, 3, 5]],
    "pentatonica": [[0, 2, 4], [1, 3, 5], [2, 4, 6], [3, 5, 7]],
    "blues":       [[0, 2, 4], [0, 3, 5], [1, 3, 6], [2, 4, 7]],
}

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

SAMPLES_PATH = "F:\\VIDEOGAMEEE\\elementos\\MPC60vsVB_Maschine\\MPC60vsVB_Maschine\\MPCVB Fat Samples\\"

def cargar_samples(prefijo):
    archivos = sorted(glob.glob(SAMPLES_PATH + prefijo + "*.wav"))
    return [pygame.mixer.Sound(a) for a in archivos]

print("Cargando samples...")
kicks    = cargar_samples("BD MPCVB Fat")
snares   = cargar_samples("SD MPCVB Fat")
hihats   = cargar_samples("HH MPCVB Fat")
hihats_o = cargar_samples("HHo MPCVB Fat")
claps    = cargar_samples("Clap MPCVB Fat")
claves   = cargar_samples("Clave MPCVB Fat")
crashes  = cargar_samples("Crash MPCVB Fat")
agogos   = cargar_samples("Agogo MPCVB Fat")
toms     = cargar_samples("Tom MPCVB Fat")
print(f"OK: {len(kicks)}k {len(snares)}s {len(hihats)}h {len(claps)}c {len(toms)}t")

print("Renderizando notas...")
SOUNDFONT = "F:\\VIDEOGAMEEE\\8bitsf.SF2"
fs = fluidsynth.Synth(samplerate=44100.0)
sfid = fs.sfload(SOUNDFONT)
INSTRUMENTOS_JUGADOR = {
    "E.PIANO":   4,
    "MARIMBA":   12,
    "ORGAN":     16,
    "SYNTH":     80,
    "SAW":       81,
    "CALLIOPE":  82,
    "STRINGS":   48,
    "BRASS":     62,
}

SR = 44100
cache_por_instrumento = {}
cache_largas_por_instrumento = {}

def renderizar_nota(midi, duracion_seg):
    fs.noteon(0, midi, 100)
    total = int(SR * duracion_seg)
    buf = np.zeros(total * 2, dtype=np.int16)
    pos = 0
    while pos < total * 2:
        chunk = min(512, (total * 2 - pos) // 2)
        if chunk <= 0:
            break
        raw = fs.get_samples(chunk)
        arr = np.frombuffer(raw, dtype=np.int16)
        end = min(pos + len(arr), total * 2)
        buf[pos:end] = arr[:end - pos]
        pos = end
    fs.noteoff(0, midi)
    fs.get_samples(2048)
    stereo = buf.reshape(-1, 2)
    return pygame.sndarray.make_sound(stereo)

for nombre, prog in INSTRUMENTOS_JUGADOR.items():
    print(f"  {nombre}...")
    fs.program_select(0, sfid, 0, prog)
    c_cortas = {}
    c_largas = {}
    for midi in range(36, 96):
        c_cortas[midi] = renderizar_nota(midi, 0.3)
        c_largas[midi] = renderizar_nota(midi, 2.0)
    cache_por_instrumento[nombre] = c_cortas
    cache_largas_por_instrumento[nombre] = c_largas

cache_notas = cache_por_instrumento["E.PIANO"]
cache_notas_largas = cache_largas_por_instrumento["E.PIANO"]

fs.delete()
print("Notas OK")

canal_hold = {}
particulas = []
textos_flotantes = []

def crear_explosion(x, y, cantidad, color=BLANCO):
    for _ in range(cantidad):
        angulo = random.uniform(0, 6.28)
        fuerza = random.uniform(1, 7)
        import math
        dx = math.cos(angulo) * fuerza
        dy = math.sin(angulo) * fuerza - 3
        vida = random.randint(20, 50)
        tam = random.randint(2, 7)
        particulas.append({"x": x, "y": y, "dx": dx, "dy": dy, "vida": vida, "vida_max": vida, "tam": tam, "color": color})

def crear_texto_flotante(x, y, texto, color=BLANCO, grande=False):
    textos_flotantes.append({
        "x": x, "y": y, "texto": texto, "color": color,
        "vida": 60, "vida_max": 60, "grande": grande,
    })

def actualizar_particulas():
    for p in particulas:
        p["x"] += p["dx"]
        p["y"] += p["dy"]
        p["dy"] += 0.15
        p["dx"] *= 0.98
        p["vida"] -= 1
    particulas[:] = [p for p in particulas if p["vida"] > 0]
    for t in textos_flotantes:
        t["y"] -= 1.5
        t["vida"] -= 1
    textos_flotantes[:] = [t for t in textos_flotantes if t["vida"] > 0]

def dibujar_particulas():
    for p in particulas:
        pct = p["vida"] / p["vida_max"]
        alpha = int(255 * pct)
        color = (min(p["color"][0], alpha), min(p["color"][1], alpha), min(p["color"][2], alpha))
        tam = max(1, int(p["tam"] * pct))
        pygame.draw.rect(pantalla, color, (int(p["x"]), int(p["y"]), tam, tam))
    for t in textos_flotantes:
        pct = t["vida"] / t["vida_max"]
        alpha = int(255 * pct)
        color = (min(t["color"][0], alpha), min(t["color"][1], alpha), min(t["color"][2], alpha))
        f = fuente if t["grande"] else fuente_chica
        txt = f.render(t["texto"], True, color)
        pantalla.blit(txt, (int(t["x"]) - txt.get_width() // 2, int(t["y"])))
def nota_midi(tonica, escala, grado):
    return tonica + escala[grado % len(escala)]

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
    kit = {}
    kit["kick"]    = rng.choice(kicks)   if kicks    else None
    kit["snare"]   = rng.choice(snares)  if snares   else None
    kit["hihat"]   = rng.choice(hihats)  if hihats   else None
    kit["hihat_o"] = rng.choice(hihats_o) if hihats_o else None
    kit["clap"]    = rng.choice(claps)   if claps    else None
    kit["clave"]   = rng.choice(claves)  if claves   else None
    kit["crash"]   = rng.choice(crashes) if crashes  else None
    kit["agogo"]   = rng.choice(agogos)  if agogos   else None
    kit["tom1"]    = rng.choice(toms)    if toms     else None
    kit["tom2"]    = rng.choice(toms)    if toms     else None
    return kit

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
    percusion = []
    total = c_intro + c_nudo + c_desenlace
    for c in range(total):
        tc = c * 4 * beat
        if tc >= t_desenlace_fin:
            break
        es_fill = (c > 0) and (c % 4 == 3)
        if tc < tercio1:
            p = pats
        elif tc < tercio2:
            p = pats2
        else:
            p = pats3
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
    patron_acordes = ACORDES_PATRON[nombre_escala]
    progresion   = [rng.randint(0, 3) for _ in range(8)]

    notas_columnas = [nota_midi(tonica + 12, escala, i) for i in range(num_columnas)]
    kit = elegir_kit(rng)
    instrumento = rng.choice(list(INSTRUMENTOS_JUGADOR.keys()))

    C_INTRO     = 4
    C_NUDO      = 24
    C_DESENLACE = 4
    t_intro_fin     = C_INTRO * 4 * beat
    t_nudo_fin      = t_intro_fin + C_NUDO * 4 * beat
    t_desenlace_fin = t_nudo_fin + C_DESENLACE * 4 * beat

    prob_acorde = {3: 0.2, 4: 0.3, 5: 0.4, 6: 0.5, 7: 0.6}.get(num_columnas, 0.2)

    frases_subir = [
        [0, 1, 2, 2],
        [0, 0, 1, 2],
        [0, 2, 1, 2],
        [1, 2, 2, 1],
        [0, 1, 0, 2],
        [0, 1, 2, 0],
        [0, 0, 2, 1],
    ]
    frases_bajar = [
        [2, 1, 0, 0],
        [2, 2, 1, 0],
        [2, 0, 1, 0],
        [1, 0, 0, 1],
        [2, 1, 2, 0],
        [2, 0, 2, 0],
        [2, 1, 0, 2],
    ]
    frases_medio = [
        [1, 0, 2, 1],
        [1, 2, 0, 1],
        [0, 2, 0, 2],
        [2, 0, 1, 0],
        [1, 1, 0, 2],
        [0, 2, 1, 0],
        [1, 0, 1, 2],
    ]

    def escalar_frase(frase):
        if num_columnas <= 3:
            return [min(g, num_columnas - 1) for g in frase]
        bajo  = rng.randint(0, num_columnas // 3)
        medio = num_columnas // 2
        alto  = rng.randint(num_columnas * 2 // 3, num_columnas - 1)
        mapa = {0: bajo, 1: medio, 2: alto}
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
                    if dur >= 2 * (beat // 4):
                        compas[pos]["hold"] = dur - beat // 4
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

    pat_des = [1,0,0,0,0,0,0,0,0,0,0,0,1,0,0,0]
    for c in range(C_DESENLACE):
        for s in range(16):
            if pat_des[s] == 0:
                continue
            t        = t_nudo_fin + c * 4 * beat + (s // 4) * beat
            progreso = (c * 16 + s) / (C_DESENLACE * 16)
            col      = min(int(progreso * num_columnas), num_columnas - 1)
            midi     = notas_columnas[col] + 12
            es_hold  = rng.random() < 0.7
            hold_dur = rng.choice([8, 10, 12]) * paso16 if es_hold else 0
            notas_jugador.append({
                "cols": [col], "midis": [midi],
                "tiempo": t, "es_acorde": False, "parte": "desenlace", "hold": hold_dur,
            })

    percusion = generar_percusion(rng, beat, t_intro_fin, t_nudo_fin, t_desenlace_fin,
                                  C_INTRO, C_NUDO, C_DESENLACE, kit)

    return {
        "bpm":            BPM,
        "beat":           beat,
        "paso16":         paso16,
        "escala":         nombre_escala,
        "duracion_loop":  t_desenlace_fin,
        "notas_jugador":  sorted(notas_jugador, key=lambda n: n["tiempo"]),
        "percusion":      percusion,
        "kit":            kit,
        "instrumento":    instrumento,
        "notas_columnas": notas_columnas,
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
    cache_notas = cache_por_instrumento[cancion["instrumento"]]
    cache_notas_largas = cache_largas_por_instrumento[cancion["instrumento"]]
    return {
        "seed":           seed,
        "dificultad":     dif,
        "cancion":        cancion,
        "indice_jugador": 0,
        "indice_perc":    0,
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
    }

def tick_background(partida, ahora):
    c = partida["cancion"]
    kit = c["kit"]

    if ahora >= c["duracion_loop"] and not partida["terminada"]:
        partida["terminada"] = True

    while partida["indice_perc"] < len(c["percusion"]) and ahora >= c["percusion"][partida["indice_perc"]]["tiempo"]:
        p = c["percusion"][partida["indice_perc"]]
        sample = kit.get(p["sample"])
        if sample:
            sample.set_volume(p["vol"])
            sample.play()
        partida["indice_perc"] += 1

def get_parte(partida, ahora):
    e = partida["cancion"]["estructura"]
    if ahora < e["intro_fin"]:       return "INTRO"
    elif ahora < e["nudo_fin"]:      return "NUDO"
    elif ahora < e["desenlace_fin"]: return "FIN"
    return "FIN"

def dibujar_juego(partida, ahora):
    num_cols  = partida["dificultad"]["columnas"]
    ancho_col = ANCHO // num_cols
    parte     = get_parte(partida, ahora)

    for i in range(1, num_cols):
        pygame.draw.line(pantalla, GRIS, (i * ancho_col, 0), (i * ancho_col, ALTO), 1)

    pygame.draw.line(pantalla, BLANCO, (0, ZONA_Y), (ANCHO, ZONA_Y), 2)
    pygame.draw.line(pantalla, BLANCO, (0, ZONA_Y + 54), (ANCHO, ZONA_Y + 54), 1)

    for i in range(num_cols):
        x     = i * ancho_col
        label = fuente_chica.render(LABELS[i], True, GRIS_MED)
        pantalla.blit(label, (x + ancho_col // 2 - label.get_width() // 2, ZONA_Y + 18))

    for grupo in partida["notas_cayendo"]:
        pendientes = [c for c in grupo["cols"] if c not in grupo.get("acertadas", set())]
        cols_hold_activo = [c for c in grupo["cols"] if c in partida["holds_activos"]]
        cols_a_dibujar = list(set(pendientes + cols_hold_activo))
        xs = []
        hold_h = grupo.get("hold_px", 0)
        for col in cols_a_dibujar:
            x = col * ancho_col
            if hold_h > 0:
                bar_x = x + ancho_col // 2 - 6
                bar_y = grupo["y"] - hold_h
                bar_h = hold_h
                if col in partida["holds_activos"]:
                    pygame.draw.rect(pantalla, GRIS_MED, (bar_x - 4, bar_y, 20, bar_h))
                    pygame.draw.rect(pantalla, BLANCO, (bar_x, bar_y, 12, bar_h))
                else:
                    pygame.draw.rect(pantalla, GRIS_MED, (bar_x, bar_y, 12, bar_h))
                    pygame.draw.rect(pantalla, BLANCO, (bar_x, bar_y, 12, bar_h), 1)
            if col in pendientes:
                if grupo.get("es_acorde"):
                    pygame.draw.rect(pantalla, BLANCO, (x + 6,  grupo["y"],     ancho_col - 12, 28))
                    pygame.draw.rect(pantalla, NEGRO,  (x + 9,  grupo["y"] + 3, ancho_col - 18, 22))
                    pygame.draw.rect(pantalla, BLANCO, (x + 11, grupo["y"] + 5, ancho_col - 22, 18))
                else:
                    pygame.draw.rect(pantalla, BLANCO, (x + 6, grupo["y"], ancho_col - 12, 28))
            xs.append(x + ancho_col // 2)
        if len(xs) > 1:
            pygame.draw.line(pantalla, BLANCO, (xs[0], grupo["y"] + 14), (xs[-1], grupo["y"] + 14), 2)

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

    lb_txt = fuente_chica.render("L = LEADERBOARD", True, GRIS)
    pantalla.blit(lb_txt, (ANCHO // 2 - lb_txt.get_width() // 2, 510))

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
                    partida = iniciar_partida(int(seed_acumulada))
                    score_guardado = False
                    ESTADO  = "jugando"
                if evento.key == pygame.K_r:
                    seed_acumulada = 0.0
                    cargando_seed  = False
                if evento.key == pygame.K_l:
                    ESTADO = "leaderboard"
            if evento.type == pygame.KEYUP:
                if evento.key == pygame.K_SPACE:
                    cargando_seed = False

        elif ESTADO == "leaderboard":
            if evento.type == pygame.KEYDOWN:
                if evento.key == pygame.K_ESCAPE:
                    ESTADO = "menu"

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

                        if midi_fijo in cache_notas:
                            cache_notas[midi_fijo].play()

                        for grupo in partida["notas_cayendo"]:
                            if col in grupo["cols"]:
                                distancia = abs(grupo["tiempo_ms"] - (ahora_ms - partida["inicio"]))
                                if distancia < 150:
                                    if "acertadas" not in grupo:
                                        grupo["acertadas"] = set()
                                    if col not in grupo["acertadas"]:
                                        grupo["acertadas"].add(col)
                                        num_cols = partida["dificultad"]["columnas"]
                                        ancho_col = ANCHO // num_cols
                                        cx = col * ancho_col + ancho_col // 2
                                        if distancia < 30:
                                            pts = 3
                                            partida["combo"] += 1
                                            partida["ultimo_hit"] = {"texto": "PERFECTO", "tiempo": ahora_ms}
                                            crear_explosion(cx, ZONA_Y, 60)
                                        elif distancia < 60:
                                            pts = 2
                                            partida["combo"] += 1
                                            partida["ultimo_hit"] = {"texto": "BIEN", "tiempo": ahora_ms}
                                            crear_explosion(cx, ZONA_Y, 35)
                                        elif distancia < 100:
                                            pts = 1
                                            partida["combo"] += 1
                                            partida["ultimo_hit"] = {"texto": "OK", "tiempo": ahora_ms}
                                            crear_explosion(cx, ZONA_Y, 8)
                                        else:
                                            pts = 0
                                            partida["combo"] = 0
                                            partida["ultimo_hit"] = {"texto": "MAL", "tiempo": ahora_ms}
                                            crear_explosion(cx, ZONA_Y, 5, GRIS_MED)
                                            partida["puntos"] = max(0, partida["puntos"] - 2)
                                            partida["vida"] = max(0, partida["vida"] - 1)
                                            crear_texto_flotante(cx, ZONA_Y - 20, "-2", GRIS_MED)
                                        if partida["combo"] > partida["max_combo"]:
                                            partida["max_combo"] = partida["combo"]
                                        combo_mult = 1 + partida["combo"] // 10
                                        if grupo.get("hold", 0) > 0 and not grupo.get("es_acorde"):
                                            if midi_fijo in cache_notas_largas:
                                                ch = cache_notas_largas[midi_fijo].play()
                                                if ch:
                                                    canal_hold[col] = ch
                                            partida["holds_activos"][col] = {
                                                "grupo": grupo,
                                                "midi":  midi_fijo,
                                            }
                                        else:
                                            if pts > 0:
                                                total_pts = pts * len(grupo["cols"]) * combo_mult
                                                txt_pts = f"+{total_pts}"
                                                if combo_mult > 1:
                                                    txt_pts += f" x{combo_mult}"
                                                crear_texto_flotante(cx, ZONA_Y - 20, txt_pts, BLANCO, combo_mult > 1)
                                                if partida["combo"] > 0 and partida["combo"] % 10 == 0:
                                                    crear_texto_flotante(ANCHO // 2, ZONA_Y - 80, f"{partida['combo']}x COMBO!", BLANCO, True)
                                            partida["puntos"] += pts * len(grupo["cols"]) * combo_mult
                                            if grupo["acertadas"] == set(grupo["cols"]):
                                                partida["notas_cayendo"].remove(grupo)
                                    break

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
                        if grupo["y"] > ZONA_Y + 20:
                            partida["puntos"] += 3
                            num_cols = partida["dificultad"]["columnas"]
                            ancho_col = ANCHO // num_cols
                            cx = col * ancho_col + ancho_col // 2
                            crear_texto_flotante(cx, ZONA_Y - 40, "+3", BLANCO)
                        if grupo in partida["notas_cayendo"]:
                            partida["notas_cayendo"].remove(grupo)
                        del partida["holds_activos"][col]

    if ESTADO == "menu":
        if cargando_seed:
            seed_acumulada = min(seed_acumulada + SEED_VELOCIDAD, SEED_MAX)
        dibujar_menu(seed_acumulada, cargando_seed)

    elif ESTADO == "leaderboard":
        dibujar_leaderboard()

    elif ESTADO == "input_nombre":
        dibujar_input_nombre(nombre_input)

    elif ESTADO == "jugando":
        ahora = ahora_ms - partida["inicio"]

        if not partida.get("game_over"):
            tick_background(partida, ahora)

        if not partida.get("game_over"):
            holds_perdidos = []
            for col, hold in partida["holds_activos"].items():
                if hold["grupo"]["y"] > ALTO:
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
                        if partida["vida"] <= 0:
                            partida["game_over"] = True
                            pygame.mixer.stop()
                    else:
                        notas_vivas.append(n)
                else:
                    notas_vivas.append(n)
            partida["notas_cayendo"] = notas_vivas

        actualizar_particulas()
        dibujar_juego(partida, ahora)
        dibujar_particulas()

    pygame.display.flip()
    clock.tick(60)

pygame.quit()
