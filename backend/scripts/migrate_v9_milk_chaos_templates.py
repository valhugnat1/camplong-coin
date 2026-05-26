"""
migrate_v9_milk_chaos_templates.py
─────────────────────────────────────────────────────────────────────
Migration v9 : table `milk_chaos_templates` + seed de templates par defaut.

Permet a l'admin de gerer un catalogue d'evenements chaos (petite/grosse
amplitude, lore, references culturelles) sans toucher au code. Le bot dieu
tire ensuite ces templates ponderes pour generer ses chocs sur les reserves.

Ajoute aussi les settings de frequence dans app_settings :
  - milk_chaos_tick_seconds (defaut 900 = 15 min)
  - milk_chaos_proba_pct    (defaut 25 = 25% de chance par tick par pool)

Caracteristiques :
  - Idempotent : ON CONFLICT (slug) DO NOTHING sur le seed
  - Multi-schemas : par defaut test + prod
"""

import sys
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from config import DATABASE_URL


# ─── DDL ─────────────────────────────────────────────────────────────

DDL_TEMPLATE = """
CREATE TABLE IF NOT EXISTS {schema}.milk_chaos_templates (
    id          SERIAL PRIMARY KEY,
    slug        VARCHAR(64) NOT NULL UNIQUE,
    kind        VARCHAR(32) NOT NULL,
    delta_type  VARCHAR(16) NOT NULL,
    delta_min   DOUBLE PRECISION NOT NULL,
    delta_max   DOUBLE PRECISION NOT NULL,
    narrative   VARCHAR(512) NOT NULL,
    weight      INTEGER NOT NULL DEFAULT 1,
    enabled     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMP NOT NULL DEFAULT NOW(),

    CONSTRAINT chaos_tpl_kind_chk CHECK (
        kind IN ('famine','spoil','overstock','import')
    ),
    CONSTRAINT chaos_tpl_dtype_chk CHECK (
        delta_type IN ('pct','bottles')
    ),
    CONSTRAINT chaos_tpl_weight_chk CHECK (weight > 0),
    CONSTRAINT chaos_tpl_range_chk CHECK (delta_min <= delta_max)
);
CREATE INDEX IF NOT EXISTS idx_chaos_tpl_enabled
    ON {schema}.milk_chaos_templates(enabled, weight);
"""


# ─── Templates par defaut ────────────────────────────────────────────
#
# Conventions :
#   - kind in ('famine','spoil','overstock','import')
#   - delta_type='pct'     : delta en % de la reserve courante
#   - delta_type='bottles' : delta en bouteilles absolues
#   - Negatif = stock baisse (prix monte). Positif = stock monte (prix baisse).
#   - weight : ponderation pour le tirage aleatoire
#
# Les narratives utilisent {pct} {abs_pct} {n} {abs_n} comme placeholders.

