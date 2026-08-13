# -*- coding: utf-8 -*-
"""HoloEsfera — la galaxia de pensamiento de IGRIS OS (red neuronal viva).

Representacion grafica 3D de la SINAPSIS NEURONAL de IGRIS. No son puntos
aislados: es una RED CONECTADA. Reglas de diseno:

0) RED CONECTADA CON ONDAS: cada par de neuronas conectadas dibuja una
   ONDA (curva senoidal perpendicular al segmento) que pulsa con la
   actividad. El nucleo (IGRIS) envia ondas hacia TODAS sus capacidades;
   las capacidades se conectan entre si. Nada queda desconectado.

1) CADA NODO ES UNA PARTE ESENCIAL DE IGRIS: comunicacion, microfono,
   sinapsis (bus de pensamiento), comprension, razonamiento logico,
   toma de decisiones, conclusion, memoria, voz, archivos, web,
   generacion, reparacion, evolucion y experiencia. El nucleo central es
   IGRIS mismo. La identidad de cada nodo es interna: solo se ve
   la representacion grafica (sin nombres en pantalla).

2) FLUCTUACION POR ACTIVIDAD (ia_activity 0.0..1.0): cuando IGRIS piensa
   o habla (eventos del bus), sube de forma erratica. Brillo, velocidad
   de rotacion, amplitud de las ondas y tamano de los nodos dependen de
   el. En reposo decae a un murmullo basal.

3) IMPULSOS DE LUZ: cuando la actividad sube, impulsos brillantes viajan
   DESDE EL NUCLEO HACIA EL EXTERIOR por las ondas sinapticas, dejando
   un RASTRO luminoso que se desvanece (motion blur acumulativo).

4) ASIMETRIA ORGANICA: ruido por nodo y por cuadrante hincha, pulsa y
   colapsa zonas segun cual este "procesando datos". Nunca es una esfera
   perfecta.

5) EVOLUTIVO: la red CRECE con el conocimiento real de IGRIS. Lee
   data/experience.db (experiencias y lecciones) y deriva un nivel de
   crecimiento 0..1: mas conocimientos = mas neuronas, mas sinapsis,
   mas intrincada. Cada cierto tiempo reescanea y, si IGRIS aprendio,
   la red se expande (las neuronas nuevas aparecen con animacion).

Material emisivo translucido; mezcla ADITIVA (CompositionMode_Plus) para
que las ondas que se cruzan dupliquen opacidad y brillen mas. Colores:
naranja neon #FF9F00, ambar, dorado y blanco dorado.
"""

import math
import random
import sqlite3
import threading
from collections import deque

from PyQt6.QtCore import QPointF, Qt, QTimer
from PyQt6.QtGui import (QBrush, QColor, QFont, QPainter, QPen,
                             QPainterPath, QRadialGradient)
from PyQt6.QtWidgets import QWidget

try:
    from .. import config
except Exception:  # pragma: no cover
    config = None


NARANJA = (255, 159, 0)        # #FF9F00 neon
AMBAR = (255, 140, 40)
DORADO = (255, 220, 120)
BLANCO_DORADO = (255, 242, 200)
NARANJA_OSCURO = (120, 60, 10)  # zonas inactivas: naranja translucido oscuro
VERDE = (120, 255, 170)        # capacidades de entrada (micro/comunicacion)
AZUL = (120, 190, 255)         # capacidades de red/web


def _lerp(a, b, t):
    return a + (b - a) * t


def _noise_1d(x):
    """Ruido pseudoaleatorio suave 1D (hash -> -1..1) para la asimetria."""
    s = math.sin(x * 12.9898) * 43758.5453
    return (s - math.floor(s)) * 2.0 - 1.0


