import datetime
import bcrypt
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Query
from sqlalchemy.orm import Session
from eth_account import Account
from jose import jwt

from database import get_db
from models import (
    User, Transaction, MarketOrder,
    Bet, BetOption, BetParticipation,
    CoinflipRound, RouletteSpin, SlotsSpin,
    MilkPool, MilkChaosEvent, MilkTrade, MilkChaosTemplate,
)
from schemas import (
    AdminLoginIn, CreateUserIn, AmountIn, UpdateOrderIn, ResolveBetIn,
    SettingUpdateIn,
    AdminMilkCreatePoolIn, AdminMilkUpdatePoolIn, AdminMilkInjectIn,
    AdminMilkTemplateIn, AdminMilkTemplateUpdateIn,
    AnalyticsLabelIn,
)
from security import require_admin, fernet
from blockchain import admin_transfer, get_balance_camp, get_balance_eth, treasury
from email_service import send_user_order_done
from config import ADMIN_PASSWORD, JWT_SECRET
from services import escrow, coinflip, roulette, slots, milk as milk_svc
from services import settings as settings_svc
from services import analytics as analytics_svc
from routers.bets import (
    _bet_dict, _settle_resolved, _participations_for, _options_for,
    BETS_ESCROW_ROLE, ADMIN_RESOLVED_BY,
)

router = APIRouter(prefix="/admin", tags=["admin"])

# ─── Auth ──────────────────────────────────────────────

@router.post("/login")
def admin_login(body: AdminLoginIn):
    if body.password != ADMIN_PASSWORD:
        raise HTTPException(401, "Mot de passe incorrect")
    exp = datetime.datetime.utcnow() + datetime.timedelta(days=1)
    token = jwt.encode({"sub": "admin", "role": "admin", "exp": exp},
                       JWT_SECRET, algorithm="HS256")
    return {"token": token}


# ─── Treasury ──────────────────────────────────────────

@router.get("/treasury")
def get_treasury(_: bool = Depends(require_admin)):
    return {
        "address": treasury.address,
        "balance_eth": get_balance_eth(treasury.address),
        "balance_camp": get_balance_camp(treasury.address),
    }


# ─── Users ─────────────────────────────────────────────

