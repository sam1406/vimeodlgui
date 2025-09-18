import flet
from flet import ElevatedButton, Text, TextField, Column, ProgressBar, AlertDialog, Row, MainAxisAlignment, FilePicker, FilePickerResultEvent
import subprocess
import requests
import threading
import re
import os

vimeo_dl_path = "vimeo-dl.exe"
ffmpeg_path = "ffmpeg.exe"


def extract_clip_id(json_url):
    try:
        response = requests.get(json_url, timeout=5)
        response.raise_for_status()
        json_data = response.json()
        clip_id = json_data.get("clip_id")
        if not clip_id:
            raise ValueError("clip_id no encontrado en el JSON")
        return clip_id
    except requests.RequestException as e:
        return f"Error al obtener el JSON: {e}"
    except ValueError as e:
        return str(e)


def run_vimeo_dl(url, progress_bar, result_text, storage_path):
    if url == "":
        result_text.value = "Error: La URL no puede estar vacía"
        result_text.update()
        return

    command = f'{vimeo_dl_path} -i "{url}"'
    result_text.value = "Descargando..."
    try:
        progress_bar.visible = True
        progress_bar.value = 0
        progress_bar.update()

        with subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) as process:
            for line in process.stdout:
                if "Downloading" in line:
                    progress_bar.value += 0.01
                    progress_bar.update()

        process.wait()
        if process.returncode == 0:
            result = "Descarga exitosa"
        else:
            raise subprocess.CalledProcessError(process.returncode, command)
    except subprocess.CalledProcessError as e:
        error_message = e.stderr if e.stderr else str(e)
        result = f"Error: {error_message}"
    result_text.value = result
    progress_bar.value = 1
    progress_bar.update()


def run_ffmpeg(clip_id, progress_bar, result_text, output_file, finish_dialog, page, storage_path):
    command = f'{ffmpeg_path} -i {clip_id}-video.mp4 -i {clip_id}-audio.mp4 -c copy "{os.path.join(storage_path, output_file)}"'
    try:
        with subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) as process:
            for line in process.stdout:
                print(line)
                if "some_progress_indicator" in line:
                    progress_bar.value += 0.01
                    progress_bar.update()

        process.wait()
        if process.returncode == 0:
            result_text.value = "Unión exitosa"
            os.remove(f"{clip_id}-video.mp4")
            os.remove(f"{clip_id}-audio.mp4")
        else:
            raise subprocess.CalledProcessError(process.returncode, command)
    except subprocess.CalledProcessError as e:
        error_message = e.stderr if e.stderr else str(e)
        result_text.value = f"Error: {error_message}"
    except FileNotFoundError as e:
        result_text.value = f"Error al eliminar archivos: {e}"
    progress_bar.value = 1
    progress_bar.update()
    finish_dialog.open = True
    page.update()


