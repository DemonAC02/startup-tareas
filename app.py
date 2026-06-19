from flask import Flask, request, jsonify, render_template
from pymongo import MongoClient
from bson.objectid import ObjectId
from datetime import datetime
import os
import math

app = Flask(__name__)

# Cambia esta línea en app.py:
MONGO_URI = os.environ.get('MONGO_URI', 'mongodb://localhost:27017/SistemaTareas')
client = MongoClient(MONGO_URI)
db = client['SistemaTareas']

proyectos_collection = db['proyectos']
tareas_collection = db['tareas']
usuarios_collection = db['usuarios']
historial_collection = db['historial_actividades']

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/usuarios', methods=['GET', 'POST'])
def gestionar_usuarios():
    if request.method == 'POST':
        usuarios_collection.insert_one(request.json)
        return jsonify({"mensaje": "Usuario creado"}), 201
    usuarios = list(usuarios_collection.find({}, {"_id": 1, "nombre": 1}))
    for u in usuarios: u['_id'] = str(u['_id'])
    return jsonify(usuarios), 200

@app.route('/api/proyectos', methods=['GET', 'POST'])
def gestionar_proyectos():
    if request.method == 'POST':
        datos = request.json
        datos['fecha_creacion'] = datetime.now()
        proyectos_collection.insert_one(datos)
        return jsonify({"mensaje": "Proyecto creado"}), 201
    proyectos = list(proyectos_collection.find({}, {"_id": 1, "nombre": 1}))
    for p in proyectos: p['_id'] = str(p['_id'])
    return jsonify(proyectos), 200

# --- TAREAS (CREATE Y READ) ---
@app.route('/api/tareas', methods=['GET', 'POST'])
def gestionar_tareas():
    if request.method == 'POST':
        datos = request.json
        datos['estado'] = 'Pendiente'
        datos['fecha_creacion'] = datetime.now()
        resultado = tareas_collection.insert_one(datos)
        
        historial_collection.insert_one({
            "tarea_id": str(resultado.inserted_id),
            "tarea_titulo": datos.get('titulo', 'Desconocido'),
            "proyecto": datos.get('proyecto', 'Desconocido'),
            "accion": "Creación",
            "detalle": f"Tarea creada con fecha de vencimiento: {datos.get('fecha_vencimiento', 'Sin fecha')}",
            "fecha": datetime.now()
        })
        return jsonify({"mensaje": "Tarea creada"}), 201
    
    proyecto_filtro = request.args.get('proyecto')
    query = {"proyecto": proyecto_filtro} if proyecto_filtro else {}
    tareas = list(tareas_collection.find(query))
    for t in tareas: t['_id'] = str(t['_id'])
    return jsonify(tareas), 200

# --- TAREAS (UPDATE Y DELETE) ---
@app.route('/api/tareas/<id_tarea>', methods=['PUT', 'DELETE'])
def modificar_tarea(id_tarea):
    tarea_actual = tareas_collection.find_one({"_id": ObjectId(id_tarea)})
    if not tarea_actual:
        return jsonify({"error": "No encontrada"}), 404

    # ELIMINAR TAREA (Sugerencia 3)
    if request.method == 'DELETE':
        tareas_collection.delete_one({"_id": ObjectId(id_tarea)})
        historial_collection.insert_one({
            "tarea_id": id_tarea,
            "tarea_titulo": tarea_actual.get('titulo'),
            "proyecto": tarea_actual.get('proyecto'),
            "accion": "Eliminación",
            "detalle": "La tarea fue eliminada del sistema.",
            "fecha": datetime.now()
        })
        return jsonify({"mensaje": "Eliminada"}), 200

    # ACTUALIZAR ESTADO O TÍTULO
    datos = request.json
    actualizacion = {}
    detalle_log = ""
    accion_log = ""

    if 'estado' in datos:
        actualizacion['estado'] = datos['estado']
        accion_log = "Cambio de Estado"
        detalle_log = f"De '{tarea_actual.get('estado')}' a '{datos['estado']}'."
    if 'titulo' in datos:
        actualizacion['titulo'] = datos['titulo']
        accion_log = "Edición de Título"
        detalle_log = f"De '{tarea_actual.get('titulo')}' a '{datos['titulo']}'."

    tareas_collection.update_one({"_id": ObjectId(id_tarea)}, {"$set": actualizacion})
    
    historial_collection.insert_one({
        "tarea_id": id_tarea,
        "tarea_titulo": actualizacion.get('titulo', tarea_actual.get('titulo')),
        "proyecto": tarea_actual.get('proyecto'),
        "accion": accion_log,
        "detalle": detalle_log,
        "fecha": datetime.now()
    })
    return jsonify({"mensaje": "Actualizada"}), 200

# --- HISTORIAL PAGINADO (Sugerencia 4) ---
@app.route('/api/historial', methods=['GET'])
def obtener_historial():
    proyecto_filtro = request.args.get('proyecto')
    query = {"proyecto": proyecto_filtro} if proyecto_filtro else {}
    
    # Parámetros de paginación
    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 5)) # Mostramos 5 por página para probar rápido
    skip = (page - 1) * limit
    
    total_logs = historial_collection.count_documents(query)
    logs = list(historial_collection.find(query).sort("fecha", -1).skip(skip).limit(limit))
    
    for log in logs: 
        log['_id'] = str(log['_id'])
        if 'fecha' in log:
            log['fecha'] = log['fecha'].strftime("%Y-%m-%d %H:%M:%S")
            
    return jsonify({
        "datos": logs,
        "total_paginas": math.ceil(total_logs / limit),
        "pagina_actual": page
    }), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)