@router.get("/users")
def list_all_users(_: bool = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.query(User).order_by(User.created_at).all()
    return [
        {
            "username": u.username,
            "address": u.address,
            "email": u.email,
            "created_at": u.created_at.isoformat() + "Z" if u.created_at else None,
            "balance_camp": get_balance_camp(u.address),
        }
        for u in rows
    ]


@router.post("/users")
def create_user(
    body: CreateUserIn,
    _: bool = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if db.get(User, body.username):
        raise HTTPException(400, f"Username '{body.username}' deja pris")

    acct = Account.create()
    enc_pk = fernet.encrypt(acct.key.hex().encode()).decode()
    pwd_hash = bcrypt.hashpw(body.user_password.encode(), bcrypt.gensalt()).decode()

    new_user = User(
        username=body.username,
        password_hash=pwd_hash,
        address=acct.address,
        encrypted_private_key=enc_pk,
        email=body.email,
    )
    db.add(new_user)
    db.commit()

    camp_tx = None
    if body.initial_camp > 0:
        treasury_bal = get_balance_camp(treasury.address)
        if body.initial_camp > treasury_bal:
            raise HTTPException(400, f"Treasury insuffisante ({treasury_bal} CAMP)")
        camp_tx = admin_transfer(db, treasury.address, acct.address, body.initial_camp)
        db.add(Transaction(
            ts=datetime.datetime.utcnow(),
            from_username="__treasury__",
            to_username=body.username,
            amount=body.initial_camp,
            note="onboarding",
            tx_hash=camp_tx,
        ))
        db.commit()

    return {
        "username": body.username,
        "address": acct.address,
        "email": body.email,
        "camp_tx": camp_tx,
        "initial_camp": body.initial_camp,
    }


@router.delete("/users/{username}")
def delete_user(
    username: str,
    _: bool = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Supprime un user. Refuse si le user a encore du CAMD on-chain
    (l'admin doit d'abord debiter manuellement via /admin/debit pour
    eviter de laisser des CAMP orphelins).
    Les transactions liees au user sont conservees (audit), seules
    les market_orders sont supprimees en cascade.
    """
    user = db.get(User, username)
    if not user:
        raise HTTPException(404, f"User '{username}' introuvable")

    balance = get_balance_camp(user.address)
    if balance > 0:
        raise HTTPException(
            400,
            f"User a encore {balance} CAMP. Debite-le d'abord via Debiter "
            f"avant suppression."
        )

    # Cascade : on supprime les orders associes (audit transactions reste)
    db.query(MarketOrder).filter(MarketOrder.username == username).delete()
    db.delete(user)
    db.commit()

    return {"status": "deleted", "username": username}


# ─── Credit / Debit ────────────────────────────────────

@router.post("/credit")
def credit_user(
    body: AmountIn,
    _: bool = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.get(User, body.username)
    if not user:
        raise HTTPException(404, f"User '{body.username}' introuvable")

    treasury_bal = get_balance_camp(treasury.address)
    if body.amount > treasury_bal:
        raise HTTPException(400, f"Treasury insuffisante ({treasury_bal} CAMP)")

    tx_hash = admin_transfer(db, treasury.address, user.address, body.amount)

    db.add(Transaction(
        ts=datetime.datetime.utcnow(),
        from_username="__treasury__",
        to_username=user.username,
        amount=body.amount,
        note=body.note or "credit admin",
        tx_hash=tx_hash,
    ))
    db.commit()

    return {
        "tx_hash": tx_hash,
        "username": user.username,
        "new_balance_camp": get_balance_camp(user.address),
    }


@router.post("/debit")
def debit_user(
    body: AmountIn,
    _: bool = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.get(User, body.username)
    if not user:
        raise HTTPException(404, f"User '{body.username}' introuvable")

    user_bal = get_balance_camp(user.address)
    if body.amount > user_bal:
        raise HTTPException(400, f"User n'a que {user_bal} CAMP")

    tx_hash = admin_transfer(db, user.address, treasury.address, body.amount)

    db.add(Transaction(
        ts=datetime.datetime.utcnow(),
        from_username=user.username,
        to_username="__treasury__",
        amount=body.amount,
        note=body.note or "debit admin",
        tx_hash=tx_hash,
    ))
    db.commit()

    return {
        "tx_hash": tx_hash,
        "username": user.username,
        "new_balance_camp": get_balance_camp(user.address),
    }


# ─── Market Orders ─────────────────────────────────────

def _order_dict(o: MarketOrder, user_email: str | None) -> dict:
    return {
        "id": o.id,
        "ts": o.ts.isoformat() + "Z" if o.ts else None,
        "username": o.username,
        "user_email": user_email,
        "type": o.type,
        "amount_camp": o.amount_camp,
        "amount_eur": o.amount_eur,
        "handle": o.handle or "",
        "note": o.note or "",
        "status": o.status,
        "admin_note": o.admin_note or "",
        "done_at": o.done_at.isoformat() + "Z" if o.done_at else None,
        "tx_hash": o.tx_hash,
    }


@router.get("/orders")
def list_orders(
    status: str = Query("all", pattern="^(all|pending|done|cancelled)$"),
    _: bool = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Liste les demandes d'achat/vente, jointes avec l'email du user."""
    q = (
        db.query(MarketOrder, User.email)
          .outerjoin(User, User.username == MarketOrder.username)
          .order_by(MarketOrder.ts.desc())
    )
    if status != "all":
        q = q.filter(MarketOrder.status == status)

    return [_order_dict(o, em) for o, em in q.all()]


@router.patch("/orders/{order_id}")
def update_order(
    order_id: int,
    body: UpdateOrderIn,
    background_tasks: BackgroundTasks,
    _: bool = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Met a jour le statut et/ou la note admin d'une demande.

    Quand on bascule en 'done' depuis un autre statut :
      1. On execute le mouvement on-chain (atomique : si la tx echoue,
         le statut n'est pas mis a jour) :
         - BUY  -> adminTransfer(treasury -> user)  : user recoit ses CAMP
         - SELL -> adminTransfer(user -> treasury) : user envoie ses CAMP
      2. On log la tx dans la table transactions (pour l'historique user)
      3. On stocke le tx_hash sur l'order
      4. On envoie un email de confirmation au user (en background)

    Si on repasse en 'pending' ou 'cancelled' apres avoir ete 'done',
    le tx_hash et done_at sont conserves (audit, le mouvement on-chain
    est irreversible de toute facon).
    """
    order = db.get(MarketOrder, order_id)
    if not order:
        raise HTTPException(404, f"Order #{order_id} introuvable")

    previous_status = order.status
    becoming_done = body.status == "done" and previous_status != "done"

    # ─── Etape 1 : si on passe en done, on fait le mouvement on-chain
    # AVANT de toucher au statut. Si ca rate, l'order reste en pending.
    if becoming_done:
        user = db.get(User, order.username)
        if not user:
            raise HTTPException(
                400,
                f"Impossible de finaliser : user '{order.username}' n'existe plus"
            )

        if order.tx_hash:
            # Garde-fou : si l'order a deja un tx_hash, c'est qu'elle a deja
            # ete done une fois et qu'on l'a re-repassee en pending. On ne refait
            # PAS le transfert (le mouvement on-chain est irreversible).
            # On accepte juste de re-marquer le statut sans nouveau transfert.
            pass
        else:
            if order.type == "buy":
                # Treasury envoie les CAMP au user (le user a paye en EUR)
                treasury_bal = get_balance_camp(treasury.address)
                if order.amount_camp > treasury_bal:
                    raise HTTPException(
                        400,
                        f"Treasury insuffisante : {treasury_bal} CAMP disponibles, "
                        f"il en faut {order.amount_camp}. Refund ta treasury d'abord."
                    )
                from_addr, to_addr = treasury.address, user.address
                tx_from_user = "__treasury__"
                tx_to_user = order.username
                tx_note = f"order #{order.id} buy"
            else:
                # SELL : on debite le user (Hugo lui a envoye les EUR)
                user_bal = get_balance_camp(user.address)
                if order.amount_camp > user_bal:
                    raise HTTPException(
                        400,
                        f"Le user n'a que {user_bal} CAMP, impossible de debiter "
                        f"{order.amount_camp}. Il a peut-etre transfere depuis sa "
                        f"demande."
                    )
                from_addr, to_addr = user.address, treasury.address
                tx_from_user = order.username
                tx_to_user = "__treasury__"
                tx_note = f"order #{order.id} sell"

            # Execute la tx on-chain. Si ca raise, FastAPI rollback la transaction DB
            # et renvoie le detail en HTTP 500. L'order reste en pending.
            try:
                tx_hash = admin_transfer(db, from_addr, to_addr, order.amount_camp)
            except Exception as e:
                db.rollback()
                raise HTTPException(
                    500,
                    f"Echec du transfert on-chain : {e}. L'order reste en pending."
                )

            # Log dans la table transactions (pour l'historique du user)
            db.add(Transaction(
                ts=datetime.datetime.utcnow(),
                from_username=tx_from_user,
                to_username=tx_to_user,
                amount=order.amount_camp,
                note=tx_note,
                tx_hash=tx_hash,
            ))

            order.tx_hash = tx_hash

        # done_at se met a jour meme si on saute le transfert (re-done)
        order.done_at = datetime.datetime.utcnow()

    # ─── Etape 2 : update du statut et/ou note
    if body.status is not None:
        order.status = body.status

    if body.admin_note is not None:
        order.admin_note = body.admin_note

    db.commit()
    db.refresh(order)

    # ─── Etape 3 : email user (background, ne bloque pas)
    if becoming_done:
        user = db.get(User, order.username)
        if user and user.email:
            background_tasks.add_task(
                send_user_order_done,
                _order_dict(order, user.email),
                user.email,
            )

    user_email = db.query(User.email).filter(User.username == order.username).scalar()
    return _order_dict(order, user_email)


@router.delete("/orders/{order_id}")
def delete_order(
    order_id: int,
    _: bool = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Supprime definitivement une demande (utile si test/erreur)."""
    order = db.get(MarketOrder, order_id)
    if not order:
        raise HTTPException(404, f"Order #{order_id} introuvable")
    db.delete(order)
    db.commit()
    return {"status": "deleted", "id": order_id}


# ─── Bets (admin) ──────────────────────────────────────


@router.get("/bets")
def admin_list_bets(
    status: str = Query("all", pattern="^(all|open|resolved|cancelled|expired)$"),
    _: bool = Depends(require_admin),
    db: Session = Depends(get_db),
):
    q = db.query(Bet).order_by(Bet.created_at.desc())
    if status != "all":
        q = q.filter(Bet.status == status)
    return [_bet_dict(db, b) for b in q.all()]


@router.post("/bets/{bet_id}/resolve")
def admin_resolve_bet(
    bet_id: int,
    body: ResolveBetIn,
    background_tasks: BackgroundTasks,
    _: bool = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Force-resolve par l'admin. body.option_id = NULL = void (refund tous).
    Sinon : payout reparti egalement entre les participants de l'option
    designee. Si l'option n'a aucun participant ou si une seule option a
    des participants, force le void (cf. _settle_resolved).
    """
    bet = (
        db.query(Bet)
          .filter(Bet.id == bet_id)
          .with_for_update()
          .first()
    )
    if not bet:
        raise HTTPException(404, "Pari introuvable")
    if bet.status != "open":
        raise HTTPException(400, f"Pari non resolvable (statut: {bet.status})")

    if body.option_id is not None:
        opt = (
            db.query(BetOption)
              .filter(BetOption.id == body.option_id, BetOption.bet_id == bet_id)
              .first()
        )
        if not opt:
            raise HTTPException(400, "Option invalide pour ce pari")

    try:
        _settle_resolved(
            db, bet,
            resolution_option_id=body.option_id,
            resolved_by=ADMIN_RESOLVED_BY,
            background_tasks=background_tasks,
        )
    except escrow.EscrowError as e:
        db.rollback()
        raise HTTPException(400, str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Echec du settlement on-chain : {e}")

    db.commit()
    db.refresh(bet)
    return _bet_dict(db, bet)


@router.post("/bets/{bet_id}/cancel")
def admin_cancel_bet(
    bet_id: int,
    _: bool = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Force-cancel : refund de tous les participants. Refus sur 'resolved'
    (les fonds sont deja distribues, irreversibles). Sur 'cancelled' ou
    'expired' : no-op.
    """
    bet = (
        db.query(Bet)
          .filter(Bet.id == bet_id)
          .with_for_update()
          .first()
    )
    if not bet:
        raise HTTPException(404, "Pari introuvable")
    if bet.status == "resolved":
        raise HTTPException(400, "Pari deja resolu, fonds distribues - impossible d'annuler")
    if bet.status in ("cancelled", "expired"):
        return _bet_dict(db, bet)

    parts = _participations_for(db, bet.id)

    try:
        for p in parts:
            u = db.get(User, p.username)
            if not u:
                continue
            tx = escrow.release(
                db, BETS_ESCROW_ROLE, u, p.amount,
                f"bet #{bet.id} admin cancel refund",
            )
            p.tx_hash_payout = tx
    except escrow.EscrowError as e:
        db.rollback()
        raise HTTPException(400, str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Echec du refund on-chain : {e}")

    bet.status = "cancelled"
    bet.resolution_void = True
    bet.resolved_at = datetime.datetime.utcnow()
    bet.resolved_by = ADMIN_RESOLVED_BY
    db.commit()
    db.refresh(bet)
    return _bet_dict(db, bet)


@router.delete("/bets/{bet_id}")
def admin_delete_bet(
    bet_id: int,
    _: bool = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Suppression DB definitive. N'annule PAS les mouvements on-chain.
    Refus sur 'open' avec participants (fonds escrowes) et sur 'resolved'.
    Force-cancel d'abord pour les paris avec mouvements actifs.
    """
    bet = db.get(Bet, bet_id)
    if not bet:
        raise HTTPException(404, "Pari introuvable")
    if bet.status == "resolved":
        raise HTTPException(
            400,
            f"Pari resolved : suppression refusee (audit on-chain)."
        )
    if bet.status == "open":
        parts_count = (
            db.query(BetParticipation)
              .filter(BetParticipation.bet_id == bet.id)
              .count()
        )
        if parts_count > 0:
            raise HTTPException(
                400,
                f"Pari open avec {parts_count} participation(s) : "
                f"force-cancel d'abord (POST /admin/bets/{bet_id}/cancel)"
            )
    # cascade delete via FK ON DELETE CASCADE supprime options/participations/votes
    db.delete(bet)
    db.commit()
    return {"status": "deleted", "id": bet_id}


# ─── App settings (parametres modifiables a chaud) ─────

@router.get("/settings")
def admin_list_settings(
    _: bool = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Liste toutes les settings + leur description (lecture seule)."""
    return settings_svc.list_all(db)


@router.patch("/settings/{key}")
def admin_update_setting(
    key: str,
    body: SettingUpdateIn,
    _: bool = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Met a jour une setting. Le set de cles autorisees est blanchi cote
    service pour eviter qu'un admin n'introduise des cles fantaisistes.
    Validation par-cle pour les types numeriques + bornes raisonnables.
    """
    if key not in settings_svc.WRITABLE_KEYS:
        raise HTTPException(
            400,
            f"Setting '{key}' inconnue. Cles autorisees : {sorted(settings_svc.WRITABLE_KEYS)}"
        )

    value = body.value.strip()

    # ─── Validations par cle (defense en profondeur)
    if key == "coinflip_edge_pct":
        try:
            v = float(value)
        except ValueError:
            raise HTTPException(400, "edge_pct doit etre un nombre (ex: '2' ou '2.5')")
        if v < 0 or v >= 50:
            raise HTTPException(400, "edge_pct doit etre dans [0, 50[")
    elif key in ("coinflip_min_bet", "coinflip_max_bet",
                 "roulette_min_bet", "roulette_max_bet",
                 "slots_min_bet", "slots_max_bet"):
        try:
            v = int(value)
        except ValueError:
            raise HTTPException(400, f"{key} doit etre un entier")
        if v <= 0:
            raise HTTPException(400, f"{key} doit etre > 0")
        # Coherence min <= max sur la meme famille (coinflip/roulette/slots)
        family = key.rsplit("_", 2)[0]   # "coinflip" | "roulette" | "slots"
        if key.endswith("_min_bet"):
            cur_max = settings_svc.get_int(db, f"{family}_max_bet", 200)
            if v > cur_max:
                raise HTTPException(400, f"min_bet ({v}) > max_bet ({cur_max})")
        else:
            cur_min = settings_svc.get_int(db, f"{family}_min_bet", 1)
            if v < cur_min:
                raise HTTPException(400, f"max_bet ({v}) < min_bet ({cur_min})")
    elif key == "milk_chaos_tick_seconds":
        try:
            v = int(value)
        except ValueError:
            raise HTTPException(400, "milk_chaos_tick_seconds doit etre un entier")
        if v < 60 or v > 86400:
            raise HTTPException(
                400,
                "milk_chaos_tick_seconds doit etre dans [60, 86400] (1 min a 24h)"
            )
    elif key == "milk_chaos_proba_pct":
        try:
            v = int(value)
        except ValueError:
            raise HTTPException(400, "milk_chaos_proba_pct doit etre un entier (0-100)")
        if v < 0 or v > 100:
            raise HTTPException(400, "milk_chaos_proba_pct doit etre dans [0, 100]")
    elif key == "milk_chaos_max_volatility_pct":
        try:
            v = int(value)
        except ValueError:
            raise HTTPException(
                400, "milk_chaos_max_volatility_pct doit etre un entier (0-100)"
            )
        if v < 0 or v > 100:
            raise HTTPException(
                400, "milk_chaos_max_volatility_pct doit etre dans [0, 100] "
                     "(0 = bot mute, 100 = sans cap)"
            )

    row = settings_svc.set_value(db, key, value)
    db.commit()
    db.refresh(row)
    return {
        "key": row.key,
        "value": row.value,
        "description": row.description,
        "updated_at": row.updated_at.isoformat() + "Z" if row.updated_at else None,
    }


# ─── Casino stats (vue d'ensemble admin) ───────────────

@router.get("/casino/stats")
def admin_casino_stats(
    _: bool = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Snapshot pour le dashboard admin casino :
      - solde du compte systeme casino_bank
      - nombre total de rounds + PnL casino cumule
      - 20 dernieres rounds (toutes confondues, pour debug)
      - parametres courants (edge, limites)

    Le PnL casino = somme(bet_amount) - somme(payout) : positif si le casino
    gagne globalement. Avec un edge de 2%, on attend ~+2% du volume mise.
    """
    # Compte systeme casino_bank (peut etre absent au tout debut)
    try:
        bank = escrow.get_system_account(db, coinflip.CASINO_BANK_ROLE)
        bank_balance = get_balance_camp(bank.address)
        bank_addr = bank.address
    except escrow.EscrowError:
        bank_balance = 0
        bank_addr = None

    total_rounds = db.query(CoinflipRound).count()

    # PnL casino : agrega bet et payout en SQL pour ne pas tout charger
    from sqlalchemy import func as sqlfunc
    pnl_row = (
        db.query(
            sqlfunc.coalesce(sqlfunc.sum(CoinflipRound.bet_amount), 0),
            sqlfunc.coalesce(sqlfunc.sum(CoinflipRound.payout), 0),
        ).first()
    )
    total_bet = int(pnl_row[0] or 0)
    total_payout = int(pnl_row[1] or 0)
    pnl = total_bet - total_payout

    # 20 dernieres rounds coinflip
    recent = (
        db.query(CoinflipRound)
          .order_by(CoinflipRound.ts.desc())
          .limit(20)
          .all()
    )

    # ─── Roulette stats
    r_total_rounds = db.query(RouletteSpin).count()
    r_pnl_row = (
        db.query(
            sqlfunc.coalesce(sqlfunc.sum(RouletteSpin.total_bet), 0),
            sqlfunc.coalesce(sqlfunc.sum(RouletteSpin.total_payout), 0),
        ).first()
    )
    r_total_bet = int(r_pnl_row[0] or 0)
    r_total_payout = int(r_pnl_row[1] or 0)
    r_pnl = r_total_bet - r_total_payout

    r_recent = (
        db.query(RouletteSpin)
          .order_by(RouletteSpin.ts.desc())
          .limit(20)
          .all()
    )

    # ─── Slots stats
    s_total_spins = db.query(SlotsSpin).count()
    s_pnl_row = (
        db.query(
            sqlfunc.coalesce(sqlfunc.sum(SlotsSpin.bet_amount), 0),
            sqlfunc.coalesce(sqlfunc.sum(SlotsSpin.payout), 0),
        ).first()
    )
    s_total_bet = int(s_pnl_row[0] or 0)
    s_total_payout = int(s_pnl_row[1] or 0)
    s_pnl = s_total_bet - s_total_payout

    s_recent = (
        db.query(SlotsSpin)
          .order_by(SlotsSpin.ts.desc())
          .limit(20)
          .all()
    )

    return {
        "bank": {
            "role": coinflip.CASINO_BANK_ROLE,
            "address": bank_addr,
            "balance_camp": bank_balance,
        },
        "coinflip": {
            "rounds_total": total_rounds,
            "volume_bet": total_bet,
            "volume_payout": total_payout,
            "pnl_camp": pnl,
            "rtp_observed_pct": (
                round(100 * total_payout / total_bet, 2) if total_bet else None
            ),
            "edge_configured_pct": settings_svc.get_float(db, "coinflip_edge_pct", 2.0),
            "min_bet": settings_svc.get_int(db, "coinflip_min_bet", 1),
            "max_bet": settings_svc.get_int(db, "coinflip_max_bet", 200),
        },
        "roulette": {
            "spins_total": r_total_rounds,
            "volume_bet": r_total_bet,
            "volume_payout": r_total_payout,
            "pnl_camp": r_pnl,
            "rtp_observed_pct": (
                round(100 * r_total_payout / r_total_bet, 2) if r_total_bet else None
            ),
            # Edge mecanique fixe (1/37). Pas configurable.
            "edge_mechanical_pct": round(100 / 37, 2),
            "min_bet": settings_svc.get_int(db, "roulette_min_bet", 1),
            "max_bet": settings_svc.get_int(db, "roulette_max_bet", 200),
        },
        "slots": {
            "spins_total": s_total_spins,
            "volume_bet": s_total_bet,
            "volume_payout": s_total_payout,
            "pnl_camp": s_pnl,
            "rtp_observed_pct": (
                round(100 * s_total_payout / s_total_bet, 2) if s_total_bet else None
            ),
            # RTP theorique calcule depuis les poids + payouts hardcoded
            "rtp_theoretical_pct": slots.theoretical_rtp_pct(),
            "edge_mechanical_pct": round(100 - slots.theoretical_rtp_pct(), 2),
            "min_bet": settings_svc.get_int(db, "slots_min_bet", 1),
            "max_bet": settings_svc.get_int(db, "slots_max_bet", 100),
        },
        "recent_rounds": [coinflip.history_dict(r) for r in recent],
        "recent_spins": [roulette.history_dict(r) for r in r_recent],
        "recent_slots": [slots.history_dict(r) for r in s_recent],
    }


# ─── Milk (Bourse du Lait) ─────────────────────────────

@router.get("/milk/pools")
def admin_list_milk_pools(
    _: bool = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Liste tous les pools + solde CAMP du wallet (pour debug treasury)."""
    rows = db.query(MilkPool).order_by(MilkPool.created_at.asc()).all()
    out = []
    for p in rows:
        d = milk_svc.pool_dict(p)
        try:
            sys_acc = escrow.get_system_account(db, p.system_role)
            d["pool_wallet_balance_camp"] = get_balance_camp(sys_acc.address)
            d["pool_wallet_address"] = sys_acc.address
            d["pool_wallet_username"] = sys_acc.username
        except escrow.EscrowError:
            d["pool_wallet_balance_camp"] = None
            d["pool_wallet_address"] = None
            d["pool_wallet_username"] = None
        # Stats simples (volume trades, nb chaos events)
        trades_count = db.query(MilkTrade).filter(MilkTrade.pool_id == p.id).count()
        chaos_count = db.query(MilkChaosEvent).filter(MilkChaosEvent.pool_id == p.id).count()
        d["trades_count"] = trades_count
        d["chaos_count"] = chaos_count
        out.append(d)
    return out


@router.post("/milk/pools")
def admin_create_milk_pool(
    body: AdminMilkCreatePoolIn,
    _: bool = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Cree un nouveau pool laitier (+ son compte systeme custodial associe).
    Le pool est cree en statut 'paused'. L'admin doit :
      1. Crediter le wallet system du pool de `initial_camp` CAMP depuis
         la treasury (POST /admin/credit username=__pool_<sym>__ amount=…)
      2. Passer le pool en 'active' (PATCH /admin/milk/pools/{id} status=active)
    """
    from eth_account import Account

    if db.query(MilkPool).filter(MilkPool.symbol == body.symbol).first():
        raise HTTPException(400, f"Pool '{body.symbol}' existe deja")

    # Nom system_role + username (convention seed_system_accounts.py).
    # On slugify le symbol : LAIT-DEMI -> lait_demi
    slug = body.symbol.lower().replace("-", "_").replace(" ", "_")
    system_role = f"milk_pool_{slug}"
    username = f"__pool_{slug}__"

    # Garde-fous d'unicite
    if db.query(User).filter(User.system_role == system_role).first():
        raise HTTPException(400, f"system_role '{system_role}' deja pris")
    if db.get(User, username):
        raise HTTPException(400, f"username '{username}' deja pris")

    # Cree le wallet custodial
    acct = Account.create()
    enc_pk = fernet.encrypt(acct.key.hex().encode()).decode()
    sys_user = User(
        username=username,
        password_hash=None,
        address=acct.address,
        encrypted_private_key=enc_pk,
        email=None,
        account_type="system",
        system_role=system_role,
    )
    db.add(sys_user)
    db.flush()

    # Calcul des reserves d'amorcage
    reserve_milk = body.initial_bottles * 1000   # milli-bouteilles
    reserve_camp = body.initial_bottles * body.price_per_bottle

    pool = MilkPool(
        symbol=body.symbol,
        name=body.name,
        system_role=system_role,
        reserve_camp=reserve_camp,
        reserve_milk=reserve_milk,
        fee_pct=body.fee_pct,
        status="paused",
        initial_camp=reserve_camp,
        initial_milk=reserve_milk,
        chaos_enabled=True,
    )
    db.add(pool)
    db.commit()
    db.refresh(pool)

    out = milk_svc.pool_dict(pool)
    out["pool_wallet_address"] = acct.address
    out["pool_wallet_username"] = username
    out["pool_wallet_balance_camp"] = 0
    out["next_step"] = (
        f"Crediter {username} de {reserve_camp} CAMP depuis la treasury, "
        f"puis passer status='active'."
    )
    return out


@router.patch("/milk/pools/{pool_id}")
def admin_update_milk_pool(
    pool_id: int,
    body: AdminMilkUpdatePoolIn,
    _: bool = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Modifie fee_pct, chaos_enabled, status (active/paused) d'un pool."""
    pool = db.get(MilkPool, pool_id)
    if not pool:
        raise HTTPException(404, f"Pool #{pool_id} introuvable")

    if body.status == "active" and pool.status != "active":
        # Garde-fou : on verifie que le wallet system a un solde CAMP
        # >= reserve_camp pour eviter d'activer un pool insolvable.
        try:
            sys_acc = escrow.get_system_account(db, pool.system_role)
            bal = get_balance_camp(sys_acc.address)
        except escrow.EscrowError as e:
            raise HTTPException(400, str(e))
        if bal < pool.reserve_camp:
            raise HTTPException(
                400,
                f"Wallet pool ({sys_acc.username}) a {bal} CAMP, "
                f"il en faut {pool.reserve_camp} pour pouvoir honorer "
                f"les sells. Crediter d'abord."
            )

    if body.fee_pct is not None:
        pool.fee_pct = body.fee_pct
    if body.chaos_enabled is not None:
        pool.chaos_enabled = body.chaos_enabled
    if body.status is not None:
        pool.status = body.status

    db.commit()
    db.refresh(pool)
    return milk_svc.pool_dict(pool)


@router.post("/milk/pools/{pool_id}/inject")
def admin_inject_chaos(
    pool_id: int,
    body: AdminMilkInjectIn,
    _: bool = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Inject une variation manuelle de la reserve_milk.
    bottles signe : +50 = ajoute 50 bouteilles, -50 = en retire 50.
    """
    pool = (
        db.query(MilkPool)
          .filter(MilkPool.id == pool_id)
          .with_for_update()
          .first()
    )
    if not pool:
        raise HTTPException(404, f"Pool #{pool_id} introuvable")

    delta_milk = body.bottles * 1000   # milli-bouteilles
    event = milk_svc.apply_chaos(
        db, pool,
        kind=body.kind,
        delta_milk=delta_milk,
        narrative=body.narrative,
        triggered_by="admin",
    )
    if event is None:
        raise HTTPException(
            400,
            "Garde-fou declenche : la reserve passerait sous 1 bouteille. Refus."
        )
    db.commit()
    db.refresh(event)
    return milk_svc.chaos_dict(event)


@router.get("/milk/chaos")
def admin_chaos_history(
    pool_id: int | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    _: bool = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Historique des events chaos (bot + admin). Filtre optionnel par pool."""
    q = db.query(MilkChaosEvent).order_by(MilkChaosEvent.ts.desc())
    if pool_id is not None:
        q = q.filter(MilkChaosEvent.pool_id == pool_id)
    rows = q.limit(limit).all()
    return [milk_svc.chaos_dict(e) for e in rows]


@router.get("/milk/trades")
def admin_recent_trades(
    pool_id: int | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    _: bool = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Trades les plus recents (filtrables par pool)."""
    q = db.query(MilkTrade).order_by(MilkTrade.ts.desc())
    if pool_id is not None:
        q = q.filter(MilkTrade.pool_id == pool_id)
    rows = q.limit(limit).all()
    return [milk_svc.trade_dict(t) for t in rows]


# ─── Milk chaos templates (CRUD) ───────────────────────

@router.get("/milk/templates")
def admin_list_chaos_templates(
    _: bool = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Liste tous les templates (enabled ou non) tries par poids decroissant."""
    rows = (
        db.query(MilkChaosTemplate)
          .order_by(MilkChaosTemplate.enabled.desc(),
                    MilkChaosTemplate.weight.desc(),
                    MilkChaosTemplate.slug.asc())
          .all()
    )
    return [milk_svc.template_dict(t) for t in rows]


def _validate_delta_range(delta_type: str, delta_min: float, delta_max: float) -> None:
    if delta_min > delta_max:
        raise HTTPException(400, "delta_min doit etre <= delta_max")
    if delta_type == "pct":
        if abs(delta_min) > 100 or abs(delta_max) > 100:
            raise HTTPException(
                400, "delta_pct doit etre dans [-100, 100] (sinon drain instantane)"
            )
    elif delta_type == "bottles":
        if abs(delta_min) > 100_000 or abs(delta_max) > 100_000:
            raise HTTPException(
                400, "delta_bottles doit etre dans [-100000, 100000]"
            )


@router.post("/milk/templates")
def admin_create_chaos_template(
    body: AdminMilkTemplateIn,
    _: bool = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Cree un nouveau template chaos."""
    if db.query(MilkChaosTemplate).filter_by(slug=body.slug).first():
        raise HTTPException(400, f"Template '{body.slug}' existe deja")
    _validate_delta_range(body.delta_type, body.delta_min, body.delta_max)

    tpl = MilkChaosTemplate(
        slug=body.slug,
        kind=body.kind,
        delta_type=body.delta_type,
        delta_min=body.delta_min,
        delta_max=body.delta_max,
        narrative=body.narrative,
        weight=body.weight,
        enabled=body.enabled,
    )
    db.add(tpl)
    db.commit()
    db.refresh(tpl)
    return milk_svc.template_dict(tpl)


@router.patch("/milk/templates/{tpl_id}")
def admin_update_chaos_template(
    tpl_id: int,
    body: AdminMilkTemplateUpdateIn,
    _: bool = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Update partielle d'un template."""
    tpl = db.get(MilkChaosTemplate, tpl_id)
    if not tpl:
        raise HTTPException(404, f"Template #{tpl_id} introuvable")

    # Pre-resolve les valeurs cibles pour valider la coherence du range
    new_dtype = body.delta_type or tpl.delta_type
    new_min = body.delta_min if body.delta_min is not None else tpl.delta_min
    new_max = body.delta_max if body.delta_max is not None else tpl.delta_max
    _validate_delta_range(new_dtype, new_min, new_max)

    if body.kind is not None: tpl.kind = body.kind
    if body.delta_type is not None: tpl.delta_type = body.delta_type
    if body.delta_min is not None: tpl.delta_min = body.delta_min
    if body.delta_max is not None: tpl.delta_max = body.delta_max
    if body.narrative is not None: tpl.narrative = body.narrative
    if body.weight is not None: tpl.weight = body.weight
    if body.enabled is not None: tpl.enabled = body.enabled

    db.commit()
    db.refresh(tpl)
    return milk_svc.template_dict(tpl)


@router.delete("/milk/templates/{tpl_id}")
def admin_delete_chaos_template(
    tpl_id: int,
    _: bool = Depends(require_admin),
    db: Session = Depends(get_db),
):
    tpl = db.get(MilkChaosTemplate, tpl_id)
    if not tpl:
        raise HTTPException(404, f"Template #{tpl_id} introuvable")
    db.delete(tpl)
    db.commit()
    return {"status": "deleted", "id": tpl_id}


@router.post("/milk/templates/{tpl_id}/preview")
def admin_preview_chaos_template(
    tpl_id: int,
    _: bool = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Genere un exemple de narrative rendue (sans modifier la DB) pour aider
    l'admin a verifier ses placeholders avant de sauver.
    """
    tpl = db.get(MilkChaosTemplate, tpl_id)
    if not tpl:
        raise HTTPException(404, f"Template #{tpl_id} introuvable")
    return milk_svc.template_preview(tpl)


@router.get("/milk/chaos/analysis")
def admin_chaos_analysis(
    reference_bottles: int = Query(200, ge=1, le=100_000),
    _: bool = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Esperance d'impact des templates chaos sur la banque (en % de
    reserve_camp). Permet de detecter un catalogue biaise qui draine
    systematiquement la liquidite.

    reference_bottles : pour les templates en delta_type='bottles' on a
    besoin d'un pool de reference (l'impact en % depend de la taille).
    Defaut 200 btl (= reserve d'amorcage standard).

    Inclut les freq settings pour permettre au front d'extrapoler en
    impact/jour.
    """
    max_vol = settings_svc.get_int(db, "milk_chaos_max_volatility_pct", 20)
    analysis = milk_svc.chaos_analysis(
        db,
        reference_reserve_milk=reference_bottles * 1000,
        max_vol_pct=float(max_vol),
    )
    analysis["freq"] = {
        "tick_seconds": settings_svc.get_int(db, "milk_chaos_tick_seconds", 900),
        "proba_pct": settings_svc.get_int(db, "milk_chaos_proba_pct", 25),
        "max_volatility_pct": max_vol,
    }
    return analysis


# ─── Analytics (qui a fait quoi depuis le debut) ───────

def _parse_since(since: str | None) -> datetime.datetime | None:
    """Parse le query param `since` (ISO, UTC). None => defaut du service."""
    if not since:
        return None
    try:
        return datetime.datetime.fromisoformat(since.replace("Z", ""))
    except ValueError:
        raise HTTPException(
            400, f"Date `since` invalide : {since!r} (format ISO attendu)"
        )


@router.get("/analytics")
def admin_analytics(
    _: bool = Depends(require_admin),
    db: Session = Depends(get_db),
    since: str = Query(
        None,
        description="Date ISO de debut de periode (UTC). Defaut : 22/08/2026 20h UTC "
                    "= 22h Paris, le lancement.",
    ),
):
    """
    Vue transverse par joueur : d'ou vient son argent, ou il est maintenant,
    et combien il a gagne ou perdu par activite.

    Le PnL affiche est net des recharges : on compare la valeur totale actuelle
    (wallet + lait + paris bloques + stacks poker) a tout ce qui a ete injecte
    depuis la tresorerie (onboarding + recharges - retraits). Un joueur qui a
    recharge 500 CAMP et qui les a perdus ressort a -500, pas a 0.

    `since` ne filtre que l'activite de jeu (parties, trades, paris) ; les
    depots sont toujours comptes depuis l'origine, sinon le PnL n'a pas de sens.
    """
    return analytics_svc.overview(db, _parse_since(since), get_balance_camp)


@router.get("/analytics/flows")
def admin_analytics_flows(
    _: bool = Depends(require_admin),
    db: Session = Depends(get_db),
    since: str = Query(None, description="Date ISO de debut de periode (UTC)."),
):
    """
    Mouvements user <-> tresorerie avec leur classification courante, pour
    l'ecran d'ajustement.

    `source='auto'` = deduit de la note posee a l'ecriture.
    `source='manual'` = l'admin a corrige.
    """
    return analytics_svc.flows_detail(db, _parse_since(since))


@router.put("/analytics/flows/{tx_id}")
def admin_analytics_set_label(
    tx_id: int,
    body: AnalyticsLabelIn,
    _: bool = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Reclasse un mouvement de tresorerie pour le dashboard.

    N'ecrit que dans `analytics_tx_labels` : la ligne `transactions` d'origine,
    qui reflete un mouvement on-chain reel, n'est jamais modifiee. `label=null`
    retire la correction et revient a la classification automatique.
    """
    try:
        return analytics_svc.set_label(db, tx_id, body.label, body.note or "")
    except ValueError as e:
        raise HTTPException(400, str(e))
