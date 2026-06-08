# XENDA

Sistema web de captura y reporte de actividades de campo para proyectos de infraestructura.

---

## Descripción

XENDA es una Progressive Web App (PWA) desarrollada en Flask y PostgreSQL para el registro, seguimiento y reporte de actividades de campo. Permite capturar información desde dispositivos móviles —incluso sin conexión— y genera reportes quincenales en HTML con estructura institucional.

---

## Funcionalidades principales

- **Captura de campo**: Registro de actividades por tramo, entidad federativa, municipio y núcleo agrario, con geolocalización GPS.
- **Selects en cascada**: Catálogo jerárquico cargado desde Excel.
- **Sub-actividades**: Registro granular de actividades realizadas y programadas.
- **Reportes quincenales HTML**: Generación automática de reportes agrupados por dirección, tramo y tipo de propiedad.
- **Exportación a Excel**: Descarga de registros en `.xlsx` y respaldo automático mensual en la nube.
- **Panel de administración**: Gestión de usuarios y cierre remoto de sesiones activas.
- **Dashboard**: KPIs de mediciones, planos e infografías por tramo.
- **Mapa de registros**: Visualización de actividades con coordenadas GPS e identificación geoespacial.
- **PWA / Offline**: Service Worker con cola para captura sin conexión.

---

## Stack tecnológico

| Capa | Tecnología |
|---|---|
| Backend | Python 3, Flask |
| Base de datos | PostgreSQL + SQLAlchemy |
| Geoespacial | GeoPandas, Shapely |
| Autenticación | Sesiones Flask + tokens UUID |
| Almacenamiento en nube | Google Drive API v3 (service account) |
| Frontend | HTML5, CSS3, JavaScript (vanilla) |
| PWA | Service Worker, IndexedDB, Web App Manifest |

---

## Estructura de archivos

```
├── app.py
├── catalogo_1.xlsx
├── geodata/
│   ├── estados/
│   └── nucleos_agrarios/
├── static/
├── templates/
└── manifest.json
```

---

## Modelos de base de datos

- **`Usuario`**: Accesos autorizados.
- **`SesionActiva`**: Tokens de sesión activos.
- **`Registro`**: Actividad de campo capturada.
- **`SubActividad`**: Detalle por núcleo dentro de un registro.
- **`RegistroEliminado`**: Auditoría de eliminaciones.
- **`Exportacion`**: Control de exportaciones mensuales.

---

## Despliegue

1. Configurar las variables de entorno.
2. Incluir los archivos de geodata y el catálogo en el repositorio o en un volumen persistente.
3. El service worker requiere HTTPS.
