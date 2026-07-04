# Brainstorm — SPICE Model Coverage and Sanity Harness

**Date** : 2026-07-04
**Repo** : kicad-skill
**Mode** : Team (`/octo:brainstorm`) — 🔴 Codex + 🔵 Claude.
**Gemini** indisponible cette session : `IneligibleTierError` (le tier gratuit
"Gemini Code Assist for individuals" n'est plus supporté ; migration vers
Antigravity requise côté compte Google — hors de portée de l'assistant).
Le mode Team ne requiert qu'au moins 2 providers, donc la session a continué
avec Codex + Claude.

## Contexte de départ

Question initiale : comment valider les schémas/PCB KiCad via simulation ?
KiCad n'a pas de simulation native au niveau PCB (SI/EMI/thermique) — l'ERC/DRC
sont des vérifications de règles, pas des simulations. Le seul levier de
simulation réel est ngspice au niveau schématique (OP, DC sweep, AC,
transitoire, bruit).

Le repo a déjà un système d'invariants mature dans `kicad-autopilot.md`
(KICAD-01 à KICAD-14), notamment :

- **KICAD-05** — tout sous-circuit à risque électrique doit avoir des types
  d'analyse nommés explicitement (DC/point de fonctionnement, AC/petit-signal
  pour la stabilité de boucle, transitoire, thermique,
  worst-case/tolérance), chacun avec un statut (`done` / `NOT DONE` / `not
  applicable`) et, si SPICE est utilisé, une **note de confiance du modèle**
  (high/medium/low) — "simulé" n'est jamais un état de confiance terminal.
- **KICAD-06** — aucune commande de fabrication/assemblage sans confirmation
  explicite.
- **KICAD-07** — aucun sous-circuit généré sans guide de conception
  correspondant dans `resources/` ; si absent : STOP, jamais d'improvisation,
  co-écrire le guide avant de continuer.
- **KICAD-08** — ERC/DRC propres et netlist/empreintes cohérents avant export
  fab.
- **KICAD-09** — statut de cycle de vie du composant (actif/NRND/EOL) et flag
  source unique requis.

Le "SIM-01" évoqué en tout début de brainstorm a été abandonné comme nom
d'invariant : ce qui suit est un outil concret qui *implémente* KICAD-05 (la
note de confiance modèle) à un grain plus fin (par composant, pas seulement
par catégorie de sous-circuit) et une instance particulière de KICAD-07
(jamais improviser sans guide).

Convention déjà en place dans le repo (héritée de `cad-skill`) : séparation
stricte entre **méthode générique + guides de conception**, versionnés et
réutilisables (`resources/`), et **données spécifiques au projet**
(caractéristiques, dimensions, composants réels), qui vivent dans le projet
consommateur, pas dans le skill.

## Perspectives multi-IA

**🔴 Codex** a proposé le jalon "Harnais de couverture SPICE" comme premier
livrable concret : un outil qui scanne un schéma KiCad, détermine le rôle
fonctionnel de chaque composant actif, génère un smoke-test ngspice par
composant, l'exécute, et classe chaque composant.

**🔵 Claude** a structuré la discussion en questions à choix forcé
successives (voir "Décisions de conception" ci-dessous) et a assuré la
cohérence avec les invariants KICAD déjà existants ainsi que la correction
architecturale sur le hook Git (voir plus bas).

## Décisions de conception (verrouillées)

1. **Diagnostic + smoke-test exécuté** (pas seulement diagnostic statique) —
   le harnais génère et exécute réellement un test ngspice minimal par
   composant, pas seulement une analyse de cohérence de schéma.
2. **Binding de rôle via registre MPN** (pas une heuristique sur le nom du
   symbole KiCad, ni un tag manuel dans une fiche technique) — le rôle
   fonctionnel de chaque composant est déterminé via une clé MPN dans un
   registre dédié du skill.
3. **Population pure réactive du registre** (miroir de KICAD-07) — le
   registre démarre vide ; rencontrer un MPN inconnu bloque uniquement le
   smoke-test de ce composant et force la co-écriture d'une entrée de
   registre avant de continuer. Jamais de pré-remplissage ou d'improvisation.
