"""
services/poker.py - Moteur de Texas Hold'em No-Limit.

Architecture (cf. EXTENSIONS.md §5) :
  - Etat de jeu off-chain en DB (poker_hands.hand_log = blob JSON).
  - Mouvements on-chain uniquement au sit-in (lock vers poker_bank) et au
    sit-out (release du stack restant).
  - Pas de WebSockets : le front poll /casino/poker/tables/{id}/state
    toutes les ~2s. Suffisant pour 7 potes.
  - Provably fair : un commit-reveal par main, le deck est melange via
    Fisher-Yates seede sur combined_hash.

Le caller (router) commit la session DB. Les exceptions PokerError sont
metier (HTTP 400). Si l'escrow on-chain echoue : EscrowError remonte.

Etat d'une main (hand_log JSON) :
    {
      "street": "preflop|flop|turn|river|showdown|done",
      "deck": [...],          # cartes restantes (server-only)
      "board": [...],         # cartes communes visibles
      "pot": 100,
      "current_bet": 20,      # plus haute mise sur la street actuelle
      "min_raise": 20,        # incrementale min pour un raise valide
      "to_act_seat": 2,       # null = personne n'a a agir
      "last_aggressor_seat": null,
      "dealer_seat": 0,
      "sb_seat": 1,
      "bb_seat": 2,
      "players": [
        {"seat": 0, "username": "alice", "stack": 100, "bet": 0,
         "total_bet": 0, "folded": false, "all_in": false,
         "has_acted": false}
      ],
      "actions": [{"seat": 1, "move": "post_sb", "amount": 1}, ...]
    }

Quand la main se termine :
  - hand.board_cards / pot / winners_json / ended_at sont peuples
  - hand_log conserve l'etat final (sauf deck retire pour ne pas leaker)
  - les stacks des joueurs sont reportes dans poker_sessions.stack
"""
import datetime
import hashlib
import itertools
import json
from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from models import (
    User, PokerTable, PokerSession, PokerHand, PokerHandHole, RngSeed,
)
from services import escrow, randomness
from blockchain import get_balance_camp


POKER_BANK_ROLE = "poker_bank"


class PokerError(Exception):
    """Erreur metier poker (mauvais coup, mauvaise table, etc.)."""


# ═══════════════════════════════════════════════════════════════════
#  Deck & evaluateur de mains
# ═══════════════════════════════════════════════════════════════════

SUITS = ("h", "d", "c", "s")
RANKS = ("2", "3", "4", "5", "6", "7", "8", "9", "T", "J", "Q", "K", "A")
RANK_VALUE = {r: i + 2 for i, r in enumerate(RANKS)}   # '2'=2, 'A'=14


def make_deck() -> list[str]:
    """52 cartes, format 'Rs' (rank+suit), ex 'Ah', 'Td', '2c'."""
    return [r + s for r in RANKS for s in SUITS]


def shuffle_from_seed(deck: list[str], seed_hex: str) -> list[str]:
    """
    Fisher-Yates deterministe a partir d'un seed hex. Re-hash a chaque
    iteration pour produire assez d'entropie (sha256 -> 32 bytes par tour).
    """
    deck = list(deck)
    n = len(deck)
    for i in range(n - 1, 0, -1):
        h = hashlib.sha256(f"{seed_hex}:{i}".encode()).digest()
        j = int.from_bytes(h[:8], "big") % (i + 1)
        deck[i], deck[j] = deck[j], deck[i]
    return deck


def _rank_counts(ranks: list[int]) -> list[tuple[int, int]]:
    """Retourne [(rank, count), ...] trie par count DESC puis rank DESC."""
    counts: dict[int, int] = {}
    for r in ranks:
        counts[r] = counts.get(r, 0) + 1
    return sorted(counts.items(), key=lambda x: (-x[1], -x[0]))


def _straight_high(ranks: list[int]) -> Optional[int]:
    """Plus haute carte d'une suite, ou None. Gere la 'wheel' A-2-3-4-5."""
    s = set(ranks)
    if 14 in s:
        s = s | {1}                       # As bas
    sorted_unique = sorted(s, reverse=True)
    for i in range(len(sorted_unique) - 4):
        run = sorted_unique[i:i + 5]
        if run[0] - run[4] == 4 and len(set(run)) == 5:
            return run[0]
    return None


def eval_5(cards: list[str]) -> tuple:
    """
    Evalue 5 cartes. Retourne un tuple comparable :
      (categorie, *tiebreakers)
    avec categorie 1..9 :
      9 = straight flush, 8 = four of a kind, 7 = full house,
      6 = flush, 5 = straight, 4 = three of a kind,
      3 = two pair, 2 = one pair, 1 = high card.
    """
    ranks = [RANK_VALUE[c[0]] for c in cards]
    suits = [c[1] for c in cards]
    is_flush = len(set(suits)) == 1
    straight = _straight_high(ranks)
    counts = _rank_counts(ranks)
    # Pour tiebreaks : les ranks tries par (count desc, rank desc)
    flat_ranks = [r for r, _ in counts]

    if is_flush and straight is not None:
        return (9, straight)
    if counts[0][1] == 4:
        # quads : (4, kicker)
        return (8, counts[0][0], counts[1][0])
    if counts[0][1] == 3 and counts[1][1] == 2:
        return (7, counts[0][0], counts[1][0])
    if is_flush:
        return (6, *sorted(ranks, reverse=True))
    if straight is not None:
        return (5, straight)
    if counts[0][1] == 3:
        kickers = sorted([r for r in ranks if r != counts[0][0]], reverse=True)
        return (4, counts[0][0], *kickers)
    if counts[0][1] == 2 and counts[1][1] == 2:
        pair_high, pair_low = sorted([counts[0][0], counts[1][0]], reverse=True)
        kicker = max(r for r in ranks if r != pair_high and r != pair_low)
        return (3, pair_high, pair_low, kicker)
    if counts[0][1] == 2:
        kickers = sorted([r for r in ranks if r != counts[0][0]], reverse=True)
        return (2, counts[0][0], *kickers)
    return (1, *sorted(ranks, reverse=True))


