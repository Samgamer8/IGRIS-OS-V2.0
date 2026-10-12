// Núcleo de Conexión Oficial de Igris OS - FreeLLMAPI & GitHub
const { OpenAI } = require('openai');

const openai = new OpenAI({
  baseURL: 'http://localhost:3001/v1',
  apiKey: 'freellmapi-no-key-needed'
});

async function enviarOrdenAI(ordenUsuario) {
  try {
    const respuesta = await openai.chat.completions.create({
      model: 'gpt-4o-mini',
      messages: [
        {
          role: 'system',
          content: 'Eres el motor interno y Programador Jefe Autónomo de Igris OS en Windows. RESPONDE SIEMPRE EN CASTELLANO. Prohibido el texto de relleno, saludos o introducciones. Sé directo, escueto y al grano para ahorrar tokens al máximo.'
        },
        { role: 'user', content: ordenUsuario }
      ],
      temperature: 0.3
    });
    return respuesta.choices.message.content;
  } catch (error) {
    return 'Error crítico en el enlace de Igris OS: ' + error.message;
  }
}

// Exportar la función para que el sistema de Igris OS la use
module.exports = { enviarOrdenAI };

// Prueba rápida de ejecución en consola
enviarOrdenAI('hola').then(console.log);