4. **Blocage local, pas global** — une entrée de registre manquante bloque
   uniquement le smoke-test du composant concerné ; l'ERC/DRC, les
   vérifications structurelles et les smoke-tests des autres composants déjà
   enregistrés continuent indépendamment. Le rapport final mélange résultats
   verts et lacunes explicites.
5. **Pattern "never trust the client"** pour l'automatisation CI/hook :
   - Un hook Git local **pre-push** vérifie que le rapport de couverture est
     tout vert avant de pousser — *best-effort*, contournable
     (`--no-verify`, suppression du hook, édition locale).
   - Une **GitHub Action** ne peut pas vérifier que les hooks locaux n'ont
     pas été trafiqués (`.git/hooks/` n'est pas versionné, la CI n'a aucune
     visibilité sur ce qui a tourné sur la machine du développeur, sauf à
     utiliser `core.hooksPath` pointant vers un dossier versionné façon
     Husky — non retenu ici). La correction validée par l'utilisateur : la
     GitHub Action ne tente pas de vérifier l'intégrité du hook, elle
     **ré-exécute indépendamment le même contrôle de couverture** et en est
     la seule autorité. Le hook local n'est qu'un confort, jamais une
     garantie.

## Design concret

### Registre MPN — `resources/mpn-registry/<role>/<mpn_base>.yaml`

Schéma réconcilié (issu de la fusion des deux designs produits en parallèle
par deux forks — voir "Réconciliation" ci-dessous) :

```yaml
mpn_base: "LM2596"          # préfixe MPN générique, sans suffixe de boîtier/tri
role: "buck_regulator"       # doit correspondre à un dossier resources/spice-smoke-templates/<role>.yaml
lifecycle_status: "active"   # active | nrnd | eol (KICAD-09)
single_source: false         # KICAD-09
spice_model:
  source: "vendor" | "generic" | "none"
  path: "models/lm2596.lib"  # si applicable
  subckt_name: "LM2596"
pins:
  # mapping nom-de-pin -> rôle fonctionnel, utilisé pour générer la netlist
  vin: 1
  gnd: 2
  vout: 3
  fb: 4
  en: 5
datasheet_rules:
  input_cap:
    min_uf: 100
    voltage_derating: 0.8
  inductor:
    range_uh: [33, 100]
  output_cap:
    min_uf: 100
output_adjustable: true      # true = la tension de sortie dépend du câblage
                              # projet (pont diviseur, Vref) -> ces valeurs ne
                              # sont PAS génériques, elles viennent de la
                              # fiche projet, jamais du registre.
model_confidence: "medium"   # high | medium | low — alimente KICAD-05
notes: "..."
```

### Smoke-test — `resources/spice-smoke-templates/<role>.yaml`

> **Superseded by Round 2** : la classification `syntax_error` /
> `pin_mismatch` / `convergence_risk` / `missing` / `usable` ci-dessous est
> l'état de la réflexion au round 1. Le round 2 (plus bas) la reformalise en
> 7 états au niveau du harnais, dont seuls `passed`/`failed` (+ un `detail`
> de raison) sont produits à l'exécution — `missing` est remplacé par
> `blocked_missing_spec`, décidé en amont à la résolution, jamais à
> l'exécution. Voir `resources/spice-smoke-templates/_template.md` pour le
> schéma final.

