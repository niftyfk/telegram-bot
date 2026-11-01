# Bot Telegram per la tua KakoBuy Spreadsheet

Progetto Python 3.12 senza dipendenze esterne. Legge il tuo foglio pubblico, estrae foto, titolo, prezzi e link, pubblica nel canale e conserva il registro su GitHub. Non richiede OpenAI, abbonamenti ChatGPT, server o un computer sempre acceso.

## 1. Crea il bot e prepara il canale

1. Su Telegram apri il bot ufficiale **[@BotFather](https://t.me/BotFather)**.
2. Invia `/newbot`, scegli nome e username che termina con `bot`.
3. Conserva il token in un gestore di password. Non incollarlo in chat, file del progetto o screenshot.
4. Per il primo test crea un canale di prova pubblico. Apri **Gestisci canale → Amministratori → Aggiungi amministratore**, seleziona il tuo bot e abilita **Pubblicare messaggi**. Gli altri permessi non sono necessari.
5. Annota lo username del canale con `@`, per esempio `@mio_canale_prova`. Il bot non deve ricevere `/start` per pubblicare in un canale.

Anche un canale privato funziona: serve il suo ID numerico `-100…` invece dello username. Per iniziare usa il canale pubblico di prova; non confondere l'ID con il link di invito. Puoi ottenere l'ID da un aggiornamento `channel_post` della Bot API dopo aver aggiunto il bot e pubblicato un messaggio; non è necessario affidare il token a servizi di terzi.

## 2. Crea il repository GitHub

1. Crea un repository, per esempio `kakobuy-telegram-bot`, con branch principale **main**.
2. Per utilizzare gratuitamente runner standard di GitHub Actions scegli **Public**. Il codice e il registro degli invii saranno pubblici; le credenziali resteranno nei Secrets. Un repository privato usa invece i minuti inclusi nel tuo piano, con eventuali costi oltre quota: non attivare spesa aggiuntiva se vuoi mantenere costo zero.
3. Copia **tutto il contenuto** di questa cartella nella radice del repository, compresa la cartella nascosta `.github`. Il file deve trovarsi in `.github/workflows/post.yml`, non in una sottocartella del progetto.
4. Se usi GitHub dal browser: **Add file → Upload files**. Se la cartella nascosta non viene caricata, crea `.github/workflows/post.yml` con **Add file → Create new file** e incollane il contenuto.
5. In **Settings → Actions → General** consenti l'esecuzione delle Actions. Se richiesto dalle impostazioni del repository, seleziona **Read and write permissions**. Il workflow richiede già `contents: write`.

Il bot aggiorna `state.json` su `main`. Regole che impediscono al bot di scrivere su `main` impediranno gli invii: prima dell'invio il registro deve poter essere salvato. Non servono Personal Access Token: GitHub fornisce `GITHUB_TOKEN` automaticamente.

## 3. Aggiungi credenziali e interruttore

Vai in **Settings → Secrets and variables → Actions**.

Nella scheda **Secrets**, crea due **Repository secrets**:

| Nome | Valore |
| --- | --- |
| `TELEGRAM_BOT_TOKEN` | Il token ottenuto da BotFather |
| `TELEGRAM_CHAT_ID` | Lo username `@…` del canale di prova, poi quello definitivo; oppure ID `-100…` |

Nella scheda **Variables**, crea una **Repository variable**:

| Nome | Valore iniziale |
| --- | --- |
| `POSTING_ENABLED` | `false` |

Il foglio indicato è già leggibile pubblicamente: **non servono chiavi Google, service account o nuovi permessi di condivisione**. Non aggiungere token al codice. Se un token viene esposto, revocalo con BotFather e sostituisci il Secret.

## 4. Lettura del tuo foglio

`config.json` contiene già l'ID del [foglio indicato](https://docs.google.com/spreadsheets/d/1ctCZTlpEOpELxgmUPvz1i_bKxN67dEL7HXtgPglTB2w/edit).

Legge già **tutte le 9 schede visibili**, incluse tutte le categorie, con `"sheet_names": []`. Gli spazi iniziali/finali nei nomi sono ignorati. Per selezionare alcune schede inserisci i nomi esatti nell'elenco. Le schede nascoste, contenenti versioni precedenti e link di altri agenti, sono escluse.

L'importazione del file Excel fornito il 1 novembre 2026 ha registrato **8.642 entrate e 6.694 prodotti unici**. Ogni prodotto ha foto, prezzo, link KakoBuy e NinjaBuy. La cartella `catalogo` contiene il catalogo deduplicato in 27 parti JSON e il riepilogo per scheda; ogni prodotto conserva tutti i riferimenti alle celle in `sources`. Il catalogo è un'istantanea del file allegato: il bot rilegge il foglio online a ogni esecuzione, quindi seguirà anche gli aggiornamenti futuri. L'estrazione verifica la presenza degli URL delle foto, non la loro effettiva disponibilità su Telegram.

Il CSV non conserva le formule `IMAGE` e i collegamenti dietro “LINK”: il bot scarica quindi un'esportazione **XLSX** e legge direttamente i dati, senza cambiare il tuo foglio.

Il lettore riconosce le intestazioni dei gruppi di prodotti anche quando le colonne sono distanziate diversamente nelle categorie. Il layout base è:

| Posizione nel gruppo | Contenuto |
| --- | --- |
| 1 | `PRODUCT`, poi titolo |
| 2 | Link affiliato NinjaBuy del prodotto, incluso nel messaggio |
| 3 | `KAKOBUY LINK`, poi collegamento del prodotto |
| 4 | Prezzo originale o testo con valuta |
| 5 | Prezzo USD; nella riga sotto EUR, anche con riferimenti ai tassi in altre schede |
| 6 | `IMAGE`, poi formula con URL della foto |

In Trending/Update le colonne titolo sono B/H/N/T; nelle altre categorie sono B/H/O/U. Il lettore trova le colonne dai titoli, senza supporre che tutti i gruppi abbiano la stessa larghezza. I valori calcolati presenti nell'esportazione vengono arrotondati a due decimali: il bot non calcola nuovi tassi di cambio. Mantiene **esattamente entrambi i link affiliati già presenti nel foglio**, senza sostituire affcode o codici NinjaBuy. In futuro righe con foto o prezzi non riconosciuti saranno segnalate nel riepilogo dei log. Un prodotto senza NinjaBuy non viene pubblicato finché non viene aggiunto il collegamento. Le formule `IMAGE` devono contenere un URL letterale, non un riferimento a un'altra cella.

### Messaggio e collegamenti finali

Ogni post contiene foto, link alla spreadsheet, articolo, prezzo, **KakoBuy Link** e **NinjaBuy Link**, entrambi cliccabili nel testo, oltre a due pulsanti. Le ultime righe sono nello stile della foto di riferimento:

```text
My social: ▶️ Haul

🎉 Register Here 🎉
```

`Haul` punta a `https://youtube.com/@niftyfk?si=NWKIVs70L5EDq0B8`; `Register Here` punta al link fornito `https://ikako.vip/r/beqp5`. `Shorts` è omesso perché non hai ancora un URL. Puoi aggiungerlo in `shorts_url` in `config.json`. Il bonus “+135$” non è incluso perché non è stato confermato per la tua promozione. L'etichetta è modificabile con `register_label`.

Se il foglio diventa privato, questo progetto smette di leggerlo. Non rendere pubblico un foglio riservato per farlo funzionare: in quel caso occorre aggiungere autenticazione Google in sola lettura. Nel tuo caso attuale non serve.

## 5. Esegui i test senza pubblicare

1. Apri **Actions → KakoBuy Telegram → Run workflow**.
2. Scegli **preview** e avvia. Nei log trovi numero di prodotti validi e anteprima del primo prodotto, con prezzo, foto e link. Non viene inviato nulla e `state.json` non cambia.
3. Avvia nuovamente con **check**. Verifica token, tipo di canale e diritto di pubblicazione, senza inviare messaggi.
4. Solo dopo i controlli, imposta la variabile `POSTING_ENABLED` a `true`.
5. Avvia con **publish** per inviare **un prodotto reale al canale di prova**. Verifica foto, titolo, valuta e pulsante. Controlla che `state.json` abbia una voce `sent` e `message_id`.
6. Ripeti **publish**: deve comparire il prodotto successivo, senza ripetere il primo.
7. Riporta `POSTING_ENABLED` a `false`, cambia `TELEGRAM_CHAT_ID` con il tuo canale definitivo e aggiungivi il bot con gli stessi permessi. Ripeti **check**.
8. Prima del passaggio definitivo, gestisci le voci dei prodotti di prova: sono registrate globalmente, quindi saranno saltate anche nel nuovo canale. Se vuoi pubblicarli nel canale definitivo, elimina **solo quelle voci di prova**, dopo aver disattivato gli invii. Non cancellare il registro di un canale già in uso.
9. Imposta `POSTING_ENABLED` a `true` per attivare il calendario. Da quel momento le esecuzioni pianificate possono pubblicare.

Il workflow esegue anche i test automatici prima di ogni esecuzione. Non effettua retry automatici degli invii e non pubblica solo testo se una foto fallisce.

## 6. Calendario e gratuità

Il calendario iniziale è `17 11,17 * * *`: **11:17 e 17:17 UTC ogni giorno**, un prodotto per esecuzione. In Italia corrisponde alle **12:17 e 18:17 in inverno**, **13:17 e 19:17 in estate**. GitHub può ritardare o saltare esecuzioni: non è un servizio con orario garantito. Il cron è attivo solo sul branch predefinito, che qui deve essere `main`.

Per cambiare frequenza modifica `post.yml`; per cambiare quantità modifica `max_posts` (1–5) in `config.json`. Per iniziare mantieni 1. Quando il catalogo è esaurito, non invia altro; nuovi prodotti validi diventano disponibili alla successiva lettura. Il bot prende i primi prodotti ancora non registrati nell'ordine del foglio, senza generare descrizioni con AI.

GitHub può disabilitare il calendario dei repository pubblici dopo 60 giorni senza attività. I commit del registro costituiscono attività, ma quando non ci sono più nuovi prodotti non vengono creati commit: controlla le Actions e riattivale se necessario. Attiva le notifiche GitHub per i workflow falliti. Per fermare tutto imposta `POSTING_ENABLED=false` oppure disabilita il workflow in Actions.

## 7. Duplicati e invii incerti

Il registro contiene hash dell'identità del prodotto, stato, riferimento della cella, data e ID del messaggio. Non contiene token. Quando possibile l'identità deriva dall'URL sorgente del prodotto (per esempio itemID Weidian): cambiare prezzo, riga o affcode non lo rende nuovo. Per link senza ID viene usato l'URL normalizzato.

Il workflow impedisce esecuzioni simultanee. Prima di chiamare Telegram il bot scrive una voce `pending` e la salva su GitHub; dopo la risposta scrive `sent`. Se il primo salvataggio non riesce, non invia. Se la rete cade o l'esecuzione viene interrotta dopo l'invio, non è possibile sapere automaticamente se Telegram abbia pubblicato: la voce rimane `pending` e blocca le successive pubblicazioni. Questo evita un retry che potrebbe creare un doppione, ma può lasciare un prodotto non pubblicato finché non intervieni.

Per risolvere:

1. Imposta `POSTING_ENABLED=false` e attendi la fine di eventuali esecuzioni.
2. Apri `state.json`, trova la voce `pending` e usa `source` per identificare il prodotto nel foglio. Controlla il canale.
3. Se il post esiste, cambia `status` in `sent` e aggiungi il suo `message_id` quando disponibile. Se non esiste, elimina **solo quella voce** per consentire un nuovo tentativo. Correggi prima eventuali foto o link guasti.
4. Salva il file e riattiva l'interruttore.

Non cancellare tutto `state.json` dopo l'avvio: farebbe ripubblicare i prodotti precedenti. Usa una sola copia del workflow per canale. Per più canali con code indipendenti servono registri separati.

## 8. Prove locali facoltative

Con Python 3.12, nella cartella del progetto:

```powershell
python -m unittest discover -s tests -v
python bot.py --mode preview
```

Per un'anteprima offline, esporta il foglio come Excel:

```powershell
python bot.py --mode preview --xlsx percorso-del-foglio.xlsx
```

La modalità preview non richiede credenziali. Per gli invii usa il workflow GitHub configurato sopra: mantiene il registro persistente e impedisce sovrapposizioni. Non eseguire una copia locale che pubblica mentre il calendario è attivo.

## Problemi comuni

| Problema | Controllo |
| --- | --- |
| HTTP 401 | Token errato o revocato: sostituisci il Secret |
| HTTP 400/403 con `check` | Username/ID canale e permessi amministratore |
| `check` passa ma `publish` dà HTTP 400 | Verifica soprattutto che l'URL foto sia pubblico e restituisca un'immagine accettata da Telegram; risolvi la voce pending |
| HTTP 429 | Limite Telegram: attendi e controlla il canale prima di risolvere la voce pending |
| Nessun invio, workflow verde | Controlla `POSTING_ENABLED`, nuovi prodotti e modalità scelta |
| Salvataggio Git fallito | Permessi contents:write, branch main, regole di protezione e modifiche concorrenti |
| Nessun prodotto valido | Layout modificato, foto/link mancanti, scheda errata o foglio non più pubblico |

Fonti ufficiali: [Telegram BotFather](https://core.telegram.org/bots/tutorial#obtain-your-bot-token), [Bot API e sendPhoto](https://core.telegram.org/bots/api#sendphoto), [costi Actions](https://docs.github.com/en/billing/concepts/product-billing/github-actions), [calendario Actions](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule), [disattivazione per inattività](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/disable-and-enable-workflows).
