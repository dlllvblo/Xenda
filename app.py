from flask import (
    Flask,
    render_template,
    request,
    redirect,
    flash,
    session,
    jsonify,
    send_file 
)
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import pandas as pd
import unicodedata
import os
import uuid 
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# =========================================
# HORA CDMX
# =========================================

def hora_cdmx():

    return datetime.utcnow() - timedelta(hours=6)


# =========================================
# APP
# =========================================

app = Flask(__name__)


app.secret_key = os.getenv('SECRET_KEY') 
ADMIN_CORREO = os.getenv('ADMIN_CORREO')

app.permanent_session_lifetime = timedelta(days=7)

database_url = os.getenv('DATABASE_URL')

if database_url and database_url.startswith('postgres://'):

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
# SESIONES ACTIVAS
# =========================================

class SesionActiva(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    correo = db.Column(
        db.String(120),
        nullable=False
    )

    token = db.Column(
        db.String(200),
        nullable=False,
        unique=True
    )

    inicio = db.Column(

        db.DateTime,

        default=hora_cdmx
    )

    ultima_actividad = db.Column(

        db.DateTime,

        default=hora_cdmx
    )

# =========================================
# CONTROL DE SESIONES
# =========================================

@app.before_request

def actualizar_sesion():

    token = session.get(
        'session_token'
    )

    if not token:

        return

    sesion_db = SesionActiva.query.filter_by(
        token=token
    ).first()

    # =============================
    # SESIÓN ELIMINADA POR ADMIN
    # =============================

    if not sesion_db:

        session.clear()

        return redirect('/login')

    # =============================
    # ACTUALIZAR ACTIVIDAD
    # =============================

    sesion_db.ultima_actividad = hora_cdmx()

    db.session.commit()

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

        default=hora_cdmx
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

    frente = db.Column(db.Integer)

    actividad = db.Column(db.String(100))

    tipo = db.Column(db.String(100))

    mediciones_agroforestales = db.Column(db.Integer)

    mediciones_bdts = db.Column(db.Integer)

    planos = db.Column(db.Integer)

    planos_generados = db.Column(db.Integer)

    planos_validados = db.Column(db.Integer)

    num_infografias = db.Column(db.Integer)

    infografias_generadas = db.Column(db.Integer)

    infografias_validadas = db.Column(db.Integer)

    estatus_infografias = db.Column(db.String(100))

    tipo_propiedad = db.Column(db.String(100))

    observaciones = db.Column(db.Text)

    fecha = db.Column(db.DateTime(timezone=True)) 

# =========================================
# REGISTROS ELIMINADOS
# =========================================

class RegistroEliminado(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    id_original = db.Column(db.Integer)

    usuario_original = db.Column(db.String(200))

    eliminado_por = db.Column(db.String(200))

    fecha_eliminacion = db.Column(db.DateTime(timezone=True))

    tramo = db.Column(db.String(100))

    entidad = db.Column(db.String(100))

    municipio = db.Column(db.String(100))

    nucleo = db.Column(db.String(200))

    frente = db.Column(db.Integer)

    actividad = db.Column(db.String(100))

    tipo = db.Column(db.String(100))

    tipo_propiedad = db.Column(db.String(100))

    observaciones = db.Column(db.Text)

    fecha_original = db.Column(db.DateTime(timezone=True))

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

    dia = hora_cdmx().day

    return (
        (10 <= dia <= 14)
        or
        (25 <= dia <= 29)
    )


# =========================================
# EXPORTACION AUTOMATICA
# =========================================

def exportar_excel_mensual():

    ahora = hora_cdmx()

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

            'TIPO_PROPIEDAD': r.tipo_propiedad,

            'MEDICIONES_AGROFORESTALES': r.mediciones_agroforestales,

            'MEDICIONES_BDTS': r.mediciones_bdts,

            'PLANOS': r.planos,

            'PLANOS_GENERADOS': r.planos_generados,

            'PLANOS_VALIDADOS': r.planos_validados,

            'NUM_INFOGRAFIAS': r.num_infografias,

            'INFOGRAFIAS_GENERADAS': r.infografias_generadas,

            'INFOGRAFIAS_VALIDADAS': r.infografias_validadas,

            'ESTATUS_INFOGRAFIAS': r.estatus_infografias,

            'OBSERVACIONES': r.observaciones,

            'USUARIO': r.usuario
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

catalogo = pd.read_excel('catalogo_1.xlsx')

catalogo.columns = catalogo.columns.str.strip()

catalogo['TRAMO'] = (
    catalogo['TRAMO']
    .astype(str)
    .str.strip()
)

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

        APP_PASSWORD = os.getenv('APP_PASSWORD')

        if usuario and password == APP_PASSWORD: 

            session.permanent = True

            session['usuario'] = usuario.correo

            # =============================
            # CREAR TOKEN DE SESIÓN
            # =============================

            session_token = str(uuid.uuid4())

            session['session_token'] = session_token

            nueva_sesion = SesionActiva(

                correo=correo,

                token=session_token
            )

            db.session.add(nueva_sesion)

            db.session.commit()

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

    token = session.get(
        'session_token'
    )

    if token:

        sesion_db = SesionActiva.query.filter_by(
            token=token
        ).first()

        if sesion_db:

            db.session.delete(sesion_db)

            db.session.commit()

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
# REINICIAR REGISTROS
# =========================================

@app.route('/reiniciar_registros')

def reiniciar_registros():

    if session.get('usuario') != ADMIN_CORREO:

        return 'No autorizado', 403

    # =====================================
    # BORRAR SOLO REGISTROS
    # =====================================

    Registro.query.delete()

    RegistroEliminado.query.delete()

    Exportacion.query.delete()

    db.session.commit()

    flash(
        'Registros reiniciados correctamente'
    )

    return redirect('/admin')

# =========================================
# SESIONES ACTIVAS
# =========================================

@app.route('/sesiones')

def sesiones():

    if session.get('usuario') != ADMIN_CORREO:

        return redirect('/login')

    sesiones_activas = SesionActiva.query.order_by(

        SesionActiva.ultima_actividad.desc()

    ).all()

    return render_template(

        'sesiones.html',

        sesiones=sesiones_activas
    )


# =========================================
# CERRAR SESION REMOTA
# =========================================

@app.route('/cerrar_sesion/<int:id>')

def cerrar_sesion(id):

    if session.get('usuario') != ADMIN_CORREO:

        return redirect('/login')

    sesion_obj = SesionActiva.query.get_or_404(id)

    db.session.delete(sesion_obj)

    db.session.commit()

    flash(
        'Sesión cerrada correctamente'
    )

    return redirect('/sesiones')

# =========================================
# CREAR USUARIOS
# =========================================

@app.route('/xenda_admin_bootstrap_users')

def crear_usuarios():

    if session.get('usuario') != ADMIN_CORREO:
    
        return redirect('/login')

    correos = [ADMIN_CORREO]

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
# FORMULARIO PRINCIPAL
# =========================================

@app.route('/', methods=['GET', 'POST'])

def index():

    exportar_excel_mensual()

#    if (
#        not registro_habilitado()
#        and
#        session.get('usuario') != ADMIN_CORREO
#):
#
#        session.clear()
#
#        return render_template(
#            'cerrado.html'
#    )

    if 'usuario' not in session:

        return redirect('/login')

    entidades = sorted(

        catalogo['ENTIDAD_FEDERATIVA']

        .dropna()

        .unique()

    )

    frente = request.form.get('frente')

    frente = int(frente) if frente else None

    if request.method == 'POST':

        nuevo = Registro(

            usuario=session['usuario'],

            fecha=hora_cdmx(),

            tramo=request.form['tramo'],

            entidad=request.form['entidad'],

            municipio=request.form['municipio'],

            nucleo=request.form['nucleo'],

            frente=frente,

            actividad=request.form['actividad'],

            tipo=request.form['tipo'],

            mediciones_agroforestales=(request.form.get('mediciones_agroforestales') or 0),

            mediciones_bdts=(request.form.get('mediciones_bdts') or 0),

            planos=(request.form.get('planos') or 0),

            planos_generados=(request.form.get('planos_generados') or 0),

            planos_validados=(request.form.get('planos_validados') or 0),

            num_infografias=(request.form.get('num_infografias') or 0),

            infografias_generadas=(request.form.get('infografias_generadas') or 0),

            infografias_validadas=(request.form.get('infografias_validadas') or 0),

            estatus_infografias=request.form.get('estatus_infografias'),

            tipo_propiedad=request.form.get('tipo_propiedad'),

            observaciones=request.form['observaciones']
        )

        db.session.add(nuevo)

        db.session.commit()

        accion = request.form.get(
            'accion'
        )

        if accion == 'guardar_otro':

            return redirect('/')

        flash(
            'Registro guardado exitosamente'
        )

        return redirect('/')

    return render_template(

        'index.html',

        entidades=entidades

    )

#=========================================
# ENTIDADES POR TRAMO
#=========================================

@app.route('/entidades/<tramo>')

def entidades_por_tramo(tramo):

    entidades = catalogo[

        catalogo['TRAMO'] == tramo

    ][
        'ENTIDAD_FEDERATIVA'
    ].dropna().unique()

    entidades = sorted(entidades)

    return jsonify(
        list(entidades)
    )


# =========================================
# MUNICIPIOS
# =========================================

@app.route('/municipios/<tramo>/<entidad>')

def municipios(tramo, entidad):

    entidad = normalizar(entidad)

    municipios = catalogo[

        (
            catalogo['TRAMO'] == tramo
        )

        &

        (
            catalogo[
                'ENTIDAD_NORMALIZADA'
            ] == entidad
        )

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

@app.route('/nucleos/<tramo>/<entidad>/<municipio>')

def nucleos(tramo, entidad, municipio):

    entidad = normalizar(entidad)

    municipio = normalizar(municipio)

    nucleos = catalogo[

        (
            catalogo['TRAMO'] == tramo
        )

        &

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
    
    if 'usuario' not in session:
    
        return redirect('/login')

    query = Registro.query

    tramo = request.args.get('tramo')

    entidad = request.args.get('entidad')

    municipio = request.args.get('municipio')

    usuario = request.args.get('usuario')

    if tramo:

        query = query.filter(
            Registro.tramo == tramo
        )

    if entidad:

        query = query.filter(
            Registro.entidad == entidad
        )

    if municipio:

        query = query.filter(
            Registro.municipio == municipio
        )

    if usuario:

        query = query.filter(
            Registro.usuario == usuario
        )

    lista = query.order_by(
        Registro.fecha.desc()
    ).all()

    tramos = sorted([

    t[0]

    for t in db.session.query(
        Registro.tramo
    ).distinct()

    ])

    entidades = sorted([

        e[0]

        for e in db.session.query(
            Registro.entidad
        ).distinct()

    ])

    municipios = sorted([

        m[0]

        for m in db.session.query(
            Registro.municipio
        ).distinct()

    ])

    usuarios = sorted([

        u[0]

        for u in db.session.query(
            Registro.usuario
        ).distinct()

    ])

    return render_template(

    'registros.html',

    registros=lista,

    admin_correo=ADMIN_CORREO,

    tramos=tramos,

    entidades=entidades,

    municipios=municipios,

    usuarios=usuarios
)

@app.route('/xenda_delete_record/<int:id>')

def eliminar_registro(id):

    if session.get('usuario') != ADMIN_CORREO:

        return 'No autorizado', 403

    registro = Registro.query.get_or_404(id)

    eliminado = RegistroEliminado(

        id_original=registro.id,

        usuario_original=registro.usuario,

        eliminado_por=session['usuario'],

        fecha_eliminacion=hora_cdmx(),
                                       
        tramo=registro.tramo,

        entidad=registro.entidad,

        municipio=registro.municipio,

        nucleo=registro.nucleo,

        frente=registro.frente,

        actividad=registro.actividad,

        tipo=registro.tipo,

        tipo_propiedad=registro.tipo_propiedad,

        observaciones=registro.observaciones,

        fecha_original=registro.fecha
    )

    db.session.add(eliminado)

    db.session.delete(registro)

    db.session.commit()

    return redirect('/registros')

# =========================================
# DESCARGAR USUARIOS
# =========================================

@app.route('/descargar_usuarios')

def descargar_usuarios():

    if session.get('usuario') != ADMIN_CORREO:

        return 'No autorizado', 403

    usuarios = Usuario.query.all()

    datos = []

    for u in usuarios:

        datos.append({

            'CORREO': u.correo
        })

    df = pd.DataFrame(datos)

    nombre_archivo = 'usuarios_xenda.xlsx'

    df.to_excel(
        nombre_archivo,
        index=False
    )

    return send_file(
        nombre_archivo,
        as_attachment=True
    )

# =========================================
# DESCARGAR REGISTROS ELIMINADOS
# =========================================

@app.route('/descargar_eliminados')

def descargar_eliminados():

    if session.get('usuario') != ADMIN_CORREO:

        return 'No autorizado', 403

    eliminados = RegistroEliminado.query.order_by(
        RegistroEliminado.fecha_eliminacion.desc()
    ).all()

    datos = []

    for r in eliminados:

        datos.append({

            'ID_ORIGINAL': r.id_original,

            'USUARIO_ORIGINAL': r.usuario_original,

            'ELIMINADO_POR': r.eliminado_por,

            'FECHA_ELIMINACION': r.fecha_eliminacion,

            'TRAMO': r.tramo,

            'ENTIDAD': r.entidad,

            'MUNICIPIO': r.municipio,

            'NUCLEO': r.nucleo,

            'FRENTE': r.frente,

            'ACTIVIDAD': r.actividad,

            'TIPO': r.tipo,

            'TIPO_PROPIEDAD': r.tipo_propiedad,

            'OBSERVACIONES': r.observaciones,

            'FECHA_ORIGINAL': r.fecha_original
        })

    df = pd.DataFrame(datos)

    nombre_archivo = 'registros_eliminados.xlsx'

    df.to_excel(
        nombre_archivo,
        index=False
    )

    return send_file(
        nombre_archivo,
        as_attachment=True
    )

# =========================================
# DASHBOARD
# =========================================

@app.route('/dashboard')

def dashboard():

    if 'usuario' not in session:

        return redirect('/login')

    total_registros = Registro.query.count()

    total_infografias = db.session.query(
        db.func.sum(
            Registro.num_infografias
        )
    ).scalar() or 0

    total_planos = db.session.query(
        db.func.sum(
            Registro.planos
        )
    ).scalar() or 0

    total_mediciones = db.session.query(
        db.func.sum(
            Registro.mediciones_agroforestales
        )
    ).scalar() or 0

    return render_template(
        'dashboard.html',
        total_registros=total_registros,
        total_infografias=total_infografias,
        total_planos=total_planos,
        total_mediciones=total_mediciones
    )

# =========================================
# CREAR TABLAS
# =========================================

with app.app_context():
    
    db.create_all()

    admin = Usuario.query.filter_by(
        correo=ADMIN_CORREO
    ).first()

    if not admin:

        nuevo_admin = Usuario(

            correo=ADMIN_CORREO
        )

        db.session.add(nuevo_admin)

        db.session.commit()

        print('ADMIN CREADO')

# =========================================
# INICIO
# =========================================

if __name__ == '__main__':

    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True
    )