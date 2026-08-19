# -*- coding: utf-8 -*-
"""Galaxia operativa: red REAL de capacidades de IGRIS OS.

Cada nodo es una capacidad registrada en el nucleo (ya no decorativa).
Estados por nodo:

    pending   (gris)  -> pendiente
    working   (oro)   -> ejecutandose
    ok        (verde) -> completada con exito
    error     (rojo)  -> fallida

La senal ``nodeActivated(name, description, risk, state)`` se emite al pulsar
un nodo para que el panel muestre su tarea, archivos y registros.
"""

import logging
import math
import random
import time

from PyQt6.QtCore import QPointF, Qt, QTimer, pyqtSignal

logger = logging.getLogger(__name__)
from PyQt6.QtGui import (QBrush, QColor, QFont, QPainter, QPen,
                         QPainterPath, QLinearGradient, QRadialGradient)
from PyQt6.QtWidgets import QWidget

# Paleta de estados (nodos) y de la red (ondas/impulsos).
ORO = (255, 200, 80)          # trabajando
VERDE = (120, 255, 170)       # ok
ROJO = (255, 84, 96)          # error
GRIS = (110, 114, 126)        # pendiente
NARANJA = (255, 159, 0)       # ondas activas
AMBAR = (255, 140, 40)        # rastro de impulsos
DORADO = (255, 220, 120)      # micro-puntos
BLANCO_DORADO = (255, 242, 200)  # nucleo

ESTADO_COLOR = {
    "pending": GRIS,
    "working": ORO,
    "ok": VERDE,
    "error": ROJO,
}


def _lerp(a, b, t):
    return a + (b - a) * t


def _noise_1d(x):
    """Ruido pseudoaleatorio suave 1D (hash -> -1..1)."""
    s = math.sin(x * 12.9898) * 43758.5453
    return (s - math.floor(s)) * 2.0 - 1.0


