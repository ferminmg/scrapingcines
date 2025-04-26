from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
from dotenv import load_dotenv
import os
import json
import requests
import urllib.request
import re
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Cargar variables de entorno
load_dotenv()
TMDB_API_KEY = os.getenv("TMDB_API_KEY")

# Definir carpetas para templates y estáticos
if not os.path.exists('templates'):
    os.makedirs('templates')
if not os.path.exists('static'):
    os.makedirs('static')
if not os.path.exists('static/css'):
    os.makedirs('static/css')
if not os.path.exists('static/js'):
    os.makedirs('static/js')
if not os.path.exists('imagenes_filmoteca'):
    os.makedirs('imagenes_filmoteca')

# Clase para consultar TMDb
class TMDbAPI:
    def __init__(self, api_key):
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json;charset=utf-8"
        }
        self.base_url = "https://api.themoviedb.org/3"

    def _make_request(self, endpoint, params=None):
        try:
            url = f"{self.base_url}/{endpoint}"
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error making request to TMDb: {str(e)}")
            return {}

    def search_movies(self, query, language="es"):
        """Busca películas en TMDB por título"""
        results = self._make_request("search/movie", params={"query": query, "language": language})
        
        if not results or not results.get("results"):
            if language == "es":
                return self.search_movies(query, "en")
            else:
                return []
        
        return sorted(results["results"], key=lambda x: x.get("popularity", 0), reverse=True)

    def get_movie_details(self, movie_id, language="es"):
        """Obtiene detalles de una película de TMDB por ID"""
        details = self._make_request(f"movie/{movie_id}", params={"language": language})
        if not details:
            if language == "es":
                return self.get_movie_details(movie_id, "en")
            return {}
        
        credits = self._make_request(f"movie/{movie_id}/credits", params={"language": language})
        if not credits and language == "es":
            credits = self._make_request(f"movie/{movie_id}/credits", params={"language": "en"})
        
        if not credits:
            credits = {"cast": [], "crew": []}
        
        return {
            "id": details.get("id"),
            "título": details.get("title"),
            "título_original": details.get("original_title"),
            "director": ", ".join(c["name"] for c in credits.get("crew", []) if c["job"] == "Director"),
            "duración": f"{details.get('runtime', 'Desconocido')} min",
            "actores": ", ".join(a["name"] for a in credits.get("cast", [])[:5]),
            "sinopsis": details.get("overview"),
            "año": details.get("release_date", "")[:4] if details.get("release_date") else "",
            "poster_path": details.get("poster_path"),
            "popularidad": details.get("popularity")
        }

    def download_poster(self, poster_path, title):
        """Descarga el póster de una película"""
        if not poster_path:
            return ""
            
        poster_url = f"https://image.tmdb.org/t/p/w500{poster_path}"
        nombre_archivo = f"tmdb_{re.sub(r'[^a-zA-Z0-9]', '_', title)}.jpg"
        ruta_imagen = os.path.join('imagenes_filmoteca', nombre_archivo)
        
        try:
            urllib.request.urlretrieve(poster_url, ruta_imagen)
            return ruta_imagen
        except Exception as e:
            print(f"Error al descargar el póster: {str(e)}")
            return ""

# Inicializar TMDbAPI
tmdb_api = TMDbAPI(TMDB_API_KEY)

