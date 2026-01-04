# Receptų API – frontendo integracijos vadovas

Projektas naudoja **Django 5 + Django Ninja** ir ekspozuoja JSON API, kurią vartoja būsimasis Svelte/SPA frontendas. Šis dokumentas aprašo, kaip paleisti backendą, kokius endpointus turime, kokie laukų formatai, kokių saugumo reikalavimų laikytis ir kokia automatika (el. laiškai, vaizdai) vykdoma užkulisiuose.

## Darbo eiga (sutarta)

Kad nekauptume „neaiškių“ pokyčių ir frontendui visada būtų aišku kas pasikeitė, laikomės tokios taisyklės:

1. Padarom pakeitimą kode.
2. Patikrinam, kad veikia (bent: `poetry run python manage.py check` + migracijos jei buvo modelių pokyčių).
3. Iškart papildom šitą README (API laukai, endpointai, changelog, pavyzdžiai).
4. Iškart darom `git commit` ir `git push`.

Pastaba: `.env`, `.venv`, `staticfiles/` į git nekeliam.

## 1. Paleidimas ir aplinka

1. Įsidiek Poetry priklausomybes:
   ```bash
   cd backend
   poetry install
   ```
2. Susikurk `.env` pagal `.env.example`. Frontendui svarbiausi kintamieji:
   - `FRONTEND_URL` – domenas, iš kurio bus siunčiami XHR (naudojamas CORS sąrašui ir nuorodoms el. laiškuose).
   - `CORS_ALLOWED_ORIGINS` – papildomi originai jei reikia vietinių nuorodų (pvz., `http://localhost:5173`).
   - `PASSWORD_RESET_FRONTEND_PATH` – šablonas slaptažodžio keitimo „deep linkui“ (`/auth/reset-password/{uid}/{token}`).
3. Užversk DB ir paleisk serverį:
   ```bash
   poetry run python manage.py migrate
   poetry run python manage.py createsuperuser
   poetry run python manage.py runserver
   ```
4. Swagger/Redoc generuoja Ninja – pasieksi `http://127.0.0.1:8000/api/docs` kai serveris paleistas.

Naudingi skriptai: `poetry run python manage.py check`, `poetry run python manage.py makemigrations`, `poetry run pytest`, `poetry run ruff check .`.

## 2. Baziniai URL ir atsakymų formatas

- API bazinis prefiksas valdomas per `NINJA_BASE_PATH` (`api/` pagal nutylėjimą). Produkcijoje rekomenduojamas `https://api.apetitas.lt/api/...`.
- Visi atsakymai JSON, datų/timestampų formatas – ISO 8601 (UTC su laikrodžiu arba `null`).
- Aprašymo laukai (`description`) laikomi kaip **Markdown** (kaip Strapi laikais). Frontendas (Svelte) pats renderina Markdown į HTML.
- Kai kuriuose moduliuose dar gali būti legacy HTML laukai (pvz. `hero_text_html` site turinyje) – jei jie tušti, frontendas turi ignoruoti.
- Failų URL grąžinami absoliutūs (S3 arba `MEDIA_URL`) – nereikia papildomo sujungimo.

## 3. Autentifikacija, sesijos ir saugumas

- Naudojame klasikines Django sesijas + CSRF. Visi state-changing endpointai (register, login, logout, bookmarks, comments, rating, password reset) reikalauja galiojančio `csrftoken` slapuko ir `X-CSRFToken` headerio. Frontendui būtina siųsti `credentials: 'include'` kiekvienam requestui.
- Pradinė seka: iškviesk `GET /api/auth/session`. Šis endpointas visada grąžina naujausią `csrf_token` (be to, nustato `csrftoken` slapuką) ir parodo, ar naudotojas jau prisijungęs.
- Prisijungimas vyksta per `POST /api/auth/login`. Payload sudaro `identifier` (vartotojo vardas arba el. paštas) ir `password`. Jei duomenys teisingi, atsakymas – tas pats `SessionSchema` kaip iš `/session`. Atsijungimas – `POST /api/auth/logout`.
- Endpointai, kurie keičia naudotojo duomenis (`/bookmark`, `/comments`, `/rating`) reikalauja aktyvios Django sesijos; kitaip grąžinamas HTTP 401 su JSON `{"detail": "..."}`.
- CORS leidžia tik `.env` nurodytas kilmes. Kad slapukas veiktų, `fetch` kvietimuose nurodyk `credentials: 'include'` ir pridėk `X-CSRFToken` su reikšme iš `csrftoken` slapuko.
- Visas srautas privalo vykti per HTTPS; `.env` `PRIMARY_DOMAIN` ir `API_HOST` naudojami `CSRF_TRUSTED_ORIGINS` ir `ALLOWED_HOSTS` sąrašams.
- Slaptažodžio atstatymo API visada grąžina `sent: true`, kad išvengtume email enumaracijos.

