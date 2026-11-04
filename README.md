# personalized-cv

Aplicație pentru crearea de CV-uri adaptate unui anunț de angajare, pornind de la
profilul real al candidatului și folosind un LLM.

Rezultatul urmărit este un PDF cu text selectabil și căutabil, fără experiență sau
calificări inventate.

## Stadiu

Proiectul conține cinci template-uri Markdown independente în `cv-templates/`.
Cercetarea, sursele și catalogul sunt în [docs/cv-template-research.md](docs/cv-template-research.md).
Integrarea LLM și generatorul PDF nu sunt încă implementate.

## Date locale

Păstrează profilurile, anunțurile și CV-urile generate în `private/`, `input/` sau
`output/`, excluse din Git. Cheile API se păstrează local în `.env`, de asemenea
exclus din Git. Nu adăuga date personale ale candidaților în template-uri.
