import requests
import smtplib
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import re
import random
from groq import Groq
import datetime
import os
import json
import urllib.parse
import base64

# --- GENERADOR DE LLAVES SEGURO ---
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
secrets_path = os.path.join(BASE_DIR, 'client_secrets.json')
token_path = os.path.join(BASE_DIR, 'token.pickle')

if "GOOGLE_JSON" in os.environ:
    print(f"[INFO] Generando credenciales en: {secrets_path}")
    with open(secrets_path, "w") as f:
        f.write(os.environ["GOOGLE_JSON"])
else:
    print("[INFO] Usando archivo local si existe...")

if "TOKEN_PICKLE_BASE64" in os.environ:
    print("[INFO] Generando token.pickle desde los Secretos de GitHub...")
    with open(token_path, "wb") as f:
        f.write(base64.b64decode(os.environ["TOKEN_PICKLE_BASE64"]))
        
# --- 1. CONFIGURACIÓN ---
# Así el bot busca las llaves en los Secretos de GitHub (o usa las locales por defecto)
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "GROQ_API_KEY")
MODELO = "llama-3.1-8b-instant"

# Directorio base (para que funcione en PythonAnywhere sin perderse)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Datos Facebook (IMPORTANTE: Usa el token de PÁGINA que sacamos)
FB_PAGE_TOKEN = os.environ.get("FB_PAGE_TOKEN")
FB_PAGE_ID = "me" # "me" funciona si el token es de la página
BLOG_ID = os.environ.get("BLOG_ID")
URL_BLOG = os.environ.get("URL_BLOG", "https://viniloandbit.blogspot.com") # Reemplazar con tu URL

# --- HISTORIAL DE PUBLICACIONES ---
HISTORIAL_FILE = os.path.join(BASE_DIR, 'historial.json')

