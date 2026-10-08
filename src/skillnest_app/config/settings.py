import os

from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise RuntimeError(
        "GEMINI_API_KEY no está definida. "
        "Revise el archivo .env o las variables de entorno."
    )

print("Configuración válida")