def cargar_peliculas():
    """Carga las películas del archivo JSON"""
    try:
        if os.path.exists('peliculas_filmoteca.json'):
            with open('peliculas_filmoteca.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        return []
    except Exception as e:
        print(f"Error al cargar películas: {str(e)}")
        return []

def guardar_peliculas(peliculas):
    """Guarda las películas en el archivo JSON"""
    with open('peliculas_filmoteca.json', 'w', encoding='utf-8') as f:
        json.dump(peliculas, f, ensure_ascii=False, indent=4)

# Función para crear archivos estáticos
def crear_archivos_estaticos():
    # Crear archivo style.css
    with open('static/css/style.css', 'w', encoding='utf-8') as f:
        f.write('''
.card-img-top {
    height: 300px;
    object-fit: cover;
}
        ''')
    
    # Crear archivo script.js
    with open('static/js/script.js', 'w', encoding='utf-8') as f:
        f.write('''
// Script para el administrador de películas
console.log('Administrador de películas cargado');
        ''')
    
    # Crear archivo index.html
    with open('templates/index.html', 'w', encoding='utf-8') as f:
        f.write('''
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Administrador de Películas</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body>
    <div class="container mt-4">
        <h1 class="mb-4">Administrador de Películas</h1>
        
        <div class="row mb-4">
            <div class="col">
                <div class="card">
                    <div class="card-header">
                        <h5>Buscar Película</h5>
                    </div>
                    <div class="card-body">
                        <form id="search-form" method="GET" action="{{ url_for('buscar') }}">
                            <div class="mb-3">
                                <label for="query" class="form-label">Título:</label>
                                <input type="text" class="form-control" id="query" name="query" required>
                            </div>
                            <button type="submit" class="btn btn-primary">Buscar</button>
                        </form>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="row">
            <div class="col">
                <div class="card">
                    <div class="card-header d-flex justify-content-between align-items-center">
                        <h5>Películas Guardadas</h5>
                        <a href="{{ url_for('index') }}" class="btn btn-sm btn-secondary">Actualizar</a>
                    </div>
                    <div class="card-body">
                        <div class="table-responsive">
                            <table class="table table-hover">
                                <thead>
                                    <tr>
                                        <th>Título</th>
                                        <th>Año</th>
                                        <th>Cine</th>
                                        <th>Sesiones</th>
                                        <th>Acciones</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {% for pelicula in peliculas %}
                                    <tr>
                                        <td>{{ pelicula.título }}</td>
                                        <td>{{ pelicula.año }}</td>
                                        <td>{{ pelicula.cine }}</td>
                                        <td>{{ pelicula.horarios|length }}</td>
                                        <td>
                                            <a href="{{ url_for('editar', id=loop.index0) }}" class="btn btn-sm btn-warning">Editar</a>
                                            <a href="{{ url_for('eliminar', id=loop.index0) }}" class="btn btn-sm btn-danger" onclick="return confirm('¿Estás seguro de eliminar esta película?')">Eliminar</a>
                                        </td>
                                    </tr>
                                    {% else %}
                                    <tr>
                                        <td colspan="5" class="text-center">No hay películas guardadas</td>
                                    </tr>
                                    {% endfor %}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    {% with messages = get_flashed_messages(with_categories=true) %}
      {% if messages %}
        <div class="toast-container position-fixed bottom-0 end-0 p-3">
          {% for category, message in messages %}
            <div class="toast show" role="alert" aria-live="assertive" aria-atomic="true">
              <div class="toast-header bg-{{ 'success' if category == 'success' else 'danger' }}">
                <strong class="me-auto text-white">{{ 'Éxito' if category == 'success' else 'Error' }}</strong>
                <button type="button" class="btn-close" data-bs-dismiss="toast" aria-label="Close"></button>
              </div>
              <div class="toast-body">{{ message }}</div>
            </div>
          {% endfor %}
        </div>
      {% endif %}
    {% endwith %}
    
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/js/bootstrap.bundle.min.js"></script>
    <script src="{{ url_for('static', filename='js/script.js') }}"></script>
    <script>
      // Auto hide toasts after 3 seconds
      document.addEventListener('DOMContentLoaded', function() {
        setTimeout(function() {
          var toasts = document.querySelectorAll('.toast.show');
          toasts.forEach(function(toast) {
            var bsToast = new bootstrap.Toast(toast);
            bsToast.hide();
          });
        }, 3000);
      });
    </script>
</body>
</html>
        ''')
    
    # Crear resultados.html
    with open('templates/resultados.html', 'w', encoding='utf-8') as f:
        f.write('''
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Resultados de Búsqueda</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body>
    <div class="container mt-4">
        <h1 class="mb-4">Resultados de Búsqueda</h1>
        
        <div class="mb-3">
            <a href="{{ url_for('index') }}" class="btn btn-secondary">Volver</a>
        </div>
        
        <div class="row">
            {% for pelicula in resultados %}
            <div class="col-md-4 mb-4">
                <div class="card h-100">
                    {% if pelicula.poster_path %}
                    <img src="https://image.tmdb.org/t/p/w500{{ pelicula.poster_path }}" class="card-img-top" alt="{{ pelicula.title }}">
                    {% else %}
                    <div class="card-img-top bg-secondary text-white d-flex align-items-center justify-content-center" style="height: 300px;">
                        <span>Sin imagen</span>
                    </div>
                    {% endif %}
                    <div class="card-body">
                        <h5 class="card-title">{{ pelicula.title }}</h5>
                        <p class="card-text">
                            <small class="text-muted">{{ pelicula.original_title }} ({{ pelicula.release_date[:4] if pelicula.release_date else 'Desconocido' }})</small>
                        </p>
                        <p class="card-text">{{ pelicula.overview[:150] }}{% if pelicula.overview and pelicula.overview|length > 150 %}...{% endif %}</p>
                    </div>
                    <div class="card-footer">
                        <a href="{{ url_for('detalles', movie_id=pelicula.id) }}" class="btn btn-primary">Seleccionar</a>
                    </div>
                </div>
            </div>
            {% else %}
            <div class="col">
                <div class="alert alert-info">No se encontraron resultados para tu búsqueda.</div>
            </div>
            {% endfor %}
        </div>
    </div>
    
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
        ''')
    
    # Crear detalles.html
    with open('templates/detalles.html', 'w', encoding='utf-8') as f:
        f.write('''
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Detalles de la Película</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body>
    <div class="container mt-4">
        <h1 class="mb-4">Añadir Película</h1>
        
        <div class="mb-3">
            <a href="{{ url_for('index') }}" class="btn btn-secondary">Volver al Inicio</a>
            <a href="{{ url_for('buscar') }}?query={{ query }}" class="btn btn-outline-secondary">Volver a Resultados</a>
        </div>
        
        <div class="row">
            <div class="col-md-4">
                {% if detalles.poster_path %}
                <img src="https://image.tmdb.org/t/p/w500{{ detalles.poster_path }}" class="img-fluid rounded mb-3" alt="{{ detalles.título }}">
                {% else %}
                <div class="bg-secondary text-white d-flex align-items-center justify-content-center rounded" style="height: 450px;">
                    <span>Sin imagen</span>
                </div>
                {% endif %}
            </div>
            <div class="col-md-8">
                <div class="card mb-4">
                    <div class="card-header">
                        <h5>Detalles de la Película</h5>
                    </div>
                    <div class="card-body">
                        <h3>{{ detalles.título }}</h3>
                        <p class="text-muted">{{ detalles.título_original }} ({{ detalles.año }})</p>
                        
                        <dl class="row">
                            <dt class="col-sm-3">Director:</dt>
                            <dd class="col-sm-9">{{ detalles.director }}</dd>
                            
                            <dt class="col-sm-3">Duración:</dt>
                            <dd class="col-sm-9">{{ detalles.duración }}</dd>
                            
                            <dt class="col-sm-3">Actores:</dt>
                            <dd class="col-sm-9">{{ detalles.actores }}</dd>
                        </dl>
                        
                        <h5>Sinopsis</h5>
                        <p>{{ detalles.sinopsis }}</p>
                    </div>
                </div>
                
                <form action="{{ url_for('guardar') }}" method="POST">
                    <input type="hidden" name="tmdb_id" value="{{ detalles.id }}">
                    <input type="hidden" name="titulo" value="{{ detalles.título }}">
                    <input type="hidden" name="titulo_original" value="{{ detalles.título_original }}">
                    <input type="hidden" name="director" value="{{ detalles.director }}">
                    <input type="hidden" name="duracion" value="{{ detalles.duración }}">
                    <input type="hidden" name="actores" value="{{ detalles.actores }}">
                    <input type="hidden" name="sinopsis" value="{{ detalles.sinopsis }}">
                    <input type="hidden" name="anio" value="{{ detalles.año }}">
                    <input type="hidden" name="poster_path" value="{{ detalles.poster_path }}">
                    
                    <div class="card mb-4">
                        <div class="card-header">
                            <h5>Información del Cine</h5>
                        </div>
                        <div class="card-body">
                            <div class="mb-3">
                                <label for="cine" class="form-label">Nombre del Cine:</label>
                                <input type="text" class="form-control" id="cine" name="cine" required>
                            </div>
                        </div>
                    </div>
                    
                    <div class="card mb-4">
                        <div class="card-header d-flex justify-content-between align-items-center">
                            <h5>Horarios</h5>
                            <button type="button" class="btn btn-sm btn-info" id="agregar-horario">Añadir Horario</button>
                        </div>
                        <div class="card-body">
                            <div id="horarios-container">
                                <div class="row mb-3 horario-item">
                                    <div class="col-md-4">
                                        <label class="form-label">Fecha:</label>
                                        <input type="date" class="form-control" name="fechas[]" required>
                                    </div>
                                    <div class="col-md-3">
                                        <label class="form-label">Hora:</label>
                                        <input type="time" class="form-control" name="horas[]" required>
                                    </div>
                                    <div class="col-md-4">
                                        <label class="form-label">Enlace de entradas:</label>
                                        <input type="url" class="form-control" name="enlaces[]" placeholder="https://">
                                    </div>
                                    <div class="col-md-1 d-flex align-items-end">
                                        <button type="button" class="btn btn-danger eliminar-horario">×</button>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <div class="mb-4">
                        <button type="submit" class="btn btn-success">Guardar Película</button>
                        <a href="{{ url_for('index') }}" class="btn btn-outline-secondary">Cancelar</a>
                    </div>
                </form>
            </div>
        </div>
    </div>
    
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        document.addEventListener('DOMContentLoaded', function() {
            const horariosContainer = document.getElementById('horarios-container');
            const btnAgregarHorario = document.getElementById('agregar-horario');
            
            // Función para eliminar horario
            const setupEliminarListeners = () => {
                document.querySelectorAll('.eliminar-horario').forEach(btn => {
                    btn.addEventListener('click', function() {
                        if (document.querySelectorAll('.horario-item').length > 1) {
                            this.closest('.horario-item').remove();
                        } else {
                            alert('Debe haber al menos un horario');
                        }
                    });
                });
            };
            
            // Configurar listeners iniciales
            setupEliminarListeners();
            
            // Añadir nuevo horario
            btnAgregarHorario.addEventListener('click', function() {
                const template = document.querySelector('.horario-item').cloneNode(true);
                
                // Limpiar valores del template
                template.querySelectorAll('input').forEach(input => {
                    input.value = '';
                });
                
                horariosContainer.appendChild(template);
                setupEliminarListeners();
            });
        });
    </script>
</body>
</html>
        ''')

# Función para crear archivo de edición
def crear_archivo_editar():
    with open('templates/editar.html', 'w', encoding='utf-8') as f:
        f.write('''
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Editar Película</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body>
    <div class="container mt-4">
        <h1 class="mb-4">Editar Película</h1>
        
        <div class="mb-3">
            <a href="{{ url_for('index') }}" class="btn btn-secondary">Volver al Inicio</a>
        </div>
        
        <div class="row">
            <div class="col-md-4">
                {% if pelicula.cartel %}
                <img src="{{ url_for('static', filename=pelicula.cartel) }}" class="img-fluid rounded mb-3" alt="{{ pelicula.título }}">
                {% else %}
                <div class="bg-secondary text-white d-flex align-items-center justify-content-center rounded" style="height: 450px;">
                    <span>Sin imagen</span>
                </div>
                {% endif %}
            </div>
            <div class="col-md-8">
                <div class="card mb-4">
                    <div class="card-header">
                        <h5>Detalles de la Película</h5>
                    </div>
                    <div class="card-body">
                        <h3>{{ pelicula.título }}</h3>
                        <p class="text-muted">
                            {% if pelicula.año %}({{ pelicula.año }}){% endif %}
                        </p>
                        
                        <dl class="row">
                            <dt class="col-sm-3">Director:</dt>
                            <dd class="col-sm-9">{{ pelicula.director }}</dd>
                            
                            <dt class="col-sm-3">Duración:</dt>
                            <dd class="col-sm-9">{{ pelicula.duración }}</dd>
                            
                            <dt class="col-sm-3">Actores:</dt>
                            <dd class="col-sm-9">{{ pelicula.actores }}</dd>
                        </dl>
                        
                        <h5>Sinopsis</h5>
                        <p>{{ pelicula.sinopsis }}</p>
                    </div>
                </div>
                
                <form action="{{ url_for('actualizar', id=id) }}" method="POST">
                    <div class="card mb-4">
                        <div class="card-header">
                            <h5>Información del Cine</h5>
                        </div>
                        <div class="card-body">
                            <div class="mb-3">
                                <label for="cine" class="form-label">Nombre del Cine:</label>
                                <input type="text" class="form-control" id="cine" name="cine" value="{{ pelicula.cine }}" required>
                            </div>
                        </div>
                    </div>
                    
                    <div class="card mb-4">
                        <div class="card-header d-flex justify-content-between align-items-center">
                            <h5>Horarios</h5>
                            <button type="button" class="btn btn-sm btn-info" id="agregar-horario">Añadir Horario</button>
                        </div>
                        <div class="card-body">
                            <div id="horarios-container">
                                {% for horario in pelicula.horarios %}
                                <div class="row mb-3 horario-item">
                                    <div class="col-md-4">
                                        <label class="form-label">Fecha:</label>
                                        <input type="date" class="form-control" name="fechas[]" value="{{ horario.fecha }}" required>
                                    </div>
                                    <div class="col-md-3">
                                        <label class="form-label">Hora:</label>
                                        <input type="time" class="form-control" name="horas[]" value="{{ horario.hora }}" required>
                                    </div>
                                    <div class="col-md-4">
                                        <label class="form-label">Enlace de entradas:</label>
                                        <input type="url" class="form-control" name="enlaces[]" value="{{ horario.enlace_entradas }}" placeholder="https://">
                                    </div>
                                    <div class="col-md-1 d-flex align-items-end">
                                        <button type="button" class="btn btn-danger eliminar-horario">×</button>
                                    </div>
                                </div>
                                {% else %}
                                <div class="row mb-3 horario-item">
                                    <div class="col-md-4">
                                        <label class="form-label">Fecha:</label>
                                        <input type="date" class="form-control" name="fechas[]" required>
                                    </div>
                                    <div class="col-md-3">
                                        <label class="form-label">Hora:</label>
                                        <input type="time" class="form-control" name="horas[]" required>
                                    </div>
                                    <div class="col-md-4">
                                        <label class="form-label">Enlace de entradas:</label>
                                        <input type="url" class="form-control" name="enlaces[]" placeholder="https://">
                                    </div>
                                    <div class="col-md-1 d-flex align-items-end">
                                        <button type="button" class="btn btn-danger eliminar-horario">×</button>
                                    </div>
                                </div>
                                {% endfor %}
                            </div>
                        </div>
                    </div>
                    
                    <div class="mb-4">
                        <button type="submit" class="btn btn-success">Actualizar Película</button>
                        <a href="{{ url_for('index') }}" class="btn btn-outline-secondary">Cancelar</a>
                    </div>
                </form>
            </div>
        </div>
    </div>
    
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        document.addEventListener('DOMContentLoaded', function() {
            const horariosContainer = document.getElementById('horarios-container');
            const btnAgregarHorario = document.getElementById('agregar-horario');
            
            // Función para eliminar horario
            const setupEliminarListeners = () => {
                document.querySelectorAll('.eliminar-horario').forEach(btn => {
                    btn.addEventListener('click', function() {
                        if (document.querySelectorAll('.horario-item').length > 1) {
                            this.closest('.horario-item').remove();
                        } else {
                            alert('Debe haber al menos un horario');
                        }
                    });
                });
            };
            
            // Configurar listeners iniciales
            setupEliminarListeners();
            
            // Añadir nuevo horario
            btnAgregarHorario.addEventListener('click', function() {
                const template = document.querySelector('.horario-item').cloneNode(true);
                
                // Limpiar valores del template
                template.querySelectorAll('input').forEach(input => {
                    input.value = '';
                });
                
                horariosContainer.appendChild(template);
                setupEliminarListeners();
            });
        });
    </script>
</body>
</html>
        ''')

# Rutas de la aplicación Flask
@app.route('/')
def index():
    """Página principal que muestra las películas existentes"""
    peliculas = cargar_peliculas()
    return render_template('index.html', peliculas=peliculas)

@app.route('/buscar')
def buscar():
    """Busca películas en TMDB"""
    query = request.args.get('query', '')
    if not query:
        return redirect(url_for('index'))
    
    resultados = tmdb_api.search_movies(query)
    return render_template('resultados.html', resultados=resultados, query=query)

@app.route('/pelicula/<int:movie_id>')
def detalles(movie_id):
    """Muestra los detalles de una película y permite añadirla"""
    query = request.args.get('query', '')
    detalles = tmdb_api.get_movie_details(movie_id)
    if not detalles:
        flash("No se pudieron obtener los detalles de la película.", "error")
        return redirect(url_for('index'))
    
    return render_template('detalles.html', detalles=detalles, query=query)

@app.route('/guardar', methods=['POST'])
def guardar():
    """Guarda una nueva película"""
    try:
        # Obtener datos del formulario
        tmdb_id = int(request.form['tmdb_id'])
        titulo = request.form['titulo']
        titulo_original = request.form.get('titulo_original', '')
        director = request.form.get('director', '')
        duracion = request.form.get('duracion', '')
        actores = request.form.get('actores', '')
        sinopsis = request.form.get('sinopsis', '')
        anio = request.form.get('anio', '')
        poster_path = request.form.get('poster_path', '')
        cine = request.form['cine']
        
        # Procesar horarios
        fechas = request.form.getlist('fechas[]')
        horas = request.form.getlist('horas[]')
        enlaces = request.form.getlist('enlaces[]')
        
        horarios = []
        for i in range(len(fechas)):
            if fechas[i] and horas[i]:
                horarios.append({
                    "fecha": fechas[i],
                    "hora": horas[i],
                    "enlace_entradas": enlaces[i] if i < len(enlaces) else ""
                })
        
        # Descargar el póster
        ruta_poster = ""
        if poster_path:
            ruta_poster = tmdb_api.download_poster(poster_path, titulo)
        
        # Crear objeto de película
        pelicula = {
            "título": titulo,
            "tmdb_id": tmdb_id,
            "director": director,
            "duración": duracion,
            "actores": actores,
            "sinopsis": sinopsis,
            "año": anio,
            "cartel": ruta_poster,
            "cine": cine,
            "horarios": horarios
        }
        
        # Cargar películas existentes
        peliculas = cargar_peliculas()
        
        # Comprobar si la película ya existe
        for i, p in enumerate(peliculas):
            if p.get('tmdb_id') == tmdb_id:
                flash(f"La película '{titulo}' ya existe en la base de datos.", "error")
                return redirect(url_for('index'))
        
        # Añadir película y guardar
        peliculas.append(pelicula)
        guardar_peliculas(peliculas)
        
        flash(f"¡Película '{titulo}' añadida correctamente!", "success")
        return redirect(url_for('index'))
    
    except Exception as e:
        flash(f"Error al guardar la película: {str(e)}", "error")
        return redirect(url_for('index'))

@app.route('/editar/<int:id>')
def editar(id):
    """Muestra el formulario para editar una película"""
    peliculas = cargar_peliculas()
    if id < 0 or id >= len(peliculas):
        flash("Película no encontrada.", "error")
        return redirect(url_for('index'))
    
    pelicula = peliculas[id]
    return render_template('editar.html', pelicula=pelicula, id=id)

@app.route('/actualizar/<int:id>', methods=['POST'])
def actualizar(id):
    """Actualiza una película existente"""
    try:
        peliculas = cargar_peliculas()
        if id < 0 or id >= len(peliculas):
            flash("Película no encontrada.", "error")
            return redirect(url_for('index'))
        
        # Obtener película existente
        pelicula = peliculas[id]
        
        # Actualizar datos del cine
        pelicula['cine'] = request.form['cine']
        
        # Procesar horarios
        fechas = request.form.getlist('fechas[]')
        horas = request.form.getlist('horas[]')
        enlaces = request.form.getlist('enlaces[]')
        
        horarios = []
        for i in range(len(fechas)):
            if fechas[i] and horas[i]:
                horarios.append({
                    "fecha": fechas[i],
                    "hora": horas[i],
                    "enlace_entradas": enlaces[i] if i < len(enlaces) else ""
                })
        
        pelicula['horarios'] = horarios
        
        # Guardar cambios
        guardar_peliculas(peliculas)
        
        flash(f"¡Película '{pelicula['título']}' actualizada correctamente!", "success")
        return redirect(url_for('index'))
    
    except Exception as e:
        flash(f"Error al actualizar la película: {str(e)}", "error")
        return redirect(url_for('index'))

@app.route('/eliminar/<int:id>')
def eliminar(id):
    """Elimina una película"""
    try:
        peliculas = cargar_peliculas()
        if id < 0 or id >= len(peliculas):
            flash("Película no encontrada.", "error")
            return redirect(url_for('index'))
        
        titulo = peliculas[id]['título']
        del peliculas[id]
        guardar_peliculas(peliculas)
        
        flash(f"Película '{titulo}' eliminada correctamente.", "success")
    except Exception as e:
        flash(f"Error al eliminar la película: {str(e)}", "error")
    
    return redirect(url_for('index'))

# Inicializar la aplicación
def inicializar_aplicacion():
    """Inicializa la aplicación creando los archivos necesarios"""
    # Crear directorios necesarios
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static/css', exist_ok=True)
    os.makedirs('static/js', exist_ok=True)
    os.makedirs('imagenes_filmoteca', exist_ok=True)
    
    # Crear archivos estáticos
    crear_archivos_estaticos()
    crear_archivo_editar()
    
    # Inicializar archivo de películas si no existe
    if not os.path.exists('peliculas_filmoteca.json'):
        with open('peliculas_filmoteca.json', 'w', encoding='utf-8') as f:
            json.dump([], f)

# Punto de entrada principal
if __name__ == "__main__":
    # Verificar que existe TMDB_API_KEY
    if not TMDB_API_KEY:
        print("ERROR: No se ha encontrado la clave API de TMDB. Crea un archivo .env con TMDB_API_KEY=tu_clave")
        exit(1)
    
    # Inicializar la aplicación
    inicializar_aplicacion()
    
    # Ejecutar la aplicación Flask
    print("Iniciando servidor web en http://127.0.0.1:5000/")
    app.run(debug=True)