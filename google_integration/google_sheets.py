"""
Универсальный модуль для работы с Google Sheets через Google API v4.
Подключение через сервисный аккаунт (JSON-ключ).
Можно переиспользовать в любом проекте: импортировать класс GoogleSheets и вызывать методы.
"""

from __future__ import annotations

import os
from typing import Any, List, Optional, Union

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]


class GoogleSheets:
    """CRUD-клиент для Google Sheets."""

    def __init__(self, credentials_path: str, spreadsheet_id: str) -> None:
        """
        Args:
            credentials_path: путь к JSON-ключу сервисного аккаунта
            spreadsheet_id: ID таблицы (из URL после /d/)
        """
        creds = Credentials.from_service_account_file(credentials_path, scopes=SCOPES)
        self.service = build("sheets", "v4", credentials=creds)
        self.drive_service = build("drive", "v3", credentials=creds)
        self.spreadsheet_id = spreadsheet_id

    # ------------------------------------------------------------------
    # Метаданные
    # ------------------------------------------------------------------

    def get_sheet_names(self) -> List[str]:
        """Возвращает список названий всех листов."""
        meta = self.service.spreadsheets().get(spreadsheetId=self.spreadsheet_id).execute()
        return [s["properties"]["title"] for s in meta.get("sheets", [])]

    def get_sheet_id_by_name(self, sheet_name: str) -> Optional[int]:
        """Возвращает числовой sheetId по названию листа (нужен для batchUpdate)."""
        meta = self.service.spreadsheets().get(spreadsheetId=self.spreadsheet_id).execute()
        for s in meta.get("sheets", []):
            if s["properties"]["title"] == sheet_name:
                return s["properties"]["sheetId"]
        return None

    def add_sheet(self, title: str) -> int:
        """Создаёт новый лист и возвращает его sheetId."""
        body = {"requests": [{"addSheet": {"properties": {"title": title}}}]}
        resp = self.service.spreadsheets().batchUpdate(
            spreadsheetId=self.spreadsheet_id, body=body
        ).execute()
        return resp["replies"][0]["addSheet"]["properties"]["sheetId"]

    def delete_sheet(self, sheet_name: str) -> None:
        """Удаляет лист по названию (если существует)."""
        sheet_id = self.get_sheet_id_by_name(sheet_name)
        if sheet_id is None:
            return
        body = {"requests": [{"deleteSheet": {"sheetId": sheet_id}}]}
        self.service.spreadsheets().batchUpdate(
            spreadsheetId=self.spreadsheet_id, body=body
        ).execute()

    # ------------------------------------------------------------------
    # Чтение
    # ------------------------------------------------------------------

    def read_range(self, range_name: str) -> List[List[Any]]:
        """Читает диапазон. Возвращает список строк (каждая строка = список ячеек)."""
        try:
            result = (
                self.service.spreadsheets()
                .values()
                .get(spreadsheetId=self.spreadsheet_id, range=range_name)
                .execute()
            )
            rows = result.get("values", [])
            # Очищаем неразрывные пробелы (\xa0) из денежного формата
            return [
                [str(cell).replace("\xa0", "").strip() if isinstance(cell, str) else cell for cell in row]
                for row in rows
            ]
        except HttpError as e:
            raise Exception(f"Ошибка чтения диапазона {range_name}: {e}")

    def read_all_cells(self, sheet_name: Optional[str] = None) -> List[List[Any]]:
        """Читает все ячейки с первого (или указанного) листа."""
        names = self.get_sheet_names()
        if not names:
            return []
        target = sheet_name or names[0]
        return self.read_range(target)

    # ------------------------------------------------------------------
    # Запись
    # ------------------------------------------------------------------

    def write_range(
        self,
        range_name: str,
        values: List[List[Any]],
        value_input_option: str = "USER_ENTERED",
    ) -> dict:
        """
        Записывает данные в диапазон.
        Args:
            range_name: диапазон в формате "Лист!A1:D5" или "A1:D5"
            values: список строк, каждая строка = список значений
            value_input_option: 'RAW' или 'USER_ENTERED'
        """
        try:
            body = {"values": values}
            return (
                self.service.spreadsheets()
                .values()
                .update(
                    spreadsheetId=self.spreadsheet_id,
                    range=range_name,
                    valueInputOption=value_input_option,
                    body=body,
                )
                .execute()
            )
        except HttpError as e:
            raise Exception(f"Ошибка записи данных: {e}")

    def update_cell(
        self,
        cell_address: str,
        value: Union[str, int, float],
        sheet_name: Optional[str] = None,
        value_input_option: str = "USER_ENTERED",
    ) -> dict:
        """Обновляет одну ячейку. cell_address: например 'A1'."""
        range_name = f"{sheet_name}!{cell_address}" if sheet_name else cell_address
        return self.write_range(range_name, [[value]], value_input_option)

    def append_row(
        self,
        values: List[Any],
        sheet_name: Optional[str] = None,
        value_input_option: str = "USER_ENTERED",
    ) -> dict:
        """Добавляет строку в конец таблицы."""
        try:
            names = self.get_sheet_names()
            target = sheet_name or (names[0] if names else "Sheet1")
            body = {"values": [values]}
            return (
                self.service.spreadsheets()
                .values()
                .append(
                    spreadsheetId=self.spreadsheet_id,
                    range=target,
                    valueInputOption=value_input_option,
                    body=body,
                )
                .execute()
            )
        except HttpError as e:
            raise Exception(f"Ошибка добавления строки: {e}")

    def clear_range(self, range_name: str) -> dict:
        """Очищает диапазон (значения, но не форматирование)."""
        try:
            return (
                self.service.spreadsheets()
                .values()
                .clear(spreadsheetId=self.spreadsheet_id, range=range_name)
                .execute()
            )
        except HttpError as e:
            raise Exception(f"Ошибка очистки диапазона: {e}")

    def delete_row(self, row_number: int, sheet_name: Optional[str] = None) -> dict:
        """Удаляет строку по номеру (1-based)."""
        sheet_id = 0
        if sheet_name:
            sheet_id = self.get_sheet_id_by_name(sheet_name) or 0
        body = {
            "requests": [
                {
                    "deleteDimension": {
                        "range": {
                            "sheetId": sheet_id,
                            "dimension": "ROWS",
                            "startIndex": row_number - 1,
                            "endIndex": row_number,
                        }
                    }
                }
            ]
        }
        try:
            return (
                self.service.spreadsheets()
                .batchUpdate(spreadsheetId=self.spreadsheet_id, body=body)
                .execute()
            )
        except HttpError as e:
            raise Exception(f"Ошибка удаления строки: {e}")

    # ------------------------------------------------------------------
    # Форматирование (batchUpdate)
    # ------------------------------------------------------------------

    def _rgb(self, hex_color: str) -> dict:
        """Конвертирует '#RRGGBB' в {red, green, blue} 0..1."""
        hex_color = hex_color.lstrip("#")
        r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        return {"red": r / 255, "green": g / 255, "blue": b / 255}

    def _grid_range(self, sheet_id: int, start_row: int, end_row: int, start_col: int, end_col: int) -> dict:
        return {
            "sheetId": sheet_id,
            "startRowIndex": start_row,
            "endRowIndex": end_row,
            "startColumnIndex": start_col,
            "endColumnIndex": end_col,
        }

    def batch_format(self, requests: list) -> dict:
        """Выполняет список batchUpdate-запросов к spreadsheets.batchUpdate."""
        if not requests:
            return {}
        try:
            return (
                self.service.spreadsheets()
                .batchUpdate(spreadsheetId=self.spreadsheet_id, body={"requests": requests})
                .execute()
            )
        except HttpError as e:
            raise Exception(f"Ошибка форматирования: {e}")

    def format_background(self, sheet_id: int, start_row: int, end_row: int,
                          start_col: int, end_col: int, hex_color: str) -> dict:
        """Заливает фон диапазона указанным цветом."""
        req = {
            "repeatCell": {
                "range": self._grid_range(sheet_id, start_row, end_row, start_col, end_col),
                "cell": {"userEnteredFormat": {"backgroundColor": self._rgb(hex_color)}},
                "fields": "userEnteredFormat.backgroundColor",
            }
        }
        return self.batch_format([req])

    def format_text(
        self,
        sheet_id: int,
        start_row: int,
        end_row: int,
        start_col: int,
        end_col: int,
        bold: bool = False,
        font_size: int = 10,
        text_color: str = "#000000",
        horizontal_alignment: str = "LEFT",
    ) -> dict:
        """Устанавливает шрифт, размер, цвет и выравнивание в диапазоне."""
        req = {
            "repeatCell": {
                "range": self._grid_range(sheet_id, start_row, end_row, start_col, end_col),
                "cell": {
                    "userEnteredFormat": {
                        "textFormat": {
                            "bold": bold,
                            "fontSize": font_size,
                            "foregroundColor": self._rgb(text_color),
                        },
                        "horizontalAlignment": horizontal_alignment,
                    }
                },
                "fields": "userEnteredFormat(textFormat,horizontalAlignment)",
            }
        }
        return self.batch_format([req])

    def merge_cells(self, sheet_id: int, start_row: int, end_row: int,
                    start_col: int, end_col: int) -> dict:
        """Объединяет ячейки в диапазоне."""
        req = {
            "mergeCells": {
                "range": self._grid_range(sheet_id, start_row, end_row, start_col, end_col),
                "mergeType": "MERGE_ALL",
            }
        }
        return self.batch_format([req])

    def set_column_width(self, sheet_id: int, col_index: int, pixel_width: int) -> dict:
        """Устанавливает ширину столбца в пикселях."""
        req = {
            "updateDimensionProperties": {
                "range": {
                    "sheetId": sheet_id,
                    "dimension": "COLUMNS",
                    "startIndex": col_index,
                    "endIndex": col_index + 1,
                },
                "properties": {"pixelSize": pixel_width},
                "fields": "pixelSize",
            }
        }
        return self.batch_format([req])

    def add_borders(self, sheet_id: int, start_row: int, end_row: int,
                    start_col: int, end_col: int, style: str = "SOLID") -> dict:
        """Добавляет рамки ко всем ячейкам диапазона."""
        border = {"style": style, "color": self._rgb("#AAAAAA")}
        req = {
            "updateBorders": {
                "range": self._grid_range(sheet_id, start_row, end_row, start_col, end_col),
                "top": border,
                "bottom": border,
                "left": border,
                "right": border,
                "innerHorizontal": border,
                "innerVertical": border,
            }
        }
        return self.batch_format([req])


# ---------------------------------------------------------------------------
# Точка входа для тестирования модуля
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    CREDENTIALS_PATH = "service_account.json"   # JSON-ключ сервисного аккаунта
    SPREADSHEET_ID = "YOUR_SPREADSHEET_ID_HERE"  # ID из URL таблицы

    sheets = GoogleSheets(CREDENTIALS_PATH, SPREADSHEET_ID)

    print("Доступные листы:")
    for name in sheets.get_sheet_names():
        print(f"  - {name}")

    print("\nЧтение всех ячеек из первого листа:")
    print("-" * 50)
    all_cells = sheets.read_all_cells()
    if not all_cells:
        print("Таблица пуста")
    else:
        for i, row in enumerate(all_cells, 1):
            print(f"Строка {i}: {row}")
    print("-" * 50)
    print(f"Всего строк: {len(all_cells)}")
