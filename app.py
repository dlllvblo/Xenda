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
import os
from zoneinfo import ZoneInfo

from google.oauth2.service_account import Credentials

from googleapiclient.discovery import build

from googleapiclient.http import MediaFileUpload


# =========================================
# APP
# =========================================

app = Flask(__name__)

app.secret_key = 'RAN-DGCAT_2026'
ADMIN_CORREO = 'diazedgar1701@gmail.com'

app.permanent_session_lifetime = timedelta(days=7)

database_url = os.getenv('DATABASE_URL')

if database_url.startswith('postgres://'):

    database_url = database_url.replace(
        'postgres://',
        'postgresql://',
        1
    )

app.config['SQLALCHEMY_DATABASE_URI'] = database_url

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
# CONTROL EXPORTACIONES
# =========================================

class Exportacion(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    mes = db.Column(
        db.String(20),
        unique=True,
        nullable=False
    )

    fecha_exportacion = db.Column(
        db.DateTime,
        default=datetime.now
    )


# =========================================
# MODELO REGISTROS
# =========================================

class Registro(db.Model):
    
    id = db.Column(
        db.Integer,
        primary_key=True
    )
    usuario = db.Column(db.String(200))

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

    planos_generados = db.Column(db.Integer)

    planos_validados = db.Column(db.Integer)

    #infografias = db.Column(db.Integer)

    num_infografias = db.Column(db.Integer)

    infografias_generadas = db.Column(db.Integer)

    infografias_validadas = db.Column(db.Integer)

    estatus_infografias = db.Column(db.String(100))

    tipo_propiedad = db.Column(db.String(100))

    observaciones = db.Column(db.Text)

    fecha = db.Column(

    db.DateTime) 


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
# EXPORTACION AUTOMATICA
# =========================================

def exportar_excel_mensual():

    ahora = datetime.now()

    dia = ahora.day

    if dia != 30:

        return

    mes_actual = ahora.strftime('%Y_%m')

    exportado = Exportacion.query.filter_by(
        mes=mes_actual
    ).first()

    if exportado:

        return

    registros = Registro.query.filter(

        db.extract('year', Registro.fecha) == ahora.year,

        db.extract('month', Registro.fecha) == ahora.month

    ).all()

    if not registros:

        return

    datos = []

    for r in registros:

        datos.append({

            'FECHA': r.fecha,
            'TRAMO': r.tramo,
            'ENTIDAD': r.entidad,
            'MUNICIPIO': r.municipio,
            'NUCLEO': r.nucleo,
            'FRENTE': r.frente,
            'ACTIVIDAD': r.actividad,
            'MODALIDAD': r.tipo,
            'MEDICIONES_AGROFORESTALES': r.mediciones_agroforestales,
            'MEDICIONES_BDTS': r.mediciones_bdts,
            'PLANOS': r.planos,
            'INFOGRAFIAS': r.infografias,
            'OBSERVACIONES': r.observaciones

        })

    df = pd.DataFrame(datos)

    nombre_excel = f'XENDA_{mes_actual}.xlsx'

    ruta_excel = os.path.join(
        os.getcwd(),
        nombre_excel
    )

    df.to_excel(
        ruta_excel,
        index=False
    )

    SCOPES = [
        'https://www.googleapis.com/auth/drive'
    ]

    creds = Credentials.from_service_account_file(
        'credentials.json',
        scopes=SCOPES
    )

    service = build(
        'drive',
        'v3',
        credentials=creds
    )

    folders = service.files().list(

        q="mimeType='application/vnd.google-apps.folder' and name='XENDA_REPORTES'",

        spaces='drive',

        fields='files(id, name)'

    ).execute()

    folder_id = folders['files'][0]['id']

    file_metadata = {

        'name': nombre_excel,

        'parents': [folder_id]

    }

    media = MediaFileUpload(

        ruta_excel,

        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

    )

    service.files().create(

        body=file_metadata,

        media_body=media,

        fields='id'

    ).execute()

    nueva_exportacion = Exportacion(

        mes=mes_actual

    )

    db.session.add(nueva_exportacion)

    db.session.commit()


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
# ADMIN
# =========================================

@app.route('/admin', methods=['GET', 'POST'])

def admin():

    #if 'usuario' not in session:

    #    return redirect('/login')

    if session.get('usuario') != ADMIN_CORREO:
    
        return redirect('/login')

    if request.method == 'POST':

        correo = request.form['correo']

        correo = correo.strip().lower()

        existente = Usuario.query.filter_by(
            correo=correo
        ).first()

        if existente:

            flash('El usuario ya existe')

        else:

            nuevo = Usuario(
                correo=correo
            )

            db.session.add(nuevo)

            db.session.commit()

            flash('Usuario agregado correctamente')

        return redirect('/admin')

    usuarios = Usuario.query.order_by(
        Usuario.correo.asc()
    ).all()

    return render_template(
    'admin.html',
    usuarios=usuarios
)

@app.route('/eliminar_usuario/<int:id>')

def eliminar_usuario(id):

    if 'usuario' not in session:

        return redirect('/login')

    if session['usuario'] != ADMIN_CORREO:

        return 'Acceso no autorizado'

    usuario = Usuario.query.get_or_404(id)

    db.session.delete(usuario)

    db.session.commit()

    flash('Usuario eliminado')

    return redirect('/admin')

# =========================================
# CREAR USUARIOS
# =========================================

@app.route('/crear_usuarios')

def crear_usuarios():

    correos = ['diazedgar1701@gmail.com']

    for correo in correos:

        existente = Usuario.query.filter_by(
            correo=correo
        ).first()

        if not existente:

            nuevo = Usuario(
                correo=correo
            )

            db.session.add(nuevo)

    db.session.commit()

    return 'Usuarios creados correctamente'



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

    exportar_excel_mensual()

    if (
        not registro_habilitado()
        and
        session.get('usuario') != ADMIN_CORREO
):

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

            usuario=session['usuario'],

            fecha=datetime.now(ZoneInfo('America/Mexico_City')),

            tramo=request.form['tramo'],

            entidad=request.form['entidad'],

            municipio=request.form['municipio'],

            nucleo=request.form['nucleo'],

            frente=request.form['frente'],

            actividad=request.form['actividad'],

            tipo=request.form['tipo'],

            mediciones_agroforestales=(request.form.get('mediciones_agroforestales') or 0),

            mediciones_bdts=(request.form.get('mediciones_bdts') or 0),

            planos=(request.form.get('planos') or 0),

            planos_generados=request.form['planos_generados'],

            planos_validados=request.form['planos_validados'],

            num_infografias=request.form['num_infografias'],

            infografias_generadas=request.form['infografias_generadas'],

            infografias_validadas=request.form['infografias_validadas'],

            estatus_infografias=request.form['estatus_infografias'],

            tipo_propiedad=request.form.get('tipo_propiedad'),

            observaciones=request.form['observaciones']
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

@app.route('/eliminar_registro/<int:id>')

def eliminar_registro(id):

    if session.get('usuario') != 'diazedgar1701@gmail.com':

        return 'No autorizado', 403

    registro = Registro.query.get_or_404(id)

    db.session.delete(registro)

    db.session.commit()

    return redirect('/registros')


# =========================================
# CREAR TABLAS
# =========================================

with app.app_context():

    db.drop_all()

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