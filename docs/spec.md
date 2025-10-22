

Construire un bot Telegram de clipping vidéo multi-plateformes (YouTube, Twitch, Kick, Rumble, lien MP4 direct), offrant :
	•	Mode Auto (meilleurs moments), Mode Manuel (timestamps guidés), Mode Podcast/Chapitres.
	•	Presets 1-clic (TikTok 9:16, YouTube 16:9, Podcast).
	•	Aucun fichier stocké localement : pipeline URL → traitement cloud → URL ; le bot envoie l’URL à Telegram (c’est Telegram qui télécharge/affiche).
	•	Stockage éphémère (liens pré-signés, suppression < 24 h).
	•	Progression temps réel avec % et ETA (y compris lors de l’“envoi” à Telegram).
	•	Monétisation (Free/Pro), admin, observabilité, respect des droits.

Objectif UX : 1 clic pour débutant (bons réglages par défaut) + Mode Pro lisible pour affiner.

⸻

Contraintes dures (Must)
	1.	Zéro stockage local : tout traitement et fichiers temporaires en cloud ; sortie via URL pré-signée (TTL < 24 h).
	2.	Envoi par URL à Telegram (pas d’upload local), avec réutilisation du file_id Telegram si possible.
	3.	Progression : un seul message “statut” édité régulièrement (toutes 2–3 s) avec barre de progression, % et ETA.
	4.	Presets 1-clic + Mode Pro masqué par défaut.
	5.	Messages clairs en français, erreurs pédagogiques.
	6.	Respect droits & ToS (YouTube/Twitch/Kick), refus propre si privé/DRM.
	7.	Nettoyage systématique des temporaires cloud (lifecycle rules).

⸻

Expérience Utilisateur

Commandes
	•	/start : accueil + 5 boutons presets + bascule ⚙️ Mode Pro.
	•	/clip <URL> : AUTO avec preset par défaut (TikTok 3×30s + subs auto).
	•	/select <URL> : MANUEL (commande assistée par boutons).
	•	/status : affiche avancement (file d’attente + job courant).
	•	/plans : voir quotas, avantages Pro, upgrade.
	•	/help : tutoriel court + exemples.
	•	/cancel : annuler job courant.

Presets 1-clic (défauts intelligents)
	1.	Auto TikTok (3×30s) : 9:16, 1080p (fallback 720p), 30 fps, subs auto on, safe zones visage/texte, skip intro/outro 5s, diversité ON.
	2.	Auto TikTok (1×60s) : 9:16, 60 s, subs auto on.
	3.	Auto YouTube (1×60s) : 16:9, 1080p, subs off.
	4.	Podcast (3×45s + subs) : 9:16, subs on + diarisation A/B, music ducking on.
	5.	Manuel : découpe par boutons (voir plus bas).

Mode MANUEL (assisté, sans jargon)

Après /select <URL>, afficher durée totale + clavier inline :
	•	⏮ -10s -1s +1s +10s ⏭
	•	🎯 Fixer début / 🎯 Fixer fin
	•	▶️ Aperçu 10s
	•	➕ Ajouter un clip (jusqu’à 5)
	•	✅ Confirmer rendu

Protection anti-coupure de mots : marge 300 ms.

⸻

Options PRO (affichées si “Mode Pro”)
	•	clips : nombre de clips (def 3, min 1, max 10)
	•	durée : secondes par clip (def 30, 5–120)
	•	format : tiktok (9:16) | square (1:1) | youtube (16:9) (def tiktok)
	•	subs : auto | on | off (def auto)
	•	lang : auto | fr | en | es… (def auto)
	•	style_subs : clean | karaoke | compact (def clean)
	•	watermark : on/off + texte @handle (on en Free, off en Pro)
	•	music_ducking : on/off (on en Podcast)
	•	intro_outro_skip : secondes (def 5)
	•	ai_pick (AUTO) : on/off (def on)
	•	diversité_clips : on/off (def on)
	•	safe_faces_text : on/off (def on)
	•	max_durée_source : seuil d’avertissement (ex. 3 h)

Raccourcis lisibles possibles :
/clip <URL> clips=5 durée=45 format=square subs=off lang=en

⸻

AUTO “Meilleurs moments” (simple & fiable)

Score global (pondérations douces, non exposées à l’utilisateur) basé sur :
	•	Énergie audio (pics/variations),
	•	Rythme de parole (accélérations nettes),
	•	Changements de plans (détection cut),
	•	Évitement des silences,
	•	Indices sociaux si dispo (pics chat, chapitres YouTube),
	•	Mots-clés détectés dans les sous-titres (ex. “incroyable”, “wtf”, “regarde ça”, rires).

Diversité : écarter segments trop proches (≥10 s).
Coupe naturelle : ajuster aux pauses (max +20% au-delà de la durée cible) pour finir la phrase.

⸻

Sous-titres & Audio
	•	Subs : auto/on/off ; détection langue sinon lang= imposée.
	•	Style clean par défaut ; karaoké léger optionnel (highlight mots).
	•	Diarisation simple (A/B) en mode Podcast.
	•	Normalisation audio ~-14 LUFS ; limiteur doux ; music ducking optionnel.

⸻

Formats & rendu
	•	Formats : 9:16 (TikTok), 1:1 (square), 16:9 (YouTube).
	•	Résolution : 1080p par défaut (fallback 720p si source faible).
	•	Framerate : conserver si raisonnable, sinon 30 fps.
	•	Safe zones visage/texte ; recentre auto (auto-crop) pour 9:16.

⸻

