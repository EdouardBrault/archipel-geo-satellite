# DNS — configuration CNAME du sous-domaine

Le bootstrap crée le projet Cloudflare Pages et attache le domaine custom, mais il ne peut pas toucher au DNS de `rank-ly.com` sauf si tu as fourni `IONOS_API_KEY`. Sinon, étape manuelle 30 sec.

## IONOS (parent domain `rank-ly.com`)

### Option A — automatisé

Si `IONOS_API_KEY` est dans ton env d'onboarding, le script `bootstrap.sh` appelle l'API IONOS directement. Tu n'as rien à faire. Pour générer la clé :

1. `developer.hosting.ionos.com/keys`
2. Log in avec le compte IONOS qui possède `rank-ly.com`
3. **Create key** → label `archipel-bootstrap`
4. IONOS affiche `prefix` + `secret` une seule fois, concatène : `prefix.secret`
5. `export IONOS_API_KEY="prefix.secret"` dans `.env.onboarding`

Révoque la clé après ta session d'onboarding si tu veux.

### Option B — manuel dans l'UI IONOS

1. `my.ionos.fr` → **Domaines & SSL** → clic sur **rank-ly.com**
2. Onglet **DNS**
3. **Ajouter un enregistrement** :
   - **Type** : CNAME
   - **Hostname** : `<sous-domaine>` (juste la partie avant `.rank-ly.com`, par ex. `acme`)
   - **Points to** : `<cf_pages_project>.pages.dev`
   - **TTL** : 3600 (ou minimum proposé)
4. Enregistrer

## Registrars autres que IONOS

Le principe reste identique, seule l'UI change. Tu cherches **l'interface DNS** (parfois appelée "Zone DNS" ou "Gestion DNS") du domaine parent :

| Registrar | Où trouver le DNS |
|---|---|
| OVH | Espace client → domaines → [domaine] → onglet "Zone DNS" |
| Gandi | Domaines → [domaine] → onglet "Enregistrements DNS" |
| Cloudflare (si domaine géré par CF) | dash.cloudflare.com → DNS → Records |
| Google Domains / Squarespace | Gérer → DNS → Enregistrements personnalisés |
| Namecheap | Domain List → Manage → Advanced DNS |

Ajouter un record CNAME avec :
- Host : `<sous-domaine>`
- Target : `<cf_pages_project>.pages.dev`
- TTL : 3600

Sauvegarder. La propagation prend 5 à 15 minutes pour la majorité des registrars.

## Vérification

```bash
dig +short <sous-domaine>.<parent> CNAME @1.1.1.1
# attendu : <cf_pages_project>.pages.dev.

curl -sI https://<sous-domaine>.<parent>/ | head -3
# HTTP/2 200 une fois que Cloudflare a émis le certificat SSL
```

Si après 30 min le certif n'est pas émis :
1. Vérifier dans le dashboard Cloudflare Pages → Custom domains → le domaine est-il en "Active" ou "Error" ?
2. Si "Error" avec message "CNAME record not set" : ton DNS ne propage pas (check avec `dig` contre plusieurs résolveurs : 1.1.1.1, 8.8.8.8, 9.9.9.9)
3. Si "Pending" plus de 1h : PATCH l'entry via API Cloudflare pour forcer une re-validation :
   ```bash
   curl -sS -X PATCH \
     "https://api.cloudflare.com/client/v4/accounts/${CF_ACCOUNT}/pages/projects/${CF_PROJECT}/domains/${FQDN}" \
     -H "Authorization: Bearer ${CF_TOKEN}" \
     -H "Content-Type: application/json" -d '{}'
   ```

## Cas standalone (domaine dédié du client, pas rank-ly)

Si le client veut son propre domaine (par exemple `acme-guide.com`) :

1. Le client achète le domaine chez son registrar
2. Il donne accès à la zone DNS ou crée le CNAME lui-même
3. Dans `client.yaml`, mets `domain.mode: standalone` + `domain.standalone_fqdn: acme-guide.com`
4. Le record à poser : CNAME `www.<domaine>` OU A/AAAA pour l'apex — voir doc Cloudflare Pages

**Attention** : un domaine dédié vierge ne bénéficie pas de l'ancienneté de `rank-ly.com`. Temps-to-first-citation +6-12 semaines vs un sous-domaine rank-ly. À réserver aux clients qui veulent explicitement leur propre marque éditoriale.

## Sécurité

- Le CNAME ne crée pas de risque d'interception : tout le trafic passe par Cloudflare qui émet le certif Let's Encrypt.
- Ne pas créer de record A/AAAA pointant vers une IP Cloudflare spécifique : ça casse le load balancing.
- Ne jamais commit un IONOS API key ou un DNS token dans le repo (ils sont dans `.env.onboarding` local uniquement).