CATEGORY_LABELS = {
    9: "Quinte flush", 8: "Carre", 7: "Full house", 6: "Couleur",
    5: "Quinte", 4: "Brelan", 3: "Deux paires", 2: "Paire", 1: "Carte haute",
}


def _order_straight(cards: list[str]) -> list[str]:
    """Ordonne 5 cartes d'une suite en ordre croissant ; pour la wheel
    (A-2-3-4-5) on met l'As en premier (carte basse)."""
    ranks = sorted({RANK_VALUE[c[0]] for c in cards})
    if ranks == [2, 3, 4, 5, 14]:
        order = [14, 2, 3, 4, 5]
    else:
        order = ranks
    out, remaining = [], list(cards)
    for r in order:
        for c in remaining:
            if RANK_VALUE[c[0]] == r:
                out.append(c)
                remaining.remove(c)
                break
    return out


def defining_cards(score: tuple, best_5: list[str]) -> list[str]:
    """
    Sous-ensemble de best_5 qui DEFINIT la categorie de la main (sans
    les kickers). Utilise pour le surlignage cote UI : on n'eclaire que
    les cartes qui font reellement gagner.

      Quinte flush / Full / Couleur / Suite : les 5 cartes (tout compte).
      Carre  : 4 cartes (les quatre du carre).
      Brelan : 3 cartes (le trio).
      Deux paires : 4 cartes (les deux paires).
      Paire  : 2 cartes (la paire seule).
      Carte haute : 1 carte (la plus haute).
    """
    cat = score[0]
    if cat in (9, 7, 6, 5):
        return list(best_5)
    if cat == 8:
        quad_rank = score[1]
        return [c for c in best_5 if RANK_VALUE[c[0]] == quad_rank]
    if cat == 4:
        trips_rank = score[1]
        return [c for c in best_5 if RANK_VALUE[c[0]] == trips_rank]
    if cat == 3:
        high_pair, low_pair = score[1], score[2]
        return [c for c in best_5 if RANK_VALUE[c[0]] in (high_pair, low_pair)]
    if cat == 2:
        pair_rank = score[1]
        return [c for c in best_5 if RANK_VALUE[c[0]] == pair_rank]
    if cat == 1:
        top = score[1]
        for c in best_5:
            if RANK_VALUE[c[0]] == top:
                return [c]
    return []


def order_for_display(all_cards: list[str], score: tuple,
                     best_5: list[str]) -> list[str]:
    """
    Reordonne 7 (ou moins) cartes pour l'affichage : meilleure main
    d'abord, dans un ordre qui montre clairement la combinaison
    (paires ensemble, suite croissante, etc.). Les cartes "mortes"
    (non utilisees) sont mises a la fin, par rang descendant.
    """
    if not best_5:
        # Pas d'evaluation possible : juste trier descendant
        return sorted(all_cards, key=lambda c: -RANK_VALUE[c[0]])
    cat = score[0]
    if cat in (9, 5):
        ordered_best = _order_straight(best_5)
    elif cat == 6:
        # Couleur : descendant
        ordered_best = sorted(best_5, key=lambda c: -RANK_VALUE[c[0]])
    elif cat == 1:
        # Carte haute : descendant
        ordered_best = sorted(best_5, key=lambda c: -RANK_VALUE[c[0]])
    else:
        # Categories a regroupement : on suit l'ordre des ranks dans score[1:]
        # (la paire haute, puis la paire basse, puis kicker, etc.)
        ordered_ranks = list(score[1:])
        ordered_best = []
        remaining = list(best_5)
        for r in ordered_ranks:
            matched = [c for c in remaining if RANK_VALUE[c[0]] == r]
            ordered_best.extend(matched)
            for c in matched:
                remaining.remove(c)
        ordered_best.extend(remaining)   # garde-fou si le tuple ne couvre pas
    # Cartes mortes : descendant
    leftovers = [c for c in all_cards if c not in best_5]
    leftovers.sort(key=lambda c: -RANK_VALUE[c[0]])
    return ordered_best + leftovers


def eval_best(cards: list[str]) -> tuple[tuple, list[str], str]:
    """
    Evalue la meilleure main de 5 parmi N (5..7). Retourne (score, best_5, label).
    """
    if len(cards) < 5:
        raise ValueError("Il faut au moins 5 cartes pour evaluer")
    best_score = None
    best_5 = None
    for combo in itertools.combinations(cards, 5):
        s = eval_5(list(combo))
        if best_score is None or s > best_score:
            best_score = s
            best_5 = list(combo)
    return best_score, best_5, CATEGORY_LABELS[best_score[0]]


# ═══════════════════════════════════════════════════════════════════
#  Helpers d'etat
# ═══════════════════════════════════════════════════════════════════

def _active_sessions(db: Session, table_id: int) -> list[PokerSession]:
    return (
        db.query(PokerSession)
          .filter(PokerSession.table_id == table_id,
                  PokerSession.left_at.is_(None))
          .order_by(PokerSession.seat.asc())
          .all()
    )


def _current_hand(db: Session, table_id: int) -> Optional[PokerHand]:
    return (
        db.query(PokerHand)
          .filter(PokerHand.table_id == table_id,
                  PokerHand.ended_at.is_(None))
          .order_by(PokerHand.id.desc())
          .first()
    )


