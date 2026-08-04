# Medidor de nivel en vivo para diagnosticar el teclado musical (line-in).
# Abre TODAS las entradas de audio a la vez y muestra una barra por dispositivo.
# Toca el teclado y fijate cual barra se mueve: ese es el dispositivo que
# tenes que elegir en CONFIG > TECLADO MUSICAL. Ctrl+C para salir.
#
# Uso:  python test_linein.py

import sounddevice as sd
import numpy as np
import time

SR = 22050        # mismos parametros que el juego
BLOCK = 512
UMBRAL_JUEGO = 0.035   # LINEIN_THRESHOLD_ON: el nivel que el juego necesita

# solo dispositivos del host API MME (los mismos que lista el juego primero)
hostapis = sd.query_hostapis()
disponibles = []
for i, d in enumerate(sd.query_devices()):
    if d["max_input_channels"] > 0 and "MME" in hostapis[d["hostapi"]]["name"]:
        disponibles.append((i, d))

niveles = {}
picos = {}

def hacer_callback(idx):
    def cb(indata, frames, tinfo, status):
        pico = float(np.abs(indata).max())
        niveles[idx] = pico
        picos[idx] = max(picos.get(idx, 0.0), pico)
    return cb

streams = []
for i, d in disponibles:
    ch = min(2, d["max_input_channels"])
    try:
        s = sd.InputStream(device=i, channels=ch, samplerate=SR,
                           blocksize=BLOCK, dtype="float32",
                           callback=hacer_callback(i))
        s.start()
        streams.append(s)
        niveles[i] = 0.0
    except Exception as e:
        print(f"[{i}] {d['name'][:35]}: no se pudo abrir ({e})")

if not streams:
    print("No se pudo abrir ninguna entrada.")
    raise SystemExit

print()
print("TOCA EL TECLADO y mira cual barra se mueve. Ctrl+C para salir.")
print(f"El juego necesita que el pico llegue al menos a ~{UMBRAL_JUEGO}")
print("=" * 78)

try:
    while True:
        lineas = []
        for i, d in disponibles:
            if i not in niveles:
                continue
            v = niveles[i]
            barra = "#" * min(40, int(v * 120))
            marca = "  <-- SEnAL!" if v >= UMBRAL_JUEGO else ""
            lineas.append(f"[{i}] {d['name'][:32]:32s} {v:6.3f} {barra}{marca}")
        print("\n".join(lineas))
        print("-" * 78)
        time.sleep(0.4)
except KeyboardInterrupt:
    pass
finally:
    for s in streams:
        try:
            s.stop(); s.close()
        except Exception:
            pass

print()
print("PICOS MAXIMOS de la sesion:")
for i, d in disponibles:
    if i in picos:
        estado = "SUFICIENTE" if picos[i] >= UMBRAL_JUEGO else ("debil (subir ganancia)" if picos[i] >= 0.008 else "sin senal")
        print(f"[{i}] {d['name'][:35]:35s} pico {picos[i]:6.3f}  -> {estado}")