Livraison — anti-local (clé)
	•	Jamais d’écriture locale.
	•	Pipeline URL→URL : ingestion par URL, traitement cloud, bucket éphémère (règle de cycle de vie Delete < 24 h), URL pré-signée.
	•	Le bot envoie l’URL à Telegram (qui télécharge et poste).
	•	Fournir lien de téléchargement (expire < 24 h).
	•	Si re-envoi identique : réutiliser file_id Telegram.

⸻

Progression & ETA (rendu + envoi Telegram)

Un message unique de statut, édité toutes 2–3 s, avec barre, %, ETA, et boutons : 🔕 Mute, 📊 Détails, ⏩ Priorité Pro, ❌ Annuler.

Phases & % guides
	1.	Analyse (0–10%) – métadonnées, durée, langue.
	2.	Auto-pick (10–30%) – scoring meilleurs moments.
	3.	Sous-titres (30–60%) – ASR/diarisation/stylage.
	4.	Export (60–90%) – transcodage, recadrage, audio.
	5.	Livraison (90–100%) – pré-upload cloud + envoi à Telegram.

ETA = travail restant / débit estimé, lissé par moyenne mobile (s’adapte à la complexité et à l’historique).

Pendant “envoi à Telegram”
	•	Afficher Pré-upload cloud : % réel (octets vers stockage).
	•	Puis Envoi à Telegram : %/ETA estimés (taille fichier × débit moyen appris par région/heure).
	•	Envoyer sendChatAction=upload_video régulièrement.
	•	Si Telegram termine plus vite : saut à 100% + “Terminé ✅”.

Exemples de messages
	•	Analyse… 7% · ETA 3:40
	•	Auto-pick… 22% · ETA 2:55
	•	Sous-titres (FR auto)… 48% · ETA 2:02
	•	Export 1080p 9:16… 78% · ETA 0:55
	•	Livraison (pré-upload cloud)… 88% · ETA 0:35
	•	Envoi à Telegram… 95% · ETA 0:18
	•	Terminé ✅ — liens valables 24 h

Mode 📊 Détails : temps/phase, résolution/fps, durée totale, poids estimé vs réel, par clip (Clip # — durée — poids — temps).

Edge cases
	•	Stall > 60 s : “Ralentissement détecté, recalcul ETA…”.
	•	Annulation : marquer Annulé ❌, nettoyer temporaires.
	•	Échec : message clair + bouton Réessayer.

⸻


⸻

Admin & Observabilité
	•	Mini dashboard (commande admin) : jobs, erreurs, remboursements, ban/unban, ajuster quotas.
	•	Logs JSON par job_id (phase, timings, tailles) ; alertes sur erreurs répétées.
	•	Statistiques : temps moyen par phase, % échec, coût estimé/clip, débit moyen “envoi Telegram”.

⸻

Sécurité, droits, conformité
	•	Validation d’URL stricte ; refuser fichiers douteux/EXE.
	•	Alerte droits : l’utilisateur confirme qu’il a l’autorisation de clipper.
	•	Privé/DRM : refuser proprement (message pédagogique).
	•	NSFW optionnel : avertir/masquer.
	•	RGPD : commande pour supprimer historique et données.

⸻

Performance & coûts (budgets)
	•	Cible rendu 30–60 s : < 90 s/clip.
	•	Réduire ré-encodages ; couper en “copy” si possible (keyframes).
	•	Fallback 720p si ressources limitées ; limiter framerate à 30.
	•	Nettoyage agressif des temporaires, TTL < 24 h.

⸻

Cas limites & UX
	•	Source > 3 h : proposer mode Podcast/Chapitres ou réduire clips/durée.
	•	Audio faible : proposer gain auto.
	•	Langue inconnue : inviter lang= ou laisser auto.
	•	Échec plateforme : message clair + Réessayer.

⸻

Exemples d’utilisation
	•	@bot /clip https://youtu.be/abcd (Auto TikTok 3×30s, subs auto)
	•	@bot /clip https://www.twitch.tv/videos/12345 clips=5 durée=45 format=square subs=off
	•	@bot /select https://kick.com/video/999 (Manuel assisté)

⸻

Tests d’acceptation (obligatoires)
	•	✅ /clip <URL YouTube> → 3×30s 9:16 + subs auto, sans stockage local ; progression % + ETA à chaque phase ; livraison via URL + message final dans Telegram.
	•	✅ /select → timeline boutons, aperçu 10 s, confirmation, rendu propre.
	•	✅ Liens pré-signés expirant < 24 h ; file_id réutilisé si re-envoi identique.
	•	✅ Erreurs (privé/DRM/URL invalide) claires ; bouton Réessayer.
	•	✅ Plans Free/Pro fonctionnels, watermark on/off selon plan.
	•	✅ /status montre file + job courant avec %/ETA.

⸻

Notes d’implémentation (sans code)
	•	Ingestion par URL, traitement cloud, stockage éphémère (S3/Backblaze/Bunny/Cloudflare R2) avec règle Delete < 24 h, URL pré-signées.
	•	Envoi à Telegram par URL (pas d’upload local).
	•	ASR type Whisper (ou équivalent) pour sous-titres ; diarisation simple.
	•	sendChatAction=upload_video pendant “envoi à Telegram”.
	•	Un seul message statut édité périodiquement (2–3 s), bouton 🔕 Mute pour ne garder que le message final à 100%.

⸻

But de ce prompt : livrer un bot simple, fiable, rapide, avec defaults excellents, options Pro nettes, progression %/ETA réaliste, anti-local, monétisable et propre légalement.
Si un choix est ambigu, choisir un défaut intelligent (9:16, 30 s, subs auto, diversité on).
