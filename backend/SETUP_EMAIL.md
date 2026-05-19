# Configuration SMTP pour les notifications email

Le backend envoie 2 types d'emails :
- **À toi (admin)** quand un user crée une demande d'achat/vente
- **Au user** quand tu marques sa demande comme "traitée" dans le backoffice

L'envoi se fait via SMTP. Le plus simple : **Gmail avec un App Password**.

## 1. Activer la 2FA sur ton compte Gmail

Ouvre <https://myaccount.google.com/security> et active la **vérification en deux étapes**.
C'est obligatoire pour pouvoir générer un App Password (Google n'autorise plus l'auth SMTP avec ton mot de passe principal).

## 2. Créer un App Password dédié

Va sur <https://myaccount.google.com/apppasswords>.

- Si la page est introuvable : c'est que la 2FA n'est pas activée. Reviens à l'étape 1.
- Tape un nom (ex: `CamplongCoin backend`) → **Créer**.
- Google te montre un mot de passe de **16 caractères** (format `xxxx xxxx xxxx xxxx`). **Copie-le maintenant**, il ne sera plus jamais affiché.

## 3. Ajouter les variables dans ton `.env` backend

```bash
# Email (Gmail)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=hugo.philipp99@gmail.com
SMTP_PASSWORD=xxxxxxxxxxxxxxxx        # ← App Password sans les espaces
SMTP_FROM=hugo.philipp99@gmail.com    # peut être identique à SMTP_USER
ADMIN_EMAIL=hugo.philipp99@gmail.com  # destinataire des notifs admin

# URL publique du front (pour les liens dans les emails)
FRONTEND_URL=https://camplongcoin.example.com
```

## 4. Vérifier l'install (dépendances)

Le validateur `EmailStr` de Pydantic nécessite le package `email-validator`. Si pas déjà présent, ajoute dans `requirements.txt` :

```
pydantic[email]>=2.0
```

Puis :
```bash
pip install -r requirements.txt
```

## 5. Tester rapidement

Une fois le backend redémarré, crée une demande d'achat depuis l'interface user. Tu dois recevoir un email dans la minute sur `hugo.philipp99@gmail.com`. Si rien n'arrive :

```bash
# Vérifie les logs du backend
docker logs <ton-container-backend> | grep email
# ou en local
uvicorn main:app --reload   # les erreurs apparaissent dans le terminal
```

Tu devrais voir soit :
- `INFO  Email envoye a ... : ...` → tout va bien
- `ERROR Echec d'envoi d'email a ...` → vérifier user/password/SMTP_HOST

## Alternatives à Gmail

Si tu veux un truc plus pro (limite Gmail = 500 emails/jour, parfait pour ton usage mais bon) :

| Service | SMTP | Free tier |
|---|---|---|
| **Resend** | smtp.resend.com:587 | 100 / jour, gratuit |
| **Brevo** (ex-Sendinblue) | smtp-relay.brevo.com:587 | 300 / jour |
| **SendGrid** | smtp.sendgrid.net:587 | 100 / jour |
| **Mailgun** | smtp.mailgun.org:587 | 3 mois gratuits puis payant |

Pour CamplongCoin (entre potes, quelques demandes par jour), Gmail suffit largement.

## Comportement en cas d'erreur SMTP

Si SMTP n'est pas configuré (`SMTP_HOST` vide) ou si l'envoi échoue, **l'application continue de fonctionner normalement**. La demande est bien créée en base, juste l'email ne part pas. C'est intentionnel : un email cassé ne doit jamais bloquer une transaction métier.

Tu retrouves toutes les demandes dans le backoffice à l'onglet "Demandes" même sans email.