## 4. Schema santrauka

- **ImageSetSchema** – visiems receptų ir žingsnių vaizdams:
  ```json
  {
    "original": "https://cdn/recipes/hero/foo.jpg",
    "thumb": { "avif": "...", "webp": "..." },
    "small": { "avif": "...", "webp": "..." },
    "medium": { "avif": "...", "webp": "..." },
    "large": { "avif": "...", "webp": "..." }
  }
  ```
````

<!-- EOF -->
- **RecipeSummarySchema** – `images`, `rating_average`, `rating_count`, `tags`, `is_bookmarked`.
- **RecipeSummarySchema** – taip pat turi `is_generated` (AI sugeneruotas receptas).
- **RecipeDetailSchema** – pratęsia summary su `note` (tip/pastaba), `categories`, `meal_types`, `cuisines`, `cooking_methods`, `ingredients`, `steps`, `comments`, `user_rating`.
   - Taip pat gali turėti `nutrition` (JSON su maistine verte) ir `nutrition_updated_at` (kada paskutinį kartą perskaičiuota).
   - Taip pat grąžina `meta_title` ir `meta_description` (SEO; naudojama frontendo `<title>` ir `<meta name="description">`).
- **CommentSchema** – `is_approved` nurodo ar komentaras viešas. Jei komentarą išsiuntė pats prisijungęs naudotojas, jis matys jį net ir kol nepatvirtintas.

## 5. API endpointai

### 5.1 Site content routeris (`/api/sitecontent`)

| Endpointas | Metodas | Auth     | Aprasymas                                                 |
| ---------- | ------- | -------- | --------------------------------------------------------- |
| `/header`  | GET     | nereikia | Paskutinis aktyvus `SiteHeader` su menu ir dropdownais.   |
| `/footer`  | GET     | nereikia | Footer blokas su stulpeliais, hero tekstu ir hero vaizdu. |
| `/heroes`  | GET     | nereikia | Visi aktyvūs hero blokai (naudinga karuselėms).           |

Laukų struktūrą apibrėžia `sitecontent/schemas.py`. Visos vizualios reikšmės (`logo`, `image`, `hero_image`) jau absoliučios.

### 5.2 Receptų routeris (`/api/recipes`)

#### 5.2.1 Sąrašas ir filtrai

`GET /api/recipes?search=...&tag=...&category=...&cuisine=...&meal_type=...&difficulty=...&limit=20&offset=0`

- `limit` 1..100, `offset` 0..N.
- `search` ieško `title`, `description`.
- Kiti filtrai naudoja susijusių objektų slugus.