# Las capacidades esenciales de IGRIS: cada nodo de la red es una de ellas.
# (nombre, tipo, color base)
ESSENCIALES = (
    ("COMUNICACION", "entrada", VERDE),
    ("MICROFONO", "entrada", VERDE),
    ("VOZ", "salida", AMBAR),
    ("SINAPSIS", "nucleo_red", NARANJA),
    ("COMPRENSION", "proceso", NARANJA),
    ("RAZONAMIENTO", "proceso", NARANJA),
    ("DECISION", "proceso", DORADO),
    ("CONCLUSION", "proceso", DORADO),
    ("MEMORIA", "memoria", BLANCO_DORADO),
    ("EXPERIENCIA", "memoria", BLANCO_DORADO),
    ("ARCHIVOS", "herramienta", AZUL),
    ("WEB", "herramienta", AZUL),
    ("GENERACION", "herramienta", NARANJA),
    ("REPARACION", "herramienta", AMBAR),
    ("EVOLUCION", "nucleo_red", DORADO),
)


class HoloEsfera(QWidget):
    """Red neuronal viva de IGRIS (widget transparente)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)

        rnd = random.Random(20260812)
        self._t = 0.0
        self._busy = False
        self._flash = 0.0
        self._rot = 0.0
        # instante de nacimiento de la red: las ondas hacen un fade-in breve
        # al arrancar y despues quedan siempre visibles (sin esto, edad_red
        # vale 0 para siempre y las ondas se dibujan con alpha 0).
        self._t_nacimiento = 0.0

        # --- REGLA 1: estado de actividad de la IA (0.0..1.0) ---------------
        self.ia_activity = 0.0
        self._activity_target = 0.0
        self._jitter_phase = rnd.uniform(0, 6.28)

        # --- REGLA 5: nivel evolutivo real (experiencias + lecciones) -------
        self.nivel = self._nivel_conocimiento()
        self._scan_acc = 0.0

        # --- construccion de la red (neuronas + sinapsis + ondas) -----------
        self._nodes = []
        self._synapses = []
        self._core = []
        self._data_pts = []
        self._rebuild_red(rnd)

        self._queue = deque()
        self._lock = threading.Lock()
        self._pulse_acc = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    # ------------------------------------------------------------------
    # Crecimiento evolutivo (REGLA 5)
    # ------------------------------------------------------------------
    @staticmethod
    def _nivel_conocimiento():
        """Nivel 0..1 de crecimiento de la red segun el conocimiento real de
        IGRIS: numero de experiencias y de lecciones en data/experience.db."""
        try:
            if config is None:
                return 0.5
            p = config.DATA_DIR / "experience.db"
            if not p.exists():
                return 0.5
            con = sqlite3.connect(str(p), timeout=2)
            try:
                exp = con.execute(
                    "SELECT COUNT(*) FROM experiences").fetchone()[0]
                lec = con.execute(
                    "SELECT COUNT(*) FROM lessons").fetchone()[0]
            finally:
                con.close()
            # 1200+ experiencias y 6000+ lecciones -> red madura (1.0)
            nivel = 0.18 + exp / 2400.0 + lec / 12000.0
            return max(0.05, min(1.0, nivel))
        except Exception:
            return 0.5

    def _rebuild_red(self, rnd):
        """Construye (o expande) la red segun el nivel evolutivo actual."""
        # neuronas de crecimiento: cuantas mas, segun el nivel
        n_base = len(ESSENCIALES)
        n_extra = int(34 + 70 * self.nivel)          # 34..104
        n_total = n_base + n_extra
        g = (math.sqrt(5.0) - 1.0) / 2.0
        self._nodes = []
        # nucleo central = IGRIS (nodo virtual en el centro)
        for i in range(n_base):
            nombre, tipo, color = ESSENCIALES[i]
            # los esenciales se reparten en la capa media (radio 0.45..0.8)
            y = 1.0 - (i / max(1, n_base - 1)) * 2.0
            y = y * 0.55
            r = math.sqrt(max(0.01, 1.0 - y * y))
            theta = 2.0 * math.pi * i * g * 1.7
            p = (r * math.cos(theta) * 0.62, y * 0.85,
                 r * math.sin(theta) * 0.62)
            quad = (1 if p[0] >= 0 else 0) + (2 if p[2] >= 0 else 0)
            self._nodes.append({
                "p": p, "quad": quad, "esencial": nombre, "tipo": tipo,
                "color": color,
                "seed": rnd.uniform(0, 100), "f": rnd.uniform(0.6, 1.6),
                "ph": rnd.uniform(0, 6.28), "amp": rnd.uniform(0.5, 1.3),
                "r": 0.9, "born": 1.0,
            })
        # neuronas de crecimiento: nube esferica mas externa
        for i in range(n_extra):
            y = 1.0 - (i / max(1, n_extra - 1)) * 2.0
            r = math.sqrt(max(0.01, 1.0 - y * y))
            theta = 2.0 * math.pi * i * g
            p = (r * math.cos(theta), y, r * math.sin(theta))
            quad = (1 if p[0] >= 0 else 0) + (2 if p[2] >= 0 else 0)
            self._nodes.append({
                "p": p, "quad": quad, "esencial": "", "tipo": "crecimiento",
                "color": NARANJA,
                "seed": rnd.uniform(0, 100), "f": rnd.uniform(0.8, 2.0),
                "ph": rnd.uniform(0, 6.28), "amp": rnd.uniform(0.4, 1.2),
                "r": rnd.uniform(0.85, 1.25), "born": 1.0,
            })
        # --- sinapsis: TODOS conectados (nada aislado) ----------------------
        # densidad de vecinos segun el nivel: mas conocimiento = mas intrincada
        n_vecinos = 2 + int(3 * self.nivel)          # 2..5
        self._synapses = []
        vistos = set()
        for i, nd in enumerate(self._nodes):
            dists = sorted(
                range(n_total),
                key=lambda j: (nd["p"][0] - self._nodes[j]["p"][0]) ** 2 +
                              (nd["p"][1] - self._nodes[j]["p"][1]) ** 2 +
                              (nd["p"][2] - self._nodes[j]["p"][2]) ** 2
            )
            for j in dists[1:n_vecinos + 1]:
                clave = (i, j) if i < j else (j, i)
                if clave in vistos:
                    continue
                vistos.add(clave)
                self._synapses.append({
                    "a": clave[0], "b": clave[1], "energy": 0.0,
                    "pulses": deque(), "trail": deque(),
                })
        # cada esencial conecta DIRECTAMENTE con el nucleo (IGRIS): las ondas
        # del pensamiento parten de el y llegan a todas las capacidades.
        nucleo_ref = (0.0, 0.0, 0.0)
        for i in range(n_base):
            clave = ("n", i)
            if clave in vistos:
                continue
            vistos.add(clave)
            self._synapses.append({
                "a": "nucleo", "b": i, "nucleo_ref": nucleo_ref,
                "energy": 0.0, "pulses": deque(), "trail": deque(),
            })
        # --- nucleo denso y caotico ------------------------------------------
        self._core = []
        for _ in range(160):
            u = rnd.uniform(-1, 1)
            ph = math.asin(u)
            th = rnd.uniform(0, 2 * math.pi)
            rr = rnd.uniform(0.0, 0.15)
            self._core.append({
                "p": (rr * math.cos(ph) * math.cos(th), rr * math.sin(ph),
                      rr * math.cos(ph) * math.sin(th)),
                "j": (rnd.uniform(1.0, 3.5), rnd.uniform(1.0, 3.5),
                      rnd.uniform(1.0, 3.5)),
                "ph": (rnd.uniform(0, 6.28), rnd.uniform(0, 6.28),
                       rnd.uniform(0, 6.28)),
            })
        # --- micro-puntos de datos --------------------------------------------
        self._data_pts = []
        for _ in range(90):
            u = rnd.uniform(-1, 1)
            ph = math.asin(u)
            th = rnd.uniform(0, 2 * math.pi)
            self._data_pts.append({
                "p": (math.cos(ph) * math.cos(th), math.sin(ph),
                      math.cos(ph) * math.sin(th)),
                "f1": rnd.uniform(0.5, 2.2), "ph1": rnd.uniform(0, 6.28),
                "f2": rnd.uniform(2.5, 6.0), "ph2": rnd.uniform(0, 6.28),
            })

    def _expandir_si_aprendio(self):
        """REGLA 5: si el conocimiento real subio, la red crece (mas neuronas
        y mas sinapsis). Las neuronas nuevas aparecen con animacion."""
        nuevo = self._nivel_conocimiento()
        if nuevo > self.nivel + 0.02:
            antes = len(self._nodes)
            self.nivel = nuevo
            rnd = random.Random(20260812)
            self._rebuild_red(rnd)
            # SOLO las neuronas nuevas (las que no existian antes) aparecen
            # con animacion de fundido; las demas nacen ya visibles.
            for nd in self._nodes[antes:]:
                nd["born"] = 0.0
            self._t_nacimiento = self._t
            return True
        return False

    # ------------------------------------------------------------------
    # API publica
    # ------------------------------------------------------------------
    def set_busy(self, busy):
        self._busy = bool(busy)
        if busy:
            self._flash = 1.0
            self._activity_target = min(1.0, self._activity_target + 0.65)

    def _handle_event(self, event):
        tipo = event.get("tipo")
        if tipo == "orden":
            self._busy = True
        elif tipo in ("exito", "fallo"):
            self._busy = False
        base = {
            "orden": 0.50, "rama": 0.28, "tarea": 0.30, "plan": 0.32,
            "semilla": 0.40, "genera": 0.45, "especialistas": 0.38,
            "intento": 0.42, "progreso": 0.30, "error": 0.60, "exito": 0.48,
            "fallo": 0.55,
        }.get(tipo, 0.25)
        saltos = (0.62, 0.78, 0.9, 1.0, 1.15, 1.3)
        k = saltos[int(self._t * 3.1) % len(saltos)]
        jitter = 0.08 + 0.14 * abs(math.sin(self._t * 2.7 + self._jitter_phase))
        empuje = base * k * (1.0 + jitter)
        self._activity_target = min(1.0, self._activity_target + empuje)
        if tipo in ("orden", "error", "fallo", "genera", "intento"):
            self._flash = max(self._flash, 0.85)
        elif tipo == "exito":
            self._flash = max(self._flash, 0.7)
        else:
            self._flash = max(self._flash, 0.45)

    def _tick(self):
        with self._lock:
            events = list(self._queue)
            self._queue.clear()
        for ev in events:
            try:
                self._handle_event(ev)
            except Exception:
                pass
        dt = 1.0 / 30.0
        self._t += dt
        self._flash *= 0.96

        # REGLA 1: actividad suavizada hacia el objetivo + decaimiento basal.
        self.ia_activity += (self._activity_target - self.ia_activity) * 0.045
        self.ia_activity *= 0.9955
        self._activity_target *= 0.94
        self.ia_activity = max(0.02, min(1.0, self.ia_activity))
        # Mientras IGRIS trabaja (busy), la red mantiene un nivel visible: no
        # se apaga durante la lectura/respuesta aunque no lleguen eventos.
        if self._busy:
            self.ia_activity = max(self.ia_activity, 0.45)

        # REGLA 5: reescanea el conocimiento cada 20s y crece si aprendio.
        self._scan_acc += dt
        if self._scan_acc >= 20.0:
            self._scan_acc = 0.0
            try:
                self._expandir_si_aprendio()
            except Exception:
                pass

        # fundido de aparicion de neuronas nuevas (born -> 1)
        for nd in self._nodes:
            if nd["born"] < 1.0:
                nd["born"] = min(1.0, nd["born"] + 0.04)

        # rotacion vinculada a la actividad
        vel = 0.14 + 0.62 * self.ia_activity
        self._rot += vel * dt

        # impulsos por las sinapsis (desde el nucleo hacia afuera)
        for syn in self._synapses:
            syn["energy"] *= 0.965
            vivos = []
            for pulso in syn["pulses"]:
                pulso["t"] += dt * pulso["vel"] * (0.7 + 1.4 * self.ia_activity)
                if pulso["t"] < 1.0:
                    vivos.append(pulso)
                else:
                    syn["energy"] = max(syn["energy"], 0.9)
            syn["pulses"] = deque(vivos)
            for r in list(syn["trail"]):
                r["e"] *= 0.90
            syn["trail"] = deque(r for r in syn["trail"] if r["e"] > 0.03)
        # cadencia: mas actividad, impulsos mas frecuentes
        intervalo = 0.72 - 0.5 * self.ia_activity
        self._pulse_acc += dt
        if self.ia_activity > 0.15 and self._pulse_acc >= intervalo:
            self._pulse_acc = 0.0
            n_pulsos = 1 + int(self.ia_activity * 3.2)
            for _ in range(n_pulsos):
                self._lanzar_impulso()

        self.update()

    def _lanzar_impulso(self):
        """Impulso de luz que viaja por una sinapsis. Prefiere las ondas que
        parten del nucleo (IGRIS) hacia una capacidad, y luego el resto."""
        if not self._synapses:
            return
        elegida = None
        mejor = 1e9
        for _ in range(30):
            syn = self._synapses[random.randrange(len(self._synapses))]
            if syn.get("a") == "nucleo":
                d = 0.0
            else:
                na = self._nodes[syn["a"]]
                nb = self._nodes[syn["b"]]
                ra = math.sqrt(na["p"][0] ** 2 + na["p"][1] ** 2 +
                               na["p"][2] ** 2)
                rb = math.sqrt(nb["p"][0] ** 2 + nb["p"][1] ** 2 +
                               nb["p"][2] ** 2)
                d = min(ra, rb)
            if d < mejor:
                mejor = d
                elegida = syn
        if elegida is None or mejor > 0.72:
            elegida = self._synapses[random.randrange(len(self._synapses))]
        elegida["pulses"].append({
            "t": 0.0, "vel": random.uniform(0.28, 0.5), "e": 1.0})
        elegida["energy"] = max(elegida["energy"], 0.65)

    def detach(self):
        try:
            self._timer.stop()
        except Exception:
            pass

    # ------------------------------------------------------------------
    def _project(self, p, cx, cy, f, R):
        """Rota (Euler Z, X, Y) + perspectiva; devuelve (sx, sy, depth, z)."""
        x, y, z = p
        ang = self._rot
        c, s = math.cos(ang), math.sin(ang)
        x, y = x * c - y * s, x * s + y * c
        c2, s2 = math.cos(ang * 0.7), math.sin(ang * 0.7)
        y, z = y * c2 - z * s2, y * s2 + z * c2
        d = f / (f + z)
        return cx + x * R * d, cy + y * R * d, d, z

    def _pulso_cuadrante(self, quad, x, y, z):
        """REGLA 4: asimetria organica por cuadrante."""
        ejes = [(1, 0, 0), (-1, 0, 0), (0, 0, 1), (0, 0, -1)]
        ex, ey, ez = ejes[quad]
        cerca = max(0.0, (x * ex + y * ey + z * ez))
        global_p = (math.sin(self._t * 0.9) + math.cos(self._t * 0.57)) * 0.5
        activo = 0.42 * self.ia_activity * cerca * (0.6 + 0.4 * global_p)
        ruido = 0.10 * _noise_1d(self._t * 0.7 + quad * 7.3)
        return activo + ruido

    @staticmethod
    def _draw_onda(painter, x0, y0, x1, y1, t, amp, seg=7):
        """Dibuja la sinapsis como una ONDA (curva senoidal perpendicular al
        segmento). El trazado es un QPainterPath para mezcla aditiva."""
        dx = x1 - x0
        dy = y1 - y0
        largo = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / largo, dx / largo
        path = QPainterPath(QPointF(x0, y0))
        for k in range(1, seg):
            u = k / float(seg)
            bx = x0 + dx * u
            by = y0 + dy * u
            onda = math.sin(u * math.pi * 2.6 - t * 4.2) * amp
            path.lineTo(QPointF(bx + nx * onda, by + ny * onda))
        path.lineTo(QPointF(x1, y1))
        painter.drawPath(path)

    def paintEvent(self, event):
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w = self.width()
        h = self.height()
        cx, cy = w / 2.0, h / 2.0
        # La red es el foco visual del panel: ocupa casi toda la altura útil,
        # como en la interfaz militar de referencia.
        R = min(w, h) * 0.48
        f = 2.6

        act = self.ia_activity
        glitch = 0.9 + 0.1 * math.sin(self._t * 2.3)
        if int(self._t * 0.8) % 11 == 0:
            glitch = 0.78
        brillo = 0.9 + 0.65 * act + 0.22 * self._flash
        escala_nodos = 0.8 + 2.4 * act
        # animacion de aparicion de neuronas nuevas (crecimiento)
        nacimiento = getattr(self, "_t_nacimiento", self._t)
        edad_red = max(0.0, min(1.0, (self._t - nacimiento) * 2.0))

        # fuentes para los nombres de los nodos esenciales
        fuente = QFont("Consolas", 7)
        fuente.setBold(False)
        painter.setFont(fuente)

        # FONDO: velo oscuro en todo el widget + vineta fuerte en la zona de la
        # red. La foto queda como fondo tenue; el naranja de la red resalta.
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(6, 4, 1, 95)))
        painter.drawRect(0, 0, w, h)
        grd = QRadialGradient(cx, cy, R * 1.5)
        grd.setColorAt(0.0, QColor(10, 6, 2, 195))
        grd.setColorAt(0.55, QColor(7, 4, 2, 145))
        grd.setColorAt(0.85, QColor(4, 3, 1, 70))
        grd.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setBrush(QBrush(grd))
        painter.drawEllipse(QPointF(cx, cy), R * 1.5, R * 1.5)

        painter.setCompositionMode(
            QPainter.CompositionMode.CompositionMode_Plus)

        # --- proyeccion de nodos con asimetria organica ----------------------
        proj = []
        for nd in self._nodes:
            x, y, z = nd["p"]
            pulso = self._pulso_cuadrante(nd["quad"], x, y, z)
            wav = 0.5 + 0.5 * math.sin(self._t * nd["f"] + nd["ph"])
            factor = 1.0 + pulso + 0.045 * nd["amp"] * wav
            q = (x * factor, y * factor, z * factor)
            proj.append(self._project(q, cx, cy, f, R * nd["r"]))

        def pt(syn, cual):
            """Extremo (proyectado) de una sinapsis: nucleo o nodo.
            Devuelve (x, y, profundidad) — el 4o valor (z) no se usa aqui."""
            idx = syn[cual]
            if idx == "nucleo":
                return cx, cy, 1.0
            return proj[idx][0], proj[idx][1], proj[idx][2]

        # --- ondas sinapticas (REGLA 0): todo conectado, nada aislado -------
        # ONDAS: amplitude de la onda crece con la actividad. Las zonas
        # inactivas quedan naranja translucido oscuro; las activas se
        # saturan en #FF9F00.
        amp_onda = 2.5 + 9.0 * act
        for syn in self._synapses:
            ax, ay, ad = pt(syn, "a")
            bx, by, bd = pt(syn, "b")
            prof = (ad * 0.5 + 0.5 + bd * 0.5 + 0.5) * 0.5
            energia = syn["energy"]
            es_nucleo = syn.get("a") == "nucleo"
            # conexiones SIEMPRE visibles (suelo alto), mas brillantes al
            # procesar; halo grueso tenue debajo de la linea fina brillante.
            al = int((105 + 125 * prof * (0.5 + act) + 190 * energia)
                     * glitch * brillo * edad_red)
            al = min(255, al)
            col = NARANJA if (energia > 0.12 or es_nucleo) else NARANJA_OSCURO
            if es_nucleo or energia > 0.1:
                painter.setPen(QPen(QColor(*col, min(130, al // 3)),
                                    4.0 if es_nucleo else 3.2))
                self._draw_onda(painter, ax, ay, bx, by, self._t, amp_onda)
            painter.setPen(QPen(QColor(*col, al),
                                2.0 if es_nucleo else 1.5))
            try:
                self._draw_onda(painter, ax, ay, bx, by, self._t, amp_onda)
            except Exception:
                painter.drawLine(QPointF(ax, ay), QPointF(bx, by))

        # --- impulsos de luz + rastro acumulativo ----------------------------
        for syn in self._synapses:
            if not syn["pulses"] and not syn["trail"]:
                continue
            ax, ay, _ = pt(syn, "a")
            bx, by, _ = pt(syn, "b")
            for pulso in syn["pulses"]:
                t = pulso["t"]
                px = _lerp(ax, bx, t)
                py = _lerp(ay, by, t)
                e = pulso["e"] * act
                al = int(255 * e * brillo * glitch)
                painter.setBrush(QBrush(QColor(*NARANJA, min(255, al))))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(QPointF(px, py),
                                    1.6 + 1.1 * act, 1.6 + 1.1 * act)
                cola_t = max(0.0, t - 0.18)
                px0, py0 = _lerp(ax, bx, cola_t), _lerp(ay, by, cola_t)
                gcol = QColor(*NARANJA, int(150 * e * brillo * glitch))
                painter.setPen(QPen(gcol, 1.0))
                painter.drawLine(QPointF(px0, py0), QPointF(px, py))
                syn["trail"].append({"x": px, "y": py, "e": e})
            for r in syn["trail"]:
                al = int(110 * r["e"] * brillo * glitch)
                if al < 6:
                    continue
                painter.setBrush(QBrush(QColor(*AMBAR, min(200, al))))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(QPointF(r["x"], r["y"]),
                                    0.9 + 0.8 * act, 0.9 + 0.8 * act)

        # --- nodos: tamano por actividad; esenciales con su NOMBRE -----------
        for i, nd in enumerate(self._nodes):
            sx, sy, d, _z = proj[i]
            born = nd.get("born", 1.0)
            alpha_nodo = (95 + 110 * act + 70 * self._flash) * d * glitch \
                * brillo * (0.25 + 0.75 * born)
            tam = (0.9 + escala_nodos * d) * (0.5 + 0.5 * born)
            if nd["esencial"]:
                color = nd["color"]
                tam *= 1.3
                alpha_nodo *= 1.4
            else:
                color = DORADO
            painter.setBrush(QBrush(QColor(*color, min(230, int(alpha_nodo)))))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPointF(sx, sy), tam, tam)

        # --- micro-puntos de datos --------------------------------------------
        for dp in self._data_pts:
            sx, sy, d, _z = self._project(dp["p"], cx, cy, f, R)
            flick = 0.5 + 0.5 * (math.sin(self._t * dp["f1"] + dp["ph1"]) *
                                 math.cos(self._t * dp["f2"] + dp["ph2"]))
            al = int(80 * d * flick * glitch * brillo)
            painter.setBrush(QBrush(QColor(*DORADO, al)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPointF(sx, sy), 0.8, 0.8)

        # --- nucleo denso y caotico (IGRIS) -----------------------------------
        for c_pt in self._core:
            jx, jy, jz = c_pt["j"]
            px, py, pz = c_pt["p"]
            q = (
                px + 0.012 * math.sin(self._t * jx + c_pt["ph"][0]),
                py + 0.012 * math.sin(self._t * jy + c_pt["ph"][1]),
                pz + 0.012 * math.sin(self._t * jz + c_pt["ph"][2]),
            )
            sx, sy, d, _z = self._project(q, cx, cy, f, R)
            al = int((150 + 150 * act + 110 * self._flash) * d * glitch * brillo)
            painter.setBrush(QBrush(QColor(*BLANCO_DORADO, min(255, al))))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPointF(sx, sy),
                                1.35 + 0.95 * act, 1.35 + 0.95 * act)

        painter.setCompositionMode(
            QPainter.CompositionMode.CompositionMode_SourceOver)


# Alias: el panel (terminal_ui) usa el nombre GalaxiaWidget.
GalaxiaWidget = HoloEsfera