def _next_seat(seats: list[int], start_seat: int) -> Optional[int]:
    """Siege suivant present dans `seats` (modulo). None si liste vide."""
    if not seats:
        return None
    sorted_seats = sorted(seats)
    for s in sorted_seats:
        if s > start_seat:
            return s
    return sorted_seats[0]


def _next_to_act_seat(state: dict, after_seat: int) -> Optional[int]:
    """
    Trouve le siege suivant qui doit encore agir : non-folded, non-all-in.
    None si plus personne ne doit agir (street complete).
    """
    seats = [p["seat"] for p in state["players"]
             if not p["folded"] and not p["all_in"]]
    if not seats:
        return None
    s = _next_seat(seats, after_seat)
    return s


def _street_complete(state: dict) -> bool:
    """
    True si la street actuelle est finie : tous les joueurs non-folds
    non-all-in ont la meme mise (bet) et ont agi au moins une fois.
    """
    eligible = [p for p in state["players"]
                if not p["folded"] and not p["all_in"]]
    if not eligible:
        return True
    bet = state["current_bet"]
    for p in eligible:
        if not p["has_acted"]:
            return False
        if p["bet"] != bet:
            return False
    return True


def _everyone_folded_except_one(state: dict) -> Optional[int]:
    """Retourne le seat du dernier joueur non-folded, ou None."""
    alive = [p for p in state["players"] if not p["folded"]]
    if len(alive) == 1:
        return alive[0]["seat"]
    return None


# ═══════════════════════════════════════════════════════════════════
#  Demarrage d'une main
# ═══════════════════════════════════════════════════════════════════

def _next_dealer_seat(sessions: list[PokerSession], last_dealer: Optional[int]) -> int:
    """Rotation du bouton sur les sessions actives."""
    seats = [s.seat for s in sessions]
    if last_dealer is None:
        return min(seats)
    nxt = _next_seat(seats, last_dealer)
    return nxt if nxt is not None else seats[0]


def _post_blind(state: dict, seat: int, amount: int, kind: str) -> None:
    """Deduit la blind du stack et l'ajoute au pot/bet du joueur."""
    p = next(x for x in state["players"] if x["seat"] == seat)
    paid = min(amount, p["stack"])
    p["stack"] -= paid
    p["bet"] += paid
    p["total_bet"] += paid
    if p["stack"] == 0:
        p["all_in"] = True
    state["pot"] += paid
    state["actions"].append({"seat": seat, "move": kind, "amount": paid})


def start_hand(db: Session, table: PokerTable) -> Optional[PokerHand]:
    """
    Tente de demarrer une nouvelle main sur la table. Suppose qu'il n'y
    a pas de main en cours. Retourne la PokerHand creee, ou None si pas
    assez de joueurs avec stack >= big_blind.
    """
    sessions = _active_sessions(db, table.id)
    eligible = [s for s in sessions if s.stack >= table.blind_big]
    if len(eligible) < 2:
        return None

    # Numero de main : sequentiel par table
    last_n = db.query(PokerHand).filter(PokerHand.table_id == table.id) \
        .order_by(PokerHand.hand_number.desc()).first()
    hand_number = (last_n.hand_number if last_n else 0) + 1

    # Dernier dealer : on regarde la main precedente (ended_at IS NOT NULL)
    last_hand = (
        db.query(PokerHand)
          .filter(PokerHand.table_id == table.id)
          .order_by(PokerHand.id.desc())
          .first()
    )
    last_dealer = last_hand.dealer_seat if last_hand else None
    dealer_seat = _next_dealer_seat(eligible, last_dealer)

    eligible_seats = sorted([s.seat for s in eligible])
    sb_seat = _next_seat(eligible_seats, dealer_seat) if len(eligible_seats) > 2 else dealer_seat
    # En heads-up : le dealer est SB, l'autre BB
    bb_seat = _next_seat(eligible_seats, sb_seat)

    # Commit RNG seed (publie le hash, garde le secret)
    seed_hash, seed_id = randomness.commit(db, "poker")
    # Le client_seed sera la concatenation des usernames + hand_number.
    # Pas de contribution user random (1 client serait privilegie sinon).
    # On combine seed serveur + (table_id, hand_number) -> hash deterministe.
    client_seed = f"table={table.id}:hand={hand_number}"
    server_seed, combined = randomness.reveal(db, seed_id, client_seed)

    # Shuffle deck
    deck = shuffle_from_seed(make_deck(), combined)

    # Distribue 2 hole cards a chaque joueur eligible (ordre des sieges
    # a partir du SB, comme dans la vraie vie)
    order_from_sb = []
    s = sb_seat
    while True:
        order_from_sb.append(s)
        nxt = _next_seat(eligible_seats, s)
        if nxt == sb_seat:
            break
        s = nxt
        if len(order_from_sb) > len(eligible_seats):
            break  # safety

    holes_by_user: dict[str, str] = {}
    # 2 tours : une carte chacun, puis l'autre
    for round_idx in range(2):
        for seat in order_from_sb:
            sess = next(x for x in eligible if x.seat == seat)
            card = deck.pop(0)
            holes_by_user[sess.username] = holes_by_user.get(sess.username, "") + (" " if holes_by_user.get(sess.username) else "") + card

    # Construit l'etat initial
    players_state = []
    for sess in eligible:
        players_state.append({
            "seat": sess.seat,
            "username": sess.username,
            "stack": int(sess.stack),
            "bet": 0,
            "total_bet": 0,
            "folded": False,
            "all_in": False,
            "has_acted": False,
        })

    state = {
        "street": "preflop",
        "deck": deck,
        "board": [],
        "pot": 0,
        "current_bet": 0,
        "min_raise": int(table.blind_big),
        "to_act_seat": None,
        "last_aggressor_seat": None,
        "dealer_seat": dealer_seat,
        "sb_seat": sb_seat,
        "bb_seat": bb_seat,
        "players": players_state,
        "actions": [],
    }

    # Post blinds
    _post_blind(state, sb_seat, int(table.blind_small), "post_sb")
    _post_blind(state, bb_seat, int(table.blind_big), "post_bb")
    state["current_bet"] = int(table.blind_big)
    # Le BB n'a pas "agi" au sens "voluntary" : on lui laisse l'option de
    # check/raise quand l'action lui revient.
    bb_player = next(p for p in state["players"] if p["seat"] == bb_seat)
    bb_player["has_acted"] = False
    # Premier a agir preflop : seat apres le BB
    state["to_act_seat"] = _next_to_act_seat(state, bb_seat)

    # Persiste la main
    hand = PokerHand(
        table_id=table.id,
        hand_number=hand_number,
        dealer_seat=dealer_seat,
        board_cards=None,
        pot=state["pot"],
        winners_json=None,
        hand_log=json.dumps(state),
        rng_seed_id=seed_id,
        started_at=datetime.datetime.utcnow(),
        ended_at=None,
    )
    db.add(hand)
    db.flush()

    # Lie le seed a la main
    seed_row = db.get(RngSeed, seed_id)
    if seed_row is not None:
        seed_row.ref_id = hand.id

    # Persiste les hole cards
    for username, cards in holes_by_user.items():
        db.add(PokerHandHole(
            hand_id=hand.id, username=username, hole_cards=cards,
        ))

    db.flush()
    return hand


