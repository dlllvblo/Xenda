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
import requests
import geopandas as gpd
from shapely.geometry import Point
from apscheduler.schedulers.background import BackgroundScheduler  
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

    latitud = db.Column(db.Float)

    longitud = db.Column(db.Float)

    precision_gps = db.Column(db.Float)

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
    # GENERAR REPORTE HTML
    # =========================================

    def generar_reporte_html(df, mes_label):

        import json

        total_registros = len(df)
        total_infografias = int(df['NUM_INFOGRAFIAS'].sum())
        infografias_generadas = int(df['INFOGRAFIAS_GENERADAS'].sum())
        infografias_validadas = int(df['INFOGRAFIAS_VALIDADAS'].sum())
        total_planos = int(df['PLANOS_GENERADOS'].sum())
        total_mediciones = int(df['MEDICIONES_AGROFORESTALES'].sum() + df['MEDICIONES_BDTS'].sum())

        pct_validadas = round(
            (infografias_validadas / infografias_generadas * 100)
            if infografias_generadas > 0 else 0
        )

        por_tramo = df.groupby('TRAMO').size().to_dict()
        tramo_labels = list(por_tramo.keys())
        tramo_values = list(por_tramo.values())

        por_actividad = df.groupby('ACTIVIDAD').size().to_dict()
        act_labels = list(por_actividad.keys())
        act_values = list(por_actividad.values())

        avance_tramo = df.groupby('TRAMO').agg(
            generadas=('INFOGRAFIAS_GENERADAS', 'sum'),
            validadas=('INFOGRAFIAS_VALIDADAS', 'sum')
        ).reset_index()

        color_map = {
            'TQI':   '#7F77DD',
            'TAP':   '#1D9E75',
            'TIGDL': '#BA7517',
            'TIGDS': '#D85A30',
            'TIGD':  '#378ADD',
        }
        default_colors = ['#888780', '#D4537E', '#639922', '#E24B4A']

        def color_tramo(tramo, idx=0):
            return color_map.get(tramo, default_colors[idx % len(default_colors)])

        filas_registros = ''
        for _, r in df.iterrows():

            obs = (
                f'<div style="margin-top:8px;background:#FFF3EE;border-left:3px solid #D85A30;'
                f'border-radius:4px;padding:6px 10px;font-size:12px;color:#712B13;">'
                f'&#9888; {r["OBSERVACIONES"]}</div>'
            ) if pd.notna(r.get('OBSERVACIONES')) and str(r.get('OBSERVACIONES', '')).strip() else ''

            estatus = r.get('ESTATUS_INFOGRAFIAS', '')
            badge_est = ''
            if pd.notna(estatus) and str(estatus).strip():
                badge_est = (
                    f'<span style="background:#FAECE7;color:#712B13;font-size:11px;'
                    f'padding:2px 8px;border-radius:12px;">{estatus}</span>'
                )

            c = color_tramo(r['TRAMO'])
            filas_registros += f'''
            <div style="background:#fff;border:0.5px solid #e0e0e0;border-radius:12px;padding:14px 16px;margin-bottom:10px;">
              <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:8px;">
                <div>
                  <span style="background:{c}22;color:{c};font-size:11px;font-weight:500;padding:3px 10px;border-radius:12px;margin-right:6px;">{r['TRAMO']}</span>
                  <span style="font-size:14px;font-weight:500;">{r['NUCLEO']}</span>
                </div>
                <span style="font-size:12px;color:#888;">{r['FECHA']}</span>
              </div>
              <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:6px;">
                <span style="background:#f0f0f0;color:#555;font-size:11px;padding:2px 8px;border-radius:12px;">{r['ACTIVIDAD']} &middot; {r['MODALIDAD']}</span>
                {badge_est}
              </div>
              <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:6px;font-size:12px;">
                <div><span style="color:#999;display:block;">Entidad</span><b>{r['ENTIDAD']}</b></div>
                <div><span style="color:#999;display:block;">Municipio</span><b>{r['MUNICIPIO']}</b></div>
                <div><span style="color:#999;display:block;">Frente</span><b>{r['FRENTE']}</b></div>
                <div><span style="color:#999;display:block;">Infograf&iacute;as</span><b>{int(r['NUM_INFOGRAFIAS'])}</b></div>
                <div><span style="color:#999;display:block;">Generadas</span><b>{int(r['INFOGRAFIAS_GENERADAS'])}</b></div>
                <div><span style="color:#999;display:block;">Validadas</span><b>{int(r['INFOGRAFIAS_VALIDADAS'])}</b></div>
              </div>
              {obs}
            </div>'''

        barras_tramo = ''
        for _, row in avance_tramo.iterrows():
            pct = round(
                (row['validadas'] / row['generadas'] * 100)
                if row['generadas'] > 0 else 0
            )
            c = color_tramo(row['TRAMO'])
            barras_tramo += f'''
            <div style="display:flex;align-items:center;gap:10px;margin-bottom:10px;">
              <span style="min-width:80px;font-size:13px;background:{c}22;color:{c};padding:3px 10px;border-radius:12px;">{row['TRAMO']}</span>
              <div style="flex:1;height:8px;background:#f0f0f0;border-radius:4px;overflow:hidden;">
                <div style="width:{pct}%;height:100%;background:{c};border-radius:4px;"></div>
              </div>
              <span style="font-size:12px;color:#888;min-width:36px;text-align:right;">{pct}%</span>
            </div>'''

        tramo_colors = [color_tramo(t, i) for i, t in enumerate(tramo_labels)]
        act_colors = ['#534AB7', '#1D9E75', '#BA7517', '#D85A30', '#378ADD']

        html = f'''<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Reporte Xenda &middot; {mes_label}</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js"></script>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #f7f7f5; color: #1a1a1a; padding: 2rem; max-width: 860px; margin: 0 auto; }}
  .header {{ border-bottom: 1px solid #e0e0e0; padding-bottom: 1rem; margin-bottom: 1.5rem; }}
  .metrics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 10px; margin-bottom: 1.5rem; }}
  .metric {{ background: #f0f0ee; border-radius: 8px; padding: 14px 16px; }}
  .metric-label {{ font-size: 12px; color: #888; margin-bottom: 6px; }}
  .metric-value {{ font-size: 26px; font-weight: 500; }}
  .metric-sub {{ font-size: 11px; color: #aaa; margin-top: 4px; }}
  .grid2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 1.5rem; }}
  .card {{ background: #fff; border: 0.5px solid #e0e0e0; border-radius: 12px; padding: 1rem 1.25rem; }}
  .section-title {{ font-size: 12px; font-weight: 500; color: #888; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 12px; }}
  @media (max-width: 560px) {{ .grid2 {{ grid-template-columns: 1fr; }} }}
</style>
</head>
<body>

<div class="header">
  <p style="font-size:12px;color:#888;margin-bottom:4px;">Xenda &middot; Registros de campo</p>
  <h1 style="font-size:22px;font-weight:500;">Resumen operativo</h1>
  <p style="font-size:13px;color:#666;margin-top:4px;">{mes_label} &middot; {total_registros} registros</p>
</div>

<div class="metrics">
  <div class="metric">
    <div class="metric-label">Registros</div>
    <div class="metric-value">{total_registros}</div>
  </div>
  <div class="metric">
    <div class="metric-label">Infograf&iacute;as</div>
    <div class="metric-value">{total_infografias}</div>
    <div class="metric-sub">{infografias_validadas} validadas</div>
  </div>
  <div class="metric">
    <div class="metric-label">% Validaci&oacute;n</div>
    <div class="metric-value">{pct_validadas}%</div>
    <div class="metric-sub">de generadas</div>
  </div>
  <div class="metric">
    <div class="metric-label">Planos</div>
    <div class="metric-value">{total_planos}</div>
  </div>
  <div class="metric">
    <div class="metric-label">Mediciones</div>
    <div class="metric-value">{total_mediciones}</div>
  </div>
</div>

<div class="grid2">
  <div class="card">
    <div class="section-title">Por tramo</div>
    <div style="position:relative;height:180px;">
      <canvas id="chartTramo"></canvas>
    </div>
  </div>
  <div class="card">
    <div class="section-title">Por actividad</div>
    <div style="position:relative;height:180px;">
      <canvas id="chartAct"></canvas>
    </div>
  </div>
</div>

<div class="card" style="margin-bottom:1.5rem;">
  <div class="section-title">Avance infograf&iacute;as por tramo</div>
  <div style="margin-top:4px;">
    {barras_tramo}
  </div>
</div>

<div class="section-title" style="margin-bottom:12px;">Registros de campo</div>
{filas_registros}

<p style="font-size:12px;color:#aaa;text-align:center;margin-top:1.5rem;padding-bottom:1rem;">
  Generado autom&aacute;ticamente &middot; Xenda
</p>

<script>
new Chart(document.getElementById('chartTramo'), {{
  type: 'doughnut',
  data: {{
    labels: {json.dumps(tramo_labels)},
    datasets: [{{ data: {json.dumps(tramo_values)}, backgroundColor: {json.dumps(tramo_colors)}, borderWidth: 0 }}]
  }},
  options: {{ responsive: true, maintainAspectRatio: false, cutout: '60%',
    plugins: {{ legend: {{ position: 'bottom', labels: {{ font: {{ size: 12 }}, padding: 10 }} }} }} }}
}});
new Chart(document.getElementById('chartAct'), {{
  type: 'bar',
  data: {{
    labels: {json.dumps(act_labels)},
    datasets: [{{ data: {json.dumps(act_values)}, backgroundColor: {json.dumps(act_colors[:len(act_labels)])}, borderWidth: 0, borderRadius: 4 }}]
  }},
  options: {{ responsive: true, maintainAspectRatio: false, indexAxis: 'y',
    plugins: {{ legend: {{ display: false }} }},
    scales: {{ x: {{ ticks: {{ stepSize: 1 }} }}, y: {{ grid: {{ display: false }} }} }} }}
}});
</script>
</body>
</html>'''

        return html

    # =========================================
    # SUBIR REPORTE HTML A DRIVE
    # =========================================

    mes_label = ahora.strftime('%B %Y').capitalize()
    html_content = generar_reporte_html(df, mes_label)

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