DEFAULT_TEMPLATES = [
    # ═══ Evenements BAISSIERS (stock ↓, prix ↑) ═══

    # Famine / climat
    ("famine_mild",       "famine", "pct",     -8.0,   -3.0,  10,
     "Petite secheresse en Normandie, -{abs_pct}% du stock"),
    ("famine_severe",     "famine", "pct",    -25.0,  -12.0,   3,
     "🔥 Secheresse historique, -{abs_pct}% en une nuit"),
    ("winter_cold",       "famine", "pct",    -10.0,   -4.0,   6,
     "Vague de froid sur l'Auvergne, vaches moins productives (-{abs_pct}%)"),
    ("heatwave",          "famine", "pct",    -12.0,   -5.0,   5,
     "Canicule a 42°C, les vaches font la sieste (-{abs_pct}%)"),
    ("flood_brittany",    "famine", "pct",    -15.0,   -7.0,   3,
     "Inondations en Bretagne, fermes evacuees (-{abs_pct}%)"),

    # Sanitaire
    ("cow_disease",       "famine", "pct",    -18.0,   -8.0,   5,
     "🐄 Epidemie bovine, abattage preventif (-{abs_pct}%)"),
    ("spoil_lot",         "spoil",  "bottles", -200,    -50,  10,
     "Lot contamine, retrait sanitaire de {abs_n} bouteilles"),
    ("spoil_massive",     "spoil",  "bottles",-1000,   -500,   2,
     "🚨 Rappel sanitaire national, {abs_n} bouteilles detruites"),
    ("lyon_bacteria",     "spoil",  "bottles", -180,    -60,   4,
     "Bacterie detectee a Lyon, {abs_n} bouteilles retirees"),
    ("factory_fire",      "spoil",  "bottles", -350,   -100,   3,
     "🔥 Incendie a l'usine de Vire, perte de {abs_n} bouteilles"),

    # Logistique / politique
    ("strike_truckers",   "famine", "pct",    -10.0,   -3.0,   8,
     "Greve des camionneurs, livraisons a l'arret (-{abs_pct}%)"),
    ("border_closed",     "famine", "pct",    -15.0,   -7.0,   4,
     "Frontiere fermee, blocage des imports (-{abs_pct}%)"),
    ("tractor_protest",   "famine", "pct",     -6.0,   -2.0,   7,
     "🚜 Tracteurs sur l'autoroute, A6 bloquee (-{abs_pct}%)"),
    ("fuel_shortage",     "famine", "pct",     -8.0,   -3.0,   5,
     "Penurie de carburant, livraisons annulees (-{abs_pct}%)"),

    # Demande / hype
    ("export_boom_china", "famine", "pct",    -14.0,   -6.0,   5,
     "🇨🇳 Boom export vers la Chine (-{abs_pct}% du stock local)"),
    ("instagram_trend",   "famine", "pct",     -7.0,   -3.0,   4,
     "📸 Trend Insta 'milk-bath', les stocks fondent (-{abs_pct}%)"),
    ("cheese_party",      "famine", "bottles", -120,    -30,   6,
     "🧀 Raclette nationale ce soir, {abs_n} bouteilles evaporees"),
    ("gerard_depardieu",  "famine", "bottles", -250,    -80,   2,
     "Gerard D. commande {abs_n} bouteilles pour sa cave"),

    # ═══ Evenements HAUSSIERS (stock ↑, prix ↓) ═══

    # Surproduction / meteo
    ("overstock_mild",    "overstock", "pct",    3.0,    8.0,  10,
     "Petite surproduction en Bretagne, +{pct}%"),
    ("overstock_massive", "overstock", "pct",   12.0,   25.0,   3,
     "💥 Surproduction massive, le marche est inonde (+{pct}%)"),
    ("good_weather",      "overstock", "pct",    3.0,    9.0,   7,
     "☀️ Ete ideal, prairies grasses (+{pct}%)"),
    ("spring_calving",    "overstock", "pct",    6.0,   14.0,   5,
     "Pic de velages au printemps, +{pct}% de lait"),
    ("milking_record",    "overstock", "bottles", 100,   400,   5,
     "🏆 Record de traite : +{n} bouteilles en 24h"),

    # Imports
    ("import_swiss",      "import", "pct",      7.0,   15.0,   5,
     "🇨🇭 Convoi suisse exceptionnel passe la frontiere (+{pct}%)"),
    ("import_germany",    "import", "pct",      4.0,   10.0,   5,
     "🇩🇪 Import allemand, prix casses (+{pct}%)"),
    ("import_holland",    "import", "pct",      5.0,   12.0,   4,
     "🇳🇱 Camions hollandais en quantite (+{pct}%)"),
    ("import_polish",     "import", "pct",      8.0,   18.0,   3,
     "🇵🇱 Import polonais discount (+{pct}%)"),

    # Politique / demande
    ("subsidies_eu",      "overstock", "pct",    8.0,   18.0,   4,
     "🇪🇺 Subventions europeennes, prod boostee (+{pct}%)"),
    ("discount_promo",    "import",  "bottles",   50,    200,   7,
     "🛒 Promo Carrefour, +{n} bouteilles destockees"),
    ("tourists_leave",    "overstock", "pct",    4.0,   10.0,   5,
     "Fin du rush touristique, +{pct}% qui reste"),
    ("school_holidays",   "overstock", "pct",    3.0,    7.0,   5,
     "Cantines fermees, +{pct}% qui ne trouve pas preneur"),
    ("tiktok_oat_war",    "overstock", "pct",    6.0,   14.0,   3,
     "📱 TikTok declare la guerre au lait d'avoine (+{pct}%)"),
    ("vegan_failure",     "overstock", "pct",    5.0,   12.0,   3,
     "🥛 Le 'vrai lait' redevient cool, +{pct}% de demande chutee"),
]