Un template par rôle fonctionnel, avec netlist à trous et logique de
classification (version round 1, conservée pour l'historique) :

```yaml
role: "buck_regulator"
netlist_template: |
  * smoke test {{mpn_base}}
  .include {{resolved.spice_model_path}}
  Vin vin 0 {{resolved.nominal_vin}}
  Cin vin 0 {{resolved.input_cap_min}}u
  Xreg vin gnd vout fb en {{resolved.subckt_name}}
  L1 vout sw {{resolved.inductor_mid}}u
  Cout vout 0 {{resolved.output_cap_min}}u
  Rfb1 vout fb_node {{resolved.fb_divider_r1}}
  Rfb2 fb_node 0 {{resolved.fb_divider_r2}}
  .op
  .end
classification:
  - condition: "netlist ne parse pas"
    result: "syntax_error"
  - condition: "nombre de pins connectées != nombre de pins attendues du rôle"
    result: "pin_mismatch"
  - condition: "ngspice ne converge pas (.op échoue)"
    result: "convergence_risk"
  - condition: "champ resolved.* requis absent (ex: fb_divider si output_adjustable
    et pas de fiche projet)"
    result: "missing"
    reason: "explicite, ex: 'fiche projet incomplète : pont diviseur de
    feedback non fourni'"
  - condition: "sinon"
    result: "usable"
```

### Résolution registre + fiche projet → `resolved.*`

Point de réconciliation clé : les deux designs produits en parallèle par les
deux forks utilisaient des noms de champs différents (chemins imbriqués côté
registre — `datasheet_rules.input_cap.min_uf`, `feedback.voltage_v`,
`inductor.range_uh` — contre des noms plats côté template —
`registry.input_cap_min`, `registry.inductor_range.mid`,
`registry.fb_divider_r1`/`r2`, `registry.nominal_vin`). Ces deux derniers
champs (`fb_divider_r1/r2`, `nominal_vin`) n'existaient même pas dans le
schéma du registre, et le template les défaultait silencieusement
(`| default(10k)`) plutôt que de les signaler manquants — un vrai risque de
"fausse confiance" (green-checkmark trap).

Fix retenu : une étape de **résolution** dans le harnais fusionne
registre (générique) + fiche projet (spécifique, requise uniquement si
`output_adjustable: true`) en un dictionnaire plat `resolved.*` consommé par
les templates. Si `output_adjustable` et que la fiche projet ne fournit pas
le pont diviseur / la tension nominale, le composant est classé `missing`
avec une raison explicite — jamais de valeur par défaut arbitraire.

## Round 2 — architecture d'exécution (2026-07-04, suite)

Mode Team — 🔴 Codex + 🔵 Claude + 2 forks Claude par sous-question (Gemini de
nouveau indisponible : `IneligibleTierError`, inchangé). Ce round tranche les
4 points laissés ouverts au round 1.

### D tranché : CLI Python déterministe

Le harnais **n'est pas** une procédure manuelle pilotée par agent MCP — c'est
un outil scripté déterministe (CLI Python), condition nécessaire pour que la
décision 5 (GitHub Action = autorité, ré-exécute indépendamment le contrôle)
ait un sens : une CI ne peut pas re-exécuter une procédure manuelle pilotée
par LLM. MCP KiCad reste utile en amont (production d'un manifest de
composants) mais jamais comme dépendance de la CI.

Architecture à 3 étages :
1. **Ingestion** (kicad-cli natif OU manifest MCP) → `component_inventory.yaml`
   canonique
2. **Résolution** (inventaire + registre MPN + fiche projet) → `resolved.*`
   par composant
3. **Exécution** (resolved.* + template smoke-test) → run ngspice →
   classification

### Étage 1 — `component_inventory.yaml`

Format canonique unique produit par deux adaptateurs interchangeables, pour
que la résolution (étage 2) ne sache jamais d'où vient l'inventaire :

```yaml
schema_version: 1
components:
  - ref: "U3"                 # désignateur KiCad, clé unique
    source: "kicad_cli"       # kicad_cli | mcp_manifest — traçabilité/debug
    mpn: "LM2596S-5.0"        # MPN brut extrait, ou null
    mpn_status: "present"     # present | missing | ambiguous
    raw_mpn_candidates: []    # si ambiguous : valeurs concurrentes trouvées
    footprint: "Package_TO_SOT_SMD:TO-263-5_TabPin3"
    value: "LM2596S-5.0"      # champ Value KiCad brut
    fitted: true              # false = DNP, exclu du smoke-test mais listé
    role_hint: "buck_regulator"          # optionnel, jamais autoritaire
    role_hint_source: "symbol_property"  # symbol_property | footprint_heuristic
                                          # | mcp_agent | none
    sheet_path: "/power/buck1"
```

- **`from_kicad_cli()`** : utilise `kicad-cli sch export netlist --format
  kicadxml`, jamais `... export bom`.
  > **Correction apportée à l'implémentation (vérifiée empiriquement)** :
  > `--group-by` de `export bom` ne force pas un rendu un-composant-par-ligne
  > de façon fiable (des composants aux `Reference` différentes mais dont
  > les autres champs affichés sont identiques restent fusionnés, même en
  > incluant `Reference` dans `--group-by`) — confirmé en testant contre de
  > vrais projets KiCad. `export netlist --format kicadxml` donne toujours
  > un élément `<comp>` par composant, jamais agrégé.
  >
  > Le MPN vient d'un champ symbole nommé exactement `MPN`. **La détection
  > `ambiguous` via un champ concurrent (ex. `Manufacturer_PN`) a été
  > abandonnée** après test contre un vrai projet KiCad peuplé (démo
  > `tiny_tapeout` de KiCad 9) : des champs adjacents au MPN (`MPN_ALT`,
  > `DigikeyPN`, `JLC`) y coexistent couramment avec `MPN` et sont des
  > métadonnées légitimes et distinctes (pièce de seconde source, référence
  > distributeur) — jamais une revendication concurrente sur le même MPN.
  > `from_kicad_cli()` ne produit donc jamais `ambiguous`, seulement
  > `present`/`missing`. `ambiguous` reste dans le schéma canonique pour un
  > futur chemin d'ingestion qui pourrait réellement se contredire (ex.
  > fusion de deux sources indépendantes) — une seule extraction de
  > schéma ne peut pas produire ce cas.