def cargar_historial():
    if os.path.exists(HISTORIAL_FILE):
        try:
            with open(HISTORIAL_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: return []
    return []

def guardar_historial(tema_nuevo, max_items=50):
    historial = cargar_historial()
    historial.append(tema_nuevo)
    historial = historial[-max_items:] # Guardamos solo los últimos 50 para no marear a la IA
    with open(HISTORIAL_FILE, 'w', encoding='utf-8') as f:
        json.dump(historial, f, ensure_ascii=False, indent=4)

# --- IMÁGENES GENÉRICAS DE ROCK ---
# Como ya no leemos noticias con fotos, usamos imágenes libres de derechos de alta calidad
IMAGENES_ROCK = [
    "https://images.unsplash.com/photo-1498038432885-c6f3f1b912ee?q=80&w=1000&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1459749411175-04bf5292ceea?q=80&w=1000&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1511735111819-9a3f7709049c?q=80&w=1000&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1470229722913-7c090be5c560?q=80&w=1000&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1501612780327-45045538702b?q=80&w=1000&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1514525253161-7a46d19cd819?q=80&w=1000&auto=format&fit=crop", # Luces de concierto
    "https://images.unsplash.com/photo-1598488035139-bdbb2231ce04?q=80&w=1000&auto=format&fit=crop", # Cassettes retro
    "https://images.unsplash.com/photo-1614613535308-eb5fbd3d2c17?q=80&w=1000&auto=format&fit=crop", # Tocadiscos / Vinilo
    "https://images.unsplash.com/photo-1516450360452-9312f5e86fc7?q=80&w=1000&auto=format&fit=crop", # Festival
    "https://images.unsplash.com/photo-1445985543470-41fba5c3144a?q=80&w=1000&auto=format&fit=crop", # Colección de discos
    "https://images.unsplash.com/photo-1598387181032-a3103a2db5b3?q=80&w=1000&auto=format&fit=crop", # Guitarra eléctrica
    "https://images.unsplash.com/photo-1464375117522-1314d6c469e8?q=80&w=1000&auto=format&fit=crop"  # Micrófono vintage
]

client = Groq(api_key=GROQ_API_KEY)


# --- 3. REDACCIÓN CON IA ---
def transformar_con_ia(tema, historial_reciente=None):
    try:
        prompt = f"""
        Actúa como el bot redactor estrella de 'Vinilo & Bit', un blog y comunidad donde unimos la nostalgia analógica del vinilo con la inmediatez digital. 
        Tu especialidad es la historia, actualidad y curiosidades del rock de los 80, 90 y 00.
        Tu tarea es escribir un artículo fascinante, original y con actitud sobre: {tema}.
        
        REGLAS DE ORO PARA EL POST:
        1. FORMATO TÉCNICO (OBLIGATORIO):
           - Primera línea: SOLO el TÍTULO del artículo. NO escribas "Título:" ni uses comillas.
           - Resto: Cuerpo del artículo en HTML (<p>, <ul>, <li>, <strong>, <h3>, <a>). NO uses Markdown ni asteriscos.

        2. ESTRUCTURA DEL CONTENIDO:
           - TÍTULO: Atractivo, estilo "clickbait" pero informativo e intrigante (ej: "El secreto oscuro detrás de la canción más famosa de Queen").
           - 🎸 <strong>Datos que no sabías / Desarmando la Letra:</strong> Lista <ul> con 3 curiosidades increíbles o el análisis de la letra traducida al español (si es una canción).
           - 📖 <strong>La Historia:</strong> Un desarrollo apasionante de 2 o 3 párrafos <p>.
           - 📺 <strong>¡Dale Play!:</strong> Un párrafo recomendando buscar el tema o concierto. DEBES incluir obligatoriamente al final esta etiqueta exacta: [BOTONES: Artista+Tema] (reemplazando "Artista+Tema" por las palabras clave reales unidas por el signo +).
           - 🗣️ <strong>El Debate:</strong> Termina SIEMPRE con una pregunta polémica o abierta para que los fans comenten <p>.
           - � <strong>REGLA VITAL:</strong> NUNCA traduzcas los nombres de las canciones, álbumes o bandas al español. Mantenlos SIEMPRE en su idioma original (ej. NO digas "Novedad de Noviembre", debes decir "November Rain").

        3. PERSONALIDAD:
           - Usá un lenguaje muy coloquial, 100% argentino, con "voseo" directo (ej: "Mirá esta locura", "No lo vas a poder creer", "Contanos qué opinás").
           - Tu estilo es el de alguien que ama la era del vinilo y el cassette, pero que domina el mundo digital (tu lema es "El eco del rock, de la púa al algoritmo").
        """
        
        if historial_reciente:
            prompt += f"\n\n🚨 REGLA ESTRICTA DE NO REPETICIÓN:\nYa hemos publicado recientemente sobre estos temas/títulos:\n{historial_reciente}\n"
            prompt += "PROHIBIDO escribir sobre la misma anécdota, dato o canción. Busca un ángulo o historia completamente diferente."

        completion = client.chat.completions.create(
            model=MODELO,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
        )
        
        respuesta = completion.choices[0].message.content
        lineas = respuesta.split('\n')
        
        # Limpieza agresiva del título para sacar "Título atractivo:" y asteriscos
        raw_title = lineas[0]
        raw_title = re.sub(r'<[^>]+>', '', raw_title) # Eliminar etiquetas HTML del título si la IA las puso
        clean_title = re.sub(r'^(Título|Titulo|Título atractivo|Titulo atractivo|Asunto)[:\s-]*', '', raw_title, flags=re.IGNORECASE)
        nuevo_titulo = clean_title.replace('**', '').replace('*', '').replace('"', '').strip()
        
        cuerpo = "\n".join(lineas[1:])
        cuerpo = cuerpo.replace('**', '') # Eliminar asteriscos si la IA no obedeció
        
        # Generar los botones HTML automáticamente reemplazando el placeholder
        def armar_botones(match):
            query = match.group(1)
            html_botones = f'<br><br><a href="https://www.youtube.com/results?search_query={query}" target="_blank" style="display: inline-block; background-color: #ff0000; color: white; padding: 10px 15px; border-radius: 5px; text-decoration: none; font-weight: bold; margin-right: 10px;">▶️ Ver en YouTube</a> <a href="https://open.spotify.com/search/{query}" target="_blank" style="display: inline-block; background-color: #1DB954; color: white; padding: 10px 15px; border-radius: 5px; text-decoration: none; font-weight: bold;">🎧 Escuchar en Spotify</a>'
            return html_botones
            
        cuerpo = re.sub(r'\[BOTONES:\s*(.+?)\]', armar_botones, cuerpo, flags=re.IGNORECASE)
        
        return nuevo_titulo, cuerpo
    except: return None, None

# --- GENERADOR DE IMÁGENES CON IA ---
def obtener_imagen_ia(banda):
    # Creamos un prompt descriptivo en inglés para la IA generadora
    prompt_img = f"Cinematic photography of a rock and roll music concept, vintage 1990s style, vinyl records, stage neon lights, musical vibe inspired by {banda}, highly detailed, 8k resolution, photorealistic"
    prompt_encoded = urllib.parse.quote(prompt_img)
    # Usamos Pollinations (gratis, sin API Key, genera imagen JPG al vuelo)
    return f"https://image.pollinations.ai/prompt/{prompt_encoded}?width=1024&height=768&nologo=true"

from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from googleapiclient.errors import HttpError
import pickle

# Esta función se encarga de entrar a tu Blogger sin usar mails
def obtener_servicio_blogger():
    scopes = ['https://www.googleapis.com/auth/blogger']
    creds = None
    
    token_path = os.path.join(BASE_DIR, 'token.pickle')
    secrets_path = os.path.join(BASE_DIR, 'client_secrets.json')
    
    # Guardamos el "permiso" en un archivo para no tener que loguearnos cada vez
    if os.path.exists(token_path):
        print("[INFO] Cargando token de sesión de Blogger...")
        with open(token_path, 'rb') as token:
            creds = pickle.load(token)
    else:
        print("[ALERTA] No se encontró 'token.pickle'. El bot intentará abrir un navegador (fallará en la nube).")
            
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("[INFO] Refrescando token de Google...")
            creds.refresh(Request())
        else:
            # Aquí es donde usamos el archivo que bajaste de Google Cloud
            # IMPORTANTE: En GitHub Actions esto fallará si no subes el token.pickle
            if not os.path.exists(secrets_path):
                print("[ERROR] No existe client_secrets.json ni token válido. No se puede autenticar en Blogger.")
                return None
            flow = InstalledAppFlow.from_client_secrets_file(secrets_path, scopes)
            creds = flow.run_local_server(port=0)
            
        with open(token_path, 'wb') as token:
            pickle.dump(creds, token)
            
    return build('blogger', 'v3', credentials=creds)

def publicar_en_blogger_api(titulo, contenido_html, imagen_url, etiquetas=None):
    # --- ESTILOS VISUALES (CSS INLINE) ---
    estilo_contenedor = "font-family: 'Georgia', 'Times New Roman', serif; font-size: 18px; line-height: 1.8; color: #2c3e50; max-width: 800px; margin: 0 auto;"
    estilo_h2 = "color: #d35400; font-family: 'Helvetica', 'Arial', sans-serif; font-weight: bold; margin-top: 30px; border-bottom: 2px solid #f39c12; padding-bottom: 5px;"
    estilo_img = "width: 100%; height: auto; border-radius: 10px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); margin-bottom: 20px;"
    estilo_footer = "background-color: #ecf0f1; padding: 20px; border-radius: 10px; margin-top: 40px; font-family: 'Arial', sans-serif; font-size: 15px; text-align: center; color: #7f8c8d;"

    # Inyectamos los estilos
    contenido_estilizado = contenido_html.replace('<h2>', f'<h2 style="{estilo_h2}">')
    contenido_estilizado = contenido_estilizado.replace('<h3>', f'<h2 style="{estilo_h2}">')
    
    # Construimos el HTML final para la API
    cuerpo_final = f'<div style="{estilo_contenedor}">'
    if imagen_url:
        cuerpo_final += f'<img src="{imagen_url}" alt="{titulo}" style="{estilo_img}" />'
    
    cuerpo_final += f'<div>{contenido_estilizado}</div>'
    cuerpo_final += f'<div style="{estilo_footer}">💿 <strong>¡Gracias por leer! Somos Vinilo & Bit: El eco del rock, de la púa al algoritmo.</strong><br><br>Si el rock es tu ADN y te copó esta historia, compartila con tus amigos.<br><em>Seguinos en <a href="https://www.facebook.com/viniloandbit" style="color: #3b5998; text-decoration: none; font-weight: bold;">Facebook</a> y visitá nuestro <a href="{URL_BLOG}" style="color: #e67e22; text-decoration: none; font-weight: bold;">Blog</a> para más contenido.</em></div>'
    cuerpo_final += '</div>'
    
    try:
        service = obtener_servicio_blogger()
        if not service:
            print("[ERROR] Saltando publicación en Blogger por falta de credenciales.")
            return False
        
        if not BLOG_ID:
            print("[ERROR] No se encontró BLOG_ID. Saltando publicación en Blogger.")
            return False
        
        body = {
            "kind": "blogger#post",
            "title": titulo,
            "content": cuerpo_final
        }
        
        if etiquetas:
            body["labels"] = etiquetas
            
        # Reintentos ante error de cuota (429)
        for i in range(3):
            try:
                service.posts().insert(blogId=BLOG_ID, body=body).execute()
                return True
            except HttpError as e:
                if e.resp.status == 429:
                    print(f"[ALERTA] Cuota Blogger excedida. Esperando {60*(i+1)}s...")
                    time.sleep(60 * (i + 1))
                else:
                    raise e
        return False
    except Exception as e:
        print(f"[ERROR] API Blogger: {e}")
        return False

def publicar_en_facebook(titulo, cuerpo_ia, imagen_url, hashtags="", incluir_link=True):
    if not FB_PAGE_TOKEN:
        print("[ALERTA] No se encontró FB_PAGE_TOKEN en el entorno local. Saltando publicación en Facebook.")
        return False
        
    # Limpiamos el HTML para Facebook
    texto_formateado = cuerpo_ia.replace('<li>', '⚡ ').replace('</li>', '\n') # Viñetas más vistosas
    texto_formateado = texto_formateado.replace('<p>', '').replace('</p>', '\n')
    texto_formateado = texto_formateado.replace('<br>', '\n').replace('<br/>', '\n')
    
    texto_limpio = re.sub('<[^<]+?>', '', texto_formateado)
    lineas = [line.strip() for line in texto_limpio.splitlines() if line.strip()]
    
    # Armamos un "Teaser" (adelanto) tomando solo los primeros 4 párrafos/viñetas
    texto_teaser = "\n\n".join(lineas[:4])
    if len(lineas) > 4:
         texto_teaser += "\n\n[...]"
         
    separador = "━━━━━━━━━ 🎸 ━━━━━━━━━"
    
    if incluir_link:
        mensaje_final = f"🔥 ¡NUEVO POST EN VINILO & BIT! 🔥\n\n{separador}\n\n🚨 {titulo}\n\n{texto_teaser}\n\n{separador}\n\n👇 ¡NO TE QUEDES A MEDIAS! LEÉ LA HISTORIA COMPLETA ACÁ 👇\n🔗 {URL_BLOG}\n\n{hashtags}"
    else:
        mensaje_final = f"🔥 ¡DATAZO ROCKERO! 🔥\n\n{separador}\n\n🚨 {titulo}\n\n{texto_teaser}\n\n{separador}\n\n🗣️ ¡Dejanos tu comentario abajo, te leemos!\n\n{hashtags}"
    
    if imagen_url:
        url_fb = f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/photos?access_token={FB_PAGE_TOKEN}"
        payload = {'message': mensaje_final}
        try:
            # Descargamos la imagen y verificamos que sea realmente una foto válida
            img_response = requests.get(imagen_url, timeout=20)
            if img_response.status_code == 200 and 'image' in img_response.headers.get('Content-Type', '').lower():
                img_data = img_response.content
                files = {'source': ('imagen.jpg', img_data, 'image/jpeg')}
                r = requests.post(url_fb, data=payload, files=files)
            else:
                print(f"[ALERTA] La IA de imágenes falló (Status: {img_response.status_code}). Publicando sin foto en FB...")
                url_fb_feed = f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/feed?access_token={FB_PAGE_TOKEN}"
                r = requests.post(url_fb_feed, data=payload)
        except Exception as e:
            print(f"[ERROR] Descargando imagen para FB: {e}")
            url_fb_feed = f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/feed?access_token={FB_PAGE_TOKEN}"
            r = requests.post(url_fb_feed, data=payload)
    else:
        url_fb = f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/feed?access_token={FB_PAGE_TOKEN}"
        payload = {'message': mensaje_final}
        r = requests.post(url_fb, data=payload)
    
    try:
        if r.status_code == 200:
            print("[OK] Publicado en Facebook con éxito!")
        else:
            print(f"[ALERTA] Detalle del error: {r.json().get('error').get('message')}")
    except Exception as e:
        print(f"[ERROR] Conexión FB: {e}")

# --- 4. GENERACIÓN DE CONTENIDO DE ROCK ---
def ejecutar_bot_rock():
    # Listas para generar temáticas aleatorias
    bandas = [
        # Clásicos 70s y 80s
        "Queen", "Rolling Stones", "Pink Floyd", "Led Zeppelin", "AC/DC", 
        "Guns N' Roses", "KISS", "Aerosmith", "The Doors", "The Cure", "Depeche Mode", "Bon Jovi",
        # 90s y 00s (Grunge, Alternativo, Britpop, Nu Metal)
        "Nirvana", "Pearl Jam", "Red Hot Chili Peppers", "Foo Fighters", "Oasis", "Blur",
        "Radiohead", "Green Day", "Linkin Park", "Blink-182", "Arctic Monkeys", "The Strokes",
        # Rock Nacional Argentino
        "Soda Stereo", "Patricio Rey y sus Redonditos de Ricota", "Charly García", "Spinetta",
        "Los Fabulosos Cadillacs", "Divididos", "Babasónicos", "Andrés Calamaro", "Enanitos Verdes"
    ]
    enfoques = [
        "la historia oculta de uno de sus mayores éxitos", 
        "datos curiosos que casi nadie conoce", 
        "una anécdota loca de sus giras", 
        "el significado real de su mejor álbum", 
        "su concierto más legendario y desastroso", 
        "los conflictos internos que casi destruyen la banda"
    ]
    
    hoy = datetime.datetime.now()
    meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
    fecha_actual = f"{hoy.day} de {meses[hoy.month - 1]}"
    
    tipo_post = random.choice(["efemerides", "historia", "cancion"])
    banda_elegida = random.choice(bandas) # Elegimos una banda para basar el estilo de la imagen
    
    if tipo_post == "efemerides":
        tema_elegido = f"Efemérides del Rock: Un evento histórico real, nacimiento, fallecimiento o lanzamiento de un álbum icónico que haya ocurrido exactamente un {fecha_actual} (o en fechas muy cercanas) en la historia del Rock."
        hashtags = "#ViniloAndBit #Rock80s #Rock90s #Rock00s #Efemérides #UnDíaComoHoy #HistoriaDelRock"
        etiquetas_blog = ["Efemérides", "Historia del Rock"]
    elif tipo_post == "historia":
        tema_elegido = f"{banda_elegida} y {random.choice(enfoques)}"
        hashtags = "#ViniloAndBit #Rock80s #Rock90s #Rock00s #HistoriaDelRock #Curiosidades #RockBands"
        etiquetas_blog = ["Curiosidades", banda_elegida, "Bandas Legendarias"]
    else:
        tema_elegido = f"Análisis profundo de una canción icónica de {banda_elegida}. Debes desenmarañar y explicar su letra, el significado oculto, la historia detrás de la composición y traducir las partes clave del tema al español explicando exactamente de qué habla."
        hashtags = "#ViniloAndBit #SignificadoDeCanciones #AnalisisDeLetras #HistoriaDelRock #Rock80s #Rock90s"
        etiquetas_blog = ["Análisis de Letras", banda_elegida, "Significado Oculto"]

    # Generamos una imagen única con IA para cada artículo
    imagen_elegida = obtener_imagen_ia(banda_elegida)
    imagen_generada = obtener_imagen_ia(banda_elegida)
    print("[INFO] Validando y pre-cargando imagen de IA...")
    try:
        # Hacemos un GET para obligar a la IA a generar la imagen ahora y verificar que no esté rota
        res_img = requests.get(imagen_generada, timeout=30)
        if res_img.status_code == 200 and 'image' in res_img.headers.get('Content-Type', '').lower():
            imagen_elegida = imagen_generada
        else:
            print("[ALERTA] Imagen de IA rota. Usando foto de repuesto del banco de imágenes.")
            imagen_elegida = random.choice(IMAGENES_ROCK)
    except Exception as e:
        print(f"[ALERTA] Tiempo de espera agotado o error en IA: {e}. Usando repuesto.")
        imagen_elegida = random.choice(IMAGENES_ROCK)

    historial = cargar_historial()
    print(f"[INFO] Generando artículo sobre: {tema_elegido}")
    nuevo_titulo, cuerpo = transformar_con_ia(tema_elegido, historial_reciente=historial)
    
    if nuevo_titulo and cuerpo:
        print("\n" + "="*50)
        print(f"🎸 TÍTULO GENERADO: {nuevo_titulo}")
        print("="*50)
        print(f"Cuerpo del artículo:\n{cuerpo}")
        print("="*50 + "\n")

        exito_blogger = publicar_en_blogger_api(nuevo_titulo, cuerpo, imagen_elegida, etiquetas=etiquetas_blog)
        
        # ESTRATEGIA ALGORITMO: 30% de las veces NO ponemos link en Facebook para ganar alcance orgánico
        poner_link_fb = random.random() < 0.7 
        
        if exito_blogger:
            print("[OK] Publicado en Blogger")
            publicar_en_facebook(nuevo_titulo, cuerpo, imagen_elegida, hashtags, incluir_link=poner_link_fb)
            
            # Guardamos el título en el historial para que no se repita a futuro
            guardar_historial(f"[{tipo_post.upper()}] {banda_elegida}: {nuevo_titulo}")
        else:
            print("[ALERTA] Falló Blogger, publicando solo en Facebook...")
            publicar_en_facebook(nuevo_titulo, cuerpo, imagen_elegida, hashtags, incluir_link=False)
        return True
    return False

def iniciar_publicacion_rock():
    print("[INFO] --- Iniciando publicación de Rock vIcmAr ---")
    if ejecutar_bot_rock():
        print("[INFO] Publicación completada con éxito.")
    else:
        print("[ERROR] No se pudo generar la publicación.")

if __name__ == "__main__":
    print(f"--- [vIcmAr CLOUD - ROCK EDITION] ---")
    try:
        iniciar_publicacion_rock()
        print("[OK] Proceso finalizado.")
    except Exception as e:
        print(f"[ERROR]: {e}")
        
        