Filtrų pasirinkimų sąrašai (kad frontendas galėtų susirinkti dropdown'us):

Lengvi (maži) filtrai vienu request'u:

`GET /api/recipes/filters`

Grąžina:
- `cuisines[]` (id, name, slug)
- `meal_types[]` (id, name, slug)
- `cooking_methods[]` (id, name, slug)
- `difficulties[]` (key, label)

Dideliems sąrašams (geresnis našumas: paginacija + search) naudok atskirus endpointus:

- `GET /api/recipes/categories?search=...&limit=50&offset=0&parent_id=...&root_only=true`
- `GET /api/recipes/tags?search=...&limit=50&offset=0`
- (papildomai, jei reikia paginuoti ir kitus):
   - `GET /api/recipes/cuisines?search=...&limit=50&offset=0`
   - `GET /api/recipes/meal-types?search=...&limit=50&offset=0`
   - `GET /api/recipes/cooking-methods?search=...&limit=50&offset=0`

Ingredientams (ingredientų picker'iui):

- `GET /api/recipes/ingredient-categories?search=...&limit=50&offset=0&parent_id=...&root_only=true`
- `GET /api/recipes/ingredients?search=...&limit=50&offset=0&category=<CATEGORY_SLUG>`
   - `items[].category` grąžina `id/name/slug/parent_id`, kad frontendas galėtų grupuoti pagal kategorijas.
- Atsakymas:
  ```json
  {
     "total": 125,
     "items": [
        {
           "id": 42,
           "title": "Bolonijos troškinys",
           "slug": "bolonijos-troskinys",
           "difficulty": "medium",
           "is_generated": false,
           "images": { ... },
           "preparation_time": 15,
           "cooking_time": 120,
           "servings": 4,
           "published_at": "2025-12-31T12:00:00+00:00",
           "rating_average": 4.6,
           "rating_count": 32,
           "tags": [{"id": 1, "name": "Greita"}],
           "is_bookmarked": true
        }
     ]
  }
  ```

#### 5.2.2 Naudotojo žymės

- `GET /api/recipes/bookmarks` – tik prisijungus. Grąžina `RecipeListResponse` su visais išsaugotais receptais (pagal `Bookmark.created_at`).

#### 5.2.3 Detalė

- `GET /api/recipes/{slug}` – grąžina `RecipeDetailSchema`. Papildomi niuansai:
  - `ingredients` turi `Note`, `MeasurementUnit` (`name`, `short_name`).
  - `steps` turi `images` objektą, `duration` minutėmis, `video_url` jei yra.
  - `comments` – jei žiūrintis naudotojas pats autorius, matys savo komentarą nors jis ir `is_approved = false`.
  - `user_rating` – naudotojo vertė, jei buvo balsuota.

#### 5.2.4 Veiksmai

| Endpointas       | Metodas | Auth      | Aprašymas                                                                                                             |
| ---------------- | ------- | --------- | --------------------------------------------------------------------------------------------------------------------- |
| `/{id}/bookmark` | POST    | privaloma | Toggle. Jei įrašo nėra – sukuriamas (`{"is_bookmarked": true}`), kitu atveju ištrinama (`false`).                     |
| `/{id}/comments` | POST    | privaloma | Sukuria komentarą (`content` 3..2000 simbolių). Atsakymas – `CommentSchema`. Automatiškai siunčiamas laiškas adminui. |
| `/{id}/rating`   | POST    | privaloma | `value` 1..5. Įrašas atnaujinamas jei egzistuoja. Atsakymas – `{ "value": 5 }`.                                       |

Visais atvejais neautorizuotas naudotojas gauna 401 ir pranešimą lietuviškai.

### 5.3 Auth routeris (`/api/auth`)

| Endpointas     | Metodas | Auth         | Aprašymas |
| -------------- | ------- | ------------ | --------- |
| `/session`     | GET     | nereikia     | Grąžina `SessionSchema`: `is_authenticated`, `user`, `csrf_token`. Kiekvienas iškvietimas atnaujina `csrftoken` slapuką. |
| `/register`    | POST    | CSRF + slapukas | Priima `RegisterRequestSchema` (`email`, `password`, `username?`, `full_name?`, `newsletter_consent`, `privacy_policy_consent`, `terms_of_service_consent`). Sukuria naudotoją, išsaugo sutikimus, prisijungia ir grąžina `SessionSchema`. |
| `/login`       | POST    | CSRF + slapukas | Priima `LoginRequestSchema` (`identifier`, `password`). Sėkmės atveju paskiria Django sesiją ir grąžina `SessionSchema`. |
| `/logout`      | POST    | CSRF + slapukas | Ištrina sesiją ir suteikia naują CSRF tokeną. |
| `/consents`    | POST    | CSRF + slapukas | Atnaujina prisijungusio naudotojo sutikimus. Priima bet kurią `newsletter_consent|privacy_policy_consent|terms_of_service_consent` kombinaciją (kiti laukai gali būti praleisti). |
| `/password-reset` | POST | CSRF + slapukas | `{ "email": "vartotojas@example.com" }`. Net jei email neegzistuoja, atsakymas `{ "sent": true }`. Laiškas kuria nuorodą pagal `PASSWORD_RESET_FRONTEND_PATH`. |
| `/password-reset-confirm` | POST | CSRF + slapukas | Priima `{ "uid": "...", "token": "...", "new_password": "..." }` ir pakeičia slaptažodį. Atsakymas `{ "changed": true }`. |

Sutikimai grįžta per `SessionSchema.user.consents`:
```json
{
   "is_authenticated": true,
   "csrf_token": "...",
   "user": {
      "id": 1,
      "email": "u@example.com",
      "username": "u",
      "full_name": null,
      "consents": {
         "newsletter_consent": true,
         "privacy_policy_consent": true,
         "terms_of_service_consent": true,
         "newsletter_consent_at": "2026-01-03T12:00:00+00:00",
         "privacy_policy_consent_at": "2026-01-03T12:00:00+00:00",
         "terms_of_service_consent_at": "2026-01-03T12:00:00+00:00"
      }
   }
}
```

`POST /api/auth/consents` pavyzdys (update):
```json
{
   "newsletter_consent": false
}
```
Atsakymas:
```json
{
   "consents": {
      "newsletter_consent": false,
      "privacy_policy_consent": true,
      "terms_of_service_consent": true,
      "newsletter_consent_at": null,
      "privacy_policy_consent_at": "2026-01-03T12:00:00+00:00",
      "terms_of_service_consent_at": "2026-01-03T12:00:00+00:00"
   }
}
```

Frontendo seka:
1. `GET /api/auth/session` → perskaitai `csrf_token` iš atsakymo (arba `csrftoken` slapuko).
2. Visi vėlesni POST/DELETE turi headerį `X-CSRFToken: <csrftoken>` ir `credentials: 'include'`.
3. Jei sesija pasensta, `session` endpointas vėl grąžins `is_authenticated: false`.

## 6. El. laiškų automatika

- **Registracija / vartotojo sukurimas** – `notifications/signals.py` reaguoja į `post_save` ir siunčia `welcome` šabloną.
- **Slaptažodžio atstatymas** – valdomas per minėtą Auth endpointą, šablono raktas `password_reset`.
- **Komentaro pateikimas** – po `POST /recipes/{id}/comments` backendas paima `COMMENT_NOTIFICATION_RECIPIENTS` (iš `.env`) ir siunčia `comment_notification` šabloną su nuoroda į Django admin (`admin:recipes_comment_change`).

Jei kokio nors šablono nėra arba jis išjungtas, loguose matysime įspėjimą, o API vis tiek atsakys 200 – frontendui nereikia kartoti užklausos.

## 7. Medija, paveikslėliai ir talpyklos

- Įkeliant vaizdą per adminą, `django-imagekit` sukuria AVIF ir WEBP versijas keturiais dydžiais (`thumb`, `small`, `medium`, `large`). Frontendas gauna tik nuorodas – failų generuoti nereikia.
- `RecipeSummarySchema.images.original` vis dar rodo pradinį failą (paprastai JPEG/PNG) – naudok tik kaip fallback.
- Jei `USE_S3=true`, nuorodos bus `https://storage...`; kitu atveju `http://127.0.0.1:8000/media/...`.

## 8. Klaidos ir statuso kodai

- `HttpError` iš Ninja pateikiamas kaip `{ "detail": "Pranešimas" }`.
- Dažniausi kodai:
  - `400` – bendras netinkamas payloadas (pvz., trūksta `content`).
  - `401` – naudotojas neprisijungęs.
  - `404` – receptas ar slugas nerastas.
  - `422` – validacijos klaida (naudojama password reset formoje).
  - `500` – nenumatyta klaida (logai + Sentry ateityje).

## 9. Tipinė frontendo seka

1. **Konfigūracija** – laikyk API bazę `.env` (pvz., `VITE_API_URL=https://api.apetitas.lt/api`).
2. **Sesijos inicijavimas** – po puslapio įkėlimo paleisk `await fetch('/api/auth/session', { credentials: 'include' })`. Atsakymas duos `csrf_token` ir naudotojo būseną. Išsaugok tokeną (arba perskaityk `document.cookie` -> `csrftoken`).
3. **Registracija / prisijungimas / atsijungimas** – `POST /api/auth/register|login|logout` su `credentials: 'include'`, `Content-Type: application/json` ir `X-CSRFToken` iš ankstesnio žingsnio.
4. **Vieši puslapiai** – bet kuris naudotojas gali kviesti `GET /sitecontent/*` ir `GET /recipes/*` (CSRF nereikia).
5. **Naudotojo veiksmai** – bookmark, komentarai, reitingai naudoja tą pačią sesiją, todėl POST requestams būtini: aktyvi sesija, `credentials: 'include'` ir `X-CSRFToken`.
6. **Slaptažodžio atkūrimas** – `POST /auth/password-reset` (su CSRF) inicijuoja laišką; gavus nuorodą, frontendas atidarys `PASSWORD_RESET_FRONTEND_PATH` maršrutą su `uid` + `token`.
   - Atidarytame puslapyje frontendas turi iškviesti `POST /auth/password-reset-confirm` su `{ uid, token, new_password }` (taip pat su CSRF).
7. **Vaizdai** – iš `images` objekto rinkis geriausią variantą (pvz., `<source type="image/avif" srcset=...>`).

## 10. Ateities darbai / plėtra

- Vieši receptų siuntimo formos endpointai.
- Paieškos / rekomendacijų servisai su dedikuotu indeksu.
- Rate limiting ir API key palaikymas partneriams arba mobiliosioms aplikacijoms.

## 12. Changelog (backend API pokyčiai)

> Ši skiltis skirta frontendui: trumpai ir tiksliai, kas pasikeitė, kad būtų aišku ką atnaujinti.

### 2026-01-03

- **Auth / sutikimai**
   - `POST /api/auth/register` payload papildytas sutikimais: `newsletter_consent`, `privacy_policy_consent`, `terms_of_service_consent`.
   - `GET /api/auth/session` atsakyme `user` dabar turi `consents` objektą su `*_consent` + `*_consent_at`.
   - Naujas endpointas `POST /api/auth/consents` (CSRF + prisijungęs) – atnaujina sutikimus (galima siųsti dalinį payload).
   - Admin’e sutikimai matomi per `UserConsents` (inline prie User ir atskiras sąrašas).
- **Recipes / AI žyma**
   - `RecipeSummarySchema` ir `RecipeDetailSchema` turi `is_generated` – frontas gali aiškiai pažymėti AI sugeneruotus receptus.
- **Admin / Markdown turinys**
   - `Recipe.note` ir `RecipeStep.note` (tip/pastaba) pridėti kaip paprastas tekstas.
- **Recipes / nutrition (maistinė vertė)**
   - `GET /api/recipes/{slug}` detalėje gali atsirasti `nutrition` ir `nutrition_updated_at` (kol kas `null`, kol job'ai neapdoroti).
   - Pridėtas `RecipeNutritionJob` ir komanda `enqueue_recipe_nutrition_jobs` naktiniam job'ų suformavimui.

### 2026-01-02

- **Auth / slaptažodžio atkūrimas**
   - Pridėtas `POST /api/auth/password-reset-confirm` (su CSRF) – leidžia fronte užbaigti password reset flow.
- **API docs URL**
   - `/api/docs/` pataisyta (trailing slash) – Ninja docs veikia stabiliai.
- **Recipes / atsparumas trūkstamiems failams + greitis**
   - Receptų/žingsnių image URL generavimas padarytas atsparus trūkstamiems objektams S3/R2 (nebemetama 500 dėl `FileNotFoundError`).
   - Mažiau brangių S3 HEAD užklausų (URL generavimas remiasi storage URL).
- **Admin / ingredientų grupės**
   - `RecipeIngredient` unikalumas pakeistas, kad tas pats ingredientas galėtų kartotis skirtingose grupėse (pvz. tešla / įdaras).
- **Vaizdų variantai**
   - Image variantai generuojami tik kai realiai pasikeičia vaizdas, ne kiekvieno `save()` metu.

### 2026-01-01 (ar anksčiau)

- **S3/R2**
   - `AWS_S3_CUSTOM_DOMAIN` normalizacija, kad nesusidarytų neteisingi `MEDIA_URL` (pvz. `https://https://...`).

## 13. Ateities planai: OpenAI receptų generavimas

Tikslas: prisijungęs vartotojas puslapyje susirenka ingredientus (iš DB + custom tekstiniai), atsako į kelis klausimus (porcijos, laikas, dieta, virtuvė), ir sistema sugeneruoja receptą (Markdown) + (vėliau) vaizdą. Ateityje – mokamas planas.

### 13.1 Minimalus MVP (be mokėjimų)

- **Naujas modelis** `RecipeGenerationJob`:
   - `user`, `status` (queued/running/succeeded/failed), `inputs` (JSON: atsakymai + custom ingredientai), `selected_ingredient_ids` (JSON/list), `result_recipe_id`, `error`, `token_usage`, `created_at`.
- **Nauji endpointai** (Ninja, CSRF + prisijungęs):
   - `POST /api/ai/recipe-jobs` – sukuria job’ą ir grąžina `job_id`.
   - `GET /api/ai/recipe-jobs/{id}` – grąžina būseną; kai baigta – ir sugeneruoto recepto slug/id.
- **Asinchroninis vykdymas**:
   - Generavimas vykdomas worker’yje (Celery/RQ + Redis), ne HTTP request’e.
- **Rezultato įrašymas**:
   - Sukuriamas `Recipe` su `is_generated=true`, `description` (Markdown), `note` (tip, jei yra).
   - Sukuriami `RecipeStep` su `description` (Markdown) ir `note` (nebūtina).
   - Ingredientai map’inami į esamus `Ingredient`; nerasti – arba kuriami nauji (jei pasirinkta), arba paliekami kaip tekstinė pastaba ingredientų eilutėje.

### 13.2 Vaizdas (atskirai nuo MVP)

- Vaizdo generavimą verta daryti kaip **antrą job’ą** (pvz. `RecipeImageJob`), kad receptas atsirastų greitai, o hero paveikslas „prisikabintų“ vėliau.
- Sugeneruotas failas įkeliamas į R2 per esamą storage; tada suveikia įprasta image variantų grandinė.

### 13.3 Kokybė, sauga ir moderavimas

- Žymėti AI turinį per `is_generated` ir UI disclaimer.
- Alergenai/dietos: į promptą įtraukti aiškias taisykles, o rezultatus papildomai validuoti (pvz. kad nenaudotų draudžiamų ingredientų).
- Rate limiting: riboti generacijų skaičių per dieną naudotojui.
- Audit: saugoti `token_usage`, `error`, minimalų prompt/input (be jautrių duomenų).

### 13.4 Mokėjimai (vėlesnis etapas)

- Pradžiai paprasčiausia: prenumeratos planas (generacijų limitas) arba „credit“ sistema.
- Webhook’ai + patikra server-side prieš įleidžiant į `POST /api/ai/recipe-jobs`.

### 13.5 Maistinė vertė (nutrition) – batch/naktinis apdorojimas

Tikslas: turėti maistinę vertę prie recepto (pvz. kcal, baltymai, riebalai, angliavandeniai, ir kt.) ir ją automatiškai perskaičiuoti, kai pasikeičia ingredientai.

- `Recipe` modelyje yra laukai: `nutrition` (JSON), `nutrition_updated_at`, `nutrition_dirty`.
- Kai pasikeičia `RecipeIngredient`, receptas automatiškai pažymimas `nutrition_dirty=true`.
- Naktiniam job'ui yra `RecipeNutritionJob` modelis (statusai: queued/running/succeeded/failed).

Komanda, kuri sukuria job'us (pvz. cron'ui arba vėliau Celery beat):

```bash
poetry run python manage.py enqueue_recipe_nutrition_jobs --limit=200
```

Komanda, kuri apdoroja job'us ir užpildo `Recipe.nutrition` (pirmai iteracijai – tiesiogiai per OpenAI, be Batch):

```bash
poetry run python manage.py process_recipe_nutrition_jobs --limit=20
```

Batch režimas (didesniam kiekiui per naktį):

1) Submit batch iš `queued` job'ų:

```bash
poetry run python manage.py submit_recipe_nutrition_batch --limit=200
```

2) Poll batch ir importuok rezultatus (kai batch užbaigtas):