SEED_SQL = """
INSERT INTO {schema}.milk_chaos_templates
    (slug, kind, delta_type, delta_min, delta_max, weight, narrative)
VALUES
    (:slug, :kind, :delta_type, :delta_min, :delta_max, :weight, :narrative)
ON CONFLICT (slug) DO NOTHING
"""


# Settings de frequence (seed dans app_settings)
APP_SETTINGS_SEED = [
    ("milk_chaos_tick_seconds", "900",
     "Periode (en secondes) entre deux ticks du bot chaos. "
     "Bas = chocs frequents. Defaut 900 (= 15 min)."),
    ("milk_chaos_proba_pct", "25",
     "Probabilite (en %) qu'un tick declenche un evenement sur un pool donne. "
     "0 = bot desactive. 100 = un event a chaque tick. Defaut 25."),
    ("milk_chaos_max_volatility_pct", "20",
     "Cap de volatilite par event du bot (en % de variation de prix). "
     "Le delta_milk est clampe pour respecter ce plafond. "
     "Defaut 20 (price_after/price_before borne dans [0.83, 1.20])."),
]

APP_SETTINGS_SQL = """
INSERT INTO {schema}.app_settings (key, value, description, updated_at)
VALUES (:key, :value, :description, NOW())
ON CONFLICT (key) DO NOTHING
"""


# ─── Driver ──────────────────────────────────────────────────────────

def migrate_schema(engine, schema: str, dry_run: bool = False) -> None:
    print(f"\n{'='*64}\n  Migration v9 schema : {schema}\n{'='*64}")

    if dry_run:
        print(DDL_TEMPLATE.format(schema=schema))
        for tpl in DEFAULT_TEMPLATES:
            print(f"  seed: {tpl[0]}")
        for k, v, _ in APP_SETTINGS_SEED:
            print(f"  setting: {k} = {v}")
        return

    with engine.begin() as conn:
        conn.execute(text(f'SET search_path TO "{schema}", public'))

        # DDL
        print(f"  → CREATE TABLE milk_chaos_templates ...", end=" ", flush=True)
        try:
            conn.execute(text(DDL_TEMPLATE.format(schema=schema)))
            print("ok")
        except SQLAlchemyError as e:
            print(f"FAIL\n     {e}")
            raise

        # Seed templates
        seeded = 0
        for slug, kind, dtype, dmin, dmax, weight, narrative in DEFAULT_TEMPLATES:
            res = conn.execute(text(SEED_SQL.format(schema=schema)), {
                "slug": slug, "kind": kind, "delta_type": dtype,
                "delta_min": dmin, "delta_max": dmax,
                "weight": weight, "narrative": narrative,
            })
            if res.rowcount > 0:
                seeded += 1
        print(f"  → seed templates : {seeded} ajoutes (sur {len(DEFAULT_TEMPLATES)})")

        # Seed app_settings (frequence)
        seeded_settings = 0
        for key, value, desc in APP_SETTINGS_SEED:
            res = conn.execute(text(APP_SETTINGS_SQL.format(schema=schema)), {
                "key": key, "value": value, "description": desc,
            })
            if res.rowcount > 0:
                seeded_settings += 1
        print(f"  → seed app_settings : {seeded_settings} ajoutes")

    print(f"\n  Schema '{schema}' migre avec succes ✓")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry_run = "--dry-run" in sys.argv
    schemas = args if args else ["test", "prod"]

    print(f"Migration v9 — Milk chaos templates")
    print(f"  Schemas : {schemas}")
    print(f"  Dry run : {dry_run}")

    engine = create_engine(DATABASE_URL, future=True)
    for schema in schemas:
        try:
            migrate_schema(engine, schema, dry_run=dry_run)
        except SQLAlchemyError as e:
            print(f"\n❌ Echec schema '{schema}' : {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
