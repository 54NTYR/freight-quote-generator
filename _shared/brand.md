# Brand — Jericho Freight

One home for company fields: `config.py` → `COMPANY_INFO`. Edit there. Do not copy the values into other markdown files.

## Load these

- `config.py` — `company_name`, `phone`, `email`, `website`, `dot_number`, `mc_number`
- `templates/partials/page_header.html` — header used by every page
- `static/css/app.css` — shared colors (`#2a5298`, `#1e3c72`)
- `static/img/app-icon.png` — window / installer icon source
- `installer.iss` — `MyAppPublisher` must stay Jericho Freight

## Logo

Templates reference `static/img/jericho-freight-logo-blue.png`. If that file is missing, quotes show a broken header image. Place the logo at that path; do not invent a second logo filename.

## Do not

- Put secrets or API keys here
- Change publisher/app id in `installer.iss` unless shipping a different product