```bash
poetry run python manage.py poll_recipe_nutrition_batch --batch-id <OPENAI_BATCH_ID>
```

Jei `--batch-id` nenurodai, komanda bandys apdoroti visas `submitted` batch'ų grupes (iki kelių skirtingų batch'ų per vieną paleidimą).

Nutrition JSON grąžina apytikslę maistinę vertę per porciją ir EU14 alergenus. Rekomenduojama UI visada rodyti, kad tai yra apytikslės reikšmės.

#### Deploy: automatinis paleidimas per systemd (rekomenduojama)

Repo yra šablonai systemd unit/timer failams (naudojama lokali virtualenv, be Poetry):

```bash
sudo cp /home/deploy/backend/app/deploy/systemd/apetitas-nutrition-*.service /etc/systemd/system/
sudo cp /home/deploy/backend/app/deploy/systemd/apetitas-nutrition-*.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now apetitas-nutrition-nightly.timer apetitas-nutrition-poll.timer
```

Patikrinimas:

```bash
systemctl list-timers --all | grep apetitas-nutrition
journalctl -u apetitas-nutrition-nightly.service -n 100 --no-pager
journalctl -u apetitas-nutrition-poll.service -n 100 --no-pager

### 13.6 SEO meta (meta_title / meta_description) – naktinis užpildymas

- `Recipe` modelyje yra laukai: `meta_title` (max 80) ir `meta_description` (max 160).
- `Recipe.save()` automatiškai užpildo `meta_title = title`, bet senesni įrašai (arba bulk update/importai) gali likti su tuščiais meta laukais.
- Naktinis job'as **užpildo tik tuščius** (`""` / whitespace) `meta_title` ir `meta_description`, sugeneruodamas reikšmes per **OpenAI** iš recepto konteksto (pavadinimo, aprašymo, virtuvių, meal type, kategorijų, tagų, gaminimo būdų ir ingredientų).
- Naudojamas modelis konfigūruojamas per `.env` `OPENAI_META_MODEL` (default: `gpt-4o-mini`).

Rankinis paleidimas:
```bash
poetry run python manage.py fill_missing_recipe_meta --limit=500
poetry run python manage.py run_recipe_meta_nightly --limit=500
```

Dry-run (tik statistika, be DB pakeitimų):
```bash
poetry run python manage.py run_recipe_meta_nightly --limit=50 --dry-run
```

Systemd (produkcinis naktinis paleidimas):
```bash
sudo cp /home/deploy/backend/app/deploy/systemd/apetitas-meta-nightly.service /etc/systemd/system/
sudo cp /home/deploy/backend/app/deploy/systemd/apetitas-meta-nightly.timer /etc/systemd/system/

