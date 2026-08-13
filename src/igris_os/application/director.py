import re

from igris_os.domain import Mission, MissionBranch, MissionPlan


class MissionDirector:
    _ROUTES = (
        (MissionBranch.GAMES, ("videojuego", "juego", "godot", "unity", "unreal", "pygame")),
        (MissionBranch.VIDEO, ("video", "ffmpeg", "montaje", "render")),
        (MissionBranch.AUDIO, ("audio", "sonido", "voz", "musica", "transcribir")),
        (MissionBranch.IMAGE, ("imagen", "foto", "icono", "diseño", "sprite")),
        (MissionBranch.ARTIFICIAL_INTELLIGENCE, ("inteligencia artificial", "modelo", "ia", "rag", "entrenar")),
        (MissionBranch.PROGRAMMING, ("programa", "codigo", "python", "typescript", "javascript", "rust", "c++", "java")),
        (MissionBranch.DOCUMENTS, ("documento", "pdf", "excel", "archivo", "carpeta")),
        (MissionBranch.SYSTEMS, ("windows", "ordenador", "cpu", "ram", "sistema")),
    )

    def plan(self, mission: Mission) -> MissionPlan:
        text = re.sub(r"\s+", " ", mission.objective.casefold()).strip()
        branch = MissionBranch.GENERAL
        for candidate, terms in self._ROUTES:
            if any(re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text) for term in terms):
                branch = candidate
                break
        return MissionPlan(
            mission.id, branch,
            ("inspeccionar contexto", "definir entregables y riesgos",
             f"ejecutar especialista {branch.value}",
             "verificar con pruebas independientes", "entregar evidencias y rollback"),
            ("cumple el objetivo", "sin errores criticos", "respeta permisos"),
            len(text.split()) < 3,
        )
