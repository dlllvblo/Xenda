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
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from datetime import datetime, timedelta
import pandas as pd
import unicodedata
import os
import uuid
import geopandas as gpd
from shapely.geometry import Point  
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# =========================================
# HORA CDMX
# =========================================

def hora_cdmx():

    return datetime.utcnow() - timedelta(hours=6)

def periodo_quincena():
    return "01-15 de Junio 2026"
    ahora = hora_cdmx()
    dia = ahora.day
    mes = ahora.month
    anio = ahora.year

    meses = {
        1:'Enero', 2:'Febrero', 3:'Marzo', 4:'Abril',
        5:'Mayo', 6:'Junio', 7:'Julio', 8:'Agosto',
        9:'Septiembre', 10:'Octubre', 11:'Noviembre', 12:'Diciembre'
    }

    import calendar
    ultimo_dia = calendar.monthrange(anio, mes)[1]
    nombre_mes = meses[mes]

    if 10 <= dia <= 14:
        return f"01–15 de {nombre_mes} {anio}"
    elif 25 <= dia <= 29:
        return f"16–{ultimo_dia} de {nombre_mes} {anio}"
    else:
        return f"{nombre_mes} {anio}"

# =========================================
# APP
# =========================================

app = Flask(__name__)


app.secret_key = os.getenv('SECRET_KEY') 
ADMIN_CORREO = os.getenv('ADMIN_CORREO')
ADMIN_CORREO_2 = os.getenv('ADMIN_CORREO_2')
ADMIN_CORREOS = [c for c in [ADMIN_CORREO, ADMIN_CORREO_2] if c]

app.permanent_session_lifetime = timedelta(days=3)
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],
    storage_uri="memory://"
)

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
# GEODATA ESTADOS
# =========================================

estados_gdf = gpd.read_file(
    'geodata/estados/dest23gw.shp',
    encoding='latin1'
)

estados_gdf = estados_gdf.to_crs(
    epsg=4326
)

# =========================================
# GEODATA NUCLEOS AGRARIOS
# =========================================

nucleos_gdf = gpd.read_file(
    'geodata/nucleos_agrarios/perimetrales.gpkg',
    encoding='latin1'
)

nucleos_gdf = nucleos_gdf.to_crs(
    epsg=4326
)

# =========================================
# OBTENER UBICACION
# =========================================

def obtener_ubicacion(latitud, longitud):

    punto = Point(
        longitud,
        latitud
    )

    estado = 'No identificado'

    nucleo = 'No identificado'

    estado_resultado = estados_gdf[

        estados_gdf.contains(punto)

    ]

    if not estado_resultado.empty:
        estado = limpiar_texto(

            estado_resultado.iloc[0][
                'NOMGEO'
            ]
        )        

    nucleo_resultado = nucleos_gdf[

        nucleos_gdf.contains(punto)

    ]

    if not nucleo_resultado.empty:

        nucleo = limpiar_texto(

            nucleo_resultado.iloc[0][
                'Name'
            ]
        )

    return {

        'estado': estado,

        'nucleo': nucleo
    }

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

    trabajo_realizado = db.Column(db.String(100))

    actividades_realizadas = db.Column(db.Text)

    trabajo_programado = db.Column(db.String(100))

    actividades_programadas = db.Column(db.Text)

    estatus_trabajo_realizado = db.Column(db.String(100))

    estatus_trabajo_programado = db.Column(db.String(100))

    latitud = db.Column(db.Float)

    longitud = db.Column(db.Float)

    precision_gps = db.Column(db.Float)

    fecha = db.Column(db.DateTime(timezone=True))

# =========================================
# MODELO SUB-ACTIVIDADES
# =========================================

