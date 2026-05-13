from flask import Flask, render_template, request, redirect, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import pandas as pd
import unicodedata

app = Flask(__name__)
app.secret_key = 'xenda123'

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///xenda.db'

db = SQLAlchemy(app)


# =========================================
# NORMALIZAR TEXTO
# =========================================

def normalizar(texto):

    texto = str(texto).strip().upper()

    texto = unicodedata.normalize('NFKD', texto)
    texto = texto.encode('ASCII', 'ignore').decode('utf-8')

    return texto


# =========================================
# CARGAR CATALOGO
# =========================================

catalogo = pd.read_excel('catalogo.xlsx')

catalogo.columns = catalogo.columns.str.strip()

catalogo['ENTIDAD_FEDERATIVA'] = (
    catalogo['ENTIDAD_FEDERATIVA']
    .astype(str)
    .str.strip()
)

catalogo['MUNICIPIO'] = (
    catalogo['MUNICIPIO']
    .astype(str)
    .str.strip()
)

catalogo['NUCLEO_AGRARIO'] = (
    catalogo['NUCLEO_AGRARIO']
    .astype(str)
    .str.strip()
)

catalogo['ENTIDAD_NORMALIZADA'] = (
    catalogo['ENTIDAD_FEDERATIVA']
    .apply(normalizar)
)

catalogo['MUNICIPIO_NORMALIZADO'] = (
    catalogo['MUNICIPIO']
    .apply(normalizar)
)


# =========================================
# BASE DE DATOS
# =========================================

class Registro(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    direccion = db.Column(db.String(200))
    tramo = db.Column(db.String(100))
    entidad = db.Column(db.String(100))
    municipio = db.Column(db.String(100))
    nucleo = db.Column(db.String(200))
    frente = db.Column(db.String(50))
    actividad = db.Column(db.String(100))
    tipo = db.Column(db.String(100))
    observaciones = db.Column(db.Text)
    mediciones_agroforestales = db.Column(db.Integer)
    mediciones_bdts = db.Column(db.Integer)
    planos = db.Column(db.Integer)
    infografias = db.Column(db.Integer)

    fecha = db.Column(db.DateTime, default=datetime.now)


# =========================================
# CONTROL DE PERIODO
# =========================================

def periodo_abierto():

    dia = datetime.now().day

    return 10 <= dia <= 29


# =========================================
# FORMULARIO PRINCIPAL
# =========================================

@app.route('/', methods=['GET', 'POST'])
def index():

    if not periodo_abierto():
        return render_template('cerrado.html')

    entidades = sorted(
        catalogo['ENTIDAD_FEDERATIVA']
        .dropna()
        .unique()
    )

    if request.method == 'POST':

        nuevo = Registro(

            tramo=request.form['tramo'],
            entidad=request.form['entidad'],
            municipio=request.form['municipio'],
            nucleo=request.form['nucleo'],
            frente=request.form['frente'],
            actividad=request.form['actividad'],
            tipo=request.form['tipo'],
            observaciones=request.form['observaciones']
            mediciones_agroforestales=request.form.get('mediciones_agroforestales') or 0,
            mediciones_bdts=request.form.get('mediciones_bdts') or 0,
            planos=request.form.get('planos') or 0,
            infografias=request.form.get('infografias') or 0,

        )

        db.session.add(nuevo)
        db.session.commit()

        flash('Registro guardado correctamente')

        return redirect('/')

    return render_template(
        'index.html',
        entidades=entidades
    )


# =========================================
# MUNICIPIOS
# =========================================

@app.route('/municipios/<entidad>')
def municipios(entidad):

    entidad = normalizar(entidad)

    municipios = catalogo[
        catalogo['ENTIDAD_NORMALIZADA'] == entidad
    ]['MUNICIPIO'].dropna().unique()

    municipios = sorted(municipios)

    return jsonify(list(municipios))


# =========================================
# NUCLEOS
# =========================================

@app.route('/nucleos/<entidad>/<municipio>')
def nucleos(entidad, municipio):

    entidad = normalizar(entidad)
    municipio = normalizar(municipio)

    nucleos = catalogo[
        (catalogo['ENTIDAD_NORMALIZADA'] == entidad) &
        (catalogo['MUNICIPIO_NORMALIZADO'] == municipio)
    ]['NUCLEO_AGRARIO'].dropna().unique()

    nucleos = sorted(nucleos)

    return jsonify(list(nucleos))


# =========================================
# VER REGISTROS
# =========================================

@app.route('/registros')
def registros():

    lista = Registro.query.order_by(
        Registro.fecha.desc()
    ).all()

    return render_template(
        'registros.html',
        registros=lista
    )


# =========================================
# INICIO
# =========================================

if __name__ == '__main__':

    with app.app_context():
        db.create_all()

    app.run(host='0.0.0.0', port=5000, debug=True)