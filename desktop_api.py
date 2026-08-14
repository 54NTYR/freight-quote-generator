import logging
import os
import shutil

logger = logging.getLogger(__name__)


def _save_dialog_type(webview_module):
    file_dialog = getattr(webview_module, "FileDialog", None)
    if file_dialog is not None and hasattr(file_dialog, "SAVE"):
        return file_dialog.SAVE
    return webview_module.SAVE_DIALOG


class DesktopApi:
    def save_pdf_file(self, token: str, suggested_filename: str) -> dict:
        import webview

        from paths import data_path

        filename = (suggested_filename or "Freight-Quote.pdf").strip()
        if not filename.lower().endswith(".pdf"):
            filename += ".pdf"

        if not token:
            return {"success": False, "error": "Missing quote file token."}

        if not webview.windows:
            return {"success": False, "error": "Desktop window is not available."}

        temp_path = data_path(f"quote-pdf-{token}.pdf")
        if not os.path.exists(temp_path):
            return {"success": False, "error": "Quote PDF expired. Please try again."}

        save_path = webview.windows[0].create_file_dialog(
            _save_dialog_type(webview),
            save_filename=filename,
            file_types=("PDF Documents (*.pdf)", "All files (*.*)"),
        )
        if not save_path:
            return {"success": False, "cancelled": True}

        destination = save_path if isinstance(save_path, str) else save_path[0]
        try:
            shutil.copyfile(temp_path, destination)
            logger.info("Saved quote PDF to %s", destination)
            return {"success": True, "path": destination}
        except OSError as exc:
            logger.warning("Failed to save quote PDF: %s", exc)
            return {"success": False, "error": str(exc)}
        finally:
            try:
                os.remove(temp_path)
            except OSError:
                logger.warning("Could not remove temporary quote PDF: %s", temp_path)
