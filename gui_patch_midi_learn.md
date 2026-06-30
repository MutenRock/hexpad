# Patch midi-learn — instructions d'intégration dans gui.py

Ce fichier documente les changements à apporter à `gui.py` pour brancher
`LearnButton` dans le Mapping Editor. Le patch est appliqué manuellement
pour ne pas réécrire entièrement le fichier de 800+ lignes.

## 1. Import à ajouter (en tête de gui.py, après les imports existants)

```python
from modules.midi_learn_widget import LearnButton, LearnSession
```

## 2. Dans `__init__` (après `self.combo_engine = ComboEngine()`)

```python
self._learn_session = LearnSession()  # partagée entre tous les LearnButtons
```

## 3. Dans `_build_mapping_editor` — remplacer `self._me_pad_vars` init par :

```python
self._me_pad_vars     = {}
self._me_pad_sub_vars = {}
self._me_learn_session = LearnSession()  # session locale à l'éditeur
```

## 4. Dans `_me_build_pad_grid` — ajouter le bouton Learn par pad

Dans la boucle qui construit chaque ligne de pad, après le Combobox action,
ajouter :

```python
learn_btn = LearnButton(
    parent     = row,
    device_fn  = lambda: self.device_var.get(),
    on_learned = lambda kind, num, ns=note_str: self._me_on_learn(ns, kind, num),
    theme      = self.C,
    accept     = ("note",),
    session    = self._me_learn_session,
)
learn_btn.pack(side="left", padx=2)
```

## 5. Ajouter la méthode `_me_on_learn` dans HexPadGUI

```python
def _me_on_learn(self, old_note_str: str, kind: str, number: int):
    """Callback quand le MidiLearn détecte un pad/knob."""
    preset = self._get_me_preset()
    if preset is None:
        return
    pads = preset.setdefault("pads", {})
    # Déplacer le mapping existant vers la nouvelle note
    if old_note_str in pads:
        pads[str(number)] = pads.pop(old_note_str)
    self._log(f"[LEARN] {kind} {number} → remplace pad {old_note_str}")
    self._me_build_pad_grid()
    self._me_save_indicator.config(text="● modifié")
```

## 6. Dans `_me_build_knob_row` — ajouter Learn CC par knob

Après le Combobox action du knob, ajouter :

```python
learn_btn = LearnButton(
    parent     = row,
    device_fn  = lambda: self.device_var.get(),
    on_learned = lambda kind, num, cc=cc_num: self._me_on_learn_cc(cc, kind, num),
    theme      = self.C,
    accept     = ("cc",),
    session    = self._me_learn_session,
)
learn_btn.pack(side="left", padx=2)
```

## 7. Ajouter `_me_on_learn_cc`

```python
def _me_on_learn_cc(self, old_cc: int, kind: str, number: int):
    preset = self._get_me_preset()
    if preset is None:
        return
    knobs = preset.setdefault("knobs", {})
    old_key = str(old_cc)
    if old_key in knobs:
        knobs[str(number)] = knobs.pop(old_key)
    self._log(f"[LEARN CC] cc {number} → remplace knob {old_cc}")
    self._me_build_knob_rows()
    self._me_save_indicator.config(text="● modifié")
```

## Note

Le `_learn_target` natif dans `_start_monitor` reste inchangé — il gère
uniquement le flash visuel du PAD MONITOR dans l'onglet RUN.
Le nouveau `LearnButton` est indépendant et opère uniquement dans le
Mapping Editor (Toplevel dédié).
