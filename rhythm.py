import os
os.add_dll_directory("F:\\VIDEOGAMEEE")
import fluidsynth
import pygame
import random
import musicpy as mp

pygame.init()

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

CH_ARPEGIO = 0
CH_BAJO    = 1
CH_PAD     = 2
CH_JUGADOR = 3
CH_BATERIA = 9

SUBGENEROS = {
    "MINIMAL": {
        "bpms": [128, 130, 132, 135],
        "acordes": [['Cm', 'Gm'], ['Am', 'Em'], ['Dm', 'Am'], ['Em', 'Bm']],
        "inst_arpegio": 81, "inst_bajo": 38, "inst_pad": 91, "inst_jugador": 81,
        "arpegio_vel": 60, "bajo_vel": 80, "pad_vel": 35,
        "arpegio_patron": "sparse",
    },
    "MELODICO": {
        "bpms": [122, 124, 126, 128],
        "acordes": [['Cm', 'Ab', 'Bb', 'Gm'], ['Am', 'F', 'G', 'Em'], ['Dm', 'Bb', 'C', 'Am']],
        "inst_arpegio": 80, "inst_bajo": 38, "inst_pad": 89, "inst_jugador": 80,
        "arpegio_vel": 70, "bajo_vel": 75, "pad_vel": 40,
        "arpegio_patron": "melodico",
    },
    "TECHHOUSE": {
        "bpms": [120, 122, 124, 126],
        "acordes": [['Cm7', 'Fm7'], ['Am7', 'Dm7'], ['Gm7', 'Cm7'], ['Dm7', 'Gm7']],
        "inst_arpegio": 4, "inst_bajo": 38, "inst_pad": 95, "inst_jugador": 4,
        "arpegio_vel": 65, "bajo_vel": 82, "pad_vel": 32,
        "arpegio_patron": "groovy",
    },
}

DIFICULTADES = {
    1: {"nombre": "FACIL",   "columnas": 3, "acordes": False},
    2: {"nombre": "FACIL",   "columnas": 3, "acordes": False},
    3: {"nombre": "NORMAL",  "columnas": 4, "acordes": False},
    4: {"nombre": "NORMAL",  "columnas": 4, "acordes": False},
    5: {"nombre": "DIFICIL", "columnas": 5, "acordes": True},
    6: {"nombre": "PRO",     "columnas": 6, "acordes": True},
    7: {"nombre": "GOD",     "columnas": 7, "acordes": True},
    8: {"nombre": "GOD",     "columnas": 7, "acordes": True},
    9: {"nombre": "GOD",     "columnas": 7, "acordes": True},
}

SEED_MAX       = 420
SEED_VELOCIDAD = 1.0
ZONA_Y         = ALTO - 90
VELOCIDAD      = 3

fuente_grande = pygame.font.SysFont("courier", 48, bold=True)
fuente        = pygame.font.SysFont("courier", 24, bold=True)
fuente_chica  = pygame.font.SysFont("courier", 14, bold=True)

SOUNDFONT = "F:\\VIDEOGAMEEE\\GeneralUser-GS.sf2"
fs   = fluidsynth.Synth()
fs.start(driver="dsound")
sfid = fs.sfload(SOUNDFONT)

notas_activas    = {}
notas_apagar     = []
teclas_sostenidas = set()

def set_instrumentos(sub):
    fs.program_select(CH_ARPEGIO, sfid, 0, sub["inst_arpegio"])
    fs.program_select(CH_BAJO,    sfid, 0, sub["inst_bajo"])
    fs.program_select(CH_PAD,     sfid, 0, sub["inst_pad"])
    fs.program_select(CH_JUGADOR, sfid, 0, sub["inst_jugador"])

def noteon(canal, nota, vel=90):
    if canal in notas_activas:
        fs.noteoff(canal, notas_activas[canal])
    fs.noteon(canal, nota, vel)
    notas_activas[canal] = nota

def noteoff(canal):
    if canal in notas_activas:
        fs.noteoff(canal, notas_activas[canal])
        del notas_activas[canal]

def get_dificultad(seed):
    if seed <= 0:
        return DIFICULTADES[1]
    tramos = [60, 120, 180, 240, 300, 360, 420]
    for i, tope in enumerate(tramos):
        if seed <= tope:
            return DIFICULTADES[i + 1]
    return DIFICULTADES[7]

def obtener_notas_acorde(nombre):
    c = mp.C(nombre)
    return [n.degree for n in c.notes]

