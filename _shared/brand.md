# Brand — Jericho Freight

One home for company fields: `config.py` → `COMPANY_INFO`. Edit there. Do not copy the values into other markdown files.

## Load these

- `config.py` — `company_name`, `legal_name`, `address`, `phone`, `email`, `website`, `dot_number`, `mc_number`
- `templates/partials/page_header.html` — header used by builder pages
- `templates/partials/quote_header.html` — quote output letterhead
- `static/css/app.css` — shared colors (`#2a5298`, `#1e3c72`, gold `#FDB913`)
- `static/img/app-icon.png` — window / installer icon source
- `installer.iss` — `MyAppPublisher` must stay Jericho Freight

## Logo

Quote outputs use `static/img/jericho-freight-logo-compact.png` on the navy letterhead (transparent canvas). Builder pages use `static/img/jericho-freight-logo-blue.png`.

## Do not

- Put secrets or API keys here
- Change publisher/app id in `installer.iss` unless shipping a different product
