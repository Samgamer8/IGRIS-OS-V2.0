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

from PyQt6.QtCore import QPointF, Qt, QTimer, pyqtSignal

logger = logging.getLogger(__name__)
from PyQt6.QtGui import (QBrush, QColor, QFont, QPainter, QPen,
                         QPainterPath, QRadialGradient)
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
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
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

        self._timer = QTimer(self)
        self._timer.setInterval(150)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

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
        self._mark_dirty()

    def set_active(self, name: str) -> None:
        """Marca la capacidad ``name`` como en ejecucion (oro)."""
        self._active = name
        self._flash = max(self._flash, 0.9)
        self._activity_target = min(1.0, self._activity_target + 0.6)
        self._mark_dirty()

    def set_result(self, name: str, ok: bool) -> None:
        """Marca la capacidad ``name`` como ok (verde) o error (rojo)."""
        self._states[name] = "ok" if ok else "error"
        if self._active == name:
            self._active = None
        self._flash = max(self._flash, 0.7 if ok else 0.95)
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
        self._mark_dirty()

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
        for _ in range(120):
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
        for _ in range(60):
            u = rnd.uniform(-1, 1)
            ph = math.asin(u)
            th = rnd.uniform(0, 2 * math.pi)
            self._data_pts.append({
                "p": (math.cos(ph) * math.cos(th), math.sin(ph),
                      math.cos(ph) * math.sin(th)),
                "f1": rnd.uniform(0.5, 2.2), "ph1": rnd.uniform(0, 6.28),
                "f2": rnd.uniform(2.5, 6.0), "ph2": rnd.uniform(0, 6.28),
            })

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

        for g_i, group in enumerate(group_names):
            base = 2.0 * math.pi * g_i / len(group_names)
            spread = max(1, len(groups[group]) - 1)
            for k, idx in enumerate(groups[group]):
                name, description, risk = items[idx]
                y = 1.0 - 2.0 * k / spread
                y = max(-0.85, min(0.85, y))
                r = math.sqrt(max(0.08, 1.0 - y * y))
                theta = base + 0.22 * k
                p = (r * math.cos(theta), y * 0.8, r * math.sin(theta))
                quad = (1 if p[0] >= 0 else 0) + (2 if p[2] >= 0 else 2)
                self._nodes.append({
                    "name": name, "description": description, "risk": risk,
                    "p": p, "quad": quad,
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
                "a": "nucleo", "b": groups[group][0], "energy": 0.0,
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
        dt = 1.0 / 30.0
        self._t += dt
        self._flash *= 0.96

        self.ia_activity += (self._activity_target - self.ia_activity) * 0.045
        self.ia_activity *= 0.9955
        self._activity_target *= 0.94
        self.ia_activity = max(0.02, min(1.0, self.ia_activity))
        if self._busy:
            self.ia_activity = max(self.ia_activity, 0.45)

        for nd in self._nodes:
            if nd["born"] < 1.0:
                nd["born"] = min(1.0, nd["born"] + 0.04)

        vel = 0.14 + 0.62 * self.ia_activity
        self._rot += vel * dt

        for syn in self._synapses:
            syn["energy"] *= 0.965
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
                r["e"] *= 0.90

        intervalo = 0.72 - 0.5 * self.ia_activity
        self._pulse_acc += dt
        if self.ia_activity > 0.15 and self._pulse_acc >= intervalo:
            self._pulse_acc = 0.0
            for _ in range(1 + int(self.ia_activity * 3.2)):
                self._lanzar_impulso()

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
    def _draw_onda(painter, x0, y0, x1, y1, t, amp, seg=7):
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

        # Fondo: velo + vineta.
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

        # Proyeccion de nodos.
        proj = []
        for nd in self._nodes:
            x, y, z = nd["p"]
            pulso = self._pulso_cuadrante(nd["quad"], x, y, z)
            wav = 0.5 + 0.5 * math.sin(self._t * nd["f"] + nd["ph"])
            factor = 1.0 + pulso + 0.045 * nd["amp"] * wav
            q = (x * factor, y * factor, z * factor)
            proj.append(self._project(q, cx, cy, f, R * nd["r"]))

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
                painter.setPen(QPen(QColor(*col, min(130, al // 3)),
                                    4.0 if es_nucleo else 3.2))
                self._draw_onda(painter, ax, ay, bx, by, self._t, amp_onda)
            painter.setPen(QPen(QColor(*col, al),
                                2.0 if es_nucleo else 1.5))
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