def generar_patron_kick(rng):
    patrones = [
        [1,0,0,0,1,0,0,0,1,0,0,0,1,0,0,0],
        [1,0,0,0,1,0,0,0,1,0,0,1,1,0,0,0],
        [1,0,0,1,0,0,1,0,0,0,1,0,0,0,1,0],
        [1,0,0,0,1,0,1,0,1,0,0,0,1,0,0,0],
        [1,0,0,0,1,0,0,0,1,0,0,0,1,0,1,0],
        [1,0,1,0,0,0,1,0,1,0,0,0,1,0,0,0],
    ]
    return rng.choice(patrones)

def generar_patron_hihat(rng):
    patrones = [
        [1,0,1,0,1,0,1,0,1,0,1,0,1,0,1,0],
        [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],
        [1,0,1,1,1,0,1,1,1,0,1,1,1,0,1,1],
        [0,0,1,0,0,0,1,0,0,0,1,0,0,0,1,0],
        [1,0,1,0,1,0,1,1,1,0,1,0,1,0,1,1],
    ]
    return rng.choice(patrones)

def generar_patron_arpegio(rng, notas_acorde, tipo):
    if tipo == "sparse":
        patron = [0] * 16
        posiciones = rng.sample(range(16), rng.randint(3, 5))
        for p in posiciones:
            patron[p] = rng.choice(notas_acorde)
        return patron
    elif tipo == "melodico":
        patron = [0] * 16
        notas_ext = notas_acorde + [n + 12 for n in notas_acorde]
        for i in range(16):
            if i % 2 == 0:
                patron[i] = notas_ext[i % len(notas_ext)]
        return patron
    else:
        patron = [0] * 16
        base = rng.sample(notas_acorde, min(3, len(notas_acorde)))
        groove = [0,0,1,0,1,0,0,1,0,0,1,0,1,0,1,0]
        for i in range(16):
            if groove[i]:
                patron[i] = base[i % len(base)]
        return patron

def generar_bajo_techno(rng, raiz, beat, t_inicio, compases):
    bajo = []
    patrones = [
        [1,0,0,0,0,0,1,0,0,0,0,0,1,0,0,0],
        [1,0,0,0,1,0,0,0,1,0,0,0,1,0,0,0],
        [1,0,1,0,0,0,1,0,1,0,0,0,1,0,0,0],
        [1,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0],
    ]
    pat = rng.choice(patrones)
    paso_16 = beat // 4
    for c in range(compases):
        for i in range(16):
            if pat[i]:
                t    = t_inicio + (c * 16 + i) * paso_16
                nota = raiz if i < 8 else raiz + 7
                bajo.append({"midi": nota, "tiempo": t})
    return bajo

def generar_percusion(rng, beat, t_intro_fin, t_nudo_fin, t_desenlace_fin,
                      compases_intro, compases_nudo, compases_desenlace):
    paso_16 = beat // 4

    pat_kick   = generar_patron_kick(rng)
    pat_hihat  = generar_patron_hihat(rng)
    pat_clap   = [0,0,0,0,1,0,0,0,0,0,0,0,1,0,0,0]
    pat_shaker = [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1]
    pat_ride   = [0,0,1,0,0,0,1,0,0,0,1,0,0,0,1,0]

    pat_conga = [0] * 16
    for p in rng.sample(range(16), rng.randint(3, 6)):
        pat_conga[p] = 1

    pat_rim = [0] * 16
    for p in rng.sample(range(16), rng.randint(2, 4)):
        pat_rim[p] = 1

    pat_fill = [0,0,0,0,0,0,0,0,0,0,1,1,1,1,1,1]

    percusion = []
    total_compases = compases_intro + compases_nudo + compases_desenlace

    for c in range(total_compases):
        t_compas = c * 4 * beat
        if t_compas >= t_desenlace_fin:
            break
        es_fill = (c > 0) and (c % 4 == 3)

        for i in range(16):
            t = t_compas + i * paso_16

            if t < t_intro_fin:
                if pat_hihat[i]:
                    percusion.append({"tiempo": t, "midi": 42, "vel": 40})
                if pat_shaker[i] and i % 2 == 0:
                    percusion.append({"tiempo": t, "midi": 70, "vel": 25})
                continue

            if t >= t_nudo_fin:
                if pat_kick[i]:
                    percusion.append({"tiempo": t, "midi": 36, "vel": 95})
                if pat_clap[i]:
                    percusion.append({"tiempo": t, "midi": 39, "vel": 80})
                if pat_ride[i]:
                    percusion.append({"tiempo": t, "midi": 51, "vel": 55})
                continue

            if pat_kick[i]:
                percusion.append({"tiempo": t, "midi": 36, "vel": 100})
            if pat_clap[i]:
                percusion.append({"tiempo": t, "midi": 39, "vel": 85})
            if pat_hihat[i]:
                percusion.append({"tiempo": t, "midi": 42, "vel": 58})
            if i in [6, 14]:
                percusion.append({"tiempo": t, "midi": 46, "vel": 48})
            if pat_shaker[i]:
                percusion.append({"tiempo": t, "midi": 70, "vel": 30})
            if pat_ride[i]:
                percusion.append({"tiempo": t, "midi": 51, "vel": 45})
            if pat_conga[i]:
                percusion.append({"tiempo": t, "midi": 63, "vel": 60})
            if pat_rim[i]:
                percusion.append({"tiempo": t, "midi": 37, "vel": 50})
            if es_fill and pat_fill[i]:
                tom = rng.choice([47, 45, 43, 41])
                percusion.append({"tiempo": t, "midi": tom, "vel": 75})
            if i == 0 and c % 8 == 0 and t >= t_intro_fin:
                percusion.append({"tiempo": t, "midi": 49, "vel": 72})

    return sorted(percusion, key=lambda n: n["tiempo"])