# ═══════════════════════════════════════════════════════════════════
#  Actions de jeu
# ═══════════════════════════════════════════════════════════════════

VALID_MOVES = ("fold", "check", "call", "bet", "raise")


def _save_state(hand: PokerHand, state: dict) -> None:
    hand.hand_log = json.dumps(state)
    hand.pot = state["pot"]
    if state["board"]:
        hand.board_cards = " ".join(state["board"])


def _deal_street(state: dict) -> None:
    """Pioche les cartes communes pour la prochaine street."""
    if state["street"] == "preflop":
        # Flop : 3 cartes
        state["board"].extend([state["deck"].pop(0) for _ in range(3)])
        state["street"] = "flop"
    elif state["street"] == "flop":
        state["board"].append(state["deck"].pop(0))
        state["street"] = "turn"
    elif state["street"] == "turn":
        state["board"].append(state["deck"].pop(0))
        state["street"] = "river"
    else:
        return  # river : prochain pas = showdown


def _reset_for_new_street(state: dict) -> None:
    """Remet les bets a 0, reset has_acted, premier a agir = apres dealer."""
    for p in state["players"]:
        p["bet"] = 0
        p["has_acted"] = False
    state["current_bet"] = 0
    state["min_raise"] = state.get("min_raise", 0) or 1
    state["last_aggressor_seat"] = None
    # Premier a parler post-flop : seat apres le dealer
    state["to_act_seat"] = _next_to_act_seat(state, state["dealer_seat"])


