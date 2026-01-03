# Upstash Search (Recipe index) – realizacija ir deploy (gunicorn)

Šis dokumentas yra „runbook“ integracijai ir diegimui: kaip receptai automatiškai indeksuojami į Upstash Search, kaip veikia paieška per API ir kaip tai tvarkingai paleisti produkcijoje su gunicorn.

## Tikslas ir taisyklės

- **Indeksuojami tik publikuoti receptai**: `published_at != null`.
- **Dokumentas turi būti mažas**: `steps` neindeksuojami (Upstash Search turi dokumento dydžio limitus).
- **Nefailinam išsaugojimo**: Upstash klaidos turi būti tik log’inamos (DB įrašymas neturi „crashinti“).
- **Stabilus dokumento ID**: `recipe:<id>`.
- **Indeksuojam po commit**: naudojama `transaction.on_commit`, kad indeksuotume tik sėkmingai įrašytą būseną.

## Kas jau yra kode

### 1) Upstash integracijos modulis

- [backend/recipes/upstash_search.py](../recipes/upstash_search.py)
  - `upsert_recipe(recipe_id)` – upsert’ina, jei publikuotas; jei nepublikuotas/nerastas – ištrina dokumentą.
  - `delete_recipe(recipe_id)` – ištrina dokumentą.
  - `search_recipe_ids(query, limit=...)` – grąžina `list[int]` (Upstash rezultatai) arba `None` (kai išjungta / klaida).

### 2) Signalai, kurie triggerina reindeksavimą

- [backend/recipes/signals.py](../recipes/signals.py)
  - `post_save/post_delete` ant `Recipe`
  - `post_save/post_delete` ant `RecipeIngredient`
  - `m2m_changed` ant `Recipe.tags/categories/cuisines`
  - visi kvietimai planuojami per `transaction.on_commit(...)`

### 3) Paieška per API (Django Ninja)

- [backend/recipes/api.py](../recipes/api.py)
  - kai `GET /api/recipes?search=...`:
    - bando Upstash (jei `UPSTASH_SEARCH_ENABLED=True` ir `offset < 1000`)
    - jei Upstash išjungtas ar klaida – fallback į DB `icontains`

### 4) Backfill komanda (esamiems publikuotiems receptams)

- [backend/recipes/management/commands/upstash_backfill_recipes.py](../recipes/management/commands/upstash_backfill_recipes.py)
  - `python manage.py upstash_backfill_recipes` – suindeksuoja visus publikuotus
  - `--limit N` – testui
  - `--recipe-id ID` – vienam receptui

## Konfigūracija (ENV)

### Reikalingi kintamieji

Backend’as skaito kredencialus iš OS env (ne iš settings), todėl produkcijoje reikia sukonfigūruoti:

- `UPSTASH_SEARCH_REST_URL` – Upstash Search REST URL
- `UPSTASH_SEARCH_REST_TOKEN` – Upstash Search REST token
- `UPSTASH_SEARCH_INDEX` – indeksas (pvz. `recipes`)
- `UPSTASH_SEARCH_ENABLED` – `True/False` feature flag (fallback į DB, kai `False`)

### `.env` failo formatas

- **Nerašyti tarpų** aplink `=`.
- Kabutės yra OK, bet nebūtinos. Svarbiausia, kad eilutė būtų `KEY=value`.

Pavyzdys (be realių reikšmių):

```dotenv
UPSTASH_SEARCH_REST_URL=https://....upstash.io
UPSTASH_SEARCH_REST_TOKEN=...base64...
UPSTASH_SEARCH_ENABLED=True
UPSTASH_SEARCH_INDEX=recipes
```

## Deploy su gunicorn (rekomenduojamas variantas: systemd)

Žemiau – tipinis scenarijus, kai Django/gunicorn paleistas kaip systemd service.

### 1) Įdiegti Python priklausomybę

Jei naudojate Poetry:

```bash
cd backend
poetry add upstash-search
poetry lock
```

Deploy metu:

```bash
cd backend
poetry install --only main
```

Jei naudojate pip/requirements:

```bash
pip install upstash-search
```

### 2) Užtikrinti, kad signalai užsikrauna

Patikrinkite, kad `INSTALLED_APPS` naudoja AppConfig:

- `recipes.apps.RecipesConfig`

Tai svarbu, nes `ready()` importina signalus.

### 3) Suvesti ENV į gunicorn procesą

Dažniausiai patogiausia turėti atskirą environment failą, pvz.:

- `/etc/recipe-backend/env`

Ir systemd service faile nurodyti:

```ini
[Service]
EnvironmentFile=/etc/recipe-backend/env
```

Po pakeitimų:

```bash
sudo systemctl daemon-reload
sudo systemctl restart <jusu-service-pavadinimas>
```

### 4) Logų stebėjimas

```bash
sudo journalctl -u <jusu-service-pavadinimas> -f
```

Tikėtini logai indeksavimo metu:

- Upstash `httpx` `POST .../upsert-data/<index>` su `200 OK`

## Verifikacija po deploy

### 1) Greitas sanity check

```bash
cd backend
poetry run python manage.py check
```

### 2) Backfill (kad nereikėtų rankiniu būdu „per-saugoti“)

Testui (pirmas kartas):

```bash
poetry run python manage.py upstash_backfill_recipes --limit 10
```

Pilnam suindeksavimui:

```bash
poetry run python manage.py upstash_backfill_recipes
```

### 3) Patikrinti per API

- `GET /api/recipes?search=pica`
  - jei Upstash veikia – rezultatai ateis iš Upstash kandidatų, su DB filtrais.
  - jei Upstash neveikia/išjungtas – veiks DB `icontains` fallback.

### 4) Dažniausias „kodėl nesimato dokumento?“

- Receptas nepublikuotas (`published_at=None`) → pagal taisyklę jis **neindeksuojamas**.

## Incidentai / fallback

### Išjungti Upstash paiešką (nekeičiant kodo)

Užtenka deploy env pakeisti:

```dotenv
UPSTASH_SEARCH_ENABLED=False
```

Tada paieška per API automatiškai grįš į DB fallback.

### Upstash klaidos

- Klaidos suvalgomas (log + continue).
- Indeksavimas yra „best-effort“: jei Upstash laikinai down, DB veiks toliau.
- Po incidento paleiskite backfill komandą, kad atstatytumėte indeksą.

## Pastabos apie paginaciją

- Upstash Search šiame projekte naudojamas kaip kandidatų generatorius.
- `offset` emuliuojamas lokaliai, todėl sąmoningai taikomas apribojimas: `offset < 1000`.
