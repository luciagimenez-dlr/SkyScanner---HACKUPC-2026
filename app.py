"""
WanderLens - AI Travel Experience Platform
==========================================
Punt d'entrada principal de l'aplicació Flask.

COM EXECUTAR:
-------------
1. Instal·la dependències:
   pip install flask flask-cors google-generativeai requests python-dotenv

2. Crea un fitxer .env a la carpeta arrel amb:
   GEMINI_API_KEY=AIzaSyD_Inf8KJk09wNE0_xnWL7_5zQCsPWSqRk
   SKYSCANNER_API_KEY=la_teva_clau_de_skyscanner
   (Obté la clau Skyscanner a: https://developers.skyscanner.net/docs/intro)

3. Executa:
   python app.py

4. Obre el navegador a: http://localhost:5000
"""

from flask import Flask, render_template
from flask_cors import CORS
from dotenv import load_dotenv
import os

load_dotenv()

# --- Importa els Blueprints (un per cada part de la web) ---
from blueprints.input_bp import input_bp       # Part 1: Perfil d'usuari + VR upload
from blueprints.search_bp import search_bp     # Part 2: Buscador AI + rutes
from blueprints.api_bp import api_bp           # Part 3: API intermediària (Skyscanner, Gemini)

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "wanderlens-dev-secret-2024")

CORS(app)


app.register_blueprint(input_bp,  url_prefix="/input")   # /input/...
app.register_blueprint(search_bp, url_prefix="/search")  # /search/...
app.register_blueprint(api_bp,    url_prefix="/api")     # /api/...


@app.route("/")
def index():
    return render_template("index.html")


if __name__ == "__main__":
    # debug=True → recàrrega automàtica en guardar canvis
    app.run(debug=True, port=5000)