def _settle_hand(db: Session, table: PokerTable, hand: PokerHand,
                 state: dict, hole_lookup: dict[str, str]) -> dict:
    """
    Distribue le pot : gere les side pots si tout-in, evalue les mains
    non-folded, met a jour les stacks sessions, retourne winners_json dict.
    """
    # Side pots : on classe les joueurs par total_bet ascendant ; chaque
    # palier de total_bet cree un pot auquel ne participent que les
    # joueurs ayant mise au moins ce niveau.
    all_players = state["players"]
    contributors = sorted(all_players, key=lambda p: p["total_bet"])

    pots: list[dict] = []  # [{amount, eligible_seats}]
    prev_level = 0
    for i, p in enumerate(contributors):
        level = p["total_bet"]
        if level <= prev_level:
            continue
        delta = level - prev_level
        contribs = [x for x in contributors if x["total_bet"] >= level]
        pot_amount = delta * len([x for x in all_players if x["total_bet"] >= level])
        # Eligibles a gagner ce pot : tous ceux qui y ont contribue
        # ET qui ne sont pas folded.
        eligible = [x["seat"] for x in contribs if not x["folded"]]
        if eligible:
            pots.append({"amount": pot_amount, "eligible_seats": eligible})
        else:
            # Tout le monde a fold sur ce palier : on agglutine avec le
            # pot precedent (rare, ne devrait pas arriver).
            if pots:
                pots[-1]["amount"] += pot_amount
        prev_level = level

    # Evalue chaque main pour le settlement, ET prepare aussi un dump
    # transparent (hole + board reordonne) pour tous les joueurs, y
    # compris les folded. Permet d'afficher cote front "voila ce que
    # chacun avait, voila ce que ca aurait fait".
    board = state["board"]
    showdown: dict[int, dict] = {}
    for p in all_players:
        hole_str = hole_lookup.get(p["username"], "")
        hole_cards = hole_str.split(" ") if hole_str else []
        all_cards = hole_cards + list(board)
        if len(all_cards) >= 5 and not p["folded"]:
            score, best5, label = eval_best(all_cards)
        elif len(all_cards) >= 5 and p["folded"]:
            # Folded mais on calcule quand meme pour montrer "ce qu'il aurait fait"
            score, best5, label = eval_best(all_cards)
            label = f"Foldé · {label}"
        else:
            score, best5, label = (0,), [], ("Foldé" if p["folded"] else "")
        defs = defining_cards(score, best5) if best5 else []
        display = order_for_display(all_cards, score, best5)
        showdown[p["seat"]] = {
            "score": score,
            "best_5": best5,
            "label": label,
            "hole_cards": hole_cards,
            "display_cards": display,
            "defining_cards": defs,
            "username": p["username"],
            "folded": p["folded"],
        }

    # Distribue chaque pot au(x) meilleur(s) eligible(s)
    winnings: dict[int, int] = {p["seat"]: 0 for p in all_players}
    winners_summary = []
    for pot in pots:
        eligible = pot["eligible_seats"]
        if not eligible:
            continue
        scored = [(s, showdown[s]["score"]) for s in eligible if s in showdown]
        if not scored:
            continue
        best_score = max(sc for _, sc in scored)
        winners = [s for s, sc in scored if sc == best_score]
        share = pot["amount"] // len(winners)
        remainder = pot["amount"] - share * len(winners)
        for w in winners:
            winnings[w] += share
        # Le reste de division va au premier gagnant (apres le bouton)
        if remainder > 0:
            winnings[winners[0]] += remainder
        winners_summary.append({
            "amount": pot["amount"],
            "winners": [
                {
                    "seat": w,
                    "username": showdown[w]["username"],
                    "share": share + (remainder if i == 0 else 0),
                    "hand_label": showdown[w]["label"],
                    "hole_cards": showdown[w]["hole_cards"],
                    "display_cards": showdown[w]["display_cards"],
                    "defining_cards": showdown[w]["defining_cards"],
                }
                for i, w in enumerate(winners)
            ],
        })

    # Reporte les stacks gagnes sur les sessions
    sessions = _active_sessions(db, table.id)
    by_seat = {s.seat: s for s in sessions}
    final_players = []
    for p in all_players:
        net = winnings.get(p["seat"], 0)
        # p["stack"] reflete deja la sortie des mises ; on rajoute les gains
        new_stack = p["stack"] + net
        sess = by_seat.get(p["seat"])
        if sess is not None:
            sess.stack = new_stack
        final_players.append({
            "seat": p["seat"], "username": p["username"],
            "final_stack": new_stack, "net": net - p["total_bet"],
            "folded": p["folded"],
        })

    return {
        "pots": winners_summary,
        "final_players": final_players,
        "board": board,
        # Reveal des hole cards pour CHAQUE joueur (folded inclus) —
        # transparence "entre potes". Le board reste sur le feutre au-dessus.
        # `scoring_hole_cards` = subset de hole_cards qui sert REELLEMENT
        # a former la combinaison gagnante (sans les kickers).
        "shown_holes": [
            {
                "seat": s,
                "username": sh["username"],
                "hole_cards": sh["hole_cards"],
                "display_cards": sh["display_cards"],
                "defining_cards": sh["defining_cards"],
                "label": sh["label"],
                "folded": sh["folded"],
            }
            for s, sh in showdown.items()
        ],
    }


def _close_hand(db: Session, table: PokerTable, hand: PokerHand,
                state: dict, settlement: dict) -> None:
    """Marque la main comme finie + nettoie le deck du log (anti-leak)."""
    # On retire le deck restant du log persiste, ce n'est plus utile
    # et ca evite tout risque que le client recupere les cartes futures.
    state_to_persist = dict(state)
    state_to_persist["deck"] = []
    state_to_persist["street"] = "done"
    state_to_persist["to_act_seat"] = None
    hand.hand_log = json.dumps(state_to_persist)
    hand.board_cards = " ".join(state["board"]) if state["board"] else None
    hand.pot = state["pot"]
    hand.winners_json = json.dumps(settlement)
    hand.ended_at = datetime.datetime.utcnow()


