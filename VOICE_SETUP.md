# Voz de referencia local

La interfaz usa `assets/igris_voice_identity.wav` como referencia de Chatterbox
Multilingual con los pesos oficiales `ResembleAI/Chatterbox-Multilingual-es-es`
y su decodificador V3 para generar respuestas en espanol de Espana. No se limita a reproducir
la muestra. El audio y el texto se procesan localmente; la primera generacion
descarga los pesos oficiales del modelo de Hugging Face.

## Instalacion en Windows

Configuracion verificada en este equipo: Python 3.14, PyTorch 2.11 con CUDA 12.8
y RTX 5060 Ti. El entorno de voz es independiente del Python principal de IGRIS.
Desde la raiz del proyecto:

```powershell
py -3.14 -m venv .venv-voice
.\.venv-voice\Scripts\python.exe -m pip install torch==2.11.0 torchaudio==2.11.0 --index-url https://download.pytorch.org/whl/cu128
.\.venv-voice\Scripts\python.exe -m pip install chatterbox-tts==0.1.7
```

Reinicia IGRIS y activa la voz. Al activarla se sintetiza una frase nueva usando
la referencia. Las respuestas se generan en segundo plano y por segmentos.
Mientras suena un segmento se prepara el siguiente, sin alterar el orden.
Los parametros de la referencia se reutilizan mientras el WAV no cambie.
La primera frase tarda mas mientras carga el modelo. Este comparte la memoria
de la GPU con Ollama y los demas programas. En la prueba de este equipo, la carga
inicial tardo entre 21 y 31 segundos; los segmentos siguientes, entre 3 y 5.
Con tres frases consecutivas las dos pausas medidas fueron de 0,00 segundos.
Estas cifras corresponden al motor multilingue anterior y no son garantias:
dependen del modelo, la longitud del texto y la carga. El modelo de Espana requiere
descargar sus pesos adicionales en el primer uso y conserva el solapamiento.

El chat mantiene el modelo de programacion instalado de 7B por defecto y respeta
`IGRIS_CONVERSATION_MODEL` si se configura. Se probo un modelo de 3B pero no se
adopto porque no respetaba bien las instrucciones de sinceridad.

El tono de IGRIS es educado, sereno, firme y directo, con tratamiento de usted por
defecto. No debe dar la razon por complacer, ocultar errores ni prometer resultados
sin evidencia. Estas instrucciones se aplican al chat y a respuestas operativas;
no cambian las autorizaciones de las misiones.

Los fallos aparecen en el chat y en `runtime/voice/voice_identity.log`. Si falla
la sintesis con referencia, no se sustituye silenciosamente por Windows SAPI.
Si falta el archivo de referencia, la interfaz avisa y usa Windows.

## Calidad y uso

La muestra actual dura 20,46 segundos y contiene seis intervenciones del video
`MzSKfXG6MXE`, recortadas, normalizadas y confirmadas por el usuario. Se ha restaurado
esta referencia sin la limpieza adicional porque el usuario detecto un timbre
distinto en el uso real. La version filtrada se conserva en
`runtime/voice/reference/igris_voice_identity_before_restore_*.wav`.

El modelo multilingue general no conservaba el acento deseado. La version actual
usa el modelo especifico de Espana, con carga estricta de los pesos y los filtros
auxiliares calculados por el motor. La generacion fija la semilla y usa la misma
configuracion para las pruebas y la interfaz. El usuario confirmo esta version
escuchando frases nuevas mediante la ruta real de IGRIS.

Las salidas con una duracion sospechosamente corta se reintentan hasta tres veces
con semillas reproducibles 42, 43 y 44. Si siguen siendo demasiado cortas, se informa
del fallo sin reproducirlas. Esta comprobacion es heuristica, no reconocimiento
palabra por palabra. Los parametros de voz y la referencia aprobada se conservan.
La semejanza no esta garantizada: una muestra
mas larga, limpia, sin musica ni otras voces puede mejorar el resultado. Usa solo
grabaciones propias o voces cuyo uso tengas autorizado.

Chatterbox es un proyecto de Resemble AI con licencia MIT y agrega una marca de
agua perceptual al audio generado. Se conserva el comportamiento del motor.
Las frases de la prueba actual estan en `runtime/voice/spain_reference_preview/`.