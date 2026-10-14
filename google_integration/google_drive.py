"""
Модуль для работы с Google Drive API.

- Чтение файлов — через сервисный аккаунт (JSON-ключ).
- Создание файлов (Spreadsheet, Doc) — через OAuth2 личного пользователя.
  При первом запуске откроется браузер для авторизации.
  Токен сохраняется в token.pickle и переиспользуется.
"""

from __future__ import annotations

import os
import pickle
from pathlib import Path
from typing import List, Optional

from google.auth.transport.requests import Request
from google.oauth2.service_account import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SERVICE_SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
]

OAUTH_SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
]


class GoogleDrive:
    """
    CRUD-клиент Google Drive.

    Инициализация:
        # Сервисный аккаунт (чтение / листинг)
        drive = GoogleDrive(service_account_path="service_account.json")

        # OAuth2 пользователя (создание файлов)
        drive = GoogleDrive(oauth_credentials_path="client_secret.json")
    """

    def __init__(
        self,
        service_account_path: Optional[str] = None,
        oauth_credentials_path: Optional[str] = None,
        token_path: str = "token.pickle",
    ) -> None:
        self._service = None
        self._token_path = token_path

        if service_account_path and Path(service_account_path).exists():
            creds = Credentials.from_service_account_file(
                service_account_path, scopes=SERVICE_SCOPES
            )
            self._service = build("drive", "v3", credentials=creds)

        elif oauth_credentials_path and Path(oauth_credentials_path).exists():
            creds = self._load_or_refresh_oauth(oauth_credentials_path)
            self._service = build("drive", "v3", credentials=creds)

    def _load_or_refresh_oauth(self, credentials_path: str):
        """Загружает токен из pickle или запускает OAuth-флоу."""
        creds = None
        if Path(self._token_path).exists():
            with open(self._token_path, "rb") as f:
                creds = pickle.load(f)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    credentials_path, OAUTH_SCOPES
                )
                creds = flow.run_local_server(port=0)
            with open(self._token_path, "wb") as f:
                pickle.dump(creds, f)
        return creds

    @property
    def service(self):
        if self._service is None:
            raise RuntimeError(
                "GoogleDrive не инициализирован. "
                "Передайте service_account_path или oauth_credentials_path."
            )
        return self._service

    # ------------------------------------------------------------------
    # Листинг
    # ------------------------------------------------------------------

    def list_files(self, folder_id: Optional[str] = None) -> List[dict]:
        """Возвращает список файлов. Если folder_id — только из этой папки."""
        query = f"'{folder_id}' in parents and trashed=false" if folder_id else "trashed=false"
        try:
            result = (
                self.service.files()
                .list(q=query, fields="files(id,name,mimeType,createdTime)")
                .execute()
            )
            return result.get("files", [])
        except HttpError as e:
            raise Exception(f"Ошибка листинга файлов: {e}")

    # ------------------------------------------------------------------
    # Создание
    # ------------------------------------------------------------------

    def create_google_spreadsheet(
        self, name: str, parent_folder_id: Optional[str] = None
    ) -> dict:
        """Создаёт Google Таблицу. Возвращает {'id': ..., 'url': ..., 'name': ...}."""
        metadata = {
            "name": name,
            "mimeType": "application/vnd.google-apps.spreadsheet",
        }
        if parent_folder_id:
            metadata["parents"] = [parent_folder_id]
        try:
            file = self.service.files().create(body=metadata, fields="id,name").execute()
            file_id = file["id"]
            return {
                "id": file_id,
                "name": file["name"],
                "url": f"https://docs.google.com/spreadsheets/d/{file_id}/edit",
            }
        except HttpError as e:
            raise Exception(f"Ошибка создания таблицы: {e}")

    def create_google_doc(
        self, name: str, parent_folder_id: Optional[str] = None
    ) -> dict:
        """Создаёт Google Документ. Возвращает {'id': ..., 'url': ..., 'name': ...}."""
        metadata = {
            "name": name,
            "mimeType": "application/vnd.google-apps.document",
        }
        if parent_folder_id:
            metadata["parents"] = [parent_folder_id]
        try:
            file = self.service.files().create(body=metadata, fields="id,name").execute()
            file_id = file["id"]
            return {
                "id": file_id,
                "name": file["name"],
                "url": f"https://docs.google.com/document/d/{file_id}/edit",
            }
        except HttpError as e:
            raise Exception(f"Ошибка создания документа: {e}")

    # ------------------------------------------------------------------
    # Удаление
    # ------------------------------------------------------------------

    def delete_file(self, file_id: str) -> None:
        """Удаляет файл по ID."""
        try:
            self.service.files().delete(fileId=file_id).execute()
        except HttpError as e:
            raise Exception(f"Ошибка удаления файла {file_id}: {e}")


# ---------------------------------------------------------------------------
# Точка входа для тестирования
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    SERVICE_JSON = "google_integration/service_account.json"
    FOLDER_ID = None  # вставьте ID папки для фильтрации

    if not Path(SERVICE_JSON).exists():
        print(f"Файл {SERVICE_JSON} не найден. Создайте сервисный аккаунт в Google Cloud.")
        sys.exit(1)

    drive = GoogleDrive(service_account_path=SERVICE_JSON)
    files = drive.list_files(folder_id=FOLDER_ID)
    print(f"Файлов в {'папке' if FOLDER_ID else 'Drive'}: {len(files)}")
    for f in files:
        print(f"  [{f['mimeType'].split('.')[-1]}] {f['name']} — {f['id']}")