def act(
    db: Session,
    table: PokerTable,
    hand: PokerHand,
    user: User,
    move: str,
    amount: int = 0,
) -> dict:
    """
    Applique une action utilisateur sur la main en cours. Retourne un
    dict resume (move accepte + nouvel etat synth).

    Lance PokerError si :
      - ce n'est pas le tour du joueur
      - move invalide
      - montant invalide (raise < min, etc.)
    """
    if move not in VALID_MOVES:
        raise PokerError(f"Move invalide : {move}")
    state = json.loads(hand.hand_log)
    if state.get("street") in ("done", "showdown"):
        raise PokerError("Main terminee")

    to_act = state.get("to_act_seat")
    p = next((x for x in state["players"] if x["username"] == user.username), None)
    if p is None:
        raise PokerError("Tu n'es pas dans cette main")
    if to_act is None or p["seat"] != to_act:
        raise PokerError("Ce n'est pas a toi de jouer")
    if p["folded"] or p["all_in"]:
        raise PokerError("Tu ne peux pas agir (folded ou all-in)")

    current_bet = state["current_bet"]
    to_call = current_bet - p["bet"]

    if move == "fold":
        p["folded"] = True
        state["actions"].append({"seat": p["seat"], "move": "fold", "amount": 0})

    elif move == "check":
        if to_call > 0:
            raise PokerError(f"Impossible de checker, il faut suivre {to_call}")
        p["has_acted"] = True
        state["actions"].append({"seat": p["seat"], "move": "check", "amount": 0})

    elif move == "call":
        if to_call <= 0:
            raise PokerError("Rien a suivre, utilise 'check'")
        paid = min(to_call, p["stack"])
        p["stack"] -= paid
        p["bet"] += paid
        p["total_bet"] += paid
        state["pot"] += paid
        if p["stack"] == 0:
            p["all_in"] = True
        p["has_acted"] = True
        state["actions"].append({"seat": p["seat"], "move": "call", "amount": paid})

    elif move == "bet":
        if current_bet != 0:
            raise PokerError("Il y a deja une mise, utilise 'raise'")
        if amount < state["min_raise"]:
            raise PokerError(f"Mise min : {state['min_raise']}")
        if amount > p["stack"]:
            raise PokerError(f"Stack insuffisant ({p['stack']})")
        p["stack"] -= amount
        p["bet"] += amount
        p["total_bet"] += amount
        state["pot"] += amount
        if p["stack"] == 0:
            p["all_in"] = True
        state["current_bet"] = p["bet"]
        state["min_raise"] = amount
        state["last_aggressor_seat"] = p["seat"]
        # Les autres joueurs doivent re-agir
        for q in state["players"]:
            if q["seat"] != p["seat"] and not q["folded"] and not q["all_in"]:
                q["has_acted"] = False
        p["has_acted"] = True
        state["actions"].append({"seat": p["seat"], "move": "bet", "amount": amount})

    elif move == "raise":
        if current_bet == 0:
            raise PokerError("Pas de mise a relancer, utilise 'bet'")
        # amount = NOUVEAU total de mise (pas l'incrementale)
        target_total = amount
        increment = target_total - current_bet
        if increment < state["min_raise"]:
            # All-in tolere meme si < min_raise (mais ne re-ouvre pas l'action)
            if target_total - p["bet"] != p["stack"]:
                raise PokerError(
                    f"Raise min : porter le total a {current_bet + state['min_raise']}"
                )
        chips_added = target_total - p["bet"]
        if chips_added > p["stack"]:
            raise PokerError(f"Stack insuffisant ({p['stack']})")
        p["stack"] -= chips_added
        p["bet"] = target_total
        p["total_bet"] += chips_added
        state["pot"] += chips_added
        if p["stack"] == 0:
            p["all_in"] = True
        re_open = increment >= state["min_raise"]
        state["current_bet"] = target_total
        if re_open:
            state["min_raise"] = increment
            state["last_aggressor_seat"] = p["seat"]
            for q in state["players"]:
                if q["seat"] != p["seat"] and not q["folded"] and not q["all_in"]:
                    q["has_acted"] = False
        p["has_acted"] = True
        state["actions"].append({"seat": p["seat"], "move": "raise", "amount": target_total})

    # ─── Apres le coup : check fin / progression ─────────
    last_alive = _everyone_folded_except_one(state)
    if last_alive is not None:
        # Un seul joueur restant : il gagne le pot direct, pas de showdown
        return _finalize(db, table, hand, state, force_winner_seat=last_alive)

    if _street_complete(state):
        # Tout le monde a egal et a agi : street suivante
        # Cas particulier : preflop, BB peut etre a la fin (option de relance)
        # mais si bet=BB et tout le monde a call et bb a agi : ok.
        return _advance_street(db, table, hand, state)

    # Sinon, passe au joueur suivant
    state["to_act_seat"] = _next_to_act_seat(state, p["seat"])
    if state["to_act_seat"] is None:
        # Tous les autres sont all-in ou folded : avance tout droit jusqu'a la river
        return _run_out_board(db, table, hand, state)

    _save_state(hand, state)
    return {"ok": True, "move": move}


def _advance_street(db: Session, table: PokerTable, hand: PokerHand,
                    state: dict) -> dict:
    """Passe a la street suivante (ou termine la main si river -> showdown)."""
    cur = state["street"]
    if cur == "river":
        return _finalize(db, table, hand, state, force_winner_seat=None)

    _deal_street(state)
    _reset_for_new_street(state)

    # Si plus personne ne peut agir (tous all-in/folded sauf un) -> run out
    actives = [p for p in state["players"]
               if not p["folded"] and not p["all_in"]]
    if len(actives) <= 1:
        return _run_out_board(db, table, hand, state)

    _save_state(hand, state)
    return {"ok": True, "street": state["street"]}


def _run_out_board(db: Session, table: PokerTable, hand: PokerHand,
                   state: dict) -> dict:
    """Distribue toutes les cartes restantes jusqu'a la river puis showdown."""
    while state["street"] in ("preflop", "flop", "turn"):
        _deal_street(state)
    return _finalize(db, table, hand, state, force_winner_seat=None)


def _finalize(db: Session, table: PokerTable, hand: PokerHand,
              state: dict, force_winner_seat: Optional[int]) -> dict:
    """Termine la main : showdown ou gagnant unique."""
    holes = (
        db.query(PokerHandHole)
          .filter(PokerHandHole.hand_id == hand.id)
          .all()
    )
    hole_lookup = {h.username: h.hole_cards for h in holes}

    if force_winner_seat is not None:
        # Un seul joueur restant : il rafle le pot sans evaluer
        winner = next(p for p in state["players"] if p["seat"] == force_winner_seat)
        sessions = _active_sessions(db, table.id)
        for sess in sessions:
            if sess.seat == winner["seat"]:
                sess.stack = winner["stack"] + state["pot"]

        board = list(state["board"])

        # Hole cards de tous les joueurs (transparence "entre potes").
        # Pas de surlignage car pas de showdown : scoring_hole_cards=[].
        winner_hole_str = hole_lookup.get(winner["username"], "")
        winner_hole = winner_hole_str.split(" ") if winner_hole_str else []

        shown = []
        for p in state["players"]:
            if p["seat"] == winner["seat"]:
                continue
            hole_str = hole_lookup.get(p["username"], "")
            hole_cards = hole_str.split(" ") if hole_str else []
            shown.append({
                "seat": p["seat"],
                "username": p["username"],
                "hole_cards": hole_cards,
                "display_cards": hole_cards + board,
                "defining_cards": [],
                "label": "Foldé",
                "folded": True,
            })

        settlement = {
            "pots": [{
                "amount": state["pot"],
                "winners": [{
                    "seat": winner["seat"],
                    "username": winner["username"],
                    "share": state["pot"],
                    "hand_label": "Tous foldés",
                    "hole_cards": winner_hole,
                    "display_cards": winner_hole + board,
                    "defining_cards": [],
                }],
            }],
            "final_players": [
                {
                    "seat": p["seat"], "username": p["username"],
                    "final_stack": (p["stack"] + state["pot"]
                                    if p["seat"] == winner["seat"] else p["stack"]),
                    "net": (state["pot"] - p["total_bet"]
                            if p["seat"] == winner["seat"] else -p["total_bet"]),
                    "folded": p["folded"],
                }
                for p in state["players"]
            ],
            "board": board,
            "shown_holes": shown,
        }
    else:
        settlement = _settle_hand(db, table, hand, state, hole_lookup)

    state["street"] = "done"
    state["to_act_seat"] = None
    _close_hand(db, table, hand, state, settlement)
    return {"ok": True, "ended": True, "settlement": settlement}


