AGENT_PROFILES = {
    'auto': '',
    'director': 'Priorice objetivos, dependencias, riesgos y criterios de entrega.',
    'programmer': 'Priorice implementacion concreta, casos limite y pruebas reproducibles.',
    'reviewer': 'Priorice fallos, seguridad, regresiones y evidencia; no de por correcto lo no verificado.',
    'researcher': 'Priorice referencias contrastadas y distinga hechos, inferencias e incertidumbre.',
}
OUTPUT_LIMITS = {'auto': None, 'light': 512, 'balanced': 1024, 'advanced': 2048}


def preference_context(settings):
    profile = AGENT_PROFILES.get(settings.get('conversation_agent', 'auto'), '')
    return ((f'Perfil elegido por el usuario: {profile} No cambia permisos ni autoriza ejecucion.',)
            if profile else ())


def output_limit(settings):
    return OUTPUT_LIMITS.get(settings.get('resource_mode', 'auto'))