sudo systemctl daemon-reload
sudo systemctl enable --now apetitas-meta-nightly.timer

systemctl list-timers --all | grep apetitas-meta
journalctl -u apetitas-meta-nightly.service -n 100 --no-pager
```
```

## 11. Greta esantys moduliai

- `recipes/` – domeno modeliai, Ninja routeris, komentarų email logika.
- `sitecontent/` – globalūs header/footer/hero blokai, valdomi per Django adminą.
- `notifications/` – šablonizuoti el. laiškai ir helperiai (`send_templated_email`).

Turėdami šią informaciją frontendistai gali saugiai naudotis esamu API, žinoti laukų struktūrą bei suprasti kokie automatiniai procesai vyksta be papildomo koordinavimo.

### Frontend: nutrition laukų LT pavadinimai (pavyzdys)

```ts
export const perServingLt: Record<string, string> = {
   energy_kcal: 'Energija (kcal)',
   protein_g: 'Baltymai (g)',
   fat_g: 'Riebalai (g)',
   saturated_fat_g: 'Sočiosios riebalų rūgštys (g)',
   carbs_g: 'Angliavandeniai (g)',
   sugars_g: 'Cukrūs (g)',
   fiber_g: 'Skaidulos (g)',
   salt_g: 'Druska (g)',
};

export const microsLt: Record<string, string> = {
   cholesterol_mg: 'Cholesterolis (mg)',
   potassium_mg: 'Kalis (mg)',
   calcium_mg: 'Kalcis (mg)',
   iron_mg: 'Geležis (mg)',
};

export const allergensLt: Record<string, string> = {
   gluten: 'Glitimas',
   crustaceans: 'Vėžiagyviai',
   eggs: 'Kiaušiniai',
   fish: 'Žuvis',
   peanuts: 'Žemės riešutai',
   soy: 'Soja',
   milk: 'Pienas',
   tree_nuts: 'Riešutai',
   celery: 'Salierai',
   mustard: 'Garstyčios',
   sesame: 'Sezamai',
   sulphites: 'Sulfitai',
   lupin: 'Lubinai',
   molluscs: 'Moliuskai',
};
```