# Catalogo importato — 1 novembre 2026

Fonte: file Excel `Kakobuy-NIFTY-10k+Finds · NinjaBuy (column).xlsx` fornito dall'utente.

Sono state lette tutte le 9 schede visibili. Le versioni nascoste precedenti non sono incluse.

| Scheda | Entrate valide | Prodotti aggiunti al catalogo unico |
| --- | ---: | ---: |
| Trending Now | 745 | 745 |
| Update | 1.430 | 1.390 |
| Shoes | 524 | 347 |
| Coats and Jackets | 305 | 70 |
| Hoodies and Pants | 882 | 505 |
| T-shirt and shorts | 1.926 | 1.624 |
| Accessories | 573 | 413 |
| Electronic products | 317 | 202 |
| Womens Spreadsheet | 1.940 | 1.398 |
| **Totale** | **8.642** | **6.694** |

I 6.694 prodotti sono suddivisi in `parte-01.json` … `parte-27.json`. Ogni voce contiene titolo, prezzo, URL della foto, link affiliati KakoBuy e NinjaBuy, chiave del prodotto e riferimenti alle celle. `sources` conserva anche le occorrenze dello stesso prodotto nelle altre schede. La prima occorrenza determina titolo, prezzo e foto usati nel post.

Il riepilogo completo dei controlli è in `riepilogo.json`: nessuna delle entrate riconosciute come prodotto è stata scartata per mancanza di prezzo, URL foto o uno dei due link. Sono verifiche sui dati del file; non dimostrano che tutti i siti di immagini o prodotti siano attualmente raggiungibili o che ogni foto sia accettata da Telegram.

Questa è una copia del catalogo al momento dell'importazione. Il bot legge invece il foglio online a ogni esecuzione per includere i successivi aggiornamenti. Il catalogo non è il registro degli invii: `state.json` resta vuoto finché non viene realmente pubblicato un prodotto.
