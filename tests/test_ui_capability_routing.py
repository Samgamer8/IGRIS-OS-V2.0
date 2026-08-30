from igris_os.ui.cinematic import is_capability_query


def test_panel_intercepts_capability_questions_before_generic_chat():
    for question in ("que puedes hacer?", "¿puedes programar?",
                     "¿sabes programar?", "¿puedes crear juegos?"):
        assert is_capability_query(question)