@app.route(
    '/reiniciar_registros',
    methods=['GET', 'POST']
)
def reiniciar_registros():
    if session.get('usuario') != ADMIN_CORREO:
        return 'No autorizado', 403
    if request.method == 'POST':
        Registro.query.delete()
        RegistroEliminado.query.delete()
        Exportacion.query.delete()
        db.session.commit()
        flash('Registros reiniciados correctamente')
        return redirect('/admin')
    return '''
        <h2>
            ¿Seguro que deseas reiniciar TODOS los registros?
        </h2>

        <p>
            Esta acción no se puede deshacer.
        </p>

        <form method="POST">

            <button type="submit">
                Sí, reiniciar registros
            </button>

            <a href="/admin">
                Cancelar
            </a>

        </form>
    '''

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

    frente = request.form.get('frente')

    frente = int(frente) if frente else None

    if request.method == 'POST':

        if (
            not request.form.get('latitud')
            or
            not request.form.get('longitud')
        ):

            flash(
                'Debe permitir acceso a ubicación'
            )

            return redirect('/')

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

            observaciones=request.form[
                'observaciones'
                ].upper() 
        )

        db.session.add(nuevo)

        db.session.commit()

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

    if session.get('usuario') != ADMIN_CORREO:

        return 'No autorizado', 403

    registros = Registro.query.order_by(
        Registro.fecha.desc()
    ).all()

    datos = []

    for r in registros:

        datos.append({

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

            'OBSERVACIONES': r.observaciones,

            'USUARIO': r.usuario
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
    ]

    tramos_values = [
        t[1]
        for t in tramos_data
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

        admin_correo=ADMIN_CORREO
    )

# =========================================
# MAPA GENERAL
# =========================================

@app.route('/mapa_registros')

def mapa_registros():

    if session.get('usuario') != ADMIN_CORREO:

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

## =========================================
## WHATSAPP AUTOMATICO
## =========================================
#
#def enviar_whatsapp(mensaje):
#
#    telefono = '521XXXXXXXXXX'
#
#    apikey = os.getenv(
#        'CALLMEBOT_APIKEY'
#    )
#
#    url = (
#
#        'https://api.callmebot.com/whatsapp.php'
#
#        f'?phone={telefono}'
#
#        f'&text={mensaje}'
#
#        f'&apikey={apikey}'
#    )
#
#    requests.get(url)
#
## =========================================
## AVISOS AUTOMATICOS
## =========================================
#
#def aviso_apertura():
#
#    mensaje = '''
#
#XENDA - AVISO IMPORTANTE
#
#El periodo de captura estará disponible
#a partir de las 00:00 hrs de mañana.
#
#Favor de preparar y validar actividades pendientes.
#
#'''
#
#    enviar_whatsapp(mensaje)
#
#def aviso_cierre():
#
#    mensaje = '''
#
#XENDA - AVISO IMPORTANTE
#
#El periodo de captura finalizará hoy
#a las 23:59 hrs.
#
#Favor de concluir y validar registros pendientes.
#
#'''
#
#    enviar_whatsapp(mensaje)
#
## =========================================
## SCHEDULER
## =========================================
#
#scheduler = BackgroundScheduler()
#
## Apertura
#scheduler.add_job(
#
#    aviso_apertura,
#
#    'cron',
#
#    day='9,24',
#
#    hour=18,
#
#    minute=0
#)
#
## Cierre
#scheduler.add_job(
#
#    aviso_cierre,
#
#    'cron',
#
#    day='14,29',
#
#    hour=12,
#
#    minute=0
#)
#
#scheduler.start()

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