# ═══════════════════════════════════════════════════════════════════
#  Sit-in / Sit-out
# ═══════════════════════════════════════════════════════════════════

def _next_free_seat(taken: list[int], max_players: int) -> Optional[int]:
    for s in range(max_players):
        if s not in taken:
            return s
    return None


def sit_in(db: Session, table: PokerTable, user: User, buyin: int) -> PokerSession:
    """
    Asseoir un joueur a la table. Lock buyin CAMP vers poker_bank.
    Le caller commit la session.
    """
    if table.status != "open":
        raise PokerError("Table fermee, plus de sit-in autorise")
    if buyin < table.min_buyin or buyin > table.max_buyin:
        raise PokerError(
            f"Buy-in hors limites ({table.min_buyin}-{table.max_buyin} CAMP)"
        )
    if user.account_type == "system":
        raise PokerError("Les comptes systeme ne peuvent pas s'asseoir")

    active = _active_sessions(db, table.id)
    if len(active) >= table.max_players:
        raise PokerError("Table pleine")
    if any(s.username == user.username for s in active):
        raise PokerError("Tu es deja a cette table")

    seat = _next_free_seat([s.seat for s in active], table.max_players)
    if seat is None:
        raise PokerError("Table pleine")

    tx = escrow.lock(
        db, user, POKER_BANK_ROLE, buyin,
        f"poker table={table.id} buyin",
    )
    sess = PokerSession(
        table_id=table.id,
        username=user.username,
        seat=seat,
        stack=buyin,
        initial_stack=buyin,
        tx_hash_buyin=tx,
    )
    db.add(sess)
    db.flush()
    return sess


def _force_fold(db: Session, table: PokerTable, hand: PokerHand,
                state: dict, username: str) -> None:
    """
    Marque un user comme folded dans la main en cours et fait avancer
    la partie en consequence (advance_street / finalize / next-to-act).
    Utilise pour 'leave mid-hand' : le user perd sa mise courante mais
    la partie continue sans lui pour les autres.

    Le caller commit la session.
    """
    player = next(
        (p for p in state["players"] if p["username"] == username),
        None,
    )
    if player is None or player["folded"]:
        # Pas dans la main ou deja folded : rien a faire cote etat
        return

    was_to_act = state.get("to_act_seat") == player["seat"]
    player["folded"] = True
    state["actions"].append({
        "seat": player["seat"], "move": "fold_leave", "amount": 0,
    })

    # Apres le fold force : meme logique d'avancement que dans act()
    last_alive = _everyone_folded_except_one(state)
    if last_alive is not None:
        _finalize(db, table, hand, state, force_winner_seat=last_alive)
        return

    if _street_complete(state):
        _advance_street(db, table, hand, state)
        return

    if was_to_act:
        state["to_act_seat"] = _next_to_act_seat(state, player["seat"])
        if state["to_act_seat"] is None:
            _run_out_board(db, table, hand, state)
            return

    _save_state(hand, state)


def sit_out(db: Session, table: PokerTable, user: User) -> dict:
    """
    Quitter la table. Comportement :
      - Pas de main en cours OU user pas dans la main : cashout direct.
      - User dans la main et deja folded : cashout direct.
      - User dans la main et non folded : on l'auto-fold (la main continue
        sans lui pour les autres), puis cashout. Sa mise courante reste
        dans le pot et ira au gagnant.

    Release stack restant -> user. Le caller commit la session.
    """
    sess = (
        db.query(PokerSession)
          .filter(PokerSession.table_id == table.id,
                  PokerSession.username == user.username,
                  PokerSession.left_at.is_(None))
          .first()
    )
    if sess is None:
        raise PokerError("Tu n'es pas a cette table")

    cur = _current_hand(db, table.id)
    if cur is not None:
        state = json.loads(cur.hand_log)
        player = next(
            (p for p in state.get("players", [])
             if p["username"] == user.username),
            None,
        )
        if player is not None and not player["folded"]:
            # Auto-fold + avance la main. _finalize peut etre appele a
            # l'interieur, ce qui maj sess.stack (winnings=0 pour folde).
            _force_fold(db, table, cur, state, user.username)
            # Le stack 'mid-hand' (state.players[i].stack) est ce qui reste
            # devant lui apres ses mises ; c'est ce qu'on lui rend.
            sess.stack = int(player["stack"])

    final_stack = int(sess.stack)
    tx = None
    if final_stack > 0:
        tx = escrow.release(
            db, POKER_BANK_ROLE, user, final_stack,
            f"poker table={table.id} cashout",
        )
    sess.left_at = datetime.datetime.utcnow()
    if tx is not None:
        sess.tx_hash_cashout = tx
    return {
        "final_stack": final_stack,
        "tx_hash_cashout": tx,
    }


