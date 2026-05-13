from flask import (
    Flask,
    render_template,
    request,
    redirect,
    flash,
    session,
    jsonify
)

from flask_sqlalchemy import SQLAlchemy

from datetime import datetime, timedelta

import pandas as pd
import unicodedata


# =========================================
# APP
# =========================================

app = Flask(__name__)

app.secret_key = 'RAN-DGCAT_2026'

app.permanent_session_lifetime = timedelta(days=7)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///xenda_v3.db'

db = SQLAlchemy(app)


# =========================================
# MODELO USUARIOS
# =========================================

class Usuario(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    correo = db.Column(
        db.String(200),
        unique=True,
        nullable=False
    )


# =========================================
# MODELO REGISTROS
# =========================================

class Registro(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    direccion = db.Column(db.String(200))

    tramo = db.Column(db.String(100))

    entidad = db.Column(db.String(100))

    municipio = db.Column(db.String(100))

    nucleo = db.Column(db.String(200))

    frente = db.Column(db.String(50))

    actividad = db.Column(db.String(100))

    tipo = db.Column(db.String(100))

    mediciones_agroforestales = db.Column(db.Integer)

    mediciones_bdts = db.Column(db.Integer)

    planos = db.Column(db.Integer)

    infografias = db.Column(db.Integer)

    observaciones = db.Column(db.Text)

    fecha = db.Column(
        db.DateTime,
        default=datetime.now
    )


# =========================================
# NORMALIZAR TEXTO
# =========================================

def normalizar(texto):

    texto = str(texto).strip().upper()

    texto = unicodedata.normalize(
        'NFKD',
        texto
    )

    texto = texto.encode(
        'ASCII',
        'ignore'
    ).decode('utf-8')

    return texto


# =========================================
# CONTROL DE PERIODOS
# =========================================

def registro_habilitado():

    dia = datetime.now().day

    return (
        (10 <= dia <= 14)
        or
        (25 <= dia <= 29)
    )


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
# LOGIN
# =========================================

@app.route('/login', methods=['GET', 'POST'])

def login():

    if request.method == 'POST':

        correo = request.form['correo']

        password = request.form['password']

        usuario = Usuario.query.filter_by(
            correo=correo
        ).first()

        if usuario and password == 'RAN-DGCAT_2026':

            session.permanent = True

            session['usuario'] = usuario.correo

            return redirect('/')

        else:

            return render_template(
                'login.html',
                error='Acceso no autorizado'
            )

    return render_template('login.html')


# =========================================
# LOGOUT
# =========================================

@app.route('/logout')

def logout():

    session.clear()

    return redirect('/login')


# =========================================
# CREAR USUARIO
# =========================================

@app.route('/crear_usuario')

def crear_usuario():

    usuario = Usuario(

        correo='diazedgar1701@gmail.com'

    )

    db.session.add(usuario)

    db.session.commit()

    return 'Usuario creado correctamente'


# =========================================
# VER USUARIOS
# =========================================

@app.route('/usuarios')

def ver_usuarios():

    usuarios = Usuario.query.all()

    lista = []

    for u in usuarios:

        lista.append(u.correo)

    return '<br>'.join(lista)


# =========================================
# FORMULARIO PRINCIPAL
# =========================================

@app.route('/', methods=['GET', 'POST'])

def index():

    if not registro_habilitado():

        session.clear()

        return render_template(
            'cerrado.html'
        )

    if 'usuario' not in session:

        return redirect('/login')

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

            mediciones_agroforestales=(
                request.form.get(
                    'mediciones_agroforestales'
                ) or 0
            ),

            mediciones_bdts=(
                request.form.get(
                    'mediciones_bdts'
                ) or 0
            ),

            planos=(
                request.form.get(
                    'planos'
                ) or 0
            ),

            infografias=(
                request.form.get(
                    'infografias'
                ) or 0
            ),

            observaciones=request.form[
                'observaciones'
            ]

        )

        db.session.add(nuevo)

        db.session.commit()

        flash(
            'Registro guardado correctamente'
        )

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

        catalogo[
            'ENTIDAD_NORMALIZADA'
        ] == entidad

    ][
        'MUNICIPIO'
    ].dropna().unique()

    municipios = sorted(municipios)

    return jsonify(
        list(municipios)
    )


# =========================================
# NUCLEOS
# =========================================

@app.route('/nucleos/<entidad>/<municipio>')

def nucleos(entidad, municipio):

    entidad = normalizar(entidad)

    municipio = normalizar(municipio)

    nucleos = catalogo[

        (
            catalogo[
                'ENTIDAD_NORMALIZADA'
            ] == entidad
        )

        &

        (
            catalogo[
                'MUNICIPIO_NORMALIZADO'
            ] == municipio
        )

    ][
        'NUCLEO_AGRARIO'
    ].dropna().unique()

    nucleos = sorted(nucleos)

    return jsonify(
        list(nucleos)
    )


# =========================================
# REGISTROS
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
# CREAR TABLAS
# =========================================

with app.app_context():

    db.create_all()


# =========================================
# INICIO
# =========================================

if __name__ == '__main__':

    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True
    )