class GalaxiaWidget(QWidget):
    """Red de capacidades reales de IGRIS (widget transparente)."""

    nodeActivated = pyqtSignal(str, str, str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        # Opaca: pintar el fondo propio evita recompositar el panel detrás
        # (la translucidez disparaba ~80% de CPU incluso congelada).
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.setMouseTracking(True)

        rnd = random.Random(20260812)
        self._t = 0.0
        self._busy = False
        self._flash = 0.0
        self._rot = 0.0
        self.ia_activity = 0.0
        self._activity_target = 0.0
        self._active = None
        self._states = {}
        self._hover = None
        self._nodes = []
        self._synapses = []
        self._core = []
        self._data_pts = []
        self._pulse_acc = 0.0
        self._dirty = False
        self._build_ambient(rnd)
        self._build_rings()
        self._sparks = []
        self._last = time.monotonic()

        self._timer = QTimer(self)
        self._timer.setInterval(50)
        self._timer.timeout.connect(self._tick)
        # No se inicia: la galaxia arranca congelada y solo anima al pensar.

    def _mark_dirty(self):
        self._dirty = True

    def _clear_dirty(self):
        self._dirty = False

    # ------------------------------------------------------------------
    # Datos reales
    # ------------------------------------------------------------------
    def set_capabilities(self, specs) -> None:
        """Reemplaza la red con las capacidades REALES del nucleo.

        ``specs`` puede ser una lista de objetos con atributos
        ``name/description/risk`` o de diccionarios equivalentes.
        """
        items = []
        for spec in specs:
            if isinstance(spec, dict):
                name = spec.get("name")
                description = spec.get("description", "")
                risk = spec.get("risk", "")
            else:
                name = getattr(spec, "name", None)
                description = getattr(spec, "description", "") or ""
                risk = getattr(spec, "risk", "") or ""
            if not name:
                continue
            risk = getattr(risk, "value", str(risk))
            items.append((str(name), str(description), str(risk)))
        self._active = None
        self._states = {}
        self._hover = None
        self._build_nodes(items, random.Random(20260812))
        self._resume()
        self._mark_dirty()

    def set_active(self, name: str) -> None:
        """Marca la capacidad ``name`` como en ejecucion (oro)."""
        self._active = name
        self._flash = max(self._flash, 0.9)
        self._activity_target = min(1.0, self._activity_target + 0.6)
        self._resume()
        self._mark_dirty()

    def set_result(self, name: str, ok: bool) -> None:
        """Marca la capacidad ``name`` como ok (verde) o error (rojo)."""
        self._states[name] = "ok" if ok else "error"
        if self._active == name:
            self._active = None
        self._flash = max(self._flash, 0.7 if ok else 0.95)
        self._resume()
        self._mark_dirty()

    def reset_states(self) -> None:
        """Vuelve todos los nodos a pendiente."""
        self._states.clear()
        self._active = None
        self._mark_dirty()

    def state_of(self, name: str) -> str:
        """Estado efectivo de un nodo (working domina sobre ok/error)."""
        if name == self._active:
            return "working"
        return self._states.get(name, "pending")

    def set_busy(self, busy) -> None:
        self._busy = bool(busy)
        if busy:
            self._flash = 1.0
            self._activity_target = min(1.0, self._activity_target + 0.65)
            self._resume()
        self._mark_dirty()

    def _resume(self) -> None:
        """Reanuda la animación (tras reposo o al iniciar actividad)."""
        self._last = time.monotonic()
        if not self._timer.isActive():
            self._timer.start()

    def detach(self) -> None:
        try:
            self._timer.stop()
        except (RuntimeError, AttributeError) as exc:
            logger.debug("No se pudo detener el temporizador de la galaxia: %s",
                         exc)

    # ------------------------------------------------------------------
    # Construccion de la red
    # ------------------------------------------------------------------
    def _build_ambient(self, rnd) -> None:
        self._core = []
        for _ in range(70):
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
        self._data_pts = []
        for _ in range(36):
            u = rnd.uniform(-1, 1)
            ph = math.asin(u)
            th = rnd.uniform(0, 2 * math.pi)
            self._data_pts.append({
                "p": (math.cos(ph) * math.cos(th), math.sin(ph),
                      math.cos(ph) * math.sin(th)),
                "f1": rnd.uniform(0.5, 2.2), "ph1": rnd.uniform(0, 6.28),
                "f2": rnd.uniform(2.5, 6.0), "ph2": rnd.uniform(0, 6.28),
            })

    def _build_rings(self) -> None:
        """Pistas orbitales concéntricas (esfera armilar) del núcleo."""
        def _norm(x, y, z):
            largo = math.sqrt(x * x + y * y + z * z) or 1.0
            return (x / largo, y / largo, z / largo)

        rings = []
        # Tres círculos máximos ortogonales (armazón de la esfera).
        for axis in ((1, 0, 0), (0, 1, 0), (0, 0, 1)):
            rings.append({"axis": axis, "radius": 0.98, "speed": 0.10,
                          "phase": 0.0, "color": NARANJA, "width": 2.4})
        # Pistas concéntricas menores (plano ecuatorial).
        for radius, speed, color in ((0.62, 0.17, AMBAR),
                                     (0.34, 0.24, DORADO)):
            rings.append({"axis": (0, 1, 0), "radius": radius, "speed": speed,
                          "phase": 0.0, "color": color, "width": 1.6})
        # Pistas inclinadas.
        for axis, radius, speed in ((_norm(0.55, 0.80, 0.25), 0.80, 0.13),
                                    (_norm(0.35, 0.35, 0.87), 0.52, 0.19)):
            rings.append({"axis": axis, "radius": radius, "speed": speed,
                          "phase": 0.0, "color": NARANJA, "width": 1.8})
        self._rings = rings

    def _ring_basis(self, ring):
        """Base ortonormal (u, v) del plano perpendicular al eje."""
        ax, ay, az = ring["axis"]
        ref = (0, 0, 1) if abs(az) < 0.9 else (1, 0, 0)
        ux, uy, uz = (ay * ref[2] - az * ref[1],
                      az * ref[0] - ax * ref[2],
                      ax * ref[1] - ay * ref[0])
        ul = math.sqrt(ux * ux + uy * uy + uz * uz) or 1.0
        ux, uy, uz = ux / ul, uy / ul, uz / ul
        vx, vy, vz = (ay * uz - az * uy,
                      az * ux - ax * uz,
                      ax * uy - ay * ux)
        return ux, uy, uz, vx, vy, vz, ring["radius"]

    def _ring_point_at(self, ring, angle):
        """Punto 3D del anillo en un ángulo dado (sin la fase)."""
        ux, uy, uz, vx, vy, vz, r = self._ring_basis(ring)
        c, s = math.cos(angle), math.sin(angle)
        return (r * (c * ux + s * vx),
                r * (c * uy + s * vy),
                r * (c * uz + s * vz))

    def _ring_points(self, ring, n=64):
        """Circunferencia 3D perpendicular al eje del anillo."""
        ux, uy, uz, vx, vy, vz, r = self._ring_basis(ring)
        pts = []
        for k in range(n):
            th = ring["phase"] + 2.0 * math.pi * k / n
            c, s = math.cos(th), math.sin(th)
            pts.append((r * (c * ux + s * vx),
                        r * (c * uy + s * vy),
                        r * (c * uz + s * vz)))
        return pts

    def _build_nodes(self, items, rnd) -> None:
        self._nodes = []
        self._synapses = []
        if not items:
            return

        # Agrupar por especialidad (prefijo del nombre) para que los nodos
        # afines queden cerca en la esfera.
        groups: dict[str, list[int]] = {}
        for idx, (name, _desc, _risk) in enumerate(items):
            groups.setdefault(name.split(".")[0], []).append(idx)
        group_names = list(groups.keys())

        if not self._rings:
            self._build_rings()
        ring_members = [[] for _ in range(len(self._rings))]
        for g_i, group in enumerate(group_names):
            ring_members[g_i % len(self._rings)].extend(groups[group])

        idx_to_pos = {}
        for ri, members in enumerate(ring_members):
            ring = self._rings[ri]
            count = len(members)
            for pos, idx in enumerate(members):
                name, description, risk = items[idx]
                angle = 2.0 * math.pi * pos / max(1, count)
                p = self._ring_point_at(ring, angle)
                quad = (1 if p[0] >= 0 else 0) + (2 if p[2] >= 0 else 2)
                idx_to_pos[idx] = len(self._nodes)
                self._nodes.append({
                    "name": name, "description": description, "risk": risk,
                    "p": p, "quad": quad,
                    "ring": ri, "angle": angle,
                    "seed": rnd.uniform(0, 100), "f": rnd.uniform(0.5, 1.6),
                    "ph": rnd.uniform(0, 6.28), "amp": rnd.uniform(0.5, 1.2),
                    "r": 0.9, "born": 0.0,
                })

        # Sinapsis: cada nodo se conecta a sus vecinos mas cercanos; el nucleo
        # (IGRIS) se conecta al primer nodo de cada especialidad.
        vistos = set()
        n_total = len(self._nodes)
        for i in range(n_total):
            dists = sorted(range(n_total), key=lambda j: self._dist(i, j))
            for j in dists[1:4]:
                clave = (i, j) if i < j else (j, i)
                if clave in vistos:
                    continue
                vistos.add(clave)
                self._synapses.append({
                    "a": clave[0], "b": clave[1], "energy": 0.0,
                    "pulses": [], "trail": [],
                })
        for group in group_names:
            self._synapses.append({
                "a": "nucleo", "b": idx_to_pos[groups[group][0]], "energy": 0.0,
                "pulses": [], "trail": [],
            })

    def _dist(self, i, j):
        pa = self._nodes[i]["p"]
        pb = self._nodes[j]["p"]
        return ((pa[0] - pb[0]) ** 2 + (pa[1] - pb[1]) ** 2 +
                (pa[2] - pb[2]) ** 2)

    # ------------------------------------------------------------------
    # Animacion
    # ------------------------------------------------------------------
    def _tick(self):
        ahora = time.monotonic()
        dt = min(0.1, ahora - self._last)
        self._last = ahora
        self._t += dt
        self._flash *= 0.96 ** (dt * 30.0)

        self.ia_activity += (self._activity_target - self.ia_activity) * 0.045
        self.ia_activity *= 0.9955
        self._activity_target *= 0.94
        self.ia_activity = max(0.02, min(1.0, self.ia_activity))
        if self._busy:
            self.ia_activity = max(self.ia_activity, 0.45)

        # FPS adaptativo: 20fps pensando, 12fps en reposo (rotación lenta).
        objetivo = 50 if self.ia_activity > 0.25 else 83
        if self._timer.interval() != objetivo:
            self._timer.setInterval(objetivo)

        for nd in self._nodes:
            if nd["born"] < 1.0:
                nd["born"] = min(1.0, nd["born"] + dt * 1.2)

        vel = 0.14 + 0.62 * self.ia_activity
        self._rot += vel * dt

        for ring in self._rings:
            ring["phase"] += ring["speed"] * dt * (0.5 + 1.5 * self.ia_activity)

        for nd in self._nodes:
            ring = self._rings[nd["ring"]]
            nd["p"] = self._ring_point_at(ring, ring["phase"] + nd["angle"])
            x, y, z = nd["p"]
            nd["quad"] = (1 if x >= 0 else 0) + (2 if z >= 0 else 2)

        for syn in self._synapses:
            syn["energy"] *= 0.965 ** (dt * 30.0)
            vivos = []
            for pulso in syn["pulses"]:
                pulso["t"] += dt * pulso["vel"] * (0.7 + 1.4 * self.ia_activity)
                if pulso["t"] < 1.0:
                    vivos.append(pulso)
                else:
                    syn["energy"] = max(syn["energy"], 0.9)
            syn["pulses"] = vivos
            syn["trail"] = [r for r in syn["trail"] if r["e"] > 0.03]
            for r in syn["trail"]:
                r["e"] *= 0.90 ** (dt * 30.0)

        intervalo = 0.72 - 0.5 * self.ia_activity
        self._pulse_acc += dt
        if self.ia_activity > 0.15 and self._pulse_acc >= intervalo:
            self._pulse_acc = 0.0
            for _ in range(1 + int(self.ia_activity * 3.2)):
                self._lanzar_impulso()

        self._update_sparks(dt)

        # Reposo: congelar la animación cuando todo se asienta (~0 CPU).
        asentado = (
            not self._busy
            and self.ia_activity < 0.06
            and self._flash < 0.02
            and self._activity_target < 0.08
            and not self._sparks
            and all(nd.get("born", 1.0) >= 1.0 for nd in self._nodes)
            and not any(syn["pulses"] or syn["trail"] for syn in self._synapses)
        )
        if asentado:
            self._timer.stop()

        if self._dirty:
            self._clear_dirty()
        self.update()

    def _lanzar_impulso(self):
        """Impulso de luz por una sinapsis; prefiere la sinapsis del nodo
        que esta trabajando (oro)."""
        if not self._synapses:
            return
        activas = [
            syn for syn in self._synapses
            if syn.get("a") == "nucleo" and
            self.state_of(self._nodes[syn["b"]]["name"]) == "working"
        ]
        pool = activas or self._synapses
        elegida = pool[random.randrange(len(pool))]
        elegida["pulses"].append({
            "t": 0.0, "vel": random.uniform(0.28, 0.5), "e": 1.0})
        elegida["energy"] = max(elegida["energy"], 0.65)

    def _spawn_spark(self):
        """Chispa que escapa del núcleo hacia el exterior."""
        u = random.uniform(-1, 1)
        ph = math.asin(u)
        th = random.uniform(0, 2 * math.pi)
        dx = math.cos(ph) * math.cos(th)
        dy = math.sin(ph)
        dz = math.cos(ph) * math.sin(th)
        velocidad = random.uniform(0.25, 0.7)
        self._sparks.append({
            "p": [dx * 0.05, dy * 0.05, dz * 0.05],
            "v": [dx * velocidad, dy * velocidad, dz * velocidad],
            "life": random.uniform(0.5, 1.2),
            "max": 1.2,
        })

    def _update_sparks(self, dt):
        """Avanza las chispas y repone las que mueren."""
        vivos = []
        for sp in self._sparks:
            sp["life"] -= dt
            if sp["life"] <= 0:
                continue
            sp["p"][0] += sp["v"][0] * dt
            sp["p"][1] += sp["v"][1] * dt
            sp["p"][2] += sp["v"][2] * dt
            vivos.append(sp)
        self._sparks = vivos
        tasa = (0.5 + 2.5 * self.ia_activity) * dt
        if random.random() < tasa and len(self._sparks) < 50:
            self._spawn_spark()

    # ------------------------------------------------------------------
    # Proyeccion y dibujo
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
        """Asimetria organica por cuadrante."""
        ejes = [(1, 0, 0), (-1, 0, 0), (0, 0, 1), (0, 0, -1)]
        ex, ey, ez = ejes[quad]
        cerca = max(0.0, (x * ex + y * ey + z * ez))
        global_p = (math.sin(self._t * 0.9) + math.cos(self._t * 0.57)) * 0.5
        activo = 0.42 * self.ia_activity * cerca * (0.6 + 0.4 * global_p)
        ruido = 0.10 * _noise_1d(self._t * 0.7 + quad * 7.3)
        return activo + ruido

    @staticmethod
    def _draw_onda(painter, x0, y0, x1, y1, t, amp, seg=5):
        """Sinapsis como ONDA (curva senoidal perpendicular al segmento)."""
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
        R = min(w, h) * 0.46
        f = 2.6

        act = self.ia_activity
        glitch = 0.9 + 0.1 * math.sin(self._t * 2.3)
        if int(self._t * 0.8) % 11 == 0:
            glitch = 0.78
        brillo = 0.9 + 0.65 * act + 0.22 * self._flash

        # Fondo opaco: velo + vineta.
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(6, 4, 1)))
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

        # Pistas orbitales concéntricas (esfera armilar).
        pulso_ring = 0.5 + 0.5 * math.sin(self._t * 0.8)
        for ring in self._rings:
            pts = self._ring_points(ring, 36)
            pr = [self._project(pt, cx, cy, f, R) for pt in pts]
            base = int((48 + 48 * pulso_ring + 70 * act) * glitch * brillo)
            base = max(6, min(150, base))
            col = ring["color"]
            full = QPainterPath(QPointF(pr[0][0], pr[0][1]))
            for sx, sy, _d, _z in pr[1:]:
                full.lineTo(QPointF(sx, sy))
            full.closeSubpath()
            painter.setPen(QPen(QColor(*col, base), ring["width"]))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(full)
            # Mitad frontal más luminosa (un único path para abaratar el dibujo).
            front = QPainterPath()
            started = False
            for a, b in zip(pr, pr[1:]):
                if a[3] < 0 and b[3] < 0 and \
                        math.hypot(b[0] - a[0], b[1] - a[1]) < R * 0.4:
                    if not started:
                        front.moveTo(QPointF(a[0], a[1]))
                        started = True
                    front.lineTo(QPointF(b[0], b[1]))
                else:
                    started = False
            painter.setPen(QPen(QColor(*col, min(225, base + 90)),
                                ring["width"] + 0.6))
            painter.drawPath(front)

        # Proyeccion de nodos.
        proj = []
        for nd in self._nodes:
            x, y, z = nd["p"]
            pulso = self._pulso_cuadrante(nd["quad"], x, y, z)
            wav = 0.5 + 0.5 * math.sin(self._t * nd["f"] + nd["ph"])
            factor = 1.0 + pulso + 0.045 * nd["amp"] * wav
            q = (x * factor, y * factor, z * factor)
            proj.append(self._project(q, cx, cy, f, R))

        def pt(syn, cual):
            idx = syn[cual]
            if idx == "nucleo":
                return cx, cy, 1.0
            return proj[idx][0], proj[idx][1], proj[idx][2]

        # Ondas sinapticas.
        amp_onda = 2.5 + 9.0 * act
        for syn in self._synapses:
            ax, ay, ad = pt(syn, "a")
            bx, by, bd = pt(syn, "b")
            prof = (ad * 0.5 + 0.5 + bd * 0.5 + 0.5) * 0.5
            energia = syn["energy"]
            es_nucleo = syn.get("a") == "nucleo"
            al = int((105 + 125 * prof * (0.5 + act) + 190 * energia)
                     * glitch * brillo)
            al = min(255, al)
            col = NARANJA if (energia > 0.12 or es_nucleo) else GRIS
            if es_nucleo or energia > 0.1:
                pen_alpha = min(255, al)
                pen_width = 2.4 if es_nucleo else 2.0
            else:
                pen_alpha = min(160, al)
                pen_width = 1.2
            painter.setPen(QPen(QColor(*col, pen_alpha), pen_width))
            try:
                self._draw_onda(painter, ax, ay, bx, by, self._t, amp_onda)
            except Exception:
                painter.drawLine(QPointF(ax, ay), QPointF(bx, by))

        # Impulsos de luz + rastro.
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

        # Nodos con color de estado real.
        for i, nd in enumerate(self._nodes):
            sx, sy, d, _z = proj[i]
            estado = self.state_of(nd["name"])
            color = ESTADO_COLOR[estado]
            born = nd.get("born", 1.0)
            alpha = int((95 + 110 * act + 70 * self._flash) * d * brillo *
                        (0.25 + 0.75 * born))
            tam = (0.9 + (0.8 + 2.4 * act) * d) * (0.5 + 0.5 * born)
            if estado == "working":
                tam *= 1.35
                alpha = min(255, alpha + 60)
            elif estado == "ok":
                alpha = min(255, alpha + 25)
            painter.setBrush(QBrush(QColor(*color, min(230, alpha))))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPointF(sx, sy), tam, tam)

        # Micro-puntos de datos.
        for dp in self._data_pts:
            sx, sy, d, _z = self._project(dp["p"], cx, cy, f, R)
            flick = 0.5 + 0.5 * (math.sin(self._t * dp["f1"] + dp["ph1"]) *
                                 math.cos(self._t * dp["f2"] + dp["ph2"]))
            al = int(80 * d * flick * glitch * brillo)
            painter.setBrush(QBrush(QColor(*DORADO, al)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPointF(sx, sy), 0.8, 0.8)

        # Nucleo denso (IGRIS).
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

        # Chispas que escapan del núcleo.
        for sp in self._sparks:
            sx, sy, d, _z = self._project(sp["p"], cx, cy, f, R)
            vida = max(0.0, sp["life"] / sp["max"])
            al = int(190 * vida * d * brillo)
            if al >= 4:
                painter.setBrush(QBrush(QColor(*AMBAR, min(220, al))))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(QPointF(sx, sy),
                                    0.9 + 1.4 * vida, 0.9 + 1.4 * vida)

        # Destello del núcleo (lens flare) y estrías.
        flare = QRadialGradient(cx, cy, R * 0.5)
        flare.setColorAt(0.0, QColor(255, 240, 190, int(170 * brillo)))
        flare.setColorAt(0.18, QColor(255, 205, 110, int(85 * brillo)))
        flare.setColorAt(0.45, QColor(255, 165, 70, int(28 * brillo)))
        flare.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(flare))
        painter.drawEllipse(QPointF(cx, cy), R * 0.5, R * 0.5)
        for ang in (0.0, math.pi * 0.5):
            dx, dy = math.cos(ang), math.sin(ang)
            streak = QLinearGradient(cx - dx * R * 0.85, cy - dy * R * 0.85,
                                     cx + dx * R * 0.85, cy + dy * R * 0.85)
            streak.setColorAt(0.0, QColor(255, 200, 90, 0))
            streak.setColorAt(0.5, QColor(255, 215, 120, int(150 * brillo)))
            streak.setColorAt(1.0, QColor(255, 200, 90, 0))
            painter.setPen(QPen(QBrush(streak), 1.6))
            painter.drawLine(QPointF(cx - dx * R * 0.85, cy - dy * R * 0.85),
                             QPointF(cx + dx * R * 0.85, cy + dy * R * 0.85))

        # Etiquetas: texto legible (sin mezcla aditiva) para nodos activos,
        # con resultado o bajo el cursor.
        painter.setCompositionMode(
            QPainter.CompositionMode.CompositionMode_SourceOver)
        fuente = QFont("Consolas", 7)
        fuente.setBold(False)
        painter.setFont(fuente)
        for i, nd in enumerate(self._nodes):
            estado = self.state_of(nd["name"])
            if estado == "pending" and i != self._hover:
                continue
            sx, sy, d, _z = proj[i]
            color = ESTADO_COLOR[estado]
            texto = nd["name"] + (" ●" if estado == "working" else "")
            al = int(230 * d * brillo)
            painter.setPen(QPen(QColor(*color, al), 1.0))
            painter.drawText(QPointF(sx, sy + 12), texto)

    # ------------------------------------------------------------------
    # Interaccion
    # ------------------------------------------------------------------
    def _node_at(self, x, y):
        w = self.width()
        h = self.height()
        cx, cy = w / 2.0, h / 2.0
        R = min(w, h) * 0.46
        for i, nd in enumerate(self._nodes):
            sx, sy, _d, _z = self._project(nd["p"], cx, cy, 2.6, R)
            if math.hypot(sx - x, sy - y) < 22.0:
                return i
        return None

    def mouseMoveEvent(self, event):
        pos = event.position()
        idx = self._node_at(pos.x(), pos.y())
        if idx != self._hover:
            self._hover = idx
            if idx is not None:
                self.setCursor(Qt.CursorShape.PointingHandCursor)
            else:
                self.unsetCursor()
            self._mark_dirty()
            self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        if self._hover is not None:
            self._hover = None
            self.unsetCursor()
            self._mark_dirty()
            self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        pos = event.position()
        idx = self._node_at(pos.x(), pos.y())
        if idx is not None:
            nd = self._nodes[idx]
            self.nodeActivated.emit(
                nd["name"], nd["description"], nd["risk"],
                self.state_of(nd["name"]))
        super().mousePressEvent(event)


# Alias de compatibilidad con el nombre anterior del widget.
HoloEsfera = GalaxiaWidget
