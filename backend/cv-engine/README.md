# CV Engine — Backend Moteur de Génération de CV (Typst)

Ce module est le moteur de génération de documents PDF extrait et optimisé pour le produit. Il convertit des données structurées (JSON / dictionnaire Python provenant d'un modèle IA) en un document PDF d'une qualité typographique supérieure via **Typst** et **Jinja2**.

---

## 🏗️ Architecture du dossier `backend/`

```
cv-engine/
├── backend/
│   ├── typst/
│   │   ├── lib.typ              # Cœur du design system Typst (layout, spacing, 87 params)
│   │   └── typst.toml           # Configuration du package Typst local
│   ├── templates/               # Templates Jinja2
│   │   ├── Preamble.j2.typ      # Configuration & imports Typst
│   │   ├── Header.j2.typ        # En-tête (Nom, Titre, Contacts)
│   │   ├── SectionBeginning.j2.typ
│   │   ├── SectionEnding.j2.typ
│   │   └── entries/             # Templates pour chaque type d'entrée (Experience, Education, etc.)
│   ├── transformers/            # Transformateurs et utilitaires de contenu
│   │   ├── markdown_to_typst.py # Convertisseur Markdown -> Typst (bold, links, code)
│   │   ├── placeholder_engine.py# Substitution intelligente et nettoyage des champs absents
│   │   ├── date_formatter.py    # Formateur de dates multilingue (i18n, durées)
│   │   └── string_utils.py      # Bolding auto de mots-clés, nettoyage URL
│   ├── models.py                # Schémas légers (sans Pydantic lourd) & dictionnaires i18n
│   ├── renderer.py              # Orchestrateur (JSON/Dict -> Code Typst)
│   └── compiler.py              # Compilateur (Code Typst -> PDF/PNG via typst-py)
├── test_cv_engine.py            # Script de démonstration et validation
└── pyproject.toml               # Fichier de projet Python
```

---

## 🚀 Utilisation Rapide

### 1. Installation des dépendances

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install jinja2 markdown typst
```

### 2. Exécution du test de démonstration

```bash
python test_cv_engine.py
```

Cela produit :
- `cv_output.typ` : Code source Typst généré.
- `cv_output.pdf` : Fichier PDF compilé et prêt à l'emploi.

---

## 💡 Exemple d'intégration Python

```python
from backend.renderer import render_cv
from backend.compiler import compile_typst_to_pdf

# 1. Données du CV (générées par IA ou saisies par l'utilisateur)
cv_data = {
    "name": "Jean Dupont",
    "headline": "Développeur Full Stack",
    "email": "jean@example.com",
    "location": "Paris, France",
    "sections": {
        "experience": [
            {
                "company": "Tech Corp",
                "position": "Lead Developer",
                "start_date": "2021-01",
                "end_date": "present",
                "highlights": [
                    "Gestion d'une équipe de 5 personnes",
                    "Développement d'APIs sous FastAPI et Node.js"
                ]
            }
        ]
    }
}

# 2. Rendu Typst (support de la langue "fr", auto-bolding des compétences clés)
typst_source = render_cv(
    cv_data,
    locale="fr",
    bold_keywords=["FastAPI", "Node.js"]
)

# 3. Compilation en PDF
pdf_bytes = compile_typst_to_pdf(typst_source, output_path="cv.pdf")
```

---

## 🎯 Fonctionnalités clés extraites

- **Design System Paramétrique** : Supporte 8 styles de titres de section, espacements configurables, polices Google Fonts.
- **Auto-nettoyage des placeholders** : Si un champ optionnel (ex: `company` ou `location`) est manquant, le moteur supprime automatiquement les connecteurs inutiles ("at", "in") et la ponctuation superflue.
- **Multilingue (i18n)** : Support natif du Français (`fr`) et de l'Anglais (`en`) pour les mois, durées ("3 ans 2 mois") et libellés.
- **Auto-bolding** : Met automatiquement en gras les compétences clés spécifiées dans tout le CV.
- **Zero-network PDF compilation** : Génération ultra-rapide en mémoire sans dépendance réseau.