def is_valid_url(url):
    regex = re.compile(
        r'^(?:http|ftp)s?://'
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'
        r'localhost|'
        r'\d{1,3}\.\d{1,3}\.\d{1,3}|'
        r'\[?[A-F0-9]*:[A-F0-9:]+\]?)'
        r'(?::\d+)?'
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    return re.match(regex, url) is not None


def has_valid_extension(filename):
    return re.match(r'^.*\.(mp4|mkv|avi|mov|flv|wmv)$', filename, re.IGNORECASE) is not None


def main(page: flet.Page):
    page.title = "VimeoDL GUI"
    page.window_width = 600
    page.window_height = 400
    page.window_center()

    storage_path = ""

    def pick_folder(e: FilePickerResultEvent):
        nonlocal storage_path
        if e.path:
            storage_path = e.path
            storage_field.value = storage_path
            storage_field.update()
        else:
            storage_path = ""

    url_field = TextField(hint_text="Ingresa la URL de Vimeo",
                          on_change=lambda e: validate_url(e))
    output_field = TextField(hint_text="Salida (ej: video.mp4)")
    storage_field = TextField(
        hint_text="Ruta de almacenamiento (ej: C:\\Videos)", disabled=True)
    storage_picker = FilePicker(on_result=pick_folder)

    progress_bar = ProgressBar(width=300, height=3, visible=False)
    result_text = Text()
    download_button = ElevatedButton(
        "Descargar", on_click=lambda e: download_clicked(e))
    combine_button = ElevatedButton(
        "Combinar", on_click=lambda e: combine_clicked(e))
    combine_button.disabled = True
    storage_button = ElevatedButton(
        "Seleccionar carpeta", on_click=lambda _: storage_picker.get_directory_path())

    def validate_url(e):
        url = url_field.value
        if not url or not is_valid_url(url):
            result_text.value = "Error: Ingresa una URL válida"
            result_text.update()
            download_button.disabled = True
            download_button.update()
            combine_button.disabled = True
            combine_button.update()
            return

        clip_id = extract_clip_id(url)
        if "Error" in clip_id:
            result_text.value = clip_id
            result_text.update()
            download_button.disabled = True
            download_button.update()
            combine_button.disabled = True
            combine_button.update()
            return

        output_file = output_field.value.strip() + ".mp4"
        if output_file and (os.path.exists(output_file) or os.path.exists(clip_id + "-video.mp4")):
            result_text.value = f"Advertencia: El video ya existe"
            result_text.update()
            download_button.disabled = True
            download_button.update()
            combine_button.disabled = False
            combine_button.update()
        else:
            result_text.value = ""
            result_text.update()
            download_button.disabled = False
            download_button.update()
            combine_button.disabled = True
            combine_button.update()

    def download_clicked(e):
        url = url_field.value
        output_file = output_field.value.strip()
        if not output_file:
            result_text.value = "Error: El campo de salida no puede estar vacío"
            result_text.update()
            return

        progress_bar.value = 0
        progress_bar.visible = True
        progress_bar.update()

        def download_and_combine():
            result_text.value = "Iniciando descarga..."
            result_text.update()
            run_vimeo_dl(url, progress_bar, result_text, storage_path)

            if "Error" not in result_text.value:
                clip_id = extract_clip_id(url)
                if "Error" in clip_id:
                    result_text.value = clip_id
                else:
                    result_text.value = "Iniciando combinación..."
                    result_text.update()
                    run_ffmpeg(clip_id, progress_bar, result_text,
                               output_file + ".mp4", finish_dialog, page, storage_path)
                    download_button.disabled = True
                    download_button.update()
                    combine_button.disabled = False
                    combine_button.update()

        threading.Thread(target=download_and_combine).start()

    def combine_clicked(e):
        url = url_field.value
        output_file = output_field.value.strip()
        if not output_file:
            result_text.value = "Error: El campo de salida no puede estar vacío"
            result_text.update()
            return

        clip_id = extract_clip_id(url)
        if "Error" in clip_id:
            result_text.value = clip_id
            result_text.update()
            return

        progress_bar.value = 0
        progress_bar.visible = True
        progress_bar.update()

        def combine():
            result_text.value = "Iniciando combinación..."
            result_text.update()
            run_ffmpeg(clip_id, progress_bar, result_text,
                       output_file + ".mp4", finish_dialog, page, storage_path)

        threading.Thread(target=combine).start()

    def restart_app(e):
        url_field.value = ""
        output_field.value = ""
        storage_field.value = ""
        result_text.value = ""
        progress_bar.value = 0
        progress_bar.visible = False
        url_field.update()
        output_field.update()
        storage_field.update()
        result_text.update()
        progress_bar.update()
        finish_dialog.open = False
        page.update()

    def close_app(e):
        page.window_close()

    finish_dialog = AlertDialog(
        title=Text("Descarga y Conversión exitosa"),
        content=Text("¿Qué te gustaría hacer a continuación?"),
        actions=[
            ElevatedButton(text="Descargar otro video", on_click=restart_app),
            ElevatedButton(text="Salir", on_click=close_app),
        ],
        actions_alignment=MainAxisAlignment.END,
    )

    page.dialog = finish_dialog
    page.overlay.append(storage_picker)
    page.add(
        Column(
            [
                Text("Vimeo Downloader", style="headlineSmall"),
                url_field,
                output_field,
                storage_field,
                progress_bar,
                Row(
                    [download_button, combine_button, storage_button],
                    alignment=MainAxisAlignment.CENTER
                ),
                result_text,
            ],
            horizontal_alignment="center",
        )
    )


flet.app(target=main)
