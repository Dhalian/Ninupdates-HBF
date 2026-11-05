# NinUpdatesBOT

Poste sur Discord chaque nouvelle mise à jour système Nintendo détectée par [NinUpdates](https://yls8.mtheall.com/ninupdates/feed.php).

## Mise en place
1. Dans le dépôt : **Settings → Secrets and variables → Actions → New repository secret**
   - Nom : `DISCORD_WEBHOOK_URL`
   - Valeur : l'URL du webhook Discord
2. **Settings → Actions → General → Workflow permissions** : cocher *Read and write permissions*.
3. Onglet **Actions → NinUpdates → Run workflow** pour lancer le premier passage.

Le premier passage enregistre l'historique dans `seen.json` sans rien envoyer.
Ensuite, le workflow vérifie le flux toutes les 15 minutes et ne poste que les nouvelles entrées.
