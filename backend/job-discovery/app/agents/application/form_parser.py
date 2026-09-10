"""
Lecture d'un formulaire de candidature — niveau déterministe.

Ce module ne décide de rien et n'appelle aucun modèle. Il lit la page et rend,
pour chaque champ, tout ce que le HTML dit de lui : son type natif, ses
identifiants, son libellé, ce qu'il accepte, et — pour les listes — les options
réellement proposées.

C'est volontairement séparé de la classification. Un extracteur qui déciderait
en même temps qu'il lit rendrait indémêlables deux erreurs très différentes :
« je n'ai pas vu le champ » et « je n'ai pas compris à quoi il sert ».

Les libellés sont cherchés dans l'ordre de fiabilité décroissante : un
`<label for>` explicite vaut mieux qu'un `aria-label`, qui vaut mieux qu'un
`placeholder`, qui vaut mieux que le texte trouvé autour du champ.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class FormField:
    """Un champ tel que la page le décrit, avant toute interprétation."""

    #: Sélecteur utilisable pour retrouver le champ. Toujours renseigné.
    selector: str
    #: `input` | `textarea` | `select`
    tag: str
    #: Type natif (`text`, `email`, `tel`, `file`, `checkbox`…) ou `""`.
    input_type: str = ""
    name: str = ""
    element_id: str = ""
    label: str = ""
    placeholder: str = ""
    aria_label: str = ""
    autocomplete: str = ""
    #: Extensions acceptées par un champ fichier (`.pdf,.doc`).
    accept: str = ""
    required: bool = False
    #: Vrai pour un `<select>` ou un `role="combobox"`.
    is_choice: bool = False
    #: Libellés des options proposées, quand il y en a.
    options: list[str] = field(default_factory=list)
    #: Pour un groupe de boutons radio, le sélecteur de chaque bouton. Une
    #: question rendue en cinq boutons reste une question : c'est ici qu'on
    #: garde de quoi cliquer le bon.
    group_selectors: list[str] = field(default_factory=list)
    #: Comment la liste se comporte à l'ouverture, une fois éprouvée sur page
    #: vivante : `enumerable` (elle montre ses options), `recherche` (elle
    #: n'en montre qu'à la frappe), `inerte` (rien ne s'ouvre), ou `""` quand
    #: la question n'a pas été posée. Renseigné par `form_reader`, jamais ici :
    #: la lecture statique ne peut pas le savoir.
    choice_mode: str = ""

    @property
    def signals(self) -> str:
        """
        Tout ce qui décrit le champ, en un seul texte minuscule.

        La classification travaille dessus plutôt que sur chaque attribut
        séparément : un formulaire met l'intitulé tantôt dans le `name`,
        tantôt dans le `placeholder`, tantôt nulle part ailleurs que dans le
        libellé visible.
        """
        return " ".join(
            s for s in (
                self.label, self.aria_label, self.placeholder,
                self.name, self.element_id, self.autocomplete,
            ) if s
        ).lower()


# Extraction faite en une seule évaluation JavaScript : un aller-retour par
# champ multiplierait la latence sur un formulaire de vingt entrées.
#
# Quatre règles y ont été ajoutées après mesure sur un corpus de 109 pages
# gelées, chacune corrigeant une cécité constatée :
#   · un champ sans `id` ni `name` reste adressable, au lieu d'être sauté ;
#   · la visibilité se teste sur l'élément ET ses ancêtres ;
#   · un groupe de boutons radio est UNE question, pas cinq champs ;
#   · le champ fantôme des listes React est écarté, pas compté.
# Chaîne brute : le JavaScript contient ses propres échappements (`\n`, `\b`,
# `\*`). Sans le préfixe `r`, Python les consommerait — `\b` deviendrait un
# retour arrière et la détection du caractère obligatoire cesserait de marcher.
_EXTRACT_JS = r"""
() => {
  let compteur = 0;

  // Un champ sans `id` ni `name` reste adressable : on lui pose une marque.
  // Sans ça, `selectorOf` rendait '' et le champ était sauté en silence —
  // 7 champs obligatoires disparaissaient ainsi sur une page boards.eu.
  const marquer = el => {
    if (el.id) return '#' + CSS.escape(el.id);
    if (el.name) return el.tagName.toLowerCase() + '[name="' + CSS.escape(el.name) + '"]';
    if (!el.dataset.ufMarque) el.dataset.ufMarque = 'uf' + (++compteur);
    return '[data-uf-marque="' + el.dataset.ufMarque + '"]';
  };

  // `getComputedStyle(el).display` ne vaut pas 'none' quand c'est un ANCÊTRE
  // qui est masqué : display ne s'hérite pas. L'ancien test laissait donc
  // passer les champs des sections repliées.
  const visible = el => {
    if (el.type === 'file') return true;  // souvent caché derrière un bouton stylisé
    if (el.checkVisibility) return el.checkVisibility();
    return el.getClientRects().length > 0;
  };

  const texteDe = el => (el ? (el.innerText || '').trim() : '');

  const obligatoire = el => {
    if (el.required || el.getAttribute('aria-required') === 'true') return true;
    // L'astérisque du libellé est un marqueur d'obligation aussi répandu que
    // l'attribut, et souvent le seul présent sur les formulaires React.
    const bloc = el.closest('label, div, fieldset, li');
    if (!bloc) return false;
    const etiquette = bloc.querySelector('label, legend');
    const premier = texteDe(etiquette || bloc).split('\n')[0];
    return /\*\s*$|\*\s*\(|\brequired\b|\bobligatoire\b/i.test(premier);
  };

  // `aria-labelledby` est la façon normalisée d'attacher une question à un
  // composant qui n'est pas un <input> ordinaire. Les listes React s'en
  // servent presque toujours, et on ne la consultait pas du tout.
  const parLabelledby = el => {
    const ids = (el.getAttribute('aria-labelledby') || '').split(/\s+/).filter(Boolean);
    const morceaux = ids.map(id => texteDe(document.getElementById(id))).filter(Boolean);
    return morceaux.join(' ').trim();
  };

  const libelleDe = el => {
    if (el.id) {
      const l = document.querySelector('label[for="' + CSS.escape(el.id) + '"]');
      if (texteDe(l)) return texteDe(l);
    }
    const parAria = parLabelledby(el);
    if (parAria) return parAria;

    const enveloppe = el.closest('label');
    if (texteDe(enveloppe)) return texteDe(enveloppe);

    const bloc = el.closest('div, fieldset, li');
    if (bloc) {
      // Le texte du bloc contient aussi celui du composant lui-même : pour une
      // liste React, « Select... » arrive AVANT la question et était pris pour
      // elle — 64 champs obligatoires classés inconnus pour cette seule raison.
      // On retire donc ce que le contrôle affiche, et on garde la première
      // ligne de ce qui reste.
      const sien = new Set([
        texteDe(el), el.placeholder || '', el.value || '',
        ...Array.from(bloc.querySelectorAll('[role=option], option')).map(texteDe),
      ].filter(Boolean).map(s => s.toLowerCase()));

      for (const ligne of texteDe(bloc).split('\n').map(s => s.trim()).filter(Boolean)) {
        const nu = ligne.replace(/\s*\*$/, '').toLowerCase();
        if (sien.has(nu) || sien.has(ligne.toLowerCase())) continue;
        if (ligne.length < 160) return ligne;
      }
    }
    return '';
  };

  // Le plus petit ancêtre qui contient tout le groupe : c'est là que se trouve
  // la question, alors que chaque bouton ne porte que son option.
  const ancetreCommun = elements => {
    let noeud = elements[0];
    while (noeud && !elements.every(e => noeud.contains(e))) noeud = noeud.parentElement;
    return noeud;
  };

  const libelleDeGroupe = (elements, options) => {
    const intitules = new Set(options.map(o => o.toLowerCase().replace(/\s*\*$/, '')));
    // L'ancêtre commun ne contient parfois QUE les options — c'est le cas des
    // douze cases « pronouns » de Lever, empilées dans une grille dont aucun
    // niveau ne porte la question. On remonte donc jusqu'à trouver un texte
    // qui ne soit pas l'intitulé d'une option, sans jamais sortir du
    // formulaire : au-delà, on ramasserait le titre de la page.
    let racine = ancetreCommun(elements);
    for (let i = 0; i < 5 && racine && !['FORM', 'BODY'].includes(racine.tagName); i++) {
      const legende = racine.querySelector('legend');
      if (texteDe(legende)) return texteDe(legende);
      for (const ligne of texteDe(racine).split('\n').map(s => s.trim()).filter(Boolean)) {
        const nu = ligne.toLowerCase().replace(/\s*\*$/, '');
        if (!intitules.has(nu) && ligne.length < 200) return ligne;
      }
      racine = racine.parentElement;
    }
    return '';
  };

  const optionsDansPanneau = panneau =>
    Array.from(panneau.querySelectorAll('[role="option"]'))
         .map(o => texteDe(o)).filter(Boolean).slice(0, 400);

  const optionsDe = el => {
    if (el.tagName === 'SELECT') {
      return Array.from(el.options).map(o => o.label || o.text).filter(Boolean);
    }
    if ((el.getAttribute('role') || '') !== 'combobox') return [];

    // Le lien déclaré est la seule preuve d'appartenance qui vaille.
    const lie = el.getAttribute('aria-controls') || el.getAttribute('aria-owns');
    const declare = lie ? document.getElementById(lie) : null;
    if (declare) return optionsDansPanneau(declare);

    // À défaut, on cherche le panneau DANS le composant, sur trois niveaux
    // au plus. Jamais dans le document entier : l'ancienne version le faisait
    // et ramassait les options du premier panneau ouvert venu — mesuré, 88 %
    // des listes se voyaient attribuer la liste des indicatifs téléphoniques,
    // « Diplôme » proposant « Afghanistan+93 ».
    let boite = el.parentElement;
    for (let i = 0; i < 3 && boite; i++, boite = boite.parentElement) {
      const local = boite.querySelector('[role="listbox"]');
      if (local && !local.contains(el)) return optionsDansPanneau(local);
    }

    // Une liste fermée ne montre pas ses options : elles n'existent pas encore
    // dans le DOM. Ne rien rendre est exact ; rendre celles du voisin ne
    // l'est pas. C'est à l'étage d'interaction d'ouvrir la liste pour voir.
    return [];
  };

  // Les bibliothèques de listes déroulantes doublent leur composant d'un
  // champ fantôme, sans `id` ni `name`, dont le seul rôle est de déclencher la
  // validation native du navigateur — `remix-css-…-requiredInput` chez
  // react-select. Ce n'est pas une question : c'est le mécanisme de celle
  // d'à côté. Le compter en ferait un champ obligatoire perpétuellement
  // incompris.
  const estFantome = el => {
    if (el.id || el.name) return false;
    const bloc = el.closest('div, fieldset, li, label');
    if (!bloc) return false;
    return Array.from(bloc.querySelectorAll('input, textarea, select'))
                .some(x => x !== el && x.type !== 'hidden' && (x.id || x.name));
  };

  const sortie = [];
  const groupes = new Map();   // clé de groupe → boutons radio

  for (const el of document.querySelectorAll('input, textarea, select')) {
    if (['hidden', 'submit', 'button', 'reset', 'image'].includes(el.type)) continue;
    if (!visible(el)) continue;
    if (estFantome(el)) continue;

    // Un groupe de radios est UNE question, pas cinq champs. L'extracteur les
    // rendait un par un, avec l'intitulé de l'option pris pour la question :
    // 13 radios Ashby au lieu de 4 questions.
    if (el.type === 'radio' || el.type === 'checkbox') {
      // Une case seule est une question (« j'accepte les conditions ») ; un
      // paquet de cases qui partagent un nom est UNE question à choix
      // multiple. On ne peut trancher qu'après avoir tout vu : on met de côté
      // et on décide plus bas.
      const cle = el.type + ':' + (el.name || '#' + (el.id || Math.random()));
      if (!groupes.has(cle)) groupes.set(cle, []);
      groupes.get(cle).push(el);
      continue;
    }

    sortie.push({
      selector: marquer(el),
      tag: el.tagName.toLowerCase(),
      input_type: el.type || '',
      name: el.name || '',
      element_id: el.id || '',
      label: libelleDe(el),
      placeholder: el.placeholder || '',
      aria_label: el.getAttribute('aria-label') || '',
      autocomplete: el.getAttribute('autocomplete') || '',
      accept: el.getAttribute('accept') || '',
      required: obligatoire(el),
      is_choice: el.tagName === 'SELECT' || (el.getAttribute('role') || '') === 'combobox',
      options: optionsDe(el),
      group_selectors: [],
    });
  }

  for (const [cle, boutons] of groupes) {
    // Une case à cocher isolée n'est pas un choix : c'est un engagement, et
    // son libellé EST la question. La rendre comme groupe la priverait du
    // sien.
    if (boutons.length === 1 && boutons[0].type === 'checkbox') {
      const el = boutons[0];
      sortie.push({
        selector: marquer(el), tag: 'input', input_type: 'checkbox',
        name: el.name || '', element_id: el.id || '', label: libelleDe(el),
        placeholder: '', aria_label: el.getAttribute('aria-label') || '',
        autocomplete: '', accept: '', required: obligatoire(el),
        is_choice: false, options: [], group_selectors: [],
      });
      continue;
    }
    const options = boutons.map(b => libelleDe(b) || b.value).filter(Boolean);
    sortie.push({
      selector: marquer(boutons[0]),
      tag: 'radiogroup',
      input_type: boutons[0].type,
      name: boutons[0].name || '',
      element_id: '',
      label: libelleDeGroupe(boutons, options),
      placeholder: '', aria_label: '', autocomplete: '', accept: '',
      required: boutons.some(obligatoire),
      is_choice: true,
      options: options,
      group_selectors: boutons.map(marquer),
    });
  }

  return sortie;
}
"""


async def extract_fields(page) -> list[FormField]:
    """Lit tous les champs exploitables de la page."""
    try:
        raw: list[dict[str, Any]] = await page.evaluate(_EXTRACT_JS)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Extraction du formulaire impossible : %s", exc)
        return []

    fields = [FormField(**item) for item in raw]

    # Un libellé repris du bloc parent contient souvent l'astérisque et la
    # mention d'obligation ; on la retient plutôt que de la jeter.
    for f in fields:
        if not f.required and f.label.rstrip().endswith("*"):
            f.required = True
        f.label = f.label.rstrip(" *").strip()

    logger.info("Formulaire lu : %d champs, dont %d obligatoires",
                len(fields), sum(1 for f in fields if f.required))
    return fields