def generar_cancion(seed, dif):
    num_columnas = dif["columnas"]
    usar_acordes = dif["acordes"]
    rng          = random.Random(seed)

    nombre_sub = rng.choice(list(SUBGENEROS.keys()))
    sub        = SUBGENEROS[nombre_sub]
    BPM        = rng.choice(sub["bpms"])
    beat       = 60000 // BPM
    subdiv     = beat // 2
    paso_16    = beat // 4

    nombres_prog = rng.choice(sub["acordes"])
    acordes_midi = [obtener_notas_acorde(nombre) for nombre in nombres_prog]
    raiz_bajo    = acordes_midi[0][0] - 12

    escala_jugador = sorted(set(
        [n for ac in acordes_midi for n in ac] +
        [n + 12 for ac in acordes_midi for n in ac]
    ))
    notas_columnas = escala_jugador[:num_columnas]

    COMPASES_INTRO     = 4
    COMPASES_NUDO      = 16
    COMPASES_DESENLACE = 4
    t_intro_fin     = COMPASES_INTRO * 4 * beat
    t_nudo_fin      = t_intro_fin + COMPASES_NUDO * 4 * beat
    t_desenlace_fin = t_nudo_fin + COMPASES_DESENLACE * 4 * beat

    patrones_arp = []
    for ac in acordes_midi:
        patrones_arp.append(generar_patron_arpegio(rng, ac, sub["arpegio_patron"]))

    arpegio = []
    for c in range(COMPASES_INTRO + COMPASES_NUDO + COMPASES_DESENLACE):
        t_compas = c * 4 * beat
        if t_compas >= t_desenlace_fin:
            break
        ac_idx  = c % len(patrones_arp)
        pat_arp = patrones_arp[ac_idx]
        for i in range(16):
            t = t_compas + i * paso_16
            if t >= t_desenlace_fin:
                break
            nota = pat_arp[i]
            if nota > 0:
                if t >= t_nudo_fin:
                    nota += 12
                arpegio.append({"midi": nota, "tiempo": t})

    bajo = generar_bajo_techno(rng, raiz_bajo, beat, t_intro_fin, COMPASES_NUDO)

    pad = []
    for i in range(COMPASES_NUDO // 4):
        t  = t_intro_fin + i * 4 * 4 * beat
        ac = acordes_midi[i % len(acordes_midi)]
        pad.append({"midis": ac, "tiempo": t})

    percusion = generar_percusion(rng, beat, t_intro_fin, t_nudo_fin, t_desenlace_fin,
                                  COMPASES_INTRO, COMPASES_NUDO, COMPASES_DESENLACE)

    notas_jugador = []
    cols_activas  = list(range(num_columnas))
    prob_acorde   = {5: 0.15, 6: 0.25, 7: 0.4}.get(num_columnas, 0)

    for c in range(COMPASES_INTRO):
        for b in range(4):
            if b % 2 == 0 and rng.random() < 0.5:
                col = rng.choice(cols_activas)
                notas_jugador.append({
                    "cols": [col], "midis": [notas_columnas[col]],
                    "tiempo": c * 4 * beat + b * beat,
                    "es_acorde": False, "parte": "intro", "hold": 0,
                })

    patrones_nudo = [
        [1,0,1,0,1,0,1,0],
        [1,0,0,1,0,1,0,0],
        [1,0,1,0,0,1,0,1],
        [1,1,0,0,1,0,0,1],
    ]
    for c in range(COMPASES_NUDO):
        pat = patrones_nudo[rng.randint(0, len(patrones_nudo) - 1)]
        for s in range(8):
            if pat[s] == 0:
                continue
            t        = t_intro_fin + (c * 8 + s) * subdiv
            es_hold  = rng.random() < 0.2
            hold_dur = rng.choice([2, 3, 4]) * subdiv if es_hold else 0

            if usar_acordes and s % 4 == 0 and rng.random() < prob_acorde:
                ac_idx  = c % len(acordes_midi)
                cols_ac = []
                for midi_n in acordes_midi[ac_idx][:3]:
                    col_ac = min(range(num_columnas), key=lambda x: abs(notas_columnas[x] - midi_n))
                    if col_ac not in cols_ac:
                        cols_ac.append(col_ac)
                if len(cols_ac) >= 2:
                    notas_jugador.append({
                        "cols": cols_ac,
                        "midis": [notas_columnas[cx] for cx in cols_ac],
                        "tiempo": t, "es_acorde": True, "parte": "nudo", "hold": 0,
                    })
                    continue

            col = rng.choice(cols_activas)
            notas_jugador.append({
                "cols": [col], "midis": [notas_columnas[col]],
                "tiempo": t, "es_acorde": False, "parte": "nudo", "hold": hold_dur,
            })

    pat_final = [1,0,0,1,1,0,1,0]
    for c in range(COMPASES_DESENLACE):
        for s in range(8):
            if pat_final[s] == 0:
                continue
            t        = t_nudo_fin + (c * 8 + s) * subdiv
            col      = rng.choice(cols_activas)
            midi     = notas_columnas[col] + 12
            es_hold  = rng.random() < 0.35
            hold_dur = rng.choice([3, 4, 5, 6]) * subdiv if es_hold else 0
            notas_jugador.append({
                "cols": [col], "midis": [midi],
                "tiempo": t, "es_acorde": False, "parte": "desenlace", "hold": hold_dur,
            })

    tiempos_jugador = set(n["tiempo"] for n in notas_jugador)
    arpegio = [a for a in arpegio if a["tiempo"] not in tiempos_jugador]

    return {
        "bpm":            BPM,
        "beat":           beat,
        "subdiv":         subdiv,
        "subgenero":      nombre_sub,
        "subgenero_data": sub,
        "progresion":     " ".join(nombres_prog),
        "duracion_loop":  t_desenlace_fin,
        "notas_jugador":  sorted(notas_jugador, key=lambda n: n["tiempo"]),
        "arpegio":        sorted(arpegio, key=lambda n: n["tiempo"]),
        "bajo":           bajo,
        "pad":            pad,
        "percusion":      percusion,
        "notas_columnas": notas_columnas,
        "estructura": {
            "intro_fin":     t_intro_fin,
            "nudo_fin":      t_nudo_fin,
            "desenlace_fin": t_desenlace_fin,
        }
    }

def iniciar_partida(seed):
    dif     = get_dificultad(seed)
    cancion = generar_cancion(int(seed * 23819), dif)
    set_instrumentos(cancion["subgenero_data"])
    return {
        "seed":           seed,
        "dificultad":     dif,
        "cancion":        cancion,
        "indice_jugador": 0,
        "indice_arp":     0,
        "indice_bajo":    0,
        "indice_pad":     0,
        "indice_perc":    0,
        "inicio":         pygame.time.get_ticks(),
        "loop_offset":    0,
        "notas_cayendo":  [],
        "puntos":         0,
        "terminada":      False,
        "pad_apagado":    False,
        "todo_apagado":   False,
        "holds_activos":  {},
    }

def tick_background(partida, ahora):
    c = partida["cancion"]
    t = ahora - partida["loop_offset"]
    ahora_real = pygame.time.get_ticks()
    beat = c["beat"]

    if t >= c["duracion_loop"] and not partida["terminada"]:
        partida["terminada"] = True

    pendientes = []
    for fin, canal, midi in notas_apagar:
        if ahora_real >= fin:
            fs.noteoff(canal, midi)
        else:
            pendientes.append((fin, canal, midi))
    notas_apagar.clear()
    notas_apagar.extend(pendientes)

    while partida["indice_arp"] < len(c["arpegio"]) and t >= c["arpegio"][partida["indice_arp"]]["tiempo"]:
        midi = c["arpegio"][partida["indice_arp"]]["midi"]
        fs.noteoff(CH_ARPEGIO, midi)
        fs.noteon(CH_ARPEGIO, midi, c["subgenero_data"]["arpegio_vel"])
        notas_apagar.append((ahora_real + beat // 3, CH_ARPEGIO, midi))
        partida["indice_arp"] += 1

    while partida["indice_bajo"] < len(c["bajo"]) and t >= c["bajo"][partida["indice_bajo"]]["tiempo"]:
        midi = c["bajo"][partida["indice_bajo"]]["midi"]
        fs.noteoff(CH_BAJO, midi)
        fs.noteon(CH_BAJO, midi, c["subgenero_data"]["bajo_vel"])
        notas_apagar.append((ahora_real + beat // 2, CH_BAJO, midi))
        partida["indice_bajo"] += 1

    while partida["indice_pad"] < len(c["pad"]) and t >= c["pad"][partida["indice_pad"]]["tiempo"]:
        for m in range(128):
            fs.noteoff(CH_PAD, m)
        for m in c["pad"][partida["indice_pad"]]["midis"]:
            fs.noteon(CH_PAD, m, c["subgenero_data"]["pad_vel"])
            notas_apagar.append((ahora_real + beat * 8, CH_PAD, m))
        partida["indice_pad"] += 1

    if t >= c["estructura"]["nudo_fin"] and not partida["pad_apagado"]:
        for m in range(128):
            fs.noteoff(CH_PAD, m)
        partida["pad_apagado"] = True

    while partida["indice_perc"] < len(c["percusion"]) and t >= c["percusion"][partida["indice_perc"]]["tiempo"]:
        p = c["percusion"][partida["indice_perc"]]
        fs.noteon(CH_BATERIA, p["midi"], p["vel"])
        partida["indice_perc"] += 1

    if partida["terminada"] and not partida["todo_apagado"]:
        for ch in [CH_ARPEGIO, CH_BAJO, CH_PAD]:
            for m in range(128):
                fs.noteoff(ch, m)
        notas_apagar.clear()
        partida["todo_apagado"] = True

def hold_pixels(hold_ms, velocidad_px_frame, fps=60):
    if hold_ms <= 0:
        return 0
    frames = hold_ms / (1000 / fps)
    return int(frames * velocidad_px_frame)

def get_parte(partida, ahora):
    e = partida["cancion"]["estructura"]
    t = ahora - partida["loop_offset"]
    if t < e["intro_fin"]:       return "INTRO"
    elif t < e["nudo_fin"]:      return "NUDO"
    elif t < e["desenlace_fin"]: return "FIN"
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
        xs = []
        hold_h = grupo.get("hold_px", 0)

        for col in pendientes:
            x = col * ancho_col

            if hold_h > 0:
                bar_x = x + ancho_col // 2 - 6
                bar_y = grupo["y"] - hold_h
                bar_h = hold_h
                if col in partida["holds_activos"]:
                    pygame.draw.rect(pantalla, BLANCO, (bar_x, bar_y, 12, bar_h))
                else:
                    pygame.draw.rect(pantalla, GRIS_MED, (bar_x, bar_y, 12, bar_h))
                    pygame.draw.rect(pantalla, BLANCO, (bar_x, bar_y, 12, bar_h), 1)

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

    dif_txt = fuente_chica.render(partida["dificultad"]["nombre"], True, GRIS_MED)
    pantalla.blit(dif_txt, (10, 10))
    parte_txt = fuente_chica.render(parte, True, GRIS)
    pantalla.blit(parte_txt, (10, 28))
    sub_txt = fuente_chica.render(partida["cancion"]["subgenero"], True, GRIS)
    pantalla.blit(sub_txt, (10, 46))

    prog_txt = fuente_chica.render(partida["cancion"]["progresion"], True, GRIS)
    pantalla.blit(prog_txt, (ANCHO - prog_txt.get_width() - 10, 28))
    info = fuente_chica.render(f"{partida['cancion']['bpm']}BPM", True, GRIS)
    pantalla.blit(info, (ANCHO - info.get_width() - 10, 10))

    esc_txt = fuente_chica.render("ESC", True, GRIS)
    pantalla.blit(esc_txt, (10, ALTO - 20))

    if partida["terminada"] and not partida["notas_cayendo"]:
        fin = fuente.render("FIN  -  ESC PARA VOLVER", True, BLANCO)
        pantalla.blit(fin, (ANCHO // 2 - fin.get_width() // 2, ALTO // 2))

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

ESTADO         = "menu"
partida        = None
seed_acumulada = 0.0
cargando_seed  = False

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
                    ESTADO  = "jugando"
                if evento.key == pygame.K_r:
                    seed_acumulada = 0.0
                    cargando_seed  = False
            if evento.type == pygame.KEYUP:
                if evento.key == pygame.K_SPACE:
                    cargando_seed = False

        elif ESTADO == "jugando":
            if evento.type == pygame.KEYDOWN:
                if evento.key == pygame.K_ESCAPE:
                    for ch in [CH_ARPEGIO, CH_BAJO, CH_PAD, CH_JUGADOR]:
                        for m in range(128):
                            fs.noteoff(ch, m)
                    notas_apagar.clear()
                    notas_activas.clear()
                    teclas_sostenidas.clear()
                    ESTADO = "menu"
                elif evento.key in COLUMNAS:
                    col = COLUMNAS[evento.key]
                    if col < partida["dificultad"]["columnas"]:
                        teclas_sostenidas.add(col)
                        midi_fijo = partida["cancion"]["notas_columnas"][col]
                        fs.noteon(CH_JUGADOR, midi_fijo, 127)

                        for grupo in partida["notas_cayendo"]:
                            if col in grupo["cols"] and ZONA_Y - 40 < grupo["y"] < ZONA_Y + 60:
                                if "acertadas" not in grupo:
                                    grupo["acertadas"] = set()
                                if col not in grupo["acertadas"]:
                                    grupo["acertadas"].add(col)
                                    if grupo.get("hold", 0) > 0 and not grupo.get("es_acorde"):
                                        partida["holds_activos"][col] = {
                                            "grupo": grupo,
                                            "midi":  midi_fijo,
                                        }
                                    else:
                                        notas_apagar.append((ahora_ms + partida["cancion"]["beat"] // 3, CH_JUGADOR, midi_fijo))
                                        if grupo["acertadas"] == set(grupo["cols"]):
                                            partida["puntos"] += len(grupo["cols"])
                                            partida["notas_cayendo"].remove(grupo)
                                break

            if evento.type == pygame.KEYUP:
                if evento.key in COLUMNAS:
                    col = COLUMNAS[evento.key]
                    teclas_sostenidas.discard(col)
                    if col in partida.get("holds_activos", {}):
                        hold = partida["holds_activos"][col]
                        fs.noteoff(CH_JUGADOR, hold["midi"])
                        grupo = hold["grupo"]
                        if grupo["y"] > ZONA_Y + 20:
                            partida["puntos"] += 3
                            if grupo in partida["notas_cayendo"]:
                                partida["notas_cayendo"].remove(grupo)
                        del partida["holds_activos"][col]

    if ESTADO == "menu":
        if cargando_seed:
            seed_acumulada = min(seed_acumulada + SEED_VELOCIDAD, SEED_MAX)
        dibujar_menu(seed_acumulada, cargando_seed)

    elif ESTADO == "jugando":
        ahora = ahora_ms - partida["inicio"]
        tick_background(partida, ahora)

        holds_perdidos = []
        for col, hold in partida["holds_activos"].items():
            if hold["grupo"]["y"] > ALTO:
                fs.noteoff(CH_JUGADOR, hold["midi"])
                holds_perdidos.append(col)
        for col in holds_perdidos:
            del partida["holds_activos"][col]

        if not partida["terminada"]:
            while partida["indice_jugador"] < len(partida["cancion"]["notas_jugador"]) and ahora >= partida["cancion"]["notas_jugador"][partida["indice_jugador"]]["tiempo"]:
                n = partida["cancion"]["notas_jugador"][partida["indice_jugador"]]
                hold_ms = n.get("hold", 0)
                partida["notas_cayendo"].append({
                    "cols":      n["cols"],
                    "midis":     n["midis"],
                    "y":         -40,
                    "acertadas": set(),
                    "es_acorde": n.get("es_acorde", False),
                    "hold":      hold_ms,
                    "hold_px":   hold_pixels(hold_ms, VELOCIDAD),
                })
                partida["indice_jugador"] += 1

        for grupo in partida["notas_cayendo"]:
            grupo["y"] += VELOCIDAD

        partida["notas_cayendo"] = [n for n in partida["notas_cayendo"] if n["y"] < ALTO + 50]

        dibujar_juego(partida, ahora)

    pygame.display.flip()
    clock.tick(60)

fs.delete()
pygame.quit()