- **`from_mcp_manifest()`** : mapping direct depuis le manifest produit par
  l'agent MCP, `role_hint_source: mcp_agent` pour distinguer un jugement
  agent d'une heuristique mécanique. Non vérifié contre un vrai serveur MCP
  KiCad (aucun disponible pendant l'implémentation), contrairement à
  `from_kicad_cli()` testé contre de vrais projets KiCad (kicad-cli 9.0.2).
- Composant générique sans MPN (résistance nue) : `mpn_status: missing`,
  `value` renseigné — jamais de MPN inventé.
- `role_hint` n'est jamais consommé comme donnée de vérité par l'exécution ;
  seul le champ `role` de l'entrée registre (étage 2) fait foi.

### Étage 2 — résolution

Séquence par composant `fitted: true` (les `fitted: false` sont classés
`not_fitted` avant d'entrer dans cette étape) :

1. `mpn_status` = `missing`/`ambiguous` → `blocked_missing_registry`, arrêt.
2. Normaliser `mpn` → `mpn_base_normalized` : `strip().upper()`, troncature au
   premier `/` (couvre `LM2596S-5.0/NOPB` → `LM2596S-5.0`), puis suffixes
   connus retirés via une table explicite
   `resources/mpn-registry/_normalization-rules.yaml`. **Pas de fuzzy
   matching** — égalité de chaîne stricte contre le `mpn_base` déclaré en
   registre. Zéro match → bloc de co-écriture affichant `raw_mpn` et
   `mpn_base_normalized` côte à côte.
3. Recherche exacte dans `resources/mpn-registry/*/<mpn_base>.yaml`, tous
   rôles confondus (le `role_hint` n'oriente jamais la recherche). Plusieurs
   matches sous des rôles différents → `blocked_missing_registry` avec raison
   "conflit de registre".
4. Un seul match → `role` = champ `role` de l'entrée (jamais `role_hint`).
   Chercher `resources/spice-smoke-templates/<role>.yaml`. Absent →
   `blocked_missing_template`.
5. Si `output_adjustable: true` → chercher dans la fiche projet un bloc
   `components.<ref>` (keyé par `ref`, pas par `role` — un projet peut avoir
   plusieurs régulateurs ajustables) listant les champs déclarés requis par
   `project_specific_fields` du smoke-test template du rôle. Absent/incomplet
   → **`blocked_missing_spec`** (nouvel état, distinct de
   `blocked_missing_registry`/`blocked_missing_template` : le responsable du
   fix est le projet consommateur, pas le skill).
6. Fusion registre (+ fiche projet si applicable) → `resolved.*`.

> **Correction apportée pendant l'implémentation** : `datasheet_rules` (ex.
> `inductor.range_uh: [33, 100]`) reste purement informatif/humain — le
> harnais ne dérive jamais mécaniquement une valeur "représentative" d'une
> plage (choisir un point dans une plage est un jugement d'ingénierie, pas
> une dérivation mécanique fiable, cf. KICAD-01 "jamais de dérivation
> silencieuse"). Le registre porte un champ explicite `smoke_test_values`
> (valeurs exactes choisies par l'auteur, copiées verbatim dans
> `resolved.*`) — voir `resources/mpn-registry/_template.md`.

Schéma `resolved.*` (noms alignés strictement sur le template smoke-test —
aucun nom divergent, contrairement au round 1) :

```yaml
resolved:
  ref: "U3"
  mpn_base: "LM2596"
  role: "buck_regulator"
  registry_path: "resources/mpn-registry/buck_regulator/LM2596.yaml"
  lifecycle_status: "active"
  single_source: false
  model_confidence: "medium"
  spice_model_path: "models/lm2596.lib"
  subckt_name: "LM2596"
  pins: {vin: 1, gnd: 2, vout: 3, fb: 4, en: 5}
  input_cap_min: 100
  inductor_mid: 66.5
  output_cap_min: 100
  output_adjustable: true
  nominal_vin: 12.0
  fb_divider_r1: 4700
  fb_divider_r2: 1000
  smoke_template_path: "resources/spice-smoke-templates/buck_regulator.yaml"
```

Cas `spice_model.source: "none"` (ex. connecteur sans modèle SPICE
pertinent) → état terminal dédié **`not_applicable`** à l'étage 3, pas une
erreur de résolution.

### Classification finale : 7 états

`passed`, `failed`, `blocked_missing_registry`, `blocked_missing_template`,
`blocked_missing_spec`, `not_fitted`, `not_applicable`. Chaque état
`blocked_*`/`not_fitted`/`not_applicable` a un responsable de fix distinct
(skill vs projet vs non-applicable) — les mélanger masquerait qui doit agir.

### Étage 3 — rapport final

**JSON canonique + Markdown généré** (jamais l'inverse — évite le drift déjà
rencontré entre schémas indépendants). Le hook et la CI ne lisent que le
JSON ; un humain lit le Markdown.

```json
{
  "schema_version": 1,
  "generated_at": "2026-07-04T12:34:56Z",
  "mode": "local",
  "git_ref": "abc1234",
  "summary": {
    "total": 42, "passed": 30, "failed": 2,
    "blocked_missing_registry": 5, "blocked_missing_template": 1,
    "blocked_missing_spec": 0, "not_fitted": 4, "not_applicable": 0,
    "waived": 3, "blocking_ci": 3
  },
  "exit_code": 1,
  "components": [
    {
      "ref": "U3", "mpn": "LM2596S-5.0", "role": "buck_regulator",
      "state": "blocked_missing_registry",
      "waived": false, "waiver": null,
      "expected_registry_path": "resources/mpn-registry/buck_regulator/lm2596s-5_0.yaml",
      "detail": "MPN inconnu du registre — co-écriture requise avant smoke-test.",
      "ngspice_log_path": null
    }
  ]
}
```

`summary.blocking_ci` = `failed` + `blocked_*` non-waivés — c'est le **seul**
compteur qui gouverne le code de sortie (jamais `blocked` brut, qui
mélangerait bloquant réel et couvert par waiver actif).

**Politique CI — waivers versionnés, stricte par défaut :**
- `failed` fait toujours échouer la CI.
- `blocked_*` fait échouer la CI **sauf** listé dans
  `spice-coverage-waivers.yaml` (committé au repo projet ; champs :
  `mpn_base`, `state`, `reason`, `added`, `expires`).
- `exit 0` ssi `blocking_ci == 0`, identique en mode `local` (hook) et `ci`
  (GitHub Action) — pas de permissivité supplémentaire côté hook, cohérent
  avec la décision 5 (single source of truth). Cas 100% waivé : `exit 0`,
  mais bandeau `WARNING` toujours imprimé (jamais silencieux). Waiver expiré
  → repasse automatiquement bloquant (`waiver_expired: true`), le rouge CI
  reste auto-explicable sans changement de code.
- Pas d'historique custom : la GitHub Action diffe le rapport courant contre
  celui de la branche de base (artefact/cache) pour signaler les régressions
  en affichage (`passed`→`failed`) — le gating repose uniquement sur l'état
  absolu du run courant, pas sur la fiabilité du diff.

### Fiche projet — section `_spec-template.md`

Nouvelle section, uniquement présente si au moins un composant du
sous-circuit a `output_adjustable: true` (même règle de suppression
conditionnelle que les autres sections optionnelles du fichier) :

```markdown
## SPICE resolution values (component-specific)

<Only if at least one component in this subcircuit has
output_adjustable: true in its registry entry — delete otherwise.
Field names below must match resolved.* exactly (see
resources/spice-smoke-templates/<role>.yaml's project_specific_fields
list for the required set per role) — no translation layer.>

\`\`\`yaml
components:
  U1:
    nominal_vin: 12
    fb_divider_r1: 4700
    fb_divider_r2: 1000
\`\`\`
```

Bloc YAML fenced (pas une table Markdown) : cohérent avec le reste du
harnais (tout est YAML machine-lisible), parsing déterministe plutôt que du
scraping de table fragile. Les champs requis par rôle ne sont pas codés en
dur dans le résolveur : ils sont déclarés par `project_specific_fields` dans
le smoke-test template du rôle concerné — ça généralise à n'importe quel
rôle `output_adjustable` sans logique spécifique par rôle.

## Prochaines étapes (implémentation en cours)

- [x] Trancher D (CLI Python scripté).
- [x] Concevoir `component_inventory.yaml`, l'étape résolution, `resolved.*`,
  le rapport, la politique CI, la section `_spec-template.md`.
- [x] Écrire les vrais fichiers `_template.md` pour `resources/mpn-registry/`
  et `resources/spice-smoke-templates/`.
- [x] Appliquer la section "SPICE resolution values" à `_spec-template.md`.
- [x] Décider (B) : nouveau doc top-level → `kicad-spice-coverage.md`, ce
  brainstorm reste le compte-rendu historique.
- [x] Implémenter `scripts/check_spice_coverage.py` (les 3 étages) +
  `resources/mpn-registry/_normalization-rules.yaml`. Testé sur fixture
  (5 états hors exécution + waivers) **et** contre un vrai `ngspice
  44.2` (finalement disponible dans le sandbox — ma vérification
  initiale était fausse) : `passed` réel, `failed`/`syntax_error` réel
  (subckt non défini + ligne malformée), `failed`/`convergence_risk`
  réel (nœud flottant — ngspice sort en exit 0 après récupération par
  gmin/source stepping, seul le contenu du log détecte le problème, pas
  le code de sortie) — tous reproduits et classés correctement de bout
  en bout (rapport JSON, code de sortie, log `.log` sauvegardé).
- [x] Implémenter le hook pre-push (`scripts/install-hooks.sh` +
  `.githooks/pre-push`, car `.git/hooks/` n'est pas versionnable
  directement) et la GitHub Action (mode `ci`, autorité). Les deux se
  désactivent proprement (exit 0) sur ce repo, qui n'a pas de schéma
  propre.
- [x] Implémenter les adaptateurs d'ingestion
  (`scripts/build_component_inventory.py`) : `from_kicad_cli()` testé
  contre de vrais projets KiCad 9 (`flat_hierarchy`, `tiny_tapeout`,
  150 composants réels dont des DNP et des MPN réels) ; `from_mcp_manifest()`
  écrit et testé contre un manifest à la main, mais pas contre un vrai
  serveur MCP KiCad (indisponible). Correction de design trouvée en
  testant : `export bom` de `kicad-cli` abandonné au profit de
  `export netlist --format kicadxml` (le premier n'isole pas fiablement
  un composant par ligne) ; détection `ambiguous` du MPN abandonnée côté
  `from_kicad_cli()` (les champs adjacents au MPN dans un vrai projet
  sont des métadonnées légitimes, pas des conflits).
- [ ] Committer une fixture minimale dans le repo (suggestion Codex) pour
  que la CI puisse s'auto-valider sans dépendre d'un projet KiCad externe.
