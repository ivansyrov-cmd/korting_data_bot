# Каталог USP

Публичная страница формируется из:

- `FULL_GLOSSARY_USP_TEXTS.xlsx` — модели, категории, USP и описания;
- актуального Bitrix-фида на Яндекс.Диске — изображения `DIRECT_PHOTO`,
  названия и ссылки на товары.

## Обновление

Из корня репозитория:

```powershell
python build_usp_catalog.py
```

При необходимости путь к другой версии глоссария можно передать явно:

```powershell
python build_usp_catalog.py --glossary "C:\path\FULL_GLOSSARY_USP_TEXTS.xlsx"
```

Генератор обновляет:

- `docs/USP_CATALOG/catalog.json`;
- `docs/USP_CATALOG/quality-report.json`.

Страница размещена в `docs/USP_CATALOG/`. GitHub Pages публикует изменения
после отправки ветки `main`.

На страницу попадают только категории и модели, для которых заполнены USP
на листах `USP_MODELS_*`. Исходная Excel-таблица в репозиторий не добавляется.