class SubActividad(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    registro_id = db.Column(
        db.Integer,
        db.ForeignKey('registro.id'),
        nullable=False
    )

    tipo = db.Column(
        db.String(20)  # 'realizada' o 'programada'
    )

    entidad = db.Column(db.String(100))

    municipio = db.Column(db.String(100))

    nucleo = db.Column(db.String(200))

    frente = db.Column(db.String(20))

    descripcion = db.Column(db.Text)

    trabajo_campo = db.Column(db.String(300))

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

def limpiar_texto(texto):
    
    if not texto:

        return texto

    try:

        return str(texto).encode(
            'latin1'
        ).decode(
            'utf-8'
        )

    except:

        return str(texto)

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

    meses = {
        'January': 'Enero', 'February': 'Febrero', 'March': 'Marzo',
        'April': 'Abril', 'May': 'Mayo', 'June': 'Junio',
        'July': 'Julio', 'August': 'Agosto', 'September': 'Septiembre',
        'October': 'Octubre', 'November': 'Noviembre', 'December': 'Diciembre'
    }
    mes_en = ahora.strftime('%B')
    mes_label = f"{meses.get(mes_en, mes_en)} {ahora.year}"
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

            'ID': r.id,

            'DIRECCIÓN': r.direccion,

            'FECHA': r.fecha.strftime(
                '%d/%m/%Y %H:%M:%S'
            ) if r.fecha else '',

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

            'TRABAJO_REALIZADO': r.trabajo_realizado,

            'ESTATUS_TRABAJO_REALIZADO': r.estatus_trabajo_realizado,

            'ACTIVIDADES_REALIZADAS': r.actividades_realizadas,

            'TRABAJO_PROGRAMADO': r.trabajo_programado,

            'ESTATUS_TRABAJO_PROGRAMADO': r.estatus_trabajo_programado,

            'ACTIVIDADES_PROGRAMADAS': r.actividades_programadas,

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

    # =========================================
    # SUBIR REPORTE HTML A DRIVE
    # =========================================

    html_content = generar_reporte_quincenal_html(registros, mes_label)

    nombre_html = f'REPORTE_XENDA_{mes_actual}.html'
    ruta_html = os.path.join(os.getcwd(), nombre_html)

    with open(ruta_html, 'w', encoding='utf-8') as f:
        f.write(html_content)

    file_metadata_html = {
        'name': nombre_html,
        'parents': [folder_id]
    }

    media_html = MediaFileUpload(
        ruta_html,
        mimetype='text/html'
    )

    service.files().create(
        body=file_metadata_html,
        media_body=media_html,
        fields='id'
    ).execute()

    nueva_exportacion = Exportacion(

        mes=mes_actual

    )

    db.session.add(nueva_exportacion)

    db.session.commit()

# =========================================
# GENERAR PRE-REPORTE QUINCENAL HTML
# =========================================

def generar_reporte_quincenal_html(registros, periodo_label):
    quincena = periodo_quincena()

    tramos_nombres = {
        'TAP':   'AIFA - PACHUCA',
        'TIGDL': 'IRAPUATO - GUADALAJARA',
        'TMLM':  'MAZATLÁN - LOS MOCHIS',
        'TMQ':   'MÉXICO - QUERÉTARO',
        'TQI':   'QUERÉTARO - IRAPUATO',
        'TQSLP': 'QUERÉTARO - SAN LUIS POTOSÍ',
        'TSNL':  'SALTILLO - NUEVO LAREDO',
        'TSLPS': 'SAN LUIS POTOSÍ - SALTILLO',
    }

    # Agrupar por dirección y tramo
    grupos = {}
    for r in registros:
        key = (r.direccion or 'SIN DIRECCIÓN', r.tramo or '')
        if key not in grupos:
            grupos[key] = []
        grupos[key].append(r)

    secciones_html = ''

    for (direccion, tramo), regs in sorted(grupos.items()):

        tramo_nombre = tramos_nombres.get(tramo, '') if tramo else ''

        # Separar por tipo de propiedad
        social = [r for r in regs if r.tipo_propiedad and 'SOCIAL' in r.tipo_propiedad.upper()]
        privada = [r for r in regs if r.tipo_propiedad and 'PRIVADA' in r.tipo_propiedad.upper()]

        # ---- PORTADA DE SECCIÓN ----
        secciones_html += f'''
        <div class="pagina portada-seccion">
            <div class="portada-bandera"></div>
            <div class="portada-contenido">
                <p class="portada-subtitulo">Reporte de actividades</p>
                <div class="portada-divider"></div>
                <p class="portada-periodo">Proyectos Ferroviarios &middot; {quincena}</p>
                <p class="portada-tramo">{'TRAMO ' + tramo_nombre if tramo_nombre else 'DIRECCIÓN DE ' + direccion}</p>
                <p class="portada-dir">{direccion}</p>
            </div>
        </div>
        '''

        # ---- PROPIEDAD SOCIAL ----
        filas_tabla_social = ''
        if social:

            # SOCIAL — bloques realizados
            bloques_r = ''
            for r in social:
                trabajos_r = SubActividad.query.filter_by(registro_id=r.id, tipo='trabajo_realizado').all()
                if trabajos_r:
                    for tr in trabajos_r:
                        tipo_tr = tr.frente or ''
                        desc_tr = tr.descripcion or ''
                        estatus_tr = ''
                        if desc_tr.startswith('['):
                            end = desc_tr.find(']')
                            if end > 0:
                                estatus_tr = desc_tr[1:end]
                                desc_tr = desc_tr[end+2:]
                        bloques_r += f'<p><strong>Trabajo de {tipo_tr.lower()}:</strong> <span class="estatus-badge">{estatus_tr}</span></p><p class="acts-texto">{desc_tr.replace(chr(10), "<br>")}</p>'
                elif r.trabajo_realizado:
                    bloques_r += f'<p><strong>Trabajo de {(r.trabajo_realizado or "").lower()}:</strong> <span class="estatus-badge">{r.estatus_trabajo_realizado or ""}</span></p><p class="acts-texto">{(r.actividades_realizadas or "").replace(chr(10), "<br>")}</p>'

            # SOCIAL — bloques programados
            bloques_p = ''
            for r in social:
                trabajos_p = SubActividad.query.filter_by(registro_id=r.id, tipo='trabajo_programado').all()
                if trabajos_p:
                    for tp in trabajos_p:
                        tipo_tp = tp.frente or ''
                        desc_tp = tp.descripcion or ''
                        estatus_tp = ''
                        if desc_tp.startswith('['):
                            end = desc_tp.find(']')
                            if end > 0:
                                estatus_tp = desc_tp[1:end]
                                desc_tp = desc_tp[end+2:]
                        bloques_p += f'<p><strong>Trabajo de {tipo_tp.lower()}:</strong> <span class="estatus-badge">{estatus_tp}</span></p><p class="acts-texto">{desc_tp.replace(chr(10), "<br>")}</p>'
                elif r.trabajo_programado:
                    bloques_p += f'<p><strong>Trabajo de {(r.trabajo_programado or "").lower()}:</strong> <span class="estatus-badge">{r.estatus_trabajo_programado or ""}</span></p><p class="acts-texto">{(r.actividades_programadas or "").replace(chr(10), "<br>")}</p>'

            secciones_html += f'''
            <div class="pagina">
                <div class="encabezado-pagina">
                    <div class="encabezado-texto">
                        <p class="proyecto">Proyecto ferroviario</p>
                        <p class="tramo-nombre">{tramo_nombre if tramo_nombre else 'DIRECCIÓN DE ' + direccion}</p>
                        <p class="liberacion">Liberación del derecho de vía <span style="color:#6E152E;">(Propiedad Social)</span></p>
                    </div>
                    <div class="encabezado-logo"></div>
                </div>
                <div class="seccion-header verde">
                    ACTIVIDADES REALIZADAS EN CAMPO Y/O GABINETE, PROPIEDAD SOCIAL
                </div>
                <div class="seccion-body">{bloques_r}</div>
                <div class="seccion-header guinda">
                    ACTIVIDADES PROGRAMADAS DEL {quincena} EN PROPIEDAD SOCIAL
                </div>
                <div class="seccion-body">{bloques_p}</div>
            </div>
            '''
            # ---- TABLA NÚCLEOS SOCIAL ----
            filas_tabla_social = ''
            contador = 1
            for r in social:
                subs = SubActividad.query.filter_by(
                    registro_id=r.id,
                    tipo='realizada'
                ).all()
                if subs:
                    for sub in subs:
                        filas_tabla_social += f'''
                        <tr>
                            <td>{contador}</td>
                            <td>{sub.entidad or ''}</td>
                            <td>{sub.municipio or ''}</td>
                            <td>{sub.nucleo or ''}</td>
                            <td>{('F' + str(sub.frente)) if sub.frente else ''}</td>
                            <td>{'<strong>Trabajo de campo:</strong> ' + sub.trabajo_campo + '<br>' if sub.trabajo_campo else ''}<strong>Actividades:</strong> {(sub.descripcion or '').replace(chr(10), '<br>')}</td>
                        </tr>
                        '''
                        contador += 1
        if filas_tabla_social:
            secciones_html += f'''
            <div class="pagina">
                <div class="encabezado-pagina">
                    <div class="encabezado-texto">
                        <p class="proyecto">Proyecto ferroviario</p>
                        <p class="tramo-nombre">{tramo_nombre if tramo_nombre else 'DIRECCIÓN DE ' + direccion}</p>
                        <p class="liberacion">Liberación del derecho de vía <span style="color:#6E152E;">(Propiedad Social)</span></p>
                    </div>
                    <div class="encabezado-logo"></div>
                </div>
                <div class="seccion-header verde">
                    ACTIVIDADES REALIZADAS EN CAMPO (MEDICIÓN) &ndash; PROPIEDAD SOCIAL
                </div>
                <table class="tabla-nucleos">
                    <thead>
                        <tr>
                            <th>No.</th>
                            <th>Entidad Federativa</th>
                            <th>Municipio</th>
                            <th>N&uacute;cleo Agrario</th>
                            <th>Frente</th>
                            <th>Actividades Realizadas</th>
                        </tr>
                    </thead>
                    <tbody>
                        {filas_tabla_social}
                    </tbody>
                </table>
            </div>
            '''
            # TABLA NÚCLEOS PROGRAMADOS SOCIAL
            filas_prog_social = ''
            contador = 1
            for r in social:
                subs = SubActividad.query.filter_by(registro_id=r.id, tipo='programada').all()
                if subs:
                    for sub in subs:
                        filas_prog_social += f'''
                        <tr>
                            <td>{contador}</td>
                            <td>{sub.entidad or ''}</td>
                            <td>{sub.municipio or ''}</td>
                            <td>{sub.nucleo or ''}</td>
                            <td>{('F' + str(sub.frente)) if sub.frente else ''}</td>
                            <td>{'<strong>Trabajo de campo:</strong> ' + sub.trabajo_campo + '<br>' if sub.trabajo_campo else ''}<strong>Actividades:</strong> {(sub.descripcion or '').replace(chr(10), '<br>')}</td>
                        </tr>
                        '''
                        contador += 1

            if filas_prog_social:
                secciones_html += f'''
                <div class="pagina">
                    <div class="encabezado-pagina">
                        <div class="encabezado-texto">
                            <p class="proyecto">Proyecto ferroviario</p>
                            <p class="tramo-nombre">{tramo_nombre if tramo_nombre else 'DIRECCIÓN DE ' + direccion}</p>
                            <p class="liberacion">Liberación del derecho de vía <span style="color:#6E152E;">(Propiedad Social)</span></p>
                        </div>
                        <div class="encabezado-logo"></div>
                    </div>
                    <div class="seccion-header guinda">
                        ACTIVIDADES PROGRAMADAS EN CAMPO (MEDICIÓN) &ndash; PROPIEDAD SOCIAL
                    </div>
                    <table class="tabla-nucleos">
                        <thead><tr>
                            <th>No.</th><th>Entidad Federativa</th><th>Municipio</th>
                            <th>N&uacute;cleo Agrario</th><th>Frente</th><th>Actividades Programadas</th>
                        </tr></thead>
                        <tbody>{filas_prog_social}</tbody>
                    </table>
                </div>
                '''

        # ---- PROPIEDAD PRIVADA ----
        filas_tabla_priv = ''
        if privada:

            # Bloques realizados
            bloques_r = ''
            for r in privada:
                trabajos_r = SubActividad.query.filter_by(registro_id=r.id, tipo='trabajo_realizado').all()
                if trabajos_r:
                    for tr in trabajos_r:
                        tipo_tr = tr.frente or ''
                        desc_tr = tr.descripcion or ''
                        estatus_tr = ''
                        if desc_tr.startswith('['):
                            end = desc_tr.find(']')
                            if end > 0:
                                estatus_tr = desc_tr[1:end]
                                desc_tr = desc_tr[end+2:]
                        bloques_r += f'<p><strong>Trabajo de {tipo_tr.lower()}:</strong> <span class="estatus-badge">{estatus_tr}</span></p><p class="acts-texto">{desc_tr.replace(chr(10), "<br>")}</p>'
                elif r.trabajo_realizado:
                    bloques_r += f'<p><strong>Trabajo de {(r.trabajo_realizado or "").lower()}:</strong> <span class="estatus-badge">{r.estatus_trabajo_realizado or ""}</span></p><p class="acts-texto">{(r.actividades_realizadas or "").replace(chr(10), "<br>")}</p>'

            # Bloques programados
            bloques_p = ''
            for r in privada:
                trabajos_p = SubActividad.query.filter_by(registro_id=r.id, tipo='trabajo_programado').all()
                if trabajos_p:
                    for tp in trabajos_p:
                        tipo_tp = tp.frente or ''
                        desc_tp = tp.descripcion or ''
                        estatus_tp = ''
                        if desc_tp.startswith('['):
                            end = desc_tp.find(']')
                            if end > 0:
                                estatus_tp = desc_tp[1:end]
                                desc_tp = desc_tp[end+2:]
                        bloques_p += f'<p><strong>Trabajo de {tipo_tp.lower()}:</strong> <span class="estatus-badge">{estatus_tp}</span></p><p class="acts-texto">{desc_tp.replace(chr(10), "<br>")}</p>'
                elif r.trabajo_programado:
                    bloques_p += f'<p><strong>Trabajo de {(r.trabajo_programado or "").lower()}:</strong> <span class="estatus-badge">{r.estatus_trabajo_programado or ""}</span></p><p class="acts-texto">{(r.actividades_programadas or "").replace(chr(10), "<br>")}</p>'

            secciones_html += f'''
            <div class="pagina">
                <div class="encabezado-pagina">
                    <div class="encabezado-texto">
                        <p class="proyecto">Proyecto ferroviario</p>
                        <p class="tramo-nombre">{tramo_nombre if tramo_nombre else 'DIRECCIÓN DE ' + direccion}</p>
                        <p class="liberacion">Liberación del derecho de vía <span style="color:#6E152E;">(Propiedad Privada)</span></p>
                    </div>
                    <div class="encabezado-logo"></div>
                </div>
                <div class="seccion-header verde">
                    ACTIVIDADES REALIZADAS EN CAMPO Y/O GABINETE, PROPIEDAD PRIVADA
                </div>
                <div class="seccion-body">{bloques_r}</div>
                <div class="seccion-header guinda">
                    ACTIVIDADES PROGRAMADAS DEL {quincena} EN PROPIEDAD PRIVADA
                </div>
                <div class="seccion-body">{bloques_p}</div>
            </div>
            '''
            # ---- TABLA NÚCLEOS PRIVADA ----
            filas_tabla_priv = ''
            contador = 1
            for r in privada:
                subs = SubActividad.query.filter_by(
                    registro_id=r.id,
                    tipo='realizada'
                ).all()
                if subs:
                    for sub in subs:
                        filas_tabla_priv += f'''
                        <tr>
                            <td>{contador}</td>
                            <td>{sub.entidad or ''}</td>
                            <td>{sub.municipio or ''}</td>
                            <td>{sub.nucleo or ''}</td>
                            <td>{('F' + str(sub.frente)) if sub.frente else ''}</td>
                            <td>{'<strong>Trabajo de campo:</strong> ' + sub.trabajo_campo + '<br>' if sub.trabajo_campo else ''}<strong>Actividades:</strong> {(sub.descripcion or '').replace(chr(10), '<br>')}</td>
                        </tr>
                        '''
                        contador += 1
        if filas_tabla_priv:
            secciones_html += f'''
            <div class="pagina">
                <div class="encabezado-pagina">
                    <div class="encabezado-texto">
                        <p class="proyecto">Proyecto ferroviario</p>
                        <p class="tramo-nombre">{tramo_nombre if tramo_nombre else 'DIRECCIÓN DE ' + direccion}</p>
                        <p class="liberacion">Liberación del derecho de vía <span style="color:#6E152E;">(Propiedad Privada)</span></p>
                    </div>
                    <div class="encabezado-logo"></div>
                </div>
                <div class="seccion-header verde">
                    ACTIVIDADES REALIZADAS EN CAMPO (MEDICIÓN) &ndash; PROPIEDAD PRIVADA
                </div>
                <table class="tabla-nucleos">
                    <thead>
                        <tr>
                            <th>No.</th>
                            <th>Entidad Federativa</th>
                            <th>Municipio</th>
                            <th>N&uacute;cleo Agrario</th>
                            <th>Frente</th>
                            <th>Actividades Realizadas</th>
                        </tr>
                    </thead>
                    <tbody>
                        {filas_tabla_priv}
                    </tbody>
                </table>
            </div>
            '''
             # TABLA NÚCLEOS PROGRAMADOS PRIVADA
            filas_prog_privada = ''
            contador = 1
            for r in privada:
                subs = SubActividad.query.filter_by(registro_id=r.id, tipo='programada').all()
                if subs:
                    for sub in subs:
                        filas_prog_privada += f'''
                        <tr>
                            <td>{contador}</td>
                            <td>{sub.entidad or ''}</td>
                            <td>{sub.municipio or ''}</td>
                            <td>{sub.nucleo or ''}</td>
                            <td>{('F' + str(sub.frente)) if sub.frente else ''}</td>
                            <td>{'<strong>Trabajo de campo:</strong> ' + sub.trabajo_campo + '<br>' if sub.trabajo_campo else ''}<strong>Actividades:</strong> {(sub.descripcion or '').replace(chr(10), '<br>')}</td>
                        </tr>
                        '''
                        contador += 1

            if filas_prog_privada:
                secciones_html += f'''
                <div class="pagina">
                    <div class="encabezado-pagina">
                        <div class="encabezado-texto">
                            <p class="proyecto">Proyecto ferroviario</p>
                            <p class="tramo-nombre">{tramo_nombre if tramo_nombre else 'DIRECCIÓN DE ' + direccion}</p>
                            <p class="liberacion">Liberación del derecho de vía <span style="color:#6E152E;">(Propiedad Privada)</span></p>
                        </div>
                        <div class="encabezado-logo"></div>
                    </div>
                    <div class="seccion-header guinda">
                        ACTIVIDADES PROGRAMADAS EN CAMPO (MEDICIÓN) &ndash; PROPIEDAD PRIVADA
                    </div>
                    <table class="tabla-nucleos">
                        <thead><tr>
                            <th>No.</th><th>Entidad Federativa</th><th>Municipio</th>
                            <th>N&uacute;cleo Agrario</th><th>Frente</th><th>Actividades Programadas</th>
                        </tr></thead>
                        <tbody>{filas_prog_privada}</tbody>
                    </table>
                </div>
                '''

    html = f'''<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Pre-Reporte Quincenal &middot; {periodo_label}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: 'Segoe UI', Arial, sans-serif;
    background: #f0f0f0;
    color: #1a1a1a;
  }}
  .pagina {{
    width: 960px;
    min-height: 540px;
    background: url('/static/contenido_reporte.png') no-repeat center center;
    background-size: 100% 100%;
    margin: 30px auto;
    padding: 40px 48px;
    box-shadow: 0 4px 24px rgba(0,0,0,0.12);
    position: relative;
  }}
  /* ENCABEZADO */
  .encabezado-pagina {{
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 20px;
  }}
  .encabezado-texto p.proyecto {{
    font-size: 13px;
    color: #BC945A;
    font-style: italic;
    margin-bottom: 2px;
  }}
  .encabezado-texto p.tramo-nombre {{
    font-size: 20px;
    font-weight: bold;
    color: #6E152E;
    text-transform: uppercase;
    margin-bottom: 2px;
  }}
  .encabezado-texto p.liberacion {{
    font-size: 13px;
    color: #245C4F;
    font-weight: 500;
  }}
  .encabezado-logo {{
    width: 120px;
    height: 35px;
    background: url('/static/logo_RAN.png') no-repeat right center;
    background-size: contain;
  }}
  .pagina::after {{
    content: '';
    display: block;
    position: absolute;
    bottom: -15px;
    left: 18px;
    width: 100px;
    height: 90px;
    background: url('/static/gob_mex2-sf.png') no-repeat left center;
    background-size: contain;
  }}
  /* PORTADA */
  .portada-seccion {{
    background: url('/static/portada_reporte.png') no-repeat center center;
    background-size: 100% 100%;
    color: white;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: space-between;
    min-height: 540px;
    padding: 0;
    overflow: hidden;
  }}
  .portada-bandera {{
    position: absolute;
    left: 0;
    bottom: -10px;
    width: 200px;
    height: 260px;
    background: url('/static/bandera.png') no-repeat left center;
    background-size: contain;
    z-index: 10;
  }}
  .portada-seccion::before {{
    content: '';
    position: absolute;
    top: 16px;
    right: 24px;
    width: 380px;
    height: 100px;
    background: url('/static/encabezado_html1.png') no-repeat right center;
    background-size: contain;
    filter: brightness(10);
  }}
  .portada-seccion::after {{
    content: 'Dirección General de Catastro y Asistencia Técnica · Dirección Técnica';
    display: block;
    width: 100%;
    text-align: center;
    font-size: 11px;
    color: #BC945A;
    background: transparent;
    padding: 12px;
    letter-spacing: 0.05em;
  }}
  .portada-contenido {{
    text-align: center;
    padding: 30px 60px;
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
  }}
  .portada-subtitulo {{
    font-size: 15px;
    font-weight: 300;
    margin-bottom: 6px;
    color: #dec9a2;
    letter-spacing: 0.1em;
    text-transform: uppercase;
  }}
  .portada-inst {{
    font-size: 13px;
    color: rgba(222,201,162,0.7);
    margin-bottom: 3px;
  }}
  .portada-divider {{
    width: 60px;
    height: 2px;
    background: #BC945A;
    margin: 20px auto;
  }}
  .portada-periodo {{
    font-size: 15px;
    color: #dec9a2;
    margin-bottom: 16px;
    font-style: italic;
  }}
  .portada-tramo {{
    font-size: 32px;
    font-weight: bold;
    color: white;
    margin-bottom: 10px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    text-shadow: 0 2px 8px rgba(0,0,0,0.3);
  }}
  .portada-dir {{
    font-size: 15px;
    color: #BC945A;
    text-transform: uppercase;
    font-weight: 600;
    letter-spacing: 0.08em;
    border-top: 1px solid rgba(188,148,90,0.4);
    padding-top: 12px;
    margin-top: 8px;
  }}
  /* SECCIONES */
  .seccion-header {{
    color: #dec9a2;
    font-size: 12px;
    font-weight: bold;
    padding: 10px 16px;
    margin-bottom: 16px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    text-align: center;
  }}
  .seccion-header.verde {{ background: #245C4F; }}
  .seccion-header.guinda {{ background: #6E152E; margin-top: 24px; }}
  .seccion-body {{
    padding: 0 8px 16px 8px;
    font-size: 13px;
    line-height: 1.7;
  }}
  .seccion-body p {{ margin-bottom: 8px; }}
  .acts-texto {{
    color: #333;
    padding-left: 16px;
    border-left: 3px solid #dec9a2;
    margin-top: 8px;
  }}
  .estatus-badge {{
    display: inline-block;
    background: #dec9a2;
    color: #691B4F;
    font-size: 11px;
    font-weight: bold;
    padding: 2px 10px;
    border-radius: 12px;
    margin-left: 6px;
    text-transform: uppercase;
  }}
  /* TABLA */
  .tabla-nucleos {{
    width: 100%;
    border-collapse: collapse;
    font-size: 12px;
    margin-top: 12px;
  }}
  .tabla-nucleos th {{
    background: #245C4F;
    color: #dec9a2;
    padding: 10px 8px;
    text-align: center;
    font-weight: 600;
    text-transform: uppercase;
    font-size: 11px;
    border: 1px solid #1a4438;
  }}
  .tabla-nucleos td {{
    padding: 9px 8px;
    border: 1px solid #d0d0d0;
    vertical-align: middle;
  }}
  .tabla-nucleos tr:nth-child(even) td {{
    background: #f9f6f0;
  }}
  .tabla-nucleos td:nth-child(1) {{ width: 40px; text-align: center; font-weight: bold; }}
  .tabla-nucleos td:nth-child(2) {{ width: 120px; font-weight: bold; text-align: center; }}
  .tabla-nucleos td:nth-child(3) {{ width: 120px; text-align:center; }}
  .tabla-nucleos td:nth-child(4) {{ width: 130px; color: #6E152E; font-weight: bold; text-align: center; }}
  .tabla-nucleos td:nth-child(5) {{ width: 60px; text-align: center; }}
  .tabla-nucleos td:nth-child(6) {{ font-size: 12px; }}
  .tabla-nucleos td {{
    padding: 9px 8px;
    border-bottom: 1px solid #e0e0e0;
    vertical-align: top;
  }}
  .tabla-nucleos tr:nth-child(even) td {{
    background: #f9f6f0;
  }}
  /* PIE */
  @media print {{
    body {{ background: white; }}
    .pagina {{
      box-shadow: none;
      margin: 0;
      page-break-after: always;
    }}
  }}
</style>
</head>
<body>
{secciones_html}
<p style="text-align:center;font-size:11px;color:#aaa;padding:20px;">
  Pre-reporte generado autom&aacute;ticamente por Xenda
</p>
</body>
</html>'''

    return html

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
@limiter.limit("5 per minute")
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

    if session.get('usuario') not in ADMIN_CORREOS:
    
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

    if session['usuario'] not in ADMIN_CORREOS:

        return 'Acceso no autorizado'

    usuario = Usuario.query.get_or_404(id)

    db.session.delete(usuario)

    db.session.commit()

    flash('Usuario eliminado')

    return redirect('/admin')

# =========================================
# REINICIAR REGISTROS
# =========================================

@app.route(
    '/reiniciar_registros',
    methods=['GET', 'POST']
)
def reiniciar_registros():
    if session.get('usuario') not in ADMIN_CORREOS:
        return 'No autorizado', 403
    if request.method == 'POST':
        confirmacion = request.form.get('confirmacion', '')
        if confirmacion.upper() != 'CONFIRMAR':
            flash('Escribe CONFIRMAR para continuar')
            return redirect('/reiniciar_registros')
        SubActividad.query.delete()
        Registro.query.delete()
        RegistroEliminado.query.delete()
        Exportacion.query.delete()
        db.session.commit()
        flash('Registros reiniciados correctamente')
        return redirect('/admin')
    return '''
        <h2>¿Seguro que deseas reiniciar TODOS los registros?</h2>
        <p>Esta acción no se puede deshacer.</p>
        <p>Escribe <strong>CONFIRMAR</strong> para continuar:</p>
        <form method="POST">
            <input
                type="text"
                name="confirmacion"
                placeholder="Escribe CONFIRMAR"
                style="padding:8px; font-size:16px; margin:10px 0;"
            >
            <br>
            <button type="submit">Reiniciar registros</button>
            <a href="/admin">Cancelar</a>
        </form>
    '''

# =========================================
# SESIONES ACTIVAS
# =========================================

@app.route('/sesiones')

def sesiones():

    if session.get('usuario') not in ADMIN_CORREOS:

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

    if session.get('usuario') not in ADMIN_CORREOS:

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

    if session.get('usuario') not in ADMIN_CORREOS:
    
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
#        session.get('usuario') not in ADMIN_CORREOS
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
            
            latitud=(
                float(request.form.get('latitud'))
                if request.form.get('latitud')
                else None
            ),

            longitud=(
                float(request.form.get('longitud'))
                if request.form.get('longitud')
                else None
            ),

            precision_gps=(
                float(request.form.get('precision_gps'))
                if request.form.get('precision_gps')
                else None
            ),

            usuario=session['usuario'],

            direccion=request.form.get('direccion'),

            fecha=hora_cdmx(),

            tramo=request.form.get('tramo') or None,

            entidad=request.form.get('entidad') or None,

            municipio=request.form.get('municipio') or None,

            nucleo=request.form.get('nucleo') or None,

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

            observaciones=request.form.get('observaciones', '').upper() or None,

            trabajo_realizado=request.form.get('trabajo_realizado'),

            actividades_realizadas=(
                request.form.get('actividades_realizadas', '').upper()
                or None
            ),

            trabajo_programado=request.form.get('trabajo_programado'),

            actividades_programadas=(
                request.form.get('actividades_programadas', '').upper()
                or None
            ),

            estatus_trabajo_realizado=request.form.get('estatus_trabajo_realizado'),

            estatus_trabajo_programado=request.form.get('estatus_trabajo_programado'),
        )

        db.session.add(nuevo)
        db.session.flush()

        # =====================================
        # GUARDAR SUB-ACTIVIDADES
        # =====================================

        import json

        sub_realizadas = request.form.get('sub_actividades_realizadas', '[]')
        sub_programadas = request.form.get('sub_actividades_programadas', '[]')

        try:
            for item in json.loads(sub_realizadas):
                sub = SubActividad(
                    registro_id=nuevo.id,
                    tipo='realizada',
                    entidad=item.get('entidad', ''),
                    municipio=item.get('municipio', ''),
                    nucleo=item.get('nucleo', ''),
                    frente=item.get('frente', ''),
                    descripcion=item.get('descripcion', ''),
                    trabajo_campo=item.get('trabajo_campo', '')
                )
                db.session.add(sub)
        except:
            pass

        try:
            for item in json.loads(sub_programadas):
                sub = SubActividad(
                    registro_id=nuevo.id,
                    tipo='programada',
                    entidad=item.get('entidad', ''),
                    municipio=item.get('municipio', ''),
                    nucleo=item.get('nucleo', ''),
                    frente=item.get('frente', ''),
                    descripcion=item.get('descripcion', ''),
                    trabajo_campo=item.get('trabajo_campo', '')
                )
                db.session.add(sub)
        except:
            pass

        trabajos_realizados_json = request.form.get('trabajos_realizados_json', '[]')
        trabajos_programados_json = request.form.get('trabajos_programados_json', '[]')

        try:
            for item in json.loads(trabajos_realizados_json):
                sub = SubActividad(
                    registro_id=nuevo.id,
                    tipo='trabajo_realizado',
                    entidad='',
                    municipio='',
                    nucleo='',
                    frente=item.get('tipo', ''),
                    descripcion=f"[{item.get('estatus','')}] {item.get('descripcion','')}"
                )
                db.session.add(sub)
        except:
            pass

        try:
            for item in json.loads(trabajos_programados_json):
                sub = SubActividad(
                    registro_id=nuevo.id,
                    tipo='trabajo_programado',
                    entidad='',
                    municipio='',
                    nucleo='',
                    frente=item.get('tipo', ''),
                    descripcion=f"[{item.get('estatus','')}] {item.get('descripcion','')}"
                )
                db.session.add(sub)
        except:
            pass

        db.session.commit()

        flash(
            'Registro guardado exitosamente'
        )

        return redirect('/')

    return render_template(

        'index.html',

        entidades=entidades,

        catalogo_json=catalogo[
            ['TRAMO', 'ENTIDAD_FEDERATIVA', 'MUNICIPIO', 'NUCLEO_AGRARIO']
        ].to_json(orient='records', force_ascii=False)

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

    # Combinar actividades del registro + subactividades para mostrar todo
    def combinar_actividades(reg, subs, kind):
        partes = []
        campo = reg.actividades_realizadas if kind == 'realizado' else reg.actividades_programadas
        if campo:
            partes.append(campo)
        tipo_bloque = 'trabajo_' + kind
        for s in subs:
            if s.tipo == tipo_bloque and s.descripcion:
                desc = s.descripcion
                estatus = ''
                if desc.startswith('['):
                    fin = desc.find(']')
                    if fin > 0:
                        estatus = desc[1:fin]
                        desc = desc[fin + 1:].strip()
                etq = (s.frente or '').strip()
                prefijo = ' / '.join(x for x in [etq, estatus] if x)
                partes.append(f"[{prefijo}] {desc}" if prefijo else desc)
        tipo_tabla = 'realizada' if kind == 'realizado' else 'programada'
        for s in subs:
            if s.tipo == tipo_tabla and (s.descripcion or s.trabajo_campo):
                ubic = ', '.join(x for x in [s.entidad, s.municipio, s.nucleo,
                                             ('F' + str(s.frente)) if s.frente else ''] if x)
                txt = s.descripcion or ''
                if s.trabajo_campo:
                    txt = f"Trabajo de campo: {s.trabajo_campo}. {txt}"
                partes.append(f"({ubic}) {txt}" if ubic else txt)
        return ' || '.join(partes) if partes else ''

    for r in lista:
        subs = SubActividad.query.filter_by(registro_id=r.id).all()
        r.acts_realizadas_full = combinar_actividades(r, subs, 'realizado')
        r.acts_programadas_full = combinar_actividades(r, subs, 'programado')

    entidades = sorted([
        e[0]
        for e in db.session.query(Registro.entidad).distinct()
        if e[0]
    ])

    municipios = sorted([
        m[0]
        for m in db.session.query(Registro.municipio).distinct()
        if m[0]
    ])

    tramos = sorted([
        t[0]
        for t in db.session.query(Registro.tramo).distinct()
        if t[0]
    ])

    usuarios = sorted([
        u[0]
        for u in db.session.query(Registro.usuario).distinct()
        if u[0]
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

    if session.get('usuario') not in ADMIN_CORREOS:

        return 'No autorizado', 403

    registro = Registro.query.get_or_404(id)

    SubActividad.query.filter_by(registro_id=id).delete()

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

    if session.get('usuario') not in ADMIN_CORREOS:

        return 'No autorizado', 403

    usuarios = Usuario.query.all()

    datos = []

    for u in usuarios:

        datos.append({

            'CORREO': u.correo
        })

    df = pd.DataFrame(datos)

    ruta_archivo = os.path.join(
    '/tmp',
    'registros_xenda.xlsx'
    )

    df.to_excel(
        ruta_archivo,
        index=False
    )

    return send_file(
        ruta_archivo,
        as_attachment=True
    )

# =========================================
# DESCARGAR REGISTROS ELIMINADOS
# =========================================

@app.route('/descargar_eliminados')

def descargar_eliminados():

    if session.get('usuario') not in ADMIN_CORREOS:

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

            'FECHA_ELIMINACION': r.fecha_eliminacion.strftime(
                '%d/%m/%Y %H:%M:%S'
            ) if r.fecha_eliminacion else '',

            'TRAMO': r.tramo,

            'ENTIDAD': r.entidad,

            'MUNICIPIO': r.municipio,

            'NUCLEO': r.nucleo,

            'FRENTE': r.frente,

            'ACTIVIDAD': r.actividad,

            'TIPO': r.tipo,

            'TIPO_PROPIEDAD': r.tipo_propiedad,

            'OBSERVACIONES': r.observaciones,

            'FECHA_ORIGINAL': r.fecha_original.strftime(
                '%d/%m/%Y %H:%M:%S'
            ) if r.fecha_original else '',
        })

    df = pd.DataFrame(datos)

    ruta_archivo = os.path.join(
        '/tmp',
        'registros_eliminados.xlsx'
    )

    df.to_excel(
        ruta_archivo,
        index=False
    )

    return send_file(
        ruta_archivo,
        as_attachment=True
    )

# =========================================
# DESCARGAR REGISTROS 
# =========================================

@app.route('/descargar_registros')

def descargar_registros():

    if session.get('usuario') not in ADMIN_CORREOS:

        return 'No autorizado', 403

    registros = Registro.query.order_by(
        Registro.fecha.desc()
    ).all()

    datos = []

    for r in registros:

        subs_realizadas = SubActividad.query.filter_by(
            registro_id=r.id, tipo='realizada'
        ).all()

        subs_programadas = SubActividad.query.filter_by(
            registro_id=r.id, tipo='programada'
        ).all()

        base = {
            'DIRECCIÓN':                      r.direccion,
            'TRAMO':                          r.tramo,
            'TIPO DE PROPIEDAD':              r.tipo_propiedad,
            'TIPO DE ACTIVIDAD':              r.actividad,
            'MODALIDAD':                      r.tipo,
            'NO. DE INFOGRAFÍAS':             r.num_infografias,
            'INFOGRAFÍAS GENERADAS':          r.infografias_generadas,
            'INFOGRAFÍAS VALIDADAS':          r.infografias_validadas,
            'ESTATUS INFOGRAFÍAS':            r.estatus_infografias,
            'NO. DE MEDICIONES':              r.mediciones_agroforestales,
            'NO. DE FICHAS':                  r.mediciones_bdts,
            'PLANOS':                         r.planos,
            'PLANOS GENERADOS':               r.planos_generados,
            'PLANOS VALIDADOS':               r.planos_validados,
            'TIPO DE TRABAJO REALIZADO':      r.trabajo_realizado,
            'ESTATUS TRABAJO REALIZADO':      r.estatus_trabajo_realizado,
            'DESCRIPCIÓN ACTIVIDADES REALIZADAS': r.actividades_realizadas,
            'ENTIDAD (TABLA)':                '',
            'MUNICIPIO (TABLA)':              '',
            'NÚCLEO AGRARIO (TABLA)':         '',
            'FRENTE (TABLA)':                 '',
            'TRABAJO DE CAMPO (TABLA)':       '',
            'DESCRIPCIÓN ACTIVIDAD (TABLA)':  '',
            'TIPO DE TRABAJO PROGRAMADO':     r.trabajo_programado,
            'ESTATUS TRABAJO PROGRAMADO':     r.estatus_trabajo_programado,
            'DESCRIPCIÓN ACTIVIDADES PROGRAMADAS': r.actividades_programadas,
            'USUARIO':                        r.usuario,
            'FECHA':                          r.fecha.strftime('%d/%m/%Y %H:%M:%S') if r.fecha else '',
        }

        # Si hay sub-actividades realizadas, una fila por cada una
        if subs_realizadas:
            for sub in subs_realizadas:
                fila = base.copy()
                fila['ENTIDAD (TABLA)']               = sub.entidad or ''
                fila['MUNICIPIO (TABLA)']             = sub.municipio or ''
                fila['NÚCLEO AGRARIO (TABLA)']        = sub.nucleo or ''
                fila['FRENTE (TABLA)']                = sub.frente or ''
                fila['TRABAJO DE CAMPO (TABLA)']      = sub.trabajo_campo or ''
                fila['DESCRIPCIÓN ACTIVIDAD (TABLA)'] = sub.descripcion or ''
                datos.append(fila)
        else:
            datos.append(base)

    df = pd.DataFrame(datos)

    ruta_archivo = os.path.join(
        '/tmp',
        'registros_xenda.xlsx'
    )

    df.to_excel(
        ruta_archivo,
        index=False
    )

    return send_file(
        ruta_archivo,
        as_attachment=True
    )

# =========================================
# DASHBOARD
# =========================================

@app.route('/dashboard')

def dashboard():

    if 'usuario' not in session:

        return redirect('/login')

    # =====================================
    # KPIs
    # =====================================

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

    usuarios_activos = db.session.query(
        Registro.usuario
    ).distinct().count()

    # =====================================
    # REGISTROS POR TRAMO
    # =====================================

    tramos_data = db.session.query(

        Registro.tramo,

        db.func.count(
            Registro.id
        )

    ).group_by(
        Registro.tramo
    ).all()

    tramos_labels = [
        t[0]
        for t in tramos_data
        if t[0]
    ]

    tramos_values = [
        t[1]
        for t in tramos_data
        if t[0]
    ]

    # =====================================
    # REGISTROS RECIENTES
    # =====================================

    recientes = Registro.query.order_by(

        Registro.fecha.desc()

    ).limit(10).all()

    # =====================================
    # DETALLES POR TRAMO
    # =====================================

    detalle_tramos = {}

    for tramo in tramos_labels:

        registros_tramo = Registro.query.filter_by(
            tramo=tramo
        ).all()

        municipios = sorted(list(set([
            str(r.municipio)
            for r in registros_tramo
            if r.municipio
        ])))

        usuarios = sorted(list(set([
            str(r.usuario)
            for r in registros_tramo
            if r.usuario
        ])))

        detalle_tramos[tramo] = {
            'total': len(registros_tramo),
            'municipios': municipios,
            'usuarios': usuarios
        }

    # =====================================
    # REGISTROS POR DIRECCIÓN
    # =====================================

    direcciones_data = db.session.query(
        Registro.direccion,
        db.func.count(Registro.id)
    ).group_by(Registro.direccion).order_by(db.func.count(Registro.id).desc()).all()
    direcciones_labels = [d[0] for d in direcciones_data if d[0]]
    direcciones_values = [d[1] for d in direcciones_data if d[0]]

    propiedad_data = db.session.query(
        Registro.tipo_propiedad,
        db.func.count(Registro.id)
    ).group_by(Registro.tipo_propiedad).all()
    propiedad_labels = [p[0] for p in propiedad_data if p[0]]
    propiedad_values = [p[1] for p in propiedad_data if p[0]]

    actividad_data = db.session.query(
        Registro.actividad,
        db.func.count(Registro.id)
    ).group_by(Registro.actividad).order_by(db.func.count(Registro.id).desc()).all()
    actividad_labels = [a[0] for a in actividad_data if a[0]]
    actividad_values = [a[1] for a in actividad_data if a[0]]

    total_fichas = db.session.query(db.func.sum(Registro.mediciones_bdts)).scalar() or 0
    total_planos_generados = db.session.query(db.func.sum(Registro.planos_generados)).scalar() or 0
    total_planos_validados = db.session.query(db.func.sum(Registro.planos_validados)).scalar() or 0

    # =====================================
    # JSON DASHBOARD
    # =====================================

    return render_template(
        'dashboard.html',
        total_registros=total_registros,
        total_infografias=total_infografias,
        total_planos=total_planos,
        total_mediciones=total_mediciones,
        usuarios_activos=usuarios_activos,
        tramos_labels=tramos_labels,
        tramos_values=tramos_values,
        recientes=recientes,
        detalle_tramos=detalle_tramos,
        direcciones_labels=direcciones_labels,
        direcciones_values=direcciones_values,
        propiedad_labels=propiedad_labels,
        propiedad_values=propiedad_values,
        actividad_labels=actividad_labels,
        actividad_values=actividad_values,
        total_fichas=total_fichas,
        total_planos_generados=total_planos_generados,
        total_planos_validados=total_planos_validados,
        admin_correo=ADMIN_CORREO
    )

# =========================================
# MAPA GENERAL
# =========================================

@app.route('/mapa_registros')

def mapa_registros():

    if session.get('usuario') not in ADMIN_CORREOS:

        return 'No autorizado', 403

    registros = Registro.query.filter(

        Registro.latitud.isnot(None),

        Registro.longitud.isnot(None)

    ).all()

    for r in registros:
    
        if r.latitud and r.longitud:

            ubicacion = obtener_ubicacion(

                r.latitud,

                r.longitud
            )

            r.estado_geo = ubicacion['estado']

            r.nucleo_geo = ubicacion['nucleo']

        else:

            r.estado_geo = 'Sin coordenadas'

            r.nucleo_geo = 'Sin coordenadas'

    return render_template(

        'mapa_registros.html',

        registros=registros
    )

# =========================================
# MANIFEST PWA
# =========================================

@app.route('/manifest.json')
def manifest():
    return send_file(
        os.path.join(os.path.dirname(__file__), 'manifest.json'),
        mimetype='application/manifest+json'
    )

# =========================================
# SERVICE WORKER PWA
# =========================================

@app.route('/service_worker.js')
def service_worker():
    return send_file('static/service_worker.js', mimetype='application/javascript')

# =========================================
# PRE-REPORTE QUINCENAL
# =========================================

@app.route('/pre_reporte')

def pre_reporte():

    if session.get('usuario') not in ADMIN_CORREOS:
        return 'No autorizado', 403

    ahora = hora_cdmx()

    registros = Registro.query.filter(
        db.extract('year', Registro.fecha) == ahora.year,
        db.extract('month', Registro.fecha) == ahora.month
    ).order_by(Registro.direccion, Registro.tramo).all()

    if not registros:
        return '<h2 style="font-family:sans-serif;padding:40px;">No hay registros en el periodo actual.</h2>'

    meses = {
        'January': 'Enero', 'February': 'Febrero', 'March': 'Marzo',
        'April': 'Abril', 'May': 'Mayo', 'June': 'Junio',
        'July': 'Julio', 'August': 'Agosto', 'September': 'Septiembre',
        'October': 'Octubre', 'November': 'Noviembre', 'December': 'Diciembre'
    }
    mes_en = ahora.strftime('%B')
    periodo_label = f"{meses.get(mes_en, mes_en)} {ahora.year}"

    html = generar_reporte_quincenal_html(registros, periodo_label)

    return html

# =========================================
# PRE-REPORTE POR TRAMO
# =========================================

@app.route('/pre_reporte_tramo')
def pre_reporte_tramo():
    if session.get('usuario') not in ADMIN_CORREOS:
        return 'No autorizado', 403

    ahora = hora_cdmx()
    tramos_nombres = {
        'TAP':   'AIFA - PACHUCA',
        'TIGDL': 'IRAPUATO - GUADALAJARA',
        'TMLM':  'MAZATLÁN - LOS MOCHIS',
        'TMQ':   'MÉXICO - QUERÉTARO',
        'TQI':   'QUERÉTARO - IRAPUATO',
        'TQSLP': 'QUERÉTARO - SAN LUIS POTOSÍ',
        'TSNL':  'SALTILLO - NUEVO LAREDO',
        'TSLPS': 'SAN LUIS POTOSÍ - SALTILLO',
    }

    tramos_disponibles = db.session.query(Registro.tramo).filter(
        db.extract('year', Registro.fecha) == ahora.year,
        db.extract('month', Registro.fecha) == ahora.month,
        Registro.tramo.isnot(None)
    ).distinct().all()

    tramos = [(t[0], tramos_nombres.get(t[0], t[0])) for t in tramos_disponibles]

    return f'''<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"><title>Pre-Reporte por Tramo</title>
<style>
  body {{ font-family: Segoe UI, sans-serif; background: #f0f0f0; padding: 40px; }}
  h2 {{ color: #6E152E; margin-bottom: 24px; }}
  .btn {{ display: block; width: 300px; margin: 10px auto; padding: 14px;
          background: #6E152E; color: white; text-align: center;
          border-radius: 10px; text-decoration: none; font-weight: bold; }}
  .btn:hover {{ background: #a42145; }}
</style>
</head>
<body>
<h2 style="text-align:center;">Seleccione un tramo</h2>
{''.join(f'<a class="btn" href="/pre_reporte_tramo/{t[0]}" target="_blank">{t[1]}</a>' for t in sorted(tramos, key=lambda x: x[1]))}
</body></html>'''


@app.route('/pre_reporte_tramo/<tramo>')
def pre_reporte_tramo_detalle(tramo):
    if session.get('usuario') not in ADMIN_CORREOS:
        return 'No autorizado', 403

    ahora = hora_cdmx()
    registros = Registro.query.filter(
        db.extract('year', Registro.fecha) == ahora.year,
        db.extract('month', Registro.fecha) == ahora.month,
        Registro.tramo == tramo
    ).order_by(Registro.direccion).all()

    if not registros:
        return '<h2 style="font-family:sans-serif;padding:40px;">No hay registros para este tramo.</h2>'

    meses = {
        'January': 'Enero', 'February': 'Febrero', 'March': 'Marzo',
        'April': 'Abril', 'May': 'Mayo', 'June': 'Junio',
        'July': 'Julio', 'August': 'Agosto', 'September': 'Septiembre',
        'October': 'Octubre', 'November': 'Noviembre', 'December': 'Diciembre'
    }
    mes_en = ahora.strftime('%B')
    periodo_label = f"{meses.get(mes_en, mes_en)} {ahora.year}"

    return generar_reporte_quincenal_html(registros, periodo_label)


# =========================================
# PRE-REPORTE POR DIRECCIÓN
# =========================================

@app.route('/pre_reporte_direccion')
def pre_reporte_direccion():
    if session.get('usuario') not in ADMIN_CORREOS:
        return 'No autorizado', 403

    ahora = hora_cdmx()

    direcciones_disponibles = db.session.query(Registro.direccion).filter(
        db.extract('year', Registro.fecha) == ahora.year,
        db.extract('month', Registro.fecha) == ahora.month
    ).distinct().all()

    direcciones = [d[0] for d in direcciones_disponibles if d[0]]

    return f'''<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"><title>Pre-Reporte por Dirección</title>
<style>
  body {{ font-family: Segoe UI, sans-serif; background: #f0f0f0; padding: 40px; }}
  h2 {{ color: #245C4F; margin-bottom: 24px; }}
  .btn {{ display: block; width: 340px; margin: 10px auto; padding: 14px;
          background: #245C4F; color: white; text-align: center;
          border-radius: 10px; text-decoration: none; font-weight: bold; }}
  .btn:hover {{ background: #1a3f36; }}
</style>
</head>
<body>
<h2 style="text-align:center;">Seleccione una dirección</h2>
{''.join(f'<a class="btn" href="/pre_reporte_direccion/{d}" target="_blank">{d}</a>' for d in sorted(direcciones))}
</body></html>'''


@app.route('/pre_reporte_direccion/<direccion>')
def pre_reporte_direccion_detalle(direccion):
    if session.get('usuario') not in ADMIN_CORREOS:
        return 'No autorizado', 403

    ahora = hora_cdmx()
    registros = Registro.query.filter(
        db.extract('year', Registro.fecha) == ahora.year,
        db.extract('month', Registro.fecha) == ahora.month,
        Registro.direccion == direccion,
    ).order_by(Registro.fecha).all()

    if not registros:
        return '<h2 style="font-family:sans-serif;padding:40px;">No hay registros para esta dirección.</h2>'

    meses = {
        'January': 'Enero', 'February': 'Febrero', 'March': 'Marzo',
        'April': 'Abril', 'May': 'Mayo', 'June': 'Junio',
        'July': 'Julio', 'August': 'Agosto', 'September': 'Septiembre',
        'October': 'Octubre', 'November': 'Noviembre', 'December': 'Diciembre'
    }
    mes_en = ahora.strftime('%B')
    periodo_label = f"{meses.get(mes_en, mes_en)} {ahora.year}"

    return generar_reporte_quincenal_html(registros, periodo_label)

# =========================================
# VERSION
# =========================================

@app.route('/version')
def version():
    return 'v2'

@app.route('/test_html')
def test_html():
    with open('templates/index.html', 'r', encoding='utf-8') as f:
        contenido = f.read()
    if 'CONFIG_DIRECCION' in contenido:
        return 'CONFIG_DIRECCION ENCONTRADO'
    else:
        return 'NO ENCONTRADO'

# =========================================
# CREAR TABLAS
# =========================================

with app.app_context():
    
    db.create_all()

    for correo_admin in ADMIN_CORREOS:
        admin = Usuario.query.filter_by(correo=correo_admin).first()
        if not admin:
            nuevo_admin = Usuario(correo=correo_admin)
            db.session.add(nuevo_admin)
            db.session.commit()
            print(f'ADMIN CREADO: {correo_admin}')   

# =========================================
# INICIO
# =========================================

if __name__ == '__main__':

    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True
    )
