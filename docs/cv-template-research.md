# Structura CV-urilor: cercetare și catalog de template-uri

Verificat la: **4 noiembrie 2026**. Acesta este un rezumat al recomandărilor disponibile
la această dată, nu un studiu statistic care demonstrează că un anumit format este
mai popular în 2026 sau că îmbunătățește rata de angajare.

## Concluzii din surse

- **Lizibilitate și extragerea datelor.** Greenhouse enumeră coloanele, tabelele,
  imaginile și contactul din antet/subsol printre cauzele de interpretare incorectă.
  Acest lucru susține alegerea conservatoare a unei singure coloane cu text real.
  O eroare de parsare nu demonstrează respingerea automată a candidatului.
  [Greenhouse — Unsuccessful resume parse](https://support.greenhouse.io/hc/en-us/articles/200989175-Unsuccessful-resume-parse)
- **Formatare simplă.** CareerOneStop recomandă titluri uzuale, spațiere consecventă,
  font lizibil și, pentru CV-urile profesionale obișnuite, una sau două pagini.
  Recomandă PDF dacă angajatorul nu cere alt format. Lungimea nu este universală.
  [CareerOneStop — Formatting](https://cloudfront.careeronestop.org/JobSearch/Resumes/ResumeGuide/formatting.aspx)
- **Adaptare autentică asistată de AI.** Harvard descrie folosirea AI pentru revizuirea
  formulărilor și introducerea termenilor relevanți, păstrând reprezentarea autentică
  a candidatului. În proiect, orice reformulare trebuie legată de o dovadă din profil.
  [Harvard — Create a Strong Resume](https://careerservices.fas.harvard.edu/resources/create-a-strong-resume/)
- **Structura depinde de parcurs.** Oxford descrie formatul cronologic invers și
  varianta bazată pe competențe pentru tranziții. Am ales un hibrid pentru schimbarea
  de carieră, astfel încât dovezile transferabile să nu înlocuiască istoricul cu date.
  [Oxford — CVs](https://www.ox.ac.uk/careers/careers-guidance/job-search-and-applications/writing-applications/cvs)
- **Un profil, mai multe aplicații.** Europass permite alegerea informațiilor dintr-un
  profil și adaptarea CV-ului la o oportunitate. Susține fluxul proiectului:
  profil complet → selecție pentru anunț → document separat. Nu reproducem designul
  Europass și nu pretindem că fișierele noastre sunt documente Europass oficiale.
  [Europass — Create your CV](https://europass.europa.eu/en/create-europass-cv)
- **Excepții academice.** Oxford descrie secțiuni dedicate cercetării, publicațiilor
  și predării. Menționează și CV-urile narative cerute de unii finanțatori;
  acestea necesită instrucțiunile instituției, nu un template profesional generic.
  [Oxford — Academic applications](https://www.ox.ac.uk/careers/careers-guidance/job-search-and-applications/writing-applications/academic-applications)

## Alegeri ale proiectului

Template-urile reprezintă o sinteză proprie, nu copii ale unor modele instituționale.
Nu există aici o dovadă că PDF este acceptat de orice portal sau că un layout poate
obține un „scor ATS” universal. Instrucțiunile angajatorului au prioritate în privința
formatului, lungimii și formularului cerut.

Am ales implicit documente fără fotografie. Recomandările regionale diferă: de
exemplu, Europass sugerează o fotografie, în timp ce alte surse semnalează riscuri
pentru parsare. Nu tratăm o convenție regională ca regulă globală. O cerință explicită
diferită trebuie discutată înainte de folosirea acestor template-uri.

A4, marginile de 20 mm, fontul de 11 pt, numărul orientativ de puncte și separarea
raportului de adaptare sunt decizii de produs și implementare. Nu le prezentăm drept
cerințe ATS dovedite. Nu oferim un template pur funcțional sau unul cu infografice
în colecția inițială; păstrăm contextul profesional și o ordine de lectură simplă.

## Catalog

| Fișier din `cv-templates/` | Utilizare | Lungime orientativă |
| --- | --- | --- |
| `01-reverse-chronological.md` | Implicit; experiență relevantă, inclusiv senior | 1-2 pagini |
| `02-early-career.md` | Student, absolvent, internship, primul job | 1 pagină |
| `03-technical.md` | Roluri tehnice cu instrumente și proiecte documentate | 1-2 pagini |
| `04-career-change.md` | Tranziție profesională, competențe cu dovezi și istoric | 1-2 pagini |
| `05-academic.md` | Cercetare și posturi academice | După cerințele instituției |

Fiecare fișier este independent și include contractul de intrare, regulile factuale,
structura, specificația PDF și verificările. Repetarea regulilor comune este
intenționată: un LLM care primește un singur template trebuie să aibă toate regulile.
La modificarea regulilor comune, actualizează toate cele cinci fișiere și versiunile.

## Integrarea viitoare în aplicație

1. Aplicația listează numai `cv-templates/*.md`, citește metadatele și validează
   template-ul ales. Documentul de cercetare rămâne separat de catalog.
2. Alegerea explicită a utilizatorului are prioritate. Dacă aplicația recomandă
   automat o variantă, explică alegerea pe baza profilului și anunțului.
3. Trimite regulile template-ului separat de cele două intrări delimitate ca date.
   Simplele instrucțiuni anti-injecție din Markdown nu înlocuiesc izolarea din aplicație.
4. LLM-ul produce conținutul și raportul de proveniență. Aplicația validează datele
   și le transmite unui renderer controlat, de exemplu ReportLab. Nu executa cod
   generat de LLM și nu permite încărcarea automată de resurse externe.
5. Rendererul produce PDF cu text, apoi aplicația verifică extracția și layoutul.
   Înaintea trimiterii către un furnizor LLM, aplicația trebuie să explice utilizatorului
   ce date personale sunt trimise și către cine. Evită logarea profilului și cheilor API.

**Stadiu actual:** colecție de instrucțiuni Markdown. Nu există încă integrare LLM,
renderer, CV-uri generate sau validare în portaluri ATS reale. Acestea sunt pașii
următori de implementare, nu funcționalități deja livrate.
