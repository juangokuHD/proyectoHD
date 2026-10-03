"""Interfaz Streamlit para SmartPark - Sistema inteligente de estacionamiento."""

from __future__ import annotations

import base64
import hashlib
from io import BytesIO
import uuid
from pathlib import Path
from typing import Any

import streamlit as st
import streamlit.components.v1 as components
from PIL import Image, UnidentifiedImageError

from vision.camera_store import delete_camera, load_cameras, save_camera
from vision.pipeline import analyze_image, get_model


# ============================================================
# CONFIGURACIÓN DE LA APLICACIÓN
# ============================================================

st.set_page_config(
    page_title="SmartPark · Estacionamiento inteligente",
    page_icon="🅿️",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# MODELO YOLO
# ============================================================

@st.cache_resource
def cached_yolo_model() -> Any:
    """
    Mantiene el modelo YOLO cargado en memoria para evitar
    cargarlo nuevamente en cada actualización de Streamlit.
    """
    return get_model()


# ============================================================
# EDITOR DE ESPACIOS DE ESTACIONAMIENTO
# ============================================================

@st.cache_resource
def parking_editor_component() -> Any:
    """
    Registra el componente visual utilizado para seleccionar
    las cuatro esquinas de cada espacio de estacionamiento.
    """

    component_path = (
        Path(__file__).parent
        / "components"
        / "parking_editor"
    )

    return components.declare_component(
        "smartpark_parking_editor",
        path=str(component_path),
    )


# ============================================================
# FUNCIONES AUXILIARES
# ============================================================

def image_dimensions(image_bytes: bytes) -> tuple[int, int]:
    """
    Obtiene automáticamente el ancho y alto de una imagen.
    El usuario no necesita introducir estas medidas.
    """

    with Image.open(BytesIO(image_bytes)) as image:
        image.verify()

    with Image.open(BytesIO(image_bytes)) as image:
        return image.size


def component_image_editor(
    image_data_url: str,
    width: int,
    height: int,
    spaces: list[dict[str, Any]],
    editable: bool,
    key: str,
    reference_width: int | None = None,
    reference_height: int | None = None,
) -> list[dict[str, float]]:
    """
    Muestra el editor de espacios de estacionamiento.

    El editor permite seleccionar cuatro puntos para definir
    un espacio de estacionamiento.
    """

    value = parking_editor_component()(
        image=image_data_url,
        width=width,
        height=height,
        referenceWidth=reference_width or width,
        referenceHeight=reference_height or height,
        spaces=spaces,
        editable=editable,
        key=key,
        default={"points": []},
    )

    if isinstance(value, dict) and isinstance(value.get("points"), list):
        return value["points"]

    return []


# ============================================================
# ESTILOS
# ============================================================

def render_styles() -> None:
    """
    Estilos visuales de SmartPark.
    """

    st.markdown(
        """
        <style>

        :root {
            color-scheme: dark;
        }

        [data-testid="stAppViewContainer"] {
            background: #111820;
        }

        [data-testid="stHeader"] {
            background: #111820;
        }

        [data-testid="stSidebar"] {
            background: #17212a;
            border-right: 1px solid #273541;
        }

        [data-testid="stMetric"] {
            background: #19242d;
            border: 1px solid #2b3945;
            border-radius: 12px;
            padding: 14px 16px;
        }

        [data-testid="stMetricLabel"] {
            color: #9aabb8;
        }

        [data-testid="stMetricValue"] {
            color: #eaf2f6;
        }

        .sp-kicker {
            color: #68d3c2;
            text-transform: uppercase;
            letter-spacing: .14em;
            font-size: .75rem;
            font-weight: 700;
        }

        .sp-note {
            color: #aab8c2;
            font-size: .9rem;
        }

        .sp-success {
            padding: 12px;
            border-radius: 10px;
            background: #17352f;
            border: 1px solid #2d685c;
            margin-bottom: 15px;
        }

        .sp-info {
            padding: 12px;
            border-radius: 10px;
            background: #192c38;
            border: 1px solid #315266;
            margin-bottom: 15px;
        }

        div.stButton > button[kind="primary"] {
            background: #18a794;
            border-color: #18a794;
            color: #061b19;
        }

        </style>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# APLICACIÓN PRINCIPAL
# ============================================================

def main() -> None:

    render_styles()

    # --------------------------------------------------------
    # ENCABEZADO
    # --------------------------------------------------------

    st.markdown(
        '<div class="sp-kicker">Sistema inteligente de estacionamiento</div>',
        unsafe_allow_html=True,
    )

    st.title("🅿️ SmartPark")

    st.caption(
        "Detección inteligente de espacios de estacionamiento mediante visión por computadora"
    )

    st.markdown(
        """
        **SmartPark** analiza imágenes de estacionamientos mediante
        visión por computadora e inteligencia artificial.

        El sistema utiliza un modelo **YOLO** para detectar vehículos
        y relacionarlos con los espacios de estacionamiento previamente
        definidos en la imagen.
        """
    )

    # --------------------------------------------------------
    # CARGAR CÁMARAS
    # --------------------------------------------------------

    cameras = load_cameras()

    pending_camera_selection = st.session_state.pop(
        "pending_camera_selection",
        None,
    )

    if pending_camera_selection:
        st.session_state["selected_camera_id"] = pending_camera_selection

    # ========================================================
    # BARRA LATERAL
    # ========================================================

    with st.sidebar:

        st.header("⚙️ Configuración")

        st.markdown(
            """
            <p class="sp-note">
            Primero selecciona una imagen del estacionamiento.
            Después podrás definir sus espacios.
            </p>
            """,
            unsafe_allow_html=True,
        )

        # ----------------------------------------------------
        # SUBIR IMAGEN
        # ----------------------------------------------------

        uploaded_file = st.file_uploader(
            "📷 Subir imagen del estacionamiento",
            type=["png", "jpg", "jpeg"],
            accept_multiple_files=False,
            help=(
                "Selecciona una fotografía del estacionamiento "
                "que deseas analizar."
            ),
        )

        # ----------------------------------------------------
        # SELECCIÓN DE CÁMARA
        # ----------------------------------------------------

        camera_ids = ["new-camera"] + [
            camera["id"]
            for camera in cameras
        ]

        camera_labels = {
            "new-camera": "➕ Configurar nueva vista"
        }

        camera_labels.update(
            {
                camera["id"]: camera["name"]
                for camera in cameras
            }
        )

        selected_id = st.selectbox(
            "🎥 Vista / cámara",
            camera_ids,
            format_func=lambda camera_id:
                camera_labels.get(camera_id, camera_id),
            key="selected_camera_id",
        )

        # ----------------------------------------------------
        # ELIMINAR CONFIGURACIÓN
        # ----------------------------------------------------

        if selected_id != "new-camera":

            selected_camera = next(
                (
                    camera
                    for camera in cameras
                    if camera["id"] == selected_id
                ),
                None,
            )

            if selected_camera and st.button(
                "🗑️ Eliminar configuración",
                key="delete_camera_layout",
            ):

                delete_camera(selected_id)

                st.session_state[
                    "pending_camera_selection"
                ] = "new-camera"

                st.session_state.pop(
                    "analysis",
                    None,
                )

                st.session_state.pop(
                    "analysis_key",
                    None,
                )

                st.rerun()

        # ----------------------------------------------------
        # CONFIANZA YOLO
        # ----------------------------------------------------

        confidence = st.slider(
            "🎯 Confianza de detección",
            min_value=0.05,
            max_value=0.95,
            value=0.30,
            step=0.05,
            help=(
                "Valores bajos detectan más objetos pero pueden "
                "generar detecciones incorrectas. Valores altos "
                "requieren mayor seguridad del modelo."
            ),
        )

        st.divider()

        st.caption(
            "SmartPark · Proyecto de visión por computadora"
        )

    # ========================================================
    # SI NO HAY IMAGEN
    # ========================================================

    if uploaded_file is None:

        st.info(
            "📷 Sube una imagen de un estacionamiento para comenzar."
        )

        st.markdown(
            """
            ### ¿Cómo funciona?

            **1. Sube una imagen**

            Puedes utilizar una fotografía de un estacionamiento.

            **2. Marca los espacios**

            Haz clic en las cuatro esquinas de cada cajón.

            **3. Guarda la vista**

            SmartPark guarda automáticamente la configuración.

            **4. Analiza**

            YOLO detectará los vehículos y determinará qué espacios
            están ocupados.

            **5. Consulta los resultados**

            El sistema mostrará:

            - 🟢 Espacios disponibles
            - 🔴 Espacios ocupados
            - 🚗 Vehículos detectados
            - 📊 Porcentaje de ocupación
            """,
        )

        st.markdown(
            '<p class="sp-note">Consejo: utiliza una imagen clara y, '
            "preferentemente, tomada desde una posición elevada.</p>",
            unsafe_allow_html=True,
        )

        return

    # ========================================================
    # PROCESAR IMAGEN
    # ========================================================

    image_bytes = uploaded_file.getvalue()

    try:

        width, height = image_dimensions(
            image_bytes
        )

    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
    ):

        st.error(
            "❌ No fue posible abrir la imagen. "
            "Sube una imagen PNG o JPEG válida."
        )

        return

    mime_type = uploaded_file.type or "image/jpeg"

    image_data_url = (
        f"data:{mime_type};base64,"
        f"{base64.b64encode(image_bytes).decode('ascii')}"
    )

    # ========================================================
    # NUEVA CÁMARA / NUEVA VISTA
    # ========================================================

    if selected_id == "new-camera":

        st.header("📐 Configurar espacios")

        st.markdown(
            """
            <div class="sp-info">

            <b>Instrucciones:</b>

            Haz clic en las cuatro esquinas de cada espacio
            de estacionamiento.

            El sistema obtiene automáticamente las dimensiones
            de la imagen. No necesitas introducirlas manualmente.

            </div>
            """,
            unsafe_allow_html=True,
        )

        # ----------------------------------------------------
        # NOMBRE
        # ----------------------------------------------------

        camera_name = st.text_input(
            "Nombre de la vista",
            placeholder="Ejemplo: Estacionamiento principal",
            key="draft_camera_name",
        )

        # ----------------------------------------------------
        # INFORMACIÓN DE IMAGEN
        # ----------------------------------------------------

        st.caption(
            f"📷 Imagen detectada automáticamente: "
            f"**{width:,} × {height:,} píxeles**"
        )

        st.caption(
            "Selecciona las cuatro esquinas de cada espacio "
            "siguiendo el contorno del cajón."
        )

        # ----------------------------------------------------
        # ESPACIOS TEMPORALES
        # ----------------------------------------------------

        draft_spaces: list[
            dict[str, Any]
        ] = st.session_state.setdefault(
            "draft_spaces",
            [],
        )

        editor_key = (
            "new-camera-editor-"
            f"{st.session_state.get('editor_generation', 0)}"
        )

        points = component_image_editor(
            image_data_url=image_data_url,
            width=width,
            height=height,
            spaces=draft_spaces,
            editable=True,
            key=editor_key,
        )

        # ----------------------------------------------------
        # CONTADOR DE PUNTOS
        # ----------------------------------------------------

        if points:

            st.caption(
                f"📍 {len(points)} de 4 puntos seleccionados."
            )

        # ----------------------------------------------------
        # BOTONES
        # ----------------------------------------------------

        add_column, clear_column = st.columns(
            [1, 1]
        )

        with add_column:

            if st.button(
                "➕ Agregar espacio",
                type="primary",
                disabled=len(points) != 4,
                key="add_parking_space",
            ):

                space_number = (
                    len(draft_spaces) + 1
                )

                draft_spaces.append(
                    {
                        "id": f"P-{space_number:02d}",
                        "polygon": points,
                    }
                )

                st.session_state[
                    "editor_generation"
                ] = (
                    st.session_state.get(
                        "editor_generation",
                        0,
                    )
                    + 1
                )

                st.rerun()

        with clear_column:

            if st.button(
                "🔄 Reiniciar puntos",
                key="reset_camera_draft",
            ):

                st.session_state[
                    "draft_spaces"
                ] = []

                st.session_state[
                    "editor_generation"
                ] = (
                    st.session_state.get(
                        "editor_generation",
                        0,
                    )
                    + 1
                )

                st.session_state.pop(
                    "analysis",
                    None,
                )

                st.rerun()

        # ----------------------------------------------------
        # ESPACIOS MAPEADOS
        # ----------------------------------------------------

        if draft_spaces:

            st.success(
                f"Espacios configurados: "
                f"{len(draft_spaces)}"
            )

            st.write(
                "Espacios:",
                ", ".join(
                    space["id"]
                    for space in draft_spaces
                ),
            )

        # ----------------------------------------------------
        # GUARDAR CÁMARA
        # ----------------------------------------------------

        if st.button(
            "💾 Guardar configuración",
            type="primary",
            disabled=(
                not camera_name.strip()
                or not draft_spaces
            ),
            key="save_camera_layout",
        ):

            camera = {
                "id": str(uuid.uuid4()),

                "name": camera_name.strip(),

                # Las dimensiones se obtienen
                # automáticamente de la imagen.
                "referenceWidth": width,

                "referenceHeight": height,

                "spaces": draft_spaces.copy(),
            }

            save_camera(camera)

            st.session_state[
                "pending_camera_selection"
            ] = camera["id"]

            st.session_state[
                "draft_spaces"
            ] = []

            st.session_state[
                "editor_generation"
            ] = (
                st.session_state.get(
                    "editor_generation",
                    0,
                )
                + 1
            )

            st.success(
                f"✅ Se guardó la configuración "
                f"'{camera['name']}' con "
                f"{len(camera['spaces'])} espacios."
            )

            st.rerun()

        st.stop()

    # ========================================================
    # CARGAR CÁMARA EXISTENTE
    # ========================================================

    camera = next(
        (
            entry
            for entry in cameras
            if entry["id"] == selected_id
        ),
        None,
    )

    if camera is None:

        st.warning(
            "⚠️ La configuración de esta cámara "
            "ya no está disponible."
        )

        return

    # ========================================================
    # INFORMACIÓN DE LA CÁMARA
    # ========================================================

    st.header(
        f"🎥 {camera['name']}"
    )

    st.caption(
        f"Configuración original: "
        f"{camera['referenceWidth']:,} × "
        f"{camera['referenceHeight']:,} px"
    )

    st.info(
        "Los espacios se ajustan automáticamente a la "
        "resolución de la imagen. Si utilizas otra vista "
        "o una cámara con un ángulo diferente, crea una "
        "nueva configuración."
    )

    # ========================================================
    # MOSTRAR ESPACIOS
    # ========================================================

    component_image_editor(
        image_data_url=image_data_url,
        width=width,
        height=height,
        spaces=camera["spaces"],
        editable=False,
        key=(
            f"saved-camera-"
            f"{camera['id']}-"
            f"{width}x{height}"
        ),
        reference_width=camera["referenceWidth"],
        reference_height=camera["referenceHeight"],
    )

    # ========================================================
    # VALIDAR ESPACIOS
    # ========================================================

    if not camera["spaces"]:

        st.info(
            "Esta configuración no tiene espacios "
            "de estacionamiento. Crea una nueva "
            "configuración para agregarlos."
        )

        return

    # ========================================================
    # IDENTIFICADOR DEL ANÁLISIS
    # ========================================================

    analysis_key = (
        f"{selected_id}:"
        f"{hashlib.sha256(image_bytes).hexdigest()}:"
        f"{confidence:.2f}"
    )

    # ========================================================
    # BOTÓN ANALIZAR
    # ========================================================

    if st.button(
        "🔍 Analizar estacionamiento",
        type="primary",
        key="analyze_parking_lot",
    ):

        try:

            with st.spinner(
                "🤖 Analizando imagen con inteligencia artificial..."
            ):

                # Cargar YOLO
                cached_yolo_model()

                # Analizar imagen
                result = analyze_image(
                    base64.b64encode(
                        image_bytes
                    ).decode("ascii"),
                    camera,
                    confidence,
                )

            st.session_state[
                "analysis"
            ] = result

            st.session_state[
                "analysis_key"
            ] = analysis_key

            st.success(
                "✅ Análisis completado correctamente."
            )

        except Exception as error:

            st.error(
                f"❌ Error durante el análisis: {error}"
            )

    # ========================================================
    # OBTENER RESULTADO
    # ========================================================

    result = (
        st.session_state.get("analysis")
        if st.session_state.get(
            "analysis_key"
        ) == analysis_key
        else None
    )

    if not result:

        return

    # ========================================================
    # RESULTADOS
    # ========================================================

    st.divider()

    st.header("📊 Resultados del análisis")

    # --------------------------------------------------------
    # MÉTRICAS
    # --------------------------------------------------------

    columns = st.columns(5)

    columns[0].metric(
        "🅿️ Espacios totales",
        result["totalSpaces"],
    )

    columns[1].metric(
        "🟢 Disponibles",
        result["availableSpaces"],
    )

    columns[2].metric(
        "🔴 Ocupados",
        result["occupiedSpaces"],
    )

    columns[3].metric(
        "📊 Ocupación",
        f'{result["occupancyPercent"]:.1f}%',
    )

    columns[4].metric(
        "🚗 Vehículos",
        len(result["vehicles"]),
    )

    # --------------------------------------------------------
    # NIVEL DE OCUPACIÓN
    # --------------------------------------------------------

    st.markdown(
        f'### Nivel de ocupación: `{result["occupancyLevel"]}`'
    )

    # ========================================================
    # SIN VEHÍCULOS
    # ========================================================

    if not result["vehicles"]:

        st.warning(
            "⚠️ No se detectaron vehículos en la imagen. "
            "Las áreas de estacionamiento continúan "
            "mostrándose en la imagen."
        )

    # ========================================================
    # IMAGEN RESULTADO
    # ========================================================

    annotated_bytes = base64.b64decode(
        result["imageBase64"]
    )

    st.subheader(
        "🖼️ Imagen analizada"
    )

    st.image(
        annotated_bytes,
        caption=(
            "Resultado del análisis de SmartPark"
        ),
        use_container_width=True,
    )

    # ========================================================
    # DESCARGAR RESULTADO
    # ========================================================

    st.download_button(
        "⬇️ Descargar imagen analizada",
        data=annotated_bytes,
        file_name="smartpark-analysis.png",
        mime="image/png",
        key="download_analysis",
    )

    # ========================================================
    # TABLA DE VEHÍCULOS
    # ========================================================

    if result["vehicles"]:

        st.subheader(
            "🚗 Vehículos detectados"
        )

        vehicle_data = []

        for vehicle in result["vehicles"]:

            occupied_spaces = (
                ", ".join(
                    vehicle[
                        "occupiedSpaceIds"
                    ]
                )
                if vehicle[
                    "occupiedSpaceIds"
                ]
                else "Ninguno"
            )

            vehicle_data.append(
                {
                    "Vehículo": vehicle[
                        "label"
                    ].title(),

                    "Confianza": (
                        f'{vehicle["confidence"]:.1%}'
                    ),

                    "Espacio asignado": (
                        occupied_spaces
                    ),
                }
            )

        st.dataframe(
            vehicle_data,
            hide_index=True,
            use_container_width=True,
        )

    # ========================================================
    # RESUMEN
    # ========================================================

    st.divider()

    st.subheader(
        "📝 Resumen"
    )

    total = result["totalSpaces"]
    available = result["availableSpaces"]
    occupied = result["occupiedSpaces"]

    st.markdown(
        f"""
        SmartPark analizó **{total} espacios** de estacionamiento.

        - 🟢 **{available} espacios disponibles**
        - 🔴 **{occupied} espacios ocupados**
        - 🚗 **{len(result["vehicles"])} vehículos detectados**
        - 📊 **{result["occupancyPercent"]:.1f}% de ocupación**

        El estado de cada espacio se determina mediante la
        detección de vehículos realizada por el modelo YOLO.
        """
    )


# ============================================================
# EJECUCIÓN
# ============================================================

if __name__ == "__main__":
    main()