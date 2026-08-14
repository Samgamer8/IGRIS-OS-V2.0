from tools.align_voice_transcripts import align, normalized


def test_normalization_handles_spanish_accents():
    assert normalized("Configuración, misión.") == "configuracion mision"


def test_alignment_corrects_recognition_errors_sequentially():
    reference = "IGRIS analiza archivos. Después ejecuta todas las pruebas."
    records = [
        {"text": "Igris analisa archivos", "source_part": 1},
        {"text": "despues ejecuta todas las palabras", "source_part": 1},
    ]
    result = align(records, reference)
    assert result[0]["text"] == "IGRIS analiza archivos."
    assert "pruebas." in result[1]["text"]
    assert result[1]["alignment_score"] > 0.7


def test_alignment_recovers_exact_text_outside_current_window():
    reference = "Primera frase correcta. Texto intermedio muy largo. Última frase."
    records = [
        {"text": "ultima frase", "source_part": 1},
        {"text": "primera frase correcta", "source_part": 1},
    ]
    result = align(records, reference)
    assert result[1]["text"] == "Primera frase correcta."
    assert not result[1]["requires_text_review"]