# ═══════════════════════════════════════════════════════════════════
#  Vue d'etat (pour le polling)
# ═══════════════════════════════════════════════════════════════════

def state_dict(db: Session, table: PokerTable, user: Optional[User]) -> dict:
    """
    Retourne l'etat complet visible par `user` (None si non-authentifie).
    - Cartes communes + pot + actions + joueurs visibles (sans hole cards)
    - Hole cards du user lui-meme (si il est dans la main)
    - Si la main est terminee : hole cards de tous les non-folded
    """
    sessions = _active_sessions(db, table.id)
    sessions_view = [
        {
            "seat": s.seat,
            "username": s.username,
            "stack": int(s.stack),
            "joined_at": s.joined_at.isoformat() + "Z" if s.joined_at else None,
        }
        for s in sessions
    ]

    hand = _current_hand(db, table.id)
    hand_view = None
    if hand is not None:
        state = json.loads(hand.hand_log)
        # Cartes des joueurs : public = "??" sauf user lui-meme et showdown
        players_pub = []
        for p in state["players"]:
            entry = {k: v for k, v in p.items()}
            entry["hole_cards"] = None
            players_pub.append(entry)

        # Hole cards du user lui-meme
        my_hole = None
        if user is not None:
            row = (
                db.query(PokerHandHole)
                  .filter(PokerHandHole.hand_id == hand.id,
                          PokerHandHole.username == user.username)
                  .first()
            )
            if row is not None:
                my_hole = row.hole_cards.split(" ")
                for ent in players_pub:
                    if ent["username"] == user.username:
                        ent["hole_cards"] = my_hole

        hand_view = {
            "id": hand.id,
            "hand_number": hand.hand_number,
            "street": state["street"],
            "board": state["board"],
            "pot": state["pot"],
            "current_bet": state["current_bet"],
            "min_raise": state["min_raise"],
            "to_act_seat": state["to_act_seat"],
            "dealer_seat": state["dealer_seat"],
            "sb_seat": state.get("sb_seat"),
            "bb_seat": state.get("bb_seat"),
            "players": players_pub,
            "actions": state["actions"],
            "started_at": hand.started_at.isoformat() + "Z" if hand.started_at else None,
            "my_hole_cards": my_hole,
        }

    # Derniere main terminee (pour afficher le resultat ~5s apres la fin)
    last_done = (
        db.query(PokerHand)
          .filter(PokerHand.table_id == table.id,
                  PokerHand.ended_at.isnot(None))
          .order_by(PokerHand.id.desc())
          .first()
    )
    last_done_view = None
    if last_done is not None:
        try:
            settlement = json.loads(last_done.winners_json) if last_done.winners_json else None
        except Exception:
            settlement = None
        last_done_view = {
            "id": last_done.id,
            "hand_number": last_done.hand_number,
            "board": last_done.board_cards.split(" ") if last_done.board_cards else [],
            "pot": int(last_done.pot or 0),
            "settlement": settlement,
            "ended_at": last_done.ended_at.isoformat() + "Z" if last_done.ended_at else None,
        }

    cs = can_start_hand(db, table)
    return {
        "table": table_dict(table),
        "sessions": sessions_view,
        "hand": hand_view,
        "last_hand": last_done_view,
        "can_start_hand": cs["can_start"],
        "start_hand_reason": cs["reason"],
    }


def can_start_hand(db: Session, table: PokerTable) -> dict:
    """
    Indique si une nouvelle main peut etre lancee. Retourne :
      {can_start: bool, reason: Optional[str], eligible_count: int}
    """
    if table.status != "open":
        return {"can_start": False, "reason": "Table fermee",
                "eligible_count": 0}
    if _current_hand(db, table.id) is not None:
        return {"can_start": False, "reason": "Main deja en cours",
                "eligible_count": 0}
    sessions = _active_sessions(db, table.id)
    eligible = [s for s in sessions if s.stack >= table.blind_big]
    if len(eligible) < 2:
        return {
            "can_start": False,
            "reason": (
                "Il faut au moins 2 joueurs avec un stack ≥ big blind"
                if sessions else "Personne a table"
            ),
            "eligible_count": len(eligible),
        }
    return {"can_start": True, "reason": None, "eligible_count": len(eligible)}


# ═══════════════════════════════════════════════════════════════════
#  Serialiseurs
# ═══════════════════════════════════════════════════════════════════

def table_dict(t: PokerTable) -> dict:
    return {
        "id": t.id,
        "name": t.name,
        "blind_small": int(t.blind_small),
        "blind_big": int(t.blind_big),
        "min_buyin": int(t.min_buyin),
        "max_buyin": int(t.max_buyin),
        "max_players": int(t.max_players),
        "status": t.status,
        "creator_username": t.creator_username,
        "created_at": t.created_at.isoformat() + "Z" if t.created_at else None,
    }


def hand_history_dict(h: PokerHand) -> dict:
    """Serialise une main finie pour /me/poker/history."""
    try:
        settlement = json.loads(h.winners_json) if h.winners_json else None
    except Exception:
        settlement = None
    return {
        "id": h.id,
        "table_id": h.table_id,
        "hand_number": h.hand_number,
        "board": h.board_cards.split(" ") if h.board_cards else [],
        "pot": int(h.pot or 0),
        "settlement": settlement,
        "started_at": h.started_at.isoformat() + "Z" if h.started_at else None,
        "ended_at": h.ended_at.isoformat() + "Z" if h.ended_at else None,
    }
